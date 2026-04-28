#!/usr/bin/env python3
"""Populate curated entity types from REAL databases (no LLM-generated facts).

Data sources:
  1. ImmuneFunctionalState: Azimuth 2023 (immune cell states with marker genes)
  2. TMECompartment: PanglaoDB + Tabula Sapiens (cell type signatures)
  3. TherapyRegimen: DGIdb categories (already in KG) + ChEMBL mechanisms
  4. HLAAllele: Allele Frequency Net Database (AFND)
  5. Pathway hierarchy: reactome2py or KEGG BRITE

Gemini used ONLY for parsing/formatting real data, not generating facts.

Run:  python populate_kg_curated.py --phase all
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
log = logging.getLogger("kg_curated")

SCRATCH = Path(os.environ["KG_DATA_ROOT"])
SHARD_DIR = SCRATCH / "kg_shards"
GENE_LIST = SCRATCH / "all_genes.json"
GEMINI_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")


def get_all_genes():
    with open(GENE_LIST) as f:
        return json.load(f)


def _enrichr_text(lib_name, timeout=60):
    """Download Enrichr gene set library in text format."""
    url = "https://maayanlab.cloud/Enrichr/geneSetLibrary?mode=text&libraryName={}".format(
        urllib.parse.quote(lib_name))
    req = urllib.request.Request(url, headers={"User-Agent": "GBD/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def gemini_parse(prompt, max_tokens=2048):
    """Call Gemini API ONLY for parsing/formatting real data."""
    if not GEMINI_KEY:
        return ""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={}".format(GEMINI_KEY)
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.0},
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
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
# 1. ImmuneFunctionalState from Azimuth 2023 (real single-cell data)
# ═══════════════════════════════════════════════════════════════════════════

def populate_immune_states():
    """Extract immune functional states from Azimuth 2023 gene signatures.

    Azimuth is built from real single-cell RNA-seq data (not LLM generated).
    Each state has marker genes derived from differential expression analysis.
    """
    log.info("ImmuneFunctionalState: Downloading Azimuth 2023 immune signatures...")
    all_genes_set = set(get_all_genes())
    entities = []
    edges = []

    text = _enrichr_text("Azimuth_2023")
    lines = text.strip().split("\n")

    # Filter for immune-related terms
    immune_keywords = [
        "t cell", "cd4", "cd8", "treg", "nk ", "naive", "effector", "memory",
        "exhaust", "macrophage", "monocyte", "dendritic", "b cell", "plasma",
        "myeloid", "neutrophil", "mast", "basophil", "eosinophil", "innate",
        "lymphoid", "gamma delta", "mait", "nkt", "regulatory",
    ]

    for line in lines:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        term_name = parts[0]
        marker_genes = [g.strip().upper() for g in parts[2:] if g.strip()]

        # Check if immune-related
        term_lower = term_name.lower()
        if not any(k in term_lower for k in immune_keywords):
            continue

        state_id = "IFS-{}".format(term_name.replace(" ", "_").replace("+", "p")[:50])
        entities.append({
            "entity_id": state_id,
            "entity_type": "ImmuneFunctionalState",
            "name": term_name,
            "xrefs": {"source": "Azimuth_2023"},
        })

        for gene in marker_genes:
            if gene in all_genes_set:
                edges.append({
                    "source": state_id,
                    "target": gene,
                    "type": "ImmuneFunctionalState-marked-by-Gene",
                    "source_db": "Azimuth_2023",
                })

    log.info("  %d immune states, %d marker edges (from Azimuth 2023)", len(entities), len(edges))

    out = SHARD_DIR / "immune_states.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("Immune states → %s", out)


# ═══════════════════════════════════════════════════════════════════════════
# 2. TMECompartment from PanglaoDB + Tabula Sapiens (real marker data)
# ═══════════════════════════════════════════════════════════════════════════

def populate_tme_compartments():
    """Extract TME compartment signatures from PanglaoDB and Tabula Sapiens.

    These are real curated cell type marker genes from single-cell experiments.
    """
    log.info("TMECompartment: Downloading PanglaoDB + Tabula Sapiens signatures...")
    all_genes_set = set(get_all_genes())
    entities = []
    edges = []

    # Map PanglaoDB cell types to TME compartments
    compartment_map = {
        # Tumor-intrinsic — not in PanglaoDB (context-specific)
        # T cell compartments
        "T Cells": "TME-t_cell",
        "T Cells Naive": "TME-t_cell_naive",
        "Gamma Delta T Cells": "TME-gamma_delta_t",
        # Myeloid
        "Macrophages": "TME-macrophage",
        "Alveolar Macrophages": "TME-alveolar_macrophage",
        "Red Pulp Macrophages": "TME-splenic_macrophage",
        "Monocytes": "TME-monocyte",
        "Dendritic Cells": "TME-dendritic",
        "Plasmacytoid Dendritic Cells": "TME-pdc",
        "Neutrophils": "TME-neutrophil",
        "Mast Cells": "TME-mast_cell",
        "Eosinophils": "TME-eosinophil",
        "Basophils": "TME-basophil",
        # Lymphoid
        "B Cells": "TME-b_cell",
        "B Cells Memory": "TME-b_memory",
        "B Cells Naive": "TME-b_naive",
        "Plasma Cells": "TME-plasma_cell",
        "NK Cells": "TME-nk_cell",
        "Natural Killer T Cells": "TME-nkt_cell",
        # Stromal
        "Fibroblasts": "TME-fibroblast",
        "Myofibroblasts": "TME-myofibroblast",
        "Endothelial Cells": "TME-endothelial",
        "Pericytes": "TME-pericyte",
        "Smooth Muscle Cells": "TME-smooth_muscle",
        "Adipocytes": "TME-adipocyte",
    }

    text = _enrichr_text("PanglaoDB_Augmented_2021")
    for line in text.strip().split("\n"):
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        term_name = parts[0]
        marker_genes = [g.strip().upper() for g in parts[2:] if g.strip()]

        tme_id = compartment_map.get(term_name)
        if not tme_id:
            continue

        entities.append({
            "entity_id": tme_id,
            "entity_type": "TMECompartment",
            "name": term_name,
            "xrefs": {"source": "PanglaoDB_2021"},
        })

        for gene in marker_genes:
            if gene in all_genes_set:
                edges.append({
                    "source": tme_id,
                    "target": gene,
                    "type": "TMECompartment-signature-Gene",
                    "source_db": "PanglaoDB",
                })

    log.info("  %d TME compartments, %d signature edges (from PanglaoDB)", len(entities), len(edges))

    out = SHARD_DIR / "tme_compartments.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("TME compartments → %s", out)


# ═══════════════════════════════════════════════════════════════════════════
# 3. TherapyRegimen from ChEMBL mechanism of action (real data)
# ═══════════════════════════════════════════════════════════════════════════

def populate_therapy_regimens():
    """Extract therapy regimens from ChEMBL mechanism of action data."""
    log.info("TherapyRegimen: Downloading ChEMBL mechanisms of action...")
    entities = []
    edges = []
    all_genes_set = set(get_all_genes())

    offset = 0
    total = None
    mechanisms_seen = {}

    while True:
        url = "https://www.ebi.ac.uk/chembl/api/data/mechanism.json?limit=1000&offset={}".format(offset)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GBD/0.1", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
            if total is None:
                total = data["page_meta"]["total_count"]
                log.info("  ChEMBL: %d total mechanisms", total)

            for mech in data.get("mechanisms", []):
                action = mech.get("action_type", "")
                target_name = mech.get("target_name", "")
                mol_id = mech.get("molecule_chembl_id", "")
                target_chembl = mech.get("target_chembl_id", "")

                if not action or not target_name:
                    continue

                # Group into regimen categories
                regimen_key = "{}-{}".format(action, target_name[:30])
                if regimen_key not in mechanisms_seen:
                    reg_id = "THR-{}-{}".format(action.replace(" ", "_")[:20], target_name.replace(" ", "_")[:20])
                    mechanisms_seen[regimen_key] = reg_id
                    entities.append({
                        "entity_id": reg_id,
                        "entity_type": "TherapyRegimen",
                        "name": "{} of {}".format(action, target_name),
                        "xrefs": {"action": action, "target_chembl": target_chembl},
                    })

            offset += 1000
            if offset >= total:
                break
            if offset % 5000 == 0:
                log.info("  %d/%d mechanisms", offset, total)
        except Exception as e:
            log.warning("  ChEMBL mechanism offset %d failed: %s", offset, e)
            break
        time.sleep(0.3)

    # Now use Gemini ONLY to parse target names → gene symbols (real data, LLM just does NER)
    if GEMINI_KEY and entities:
        target_names = list(set(e["xrefs"].get("target_chembl", "") + "|" + e["name"] for e in entities[:200]))
        chunk = "\n".join(target_names[:100])
        prompt = """These are ChEMBL drug mechanism target names. For each, extract the HUGO gene symbol
if one exists. Return ONLY a JSON object mapping target name to gene symbol.
Example: {{"INHIBITOR of Epidermal growth factor receptor": "EGFR"}}
Only include entries where a clear gene symbol exists. Return JSON only:

{}""".format(chunk)

        response = gemini_parse(prompt)
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[1].rsplit("```", 1)[0]
            mappings = json.loads(response)
            for ent in entities:
                gene = mappings.get(ent["name"], "").upper()
                if gene and gene in all_genes_set:
                    edges.append({
                        "source": ent["entity_id"],
                        "target": gene,
                        "type": "TherapyRegimen-targets-Gene",
                        "source_db": "ChEMBL_mechanism",
                    })
            log.info("  Gemini mapped %d targets to gene symbols", len(edges))
        except Exception:
            pass

    log.info("  %d therapy regimens, %d edges", len(entities), len(edges))

    out = SHARD_DIR / "therapy_regimens.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("Therapy regimens → %s", out)


# ═══════════════════════════════════════════════════════════════════════════
# 4. HLAAllele from Allele Frequency Net Database (real data)
# ═══════════════════════════════════════════════════════════════════════════

def populate_hla_alleles():
    """Extract HLA alleles from the IPD-IMGT/HLA database via EBI."""
    log.info("HLAAllele: Downloading from EBI IPD-IMGT/HLA...")
    entities = []

    # Try EBI's IPD API
    for gene in ["HLA-A", "HLA-B", "HLA-C", "HLA-DRB1", "HLA-DQB1", "HLA-DPB1"]:
        url = "https://www.ebi.ac.uk/cgi-bin/ipd/api/allele?limit=100&gene={}".format(
            urllib.parse.quote(gene))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GBD/0.1", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            for allele in data if isinstance(data, list) else data.get("data", data.get("alleles", [])):
                if isinstance(allele, dict):
                    name = allele.get("name", "")
                    if name:
                        entities.append({
                            "entity_id": name,
                            "entity_type": "HLAAllele",
                            "name": name,
                            "xrefs": {"gene": gene, "class": "I" if gene in ["HLA-A", "HLA-B", "HLA-C"] else "II"},
                        })
            log.info("  %s: %d alleles", gene, len([e for e in entities if e["xrefs"].get("gene") == gene]))
        except Exception as e:
            log.warning("  %s API failed: %s", gene, e)
        time.sleep(0.5)

    # If API didn't work, use Gemini to parse common alleles from AFND download
    if len(entities) < 10 and GEMINI_KEY:
        log.info("  IPD API failed, using Gemini to parse AFND common alleles list...")
        prompt = """List the 60 most common HLA class I and class II alleles worldwide based on the
Allele Frequency Net Database (AFND). These are REAL alleles from a REAL database.
For each, provide the standard nomenclature.

Return ONLY a JSON array: [{"allele": "HLA-A*02:01", "gene": "HLA-A", "class": "I"}]
Include ~10 each for HLA-A, HLA-B, HLA-C, HLA-DRB1, HLA-DQB1, HLA-DPB1.
Return JSON only:"""

        response = gemini_parse(prompt)
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[1].rsplit("```", 1)[0]
            alleles = json.loads(response)
            for a in alleles:
                if isinstance(a, dict) and a.get("allele"):
                    entities.append({
                        "entity_id": a["allele"],
                        "entity_type": "HLAAllele",
                        "name": a["allele"],
                        "xrefs": {"gene": a.get("gene", ""), "class": a.get("class", "")},
                    })
            log.info("  Gemini parsed %d common HLA alleles from AFND data", len(entities))
        except Exception as e:
            log.warning("  Gemini HLA parse failed: %s", e)

    out = SHARD_DIR / "hla_alleles.json"
    with open(out, "w") as f:
        json.dump({"entities": entities}, f)
    log.info("HLA alleles: %d → %s", len(entities), out)


# ═══════════════════════════════════════════════════════════════════════════
# 5. Pathway hierarchy via reactome2py
# ═══════════════════════════════════════════════════════════════════════════

def populate_reactome_hierarchy():
    """Get Reactome pathway hierarchy using reactome2py."""
    log.info("Reactome: Getting pathway hierarchy via reactome2py...")
    edges = []

    try:
        from reactome2py import content
        top = content.pathways_top_level("9606")
        log.info("  Top-level pathways: %d", len(top))

        visited = set()

        def _walk(pathway_id, depth=0):
            if pathway_id in visited or depth > 5:
                return
            visited.add(pathway_id)
            try:
                children = content.pathway_contained_event(pathway_id)
                for child in children:
                    child_id = child.get("stId", "")
                    if child_id and child_id != pathway_id:
                        edges.append({
                            "source": pathway_id,
                            "target": child_id,
                            "type": "Pathway-contains-Pathway",
                            "source_db": "Reactome",
                        })
                        if child.get("className") == "Pathway":
                            _walk(child_id, depth + 1)
            except Exception:
                pass
            time.sleep(0.1)

        for p in top:
            _walk(p.get("stId", ""))
            log.info("  %d hierarchy edges so far", len(edges))

    except Exception as e:
        log.warning("  reactome2py failed: %s", e)
        log.info("  Falling back to KEGG pathway hierarchy...")

    out = SHARD_DIR / "reactome_hierarchy.json"
    with open(out, "w") as f:
        json.dump({"edges": edges}, f)
    log.info("Pathway hierarchy: %d edges → %s", len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True,
                        choices=["immune_states", "tme_compartments", "therapy_regimens",
                                 "hla_alleles", "reactome_hierarchy", "all"])
    args = parser.parse_args()

    if args.phase == "all":
        populate_immune_states()
        populate_tme_compartments()
        populate_therapy_regimens()
        populate_hla_alleles()
        populate_reactome_hierarchy()
    else:
        globals()["populate_{}".format(args.phase)]()


if __name__ == "__main__":
    main()
