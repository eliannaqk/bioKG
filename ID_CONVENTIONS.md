# ID conventions

Every entity_id and edge_id is constructed from a small set of rules.
Following these exactly is what makes ingestion idempotent and makes two
independent KG builds deterministically agree.

## Entity IDs

Entities use the upstream identifier when one exists; otherwise a typed
prefix + slugified name. Slugs are produced by:

```python
slug = name.replace(" ", "_").replace("+", "p")[:N]   # N varies per type
```

| Entity type | ID format | Example | Source of the slug |
|---|---|---|---|
| `Gene` | HGNC symbol verbatim | `A1BG` | MyGene.info |
| `Protein` | UniProt accession verbatim | `P04217` | UniProt |
| `Variant` | `ClinVar:{uid}` | `ClinVar:4445985` | ClinVar Entrez UID |
| `Pathway` (Reactome) | Reactome stable ID | `R-HSA-109582` | Reactome |
| `Pathway` (KEGG) | KEGG ID (`hsa…`) | `hsa04110` | KEGG |
| `BiologicalProcess` / `MolecularFunction` / `CellularComponent` | GO ID verbatim | `GO:0060396` | Gene Ontology |
| `CellType` (Cell Ontology) | CL ID verbatim | `CL:0000000` | Cell Ontology |
| `CellType` (HPA) | `CT-{tissue[:15]}-{cell_type[:15]}` | `CT-appendix-glandular_cells` | HPA v23 |
| `Disease` (EFO/MONDO) | EFO/MONDO ID verbatim | `EFO_0004274`, `MONDO_0007244` | Open Targets |
| `Disease` (ChEMBL) | ChEMBL indication ID | `CHEMBL_…` | ChEMBL |
| `CancerType` | `ONCO-{oncotree_code}` | `ONCO-THYROID` | OncoTree |
| `CancerLineage` | `LINEAGE-{lineage.replace(' ', '_')}` | `LINEAGE-Ovary/Fallopian_Tube` | DepMap Model.csv |
| `CellLine` | DepMap Achilles ID | `ACH-000001` | DepMap |
| `Anatomy` | `ANAT-{tissue.replace(' ', '_')[:30]}` | `ANAT-appendix` | HPA v23 |
| `Compound` (DGIdb) | `iuphar.ligand:{n}` or `chembl:{n}` (xref preserved) | `iuphar.ligand:7635` | DGIdb |
| `Compound` (ChEMBL) | ChEMBL molecule ID | `CHEMBL1201823` | ChEMBL |
| `TherapyRegimen` | `THR-{action[:20]}-{target[:20]}` | `THR-Carbonic_anhydrase_VII_inhibitor` | ChEMBL mechanism |
| `EC` | `EC:{ec_number}` | `EC:1.1.1.1` | KEGG |
| `Reaction` | KEGG reaction ID | `R00001` | KEGG |
| `MiRNA` | miRBase precursor name | `hsa-mir-6859-1` | miRBase |
| `HLAAllele` | full nomenclature | `A*01:01:01:01` | IPD-IMGT/HLA |
| `ImmuneFunctionalState` (Azimuth/curated) | `IFS-{name.replace(' ', '_').replace('+','p')[:50]}` | `IFS-STCAT-CD4_Tc` | Azimuth/STCAT |
| `TMECompartment` | `TME-{name}` | `TME-adipocyte` | PanglaoDB |
| `Phenotype` (TCPGdb) | `PHENO-{phenotype_id}` | `PHENO-cytokine_IFNG` | TCPGdb |

**Slug rules (when applied):**
1. Lowercase is **not** forced — preserve source casing.
2. Replace spaces with `_`.
3. Replace `+` with `p` (gene-name conventions: `CD4+` → `CD4p`).
4. Truncate to the per-type length cap shown above.
5. Do **not** percent-encode; do **not** strip punctuation other than spaces/`+`.

## Edge IDs

Edge IDs are deterministic functions of `(source_id, target_id, edge_type)` so
re-ingestion never duplicates and any two implementations converge byte-for-byte.

| Edge group | Format | Example |
|---|---|---|
| STRING PPI | `PPI-{min(a,b)}-{max(a,b)}` (sorted!) | `PPI-AASDH-ABHD11` |
| Enrichr LINCS | `LINCS-{perturbed}-{target}-{library[:10]}` | `LINCS-A1BG-HOMER2-LINCS_L100` |
| Reactome pathway membership | `reactome-{gene}-{pathway_id}` | `reactome-A1BG-R-HSA-109582` |
| CollecTRI TF→target | `collectri-{tf}-{target}` | `collectri-MYC-TERT` |
| STRING (reference edges) | `string-{a}-{b}` | `string-AASDH-ABHD11` |
| iPTMnet phospho | `iptmnet-{kinase}-phospho-{substrate}-{site?}` | `iptmnet-CDK1-phospho-RB1-S807` |
| TCPGdb | `TCPG-{gene[:15]}-{phenotype[:15]}-{concordance[:3]}` | `TCPG-MAP4K1-PHENO-cytokine-sup` |
| Generic | `{source_id}|{edge_type}|{target_id}` (fallback in merger) | `MYC\|TF-bindsPromoter-Gene\|TERT` |

**Sorting rule** for symmetric edges (PPI, synthetic-lethality): always store
`min(a,b)` as `source_id` and `max(a,b)` as `target_id`, lexicographic order.
This avoids storing the same physical interaction twice.

**Confidence semantics in edge_id:** never. Confidence lives in the row, not the
key — it's expected to change when a source releases a new version.

## xrefs convention

`xrefs` is a flat `dict[str,str]` always keyed by lowercase source name:

```json
{"entrez": "1499", "uniprot": "P35222", "hgnc": "2514", "ensembl": "ENSG00000168036",
 "source_db": "MyGene_via_HGNC"}
```

`source_db` is reserved — it identifies which loader produced the row, not a
biological cross-reference.

## Properties convention

Free-form `properties` JSON, but a few keys are load-bearing:

| Key | Used by | Meaning |
|---|---|---|
| `n_cell_lines` | `CancerLineage` | DepMap cell-line count in the lineage |
| `lineage` | `CellLine` | back-reference to its `LINEAGE-…` ID |
| `level` | `Gene-expressedIN-CellType` | HPA expression band: `Not detected` / `Low` / `Medium` / `High` |
| `phase` | `Compound-treats-Disease` | ChEMBL max phase (3 or 4) |
| `action` | `Compound-binds-Protein`, `TherapyRegimen` | `INHIBITOR` / `AGONIST` / etc. |
| `significance` | `Variant` | ClinVar clinical significance string |
