#!/usr/bin/env python3
"""Populate KG REFERENCE GRAPH with stable curated edges.

Reference edges are biological FACTS — not context-dependent, not from
a specific experiment. They represent stable knowledge from gold-standard
databases.

Sources:
  1. Reactome → GENE_PARTICIPATES_PATHWAY (gene → pathway membership)
  2. CollecTRI → TF_BINDS_PROMOTER (TF → target gene, curated regulatory)
  3. STRING (>700) → PROTEIN_INTERACTS_PROTEIN (high-confidence PPI)
  4. PhosphoSitePlus → PHOSPHORYLATES (kinase → substrate, via iPTMnet API)

These are loaded from pre-downloaded bulk files where available,
falling back to API calls for kinase-substrate relationships.

Run:  python populate_kg_reference_edges.py
"""
import csv
import json
import logging
import sqlite3
import sys
import hashlib
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("kg_ref_edges")

KG_PATH = Path(os.environ["KG_DATA_ROOT"]) / "gbd_knowledge_graph.db"
DEPMAP = Path(os.environ["EXTERNAL_DATA_ROOT"]) / "depmap"
TF_NETWORKS = Path(os.environ["KG_DATA_ROOT"]) / "tf_networks"


def main():
    db = sqlite3.connect(str(KG_PATH))
    db.execute("PRAGMA journal_mode=WAL")

    all_genes = set(r[0] for r in db.execute(
        "SELECT entity_id FROM entities WHERE entity_type = 'Gene'"
    ).fetchall())
    log.info("KG has %d gene entities", len(all_genes))

    # Check existing edge counts
    for row in db.execute(
        "SELECT edge_type, COUNT(*) FROM backbone_edges GROUP BY edge_type ORDER BY COUNT(*) DESC LIMIT 5"
    ).fetchall():
        log.info("  Existing: %s = %d", row[0], row[1])

    # ══════════════════════════════════════════════════════════════════
    # Step 1: Reactome pathway membership
    # ══════════════════════════════════════════════════════════════════
    log.info("\nStep 1: Reactome pathway membership...")
    reactome_path = DEPMAP / "reactome_hsa_pathways_v2.tsv"

    if reactome_path.exists():
        # Create pathway entities
        pathways_seen = set()
        gene_pathway_pairs = []

        with open(reactome_path) as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                gene = row.get("gene", "").strip()
                pathway_id = row.get("pathway_id", "").strip()
                pathway_name = row.get("pathway_name", "").strip()

                if not gene or gene not in all_genes:
                    continue
                if not pathway_id:
                    continue

                # Create pathway entity if new
                if pathway_id not in pathways_seen:
                    db.execute(
                        "INSERT OR IGNORE INTO entities VALUES (?, ?, ?, ?, ?, ?)",
                        (pathway_id, "Pathway", pathway_name,
                         json.dumps([]), json.dumps({}),
                         json.dumps({"source_db": "Reactome"})),
                    )
                    pathways_seen.add(pathway_id)

                gene_pathway_pairs.append((gene, pathway_id, pathway_name))

        # Insert edges (skip duplicates of existing GENE_PARTICIPATES_PATHWAY)
        n_new = 0
        for gene, pathway_id, pathway_name in gene_pathway_pairs:
            edge_id = f"reactome-{gene}-{pathway_id}"
            db.execute("""
                INSERT OR IGNORE INTO backbone_edges
                (edge_id, edge_type, source_id, target_id, properties, source_db, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                edge_id,
                "Gene-participates-Pathway",
                gene,
                pathway_id,
                json.dumps({"pathway_name": pathway_name}),
                "Reactome",
                1.0,
            ))
            n_new += 1

        db.commit()
        log.info("  Reactome: %d pathway membership edges, %d pathways",
                 n_new, len(pathways_seen))
    else:
        log.warning("  Reactome file not found: %s", reactome_path)

    # ══════════════════════════════════════════════════════════════════
    # Step 2: CollecTRI TF → target regulatory edges
    # ══════════════════════════════════════════════════════════════════
    log.info("\nStep 2: CollecTRI TF-target regulatory edges...")
    collectri_path = TF_NETWORKS / "collectri_human.tsv"

    if collectri_path.exists():
        n_tf_edges = 0
        with open(collectri_path) as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                tf = row.get("source", "").strip()
                target = row.get("target", "").strip()
                weight = float(row.get("weight", 0))

                if not tf or not target:
                    continue
                if tf not in all_genes or target not in all_genes:
                    continue

                edge_id = f"collectri-{tf}-{target}"
                edge_type = "TF-bindsPromoter-Gene"

                db.execute("""
                    INSERT OR IGNORE INTO backbone_edges
                    (edge_id, edge_type, source_id, target_id, properties, source_db, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    edge_id,
                    edge_type,
                    tf,
                    target,
                    json.dumps({"weight": weight, "direction": "activates" if weight > 0 else "represses"}),
                    "CollecTRI",
                    min(abs(weight), 1.0),
                ))
                n_tf_edges += 1

        db.commit()
        log.info("  CollecTRI: %d TF→target edges", n_tf_edges)
    else:
        log.warning("  CollecTRI file not found: %s", collectri_path)

    # ══════════════════════════════════════════════════════════════════
    # Step 3: STRING PPI (high confidence ≥ 700)
    # ══════════════════════════════════════════════════════════════════
    log.info("\nStep 3: STRING PPI edges (score ≥ 700)...")
    string_path = DEPMAP / "tdtool_pan_cancer" / "graph" / "edges_string_ppi.csv"

    if string_path.exists():
        n_ppi = 0
        with open(string_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                gene1 = row.get("gene1", "").strip()
                gene2 = row.get("gene2", "").strip()
                score = int(row.get("combined_score", 0))

                if score < 700:
                    continue
                if not gene1 or not gene2:
                    continue
                if gene1 not in all_genes or gene2 not in all_genes:
                    continue

                # Canonical ordering to avoid duplicate edges
                a, b = sorted([gene1, gene2])
                edge_id = f"string-{a}-{b}"

                db.execute("""
                    INSERT OR IGNORE INTO backbone_edges
                    (edge_id, edge_type, source_id, target_id, properties, source_db, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    edge_id,
                    "Protein-interacts-Protein",
                    a,
                    b,
                    json.dumps({"combined_score": score}),
                    "STRING",
                    score / 1000.0,
                ))
                n_ppi += 1

        db.commit()
        log.info("  STRING: %d high-confidence PPI edges (score ≥ 700)", n_ppi)
    else:
        log.warning("  STRING PPI file not found: %s", string_path)

    # ══════════════════════════════════════════════════════════════════
    # Step 4: PhosphoSitePlus kinase-substrate (via iPTMnet API)
    # ══════════════════════════════════════════════════════════════════
    log.info("\nStep 4: Kinase-substrate relationships (iPTMnet API)...")

    # Query top kinases and their substrates via the existing tool
    # This is API-based so we limit to the most important kinases
    TOP_KINASES = [
        "AKT1", "AKT2", "BRAF", "CDK1", "CDK2", "CDK4", "CDK6",
        "CHEK1", "CHEK2", "EGFR", "ERBB2", "ERK1", "ERK2",
        "FGFR1", "GSK3B", "JAK1", "JAK2", "KIT", "LCK",
        "MAPK1", "MAPK3", "MAPK8", "MAPK14", "MET", "MTOR",
        "PIK3CA", "PLK1", "PRKCA", "RAF1", "RET", "ROS1",
        "SRC", "SYK", "TYK2", "ZAP70", "ABL1", "ALK",
        "ATM", "ATR", "AURKA", "AURKB", "BTK", "CAMK2A",
        "CSNK2A1", "DYRK1A", "FLT3", "IGF1R", "INSR",
        "MAP2K1", "MAP2K2", "NEK2", "PDGFRA", "PRKCD",
        "ROCK1", "STK11", "TGFBR1", "TGFBR2", "VEGFR2",
    ]

    try:
        from gbd.core.analysis_tools import get_analysis_registry
        registry = get_analysis_registry()

        n_ks_edges = 0
        for kinase in TOP_KINASES:
            if kinase not in all_genes:
                continue

            try:
                ar = registry.dispatch("iptmnet_substrates", {"gene": kinase})
                if not ar.success:
                    continue

                result = ar.result
                substrates = []
                if isinstance(result, dict):
                    substrates = result.get("substrates", [])
                elif hasattr(result, "substrates"):
                    substrates = getattr(result, "substrates", [])

                for sub in substrates:
                    substrate_gene = ""
                    site = ""
                    if isinstance(sub, dict):
                        substrate_gene = sub.get("gene", sub.get("substrate", "")).strip()
                        site = sub.get("site", sub.get("residue", ""))
                    elif isinstance(sub, str):
                        substrate_gene = sub

                    if not substrate_gene or substrate_gene not in all_genes:
                        continue

                    edge_id = f"iptmnet-{kinase}-phospho-{substrate_gene}"
                    if site:
                        edge_id = f"iptmnet-{kinase}-phospho-{substrate_gene}-{site}"

                    db.execute("""
                        INSERT OR IGNORE INTO backbone_edges
                        (edge_id, edge_type, source_id, target_id, properties, source_db, confidence)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        edge_id,
                        "Kinase-phosphorylates-Substrate",
                        kinase,
                        substrate_gene,
                        json.dumps({"site": str(site), "ptm_type": "phosphorylation"}),
                        "iPTMnet",
                        0.8,
                    ))
                    n_ks_edges += 1

                time.sleep(0.5)  # rate limit iPTMnet API

            except Exception as e:
                log.debug("  iPTMnet failed for %s: %s", kinase, e)
                continue

        db.commit()
        log.info("  iPTMnet: %d kinase→substrate edges from %d kinases",
                 n_ks_edges, len(TOP_KINASES))

    except Exception as e:
        log.warning("  iPTMnet step failed: %s", e)

    # ══════════════════════════════════════════════════════════════════
    # Summary
    # ══════════════════════════════════════════════════════════════════
    log.info("\n=== REFERENCE GRAPH SUMMARY ===")
    for row in db.execute(
        "SELECT edge_type, COUNT(*) FROM backbone_edges GROUP BY edge_type ORDER BY COUNT(*) DESC"
    ).fetchall():
        log.info("  %s: %d", row[0], row[1])
    total = db.execute("SELECT COUNT(*) FROM backbone_edges").fetchone()[0]
    log.info("Total backbone edges: %d", total)

    db.close()
    log.info("Done.")


if __name__ == "__main__":
    main()
