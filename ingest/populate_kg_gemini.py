#!/usr/bin/env python3
"""Gemini-powered KG population — uses Gemini API to extract structured
biological knowledge for genes that can't be fully covered by free APIs.

This handles:
1. Disease associations (via Gemini parsing of gene summaries + GeneRIF)
2. Drug targets (via Gemini extraction from literature)
3. Clinical relevance (via Gemini reasoning about gene function)
4. HPA tissue expression (from proteinatlas.org v23)
5. TF-target relationships (from Enrichr gene set libraries)

Uses Gemini API tokens instead of Claude.

Run: python populate_kg_gemini.py --phase all --shard 0 --total-shards 10
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

from dotenv import load_dotenv
load_dotenv(".env")
load_dotenv(".env.local", override=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("kg_gemini")

SCRATCH = Path(os.environ["KG_DATA_ROOT"])
SHARD_DIR = SCRATCH / "kg_shards"
GENE_LIST = SCRATCH / "all_genes.json"
GEMINI_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")


def _http_get(url, timeout=20):
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GBD/0.1", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception:
            if i == 2: raise
            time.sleep(2 * (i + 1))


def get_shard_genes(shard, total):
    with open(GENE_LIST) as f:
        genes = json.load(f)
    size = len(genes) // total + 1
    return genes[shard * size: min((shard + 1) * size, len(genes))]


def gemini_extract(prompt: str, max_tokens: int = 1024) -> str:
    """Call Gemini API for structured extraction."""
    if not GEMINI_KEY:
        return ""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.1},
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
        candidates = resp.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "")
    except Exception as e:
        log.debug("Gemini failed: %s", e)
    return ""


# ═══════════════════════════════════════════════════════════════════════════
# Phase 1: Gemini-powered disease + drug extraction from gene summaries
# ═══════════════════════════════════════════════════════════════════════════

def populate_disease_drug_gemini(shard: int, total: int):
    """Use Gemini to extract disease associations and drug targets from
    gene summaries obtained via MyGene.info.

    For each batch of genes:
    1. Fetch gene summaries + GeneRIF from MyGene
    2. Send to Gemini: "Extract diseases, drugs, and clinical relevance"
    3. Parse structured JSON response
    """
    genes = get_shard_genes(shard, total)
    log.info("Gemini disease/drug shard %d: %d genes", shard, len(genes))

    edges = []
    entities = []

    for batch_start in range(0, len(genes), 20):
        batch = genes[batch_start:batch_start + 20]

        # Get summaries from MyGene
        try:
            data = urllib.parse.urlencode({
                "q": ",".join(batch),
                "scopes": "symbol",
                "species": "human",
                "fields": "symbol,name,summary,generif",
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://mygene.info/v3/query", data=data,
                headers={"User-Agent": "GBD/0.1", "Accept": "application/json",
                         "Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                hits = json.loads(r.read())
        except Exception as e:
            log.warning("  MyGene batch %d failed: %s", batch_start, e)
            continue

        # Build context for Gemini
        gene_info = {}
        for h in hits:
            if not isinstance(h, dict) or h.get("notfound"):
                continue
            sym = h.get("symbol", "")
            summary = (h.get("summary") or "")[:500]
            generif = h.get("generif", [])
            if isinstance(generif, list):
                rif_text = " ".join(g.get("text", "")[:100] for g in generif[:3] if isinstance(g, dict))
            else:
                rif_text = ""
            if sym and (summary or rif_text):
                gene_info[sym] = f"{summary} {rif_text}"[:600]

        if not gene_info:
            continue

        # Gemini extraction
        gene_text = "\n".join(f"- {sym}: {info}" for sym, info in gene_info.items())
        prompt = f"""Extract disease associations and drug targets from these gene descriptions.
Return ONLY a JSON array. Each element should have:
{{"gene": "SYMBOL", "diseases": ["disease1", "disease2"], "drugs": ["drug1"], "cancer_relevant": true/false}}

Only include diseases and drugs explicitly mentioned. If none mentioned, use empty arrays.

Genes:
{gene_text}

Return JSON array only, no markdown:"""

        try:
            response = gemini_extract(prompt, max_tokens=2048)
            # Parse JSON from response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[1].rsplit("```", 1)[0]
            parsed = json.loads(response)

            for item in parsed:
                if not isinstance(item, dict):
                    continue
                gene = item.get("gene", "")
                for disease in item.get("diseases", [])[:5]:
                    d_id = f"DIS-{disease[:30].replace(' ', '_')}"
                    entities.append({"entity_id": d_id, "entity_type": "Disease", "name": disease})
                    edges.append({"source": d_id, "target": gene, "type": "Disease-associates-Gene",
                                  "source_db": "Gemini_extraction"})
                for drug in item.get("drugs", [])[:3]:
                    dr_id = f"DRUG-{drug[:30].replace(' ', '_')}"
                    entities.append({"entity_id": dr_id, "entity_type": "Compound", "name": drug})
                    edges.append({"source": dr_id, "target": gene, "type": "Compound-binds-Protein",
                                  "source_db": "Gemini_extraction"})

        except Exception as e:
            log.debug("  Gemini parse failed for batch %d: %s", batch_start, e)

        if (batch_start + 20) % 100 == 0:
            log.info("  %d/%d genes, %d disease edges, %d drug edges",
                     batch_start + 20, len(genes),
                     sum(1 for e in edges if "Disease" in e["type"]),
                     sum(1 for e in edges if "Compound" in e["type"]))
        time.sleep(0.5)  # Gemini rate limit

    out = SHARD_DIR / f"gemini_disease_drug_{shard:03d}.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("Gemini shard %d: %d entities, %d edges → %s",
             shard, len(entities), len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2: HPA tissue expression (fixed URL)
# ═══════════════════════════════════════════════════════════════════════════

def populate_hpa_v23():
    """Download HPA normal tissue from v23 (working URL)."""
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

        seen_edges = set()
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) < 6:
                continue
            gene = parts[1]
            tissue = parts[2]
            cell_type = parts[3]
            level = parts[4]

            if gene not in all_genes_set or level in ("Not detected", ""):
                continue

            # Deduplicate
            edge_key = f"{gene}-{tissue}-{cell_type}"
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)

            tissue_id = f"ANAT-{tissue.replace(' ', '_')[:30]}"
            entities.append({"entity_id": tissue_id, "entity_type": "Anatomy", "name": tissue})
            edges.append({
                "source": tissue_id, "target": gene,
                "type": "Anatomy-expresses-Gene",
                "level": level, "cell_type": cell_type,
            })

        log.info("  HPA: %d unique tissue-gene edges", len(edges))

    except Exception as e:
        log.error("  HPA download failed: %s", e)

    out = SHARD_DIR / "hpa_v23.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("HPA → %s", out)


# ═══════════════════════════════════════════════════════════════════════════
# Phase 3: TF-target from Enrichr gene set libraries
# ═══════════════════════════════════════════════════════════════════════════

def populate_tf_targets_enrichr():
    """Extract TF-target edges from Enrichr's ENCODE/ChEA libraries.

    These libraries contain TF→target gene sets derived from ChIP-seq.
    """
    log.info("Enrichr TF-targets: Querying ChIP-seq-derived TF-target edges...")
    edges = []
    all_genes_set = set()
    try:
        with open(GENE_LIST) as f:
            all_genes_set = set(json.load(f))
    except:
        pass

    # Download library gene sets
    for lib in ["ENCODE_and_ChEA_Consensus_TFs_from_ChIP-X",
                "ENCODE_TF_ChIP-seq_2015"]:
        url = f"https://maayanlab.cloud/Enrichr/geneSetLibrary?mode=json&libraryName={urllib.parse.quote(lib)}"
        try:
            data = json.loads(_http_get(url, timeout=30))
            terms = data.get(lib, data)
            if isinstance(terms, dict):
                n_edges = 0
                for term_name, gene_list in terms.items():
                    # Term format: "STAT1_ChIP-Seq_ENCODE" or "STAT1 ENCODE"
                    tf = term_name.split("_")[0].split(" ")[0].upper()
                    if tf not in all_genes_set:
                        continue

                    targets = []
                    if isinstance(gene_list, list):
                        targets = [g for g in gene_list if isinstance(g, str)]
                    elif isinstance(gene_list, dict):
                        targets = list(gene_list.keys())

                    for target in targets:
                        target_up = target.upper().split(",")[0].strip()
                        if target_up in all_genes_set:
                            edges.append({
                                "source": tf, "target": target_up,
                                "type": "Protein-regulates-Gene",
                                "source_db": lib[:30],
                            })
                            n_edges += 1

                log.info("  %s: %d TF-target edges", lib[:30], n_edges)
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
                        choices=["disease_drug", "hpa", "tf_targets", "all"])
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--total-shards", type=int, default=1)
    args = parser.parse_args()

    if args.phase == "all":
        populate_hpa_v23()
        populate_tf_targets_enrichr()
        populate_disease_drug_gemini(args.shard, args.total_shards)
    elif args.phase == "disease_drug":
        populate_disease_drug_gemini(args.shard, args.total_shards)
    elif args.phase == "hpa":
        populate_hpa_v23()
    elif args.phase == "tf_targets":
        populate_tf_targets_enrichr()


if __name__ == "__main__":
    main()
