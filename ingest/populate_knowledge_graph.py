#!/usr/bin/env python3
"""Populate the bioKG
sbatch scripts/populate_kg.sh

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

from gbd.knowledge_graph.graph import KnowledgeGraph
from gbd.knowledge_graph.schema import (
    Entity, EntityType, BackboneEdge, BackboneEdgeType,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("populate_kg")

KG_PATH = Path(os.environ["KG_DATA_ROOT"]) / "gbd_knowledge_graph.db"


def _http_get(url, timeout=20):
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GBD/0.1", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception:
            if i == 2: raise
            time.sleep(2 * (i + 1))


# ═══════════════════════════════════════════════════════════════════════════
# Gene sets to populate (cancer immunology focused)
# ═══════════════════════════════════════════════════════════════════════════

CANCER_IMMUNO_GENES = {
    # Antigen presentation
    "antigen_presentation": [
        "HLA-A", "HLA-B", "HLA-C", "B2M", "TAP1", "TAP2", "TAPBP",
        "PSMB8", "PSMB9", "PSMB10", "CALR", "CANX", "ERAP1", "ERAP2",
        "NLRC5", "CIITA", "RFX5", "RFXANK", "RFXAP",
    ],
    # IFN signaling
    "ifn_signaling": [
        "IFNG", "IFNGR1", "IFNGR2", "JAK1", "JAK2", "STAT1", "STAT2",
        "IRF1", "IRF2", "IRF7", "IRF9", "GBP1", "GBP2",
        "IFNB1", "IFNAR1", "IFNAR2", "TYK2",
    ],
    # Immune checkpoints
    "checkpoints": [
        "CD274", "PDCD1LG2", "PDCD1", "CTLA4", "LAG3", "HAVCR2",
        "TIGIT", "VSIR", "CD276", "VTCN1", "IDO1", "ADORA2A",
    ],
    # T cell biology
    "tcell": [
        "CD8A", "CD8B", "CD4", "CD3E", "CD3D", "CD3G",
        "GZMA", "GZMB", "GZMK", "PRF1", "FASLG",
        "IL2", "IL2RA", "IL2RB", "IL7R", "IL15", "IL21",
        "TBX21", "EOMES", "TCF7", "TOX", "NR4A1", "BATF",
        "FOXP3", "IKZF2",
    ],
    # Chemokines
    "chemokines": [
        "CXCL9", "CXCL10", "CXCL11", "CXCR3", "CCL4", "CCL5",
        "CCR5", "CXCL13", "CCL2", "CCR2",
    ],
    # NK cells
    "nk": ["NKG7", "KLRD1", "KLRK1", "NCR1", "FCGR3A"],
    # Myeloid / DC
    "myeloid": [
        "CD68", "CD163", "CD14", "CSF1R", "ITGAM", "TREM2",
        "CLEC9A", "XCR1", "BATF3", "IRF8", "FLT3",
    ],
    # TGF-beta / exclusion
    "tgfb_exclusion": [
        "TGFB1", "TGFB2", "TGFB3", "TGFBR1", "TGFBR2",
        "SMAD2", "SMAD3", "SMAD4", "SMAD7",
        "CTNNB1", "APC", "AXIN1", "AXIN2", "WNT5A", "WNT3A",
        "AXL", "TWIST1", "SNAI1", "SNAI2", "ZEB1", "CDH1",
    ],
    # Proliferation
    "proliferation": [
        "MKI67", "TOP2A", "PCNA", "CDK4", "CDK6", "CCNB1",
        "CCND1", "MYC", "AURKA", "E2F1",
    ],
    # DNA damage / repair
    "dna_repair": [
        "TP53", "BRCA1", "BRCA2", "ATM", "ATR", "CHEK1", "CHEK2",
        "MLH1", "MSH2", "MSH6", "PMS2", "POLE",
    ],
    # Oncogenes / TSGs
    "oncogenes": [
        "KRAS", "BRAF", "EGFR", "ERBB2", "PIK3CA", "PTEN",
        "RB1", "NF1", "VHL", "KEAP1", "STK11", "ARID1A",
        "IDH1", "IDH2", "FGFR3", "NRAS", "KIT", "ALK",
    ],
    # Trafficking / ER (from our MHC-I work)
    "trafficking": [
        "SEC61A1", "SEC61B", "COPA", "COPB1", "COPB2",
        "STX5", "SEC13", "SEC23A", "ARF1",
    ],
    # TMEM candidates (from our investigation)
    "tmem": ["TMEM127", "TMEM219", "TMEM8B"],
    # Metabolism
    "metabolism": [
        "HMGCR", "SQLE", "LDLR", "ABCA1", "SLC2A1", "HK2",
        "LDHA", "PKM", "IDO1", "TDO2",
    ],
}


def get_all_genes() -> list[str]:
    all_g = set()
    for genes in CANCER_IMMUNO_GENES.values():
        all_g.update(genes)
    return sorted(all_g)


# ═══════════════════════════════════════════════════════════════════════════
# Phase 1: Populate Gene entities with annotations
# ═══════════════════════════════════════════════════════════════════════════

def populate_genes(kg: KnowledgeGraph):
    """Populate Gene entities from MyGene.info with GO, pathways, domains."""
    genes = get_all_genes()
    log.info("Phase 1: Populating %d genes...", len(genes))

    for i, symbol in enumerate(genes):
        if (i + 1) % 25 == 0:
            log.info("  %d/%d genes processed", i + 1, len(genes))

        url = (
            f"https://mygene.info/v3/query"
            f"?q=symbol:{urllib.parse.quote(symbol)}&species=human"
            f"&fields=symbol,entrezgene,name,summary,"
            f"pathway.reactome,pathway.kegg,"
            f"go.BP,go.CC,go.MF,interpro"
        )
        try:
            resp = json.loads(_http_get(url))
            hits = resp.get("hits", [])
            if not hits:
                continue
            h = hits[0]

            # Create gene entity
            entity = Entity(
                entity_id=symbol,
                entity_type=EntityType.GENE,
                name=h.get("name", symbol),
                xrefs={
                    "entrez": str(h.get("entrezgene", "")),
                },
                properties={
                    "summary": (h.get("summary") or "")[:500],
                },
            )
            kg.add_entity(entity)

            # Add GO biological process edges
            go = h.get("go", {})
            bp_terms = go.get("BP", [])
            if isinstance(bp_terms, list):
                for term in bp_terms[:10]:
                    if isinstance(term, dict) and "term" in term:
                        bp_id = term.get("id", "")
                        bp_name = term["term"]
                        # Ensure BP entity exists
                        kg.add_entity(Entity(
                            entity_id=bp_id, entity_type=EntityType.BIOLOGICAL_PROCESS,
                            name=bp_name,
                        ))
                        kg.conn.execute(
                            "INSERT OR IGNORE INTO backbone_edges VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (f"E-{symbol}-{bp_id}", "Gene-participates-BiologicalProcess",
                             symbol, bp_id, "{}", "GO", 1.0),
                        )

            # Add pathway edges
            pw = h.get("pathway", {})
            for source in ["reactome", "kegg"]:
                pathways = pw.get(source, [])
                if isinstance(pathways, dict):
                    pathways = [pathways]
                if isinstance(pathways, list):
                    for p in pathways[:10]:
                        if isinstance(p, dict) and "name" in p:
                            pw_id = p.get("id", p["name"][:30])
                            kg.add_entity(Entity(
                                entity_id=pw_id, entity_type=EntityType.PATHWAY,
                                name=p["name"],
                            ))
                            kg.conn.execute(
                                "INSERT OR IGNORE INTO backbone_edges VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (f"E-{symbol}-{pw_id}", "Gene-participates-Pathway",
                                 symbol, pw_id, "{}", source, 1.0),
                            )

            # Add cellular component edges
            cc_terms = go.get("CC", [])
            if isinstance(cc_terms, list):
                for term in cc_terms[:5]:
                    if isinstance(term, dict) and "term" in term:
                        cc_id = term.get("id", "")
                        kg.add_entity(Entity(
                            entity_id=cc_id, entity_type=EntityType.CELLULAR_COMPONENT,
                            name=term["term"],
                        ))
                        kg.conn.execute(
                            "INSERT OR IGNORE INTO backbone_edges VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (f"E-{symbol}-{cc_id}", "Gene-participates-CellularComponent",
                             symbol, cc_id, "{}", "GO", 1.0),
                        )

        except Exception as e:
            log.warning("  %s failed: %s", symbol, e)

        time.sleep(0.15)  # Rate limit

    kg.conn.commit()
    log.info("Phase 1 complete")


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2: Protein-Protein interactions from STRING
# ═══════════════════════════════════════════════════════════════════════════

def populate_interactions(kg: KnowledgeGraph):
    """Populate Protein-interacts-Protein from STRING-DB."""
    genes = get_all_genes()
    log.info("Phase 2: Populating PPI for %d genes...", len(genes))

    # Batch query STRING (up to 200 at a time)
    for batch_start in range(0, len(genes), 50):
        batch = genes[batch_start:batch_start + 50]
        identifiers = "%0d".join(batch)
        url = (
            f"https://string-db.org/api/json/network"
            f"?identifiers={urllib.parse.quote(identifiers)}"
            f"&species=9606&limit=10"
        )
        try:
            data = json.loads(_http_get(url, timeout=30))
            n_edges = 0
            for item in data:
                a = item.get("preferredName_A", "")
                b = item.get("preferredName_B", "")
                score = item.get("score", 0)
                if a and b and score >= 0.4:
                    edge_id = f"PPI-{min(a,b)}-{max(a,b)}"
                    kg.conn.execute(
                        "INSERT OR IGNORE INTO backbone_edges VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (edge_id, "Protein-interacts-Protein", a, b,
                         json.dumps({"score": score, "escore": item.get("escore", 0)}),
                         "STRING", score),
                    )
                    n_edges += 1
            log.info("  Batch %d-%d: %d PPI edges", batch_start, batch_start + len(batch), n_edges)
        except Exception as e:
            log.warning("  STRING batch failed: %s", e)
        time.sleep(1)  # STRING rate limit

    kg.conn.commit()
    log.info("Phase 2 complete")


# ═══════════════════════════════════════════════════════════════════════════
# Phase 3: LINCS L1000 perturbation edges via Enrichr
# ═══════════════════════════════════════════════════════════════════════════

def populate_lincs(kg: KnowledgeGraph):
    """Populate KGene→downregulates/upregulates→Gene from LINCS via Enrichr.

    These are Level 4 perturbational molecular evidence — the most valuable
    edges for proving mechanism.
    """
    genes = get_all_genes()
    log.info("Phase 3: Populating LINCS perturbation edges...")

    # Query Enrichr's LINCS L1000 libraries for each gene set
    for group_name, group_genes in CANCER_IMMUNO_GENES.items():
        if len(group_genes) < 3:
            continue
        gene_str = "\n".join(group_genes)

        try:
            # Submit gene list
            data = urllib.parse.urlencode({
                "list": gene_str, "description": f"GBD_{group_name}"
            }).encode()
            req = urllib.request.Request(
                "https://maayanlab.cloud/Enrichr/addList",
                data=data, headers={"User-Agent": "GBD/0.1"},
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                resp = json.loads(r.read())
            list_id = resp.get("userListId")
            if not list_id:
                continue

            time.sleep(0.5)

            # Query LINCS KD library
            for library in ["LINCS_L1000_Chem_Pert_Consensus_Sigs",
                            "LINCS_L1000_CRISPR_KO_Consensus_Sigs"]:
                try:
                    url = f"https://maayanlab.cloud/Enrichr/enrich?userListId={list_id}&backgroundType={library}"
                    resp2 = json.loads(_http_get(url, timeout=20))
                    results = resp2.get(library, [])

                    n_edges = 0
                    for row in results[:20]:
                        if len(row) >= 7:
                            term = row[1]  # e.g., "STAT1 KO - MCF7"
                            p_value = row[2]
                            overlap_genes = row[5]  # genes that match

                            # Parse perturbation from term
                            parts = term.split(" - ")
                            if len(parts) >= 1:
                                perturbed = parts[0].replace(" KO", "").replace(" KD", "").strip()

                                for target_gene in overlap_genes:
                                    if target_gene in genes:
                                        edge_id = f"LINCS-{perturbed}-{target_gene}-{library[:10]}"
                                        direction = "KGene-downregulates-Gene" if "KO" in term or "KD" in term else "Compound-downregulates-Gene"
                                        kg.conn.execute(
                                            "INSERT OR IGNORE INTO backbone_edges VALUES (?, ?, ?, ?, ?, ?, ?)",
                                            (edge_id, direction, perturbed, target_gene,
                                             json.dumps({"p_value": p_value, "term": term[:100]}),
                                             "LINCS_L1000", 1 - min(p_value, 1)),
                                        )
                                        n_edges += 1
                    if n_edges:
                        log.info("  %s × %s: %d LINCS edges", group_name, library[:20], n_edges)
                except Exception as e:
                    log.debug("  Enrichr %s failed: %s", library[:20], e)

            time.sleep(1)
        except Exception as e:
            log.warning("  Enrichr submit failed for %s: %s", group_name, e)

    kg.conn.commit()
    log.info("Phase 3 complete")


# ═══════════════════════════════════════════════════════════════════════════
# Phase 4: Disease associations
# ═══════════════════════════════════════════════════════════════════════════

def populate_diseases(kg: KnowledgeGraph):
    """Populate Disease-associates-Gene from MyGene.info/DISEASES."""
    genes = get_all_genes()
    log.info("Phase 4: Populating disease associations...")

    # Add key cancer types as disease entities
    cancer_types = {
        "DOID:1909": "melanoma",
        "DOID:3908": "non-small cell lung carcinoma",
        "DOID:4450": "renal cell carcinoma",
        "DOID:4006": "bladder carcinoma",
        "DOID:5520": "head and neck squamous cell carcinoma",
        "DOID:9256": "colorectal cancer",
        "DOID:1612": "breast cancer",
        "DOID:1781": "thyroid cancer",
        "DOID:2394": "ovarian cancer",
        "DOID:10283": "prostate cancer",
    }
    for did, name in cancer_types.items():
        kg.add_entity(Entity(entity_id=did, entity_type=EntityType.DISEASE, name=name))

    # Query gene-disease associations from mygene
    for i, gene in enumerate(genes):
        if (i + 1) % 50 == 0:
            log.info("  %d/%d genes", i + 1, len(genes))
        url = f"https://mygene.info/v3/query?q=symbol:{urllib.parse.quote(gene)}&species=human&fields=disgenet"
        try:
            resp = json.loads(_http_get(url))
            hits = resp.get("hits", [])
            if hits:
                disgenet = hits[0].get("disgenet", [])
                if isinstance(disgenet, list):
                    for assoc in disgenet[:10]:
                        if isinstance(assoc, dict):
                            disease_name = assoc.get("disease_name", "")
                            score = assoc.get("score", 0)
                            if score > 0.1 and disease_name:
                                d_id = f"DG-{disease_name[:30].replace(' ','_')}"
                                kg.add_entity(Entity(
                                    entity_id=d_id, entity_type=EntityType.DISEASE,
                                    name=disease_name,
                                ))
                                kg.conn.execute(
                                    "INSERT OR IGNORE INTO backbone_edges VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    (f"DGA-{gene}-{d_id[:20]}", "Disease-associates-Gene",
                                     d_id, gene, json.dumps({"score": score}),
                                     "DisGeNET", score),
                                )
        except Exception:
            pass
        time.sleep(0.1)

    kg.conn.commit()
    log.info("Phase 4 complete")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", default="all",
                        choices=["all", "genes", "interactions", "lincs", "diseases"])
    args = parser.parse_args()

    kg = KnowledgeGraph(KG_PATH)

    phases = {
        "genes": populate_genes,
        "interactions": populate_interactions,
        "lincs": populate_lincs,
        "diseases": populate_diseases,
    }

    if args.phase == "all":
        for name, func in phases.items():
            log.info("═══ %s ═══", name.upper())
            func(kg)
    else:
        phases[args.phase](kg)

    summary = kg.summary()
    log.info("═══ KNOWLEDGE GRAPH SUMMARY ═══")
    for k, v in summary.items():
        log.info("  %-30s %s", k, v)

    kg.close()


if __name__ == "__main__":
    main()
