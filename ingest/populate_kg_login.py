#!/usr/bin/env python3
"""Populate KG from login node (compute nodes lack outbound internet).

Data sources (all real curated databases, no LLM):
  1. Open Targets Platform: Disease-associates-Gene (GraphQL API)
  2. Enrichr TF-target: Protein-regulates-Gene (ENCODE/ChEA ChIP-seq, text mode)
  3. Enrichr LINCS L1000: KGene-regulates-Gene (CRISPR KO signatures)

HPA v23 already populated (418K edges in hpa_v23.json).
Gene annotations + PPI already in KG (14K genes, 266K edges).

Run:  python populate_kg_login.py --phase tf_targets
      python populate_kg_login.py --phase lincs
      python populate_kg_login.py --phase opentargets --shard 0 --total-shards 4
"""
import argparse
import json
import logging
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("kg_login")

SCRATCH = Path(os.environ["KG_DATA_ROOT"])
SHARD_DIR = SCRATCH / "kg_shards"
GENE_LIST = SCRATCH / "all_genes.json"


def get_all_genes():
    with open(GENE_LIST) as f:
        return json.load(f)


def get_shard_genes(shard, total):
    genes = get_all_genes()
    size = len(genes) // total + 1
    return genes[shard * size: min((shard + 1) * size, len(genes))]


def _http_get(url, timeout=30):
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GBD/0.1"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            if i == 2:
                raise
            log.debug("  Retry %d: %s", i + 1, e)
            time.sleep(2 * (i + 1))


def _graphql(query, variables=None, timeout=20):
    """Query Open Targets GraphQL API."""
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.platform.opentargets.org/api/v4/graphql",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "GBD/0.1"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:
            if "429" in str(e):
                time.sleep(5 * (attempt + 1))
            elif attempt == 2:
                raise
            else:
                time.sleep(2 * (attempt + 1))


# ═══════════════════════════════════════════════════════════════════════════
# TF-target edges from Enrichr (ENCODE/ChEA ChIP-seq) — TEXT mode
# ═══════════════════════════════════════════════════════════════════════════

def populate_tf_targets():
    """Download TF-target gene sets from Enrichr in text format."""
    log.info("Enrichr TF-targets: Downloading ChIP-seq gene sets (text mode)...")
    all_genes_set = set(get_all_genes())
    edges = []

    libraries = [
        "ENCODE_and_ChEA_Consensus_TFs_from_ChIP-X",
        "ENCODE_TF_ChIP-seq_2015",
        "ChEA_2022",
    ]

    for lib in libraries:
        url = "https://maayanlab.cloud/Enrichr/geneSetLibrary?mode=text&libraryName={}".format(
            urllib.parse.quote(lib))
        try:
            text = _http_get(url, timeout=60)
            lines = text.strip().split("\n")
            n_edges = 0

            for line in lines:
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                term_name = parts[0]  # e.g., "STAT1 ENCODE" or "STAT1_ChIP-Seq_ENCODE"
                # parts[1] is empty (description placeholder)
                targets = parts[2:]  # gene symbols

                # Extract TF name
                tf = term_name.split("_")[0].split(" ")[0].upper()
                if tf not in all_genes_set:
                    continue

                for t in targets:
                    t_clean = t.strip().upper().split(",")[0]
                    if t_clean and t_clean in all_genes_set and t_clean != tf:
                        edges.append({
                            "source": tf,
                            "target": t_clean,
                            "type": "Protein-regulates-Gene",
                            "source_db": lib[:40],
                        })
                        n_edges += 1

            log.info("  %s: %d terms, %d TF-target edges", lib, len(lines), n_edges)
        except Exception as e:
            log.warning("  %s failed: %s", lib, e)
        time.sleep(1)

    # Deduplicate
    seen = set()
    unique_edges = []
    for e in edges:
        key = (e["source"], e["target"])
        if key not in seen:
            seen.add(key)
            unique_edges.append(e)

    out = SHARD_DIR / "tf_targets_enrichr.json"
    with open(out, "w") as f:
        json.dump({"edges": unique_edges}, f)
    log.info("TF-targets: %d unique edges (from %d raw) → %s", len(unique_edges), len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════
# LINCS L1000: KGene-regulates-Gene (CRISPR KO perturbation signatures)
# ═══════════════════════════════════════════════════════════════════════════

def populate_lincs():
    """Download LINCS L1000 CRISPR KO consensus signatures from Enrichr."""
    log.info("LINCS L1000: Downloading perturbation gene sets (text mode)...")
    all_genes_set = set(get_all_genes())
    edges = []

    libraries = [
        "LINCS_L1000_CRISPR_KO_Consensus_Sigs",
        "LINCS_L1000_Ligand_Perturbations_up",
        "LINCS_L1000_Ligand_Perturbations_down",
    ]

    for lib in libraries:
        url = "https://maayanlab.cloud/Enrichr/geneSetLibrary?mode=text&libraryName={}".format(
            urllib.parse.quote(lib))
        try:
            text = _http_get(url, timeout=60)
            lines = text.strip().split("\n")
            n_edges = 0

            for line in lines:
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                term_name = parts[0]  # e.g., "TP53 knockdown - A549 cell"
                targets = parts[2:]

                # Extract perturbed gene
                perturbed = term_name.split(" ")[0].split("_")[0].upper()
                if perturbed not in all_genes_set:
                    continue

                # Determine direction
                if "down" in lib.lower():
                    edge_type = "KGene-downregulates-Gene"
                elif "up" in lib.lower():
                    edge_type = "KGene-upregulates-Gene"
                else:
                    edge_type = "KGene-regulates-Gene"

                for t in targets:
                    t_clean = t.strip().upper().split(",")[0]
                    if t_clean and t_clean in all_genes_set and t_clean != perturbed:
                        edges.append({
                            "source": perturbed,
                            "target": t_clean,
                            "type": edge_type,
                            "source_db": lib[:40],
                            "term": term_name[:80],
                        })
                        n_edges += 1

            log.info("  %s: %d terms, %d edges", lib, len(lines), n_edges)
        except Exception as e:
            log.warning("  %s failed: %s", lib, e)
        time.sleep(1)

    # Deduplicate by (source, target, type)
    seen = set()
    unique_edges = []
    for e in edges:
        key = (e["source"], e["target"], e["type"])
        if key not in seen:
            seen.add(key)
            unique_edges.append(e)

    out = SHARD_DIR / "lincs_l1000.json"
    with open(out, "w") as f:
        json.dump({"edges": unique_edges}, f)
    log.info("LINCS: %d unique edges (from %d raw) → %s", len(unique_edges), len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════
# Open Targets: Disease-associates-Gene (GraphQL API, per gene)
# ═══════════════════════════════════════════════════════════════════════════

OT_QUERY = """
query targetDiseases($id: String!) {
  target(ensemblId: $id) {
    approvedSymbol
    associatedDiseases(page: {size: 25, index: 0}) {
      count
      rows {
        disease { id name }
        score
      }
    }
  }
}
"""


def get_ensembl_ids(genes):
    """Batch lookup symbol → Ensembl ID via MyGene.info."""
    mapping = {}
    for batch_start in range(0, len(genes), 200):
        batch = genes[batch_start:batch_start + 200]
        try:
            data = urllib.parse.urlencode({
                "q": ",".join(batch),
                "scopes": "symbol",
                "species": "human",
                "fields": "symbol,ensembl.gene",
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://mygene.info/v3/query", data=data,
                headers={"User-Agent": "GBD/0.1", "Accept": "application/json",
                         "Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                hits = json.loads(r.read())
            for h in hits:
                if not isinstance(h, dict) or h.get("notfound"):
                    continue
                sym = h.get("symbol", "")
                ens = h.get("ensembl", {})
                if isinstance(ens, list):
                    ens_id = ens[0].get("gene", "") if ens else ""
                elif isinstance(ens, dict):
                    ens_id = ens.get("gene", "")
                else:
                    ens_id = ""
                if sym and ens_id:
                    mapping[sym] = ens_id
        except Exception as e:
            log.warning("  Ensembl batch %d failed: %s", batch_start, e)
        time.sleep(0.5)

    log.info("  Mapped %d/%d genes to Ensembl IDs", len(mapping), len(genes))
    return mapping


def populate_opentargets(shard, total):
    """Query Open Targets for disease associations — real curated data."""
    genes = get_shard_genes(shard, total)
    log.info("Open Targets shard %d/%d: %d genes", shard, total, len(genes))

    ensembl_map = get_ensembl_ids(genes)
    log.info("  %d genes with Ensembl IDs", len(ensembl_map))

    edges = []
    entities = []
    disease_seen = set()

    for i, (symbol, ens_id) in enumerate(ensembl_map.items()):
        if (i + 1) % 100 == 0:
            log.info("  %d/%d genes queried, %d disease edges so far",
                     i + 1, len(ensembl_map), len(edges))

        try:
            resp = _graphql(OT_QUERY, {"id": ens_id})
            target = resp.get("data", {}).get("target")
            if not target:
                continue

            ad = target.get("associatedDiseases", {})
            for row in ad.get("rows", []):
                disease = row.get("disease", {})
                d_id = disease.get("id", "")
                d_name = disease.get("name", "")
                score = row.get("score", 0)

                if d_name and score > 0.1:
                    if d_id not in disease_seen:
                        entities.append({
                            "entity_id": d_id,
                            "entity_type": "Disease",
                            "name": d_name,
                        })
                        disease_seen.add(d_id)

                    edges.append({
                        "source": d_id,
                        "target": symbol,
                        "type": "Disease-associates-Gene",
                        "score": score,
                        "source_db": "OpenTargets",
                    })

        except Exception as e:
            if "429" in str(e):
                log.info("  Rate limited, sleeping 10s...")
                time.sleep(10)
            else:
                log.debug("  %s (%s) failed: %s", symbol, ens_id, e)

        time.sleep(0.12)  # ~8 queries/sec

    out = SHARD_DIR / "opentargets_disease_{:03d}.json".format(shard)
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("Open Targets shard %d: %d diseases, %d edges → %s",
             shard, len(disease_seen), len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True,
                        choices=["tf_targets", "lincs", "opentargets", "all_fast"])
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--total-shards", type=int, default=4)
    args = parser.parse_args()

    if args.phase == "tf_targets":
        populate_tf_targets()
    elif args.phase == "lincs":
        populate_lincs()
    elif args.phase == "opentargets":
        populate_opentargets(args.shard, args.total_shards)
    elif args.phase == "all_fast":
        # TF targets + LINCS are fast downloads
        populate_tf_targets()
        populate_lincs()


if __name__ == "__main__":
    main()
