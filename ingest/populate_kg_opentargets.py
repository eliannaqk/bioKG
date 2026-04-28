#!/usr/bin/env python3
"""Populate KG with Open Targets disease associations + HPA tissue expression.

Data sources (all real curated databases, no LLM):
  1. Open Targets Platform: Disease-associates-Gene (3000+ diseases per gene)
  2. HPA v23: Anatomy-expresses-Gene (tissue expression)
  3. Enrichr ChEA/ENCODE: Protein-regulates-Gene (ChIP-seq TF-target)

Run as SLURM array:
  python populate_kg_opentargets.py --phase diseases --shard 0 --total-shards 20
  python populate_kg_opentargets.py --phase hpa
  python populate_kg_opentargets.py --phase tf_targets
"""
import argparse
import json
import logging
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("kg_ot")

SCRATCH = Path(os.environ["KG_DATA_ROOT"])
SHARD_DIR = SCRATCH / "kg_shards"
GENE_LIST = SCRATCH / "all_genes.json"


def _http_get(url, timeout=20):
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GBD/0.1", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception:
            if i == 2: raise
            time.sleep(2 * (i + 1))


def _graphql(query, variables=None, timeout=20):
    """Query Open Targets GraphQL API."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.platform.opentargets.org/api/v4/graphql",
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "GBD/0.1"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def get_shard_genes(shard, total):
    with open(GENE_LIST) as f:
        genes = json.load(f)
    size = len(genes) // total + 1
    return genes[shard * size: min((shard + 1) * size, len(genes))]


# ═══════════════════════════════════════════════════════════════════════════
# Step 1: Get Ensembl IDs for all genes (needed for Open Targets)
# ═══════════════════════════════════════════════════════════════════════════

def get_ensembl_ids(genes: list[str]) -> dict[str, str]:
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
        time.sleep(0.3)

    log.info("  Mapped %d/%d genes to Ensembl IDs", len(mapping), len(genes))
    return mapping


# ═══════════════════════════════════════════════════════════════════════════
# Phase 1: Open Targets disease associations
# ═══════════════════════════════════════════════════════════════════════════

OT_QUERY = """
query targetDiseases($id: String!) {
  target(ensemblId: $id) {
    approvedSymbol
    associatedDiseases(page: {size: 20, index: 0}) {
      count
      rows {
        disease {
          id
          name
        }
        score
        datatypeScores {
          componentId
          score
        }
      }
    }
  }
}
"""

def populate_diseases(shard: int, total: int):
    """Query Open Targets for disease associations — real curated data."""
    genes = get_shard_genes(shard, total)
    log.info("Open Targets diseases shard %d: %d genes", shard, len(genes))

    # Get Ensembl IDs
    ensembl_map = get_ensembl_ids(genes)
    log.info("  %d genes with Ensembl IDs", len(ensembl_map))

    edges = []
    entities = []

    for i, (symbol, ens_id) in enumerate(ensembl_map.items()):
        if (i + 1) % 50 == 0:
            log.info("  %d/%d genes, %d disease edges", i + 1, len(ensembl_map), len(edges))

        try:
            resp = _graphql(OT_QUERY, {"id": ens_id})
            target = resp.get("data", {}).get("target", {})
            if not target:
                continue

            ad = target.get("associatedDiseases", {})
            for row in ad.get("rows", []):
                disease = row.get("disease", {})
                d_id = disease.get("id", "")
                d_name = disease.get("name", "")
                score = row.get("score", 0)

                if d_name and score > 0.1:
                    entities.append({
                        "entity_id": d_id,
                        "entity_type": "Disease",
                        "name": d_name,
                    })
                    edges.append({
                        "source": d_id,
                        "target": symbol,
                        "type": "Disease-associates-Gene",
                        "score": score,
                        "source_db": "OpenTargets",
                    })

        except Exception as e:
            if "429" in str(e):
                time.sleep(5)  # Rate limited
            pass

        time.sleep(0.15)  # ~6 queries/sec

    out = SHARD_DIR / f"opentargets_disease_{shard:03d}.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("Open Targets shard %d: %d disease edges → %s", shard, len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2: HPA tissue expression (v23)
# ═══════════════════════════════════════════════════════════════════════════

def populate_hpa():
    """Download HPA normal tissue from v23."""
    log.info("HPA v23: Downloading tissue expression...")
    edges = []
    entities = []

    url = "https://v23.proteinatlas.org/download/normal_tissue.tsv.zip"
    try:
        import io, zipfile
        raw = urllib.request.urlopen(url, timeout=120).read()
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            with zf.open(zf.namelist()[0]) as f:
                lines = f.read().decode("utf-8").splitlines()

        log.info("  HPA: %d rows", len(lines) - 1)
        all_genes_set = set()
        try:
            with open(GENE_LIST) as f:
                all_genes_set = set(json.load(f))
        except:
            pass

        seen = set()
        tissues_seen = set()
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) < 6:
                continue
            gene, tissue, cell_type, level = parts[1], parts[2], parts[3], parts[4]

            if gene not in all_genes_set or level in ("Not detected", ""):
                continue

            key = f"{gene}-{tissue}"
            if key in seen:
                continue
            seen.add(key)

            t_id = f"ANAT-{tissue.replace(' ', '_')[:30]}"
            if tissue not in tissues_seen:
                entities.append({"entity_id": t_id, "entity_type": "Anatomy", "name": tissue})
                tissues_seen.add(tissue)
            edges.append({
                "source": t_id, "target": gene,
                "type": "Anatomy-expresses-Gene",
                "level": level,
            })

        log.info("  HPA: %d tissue-gene edges, %d tissues", len(edges), len(tissues_seen))

    except Exception as e:
        log.error("  HPA download failed: %s", e)

    out = SHARD_DIR / "hpa_v23.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("HPA → %s", out)


# ═══════════════════════════════════════════════════════════════════════════
# Phase 3: TF-target edges from Enrichr ChIP-seq libraries
# ═══════════════════════════════════════════════════════════════════════════

def populate_tf_targets():
    """Extract TF-target from Enrichr ENCODE/ChEA ChIP-seq data."""
    log.info("Enrichr TF-targets from ChIP-seq...")
    edges = []
    all_genes_set = set()
    try:
        with open(GENE_LIST) as f:
            all_genes_set = set(json.load(f))
    except:
        pass

    for lib in ["ENCODE_and_ChEA_Consensus_TFs_from_ChIP-X",
                "ENCODE_TF_ChIP-seq_2015"]:
        url = f"https://maayanlab.cloud/Enrichr/geneSetLibrary?mode=json&libraryName={urllib.parse.quote(lib)}"
        try:
            data = json.loads(_http_get(url, timeout=30))
            terms = data.get(lib, data)
            n = 0
            if isinstance(terms, dict):
                for term_name, gene_list in terms.items():
                    tf = term_name.split("_")[0].split(" ")[0].upper()
                    if tf not in all_genes_set:
                        continue
                    targets = gene_list if isinstance(gene_list, list) else list(gene_list.keys()) if isinstance(gene_list, dict) else []
                    for t in targets:
                        t_up = t.upper().split(",")[0].strip()
                        if t_up in all_genes_set and t_up != tf:
                            edges.append({"source": tf, "target": t_up,
                                          "type": "Protein-regulates-Gene",
                                          "source_db": lib[:30]})
                            n += 1
            log.info("  %s: %d edges", lib[:40], n)
        except Exception as e:
            log.warning("  %s failed: %s", lib[:20], e)
        time.sleep(1)

    out = SHARD_DIR / "tf_targets_enrichr.json"
    with open(out, "w") as f:
        json.dump({"edges": edges}, f)
    log.info("TF-targets: %d edges → %s", len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True,
                        choices=["diseases", "hpa", "tf_targets", "all"])
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--total-shards", type=int, default=1)
    args = parser.parse_args()

    if args.phase == "all":
        populate_hpa()
        populate_tf_targets()
    elif args.phase == "diseases":
        populate_diseases(args.shard, args.total_shards)
    elif args.phase == "hpa":
        populate_hpa()
    elif args.phase == "tf_targets":
        populate_tf_targets()


if __name__ == "__main__":
    main()
