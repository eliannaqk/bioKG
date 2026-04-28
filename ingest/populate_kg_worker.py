#!/usr/bin/env python3
"""Knowledge graph population worker — processes a shard of genes.

Fixed version: proper MyGene.info batch POST with Content-Type header.
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [shard-%(name)s] %(message)s", datefmt="%H:%M:%S")

SCRATCH = Path(os.environ["KG_DATA_ROOT"])
GENE_LIST = SCRATCH / "all_genes.json"
KG_SHARD_DIR = SCRATCH / "kg_shards"
KG_SHARD_DIR.mkdir(exist_ok=True)


def _http_get(url, timeout=20):
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GBD/0.1", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception:
            if i == 2: raise
            time.sleep(2 * (i + 1))


def get_shard_genes(shard: int, total: int) -> list[str]:
    with open(GENE_LIST) as f:
        all_genes = json.load(f)
    shard_size = len(all_genes) // total + 1
    start = shard * shard_size
    end = min(start + shard_size, len(all_genes))
    return all_genes[start:end]


def mygene_batch_query(genes: list[str], fields: str) -> list[dict]:
    """Proper MyGene.info batch POST query."""
    data = urllib.parse.urlencode({
        "q": ",".join(genes),
        "scopes": "symbol",
        "species": "human",
        "fields": fields,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://mygene.info/v3/query",
        data=data,
        headers={
            "User-Agent": "GBD/0.1",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        result = json.loads(r.read().decode("utf-8"))
    if not isinstance(result, list):
        result = [result]
    return result


def populate_genes_shard(shard: int, total: int):
    """Phase 1: Gene annotations from MyGene.info batch API."""
    genes = get_shard_genes(shard, total)
    log = logging.getLogger(str(shard))
    log.info("Shard %d/%d: %d genes (%s ... %s)", shard, total, len(genes), genes[0], genes[-1])

    results = {"entities": [], "edges": []}
    fields = "symbol,entrezgene,name,summary,pathway.reactome,pathway.kegg,go.BP,go.CC,go.MF"

    # Batch size 100 — safe for POST body size
    for batch_start in range(0, len(genes), 100):
        batch = genes[batch_start:batch_start + 100]

        try:
            hits = mygene_batch_query(batch, fields)
            n_found = 0

            for h in hits:
                if not isinstance(h, dict) or h.get("notfound"):
                    continue
                symbol = h.get("symbol", h.get("query", ""))
                if not symbol:
                    continue
                n_found += 1

                # Entity
                results["entities"].append({
                    "entity_id": symbol,
                    "entity_type": "Gene",
                    "name": h.get("name", symbol),
                    "xrefs": {"entrez": str(h.get("entrezgene", ""))},
                    "summary": (h.get("summary") or "")[:300],
                })

                # Helper: MyGene returns dict for single items, list for multiple
                def _as_list(val):
                    if val is None: return []
                    if isinstance(val, dict): return [val]
                    if isinstance(val, list): return val
                    return []

                # GO Biological Process
                go = h.get("go", {})
                if not isinstance(go, dict):
                    go = {}
                for bp in _as_list(go.get("BP"))[:8]:
                    if isinstance(bp, dict) and "id" in bp:
                        results["edges"].append({
                            "source": symbol, "target": bp["id"],
                            "type": "Gene-participates-BiologicalProcess",
                            "target_name": bp.get("term", ""),
                            "target_type": "BiologicalProcess",
                        })

                # GO Cellular Component
                for cc in _as_list(go.get("CC"))[:5]:
                    if isinstance(cc, dict) and "id" in cc:
                        results["edges"].append({
                            "source": symbol, "target": cc["id"],
                            "type": "Gene-participates-CellularComponent",
                            "target_name": cc.get("term", ""),
                            "target_type": "CellularComponent",
                        })

                # GO Molecular Function
                for mf in _as_list(go.get("MF"))[:5]:
                    if isinstance(mf, dict) and "id" in mf:
                        results["edges"].append({
                            "source": symbol, "target": mf["id"],
                            "type": "Gene-participates-MolecularFunction",
                            "target_name": mf.get("term", ""),
                            "target_type": "MolecularFunction",
                        })

                # Pathways
                pw = h.get("pathway", {})
                if not isinstance(pw, dict):
                    pw = {}
                for src in ["reactome", "kegg"]:
                    pathways = _as_list(pw.get(src))
                    for p in pathways[:8]:
                        if isinstance(p, dict) and "name" in p:
                            results["edges"].append({
                                "source": symbol,
                                "target": p.get("id", p["name"][:30]),
                                "type": "Gene-participates-Pathway",
                                "target_name": p["name"],
                                "target_type": "Pathway",
                                "source_db": src,
                            })

            log.info("  Batch %d-%d: %d/%d resolved, %d entities, %d edges total",
                     batch_start, batch_start + len(batch), n_found, len(batch),
                     len(results["entities"]), len(results["edges"]))

        except Exception as e:
            log.warning("  Batch %d failed: %s", batch_start, e)

        time.sleep(0.3)

    # Save shard
    out_path = KG_SHARD_DIR / f"genes_shard_{shard:03d}.json"
    with open(out_path, "w") as f:
        json.dump(results, f)
    log.info("Shard %d complete: %d entities, %d edges → %s",
             shard, len(results["entities"]), len(results["edges"]), out_path)


def populate_interactions_shard(shard: int, total: int):
    """Phase 2: STRING PPI for a shard of genes."""
    genes = get_shard_genes(shard, total)
    log = logging.getLogger(str(shard))
    log.info("PPI shard %d: %d genes", shard, len(genes))

    edges = []
    for batch_start in range(0, len(genes), 50):
        batch = genes[batch_start:batch_start + 50]
        identifiers = "%0d".join(batch)
        url = (
            f"https://string-db.org/api/json/network"
            f"?identifiers={urllib.parse.quote(identifiers)}"
            f"&species=9606&limit=5"
        )
        try:
            data = json.loads(_http_get(url, timeout=30))
            for item in data:
                a = item.get("preferredName_A", "")
                b = item.get("preferredName_B", "")
                score = item.get("score", 0)
                if a and b and score >= 0.4:
                    edges.append({"source": a, "target": b, "score": score,
                                  "type": "Protein-interacts-Protein"})
            log.info("  PPI batch %d: %d interactions", batch_start, len(data))
        except Exception as e:
            log.warning("  STRING batch %d failed: %s", batch_start, e)
        time.sleep(1.5)

    out_path = KG_SHARD_DIR / f"ppi_shard_{shard:03d}.json"
    with open(out_path, "w") as f:
        json.dump({"edges": edges}, f)
    log.info("PPI shard %d: %d edges → %s", shard, len(edges), out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--total-shards", type=int, required=True)
    parser.add_argument("--phase", default="genes", choices=["genes", "interactions"])
    args = parser.parse_args()

    if args.phase == "genes":
        populate_genes_shard(args.shard, args.total_shards)
    elif args.phase == "interactions":
        populate_interactions_shard(args.shard, args.total_shards)


if __name__ == "__main__":
    main()
