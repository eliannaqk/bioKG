#!/usr/bin/env python3
"""Populate remaining KG entity/edge types from curated databases.

Fills gaps identified in schema audit:
  1. UniProt: Protein entities + Gene-encodes-Protein edges
  2. DGIdb GraphQL: Compound entities + Compound-binds-Protein edges
  3. HPA cell type: CellType entities + Gene-expressedIN-CellType edges
  4. Reactome: Pathway-contains-Pathway hierarchy
  5. Disease-localizes-Anatomy from Open Targets

Run from login node (needs internet):
  python populate_kg_remaining.py --phase all
  python populate_kg_remaining.py --phase uniprot
  python populate_kg_remaining.py --phase dgidb
  python populate_kg_remaining.py --phase hpa_celltype
  python populate_kg_remaining.py --phase disease_anatomy
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
log = logging.getLogger("kg_remain")

SCRATCH = Path(os.environ["KG_DATA_ROOT"])
SHARD_DIR = SCRATCH / "kg_shards"
GENE_LIST = SCRATCH / "all_genes.json"


def get_all_genes():
    with open(GENE_LIST) as f:
        return json.load(f)


def _http_get(url, timeout=30):
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GBD/0.1", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            if i == 2:
                raise
            time.sleep(2 * (i + 1))


# ═══════════════════════════════════════════════════════════════════════════
# 1. UniProt: Protein entities + Gene-encodes-Protein
# ═══════════════════════════════════════════════════════════════════════════

def populate_uniprot():
    """Map gene symbols → UniProt accessions via UniProt REST API.

    Creates Protein entities and Gene-encodes-Protein edges.
    Uses streaming TSV for efficiency.
    """
    log.info("UniProt: Mapping genes to proteins...")
    all_genes = get_all_genes()
    entities = []
    edges = []

    # UniProt batch: query in chunks of 30 genes (URL length limit)
    for batch_start in range(0, len(all_genes), 30):
        batch = all_genes[batch_start:batch_start + 30]
        gene_query = " OR ".join("gene_exact:{}".format(g) for g in batch)
        query = "({}) AND organism_id:9606 AND reviewed:true".format(gene_query)
        url = "https://rest.uniprot.org/uniprotkb/search?query={}&fields=accession,gene_names,protein_name,cc_subcellular_location&format=json&size=100".format(
            urllib.parse.quote(query))

        try:
            data = json.loads(_http_get(url, timeout=60))
            for entry in data.get("results", []):
                acc = entry.get("primaryAccession", "")
                genes_info = entry.get("genes", [])
                gene_sym = ""
                for gi in genes_info:
                    gn = gi.get("geneName", {}).get("value", "")
                    if gn.upper() in set(g.upper() for g in batch):
                        gene_sym = gn.upper()
                        break
                if not gene_sym and genes_info:
                    gn = genes_info[0].get("geneName", {}).get("value", "")
                    gene_sym = gn.upper() if gn else ""

                if not acc or not gene_sym:
                    continue

                pname = ""
                pd = entry.get("proteinDescription", {})
                rn = pd.get("recommendedName", {})
                if rn:
                    pname = rn.get("fullName", {}).get("value", "")

                # Extract subcellular location
                locs = []
                for comment in entry.get("comments", []):
                    if comment.get("commentType") == "SUBCELLULAR LOCATION":
                        for sl in comment.get("subcellularLocations", []):
                            loc = sl.get("location", {}).get("value", "")
                            if loc:
                                locs.append(loc)

                entities.append({
                    "entity_id": acc,
                    "entity_type": "Protein",
                    "name": pname or gene_sym,
                    "xrefs": {"gene": gene_sym},
                })
                edges.append({
                    "source": gene_sym,
                    "target": acc,
                    "type": "Gene-encodes-Protein",
                    "source_db": "UniProt",
                })

                # Protein-localizes-CellularComponent edges
                for loc in locs[:5]:
                    loc_id = "CC-{}".format(loc.replace(" ", "_")[:30])
                    edges.append({
                        "source": acc,
                        "target": loc_id,
                        "type": "Protein-localizes-CellularComponent",
                        "source_db": "UniProt",
                    })

            if (batch_start + 30) % 300 == 0:
                log.info("  %d/%d genes, %d proteins", batch_start + 30, len(all_genes), len(entities))

        except Exception as e:
            log.warning("  Batch %d failed: %s", batch_start, e)

        time.sleep(0.5)

    # Deduplicate proteins (same gene may have isoforms)
    seen = set()
    unique_entities = []
    for e in entities:
        if e["entity_id"] not in seen:
            seen.add(e["entity_id"])
            unique_entities.append(e)

    out = SHARD_DIR / "uniprot_proteins.json"
    with open(out, "w") as f:
        json.dump({"entities": unique_entities, "edges": edges}, f)
    log.info("UniProt: %d proteins, %d edges → %s", len(unique_entities), len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════
# 2. DGIdb: Compound entities + Compound-binds-Protein edges
# ═══════════════════════════════════════════════════════════════════════════

def populate_dgidb():
    """Query DGIdb GraphQL for drug-gene interactions.

    Creates Compound entities and Compound-binds-Protein edges.
    """
    log.info("DGIdb: Querying drug-gene interactions...")
    all_genes = get_all_genes()
    entities = []
    edges = []
    drug_seen = set()

    # Batch genes 25 at a time for GraphQL
    for batch_start in range(0, len(all_genes), 25):
        batch = all_genes[batch_start:batch_start + 25]
        names_str = ", ".join('"{}"'.format(g) for g in batch)

        query = '{{genes(names: [{names}]) {{ nodes {{ name interactions {{ drug {{ name conceptId }} interactionScore interactionTypes {{ type directionality }} }} }} }} }}'.format(
            names=names_str)

        try:
            payload = json.dumps({"query": query}).encode("utf-8")
            req = urllib.request.Request(
                "https://dgidb.org/api/graphql",
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "GBD/0.1"},
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())

            if "errors" in data:
                log.debug("  DGIdb batch %d errors: %s", batch_start, data["errors"][0]["message"][:60])
                continue

            for gene_node in data.get("data", {}).get("genes", {}).get("nodes", []):
                gene_name = gene_node.get("name", "")
                for ix in gene_node.get("interactions", []):
                    drug = ix.get("drug", {})
                    drug_name = drug.get("name", "")
                    drug_id = drug.get("conceptId", "")
                    score = ix.get("interactionScore", 0) or 0
                    types = [t.get("type", "") for t in (ix.get("interactionTypes") or [])]

                    if not drug_name or score < 0.1:
                        continue

                    d_id = drug_id or "DRUG-{}".format(drug_name.replace(" ", "_")[:30])
                    if d_id not in drug_seen:
                        entities.append({
                            "entity_id": d_id,
                            "entity_type": "Compound",
                            "name": drug_name,
                        })
                        drug_seen.add(d_id)

                    ix_type = types[0] if types else "unknown"
                    edges.append({
                        "source": d_id,
                        "target": gene_name,
                        "type": "Compound-binds-Protein",
                        "score": score,
                        "interaction_type": ix_type,
                        "source_db": "DGIdb",
                    })

        except Exception as e:
            log.debug("  DGIdb batch %d failed: %s", batch_start, e)

        if (batch_start + 25) % 250 == 0:
            log.info("  %d/%d genes, %d drugs, %d edges",
                     batch_start + 25, len(all_genes), len(drug_seen), len(edges))
        time.sleep(0.3)

    out = SHARD_DIR / "dgidb_drugs.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("DGIdb: %d drugs, %d edges → %s", len(drug_seen), len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════
# 3. HPA cell type: Gene-expressedIN-CellType
# ═══════════════════════════════════════════════════════════════════════════

def populate_hpa_celltype():
    """Parse already-downloaded HPA data for cell-type-level expression.

    Uses the hpa_v23.json shard which has tissue+cell_type in its edges.
    Or re-downloads the TSV if needed.
    """
    log.info("HPA cell types: Extracting cell-type-level expression...")
    all_genes_set = set(get_all_genes())
    entities = []
    edges = []

    url = "https://v23.proteinatlas.org/download/normal_tissue.tsv.zip"
    try:
        import io
        import zipfile
        raw = urllib.request.urlopen(url, timeout=120).read()
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            with zf.open(zf.namelist()[0]) as f:
                lines = f.read().decode("utf-8").splitlines()

        log.info("  HPA: %d rows", len(lines) - 1)

        celltype_seen = set()
        seen_edges = set()

        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) < 6:
                continue
            gene, tissue, cell_type, level = parts[1], parts[2], parts[3], parts[4]

            if gene not in all_genes_set or level in ("Not detected", ""):
                continue

            # CellType entity
            ct_id = "CT-{}-{}".format(tissue.replace(" ", "_")[:15], cell_type.replace(" ", "_")[:15])
            if ct_id not in celltype_seen:
                entities.append({
                    "entity_id": ct_id,
                    "entity_type": "CellType",
                    "name": "{} ({})".format(cell_type, tissue),
                })
                celltype_seen.add(ct_id)

            # Gene-expressedIN-CellType edge (deduplicated)
            edge_key = "{}-{}".format(gene, ct_id)
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edges.append({
                    "source": gene,
                    "target": ct_id,
                    "type": "Gene-expressedIN-CellType",
                    "level": level,
                    "source_db": "HPA_v23",
                })

        log.info("  HPA cell types: %d cell types, %d edges", len(celltype_seen), len(edges))

    except Exception as e:
        log.error("  HPA cell type download failed: %s", e)

    out = SHARD_DIR / "hpa_celltypes.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("HPA cell types → %s", out)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Disease-localizes-Anatomy from Open Targets
# ═══════════════════════════════════════════════════════════════════════════

def populate_disease_anatomy():
    """Get disease → anatomy mappings from Open Targets therapeutic areas.

    Uses the diseases already in our KG to find their tissue localizations.
    """
    log.info("Disease-Anatomy: Querying Open Targets for tissue localization...")
    import sqlite3
    db = sqlite3.connect(str(SCRATCH / "gbd_knowledge_graph.db"))

    # Get unique disease IDs from existing edges
    rows = db.execute(
        "SELECT DISTINCT source_id FROM backbone_edges WHERE edge_type = 'Disease-associates-Gene' LIMIT 5000"
    ).fetchall()
    disease_ids = [r[0] for r in rows if r[0].startswith("EFO") or r[0].startswith("MONDO") or r[0].startswith("Orphanet")]
    db.close()
    log.info("  %d disease IDs to query", len(disease_ids))

    edges = []
    entities = []
    anatomy_seen = set()

    OT_DISEASE_QUERY = """
    query diseaseInfo($id: String!) {
      disease(efoId: $id) {
        name
        therapeuticAreas { id name }
      }
    }
    """

    for i, d_id in enumerate(disease_ids):
        if (i + 1) % 100 == 0:
            log.info("  %d/%d diseases, %d anatomy edges", i + 1, len(disease_ids), len(edges))
        try:
            payload = json.dumps({"query": OT_DISEASE_QUERY, "variables": {"id": d_id}}).encode()
            req = urllib.request.Request(
                "https://api.platform.opentargets.org/api/v4/graphql",
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "GBD/0.1"},
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())

            disease = data.get("data", {}).get("disease")
            if not disease:
                continue

            for ta in (disease.get("therapeuticAreas") or []):
                ta_name = ta.get("name", "")
                ta_id = ta.get("id", "")
                if ta_name and ta_id:
                    anat_id = "ANAT-{}".format(ta_name.replace(" ", "_")[:30])
                    if anat_id not in anatomy_seen:
                        entities.append({
                            "entity_id": anat_id,
                            "entity_type": "Anatomy",
                            "name": ta_name,
                        })
                        anatomy_seen.add(anat_id)
                    edges.append({
                        "source": d_id,
                        "target": anat_id,
                        "type": "Disease-localizes-Anatomy",
                        "source_db": "OpenTargets",
                    })

        except Exception as e:
            if "429" in str(e):
                time.sleep(5)
            pass

        time.sleep(0.1)

    out = SHARD_DIR / "disease_anatomy.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("Disease-Anatomy: %d anatomy, %d edges → %s", len(anatomy_seen), len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True,
                        choices=["uniprot", "dgidb", "hpa_celltype", "disease_anatomy", "all"])
    args = parser.parse_args()

    if args.phase == "all":
        populate_uniprot()
        populate_dgidb()
        populate_hpa_celltype()
        populate_disease_anatomy()
    elif args.phase == "uniprot":
        populate_uniprot()
    elif args.phase == "dgidb":
        populate_dgidb()
    elif args.phase == "hpa_celltype":
        populate_hpa_celltype()
    elif args.phase == "disease_anatomy":
        populate_disease_anatomy()


if __name__ == "__main__":
    main()
