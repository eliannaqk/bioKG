# Ingestion scripts

## Required environment

```bash
# Where the SQLite DB and shard JSONs go (must exist, ~10 GB free).
export KG_DATA_ROOT=/path/to/kg_scratch
mkdir -p $KG_DATA_ROOT/kg_shards $KG_DATA_ROOT/logs

# Where DepMap / CPTAC bulk downloads live. Subdirs expected:
#   $EXTERNAL_DATA_ROOT/depmap/Model.csv
#   $EXTERNAL_DATA_ROOT/depmap/CRISPRGeneEffect.csv
#   $EXTERNAL_DATA_ROOT/cptac_all/pdc/...
#   $EXTERNAL_DATA_ROOT/cptac_rnaseq/...
export EXTERNAL_DATA_ROOT=/path/to/external_bulk

# Optional. Used only by populate_kg_curated.py and populate_kg_gemini.py to
# fill a few small gold-standard lists (HLA alleles, immune-state names) when
# the source DB doesn't expose a clean download. Every biological *edge* in
# the KG comes from a curated database — never from an LLM.
export GEMINI_API_KEY=...
```

The ingest scripts also call `dotenv` on `./.env` and `./.env.local` for
non-secret config; either file is optional.

## Running

End-to-end, using the SLURM driver:

```bash
sbatch populate_kg.sh                  # phase=all
```

Or step-by-step from a login node:

```bash
python populate_knowledge_graph.py --phase genes        # MyGene + UniProt
python populate_knowledge_graph.py --phase interactions # STRING PPI
python populate_knowledge_graph.py --phase lincs        # Enrichr LINCS L1000
python populate_knowledge_graph.py --phase diseases     # OpenTargets, etc.
python populate_kg_full.py                              # ChEMBL, KEGG, OncoTree, ClinVar, miRBase
python populate_kg_login.py                             # OpenTargets, Enrichr TF/LINCS (login-node mode)
python populate_kg_curated.py                           # PanglaoDB, Azimuth, IPD-IMGT/HLA
python populate_kg_gemini.py                            # HPA v23, Enrichr libraries
python populate_kg_remaining.py                         # UniProt, DGIdb, missing CC localizations
python populate_kg_opentargets.py                       # OT-specific shard
python populate_kg_depmap.py                            # DepMap CRISPR essentiality
python populate_kg_depmap_advanced.py                   # DepMap synthetic lethality (advanced)
python populate_kg_genomic_taiji.py                     # Taiji2 communities + SL pairs
python populate_kg_tcpgdb.py                            # TCPGdb concordance
python populate_kg_cptac.py                             # CPTAC PDC essentiality
python populate_kg_reference_edges.py                   # Reactome, CollecTRI, STRING (reference)
python merge_kg_shards.py                               # batch-insert all shards into SQLite
```

Each loader is idempotent on `entity_id` / `edge_id`. Re-running a single
loader is safe.

## File index

| File | Sources covered |
|---|---|
| `populate_knowledge_graph.py` | Driver. Phases: genes, interactions, lincs, diseases. |
| `populate_kg_worker.py` | Sharded workers for `populate_genes` and `populate_interactions`. |
| `populate_kg_full.py` | ChEMBL indications, InterPro, EFO/Disease hierarchy, Cell Ontology, OncoTree, KEGG, ClinVar, miRBase, IPD-IMGT/HLA. |
| `populate_kg_login.py` | OpenTargets GraphQL, Enrichr TF/LINCS libraries (login-node-friendly). |
| `populate_kg_curated.py` | PanglaoDB (TME compartments), Azimuth (immune states), IPD-IMGT/HLA. |
| `populate_kg_gemini.py` | HPA v23, Enrichr ChIP-seq libraries; uses Gemini only to fill gold-standard lists. |
| `populate_kg_datasets.py` | Alternate LINCS, HPA, TFLink loaders. |
| `populate_kg_opentargets.py` | OpenTargets-specific shards (Disease, Anatomy). |
| `populate_kg_remaining.py` | UniProt, DGIdb, residual subcellular localization. |
| `populate_kg_depmap.py` | DepMap CRISPR essentiality (CellLine, CancerLineage, edges). |
| `populate_kg_depmap_advanced.py` | DepMap synthetic-lethality and selective-dependency claims. |
| `populate_kg_genomic_taiji.py` | Taiji2 PageRank communities + SL pairs (`Gene-syntheticLethal-Gene`). |
| `populate_kg_tcpgdb.py` | TCPGdb concordance (`Gene-{drives,suppresses}-ImmunePhenotype`). |
| `populate_kg_cptac.py` | CPTAC patient-tumor proteome essentiality. |
| `populate_kg_reference_edges.py` | Reactome pathway membership, CollecTRI, STRING (reference graph). |
| `merge_kg_shards.py` | Batch-insert all `kg_shards/*.json` into SQLite. |
| `populate_kg.sh` | SLURM wrapper for `populate_knowledge_graph.py --phase all`. |

