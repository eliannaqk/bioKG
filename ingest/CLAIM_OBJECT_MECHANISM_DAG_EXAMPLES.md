# Claim Object Mechanism DAG Examples

This document gives examples for the architecture in
`CLAIM_DECOMPOSITION_DAG_ARCHITECTURE.md`.

The key rule is:

```text
claims are biological assertions
claim_relations are semantic relations
claim_decomposition_edges are proof/decomposition DAG edges
```

`claim_type` is not used to decide what to prove. The agent reads the claim
object and the decomposition edges.

## 1. Edge Shape

Example decomposition edge from a shared anchor fact into a mechanism module:

```json
{
  "edge_id": "decomp:setdb1:A1-to-te-dsrna",
  "source_claim_id": "F_SETDB1_H3K9me3",
  "target_claim_id": "M_TE_DSRNA",
  "support_operator": "ALL_OF",
  "support_operator_params": {},
  "source_role": "shared_anchor",
  "target_role": "mechanism_module",
  "group_id": "setdb1_te_dsrna",
  "edge_status": "active",
  "notes": "Shared chromatin anchor required by the TE/dsRNA arm."
}
```

Example semantic ordering relation:

```json
{
  "relation_id": "rel:setdb1-h3k9me3-enables-te-repression",
  "source_claim_id": "F_SETDB1_H3K9me3",
  "target_claim_id": "F_TE_REPRESSION",
  "relation_kind": "enables",
  "relation_status": "active",
  "notes": "Mechanistic order only; not Boolean parent rollup."
}
```

## 2. Local Boolean Semantics

All active decomposition edges into one `target_claim_id` form that target's
local Boolean rule.

```text
source_claim_id -> target_claim_id
child claim     -> parent or mechanism-module claim
```

No mixed operators at a target:

```text
valid:   all active children into M_A use ALL_OF
valid:   all active children into P use ANY_OF
invalid: one child into P uses ALL_OF and another child into P uses ANY_OF
```

For mixed expressions, introduce mechanism modules.

## 3. Shared Anchor: SETDB1 Immunogenicity Arms

Broad parent:

```text
P_SETDB1:
SETDB1 overactivity suppresses tumour-intrinsic immunogenicity and can
contribute to immune-checkpoint-blockade resistance.
```

Boolean structure:

```text
P_SETDB1 = M_IMMUNOGENICITY AND M_THERAPY_CONTEXT
M_IMMUNOGENICITY = M_TE_DSRNA OR M_ANTIGEN_PRESENTATION
M_TE_DSRNA = F_SETDB1_H3K9me3 AND F_TE_DEREPRESSION AND F_DSRNA_SIGNALING
M_ANTIGEN_PRESENTATION = F_SETDB1_H3K9me3 AND F_AP_REPRESSION AND F_TCELL_RECOGNITION
M_THERAPY_CONTEXT = F_HUMAN_SETDB1_AMP AND F_ICB_ASSOCIATION
```

Atomic claims:

| Claim | Meaning |
|---|---|
| `F_SETDB1_H3K9me3` | SETDB1 imposes repressive H3K9me3/heterochromatin at immune-relevant repetitive or open-genome regions. |
| `F_TE_DEREPRESSION` | Loss of SETDB1 derepresses transposable-element-derived RNAs or regulatory elements. |
| `F_DSRNA_SIGNALING` | TE derepression increases dsRNA/viral-mimicry or tumour-intrinsic inflammatory signaling. |
| `F_AP_REPRESSION` | SETDB1 activity represses antigen-presentation-related loci or MHC-I pathway output. |
| `F_TCELL_RECOGNITION` | Reduced antigen presentation lowers tumour recognition by cytotoxic T cells. |
| `F_HUMAN_SETDB1_AMP` | SETDB1 amplification/overactivity occurs in human tumours in the claimed context. |
| `F_ICB_ASSOCIATION` | SETDB1 amplification/overactivity is associated with immune exclusion or checkpoint-blockade resistance. |

```mermaid
flowchart TD
  P["P_SETDB1"]
  IMM["M_IMMUNOGENICITY"]
  TE["M_TE_DSRNA"]
  AP["M_ANTIGEN_PRESENTATION"]
  TX["M_THERAPY_CONTEXT"]
  A1["F_SETDB1_H3K9me3\nshared anchor"]
  A2["F_TE_DEREPRESSION"]
  A3["F_DSRNA_SIGNALING"]
  B2["F_AP_REPRESSION"]
  B3["F_TCELL_RECOGNITION"]
  H1["F_HUMAN_SETDB1_AMP"]
  H2["F_ICB_ASSOCIATION"]

  IMM -- "ALL_OF at P" --> P
  TX -- "ALL_OF at P" --> P
  TE -- "ANY_OF at M_IMMUNOGENICITY" --> IMM
  AP -- "ANY_OF at M_IMMUNOGENICITY" --> IMM

  A1 -- "ALL_OF; source_role=shared_anchor" --> TE
  A2 -- "ALL_OF" --> TE
  A3 -- "ALL_OF" --> TE

  A1 -- "ALL_OF; source_role=shared_anchor" --> AP
  B2 -- "ALL_OF" --> AP
  B3 -- "ALL_OF" --> AP

  H1 -- "ALL_OF" --> TX
  H2 -- "ALL_OF" --> TX
```

`F_SETDB1_H3K9me3` is one claim row with two active decomposition edges. That
fan-out is the DAG join point.

Semantic order can still be stored separately:

```text
F_SETDB1_H3K9me3 enables F_TE_DEREPRESSION
F_TE_DEREPRESSION enables F_DSRNA_SIGNALING
F_SETDB1_H3K9me3 enables F_AP_REPRESSION
F_AP_REPRESSION enables F_TCELL_RECOGNITION
```

Those `enables` rows live in `claim_relations`; they do not roll up
`P_SETDB1`.

Source anchor: Griffin et al., Nature 2021,
https://www.nature.com/articles/s41586-021-03520-4.

## 4. Mixed Logic Reified As Modules

Target expression:

```text
P = (A AND B) OR (C AND D)
```

Correct storage:

```text
M_AB = A AND B
M_CD = C AND D
P = M_AB OR M_CD
```

```mermaid
flowchart TD
  P["P"]
  MAB["M_AB"]
  MCD["M_CD"]
  A["F_A"]
  B["F_B"]
  C["F_C"]
  D["F_D"]

  MAB -- "ANY_OF at P" --> P
  MCD -- "ANY_OF at P" --> P
  A -- "ALL_OF at M_AB" --> MAB
  B -- "ALL_OF at M_AB" --> MAB
  C -- "ALL_OF at M_CD" --> MCD
  D -- "ALL_OF at M_CD" --> MCD
```

This satisfies the no-mixed-operators rule because each target has exactly one
operator across active incoming edges.

## 5. ALL_OF Mechanism: Statins Lower LDL

Parent:

```text
P_STATINS_LDL:
Statins lower serum LDL cholesterol through hepatic cholesterol synthesis
inhibition and LDL receptor upregulation.
```

Decomposition:

```text
P_STATINS_LDL = M_HEPATIC_UPTAKE AND M_SREBP2_LDLR_AXIS
M_HEPATIC_UPTAKE = F_HMGCR_INHIBITION AND F_INTRACELLULAR_CHOL_FALLS
M_SREBP2_LDLR_AXIS = F_SREBP2_ACTIVATED AND F_LDLR_UPREGULATED AND F_SERUM_LDL_CLEARED
```

```mermaid
flowchart TD
  P["P_STATINS_LDL"]
  M1["M_HEPATIC_UPTAKE"]
  M2["M_SREBP2_LDLR_AXIS"]
  F1["F_HMGCR_INHIBITION"]
  F2["F_INTRACELLULAR_CHOL_FALLS"]
  F3["F_SREBP2_ACTIVATED"]
  F4["F_LDLR_UPREGULATED"]
  F5["F_SERUM_LDL_CLEARED"]

  M1 -- "ALL_OF at P" --> P
  M2 -- "ALL_OF at P" --> P
  F1 -- "ALL_OF at M_HEPATIC_UPTAKE" --> M1
  F2 -- "ALL_OF at M_HEPATIC_UPTAKE" --> M1
  F3 -- "ALL_OF at M_SREBP2_LDLR_AXIS" --> M2
  F4 -- "ALL_OF at M_SREBP2_LDLR_AXIS" --> M2
  F5 -- "ALL_OF at M_SREBP2_LDLR_AXIS" --> M2
```

Temporal order belongs in `claim_relations`:

```text
F_HMGCR_INHIBITION enables F_INTRACELLULAR_CHOL_FALLS
F_INTRACELLULAR_CHOL_FALLS enables F_SREBP2_ACTIVATED
F_SREBP2_ACTIVATED enables F_LDLR_UPREGULATED
F_LDLR_UPREGULATED enables F_SERUM_LDL_CLEARED
```

This is a context-free biochemical chain example. The parent does not require
a genotype/state anchor such as "MMR-deficient genome" or "del(5q) clone"
before the substrate exists. Section 11 uses WRN/MSI to show the contrasting
pattern: a required context module plus a linear mechanism chain.

## 6. ANY_OF Mechanism: Ferroptosis Suppression

Parent:

```text
P_FERROPTOSIS_SUPPRESSED:
Cells suppress ferroptosis by maintaining lipid-peroxide detoxification.
```

Decomposition:

```text
P_FERROPTOSIS_SUPPRESSED = M_GPX4_AXIS OR M_FSP1_AXIS
M_GPX4_AXIS = F_GSH_AVAILABLE AND F_GPX4_REDUCES_LIPID_PEROXIDES
M_FSP1_AXIS = F_COQ10_REGENERATED AND F_FSP1_TRAPS_LIPID_RADICALS
```

```mermaid
flowchart TD
  P["P_FERROPTOSIS_SUPPRESSED"]
  G["M_GPX4_AXIS"]
  F["M_FSP1_AXIS"]
  G1["F_GSH_AVAILABLE"]
  G2["F_GPX4_REDUCES_LIPID_PEROXIDES"]
  F1["F_COQ10_REGENERATED"]
  F2["F_FSP1_TRAPS_LIPID_RADICALS"]

  G -- "ANY_OF at P" --> P
  F -- "ANY_OF at P" --> P
  G1 -- "ALL_OF at M_GPX4_AXIS" --> G
  G2 -- "ALL_OF at M_GPX4_AXIS" --> G
  F1 -- "ALL_OF at M_FSP1_AXIS" --> F
  F2 -- "ALL_OF at M_FSP1_AXIS" --> F
```

The two modules are sufficient alternatives. Both may be true in the same cell,
but either one can satisfy this parent claim.

Section 12 expands this into the FSP1/GPX4 Nature example and explains why
there is no clean shared upstream anchor.

## 7. K_OF_N Mechanism: Senescence Call

Parent:

```text
P_SENESCENCE:
The cell population is senescent.
```

Decomposition:

```text
P_SENESCENCE = K_OF_N(3, F_SA_BETAGAL, F_P16_HIGH, F_SASP, F_IRREVERSIBLE_ARREST)
```

```mermaid
flowchart TD
  P["P_SENESCENCE\nK_OF_N min_required=3"]
  A["F_SA_BETAGAL"]
  B["F_P16_HIGH"]
  C["F_SASP"]
  D["F_IRREVERSIBLE_ARREST"]

  A -- "K_OF_N at P" --> P
  B -- "K_OF_N at P" --> P
  C -- "K_OF_N at P" --> P
  D -- "K_OF_N at P" --> P
```

Each edge into `P_SENESCENCE` uses:

```json
{
  "support_operator": "K_OF_N",
  "support_operator_params": {
    "min_required": 3
  }
}
```

## 8. Mutually Exclusive Alternatives: T Helper Fate

Parent:

```text
P_T_HELPER_FATE:
A CD4 T cell is committed to one helper-cell fate in this context.
```

Decomposition:

```text
P_T_HELPER_FATE = exactly_one(M_TH1, M_TH2, M_TH17, M_TREG, M_TFH)
```

```mermaid
flowchart TD
  P["P_T_HELPER_FATE"]
  A["M_TH1"]
  B["M_TH2"]
  C["M_TH17"]
  D["M_TREG"]
  E["M_TFH"]

  A -- "MUTUALLY_EXCLUSIVE_ALTERNATIVES at P" --> P
  B -- "MUTUALLY_EXCLUSIVE_ALTERNATIVES at P" --> P
  C -- "MUTUALLY_EXCLUSIVE_ALTERNATIVES at P" --> P
  D -- "MUTUALLY_EXCLUSIVE_ALTERNATIVES at P" --> P
  E -- "MUTUALLY_EXCLUSIVE_ALTERNATIVES at P" --> P
```

If evidence supports both `M_TH1` and `M_TREG` in the same cell/context, that
is not redundant support. It flags either a mixed population, ambiguous
context, or a bad decomposition.

## 9. Independent Causes: Diabetes Etiology

Parent:

```text
P_DIABETES_ETIOLOGY:
This patient's diabetes can be explained by a supported etiology.
```

Decomposition:

```text
P_DIABETES_ETIOLOGY = independent_causes(M_T1D, M_T2D, M_MODY, M_GESTATIONAL, M_DRUG_INDUCED)
```

```mermaid
flowchart TD
  P["P_DIABETES_ETIOLOGY"]
  A["M_T1D"]
  B["M_T2D"]
  C["M_MODY"]
  D["M_GESTATIONAL"]
  E["M_DRUG_INDUCED"]

  A -- "INDEPENDENT_CAUSES at P" --> P
  B -- "INDEPENDENT_CAUSES at P" --> P
  C -- "INDEPENDENT_CAUSES at P" --> P
  D -- "INDEPENDENT_CAUSES at P" --> P
  E -- "INDEPENDENT_CAUSES at P" --> P
```

More than one cause may be true. The search policy should prefer the cause
most plausible in the current `context_set_json`.

## 10. Statins As The Context-Free ALL_OF Reference

The statin example in Section 5 is the reference pattern for a required
mechanism chain without a separate context anchor:

```text
P_STATINS_LDL = M_HEPATIC_UPTAKE AND M_SREBP2_LDLR_AXIS
```

The decomposition is still modular, but all modules are mechanism modules. The
claim does not first need a disease-genotype context such as MSI, BRCA1/2
deficiency, or del(5q). That is why the statin example is structurally closer
to the BRCA/PARP chain than to WRN/MSI or lenalidomide/del(5q) MDS.

## 11. WRN / MSI Synthetic Lethality

Parent:

```text
P_WRN_MSI_SL:
WRN loss or inhibition selectively kills microsatellite-unstable cancer cells.
```

This is the clean required-context-anchor pattern. The parent needs both a
context module and a mechanism module:

```text
P_WRN_MSI_SL = M_MSI_CONTEXT AND M_WRN_LOSS_DAMAGE_CHAIN
M_MSI_CONTEXT = F_MMR_DEFICIENT AND F_TA_REPEAT_EXPANDED
M_WRN_LOSS_DAMAGE_CHAIN =
  F_CRUCIFORM_SUBSTRATE AND
  F_REPLICATION_FORK_STALLING AND
  F_MUS81_CLEAVAGE AND
  F_DSB_CHROMOSOME_SHATTERING AND
  F_MSI_SELECTIVE_DEATH
```

Atomic claims:

| Claim | Meaning |
|---|---|
| `F_MMR_DEFICIENT` | The cancer context is mismatch-repair deficient / microsatellite unstable. |
| `F_TA_REPEAT_EXPANDED` | TA-dinucleotide repeat expansions are present in the MSI genome. |
| `F_CRUCIFORM_SUBSTRATE` | Expanded TA repeats form non-B DNA structures such as cruciform-like substrates. |
| `F_REPLICATION_FORK_STALLING` | Those structures stall replication forks and require WRN-dependent resolution. |
| `F_MUS81_CLEAVAGE` | Without WRN, structure-specific nucleases such as MUS81 cleave the stalled substrate. |
| `F_DSB_CHROMOSOME_SHATTERING` | Cleavage produces DNA double-strand breaks and chromosome shattering. |
| `F_MSI_SELECTIVE_DEATH` | The damage response produces MSI-selective growth arrest or death. |

```mermaid
flowchart TD
  P["P_WRN_MSI_SL"]
  CTX["M_MSI_CONTEXT"]
  MECH["M_WRN_LOSS_DAMAGE_CHAIN"]
  C1["F_MMR_DEFICIENT"]
  C2["F_TA_REPEAT_EXPANDED"]
  A["F_CRUCIFORM_SUBSTRATE"]
  B["F_REPLICATION_FORK_STALLING"]
  C["F_MUS81_CLEAVAGE"]
  D["F_DSB_CHROMOSOME_SHATTERING"]
  E["F_MSI_SELECTIVE_DEATH"]

  CTX -- "ALL_OF at P; source_role=context_bridge" --> P
  MECH -- "ALL_OF at P; source_role=required_step" --> P

  C1 -- "ALL_OF at M_MSI_CONTEXT" --> CTX
  C2 -- "ALL_OF at M_MSI_CONTEXT" --> CTX

  A -- "ALL_OF at M_WRN_LOSS_DAMAGE_CHAIN" --> MECH
  B -- "ALL_OF at M_WRN_LOSS_DAMAGE_CHAIN" --> MECH
  C -- "ALL_OF at M_WRN_LOSS_DAMAGE_CHAIN" --> MECH
  D -- "ALL_OF at M_WRN_LOSS_DAMAGE_CHAIN" --> MECH
  E -- "ALL_OF at M_WRN_LOSS_DAMAGE_CHAIN" --> MECH
```

Why this is not just a chain: without the upstream MMR-deficient/MSI state,
the expanded-repeat substrate does not exist at the right scale, and the WRN
dependency vanishes. That context is therefore an `ALL_OF` sibling of the
mechanism module, not background prose.

Mechanistic order still belongs in semantic relations:

```text
F_MMR_DEFICIENT enables F_TA_REPEAT_EXPANDED
F_TA_REPEAT_EXPANDED enables F_CRUCIFORM_SUBSTRATE
F_CRUCIFORM_SUBSTRATE enables F_REPLICATION_FORK_STALLING
F_REPLICATION_FORK_STALLING enables F_MUS81_CLEAVAGE
F_MUS81_CLEAVAGE enables F_DSB_CHROMOSOME_SHATTERING
F_DSB_CHROMOSOME_SHATTERING enables F_MSI_SELECTIVE_DEATH
```

Source anchors:

- Chan et al., "WRN helicase is a synthetic lethal target in microsatellite unstable cancers", Nature 2019, https://www.nature.com/articles/s41586-019-1102-x
- van Wietmarschen et al., "Repeat expansions confer WRN dependence in microsatellite-unstable cancers", Nature 2020, https://www.nature.com/articles/s41586-020-2769-8

## 12. FSP1 / GPX4 Ferroptosis Suppression

Parent:

```text
P_FERROPTOSIS_SUPPRESSED:
Cells suppress ferroptosis by detoxifying lipid peroxides or lipid radicals.
```

This is the pure `ANY_OF` pattern with no clean shared anchor:

```text
P_FERROPTOSIS_SUPPRESSED = M_GPX4_AXIS OR M_FSP1_AXIS
M_GPX4_AXIS = F_GSH_AVAILABLE AND F_GPX4_REDUCES_LIPID_PEROXIDES
M_FSP1_AXIS = F_COQ10_AVAILABLE AND F_NADPH_AVAILABLE AND F_FSP1_REGENERATES_COQ10
```

The two systems have different cofactors, localization, and chemistry. They
converge only at the phenotype level: lipid-peroxide/radical detoxification
and ferroptosis suppression. Do not force a shared upstream anchor just to make
the graph look symmetric.

```mermaid
flowchart TD
  P["P_FERROPTOSIS_SUPPRESSED"]
  G["M_GPX4_AXIS"]
  F["M_FSP1_AXIS"]
  G1["F_GSH_AVAILABLE"]
  G2["F_GPX4_REDUCES_LIPID_PEROXIDES"]
  F1["F_COQ10_AVAILABLE"]
  F2["F_NADPH_AVAILABLE"]
  F3["F_FSP1_REGENERATES_COQ10"]

  G -- "ANY_OF at P; source_role=sufficient_module" --> P
  F -- "ANY_OF at P; source_role=sufficient_module" --> P

  G1 -- "ALL_OF at M_GPX4_AXIS" --> G
  G2 -- "ALL_OF at M_GPX4_AXIS" --> G

  F1 -- "ALL_OF at M_FSP1_AXIS" --> F
  F2 -- "ALL_OF at M_FSP1_AXIS" --> F
  F3 -- "ALL_OF at M_FSP1_AXIS" --> F
```

Contrast with SETDB1: SETDB1 has a real shared upstream chromatin anchor.
FSP1/GPX4 does not. The correct parent operator is `ANY_OF`, not `ALL_OF`.

Source anchor: Bersuker et al., "The CoQ oxidoreductase FSP1 acts parallel to
GPX4 to inhibit ferroptosis", Nature 2019,
https://www.nature.com/articles/s41586-019-1705-2.

Related Nature anchor: Doll et al., "FSP1 is a glutathione-independent
ferroptosis suppressor", Nature 2019,
https://www.nature.com/articles/s41586-019-1707-0.

## 13. Lenalidomide / CK1alpha In del(5q) MDS

Parent:

```text
P_LEN_DEL5Q_MDS:
Lenalidomide creates a therapeutic window in del(5q) MDS by degrading CK1alpha.
```

This is "therapeutic window from AND": a required genetic context anchor plus a
drug-mechanism chain.

```text
P_LEN_DEL5Q_MDS = M_DEL5Q_CONTEXT AND M_CK1A_DRUG_CHAIN
M_DEL5Q_CONTEXT = F_DEL5Q_PRESENT AND F_CSNK1A1_IN_CDR AND F_CK1A_HAPLOINSUFFICIENT
M_CK1A_DRUG_CHAIN =
  F_LENALIDOMIDE_BINDS_CRBN AND
  F_CRBN_RECRUITS_CK1A AND
  F_CK1A_UBIQUITINATED AND
  F_CK1A_DEGRADED AND
  F_DEL5Q_SELECTIVE_DEATH
```

```mermaid
flowchart TD
  P["P_LEN_DEL5Q_MDS"]
  CTX["M_DEL5Q_CONTEXT"]
  DRUG["M_CK1A_DRUG_CHAIN"]
  C1["F_DEL5Q_PRESENT"]
  C2["F_CSNK1A1_IN_CDR"]
  C3["F_CK1A_HAPLOINSUFFICIENT"]
  D1["F_LENALIDOMIDE_BINDS_CRBN"]
  D2["F_CRBN_RECRUITS_CK1A"]
  D3["F_CK1A_UBIQUITINATED"]
  D4["F_CK1A_DEGRADED"]
  D5["F_DEL5Q_SELECTIVE_DEATH"]

  CTX -- "ALL_OF at P; source_role=context_bridge" --> P
  DRUG -- "ALL_OF at P; source_role=required_step" --> P

  C1 -- "ALL_OF at M_DEL5Q_CONTEXT" --> CTX
  C2 -- "ALL_OF at M_DEL5Q_CONTEXT" --> CTX
  C3 -- "ALL_OF at M_DEL5Q_CONTEXT" --> CTX

  D1 -- "ALL_OF at M_CK1A_DRUG_CHAIN" --> DRUG
  D2 -- "ALL_OF at M_CK1A_DRUG_CHAIN" --> DRUG
  D3 -- "ALL_OF at M_CK1A_DRUG_CHAIN" --> DRUG
  D4 -- "ALL_OF at M_CK1A_DRUG_CHAIN" --> DRUG
  D5 -- "ALL_OF at M_CK1A_DRUG_CHAIN" --> DRUG
```

This is structurally distinct from synthetic lethality. The del(5q) context
creates reduced CK1alpha reserve; lenalidomide then creates drug-induced
degradation through CRBN. Both are required for the therapeutic-window parent.

Cross-parent join example:

```text
F_LENALIDOMIDE_BINDS_CRBN
```

is one atomic claim. It can feed many drug-mechanism modules:

```mermaid
flowchart TD
  D1["F_LENALIDOMIDE_BINDS_CRBN"]
  CK["M_CK1A_DRUG_CHAIN\ndel(5q) MDS parent"]
  MM["M_IKZF1_3_MYELOMA_CHAIN\nmultiple myeloma parent"]
  TC["M_IKZF1_3_TCELL_CHAIN\nT-cell / immune-modulation parent"]

  D1 -- "ALL_OF; source_role=shared_anchor" --> CK
  D1 -- "ALL_OF; source_role=shared_anchor" --> MM
  D1 -- "ALL_OF; source_role=shared_anchor" --> TC
```

The shared claim is not duplicated as `D1_for_MDS`, `D1_for_myeloma`, and
`D1_for_T_cells`. It has many decomposition parents.

Source anchors:

- Kronke et al., "Lenalidomide induces ubiquitination and degradation of CK1alpha in del(5q) MDS", Nature 2015, https://www.nature.com/articles/nature14610
- Petzold et al., "Structural basis of lenalidomide-induced CK1alpha degradation by the CRL4-CRBN ubiquitin ligase", Nature 2016, https://www.nature.com/articles/nature16979

## 14. Minimal SQL

Find active decomposition children:

```sql
SELECT
  source_claim_id AS child_claim_id,
  target_claim_id AS target_claim_id,
  support_operator,
  support_operator_params,
  source_role,
  target_role,
  group_id
FROM claim_decomposition_edges
WHERE target_claim_id = '<claim_id>'
  AND edge_status = 'active'
ORDER BY group_id, source_claim_id;
```

Find shared anchors:

```sql
SELECT
  source_claim_id AS shared_child_claim_id,
  COUNT(DISTINCT target_claim_id) AS n_targets
FROM claim_decomposition_edges
WHERE edge_status = 'active'
GROUP BY source_claim_id
HAVING COUNT(DISTINCT target_claim_id) > 1;
```

Check the no-mixed-operators invariant:

```sql
SELECT target_claim_id, COUNT(DISTINCT support_operator) AS n_ops
FROM claim_decomposition_edges
WHERE edge_status = 'active'
GROUP BY target_claim_id
HAVING COUNT(DISTINCT support_operator) > 1;
```

Find semantic ordering relations:

```sql
SELECT source_claim_id, target_claim_id, relation_kind, notes
FROM claim_relations
WHERE relation_kind = 'enables'
  AND relation_status = 'active';
```
