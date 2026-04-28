# bioKG — schema export of the GBD knowledge graph

This repo is a **schema-only** snapshot of the Get-Biology-Done (GBD) knowledge graph.
Everything a collaborator needs to understand the data model and reconstruct the KG
from upstream sources — the entity types, edge types, source databases, and table
DDL — without shipping the 5.5M-edge / 142k-node payload.

Live database (not in this repo): `gbd_knowledge_graph.db` (SQLite, ~2 GB).

## Snapshot at a glance

| | count |
|---|---|
| entity types | 23 |
| edge types | 24 |
| source databases | 31 |
| total entities | 142,728 |
| total edges | 5,557,464 |

## Layout

```
schema/
  entity_types.tsv      one row per entity type — count, sources, example row
  edge_types.tsv        one row per edge type — count, head/tail entity types, sources, example row
  resources.tsv         one row per source database — what entities and edges it contributed
  table_schemas.sql     CREATE TABLE / CREATE INDEX statements from the live SQLite DB
  schema.py             dataclass + Enum schema source (Layer 1 entities, backbone edges,
                        claims, evidence, support sets, contradictions)
  KG_PROVENANCE.md      curated provenance map: license, API, proof-level per source
scripts/
  export_kg.py          regenerates everything in schema/ from a live KG DB
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

## How the schema is layered

Four layers, defined in `schema/schema.py`:

1. **Core entities** — `Gene`, `Protein`, `Pathway`, `CellType`, `Disease`, … (table `entities`).
2. **Backbone edges** — stable curated facts (`Gene-encodes-Protein`, `Protein-interacts-Protein`, …) in `backbone_edges`. These are what `edge_types.tsv` enumerates.
3. **Claims** — context-dependent assertions with three orthogonal axes (essentiality, perturbation, regulatory, …); table `claims`.
4. **Logic** — `support_sets` (AND/OR), `contradictions`, `evidence` rows tying claims to data.

`table_schemas.sql` shows the full DDL for all 28 tables, not just the four covered here.

## Source database contributions

Top contributors by edge count (full list in `schema/resources.tsv`):

| source | edges | example edge type |
|---|---|---|
| LINCS L1000 CRISPR KO | 2,477,140 | KGene-regulates-Gene |
| HPA v23 | 1,035,265 | Gene-expressedIN-CellType, Anatomy-expresses-Gene |
| ChEA 2022 | 501,938 | Protein-regulates-Gene |
| ENCODE TF ChIP-seq 2015 | 470,577 | Protein-regulates-Gene |
| STRING | 306,663 | Protein-interacts-Protein |
| Open Targets | 177,499 | Disease-associates-Gene, Disease-localizes-Anatomy |
| GO via MyGene | 175,271 | Gene-participates-{BP,MF,CC} |
| Reactome | 108,931 | Gene-participates-Pathway |
| UniProt | 49,671 | Gene-encodes-Protein, Protein-localizes-CC |
| DGIdb | 38,322 | Compound-binds-Protein |
| CollecTRI | 38,420 | TF-bindsPromoter-Gene |
| TDtool SL LASSO | 28,792 | Gene-syntheticLethal-Gene |
| ChEMBL | 23,222 | Compound-treats-Disease |
| KEGG | 22,118 | Gene-participates-Pathway |
| ClinVar | 4,905 | Gene-has-Variant |

See `schema/KG_PROVENANCE.md` for license, API endpoint, and proof level
(L1 ontology / L2 observational / L4 perturbational / L7 clinical) per source.
