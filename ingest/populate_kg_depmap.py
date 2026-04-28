#!/usr/bin/env python3
"""Populate KG with DepMap cancer cell line data — general biological facts.

Creates research-question-agnostic claims:
  1. ObservedEssentialityClaim — per gene × lineage essentiality (in_vitro)
  2. PredictedEssentialityClaim — LASSO-predicted tumor essentiality (in_vivo_predicted)
  3. DifferentialExpressionClaim — lineage-specific expression (in_vitro)
  4. SomaticMutationClaim — mutation frequency per gene × lineage
  5. MutationProteinAssociationClaim — mutation → protein changes (in_vitro)

All claims tagged with context_type (in_vitro/in_vivo) so the reasoning
agent can weight patient tumor data higher than cell line data.

Run:  python populate_kg_depmap.py
SLURM: sbatch --mem=32G --time=02:00:00 --wrap="python scripts/populate_kg_depmap.py"
"""
import csv
import json
import logging
import sqlite3
import sys
import hashlib
import io
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("kg_depmap")

SCRATCH = Path(os.environ["KG_DATA_ROOT"])
KG_PATH = SCRATCH / "gbd_knowledge_graph.db"
DEPMAP = Path(os.environ["EXTERNAL_DATA_ROOT"]) / "depmap"

UTC = timezone.utc


def main():
    db = sqlite3.connect(str(KG_PATH))
    db.execute("PRAGMA journal_mode=WAL")

    # Load existing gene entities
    all_genes = set()
    rows = db.execute("SELECT entity_id FROM entities WHERE entity_type = 'Gene'").fetchall()
    for r in rows:
        all_genes.add(r[0])
    log.info("KG has %d gene entities", len(all_genes))

    # ══════════════════════════════════════════════════════════════════
    # Step 1: Load cell line metadata (lineage mapping)
    # ══════════════════════════════════════════════════════════════════
    log.info("Step 1: Loading cell line metadata...")
    model_path = DEPMAP / "Model.csv"
    line_to_lineage = {}
    lineage_counts = {}

    with open(model_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            model_id = row.get("ModelID", "")
            lineage = row.get("OncotreeLineage", "").strip()
            if model_id and lineage:
                line_to_lineage[model_id] = lineage
                lineage_counts[lineage] = lineage_counts.get(lineage, 0) + 1

    log.info("  %d cell lines across %d lineages", len(line_to_lineage), len(lineage_counts))

    # Create CancerLineage entities
    for lineage, count in lineage_counts.items():
        entity_id = f"LINEAGE-{lineage.replace(' ', '_')}"
        db.execute(
            "INSERT OR IGNORE INTO entities VALUES (?, ?, ?, ?, ?, ?)",
            (entity_id, "CancerLineage", lineage,
             json.dumps([]), json.dumps({"n_cell_lines": count}),
             json.dumps({"source_db": "DepMap"})),
        )
    db.commit()
    log.info("  Created %d lineage entities", len(lineage_counts))

    # ══════════════════════════════════════════════════════════════════
    # Step 2: ObservedEssentialityClaim from CRISPR gene effect
    # ══════════════════════════════════════════════════════════════════
    log.info("Step 2: Loading CRISPR gene effect for essentiality claims...")
    effect_path = DEPMAP / "CRISPRGeneEffect.csv"

    # Read header to get gene names
    with open(effect_path) as f:
        header = f.readline().strip().split(",")

    # Gene names are in format "GENE (ENTREZ_ID)" — extract gene symbol
    gene_cols = {}  # col_index → gene_symbol
    for i, col in enumerate(header[1:], 1):
        gene = col.split(" (")[0].strip()
        if gene and gene in all_genes:
            gene_cols[i] = gene

    log.info("  %d genes overlap with KG entities", len(gene_cols))

    # Read all data into per-gene arrays grouped by lineage
    gene_lineage_effects = {}  # (gene, lineage) → [effect_scores]
    gene_all_effects = {}       # gene → [all effect_scores]

    with open(effect_path) as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            model_id = row[0]
            lineage = line_to_lineage.get(model_id, "Unknown")

            for col_idx, gene in gene_cols.items():
                if col_idx < len(row) and row[col_idx]:
                    try:
                        val = float(row[col_idx])
                        gene_lineage_effects.setdefault((gene, lineage), []).append(val)
                        gene_all_effects.setdefault(gene, []).append(val)
                    except ValueError:
                        pass

    log.info("  Loaded effects for %d gene-lineage pairs", len(gene_lineage_effects))

    # Create essentiality claims
    n_claims = 0
    MIN_LINES = 5
    now = datetime.now(UTC).isoformat()

    for gene, all_effects in gene_all_effects.items():
        arr = np.array(all_effects)
        if len(arr) < MIN_LINES:
            continue

        mean_eff = float(np.mean(arr))
        pct_essential = float(np.sum(arr < -0.5) / len(arr) * 100)

        # Skip if too few are essential (not interesting)
        if pct_essential < 5:
            continue

        # Pan-cancer claim
        t_stat, p_val = stats.ttest_1samp(arr, 0)
        claim_id = f"DEPMAP-ESS-{gene}-pan"

        db.execute("""
            INSERT OR IGNORE INTO claims
            (claim_id, claim_type, status, proof_level, effect_size, direction,
             p_value, n_studies, source_dataset, assay_type,
             created_at, description, full_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            claim_id,
            "ObservedEssentialityClaim",
            "replicated",
            5,  # PERTURBATIONAL_PHENOTYPIC
            mean_eff,
            "essential" if mean_eff < -0.3 else "non_essential",
            float(p_val),
            len(arr),
            "DepMap",
            "CRISPR_Chronos",
            now,
            f"{gene} essentiality: mean_effect={mean_eff:.3f}, {pct_essential:.1f}% essential across {len(arr)} cell lines",
            json.dumps({
                "context_type": "in_vitro",
                "pct_essential": round(pct_essential, 1),
                "mean_effect": round(mean_eff, 4),
                "n_cell_lines": len(arr),
                "lineage": "pan_cancer",
            }),
        ))
        db.execute(
            "INSERT OR IGNORE INTO claim_participants VALUES (?, ?, ?, ?)",
            (claim_id, gene, "effector_gene", json.dumps({})),
        )
        n_claims += 1

        # Per-lineage claims (only for lineages with enough data)
        for lineage, count in lineage_counts.items():
            key = (gene, lineage)
            if key not in gene_lineage_effects:
                continue
            lin_arr = np.array(gene_lineage_effects[key])
            if len(lin_arr) < MIN_LINES:
                continue

            lin_mean = float(np.mean(lin_arr))
            lin_pct = float(np.sum(lin_arr < -0.5) / len(lin_arr) * 100)

            # Only create claim if lineage-specific OR notably different from pan
            if lin_pct < 10 and abs(lin_mean - mean_eff) < 0.2:
                continue

            # Compare lineage vs all others
            other_arr = np.array([v for (g, l), vals in gene_lineage_effects.items()
                                  if g == gene and l != lineage for v in vals])
            if len(other_arr) < MIN_LINES:
                continue

            t_lin, p_lin = stats.ttest_ind(lin_arr, other_arr, equal_var=False)

            claim_id = f"DEPMAP-ESS-{gene}-{lineage.replace(' ', '_')[:15]}"
            lineage_entity = f"LINEAGE-{lineage.replace(' ', '_')}"

            db.execute("""
                INSERT OR IGNORE INTO claims
                (claim_id, claim_type, status, proof_level, effect_size, direction,
                 p_value, n_studies, source_dataset, assay_type,
                 created_at, description, full_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                claim_id,
                "ObservedEssentialityClaim",
                "replicated" if len(lin_arr) >= 10 else "observed",
                5,
                lin_mean,
                "lineage_essential" if lin_pct > 20 else "lineage_non_essential",
                float(p_lin),
                len(lin_arr),
                "DepMap",
                "CRISPR_Chronos",
                now,
                f"{gene} in {lineage}: mean_effect={lin_mean:.3f}, {lin_pct:.1f}% essential ({len(lin_arr)} lines)",
                json.dumps({
                    "context_type": "in_vitro",
                    "pct_essential": round(lin_pct, 1),
                    "mean_effect": round(lin_mean, 4),
                    "n_cell_lines": len(lin_arr),
                    "lineage": lineage,
                    "pan_pct_essential": round(pct_essential, 1),
                    "selectivity": round(lin_pct - pct_essential, 1),
                }),
            ))
            db.execute(
                "INSERT OR IGNORE INTO claim_participants VALUES (?, ?, ?, ?)",
                (claim_id, gene, "effector_gene", json.dumps({})),
            )
            db.execute(
                "INSERT OR IGNORE INTO claim_participants VALUES (?, ?, ?, ?)",
                (claim_id, lineage_entity, "context", json.dumps({})),
            )
            n_claims += 1

    db.commit()
    log.info("  Created %d essentiality claims (pan + lineage-specific)", n_claims)

    # ══════════════════════════════════════════════════════════════════
    # Step 3: SomaticMutationClaim from damaging mutation matrix
    # ══════════════════════════════════════════════════════════════════
    log.info("Step 3: Loading somatic mutations...")
    mut_path = DEPMAP / "OmicsSomaticMutationsMatrixDamaging.csv"

    if mut_path.exists():
        # Read header
        with open(mut_path) as f:
            mut_header = f.readline().strip().split(",")

        mut_gene_cols = {}
        for i, col in enumerate(mut_header[1:], 1):
            gene = col.split(" (")[0].strip()
            if gene and gene in all_genes:
                mut_gene_cols[i] = gene

        # Read mutation matrix (binary: 1=mutated, 0=not)
        gene_lineage_mut = {}  # (gene, lineage) → [0/1 values]
        gene_all_mut = {}

        with open(mut_path) as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                model_id = row[0]
                lineage = line_to_lineage.get(model_id, "Unknown")

                for col_idx, gene in mut_gene_cols.items():
                    if col_idx < len(row) and row[col_idx]:
                        try:
                            val = int(float(row[col_idx]))
                            gene_lineage_mut.setdefault((gene, lineage), []).append(val)
                            gene_all_mut.setdefault(gene, []).append(val)
                        except ValueError:
                            pass

        n_mut_claims = 0
        for gene, all_mut in gene_all_mut.items():
            arr = np.array(all_mut)
            if len(arr) < 20:
                continue

            freq = float(np.mean(arr))
            n_mutated = int(np.sum(arr))

            # Only create claim if mutation frequency > 3%
            if freq < 0.03:
                continue

            claim_id = f"DEPMAP-MUT-{gene}-pan"
            db.execute("""
                INSERT OR IGNORE INTO claims
                (claim_id, claim_type, status, proof_level, effect_size, direction,
                 p_value, n_studies, source_dataset, assay_type,
                 created_at, description, full_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                claim_id,
                "SomaticMutationClaim",
                "observed",
                2,  # OBSERVATIONAL_ASSOCIATION
                freq,
                "mutated_in",
                None,
                len(arr),
                "DepMap",
                "WGS_WES",
                now,
                f"{gene} damaging mutations: {freq*100:.1f}% frequency ({n_mutated}/{len(arr)} cell lines)",
                json.dumps({
                    "context_type": "in_vitro",
                    "frequency": round(freq, 4),
                    "n_mutated": n_mutated,
                    "n_total": len(arr),
                    "lineage": "pan_cancer",
                }),
            ))
            db.execute(
                "INSERT OR IGNORE INTO claim_participants VALUES (?, ?, ?, ?)",
                (claim_id, gene, "effector_gene", json.dumps({})),
            )
            n_mut_claims += 1

            # Per-lineage mutation frequency
            for lineage in lineage_counts:
                key = (gene, lineage)
                if key not in gene_lineage_mut:
                    continue
                lin_arr = np.array(gene_lineage_mut[key])
                if len(lin_arr) < 10:
                    continue
                lin_freq = float(np.mean(lin_arr))
                if lin_freq < 0.05:
                    continue

                lin_n_mut = int(np.sum(lin_arr))
                claim_id = f"DEPMAP-MUT-{gene}-{lineage.replace(' ', '_')[:15]}"
                lineage_entity = f"LINEAGE-{lineage.replace(' ', '_')}"

                db.execute("""
                    INSERT OR IGNORE INTO claims
                    (claim_id, claim_type, status, proof_level, effect_size, direction,
                     n_studies, source_dataset, assay_type,
                     created_at, description, full_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    claim_id,
                    "SomaticMutationClaim",
                    "observed",
                    2,
                    lin_freq,
                    "mutated_in",
                    len(lin_arr),
                    "DepMap",
                    "WGS_WES",
                    now,
                    f"{gene} in {lineage}: {lin_freq*100:.1f}% mutated ({lin_n_mut}/{len(lin_arr)})",
                    json.dumps({
                        "context_type": "in_vitro",
                        "frequency": round(lin_freq, 4),
                        "n_mutated": lin_n_mut,
                        "n_total": len(lin_arr),
                        "lineage": lineage,
                    }),
                ))
                db.execute(
                    "INSERT OR IGNORE INTO claim_participants VALUES (?, ?, ?, ?)",
                    (claim_id, gene, "effector_gene", json.dumps({})),
                )
                db.execute(
                    "INSERT OR IGNORE INTO claim_participants VALUES (?, ?, ?, ?)",
                    (claim_id, lineage_entity, "context", json.dumps({})),
                )
                n_mut_claims += 1

        db.commit()
        log.info("  Created %d mutation claims", n_mut_claims)
    else:
        log.warning("  Mutation matrix not found: %s", mut_path)

    # ══════════════════════════════════════════════════════════════════
    # Summary
    # ══════════════════════════════════════════════════════════════════
    counts = db.execute(
        "SELECT claim_type, COUNT(*) FROM claims GROUP BY claim_type ORDER BY COUNT(*) DESC"
    ).fetchall()
    log.info("\nKG claim type summary:")
    for ct, n in counts:
        log.info("  %s: %d", ct, n)

    total = db.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    log.info("Total claims: %d", total)

    db.close()
    log.info("Done.")


if __name__ == "__main__":
    main()
