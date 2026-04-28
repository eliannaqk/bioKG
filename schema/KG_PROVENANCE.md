# GBD Knowledge Graph — Complete Provenance Map

**Database**: `/home/eqk3/scratch_pi_mg269/eqk3/coscientist_data/gbd_knowledge_graph.db`
**Generated**: 2026-04-10
**Total**: 118,137 entities (19 types), 5,206,053 edges (20 types), 18 curated databases
**Provenance**: 100% of edges have source_db, 98.1% of entities have xrefs

All data from real curated databases. Zero LLM-generated biological facts.

---

## Entity Types (Nodes)

| Entity Type | Count | Source Database | API / Method | What It Represents |
|---|---|---|---|---|
| **Compound** | 21,895 | DGIdb + ChEMBL | DGIdb GraphQL + ChEMBL REST | Drugs, small molecules, biologics |
| **Protein** | 19,220 | UniProt | REST API (reviewed human) | Human proteins (SwissProt accessions) |
| **Gene** | 19,208 | MyGene.info | Batch POST (symbol→annotation) | Human gene symbols (HGNC) |
| **Disease** | 14,003 | Open Targets + ChEMBL | GraphQL + REST | Diseases (EFO, MONDO, MESH IDs) |
| **Reaction** | 12,384 | KEGG | REST (rest.kegg.jp/list/reaction) | Biochemical reactions |
| **EC** | 8,309 | KEGG | REST (rest.kegg.jp/list/enzyme) | Enzyme Commission numbers |
| **BiologicalProcess** | 7,027 | Gene Ontology | via MyGene.info | GO Biological Process terms |
| **Variant** | 3,049 | ClinVar | NCBI Entrez eutils | Pathogenic/likely pathogenic variants |
| **MolecularFunction** | 2,796 | Gene Ontology | via MyGene.info | GO Molecular Function terms |
| **Pathway** | 2,426 | Reactome + KEGG | via MyGene.info | Curated biological pathways |
| **CellType** | 2,244 | Cell Ontology + HPA v23 | EBI OLS4 API + TSV download | Cell types (CL ontology + HPA tissue cell types) |
| **MiRNA** | 1,913 | miRBase | GFF3 download (hsa.gff3) | Human microRNA precursors |
| **TherapyRegimen** | 1,299 | ChEMBL | REST (mechanism of action) | Drug mechanisms (inhibitor, agonist, etc.) |
| **CellularComponent** | 910 | Gene Ontology | via MyGene.info | GO Cellular Component terms |
| **CancerType** | 897 | OncoTree | REST (oncotree.info) | MSK tumor type classification |
| **ImmuneFunctionalState** | 344 | STCAT + Azimuth 2023 | TSV (1.7M cells) + Enrichr | T-cell functional states (68 STCAT + 276 Azimuth) |
| **HLAAllele** | 100 | IPD-IMGT/HLA | EBI IPD API | Major HLA class I and II alleles |
| **Anatomy** | 88 | HPA v23 + Open Targets | TSV + GraphQL | Tissues and anatomical regions |
| **TMECompartment** | 25 | PanglaoDB | Enrichr text download | Tumor microenvironment compartments |

---

## Edge Types (Relationships)

| Edge Type | Count | Source Database | API / Method | Confidence | What It Means |
|---|---|---|---|---|---|
| **KGene-regulates-Gene** | 2,477,140 | LINCS L1000 | Enrichr text download | 1.0 (binary) | KO of gene X changes expression of gene Y |
| **Protein-regulates-Gene** | 1,051,989 | ENCODE/ChEA/ChEA2022 | Enrichr text download | 1.0 (binary) | TF X binds promoter of gene Y (ChIP-seq) |
| **Gene-expressedIN-CellType** | 616,565 | HPA v23 | TSV download | 1.0 (level in props) | Gene X expressed in cell type Y (IHC) |
| **Anatomy-expresses-Gene** | 418,700 | HPA v23 | TSV download | 1.0 (level in props) | Tissue X expresses gene Y |
| **Disease-associates-Gene** | 169,540 | Open Targets | GraphQL API | 0.1–0.91 (OT score) | Disease X associated with gene Y (GWAS/OMIM/ClinVar) |
| **Gene-participates-Pathway** | 83,365 | Reactome + KEGG | via MyGene.info | 1.0 (curated) | Gene X is in pathway Y |
| **Protein-interacts-Protein** | 78,571 | STRING-DB | REST API | 0.4–0.999 (STRING score) | Protein A interacts with protein B |
| **Gene-participates-BP** | 74,679 | Gene Ontology | via MyGene.info | 1.0 (curated) | Gene X in biological process Y |
| **Gene-participates-MF** | 52,625 | Gene Ontology | via MyGene.info | 1.0 (curated) | Gene X has molecular function Y |
| **Gene-participates-CC** | 47,967 | Gene Ontology | via MyGene.info | 1.0 (curated) | Gene X localizes to component Y |
| **Compound-binds-Protein** | 38,322 | DGIdb | GraphQL API | 0–1.0 (normalized score) | Drug X binds/modulates protein Y |
| **Protein-localizes-CC** | 30,447 | UniProt | REST API | 1.0 (reviewed) | Protein X in subcellular location Y |
| **Compound-treats-Disease** | 23,222 | ChEMBL | REST API | 1.0 (phase 3+) | Drug X indicated for disease Y (FDA/EMA) |
| **Gene-encodes-Protein** | 19,224 | UniProt | REST API | 1.0 (canonical) | Gene X encodes protein Y |
| **Disease-localizes-Anatomy** | 7,959 | Open Targets | GraphQL API | 1.0 (curated) | Disease X affects anatomy Y |
| **Gene-has-Variant** | 4,905 | ClinVar | NCBI Entrez eutils | 1.0 (pathogenic) | Gene X has pathogenic variant Y |
| **TMECompartment-signature** | 3,827 | PanglaoDB | Enrichr text download | 1.0 (curated marker) | TME compartment X marked by gene Y |
| **IFS-marked-by-Gene** | 3,396 | STCAT + Azimuth | TSV + Enrichr | 1.0 (classifier weight) | Immune state X marked by gene Y |
| **CellType-isa-CellType** | 2,713 | Cell Ontology | EBI OLS4 API | 1.0 (ontology) | Cell type X is subtype of Y |
| **Disease-contains-Disease** | 897 | OncoTree | REST API | 1.0 (ontology) | Disease category X contains Y |

---

## Data Source Registry

| # | Database | URL | API Type | License | Edges | Entities | Proof Level |
|---|---|---|---|---|---|---|---|
| 1 | LINCS L1000 (Enrichr) | maayanlab.cloud/Enrichr | REST text | CC-BY | 2,477,140 | — | L4 Perturbational |
| 2 | HPA v23 | v23.proteinatlas.org | TSV download | CC-BY-SA | 1,035,265 | 2,244 | L1 Experimental |
| 3 | ChEA 2022 (Enrichr) | maayanlab.cloud/Enrichr | REST text | CC-BY | 501,938 | — | L1 ChIP-seq |
| 4 | ENCODE TF ChIP-seq 2015 | maayanlab.cloud/Enrichr | REST text | CC-BY | 470,577 | — | L1 ChIP-seq |
| 5 | Open Targets | api.platform.opentargets.org | GraphQL | Apache-2.0 | 177,499 | 14,003 | L2 Observational |
| 6 | Gene Ontology (MyGene) | mygene.info | REST POST | CC-BY | 175,271 | 10,733 | L1 Curated |
| 7 | ENCODE/ChEA Consensus | maayanlab.cloud/Enrichr | REST text | CC-BY | 79,474 | — | L1 ChIP-seq |
| 8 | STRING-DB | string-db.org | REST | CC-BY | 78,571 | — | L2 Combined |
| 9 | Reactome (MyGene) | mygene.info | REST POST | CC-BY | 61,247 | — | L1 Curated |
| 10 | UniProt | rest.uniprot.org | REST | CC-BY | 49,671 | 19,220 | L1 Reviewed |
| 11 | DGIdb | dgidb.org | GraphQL | MIT | 38,322 | 17,065* | L1 Curated |
| 12 | ChEMBL | ebi.ac.uk/chembl | REST | CC-BY-SA | 23,222 | 6,129* | L7 Clinical |
| 13 | KEGG | rest.kegg.jp | REST | Academic | 22,118 | 20,693 | L1 Curated |
| 14 | ClinVar (NCBI) | eutils.ncbi.nlm.nih.gov | Entrez | Public | 4,905 | 3,049 | L7 Clinical |
| 15 | PanglaoDB (Enrichr) | maayanlab.cloud/Enrichr | REST text | CC-BY | 3,827 | 25 | L2 scRNA-seq |
| 16 | Cell Ontology (OLS) | ebi.ac.uk/ols4 | REST | CC-BY | 2,713 | 2,002 | L1 Ontology |
| 17 | STCAT/Azimuth (Enrichr) | TCPGdb + Enrichr | TSV + REST | Research | 3,396 | 344 | L4 Classifier |
| 18 | OncoTree | oncotree.info | REST | — | 897 | 897 | L1 Curated |

*Compound entities shared between DGIdb and ChEMBL

---

## Confidence Score Interpretation

| Score Range | Meaning | Edge Types Using It |
|---|---|---|
| **1.0** (fixed) | Curated fact — binary present/absent | Ontology edges, ChIP-seq binding, GO annotations, LINCS KO |
| **0.4–0.999** | STRING combined score (experimental + predicted + text-mining) | Protein-interacts-Protein |
| **0.1–0.913** | Open Targets overall association score (23 sources aggregated) | Disease-associates-Gene |
| **0–1.0** | DGIdb interaction score (normalized, evidence-weighted) | Compound-binds-Protein |

---

## Proof Level Assignment

| Proof Level | Description | Edge Types |
|---|---|---|
| **L1: Ontology** | Curated biological fact from authoritative database | Gene-encodes-Protein, GO edges, pathway membership, UniProt localization, CL/OncoTree hierarchy |
| **L2: Observational** | Statistical association or experimental observation | Disease-associates-Gene, Protein-interacts-Protein, Anatomy-expresses-Gene, Gene-expressedIN-CellType |
| **L4: Perturbational** | Perturbation experiment → molecular readout | KGene-regulates-Gene (LINCS CRISPR KO), IFS-marked-by-Gene (STCAT classifier) |
| **L7: Published/Clinical** | FDA-approved or clinical-grade evidence | Compound-treats-Disease (ChEMBL phase 3+), Gene-has-Variant (ClinVar pathogenic) |

---

## Schema Coverage

- **19/24 entity types populated** (missing: Study, Cohort, ProteinDomain, ProteinFamily — runtime or low-priority)
- **20/23 edge types populated** (missing: Pathway-contains-Pathway [Reactome blocked], Gene-encodes-MiRNA [needs miRTarBase], Protein-has-ProteinDomain [needs InterPro])
- **100% edge provenance** (source_db field)
- **98.1% entity provenance** (xrefs field with source_db)
- **3 edge types with variable confidence** (STRING, Open Targets, DGIdb)
- **17 edge types with binary confidence** (1.0 = curated/present)
