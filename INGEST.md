# Ingestion recipes

Per-source recipe for rebuilding `gbd_knowledge_graph.db` from public APIs.
Each row names the endpoint that was actually called, the query/library, the
version pin, what entity / edge type it produces, and the loader function in
`ingest/` that contains the concrete code.

Conventions:
- `${KG_DATA_ROOT}` = scratch dir for shards and the SQLite DB.
- `${EXTERNAL_DATA_ROOT}` = raw downloads of DepMap / CPTAC bulk files.
- `GEMINI_API_KEY` is only used to *fill* a few small gold-standard lists
  (HLA alleles, immune-state names) — every biological edge comes from a
  curated database, never from an LLM.

Run order matters because edges reference entities. The driver
`populate_knowledge_graph.py --phase all` enforces it; the table below is
sorted into the same dependency layers.

## Layer 0 — gene / protein backbone

| Source | Endpoint | Query / payload | Version | Produces | Loader |
|---|---|---|---|---|---|
| MyGene.info | `https://mygene.info/v3/query` (POST batch) | `q=symbol:<HGNC>&species=human&fields=symbol,entrezgene,ensembl,go,pathway` | live (no version) | `Gene`; `BiologicalProcess`; `MolecularFunction`; `CellularComponent`; `Pathway`; `Gene-participates-{BP,MF,CC,Pathway}`; `Gene-encodes-Protein` (xref) | `populate_knowledge_graph.py:populate_genes` → `populate_kg_worker.py:populate_genes_shard` |
| UniProt | `https://rest.uniprot.org/uniprotkb/search` | `query=reviewed:true+AND+organism_id:9606&format=json&size=500` paginated | live (release manifest in response) | `Protein`; `Gene-encodes-Protein`; `Protein-localizes-CellularComponent` | `populate_kg_remaining.py:populate_uniprot` |

## Layer 1 — ontologies & hierarchies (no edges depend on each other)

| Source | Endpoint | Query | Version | Produces | Loader |
|---|---|---|---|---|---|
| Cell Ontology (OLS4) | `https://www.ebi.ac.uk/ols4/api/ontologies/cl/terms/{iri}/children?size=100` | BFS from `CL:0000000` | OLS4 live | `CellType`; `CellType-isa-CellType` | `populate_kg_full.py:populate_cell_ontology` |
| EFO (OLS4) | `https://www.ebi.ac.uk/ols4/api/ontologies/efo/terms/{iri}/parents?size=10` | per-disease | OLS4 live | `Disease-contains-Disease` | `populate_kg_full.py:populate_disease_hierarchy` |
| OncoTree | `https://oncotree.info/api/tumorTypes` | `GET` | live | `CancerType` (`ONCO-{code}`); `Disease-contains-Disease` | `populate_kg_full.py:populate_oncotree` |
| KEGG | `https://rest.kegg.jp/list/{enzyme,reaction}` | `GET` | live | `EC` (`EC:{n}`); `Reaction`; `Pathway-contains-Pathway` | `populate_kg_full.py:populate_kegg` |
| Reactome | `https://reactome.org/ContentService` via `reactome2py` | hierarchy traversal | release pinned at run-time | `Pathway` (`R-HSA-…`); `Pathway-contains-Pathway` | `populate_kg_curated.py:populate_reactome_hierarchy` |
| miRBase | `https://mirbase.org/download/hsa.gff3` | bulk GFF3 | release in file header | `MiRNA`; `Gene-encodes-MiRNA` | `populate_kg_full.py:populate_mirna` |
| IPD-IMGT/HLA | `https://www.ebi.ac.uk/cgi-bin/ipd/api/allele?limit=100&gene={HLA-X}` | one query per HLA gene | live | `HLAAllele` (top 100 alleles) | `populate_kg_curated.py:populate_hla_alleles` |
| HPA v23 | `https://v23.proteinatlas.org/download/normal_tissue.tsv.zip` | bulk TSV | **v23 (pinned)** | `Anatomy` (`ANAT-{tissue}`); `CellType` (`CT-{tissue}-{ct}`); `Anatomy-expresses-Gene`; `Gene-expressedIN-CellType` | `populate_kg_gemini.py:populate_hpa_v23` |

## Layer 2 — disease / drug / variant

| Source | Endpoint | Query | Version | Produces | Loader |
|---|---|---|---|---|---|
| Open Targets | `https://api.platform.opentargets.org/api/v4/graphql` | `disease(id) { associatedTargets, location, … }` (sharded) | live | `Disease`; `Disease-associates-Gene` (overall score 0.1–0.91); `Disease-localizes-Anatomy` | `populate_kg_login.py:populate_opentargets` |
| ChEMBL | `https://www.ebi.ac.uk/chembl/api/data/drug_indication.json?max_phase_for_ind__gte=3&limit=1000&offset={n}` | paginated | release in response | `Compound` (`CHEMBL…`); `Compound-treats-Disease` (phase 3+ only) | `populate_kg_full.py:populate_chembl_indications` |
| ChEMBL (mechanism) | `https://www.ebi.ac.uk/chembl/api/data/mechanism.json?limit=1000&offset={n}` | paginated | release in response | `TherapyRegimen` (`THR-{action}-{target}`) | `populate_kg_curated.py:populate_chembl_mechanisms` |
| DGIdb | GraphQL `https://dgidb.org/api/graphql` | drug-gene interactions | live | `Compound` (`iuphar.ligand:…`, `chembl:…`); `Compound-binds-Protein` (score 0–1) | `populate_kg_remaining.py:populate_dgidb` |
| ClinVar | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=clinvar&term={gene}[gene]+AND+pathogenic[clinsig]` then `esummary.fcgi` | per-gene | NCBI live | `Variant` (`ClinVar:{uid}`); `Gene-has-Variant` | `populate_kg_full.py:populate_clinvar` |

## Layer 3 — interactions, regulation, perturbation

| Source | Endpoint | Query | Version | Produces | Loader |
|---|---|---|---|---|---|
| STRING | `https://string-db.org/api/json/network` | `identifiers={genes}&species=9606&required_score=400` | v12 (release in response) | `Protein-interacts-Protein` (combined score 0.4–0.999) | `populate_knowledge_graph.py:populate_interactions` → `populate_kg_worker.py:populate_interactions_shard` |
| Enrichr — ChEA 2022 | `https://maayanlab.cloud/Enrichr/geneSetLibrary?mode=text&libraryName=ChEA_2022` | bulk text | **2022** | `Protein-regulates-Gene` (TF→target ChIP-seq) | `populate_kg_login.py:populate_tf_targets` |
| Enrichr — ENCODE TF ChIP-seq | `…&libraryName=ENCODE_TF_ChIP-seq_2015` | bulk text | **2015** | `Protein-regulates-Gene` | `populate_kg_login.py:populate_tf_targets` |
| Enrichr — ENCODE+ChEA Consensus | `…&libraryName=ENCODE_and_ChEA_Consensus_TFs_from_ChIP-X` | bulk text | live | `Protein-regulates-Gene` | `populate_kg_login.py:populate_tf_targets` |
| Enrichr — LINCS L1000 CRISPR KO | `…&libraryName=LINCS_L1000_CRISPR_KO_Consensus_Sigs` | bulk text | live (consensus build date in file) | `KGene-regulates-Gene` (CRISPR-KO downstream signature) | `populate_kg_login.py:populate_lincs` |
| Enrichr — PanglaoDB | `…&libraryName=PanglaoDB_Augmented_2021` | bulk text | **2021** | `TMECompartment` (`TME-{x}`); `TME-signatureGene-Gene` | `populate_kg_curated.py:populate_tme_compartments` |
| Enrichr — Azimuth 2023 | `…&libraryName=Azimuth_Cell_Types_2021` (with 2023 update) | bulk text | **2023** | `ImmuneFunctionalState` (`IFS-{x}`); `ImmuneState-markedBy-Gene` | `populate_kg_curated.py:populate_immune_states` |
| CollecTRI | bundled TSV (curated TF→target consensus) | TSV | release pinned in `versions.lock` | `TF-bindsPromoter-Gene` | `populate_kg_reference_edges.py:populate_collectri` |

## Layer 4 — cell-line dependency (DepMap-derived)

| Source | Endpoint | Query | Version | Produces | Loader |
|---|---|---|---|---|---|
| DepMap (Achilles + Score consensus) | DepMap portal bulk download → `${EXTERNAL_DATA_ROOT}/depmap/` | `CRISPRGeneEffect.csv`, `Model.csv` | **DepMap 23Q4 / 24Q2** (see `versions.lock`) | `CellLine` (`ACH-…`); `CancerLineage` (`LINEAGE-…`); `CellLine-isa-CancerLineage`; `CancerLineage-essential-Gene`; `CellLine-dependsOn-Gene`; `Gene-syntheticLethal-Gene` (LASSO) | `populate_kg_depmap.py:populate_depmap`; `populate_kg_genomic_taiji.py:populate_sl_pairs` |
| TCPGdb | local concordance TSVs (in-house, derived from public CRISPR screens) | TSV | release pinned | `Phenotype` (`PHENO-…`); `Gene-drives-ImmunePhenotype`; `Gene-suppresses-ImmunePhenotype` | `populate_kg_tcpgdb.py:populate_tcpgdb` |
| Taiji2 | local PageRank communities (from ENCODE/GEO) | TSV | release pinned | `Gene-participates-BiologicalProcess` (community-level) | `populate_kg_genomic_taiji.py:populate_taiji` |

## Layer 5 — patient cohorts

| Source | Endpoint | Query | Version | Produces | Loader |
|---|---|---|---|---|---|
| CPTAC PDC | bulk download → `${EXTERNAL_DATA_ROOT}/cptac_all/pdc` | proteome / phospho / acetyl / ubiquityl files | **CPTAC v3.x** | `Disease-associates-Gene` (proteome essentiality) | `populate_kg_cptac.py:populate_essentiality` |

## Driver

`ingest/populate_knowledge_graph.py --phase {genes,interactions,lincs,diseases,all}` runs the per-source loaders in order, writes one JSON shard per source under `${KG_DATA_ROOT}/kg_shards/<source>.json`, then `ingest/merge_kg_shards.py` batch-inserts into the SQLite DB.

Each shard JSON is a flat list of records with the schema:
```json
{"entity_id": "...", "entity_type": "...", "name": "...", "xrefs": {...}}
{"edge_id": "...", "edge_type": "...", "source_id": "...", "target_id": "...",
 "source_db": "...", "confidence": 0.9, "properties": {...}}
```

Re-running a phase is idempotent (the merger keys on `entity_id` / `edge_id`).

## How the TDtool edges were created

`TDtool_SL_LASSO` and `TDtool_CPTAC_essentiality` are not third-party
databases — they are in-house pipelines that sit on top of public sources
(DepMap CRISPR + CPTAC tumor RNA-seq + TCPGdb / BioGRID-ORCS). The
loader at `ingest/populate_kg_genomic_taiji.py` reads precomputed CSVs
from those pipelines and writes them as backbone edges. If you want to
reproduce them you need to re-run the pipeline — the public KG only
contains the *output* edges.

### `TDtool_SL_LASSO` → 28,792 `Gene-syntheticLethal-Gene` edges

**Pipeline.** For each candidate (mutation_gene, target_gene) pair,
fit an L1-penalised regression of target gene's CERES dependency score
on the mutation status of the partner gene across DepMap cell lines,
controlling for lineage. Multiple-test correct (Benjamini-Hochberg) at
the per-target level. Keep pairs with non-zero LASSO coefficient and
`fdr_q < 0.10`. The optional `mutually_exclusive` flag marks pairs
whose mutations are mutually exclusive in TCGA — a classical SL
signature.

**Inputs.** DepMap `CRISPRGeneEffect.csv` (CERES scores), DepMap
`OmicsSomaticMutationsMatrixDamaging.csv` (binary mutation calls),
`Model.csv` for lineage covariates.

**Output file the loader reads.** `${EXTERNAL_DATA_ROOT}/depmap/tdtool_pan_cancer/graph/sl_lasso_filtered.csv` with columns `mutation_gene`,
`target_gene`, `lasso_coef`, `fdr_q`, `mutually_exclusive`.

**Edge construction** (`ingest/populate_kg_genomic_taiji.py:populate_sl_pairs`):
```
edge_id        = f"SL-{mutation_gene}-{target_gene}"
edge_type      = "Gene-syntheticLethal-Gene"
source_id      = mutation_gene
target_id      = target_gene
source_db      = "TDtool_SL_LASSO"
confidence     = clamp(1.0 - fdr_q, 0, 1)
properties     = {"relationship": "synthetic_lethality",
                  "lasso_coef": …, "fdr_q": …, "mutually_exclusive": …}
```

### `TDtool_CPTAC_essentiality` → 7,732 `Disease-associates-Gene` edges

**Pipeline.** Project CPTAC patient-tumor RNA-seq (10 cancer types)
into the DepMap cell-line latent space using Celligner, then train an
elastic-net per gene to predict CERES dependency from gene-expression
context. Apply the trained model to each patient tumor and call a gene
"essential" in that tumor when the predicted dependency falls below a
fixed CERES cutoff. `frac_essential` is the fraction of patient tumors
in the cancer-type cohort where the gene is called essential;
`mean_essentiality` is the mean predicted dependency.

**Inputs.** DepMap CRISPR dependency for training; CPTAC patient
tumor RNA-seq (PDC) for inference; Celligner reference for projection.

**Cancer types covered (10).** `breast` (BRCA), `renal` (KIRC),
`colorectal` (COAD), `glioblastoma` (GBM), `head_neck` (HNSCC),
`lung_squamous` (LUSC), `lung_adenocarcinoma` (LUAD), `ovarian` (OV),
`pancreatic` (PDAC), `endometrial` (UCEC).

**Output files the loader reads.** `${EXTERNAL_DATA_ROOT}/depmap/tdtool_pan_cancer/per_study_rnaseq/<study>/gene_tumor_summary.csv` with columns
`gene`, `mean_essentiality`, `frac_essential`, `model_cv_r`.

**Filter.** Only rows with `frac_essential > 0.5` enter the KG.

**Edge construction** (`ingest/populate_kg_genomic_taiji.py:populate_essentiality`):
```
edge_id        = f"TESS-{study_name}-{gene}"
edge_type      = "Disease-associates-Gene"
source_id      = f"cancer_{cancer}"          # CancerType entity (per-study)
target_id      = gene                         # HGNC symbol
source_db      = "TDtool_CPTAC_essentiality"
confidence     = model_cv_r                   # cross-validation R of the elastic-net
properties     = {"relationship": "predicted_tumor_essentiality",
                  "mean_essentiality": …, "frac_essential": …,
                  "model_cv_r": …, "study": <study_name>,
                  "pipeline": "CPTAC RNA-seq → Celligner → DepMap CERES elastic net"}
```

A `Study` entity (`CPTAC_ESS_<study_name>`) is also written so the
edge has full provenance back to the cohort.

### What's *not* in the KG

TDtool produces a much larger set of analytical outputs that the agent
consumes at runtime via tool calls (`phenotype_rankings.csv`,
`concordance_analysis.csv`, `cross_phenotype_comparison.csv`,
`clinical_scores.csv`, `transition_scores.csv`,
`gene_state_essentiality.csv`, `taiji_upstream_regulators.csv`).
These live in `${EXTERNAL_DATA_ROOT}/tcpgdb/tdtool_output/` and are
read by tools at proving time — they are not loaded as backbone edges
because they are claim-shaped (gene × phenotype × screen-context),
not entity-shaped.
