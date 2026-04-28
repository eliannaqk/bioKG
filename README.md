## Snapshot at a glance

| | count |
|---|---|
| entity types | 24 |
| edge types | 27 |
| source databases | 31 |
| total entities | 144,379 |
| total edges | 6,218,497 |

## Layout

```
schema/
  entity_types.tsv      one row per entity type — count, sources, example row
  edge_types.tsv        one row per edge type — count, head/tail entity types, sources, example row
  resources.tsv         one row per source database — derived_from upstream, what
                        entities and edges it contributed
  table_schemas.sql     CREATE TABLE / CREATE INDEX statements from the live SQLite DB
  KG_PROVENANCE.md      curated provenance map: license, API, proof-level per source
```

## Regenerating the export

```bash
# defaults to /home/eqk3/scratch_pi_mg269/eqk3/coscientist_data/gbd_knowledge_graph.db
python scripts/export_kg.py

# or point at a different DB
python scripts/export_kg.py --db /path/to/gbd_knowledge_graph.db
GBD_KG_DB=/path/to/db python scripts/export_kg.py
```

The script only needs Python 3.11+ stdlib (`sqlite3`, `json`, `pathlib`).

## What this repo covers

Layer 1 of the KG only — **core entities + backbone edges** (the public reference graph).

1. **Core entities** — `Gene`, `Protein`, `Pathway`, `CellType`, `Disease`, … (table `entities`).
2. **Backbone edges** — stable curated facts (`Gene-encodes-Protein`, `Protein-interacts-Protein`, …) in `backbone_edges`. These are what `edge_types.tsv` enumerates.

The DAG2 proving layers (claims, evidence, support sets, contradictions) live in
the working repo and are intentionally excluded here. `table_schemas.sql` still
shows the full DDL for all 28 tables for reference, but only the two layers
above are exported as TSVs.

## Source database contributions

Top contributors by edge count (full list in `schema/resources.tsv`):

| source | edges | example edge type |
|---|---|---|
| LINCS L1000 CRISPR KO | 2,477,140 | KGene-regulates-Gene |
| HPA v23 | 1,035,265 | Gene-expressedIN-CellType, Anatomy-expresses-Gene |
| DepMap | 661,033 | CellLine-dependsOn-Gene, CancerLineage-essential-Gene, CellLine-isa-CancerLineage |
| ChEA 2022 | 501,938 | Protein-regulates-Gene |
| ENCODE TF ChIP-seq 2015 | 470,577 | Protein-regulates-Gene |
| STRING | 306,663 | Protein-interacts-Protein |
| Open Targets | 177,499 | Disease-associates-Gene, Disease-localizes-Anatomy |
| GO via MyGene | 175,271 | Gene-participates-{BP,MF,CC} |
| Reactome | 108,931 | Gene-participates-Pathway |
| UniProt | 49,671 | Gene-encodes-Protein, Protein-localizes-CC |
| CollecTRI | 38,420 | TF-bindsPromoter-Gene |
| DGIdb | 38,322 | Compound-binds-Protein |
| TDtool SL LASSO (← DepMap) | 28,792 | Gene-syntheticLethal-Gene |
| ChEMBL | 23,222 | Compound-treats-Disease |
| KEGG | 22,118 | Gene-participates-Pathway |
| ClinVar | 4,905 | Gene-has-Variant |

See `schema/KG_PROVENANCE.md` for license, API endpoint, and proof level
(L1 ontology / L2 observational / L4 perturbational / L7 clinical) per source.
