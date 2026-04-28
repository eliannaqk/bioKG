#!/usr/bin/env python3
"""Populate KG with genomic alteration data and Taiji TF regulatory edges.

Adds to the existing KG (gbd_knowledge_graph.db):
  1. SL LASSO edges — 28,792 synthetic lethal pairs as backbone edges
  2. Taiji TF entities — 752 TFs with state-specific PageRank activity
  3. Taiji TF community edges — co-regulation community membership
  4. Tumor essentiality edges — CPTAC-predicted CERES (top essential genes)
  5. CPTAC-TCGA study pairing entities

Usage:
  python scripts/populate_kg_genomic_taiji.py --phase all
  python scripts/populate_kg_genomic_taiji.py --phase sl_pairs
  python scripts/populate_kg_genomic_taiji.py --phase taiji
  python scripts/populate_kg_genomic_taiji.py --phase essentiality
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("populate_kg_genomic_taiji")

GBD_SCRATCH = Path(os.environ.get("GBD_SCRATCH_ROOT") or os.environ["KG_DATA_ROOT"])
KG_DB_PATH = GBD_SCRATCH / "gbd_knowledge_graph.db"
DEPMAP_ROOT = Path(os.environ.get("DEPMAP_SCRATCH_ROOT") or str(Path(os.environ["EXTERNAL_DATA_ROOT"]) / "depmap"))
TAIJI_DATA = GBD_SCRATCH / "taiji2" / "nature_supplements"


def get_conn(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        log.error("KG database not found at %s", db_path)
        sys.exit(1)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _insert_entity(conn: sqlite3.Connection, entity_id: str, entity_type: str,
                    name: str, aliases: str = "[]", properties: str = "{}",
                    xrefs: str = "{}"):
    conn.execute(
        "INSERT OR REPLACE INTO entities VALUES (?, ?, ?, ?, ?, ?)",
        (entity_id, entity_type, name, aliases, properties, xrefs),
    )


def _insert_edge(conn: sqlite3.Connection, edge_id: str, edge_type: str,
                  source_id: str, target_id: str, properties: str = "{}",
                  source_db: str = "", confidence: float = 1.0):
    conn.execute(
        "INSERT OR IGNORE INTO backbone_edges VALUES (?, ?, ?, ?, ?, ?, ?)",
        (edge_id, edge_type, source_id, target_id, properties, source_db, confidence),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Phase 1: Synthetic lethality edges
# ═══════════════════════════════════════════════════════════════════════════

def populate_sl_pairs(conn: sqlite3.Connection):
    """Add 28,792 SL pairs as backbone edges."""
    import pandas as pd

    sl_path = DEPMAP_ROOT / "tdtool_pan_cancer" / "graph" / "sl_lasso_filtered.csv"
    if not sl_path.exists():
        log.warning("SL data not found: %s", sl_path)
        return

    df = pd.read_csv(sl_path)
    log.info("Loading %d SL pairs from %s", len(df), sl_path)

    n = 0
    for _, row in df.iterrows():
        target = str(row.get("target_gene", ""))
        mutation = str(row.get("mutation_gene", ""))
        if not target or not mutation:
            continue

        props = json.dumps({
            "relationship": "synthetic_lethality",
            "lasso_coef": round(float(row.get("lasso_coef", 0)), 4),
            "fdr_q": round(float(row.get("fdr_q", 1)), 6),
            "mutually_exclusive": bool(row.get("mutually_exclusive", False)),
        })
        fdr = float(row.get("fdr_q", 1))
        conf = min(1.0, max(0.0, 1.0 - fdr))

        _insert_edge(conn,
                      f"SL-{mutation}-{target}",
                      "Gene-syntheticLethal-Gene",
                      mutation, target, props,
                      "TDtool_SL_LASSO", conf)
        n += 1

    conn.commit()
    log.info("Added %d SL backbone edges", n)


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2: Taiji TF atlas — entities + community edges
# ═══════════════════════════════════════════════════════════════════════════

def populate_taiji(conn: sqlite3.Connection):
    """Add 752 TF entities with PageRank activity and community edges."""
    import pandas as pd

    activity_path = TAIJI_DATA / "tf_activity_full_752tfs.tsv"
    if not activity_path.exists():
        log.warning("Taiji TF activity not found: %s", activity_path)
        return

    df = pd.read_csv(activity_path, sep="\t", index_col=0)
    states = list(df.columns)
    log.info("Loading Taiji TF activity: %d TFs × %d states", len(df), len(states))

    # Load specificity classes
    spec = {}
    spec_path = TAIJI_DATA / "tf_state_specificity_classes.tsv"
    if spec_path.exists():
        with open(spec_path) as f:
            f.readline()  # skip header
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    spec[parts[0]] = parts[1]

    # Add/update TF entities with activity data
    n_tf = 0
    for tf in df.index:
        scores = {col: round(float(df.loc[tf, col]), 4) for col in states}
        top_state = max(scores, key=scores.get)

        props = json.dumps({
            "is_transcription_factor": True,
            "taiji_activity": scores,
            "taiji_top_state": top_state,
            "taiji_top_score": scores[top_state],
            "taiji_specificity_class": spec.get(tf, "unclassified"),
            "taiji_source": "CD8+ T cell TF atlas (Wang lab, 752 TFs × 9 states)",
        })

        _insert_entity(conn, tf, "Gene", tf, "[]", props, "{}")
        n_tf += 1

    conn.commit()
    log.info("Added/updated %d TF entities with Taiji activity", n_tf)

    # Add community edges
    comm_path = TAIJI_DATA / "tf_communities.tsv"
    if comm_path.exists():
        n_comm = 0
        with open(comm_path) as f:
            f.readline()
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 3:
                    state, community, tf = parts[0], parts[1], parts[2]
                    # Create community entity
                    comm_id = f"TF_Community_{state}_{community}"
                    _insert_entity(conn, comm_id, "BiologicalProcess",
                                   f"TF community {community} in {state}",
                                   "[]",
                                   json.dumps({"cell_state": state, "community": community,
                                              "type": "taiji_tf_community"}),
                                   "{}")
                    # Add membership edge
                    _insert_edge(conn,
                                 f"TAIJI-COMM-{state}-{community}-{tf}",
                                 "Gene-participates-BiologicalProcess",
                                 tf, comm_id,
                                 json.dumps({"cell_state": state}),
                                 "Taiji2_communities", 0.8)
                    n_comm += 1

        conn.commit()
        log.info("Added %d TF community membership edges", n_comm)


# ═══════════════════════════════════════════════════════════════════════════
# Phase 3: Tumor essentiality edges
# ═══════════════════════════════════════════════════════════════════════════

def populate_essentiality(conn: sqlite3.Connection):
    """Add tumor essentiality predictions for top essential genes."""
    import pandas as pd

    per_study = DEPMAP_ROOT / "tdtool_pan_cancer" / "per_study_rnaseq"
    if not per_study.exists():
        log.warning("Essentiality data not found: %s", per_study)
        return

    cancer_map = {
        "brca_BRCA": "breast", "ccrcc_KIRC": "renal", "coad_COAD": "colorectal",
        "gbm_GBM": "glioblastoma", "hnscc_HNSCC": "head_neck",
        "lscc_LUSC": "lung_squamous", "luad_LUAD": "lung_adenocarcinoma",
        "ov_OV": "ovarian", "pdac_PDAC": "pancreatic", "ucec_UCEC": "endometrial",
    }

    n_edges = 0
    for study_dir in sorted(per_study.iterdir()):
        if not study_dir.is_dir():
            continue
        summary = study_dir / "gene_tumor_summary.csv"
        if not summary.exists():
            continue

        study_name = study_dir.name
        cancer = cancer_map.get(study_name, study_name)
        df = pd.read_csv(summary)

        # Add Study entity
        _insert_entity(conn, f"CPTAC_ESS_{study_name}", "Study",
                        f"CPTAC Essentiality: {cancer}",
                        "[]",
                        json.dumps({
                            "study_type": "tumor_essentiality_prediction",
                            "cancer_type": cancer,
                            "n_genes": len(df),
                            "pipeline": "CPTAC RNA-seq → Celligner → DepMap CERES elastic net",
                        }),
                        "{}")

        # Add CancerType entity
        ct_id = f"cancer_{cancer}"
        _insert_entity(conn, ct_id, "CancerType", cancer, "[]", "{}", "{}")

        # Top essential genes (frac_essential > 0.5)
        essential = df[df["frac_essential"] > 0.5]
        for _, row in essential.iterrows():
            gene = str(row["gene"])
            props = json.dumps({
                "relationship": "predicted_tumor_essentiality",
                "mean_essentiality": round(float(row.get("mean_essentiality", 0)), 4),
                "frac_essential": round(float(row.get("frac_essential", 0)), 4),
                "model_cv_r": round(float(row.get("model_cv_r", 0)), 4),
                "study": study_name,
            })
            cv_r = float(row.get("model_cv_r", 0.5))

            _insert_edge(conn,
                          f"TESS-{study_name}-{gene}",
                          "Disease-associates-Gene",
                          ct_id, gene, props,
                          "TDtool_CPTAC_essentiality", cv_r)
            n_edges += 1

    conn.commit()
    log.info("Added %d tumor essentiality edges across %d studies",
             n_edges, len(cancer_map))


# ═══════════════════════════════════════════════════════════════════════════
# Phase 4: CPTAC-TCGA pairing entities
# ═══════════════════════════════════════════════════════════════════════════

def populate_cptac_tcga(conn: sqlite3.Connection):
    """Add CPTAC-TCGA matched study entities."""
    pairings = {
        "CPTAC-BRCA": {"tcga": "TCGA-BRCA", "cancer": "breast", "pdc": "PDC000120"},
        "CPTAC-COAD": {"tcga": "TCGA-COAD", "cancer": "colorectal", "pdc": "PDC000116"},
        "CPTAC-OV": {"tcga": "TCGA-OV", "cancer": "ovarian", "pdc": "PDC000360"},
        "CPTAC-LUAD": {"tcga": "TCGA-LUAD", "cancer": "lung_adenocarcinoma", "pdc": "PDC000219"},
        "CPTAC-GBM": {"tcga": "TCGA-GBM", "cancer": "glioblastoma", "pdc": "PDC000514"},
        "CPTAC-KIRC": {"tcga": "TCGA-KIRC", "cancer": "renal", "pdc": "PDC000127"},
        "CPTAC-UCEC": {"tcga": "TCGA-UCEC", "cancer": "endometrial", "pdc": "PDC000439"},
        "CPTAC-HNSCC": {"tcga": "TCGA-HNSC", "cancer": "head_neck", "pdc": "PDC000221"},
        "CPTAC-LUSC": {"tcga": "TCGA-LUSC", "cancer": "lung_squamous", "pdc": "PDC000234"},
        "CPTAC-PDAC": {"tcga": "TCGA-PAAD", "cancer": "pancreatic", "pdc": "PDC000270"},
    }

    n = 0
    for cptac_id, info in pairings.items():
        props = json.dumps({
            "cptac_id": cptac_id,
            "tcga_project": info["tcga"],
            "cancer_type": info["cancer"],
            "pdc_study_id": info["pdc"],
            "has_wes": True,
            "has_proteomics": True,
            "cross_reference_available": True,
        })
        _insert_entity(conn, f"PAIRING_{cptac_id}", "Study",
                        f"TCGA-CPTAC pairing: {cptac_id}",
                        "[]", props, "{}")
        n += 1

    conn.commit()
    log.info("Added %d CPTAC-TCGA pairing entities", n)


# ═══════════════════════════════════════════════════════════════════════════

PHASES = {
    "sl_pairs": populate_sl_pairs,
    "taiji": populate_taiji,
    "essentiality": populate_essentiality,
    "cptac_tcga": populate_cptac_tcga,
}


def main():
    parser = argparse.ArgumentParser(description="Populate KG with genomic + Taiji data")
    parser.add_argument("--phase", default="all",
                        choices=list(PHASES.keys()) + ["all"])
    parser.add_argument("--db", default=str(KG_DB_PATH))
    args = parser.parse_args()

    conn = get_conn(Path(args.db))

    # Check current state
    n_entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    n_edges = conn.execute("SELECT COUNT(*) FROM backbone_edges").fetchone()[0]
    log.info("KG before: %d entities, %d edges", n_entities, n_edges)

    if args.phase == "all":
        for name, func in PHASES.items():
            log.info("=== Running phase: %s ===", name)
            func(conn)
    else:
        PHASES[args.phase](conn)

    n_entities_after = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    n_edges_after = conn.execute("SELECT COUNT(*) FROM backbone_edges").fetchone()[0]
    log.info("KG after: %d entities (+%d), %d edges (+%d)",
             n_entities_after, n_entities_after - n_entities,
             n_edges_after, n_edges_after - n_edges)

    conn.close()
    log.info("Done.")


if __name__ == "__main__":
    main()
