#!/usr/bin/env python3
"""Populate ALL remaining KG entity/edge types.

Direct API sources (no LLM):
  1. ChEMBL: Compound-treats-Disease (approved drug indications)
  2. InterPro: Protein-has-ProteinDomain, ProteinDomain/ProteinFamily entities
  3. EFO (OLS): Disease-contains-Disease hierarchy
  4. Cell Ontology (OLS): CellType-isa-CellType hierarchy
  5. OncoTree: CancerType entities
  6. KEGG: EC, Reaction entities + Pathway hierarchy
  7. ClinVar (Entrez): Variant entities

Gemini-assisted (structured extraction):
  8. ImmuneFunctionalState entities + marker genes
  9. TMECompartment entities + signatures
  10. TherapyRegimen entities
  11. HLAAllele entities
  12. Gene-encodes-MiRNA from miRBase

Run:  python populate_kg_full.py --phase <name>
      python populate_kg_full.py --phase all_api
      python populate_kg_full.py --phase all_gemini
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
log = logging.getLogger("kg_full")

SCRATCH = Path(os.environ["KG_DATA_ROOT"])
SHARD_DIR = SCRATCH / "kg_shards"
GENE_LIST = SCRATCH / "all_genes.json"
GEMINI_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")


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


def gemini_extract(prompt, max_tokens=2048):
    """Call Gemini API for structured extraction."""
    if not GEMINI_KEY:
        log.warning("No GEMINI_API_KEY set")
        return ""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={}".format(GEMINI_KEY)
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.1},
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


def _parse_gemini_json(response):
    """Parse JSON from Gemini response, handling markdown code blocks."""
    response = response.strip()
    if response.startswith("```"):
        response = response.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(response)


# ═══════════════════════════════════════════════════════════════════════════
# 1. ChEMBL: Compound-treats-Disease
# ═══════════════════════════════════════════════════════════════════════════

def populate_chembl_indications():
    """Download ChEMBL approved drug indications (phase 4 = marketed)."""
    log.info("ChEMBL: Downloading drug indications...")
    edges = []
    entities = []
    drug_seen = set()
    disease_seen = set()

    offset = 0
    total = None
    while True:
        url = "https://www.ebi.ac.uk/chembl/api/data/drug_indication.json?max_phase_for_ind__gte=3&limit=1000&offset={}".format(offset)
        try:
            data = json.loads(_http_get(url, timeout=30))
            if total is None:
                total = data["page_meta"]["total_count"]
                log.info("  ChEMBL: %d total drug indications (phase 3+)", total)

            for di in data.get("drug_indications", []):
                mol_id = di.get("molecule_chembl_id", "")
                mesh = di.get("mesh_heading", "")
                mesh_id = di.get("mesh_id", "")
                efo_id = di.get("efo_id", "")
                phase = di.get("max_phase_for_ind", 0)

                if not mol_id or not mesh:
                    continue

                disease_id = efo_id or "MESH-{}".format(mesh.replace(" ", "_")[:30])
                if disease_id not in disease_seen:
                    entities.append({
                        "entity_id": disease_id,
                        "entity_type": "Disease",
                        "name": mesh,
                    })
                    disease_seen.add(disease_id)

                if mol_id not in drug_seen:
                    # Get drug name
                    pref_name = di.get("pref_name", mol_id)
                    entities.append({
                        "entity_id": mol_id,
                        "entity_type": "Compound",
                        "name": pref_name or mol_id,
                    })
                    drug_seen.add(mol_id)

                edges.append({
                    "source": mol_id,
                    "target": disease_id,
                    "type": "Compound-treats-Disease",
                    "phase": phase,
                    "source_db": "ChEMBL",
                })

            offset += 1000
            if offset >= total:
                break
            if offset % 5000 == 0:
                log.info("  %d/%d indications", offset, total)

        except Exception as e:
            log.warning("  ChEMBL offset %d failed: %s", offset, e)
            break
        time.sleep(0.3)

    out = SHARD_DIR / "chembl_indications.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("ChEMBL: %d drugs, %d diseases, %d edges → %s",
             len(drug_seen), len(disease_seen), len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════
# 2. InterPro: Protein-has-ProteinDomain + ProteinDomain/ProteinFamily
# ═══════════════════════════════════════════════════════════════════════════

def populate_interpro():
    """Query InterPro for protein domains via UniProt accessions."""
    log.info("InterPro: Querying protein domains...")
    import sqlite3
    db = sqlite3.connect(str(SCRATCH / "gbd_knowledge_graph.db"))
    proteins = db.execute(
        "SELECT entity_id FROM entities WHERE entity_type = 'Protein'"
    ).fetchall()
    protein_ids = [r[0] for r in proteins]
    db.close()
    log.info("  %d proteins to query", len(protein_ids))

    edges = []
    entities = []
    domain_seen = set()

    for i, prot_id in enumerate(protein_ids):
        if (i + 1) % 200 == 0:
            log.info("  %d/%d proteins, %d domain edges", i + 1, len(protein_ids), len(edges))

        url = "https://www.ebi.ac.uk/interpro/api/entry/interpro/protein/uniprot/{}?page_size=20".format(prot_id)
        try:
            data = json.loads(_http_get(url, timeout=15))
            for entry in data.get("results", []):
                meta = entry.get("metadata", {})
                acc = meta.get("accession", "")
                name = meta.get("name", "")
                entry_type = meta.get("type", "")  # domain, family, homologous_superfamily

                if not acc:
                    continue

                if acc not in domain_seen:
                    if entry_type == "family":
                        ent_type = "ProteinFamily"
                    else:
                        ent_type = "ProteinDomain"
                    entities.append({
                        "entity_id": acc,
                        "entity_type": ent_type,
                        "name": name,
                    })
                    domain_seen.add(acc)

                edges.append({
                    "source": prot_id,
                    "target": acc,
                    "type": "Protein-has-ProteinDomain",
                    "domain_type": entry_type,
                    "source_db": "InterPro",
                })

        except Exception:
            pass
        time.sleep(0.08)

    out = SHARD_DIR / "interpro_domains.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("InterPro: %d domains/families, %d edges → %s",
             len(domain_seen), len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════
# 3. EFO: Disease-contains-Disease hierarchy
# ═══════════════════════════════════════════════════════════════════════════

def populate_disease_hierarchy():
    """Get EFO disease ontology hierarchy via OLS API."""
    log.info("EFO: Building disease hierarchy...")
    import sqlite3
    db = sqlite3.connect(str(SCRATCH / "gbd_knowledge_graph.db"))
    diseases = db.execute(
        "SELECT entity_id, name FROM entities WHERE entity_type = 'Disease'"
    ).fetchall()
    db.close()
    log.info("  %d diseases to query parents for", len(diseases))

    edges = []
    seen = set()

    for i, (d_id, d_name) in enumerate(diseases):
        if (i + 1) % 500 == 0:
            log.info("  %d/%d diseases, %d hierarchy edges", i + 1, len(diseases), len(edges))

        if not d_id.startswith("EFO"):
            continue

        encoded = urllib.parse.quote(urllib.parse.quote("http://www.ebi.ac.uk/efo/{}".format(d_id.replace("_", "_")), safe=""), safe="")
        url = "https://www.ebi.ac.uk/ols4/api/ontologies/efo/terms/{}/parents?size=10".format(encoded)
        try:
            data = json.loads(_http_get(url, timeout=10))
            terms = data.get("_embedded", {}).get("terms", [])
            for t in terms:
                parent_label = t.get("label", "")
                parent_obo = t.get("obo_id", "")
                if parent_obo and parent_obo != d_id:
                    key = "{}-{}".format(d_id, parent_obo)
                    if key not in seen:
                        seen.add(key)
                        edges.append({
                            "source": parent_obo,
                            "target": d_id,
                            "type": "Disease-contains-Disease",
                            "source_db": "EFO",
                        })
        except Exception:
            pass
        time.sleep(0.05)

    out = SHARD_DIR / "disease_hierarchy.json"
    with open(out, "w") as f:
        json.dump({"edges": edges}, f)
    log.info("EFO hierarchy: %d edges → %s", len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Cell Ontology: CellType-isa-CellType
# ═══════════════════════════════════════════════════════════════════════════

def populate_cell_ontology():
    """Get Cell Ontology hierarchy via OLS API."""
    log.info("Cell Ontology: Building cell type hierarchy...")
    edges = []
    entities = []
    seen_ids = set()

    # Walk the ontology tree breadth-first from root
    queue = ["http://purl.obolibrary.org/obo/CL_0000000"]  # cell
    visited = set()

    while queue and len(seen_ids) < 2000:
        term_iri = queue.pop(0)
        if term_iri in visited:
            continue
        visited.add(term_iri)

        encoded = urllib.parse.quote(urllib.parse.quote(term_iri, safe=""), safe="")
        url = "https://www.ebi.ac.uk/ols4/api/ontologies/cl/terms/{}/children?size=100".format(encoded)
        try:
            data = json.loads(_http_get(url, timeout=10))
            terms = data.get("_embedded", {}).get("terms", [])
            parent_id = term_iri.split("/")[-1].replace("_", ":")

            for t in terms:
                child_iri = t.get("iri", "")
                child_id = t.get("obo_id", child_iri.split("/")[-1].replace("_", ":"))
                child_name = t.get("label", "")

                if child_id and child_id not in seen_ids:
                    entities.append({
                        "entity_id": child_id,
                        "entity_type": "CellType",
                        "name": child_name,
                    })
                    seen_ids.add(child_id)
                    queue.append(child_iri)

                if child_id and parent_id:
                    edges.append({
                        "source": parent_id,
                        "target": child_id,
                        "type": "CellType-isa-CellType",
                        "source_db": "CL",
                    })

        except Exception:
            pass
        time.sleep(0.05)

        if len(seen_ids) % 200 == 0 and len(seen_ids) > 0:
            log.info("  %d cell types, %d hierarchy edges", len(seen_ids), len(edges))

    out = SHARD_DIR / "cell_ontology.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("Cell Ontology: %d cell types, %d edges → %s", len(entities), len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════
# 5. OncoTree: CancerType entities
# ═══════════════════════════════════════════════════════════════════════════

def populate_oncotree():
    """Download OncoTree tumor type hierarchy."""
    log.info("OncoTree: Downloading cancer types...")
    data = json.loads(_http_get("https://oncotree.info/api/tumorTypes", timeout=30))
    entities = []
    edges = []

    for t in data:
        code = t.get("code", "")
        name = t.get("name", "")
        tissue = t.get("tissue", "")
        parent = t.get("parent", "")

        if not code:
            continue
        entities.append({
            "entity_id": "ONCO-{}".format(code),
            "entity_type": "CancerType",
            "name": name,
            "xrefs": {"tissue": tissue, "oncotree_code": code},
        })
        if parent:
            edges.append({
                "source": "ONCO-{}".format(parent),
                "target": "ONCO-{}".format(code),
                "type": "Disease-contains-Disease",
                "source_db": "OncoTree",
            })

    out = SHARD_DIR / "oncotree.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("OncoTree: %d cancer types, %d hierarchy edges → %s", len(entities), len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════
# 6. KEGG: EC numbers, Reactions, Pathway hierarchy
# ═══════════════════════════════════════════════════════════════════════════

def populate_kegg():
    """Download KEGG enzyme and reaction lists + pathway hierarchy."""
    log.info("KEGG: Downloading enzymes, reactions, pathway hierarchy...")
    entities = []
    edges = []

    # EC numbers
    try:
        text = _http_get("https://rest.kegg.jp/list/enzyme", timeout=30)
        for line in text.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 2:
                ec_id = parts[0].replace("ec:", "")
                ec_name = parts[1].split(";")[0].strip()
                entities.append({
                    "entity_id": "EC:{}".format(ec_id),
                    "entity_type": "EC",
                    "name": ec_name,
                })
        log.info("  KEGG enzymes: %d", sum(1 for e in entities if e["entity_type"] == "EC"))
    except Exception as e:
        log.warning("  KEGG enzyme failed: %s", e)

    # Reactions
    try:
        text = _http_get("https://rest.kegg.jp/list/reaction", timeout=30)
        for line in text.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 2:
                rxn_id = parts[0].replace("rn:", "")
                rxn_name = parts[1].split(";")[0].strip()
                entities.append({
                    "entity_id": rxn_id,
                    "entity_type": "Reaction",
                    "name": rxn_name,
                })
        log.info("  KEGG reactions: %d", sum(1 for e in entities if e["entity_type"] == "Reaction"))
    except Exception as e:
        log.warning("  KEGG reaction failed: %s", e)

    # Human pathway hierarchy
    try:
        text = _http_get("https://rest.kegg.jp/list/pathway/hsa", timeout=30)
        pathways = []
        for line in text.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 2:
                pw_id = parts[0].replace("path:", "")
                pw_name = parts[1].replace(" - Homo sapiens (human)", "").strip()
                pathways.append((pw_id, pw_name))

        # Get pathway hierarchy via BRITE
        brite = _http_get("https://rest.kegg.jp/get/br:hsa00001/json", timeout=30)
        brite_data = json.loads(brite)
        # Parse BRITE hierarchy
        def _walk_brite(node, parent_name=""):
            children = node.get("children", [])
            for child in children:
                child_name = child.get("name", "")
                if child_name.startswith("hsa"):
                    # This is a pathway
                    pw_id = child_name.split(" ")[0] if " " in child_name else child_name
                    if parent_name:
                        edges.append({
                            "source": "KEGG-{}".format(parent_name.replace(" ", "_")[:30]),
                            "target": pw_id,
                            "type": "Pathway-contains-Pathway",
                            "source_db": "KEGG",
                        })
                else:
                    # Category node
                    _walk_brite(child, child_name[:50])

        _walk_brite(brite_data)
        log.info("  KEGG pathway hierarchy: %d edges", len(edges))

    except Exception as e:
        log.warning("  KEGG pathway hierarchy failed: %s", e)

    out = SHARD_DIR / "kegg_ec_rxn.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("KEGG: %d entities, %d edges → %s", len(entities), len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════
# 7. ClinVar: Variant entities (pathogenic/likely pathogenic)
# ═══════════════════════════════════════════════════════════════════════════

def populate_clinvar():
    """Query ClinVar for pathogenic variants in our gene set."""
    log.info("ClinVar: Querying pathogenic variants...")
    all_genes = get_all_genes()
    entities = []
    edges = []

    # Query top genes for pathogenic variants
    important_genes = all_genes[:500]  # Top 500 most important

    for i, gene in enumerate(important_genes):
        if (i + 1) % 50 == 0:
            log.info("  %d/%d genes, %d variants", i + 1, len(important_genes), len(entities))

        # Search ClinVar for pathogenic variants
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=clinvar&term={}[gene]+AND+pathogenic[clinsig]&retmax=10&retmode=json".format(
            urllib.parse.quote(gene))
        try:
            search = json.loads(_http_get(search_url, timeout=10))
            ids = search.get("esearchresult", {}).get("idlist", [])

            if ids:
                # Get summaries
                id_str = ",".join(ids[:10])
                sum_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=clinvar&id={}&retmode=json".format(id_str)
                summaries = json.loads(_http_get(sum_url, timeout=10))

                for uid in ids[:10]:
                    doc = summaries.get("result", {}).get(uid, {})
                    if not doc or not isinstance(doc, dict):
                        continue
                    title = doc.get("title", "")
                    clinical_sig = doc.get("clinical_significance", {})
                    if isinstance(clinical_sig, dict):
                        sig = clinical_sig.get("description", "")
                    else:
                        sig = str(clinical_sig)

                    var_id = "ClinVar:{}".format(uid)
                    entities.append({
                        "entity_id": var_id,
                        "entity_type": "Variant",
                        "name": title[:100],
                        "xrefs": {"clinvar": uid, "significance": sig},
                    })
                    edges.append({
                        "source": gene,
                        "target": var_id,
                        "type": "Gene-has-Variant",
                        "significance": sig,
                        "source_db": "ClinVar",
                    })

        except Exception:
            pass
        time.sleep(0.35)  # NCBI rate limit (3/sec)

    out = SHARD_DIR / "clinvar_variants.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("ClinVar: %d variants, %d edges → %s", len(entities), len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════
# 8. Gemini: ImmuneFunctionalState entities
# ═══════════════════════════════════════════════════════════════════════════

def populate_immune_states():
    """Use Gemini to curate canonical immune functional states with marker genes."""
    log.info("Gemini: Curating immune functional states...")

    prompt = """You are a cancer immunology expert. List all canonical immune functional states
relevant to tumor immunology and immunotherapy. For each state, provide:
1. A short ID (e.g., "naive", "effector", "exhausted")
2. Full name
3. Cell types where this state occurs
4. 5-10 canonical marker genes (HUGO symbols)
5. Functional significance in cancer

Return ONLY a JSON array with objects:
{"id": "state_id", "name": "Full Name", "cell_types": ["CD8+ T cell"], "markers": ["GENE1", "GENE2"], "cancer_role": "brief description"}

Include at minimum: naive, primed, effector, memory, resident_memory, exhausted, terminally_exhausted,
progenitor_exhausted, regulatory, anergic, senescent, tissue_resident_macrophage, M1_polarized,
M2_polarized, myeloid_derived_suppressor, dendritic_mature, dendritic_immature, NK_activated, NK_resting,
B_memory, B_plasma, B_regulatory. Add any others that are important for immuno-oncology.

Return JSON array only, no markdown:"""

    response = gemini_extract(prompt, max_tokens=4096)
    entities = []
    edges = []

    try:
        states = _parse_gemini_json(response)
        all_genes = set(get_all_genes())

        for state in states:
            if not isinstance(state, dict):
                continue
            state_id = "IFS-{}".format(state.get("id", "unknown"))
            entities.append({
                "entity_id": state_id,
                "entity_type": "ImmuneFunctionalState",
                "name": state.get("name", state.get("id", "")),
                "xrefs": {
                    "cell_types": state.get("cell_types", []),
                    "cancer_role": state.get("cancer_role", ""),
                },
            })
            for marker in state.get("markers", []):
                marker_up = marker.upper()
                if marker_up in all_genes:
                    edges.append({
                        "source": state_id,
                        "target": marker_up,
                        "type": "ImmuneFunctionalState-marked-by-Gene",
                        "source_db": "Gemini_curated",
                    })

        log.info("  %d immune states, %d marker edges", len(entities), len(edges))
    except Exception as e:
        log.warning("  Gemini immune states failed: %s", e)

    out = SHARD_DIR / "immune_states.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("Immune states → %s", out)


# ═══════════════════════════════════════════════════════════════════════════
# 9. Gemini: TMECompartment entities
# ═══════════════════════════════════════════════════════════════════════════

def populate_tme_compartments():
    """Use Gemini to curate TME compartments with signature genes."""
    log.info("Gemini: Curating TME compartments...")

    prompt = """You are a tumor microenvironment expert. List all major TME compartments used in
cancer biology research. For each compartment:
1. Short ID
2. Full name
3. Key cell types
4. 10-15 signature genes (HUGO symbols) commonly used to score this compartment
5. Role in immunotherapy response

Return ONLY a JSON array:
{"id": "compartment_id", "name": "Full Name", "cell_types": ["cell1"], "signature_genes": ["GENE1"], "immunotherapy_role": "description"}

Include: tumor_intrinsic, cd8_t_cell, cd4_t_cell, treg, nk_cell, b_cell, macrophage_m1, macrophage_m2,
myeloid_derived_suppressor, dendritic_cell, neutrophil, mast_cell, fibroblast_caf, endothelial,
pericyte, adipocyte, extracellular_matrix, hypoxic_niche, perivascular_niche, tertiary_lymphoid_structure.

Return JSON array only, no markdown:"""

    response = gemini_extract(prompt, max_tokens=4096)
    entities = []
    edges = []

    try:
        compartments = _parse_gemini_json(response)
        all_genes = set(get_all_genes())

        for comp in compartments:
            if not isinstance(comp, dict):
                continue
            comp_id = "TME-{}".format(comp.get("id", "unknown"))
            entities.append({
                "entity_id": comp_id,
                "entity_type": "TMECompartment",
                "name": comp.get("name", comp.get("id", "")),
                "xrefs": {
                    "cell_types": comp.get("cell_types", []),
                    "immunotherapy_role": comp.get("immunotherapy_role", ""),
                },
            })
            for sig in comp.get("signature_genes", []):
                sig_up = sig.upper()
                if sig_up in all_genes:
                    edges.append({
                        "source": comp_id,
                        "target": sig_up,
                        "type": "TMECompartment-signature-Gene",
                        "source_db": "Gemini_curated",
                    })

        log.info("  %d TME compartments, %d signature edges", len(entities), len(edges))
    except Exception as e:
        log.warning("  Gemini TME compartments failed: %s", e)

    out = SHARD_DIR / "tme_compartments.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("TME compartments → %s", out)


# ═══════════════════════════════════════════════════════════════════════════
# 10. Gemini: TherapyRegimen entities
# ═══════════════════════════════════════════════════════════════════════════

def populate_therapy_regimens():
    """Use Gemini to curate major immunotherapy and targeted therapy regimens."""
    log.info("Gemini: Curating therapy regimens...")

    prompt = """You are a clinical oncology expert. List all major immunotherapy and targeted therapy
regimens used in cancer treatment. For each regimen:
1. Short ID (e.g., "anti_PD1", "anti_CTLA4_anti_PD1")
2. Full name
3. Drug names
4. Target genes (HUGO symbols)
5. FDA-approved cancer types
6. Mechanism class

Return ONLY a JSON array:
{"id": "regimen_id", "name": "Full Name", "drugs": ["drug1"], "target_genes": ["GENE1"],
 "approved_cancers": ["melanoma"], "mechanism": "checkpoint_inhibitor"}

Include all major categories: checkpoint inhibitors (PD-1, PD-L1, CTLA-4, LAG-3, TIM-3, TIGIT),
targeted therapies (BRAF, MEK, EGFR, ALK, HER2, CDK4/6, PARP, BTK, BCL2, PI3K, mTOR, FLT3, JAK),
cell therapies (CAR-T, TIL), bispecifics, ADCs, cytokines. Include combos.

Return JSON array only, no markdown:"""

    response = gemini_extract(prompt, max_tokens=4096)
    entities = []
    edges = []

    try:
        regimens = _parse_gemini_json(response)
        all_genes = set(get_all_genes())

        for reg in regimens:
            if not isinstance(reg, dict):
                continue
            reg_id = "THR-{}".format(reg.get("id", "unknown"))
            entities.append({
                "entity_id": reg_id,
                "entity_type": "TherapyRegimen",
                "name": reg.get("name", reg.get("id", "")),
                "xrefs": {
                    "drugs": reg.get("drugs", []),
                    "approved_cancers": reg.get("approved_cancers", []),
                    "mechanism": reg.get("mechanism", ""),
                },
            })
            for gene in reg.get("target_genes", []):
                gene_up = gene.upper()
                if gene_up in all_genes:
                    edges.append({
                        "source": reg_id,
                        "target": gene_up,
                        "type": "TherapyRegimen-targets-Gene",
                        "source_db": "Gemini_curated",
                    })

        log.info("  %d therapy regimens, %d target edges", len(entities), len(edges))
    except Exception as e:
        log.warning("  Gemini therapy regimens failed: %s", e)

    out = SHARD_DIR / "therapy_regimens.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("Therapy regimens → %s", out)


# ═══════════════════════════════════════════════════════════════════════════
# 11. Gemini: HLAAllele entities
# ═══════════════════════════════════════════════════════════════════════════

def populate_hla_alleles():
    """Use Gemini to curate major HLA alleles relevant to immuno-oncology."""
    log.info("Gemini: Curating HLA alleles...")

    prompt = """List all major HLA class I and class II alleles relevant to cancer immunology.
For each allele:
1. Standard HLA nomenclature (e.g., "HLA-A*02:01")
2. Gene (HLA-A, HLA-B, HLA-C, HLA-DRB1, etc.)
3. Population frequency category (common/intermediate/rare)
4. Notable cancer associations

Return ONLY a JSON array:
{"allele": "HLA-A*02:01", "gene": "HLA-A", "class": "I", "frequency": "common",
 "cancer_note": "common in Caucasians, well-studied neoantigen presentation"}

Include the ~50 most clinically relevant alleles across HLA-A, HLA-B, HLA-C, HLA-DRB1, HLA-DQB1.
Return JSON array only, no markdown:"""

    response = gemini_extract(prompt, max_tokens=4096)
    entities = []

    try:
        alleles = _parse_gemini_json(response)
        for a in alleles:
            if not isinstance(a, dict):
                continue
            allele_id = a.get("allele", "")
            if allele_id:
                entities.append({
                    "entity_id": allele_id,
                    "entity_type": "HLAAllele",
                    "name": allele_id,
                    "xrefs": {
                        "gene": a.get("gene", ""),
                        "class": a.get("class", ""),
                        "frequency": a.get("frequency", ""),
                        "cancer_note": a.get("cancer_note", ""),
                    },
                })
        log.info("  %d HLA alleles", len(entities))
    except Exception as e:
        log.warning("  Gemini HLA alleles failed: %s", e)

    out = SHARD_DIR / "hla_alleles.json"
    with open(out, "w") as f:
        json.dump({"entities": entities}, f)
    log.info("HLA alleles → %s", out)


# ═══════════════════════════════════════════════════════════════════════════
# 12. miRBase: Gene-encodes-MiRNA
# ═══════════════════════════════════════════════════════════════════════════

def populate_mirna():
    """Download human miRNAs from miRBase and map to host genes."""
    log.info("miRBase: Downloading human miRNAs...")

    # miRBase GFF3 has coordinates → can map to host genes
    url = "https://mirbase.org/download/hsa.gff3"
    entities = []
    edges = []
    all_genes = set(get_all_genes())

    try:
        text = _http_get(url, timeout=30)
        for line in text.strip().split("\n"):
            if line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 9:
                continue
            feature_type = parts[2]
            if feature_type != "miRNA_primary_transcript":
                continue
            attrs = {}
            for attr in parts[8].split(";"):
                if "=" in attr:
                    k, v = attr.split("=", 1)
                    attrs[k] = v

            mirna_id = attrs.get("ID", "")
            mirna_name = attrs.get("Name", "")
            if mirna_name:
                entities.append({
                    "entity_id": mirna_name,
                    "entity_type": "MiRNA",
                    "name": mirna_name,
                    "xrefs": {"mirbase_id": mirna_id},
                })

        log.info("  miRBase: %d human miRNAs from GFF3", len(entities))
    except Exception as e:
        log.warning("  miRBase GFF3 failed: %s", e)

    # Use Gemini to map miRNAs to host genes and key targets
    if entities and GEMINI_KEY:
        mirna_names = [e["name"] for e in entities[:100]]  # Top 100
        prompt = """For these human miRNAs, provide the host gene (the gene whose intron encodes the miRNA)
and 3-5 validated target genes. Return JSON array:
{{"mirna": "hsa-mir-21", "host_gene": "VMP1", "targets": ["PTEN", "PDCD4", "TPM1"]}}

miRNAs: {}

Return JSON array only, no markdown:""".format(", ".join(mirna_names[:50]))

        response = gemini_extract(prompt, max_tokens=4096)
        try:
            mappings = _parse_gemini_json(response)
            for m in mappings:
                if not isinstance(m, dict):
                    continue
                mirna = m.get("mirna", "")
                host = m.get("host_gene", "").upper()
                if mirna and host and host in all_genes:
                    edges.append({
                        "source": host,
                        "target": mirna,
                        "type": "Gene-encodes-MiRNA",
                        "source_db": "Gemini_miRBase",
                    })
            log.info("  miRNA host gene mappings: %d edges", len(edges))
        except Exception as e:
            log.warning("  Gemini miRNA mapping failed: %s", e)

    out = SHARD_DIR / "mirna.json"
    with open(out, "w") as f:
        json.dump({"entities": entities, "edges": edges}, f)
    log.info("miRNA: %d entities, %d edges → %s", len(entities), len(edges), out)


# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True,
                        choices=["chembl", "interpro", "disease_hierarchy", "cell_ontology",
                                 "oncotree", "kegg", "clinvar", "immune_states",
                                 "tme_compartments", "therapy_regimens", "hla_alleles",
                                 "mirna", "all_api", "all_gemini", "all"])
    args = parser.parse_args()

    if args.phase == "all_api":
        populate_chembl_indications()
        populate_oncotree()
        populate_kegg()
        populate_clinvar()
        populate_cell_ontology()
        populate_disease_hierarchy()
        populate_mirna()
    elif args.phase == "all_gemini":
        populate_immune_states()
        populate_tme_compartments()
        populate_therapy_regimens()
        populate_hla_alleles()
    elif args.phase == "all":
        # Fast ones first
        populate_oncotree()
        populate_kegg()
        populate_chembl_indications()
        populate_cell_ontology()
        populate_immune_states()
        populate_tme_compartments()
        populate_therapy_regimens()
        populate_hla_alleles()
        populate_mirna()
        # Slow ones
        populate_clinvar()
        populate_disease_hierarchy()
        populate_interpro()
    elif args.phase == "chembl":
        populate_chembl_indications()
    elif args.phase == "disease_hierarchy":
        populate_disease_hierarchy()
    else:
        globals()["populate_{}".format(args.phase)]()


if __name__ == "__main__":
    main()
