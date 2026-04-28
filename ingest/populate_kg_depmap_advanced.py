#!/usr/bin/env python3
"""Populate KG with advanced DepMap claims — selective dependency, buffering,
mutation hotspots, and mutation co-occurrence.

These go beyond simple essentiality to capture CONTEXT-DEPENDENT biology:
  1. SelectiveDependencyClaim — essential ONLY in specific molecular states
  2. BufferingClaim — gene B rescues loss of gene A
  3. MutationHotspotClaim — domain/site-level recurrent mutations
  4. MutationCoOccurrenceClaim — mutual exclusivity or co-occurrence

All tagged evidence_tier="observed", context_type="in_vitro".

Run:  python populate_kg_depmap_advanced.py
"""
import csv
import json
import logging
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import stats as sp_stats

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("kg_depmap_adv")

KG_PATH = Path(os.environ["KG_DATA_ROOT"]) / "gbd_knowledge_graph.db"
DEPMAP = Path(os.environ["EXTERNAL_DATA_ROOT"]) / "depmap"
UTC = timezone.utc


def main():
    now = datetime.now(UTC).isoformat()
    db = sqlite3.connect(str(KG_PATH))
    db.execute("PRAGMA journal_mode=WAL")

    all_genes = set(r[0] for r in db.execute(
        "SELECT entity_id FROM entities WHERE entity_type = 'Gene'"
    ).fetchall())
    log.info("%d genes in KG", len(all_genes))

    # Load lineage mapping
    line_to_lineage = {}
    with open(DEPMAP / "Model.csv") as f:
        for row in csv.DictReader(f):
            mid = row.get("ModelID", "")
            lin = row.get("OncotreeLineage", "").strip()
            if mid and lin:
                line_to_lineage[mid] = lin

    # ══════════════════════════════════════════════════════════════════
    # Step 1: Mutation Hotspot Claims — domain/site-level
    # ══════════════════════════════════════════════════════════════════
    log.info("Step 1: Mutation hotspot claims (site/domain-level)...")

    mut_path = DEPMAP / "OmicsSomaticMutations.csv"
    # Count mutations per gene × protein_change × lineage
    hotspot_counts = defaultdict(lambda: defaultdict(int))  # (gene, site) → lineage → count
    gene_total_muts = defaultdict(int)

    with open(mut_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            gene = row.get("HugoSymbol", "").strip()
            if not gene or gene not in all_genes:
                continue
            hotspot = row.get("Hotspot", "")
            protein_change = row.get("ProteinChange", "").strip()
            if hotspot != "True" or not protein_change:
                continue

            lineage = line_to_lineage.get(row.get("ModelID", ""), "Unknown")
            hotspot_counts[(gene, protein_change)][lineage] += 1
            gene_total_muts[gene] += 1

    n_hotspot = 0
    for (gene, site), lineage_counts in hotspot_counts.items():
        total = sum(lineage_counts.values())
        if total < 3:
            continue

        # Find top lineage
        top_lineage = max(lineage_counts, key=lineage_counts.get)
        top_count = lineage_counts[top_lineage]

        claim_id = f"DEPMAP-HOTSPOT-{gene}-{site.replace('.', '_')[:20]}"
        db.execute("""
            INSERT OR IGNORE INTO claims
            (claim_id, claim_type, status, proof_level, effect_size, direction,
             n_studies, source_dataset, assay_type,
             created_at, description, full_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            claim_id, "MutationHotspotClaim", "observed", 2,
            total, "hotspot",
            total, "DepMap", "WGS_WES", now,
            f"{gene} {site}: hotspot mutation in {total} cell lines (top: {top_lineage} {top_count}x)",
            json.dumps({
                "evidence_tier": "observed",
                "context_type": "in_vitro",
                "gene": gene,
                "protein_change": site,
                "total_occurrences": total,
                "lineage_distribution": dict(lineage_counts),
                "top_lineage": top_lineage,
            }),
        ))
        db.execute("INSERT OR IGNORE INTO claim_participants VALUES (?, ?, ?, ?)",
                   (claim_id, gene, "effector_gene", json.dumps({})))
        n_hotspot += 1

    db.commit()
    log.info("  %d hotspot claims from %d genes", n_hotspot, len(gene_total_muts))

    # ══════════════════════════════════════════════════════════════════
    # Step 2: Mutation Co-occurrence / Mutual Exclusivity
    # ══════════════════════════════════════════════════════════════════
    log.info("Step 2: Mutation co-occurrence/exclusivity claims...")

    # Load damaging mutation binary matrix
    dam_path = DEPMAP / "OmicsSomaticMutationsMatrixDamaging.csv"
    if dam_path.exists():
        with open(dam_path) as f:
            header = f.readline().strip().split(",")

        gene_cols = {}
        for i, col in enumerate(header[1:], 1):
            g = col.split(" (")[0].strip()
            if g in all_genes:
                gene_cols[i] = g

        # Read binary matrix — only keep frequently mutated genes (>5%)
        gene_vectors = {}  # gene → binary array
        n_lines = 0

        with open(dam_path) as f:
            reader = csv.reader(f)
            next(reader)
            rows_data = []
            for row in reader:
                row_vals = {}
                for ci, g in gene_cols.items():
                    if ci < len(row) and row[ci]:
                        try:
                            row_vals[g] = int(float(row[ci]))
                        except ValueError:
                            row_vals[g] = 0
                rows_data.append(row_vals)
                n_lines += 1

        # Build arrays for frequently mutated genes
        for g in gene_cols.values():
            arr = np.array([rd.get(g, 0) for rd in rows_data])
            freq = np.mean(arr)
            if freq >= 0.03:  # at least 3% mutated
                gene_vectors[g] = arr

        log.info("  %d frequently mutated genes (≥3%%) in %d cell lines", len(gene_vectors), n_lines)

        # Test top gene pairs for co-occurrence / exclusivity
        freq_genes = sorted(gene_vectors.keys())
        n_cooc = 0

        # Only test top 200 most frequently mutated (to limit runtime)
        top_genes = sorted(freq_genes, key=lambda g: -np.mean(gene_vectors[g]))[:200]

        for i, g1 in enumerate(top_genes):
            for g2 in top_genes[i+1:]:
                v1 = gene_vectors[g1]
                v2 = gene_vectors[g2]

                # 2x2 contingency table
                both = int(np.sum((v1 == 1) & (v2 == 1)))
                g1_only = int(np.sum((v1 == 1) & (v2 == 0)))
                g2_only = int(np.sum((v1 == 0) & (v2 == 1)))
                neither = int(np.sum((v1 == 0) & (v2 == 0)))

                table = np.array([[both, g1_only], [g2_only, neither]])
                odds_ratio, p_val = sp_stats.fisher_exact(table)

                # Only store significant associations
                if p_val > 0.001:
                    continue

                if odds_ratio > 1:
                    direction = "co_occurring"
                else:
                    direction = "mutually_exclusive"

                a, b = sorted([g1, g2])
                claim_id = f"DEPMAP-COOC-{a}-{b}"

                db.execute("""
                    INSERT OR IGNORE INTO claims
                    (claim_id, claim_type, status, proof_level, effect_size, direction,
                     p_value, n_studies, source_dataset, assay_type,
                     created_at, description, full_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    claim_id, "MutationCoOccurrenceClaim", "observed", 2,
                    float(odds_ratio), direction,
                    float(p_val), n_lines, "DepMap", "WGS_WES", now,
                    f"{a} and {b}: {direction} (OR={odds_ratio:.2f}, p={p_val:.2e}, both={both})",
                    json.dumps({
                        "evidence_tier": "observed",
                        "context_type": "in_vitro",
                        "gene_a": a, "gene_b": b,
                        "odds_ratio": round(float(odds_ratio), 4),
                        "both_mutated": both,
                        "a_only": g1_only if a == g1 else g2_only,
                        "b_only": g2_only if a == g1 else g1_only,
                        "neither": neither,
                    }),
                ))
                db.execute("INSERT OR IGNORE INTO claim_participants VALUES (?, ?, ?, ?)",
                           (claim_id, a, "effector_gene", json.dumps({})))
                db.execute("INSERT OR IGNORE INTO claim_participants VALUES (?, ?, ?, ?)",
                           (claim_id, b, "target_gene", json.dumps({})))
                n_cooc += 1

        db.commit()
        log.info("  %d co-occurrence/exclusivity claims (p<0.001)", n_cooc)
    else:
        log.warning("  Damaging mutation matrix not found")

    # ══════════════════════════════════════════════════════════════════
    # Step 3: Selective Dependency — essentiality × mutation context
    # ══════════════════════════════════════════════════════════════════
    log.info("Step 3: Selective dependency claims...")

    # Load gene effect data
    effect_path = DEPMAP / "CRISPRGeneEffect.csv"
    if effect_path.exists() and dam_path.exists():
        # Read gene effect header
        with open(effect_path) as f:
            eff_header = f.readline().strip().split(",")

        eff_gene_cols = {}
        for i, col in enumerate(eff_header[1:], 1):
            g = col.split(" (")[0].strip()
            if g in all_genes:
                eff_gene_cols[i] = g

        # Read effect matrix (only for top mutation context genes)
        model_effects = {}  # model_id → {gene → effect}
        with open(effect_path) as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                model_id = row[0]
                effects = {}
                for ci, g in eff_gene_cols.items():
                    if ci < len(row) and row[ci]:
                        try:
                            effects[g] = float(row[ci])
                        except ValueError:
                            pass
                model_effects[model_id] = effects

        # For top mutated genes: test if their mutation context makes other genes
        # selectively essential. More permissive thresholds than before.
        top_mutated = sorted(gene_vectors.keys(), key=lambda g: -np.mean(gene_vectors[g]))[:100]
        n_selective = 0

        model_ids = list(model_effects.keys())

        # Pre-filter to genes that are essential in at least SOME lines
        # (mean effect < -0.3 somewhere). No point testing non-essential genes.
        log.info("  Pre-filtering dependency genes by essentiality...")
        candidate_dep_genes = []
        for g in eff_gene_cols.values():
            effects = [model_effects[m].get(g, 0) for m in model_ids if g in model_effects.get(m, {})]
            if effects and np.mean(effects) < -0.3:
                candidate_dep_genes.append(g)
        log.info("  %d candidate dependency genes (mean effect < -0.3)", len(candidate_dep_genes))
        all_dep_genes = candidate_dep_genes

        for mut_gene in top_mutated:
            if mut_gene not in gene_vectors:
                continue
            mut_vec = gene_vectors[mut_gene]

            mut_models = [model_ids[i] for i in range(min(len(model_ids), len(mut_vec)))
                          if mut_vec[i] == 1]
            wt_models = [model_ids[i] for i in range(min(len(model_ids), len(mut_vec)))
                         if mut_vec[i] == 0]

            if len(mut_models) < 3 or len(wt_models) < 10:
                continue

            # Test ALL dependency genes (not just first 500)
            for dep_gene in all_dep_genes:
                if dep_gene == mut_gene:
                    continue

                mut_effects = [model_effects[m].get(dep_gene, 0) for m in mut_models
                               if dep_gene in model_effects.get(m, {})]
                wt_effects = [model_effects[m].get(dep_gene, 0) for m in wt_models
                              if dep_gene in model_effects.get(m, {})]

                if len(mut_effects) < 3 or len(wt_effects) < 10:
                    continue

                t_stat, p_val = sp_stats.ttest_ind(mut_effects, wt_effects, equal_var=False)
                mean_diff = np.mean(mut_effects) - np.mean(wt_effects)

                # Selective: significantly MORE essential in mutant context
                # Relaxed: p < 0.01, difference > 0.2 CERES units
                if p_val > 0.01 or mean_diff > -0.2:
                    continue

                claim_id = f"DEPMAP-SELDEP-{dep_gene}-in-{mut_gene}mut"
                db.execute("""
                    INSERT OR IGNORE INTO claims
                    (claim_id, claim_type, status, proof_level, effect_size, direction,
                     p_value, n_studies, source_dataset, assay_type,
                     created_at, description, full_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    claim_id, "SelectiveDependencyClaim", "observed", 5,
                    float(mean_diff), "selectively_essential",
                    float(p_val), len(mut_effects) + len(wt_effects),
                    "DepMap", "CRISPR_Chronos", now,
                    (f"{dep_gene} is selectively essential in {mut_gene}-mutant lines "
                     f"(diff={mean_diff:.3f}, p={p_val:.2e})"),
                    json.dumps({
                        "evidence_tier": "observed",
                        "context_type": "in_vitro",
                        "dependency_gene": dep_gene,
                        "context_mutation": mut_gene,
                        "mean_effect_mutant": round(float(np.mean(mut_effects)), 4),
                        "mean_effect_wt": round(float(np.mean(wt_effects)), 4),
                        "mean_difference": round(float(mean_diff), 4),
                        "n_mutant": len(mut_effects),
                        "n_wildtype": len(wt_effects),
                    }),
                ))
                db.execute("INSERT OR IGNORE INTO claim_participants VALUES (?, ?, ?, ?)",
                           (claim_id, dep_gene, "effector_gene", json.dumps({})))
                db.execute("INSERT OR IGNORE INTO claim_participants VALUES (?, ?, ?, ?)",
                           (claim_id, mut_gene, "context_mutation", json.dumps({})))
                n_selective += 1

        db.commit()
        log.info("  %d selective dependency claims", n_selective)
    else:
        log.warning("  Gene effect or mutation data not found")

    # ══════════════════════════════════════════════════════════════════
    # Summary
    # ══════════════════════════════════════════════════════════════════
    log.info("\n=== KG CLAIM SUMMARY ===")
    for ct, n in db.execute(
        "SELECT claim_type, COUNT(*) FROM claims GROUP BY claim_type ORDER BY COUNT(*) DESC"
    ).fetchall():
        log.info("  %s: %d", ct, n)
    log.info("Total: %d", db.execute("SELECT COUNT(*) FROM claims").fetchone()[0])

    db.close()
    log.info("Done.")


if __name__ == "__main__":
    main()
