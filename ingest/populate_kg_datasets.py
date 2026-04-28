#!/usr/bin/env python3
"""Populate KG with additional datasets: LINCS, HPA, DisGeNET, TFLink, DrugBank, ClinVar.

Each phase queries free public APIs and writes shard JSONs.
Uses Gemini API for any parsing that needs LLM intelligence.

Run as SLURM array:
  python populate_kg_datasets.py --phase lincs --shard 0 --total-shards 5
  python populate_kg_datasets.py --phase hpa
  python populate_kg_datasets.py --phase disgenet --shard 0 --total-shards 10
  python populate_kg_datasets.py --phase tflink
  python populate_kg_datasets.py --phase drugbank
  python populate_kg_datasets.py --phase clinvar --shard 0 --total-shards 10
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
log = logging.getLogger("kg_data")

SCRATCH = Path(os.environ["KG_DATA_ROOT"])
SHARD_DIR = SCRATCH / "kg_shards"
SHARD_DIR.mkdir(exist_ok=True)

GENE_LIST = SCRATCH / "all_genes.json"


def _http_get(url, timeout=20):
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "GBD/0.1", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception:
            if i == 2: raise
            time.sleep(2 * (i + 1))


def _http_post(url, data_dict, timeout=30):
    data = urllib.parse.urlencode(data_dict).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": "GBD/0.1", "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def get_shard_genes(shard, total):
    with open(GENE_LIST) as f:
        genes = json.load(f)
    size = len(genes) // total + 1
    return genes[shard * size: min((shard + 1) * size, len(genes))]


def get_all_genes():
    with open(GENE_LIST) as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════════════
# LINCS L1000: KGene→downregulates/upregulates→Gene
# ═══════════════════════════════════════════════════════════════════════════

def populate_lincs(shard: int, total: int):
    """Query Enrichr LINCS libraries for perturbation edges.

    LINCS L1000 tells us: when you knock out gene X, which genes go up/down?
    This is Level 4 perturbational evidence.
    """
    genes = get_shard_genes(shard, total)
    log.info("LINCS shard %d: %d genes", shard, len(genes))
    all_gene_set = set(get_all_genes())
    edges = []

    libraries = [
        "LINCS_L1000_CRISPR_KO_Consensus_Sigs",
        "LINCS_L1000_Ligand_Perturbations_up",
        "LINCS_L1000_Ligand_Perturbations_down",
    ]

    # Query each gene individually for its KO signature
    for i, gene in enumerate(genes):
        if (i + 1) % 50 == 0:
            log.info("  %d/%d genes", i + 1, len(genes))

        for lib in libraries:
            url = f"https://maayanlab.cloud/Enrichr/geneSetLibrary?mode=json&libraryName={lib}"
            # Enrichr doesn't support per-gene queries easily, so we use a different approach:
            # Query the gene as a single-gene set and see what terms it appears in
            try:
                resp = _http_post("https://maayanlab.cloud/Enrichr/addList", {
                    "list": gene, "description": f"GBD_{gene}",
                })
                list_id = json.loads(resp).get("userListId")
                if not list_id:
                    continue
                time.sleep(0.3)

                enrich_resp = _http_get(
                    f"https://maayanlab.cloud/Enrichr/enrich?userListId={list_id}&backgroundType={lib}",
                    timeout=20,
                )
                results = json.loads(enrich_resp).get(lib, [])

                for row in results[:10]:
                    if len(row) >= 6:
                        term = row[1]  # e.g., "STAT1 knockdown - A549"
                        p_val = row[2]
                        overlap = row[5]  # overlapping genes

                        # Parse perturbation type
                        if "knockdown" in term.lower() or "ko " in term.lower() or "crispr" in term.lower():
                            edge_type = "KGene-regulates-Gene"
                        else:
                            edge_type = "Compound-regulates-Gene"

                        perturbed = term.split(" ")[0] if " " in term else term

                        for target in overlap:
                            if target.upper() in all_gene_set or target in all_gene_set:
                                edges.append({
                                    "source": perturbed,
                                    "target": target,
                                    "type": edge_type,
                                    "p_value": p_val,
                                    "term": term[:80],
                                    "library": lib[:30],
                                })

            except Exception:
                pass
            time.sleep(0.2)

    out = SHARD_DIR / f"lincs_shard_{shard:03d}.json"
    with open(out, "w") as f:
        json.dump({"edges": edges}, f)
    log.info("LINCS shard %d: %d edges → %s", shard, len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════
# HPA: Gene-expressedIN-CellType, Anatomy-expresses-Gene
# ═══════════════════════════════════════════════════════════════════════════

def populate_hpa():
    """Download Human Protein Atlas normal tissue + cell type data.

    HPA provides: which genes are expressed in which tissues and cell types.
    Direct TSV download — no API rate limits.
    """
    log.info("HPA: Downloading tissue and cell type expression data...")
    edges = []
    entities = []

    # Normal tissue data
    url = "https://www.proteinatlas.org/download/normal_tissue.tsv.zip"
    try:
        import io, zipfile
        raw = urllib.request.urlopen(url, timeout=120).read()
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            with zf.open(zf.namelist()[0]) as f:
                lines = f.read().decode("utf-8").splitlines()

        header = lines[0].split("\t")
        log.info("  HPA normal tissue: %d rows, columns: %s", len(lines) - 1, header)

        all_genes = set(get_all_genes())
        tissue_genes = {}  # {tissue: [genes]}

        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) < 6:
                continue
            gene = parts[1]  # Gene name
            tissue = parts[2]  # Tissue
            cell_type = parts[3]  # Cell type
            level = parts[4]  # Expression level: Not detected, Low, Medium, High
            reliability = parts[5] if len(parts) > 5 else ""

            if gene not in all_genes:
                continue
            if level in ("Not detected", ""):
                continue

            # Gene-expressedIN-CellType (via AnatomyCellType)
            act_id = f"ACT-{tissue}-{cell_type}".replace(" ", "_")[:50]
            entities.append({
                "entity_id": act_id,
                "entity_type": "AnatomyCellType",
                "name": f"{cell_type} in {tissue}",
            })
            edges.append({
                "source": act_id, "target": gene,
                "type": "AnatomyCellType-expresses-Gene",
                "properties": {"level": level, "reliability": reliability},
            })

            # Track tissue-gene for Anatomy-expresses-Gene
            if tissue not in tissue_genes:
                tissue_genes[tissue] = set()
                entities.append({
                    "entity_id": f"ANAT-{tissue.replace(' ','_')[:30]}",
                    "entity_type": "Anatomy",
                    "name": tissue,
                })
            tissue_genes[tissue].add(gene)

        # Add Anatomy-expresses-Gene (deduplicated)
        for tissue, genes_set in tissue_genes.items():
            for gene in genes_set:
                edges.append({
                    "source": f"ANAT-{tissue.replace(' ','_')[:30]}",
                    "target": gene,
                    "type": "Anatomy-expresses-Gene",
                })

        log.info("  HPA: %d entities, %d edges", len(entities), len(edges))

    except Exception as e:
        log.error("  HPA download failed: %s", e)

    out = SHARD_DIR / "hpa_tissue.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("HPA → %s", out)


# ═══════════════════════════════════════════════════════════════════════════
# DisGeNET: Disease-associates-Gene
# ═══════════════════════════════════════════════════════════════════════════

def populate_disgenet(shard: int, total: int):
    """Query DisGeNET via MyGene.info for gene-disease associations."""
    genes = get_shard_genes(shard, total)
    log.info("DisGeNET shard %d: %d genes", shard, len(genes))
    edges = []
    entities = []

    for batch_start in range(0, len(genes), 100):
        batch = genes[batch_start:batch_start + 100]
        try:
            data = urllib.parse.urlencode({
                "q": ",".join(batch),
                "scopes": "symbol",
                "species": "human",
                "fields": "symbol,disgenet",
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://mygene.info/v3/query",
                data=data,
                headers={"User-Agent": "GBD/0.1", "Accept": "application/json",
                          "Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                hits = json.loads(r.read())

            if not isinstance(hits, list):
                hits = [hits]

            for h in hits:
                if not isinstance(h, dict) or h.get("notfound"):
                    continue
                sym = h.get("symbol", "")
                dg = h.get("disgenet", [])
                if isinstance(dg, dict):
                    dg = [dg]
                for assoc in (dg or [])[:15]:
                    if not isinstance(assoc, dict):
                        continue
                    disease = assoc.get("disease_name", "")
                    score = assoc.get("score", 0)
                    if score > 0.05 and disease:
                        d_id = f"DG-{disease[:40].replace(' ','_')}"
                        entities.append({
                            "entity_id": d_id,
                            "entity_type": "Disease",
                            "name": disease,
                        })
                        edges.append({
                            "source": d_id, "target": sym,
                            "type": "Disease-associates-Gene",
                            "score": score,
                        })

            log.info("  Batch %d: %d disease edges", batch_start, len(edges))
        except Exception as e:
            log.warning("  Batch %d failed: %s", batch_start, e)
        time.sleep(0.5)

    out = SHARD_DIR / f"disgenet_shard_{shard:03d}.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("DisGeNET shard %d: %d edges → %s", shard, len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════
# TFLink: Protein-regulates-Gene (TF→target)
# ═══════════════════════════════════════════════════════════════════════════

def populate_tflink():
    """Download TFLink TF-target edges.

    TFLink provides experimentally validated TF→gene regulatory relationships.
    """
    log.info("TFLink: Downloading TF-target regulatory edges...")
    edges = []
    all_genes = set(get_all_genes())

    # TFLink provides a bulk download
    url = "https://tflink.net/api/interactions/?species=Homo+sapiens&format=json&page_size=1000"
    page = 1
    total_fetched = 0

    while url and total_fetched < 50000:
        try:
            resp = json.loads(_http_get(url, timeout=30))
            results = resp.get("results", [])
            if not results:
                break

            for r in results:
                tf = r.get("source_name", "").upper()
                target = r.get("target_name", "").upper()
                score = r.get("confidence_score", 0)

                if tf in all_genes and target in all_genes:
                    edges.append({
                        "source": tf, "target": target,
                        "type": "Protein-regulates-Gene",
                        "score": score,
                        "source_db": "TFLink",
                    })

            total_fetched += len(results)
            url = resp.get("next")  # pagination
            log.info("  Page %d: %d results, %d edges total", page, len(results), len(edges))
            page += 1
            time.sleep(0.5)

        except Exception as e:
            log.warning("  TFLink page %d failed: %s", page, e)
            break

    out = SHARD_DIR / "tflink.json"
    with open(out, "w") as f:
        json.dump({"edges": edges}, f)
    log.info("TFLink: %d TF-target edges → %s", len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════
# DrugBank/ChEMBL: Compound-binds-Protein, Compound-treats-Disease
# ═══════════════════════════════════════════════════════════════════════════

def populate_drugbank():
    """Query drug-target relationships via Enrichr and DGIdb.

    Uses DGIdb (Drug-Gene Interaction Database) — free, no auth required.
    """
    log.info("DGIdb: Querying drug-gene interactions...")
    edges = []
    entities = []
    all_genes = get_all_genes()

    # DGIdb API — query in batches
    for batch_start in range(0, len(all_genes), 100):
        batch = all_genes[batch_start:batch_start + 100]
        gene_str = ",".join(batch)
        url = f"https://dgidb.org/api/v2/interactions.json?genes={urllib.parse.quote(gene_str)}"

        try:
            resp = json.loads(_http_get(url, timeout=30))
            for match in resp.get("matchedTerms", []):
                gene = match.get("geneName", "")
                for interaction in match.get("interactions", [])[:10]:
                    drug = interaction.get("drugName", "")
                    int_type = interaction.get("interactionType", "")
                    sources = interaction.get("sources", [])

                    if drug and gene:
                        drug_id = f"DRUG-{drug[:30].replace(' ','_')}"
                        entities.append({
                            "entity_id": drug_id,
                            "entity_type": "Compound",
                            "name": drug,
                        })
                        edges.append({
                            "source": drug_id, "target": gene,
                            "type": "Compound-binds-Protein",
                            "interaction_type": int_type,
                            "n_sources": len(sources),
                        })

            if (batch_start + 100) % 500 == 0:
                log.info("  %d genes queried, %d drug edges", batch_start + 100, len(edges))
        except Exception as e:
            log.warning("  DGIdb batch %d failed: %s", batch_start, e)
        time.sleep(0.3)

    out = SHARD_DIR / "drugbank.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("DGIdb: %d drug-gene edges → %s", len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════
# ClinVar/GWAS: Variant-associates-Phenotype, Variant-maps-Gene
# ═══════════════════════════════════════════════════════════════════════════

def populate_clinvar(shard: int, total: int):
    """Query ClinVar via MyGene.info for variant-gene-disease links."""
    genes = get_shard_genes(shard, total)
    log.info("ClinVar shard %d: %d genes", shard, len(genes))
    edges = []
    entities = []

    for batch_start in range(0, len(genes), 100):
        batch = genes[batch_start:batch_start + 100]
        try:
            data = urllib.parse.urlencode({
                "q": ",".join(batch),
                "scopes": "symbol",
                "species": "human",
                "fields": "symbol,clinvar",
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://mygene.info/v3/query",
                data=data,
                headers={"User-Agent": "GBD/0.1", "Accept": "application/json",
                          "Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                hits = json.loads(r.read())

            if not isinstance(hits, list):
                hits = [hits]

            for h in hits:
                if not isinstance(h, dict) or h.get("notfound"):
                    continue
                sym = h.get("symbol", "")
                clinvar = h.get("clinvar", {})
                if not isinstance(clinvar, dict):
                    continue

                # Variant entries
                for var in (clinvar.get("variant", []) or [])[:5]:
                    if not isinstance(var, dict):
                        if isinstance(clinvar.get("variant"), dict):
                            var = clinvar["variant"]
                        else:
                            continue
                    var_id = var.get("rsid", var.get("hgvs", {}).get("genomic", ""))
                    if not var_id:
                        continue

                    significance = var.get("clinical_significance", "")
                    conditions = var.get("rcv", [])
                    if isinstance(conditions, dict):
                        conditions = [conditions]

                    entities.append({
                        "entity_id": f"VAR-{var_id}",
                        "entity_type": "Variant",
                        "name": f"{sym} {var_id}",
                    })
                    edges.append({
                        "source": f"VAR-{var_id}", "target": sym,
                        "type": "Variant-maps-Gene",
                        "significance": significance,
                    })

                    for cond in (conditions or [])[:3]:
                        if isinstance(cond, dict):
                            phenotype = cond.get("conditions", {})
                            if isinstance(phenotype, dict):
                                name = phenotype.get("name", "")
                            elif isinstance(phenotype, list) and phenotype:
                                name = phenotype[0].get("name", "") if isinstance(phenotype[0], dict) else str(phenotype[0])
                            else:
                                name = str(phenotype)[:50]
                            if name:
                                edges.append({
                                    "source": f"VAR-{var_id}",
                                    "target": f"PHE-{name[:30].replace(' ','_')}",
                                    "type": "Variant-associates-Phenotype",
                                    "significance": significance,
                                })
                    break  # just first variant per gene

            log.info("  Batch %d: %d variant edges", batch_start, len(edges))
        except Exception as e:
            log.warning("  ClinVar batch %d failed: %s", batch_start, e)
        time.sleep(0.5)

    out = SHARD_DIR / f"clinvar_shard_{shard:03d}.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("ClinVar shard %d: %d edges → %s", shard, len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True,
                        choices=["lincs", "hpa", "disgenet", "tflink", "drugbank", "clinvar"])
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--total-shards", type=int, default=1)
    args = parser.parse_args()

    if args.phase == "lincs":
        populate_lincs(args.shard, args.total_shards)
    elif args.phase == "hpa":
        populate_hpa()
    elif args.phase == "disgenet":
        populate_disgenet(args.shard, args.total_shards)
    elif args.phase == "tflink":
        populate_tflink()
    elif args.phase == "drugbank":
        populate_drugbank()
    elif args.phase == "clinvar":
        populate_clinvar(args.shard, args.total_shards)


if __name__ == "__main__":
    main()
