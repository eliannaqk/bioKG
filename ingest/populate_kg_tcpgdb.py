#!/usr/bin/env python3
"""Populate KG with TCPGdb T-cell CRISPR screen meta-analysis data.

Data from TCPGdb tdtool pipeline — real CRISPR screen meta-analysis:
  1. phenotype_rankings.csv → CRISPRPhenotypeClaim (272K gene×phenotype results)
  2. concordance_analysis.csv → Bidirectionally validated edges (37K CRISPRi/CRISPRa pairs)
  3. cross_phenotype_comparison.csv → Gene essentiality categories (25K genes)
  4. screen_level_data.csv → Evidence (506K per-screen z-scores)

Maps to KG:
  - Backbone edges: Gene-essential-for-ImmunePhenotype (validated drivers/suppressors)
  - Claims: CRISPRPhenotypeClaim with full meta-analysis stats
  - Evidence: per-screen z-scores linked to claims

Run:  python populate_kg_tcpgdb.py
"""
import csv
import json
import logging
import sqlite3
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("kg_tcpgdb")

SCRATCH = Path(os.environ["KG_DATA_ROOT"])
KG_PATH = SCRATCH / "gbd_knowledge_graph.db"
TDTOOL = SCRATCH / "tcpgdb" / "tdtool_output"

UTC = timezone.utc


def main():
    db = sqlite3.connect(str(KG_PATH))
    db.row_factory = sqlite3.Row

    all_genes = set()
    rows = db.execute("SELECT entity_id FROM entities WHERE entity_type = 'Gene'").fetchall()
    for r in rows:
        all_genes.add(r[0])
    log.info("KG has %d genes", len(all_genes))

    # ══════════════════════════════════════════════════════════════════
    # Step 1: Create ImmunePhenotype entities
    # ══════════════════════════════════════════════════════════════════
    log.info("Step 1: Creating ImmunePhenotype entities...")

    phenotype_meta = {
        "cytokine_IFNG": {"name": "IFN-gamma production", "category": "cytokine", "lineage": "T cell"},
        "cytokine_IL2": {"name": "IL-2 production", "category": "cytokine", "lineage": "T cell"},
        "cytokine_TNF": {"name": "TNF production", "category": "cytokine", "lineage": "T cell"},
        "proliferation": {"name": "T cell proliferation", "category": "functional", "lineage": "T cell"},
        "survival": {"name": "T cell survival", "category": "functional", "lineage": "T cell"},
        "persistence": {"name": "T cell persistence", "category": "functional", "lineage": "T cell"},
        "infiltration": {"name": "T cell infiltration", "category": "functional", "lineage": "T cell"},
        "differentiation": {"name": "T cell differentiation", "category": "functional", "lineage": "T cell"},
        "treg_identity": {"name": "Treg identity maintenance", "category": "regulatory", "lineage": "CD4T"},
        "activation_CTLA4": {"name": "CTLA4 T cell activation", "category": "activation", "lineage": "CD4T"},
        "activation_IL2RA": {"name": "IL2RA T cell activation", "category": "activation", "lineage": "T cell"},
    }

    for pheno_id, meta in phenotype_meta.items():
        entity_id = "PHENO-{}".format(pheno_id)
        db.execute(
            "INSERT OR REPLACE INTO entities VALUES (?, ?, ?, ?, ?, ?)",
            (entity_id, "ImmuneFunctionalState", meta["name"],
             json.dumps([]), json.dumps({"category": meta["category"]}),
             json.dumps({"source_db": "TCPGdb", "lineage": meta["lineage"]})),
        )
    db.commit()
    log.info("  Created %d phenotype entities", len(phenotype_meta))

    # ══════════════════════════════════════════════════════════════════
    # Step 2: Load concordance analysis → validated backbone edges
    # ══════════════════════════════════════════════════════════════════
    log.info("Step 2: Loading concordance analysis (CRISPRi/CRISPRa validated)...")

    concordance_path = TDTOOL / "concordance_analysis.csv"
    n_edges = 0
    n_drivers = 0
    n_suppressors = 0

    with open(concordance_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            gene = row["gene"]
            phenotype = row["phenotype"]
            concordance = row["concordance"]  # driver, suppressor, discordant
            combined_fdr = float(row["combined_fdr"]) if row["combined_fdr"] else 1.0
            combined_p = float(row["combined_p"]) if row["combined_p"] else 1.0
            crispri_z = float(row["crispri_z"]) if row["crispri_z"] else 0
            crispra_z = float(row["crispra_z"]) if row["crispra_z"] else 0
            effect_mag = float(row["effect_magnitude"]) if row["effect_magnitude"] else 0

            if gene not in all_genes:
                continue
            if concordance not in ("driver", "suppressor"):
                continue
            if combined_fdr > 0.05:
                continue

            # Backbone edge: validated perturbational finding
            pheno_id = "PHENO-{}".format(phenotype)
            if concordance == "driver":
                edge_type = "Gene-drives-ImmunePhenotype"
                n_drivers += 1
            else:
                edge_type = "Gene-suppresses-ImmunePhenotype"
                n_suppressors += 1

            edge_id = "TCPG-{}-{}-{}".format(gene[:15], phenotype[:15], concordance[:3])
            confidence = min(1.0, effect_mag / 30.0)  # normalize to 0-1

            db.execute(
                "INSERT OR IGNORE INTO backbone_edges VALUES (?, ?, ?, ?, ?, ?, ?)",
                (edge_id, edge_type, gene, pheno_id,
                 json.dumps({
                     "crispri_z": round(crispri_z, 2),
                     "crispra_z": round(crispra_z, 2),
                     "combined_p": combined_p,
                     "combined_fdr": combined_fdr,
                     "effect_magnitude": round(effect_mag, 2),
                     "concordance": concordance,
                 }),
                 "TCPGdb_concordance", confidence),
            )
            n_edges += 1

    db.commit()
    log.info("  %d concordance edges (%d drivers, %d suppressors)", n_edges, n_drivers, n_suppressors)

    # ══════════════════════════════════════════════════════════════════
    # Step 3: Load phenotype rankings → claims
    # ══════════════════════════════════════════════════════════════════
    log.info("Step 3: Loading phenotype rankings as claims...")

    rankings_path = TDTOOL / "phenotype_rankings.csv"
    n_claims = 0

    with open(rankings_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            gene = row["gene"]
            phenotype = row["phenotype"]
            meta_z = float(row["meta_z"]) if row["meta_z"] else 0
            p_value = float(row["p_value"]) if row["p_value"] else 1.0
            fdr = float(row["fdr"]) if row["fdr"] else 1.0
            n_screens = int(row["n_screens"]) if row["n_screens"] else 0
            direction = row["direction"]
            model_type = row["model_type"]
            lineage = row["lineage"]
            pert_type = row["pert_type"]
            i_squared = float(row["i_squared"]) if row.get("i_squared") else None
            cochran_q = float(row["cochran_q"]) if row.get("cochran_q") else None

            if gene not in all_genes:
                continue
            # Only store significant results as claims (FDR < 0.1)
            if fdr > 0.1:
                continue

            claim_id = "CRISPR-{}-{}-{}-{}".format(
                gene[:10], phenotype[:15], pert_type[:5], lineage[:4])

            # Determine proof level based on evidence strength
            if n_screens >= 3 and i_squared is not None and i_squared < 50:
                proof_level = 6  # orthogonal reproduction (multiple consistent screens)
            elif n_screens >= 2:
                proof_level = 5  # perturbational phenotypic
            else:
                proof_level = 4  # perturbational molecular

            # Effect direction
            effect = "positive_regulator" if direction == "positive" else "negative_regulator"

            db.execute("""
                INSERT OR IGNORE INTO claims
                (claim_id, claim_type, status, proof_level, effect_size, direction,
                 p_value, q_value, confidence_interval,
                 n_studies, n_modalities, direction_consistency,
                 source_dataset, assay_type,
                 created_at, description, full_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                claim_id,
                "CRISPRPhenotypeClaim",
                "replicated" if n_screens >= 2 else "observed",
                proof_level,
                meta_z,       # effect_size
                effect,       # direction
                p_value,
                fdr,          # q_value
                json.dumps(None),  # CI
                n_screens,
                1,            # n_modalities (CRISPR)
                1.0 if i_squared is not None and i_squared < 25 else 0.5,
                "TCPGdb",
                "{} meta-analysis ({})".format(model_type, pert_type),
                datetime.now(UTC).isoformat(),
                "{} {} of {} in {} ({})".format(effect, gene, phenotype, lineage, pert_type),
                json.dumps({
                    "lineage": lineage,
                    "phenotype": phenotype,
                    "pert_type": pert_type,
                    "cochran_q": cochran_q,
                    "i_squared": i_squared,
                    "meta_z": meta_z,
                }),
            ))

            # Add participants
            db.execute(
                "INSERT OR IGNORE INTO claim_participants VALUES (?, ?, ?, ?)",
                (claim_id, gene, "effector_gene", json.dumps({})),
            )
            pheno_id = "PHENO-{}".format(phenotype)
            db.execute(
                "INSERT OR IGNORE INTO claim_participants VALUES (?, ?, ?, ?)",
                (claim_id, pheno_id, "outcome", json.dumps({})),
            )

            n_claims += 1

    db.commit()
    log.info("  %d CRISPR phenotype claims (FDR < 0.1)", n_claims)

    # ══════════════════════════════════════════════════════════════════
    # Step 4: Load screen-level data as evidence
    # ══════════════════════════════════════════════════════════════════
    log.info("Step 4: Loading screen-level data as evidence...")

    screen_path = TDTOOL / "screen_level_data.csv"
    n_evidence = 0

    # Build claim_id lookup for significant results
    significant_claims = set()
    rows_check = db.execute("SELECT claim_id FROM claims WHERE claim_type = 'CRISPRPhenotypeClaim'").fetchall()
    for r in rows_check:
        significant_claims.add(r[0])
    log.info("  %d claims to attach evidence to", len(significant_claims))

    with open(screen_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            gene = row["gene"]
            phenotype = row["phenotype"]
            pert_type = row["pert_type"]
            screen = row["screen"]
            zscore = float(row["zscore"]) if row["zscore"] else 0
            paper = row.get("paper", "")
            lineage = row["lineage"]

            # Match to claim
            claim_id = "CRISPR-{}-{}-{}-{}".format(
                gene[:10], phenotype[:15], pert_type[:5], lineage[:4])

            if claim_id not in significant_claims:
                continue

            evidence_id = "EV-{}-{}".format(claim_id[:30], screen[:20])

            db.execute("""
                INSERT OR IGNORE INTO evidence
                (evidence_id, evidence_type, description, source,
                 statistic_name, statistic_value, effect_size,
                 full_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                evidence_id,
                "PerturbationExperiment",
                "{} {} screen for {} in {}".format(pert_type, paper, phenotype, lineage),
                screen,
                "z-score",
                zscore,
                zscore,
                json.dumps({"paper": paper, "lineage": lineage, "claim_id": claim_id}),
            ))
            n_evidence += 1

    db.commit()
    log.info("  %d evidence items linked to claims", n_evidence)

    # ══════════════════════════════════════════════════════════════════
    # Step 5: Load cross-phenotype categories as entity properties
    # ══════════════════════════════════════════════════════════════════
    log.info("Step 5: Loading cross-phenotype gene categories...")

    cross_path = TDTOOL / "cross_phenotype_comparison.csv"
    n_updated = 0

    with open(cross_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            gene = row["gene"]
            category = row["category"]  # pan_essential, phenotype_specific, phenotype_differential
            n_sig = int(row["n_significant"]) if row["n_significant"] else 0
            mean_abs_z = float(row["mean_abs_z"]) if row["mean_abs_z"] else 0
            best_model = row.get("best_model", "")
            best_z = float(row["best_z"]) if row.get("best_z") else 0

            if gene not in all_genes:
                continue

            # Update gene entity properties with TCPGdb category
            current = db.execute(
                "SELECT properties FROM entities WHERE entity_id = ?", (gene,)
            ).fetchone()
            if current:
                try:
                    props = json.loads(current[0]) if current[0] else {}
                except:
                    props = {}
                props["tcpgdb_category"] = category
                props["tcpgdb_n_sig_phenotypes"] = n_sig
                props["tcpgdb_mean_abs_z"] = round(mean_abs_z, 2)
                props["tcpgdb_best_model"] = best_model
                props["tcpgdb_best_z"] = round(best_z, 2)
                db.execute(
                    "UPDATE entities SET properties = ? WHERE entity_id = ?",
                    (json.dumps(props), gene),
                )
                n_updated += 1

    db.commit()
    log.info("  Updated %d gene entities with TCPGdb cross-phenotype categories", n_updated)

    # ══════════════════════════════════════════════════════════════════
    # Summary
    # ══════════════════════════════════════════════════════════════════
    stats = {
        "claims": db.execute("SELECT COUNT(*) FROM claims").fetchone()[0],
        "evidence": db.execute("SELECT COUNT(*) FROM evidence").fetchone()[0],
        "concordance_edges": db.execute(
            "SELECT COUNT(*) FROM backbone_edges WHERE source_db = 'TCPGdb_concordance'"
        ).fetchone()[0],
        "driver_edges": db.execute(
            "SELECT COUNT(*) FROM backbone_edges WHERE edge_type = 'Gene-drives-ImmunePhenotype'"
        ).fetchone()[0],
        "suppressor_edges": db.execute(
            "SELECT COUNT(*) FROM backbone_edges WHERE edge_type = 'Gene-suppresses-ImmunePhenotype'"
        ).fetchone()[0],
    }

    log.info("═══ TCPGdb KG INTEGRATION COMPLETE ═══")
    for k, v in stats.items():
        log.info("  %-30s %s", k, "{:,d}".format(v))

    db.close()


if __name__ == "__main__":
    main()
