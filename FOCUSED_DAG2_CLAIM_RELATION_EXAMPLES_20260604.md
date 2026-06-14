# Focused DAG2 Claim Relation Examples

Date: 2026-06-04

Purpose: target DAG2 constructions for four hypotheses where the current broad
example file is too noisy or scientifically ambiguous. These are candidate
claim-object DAGs intended to guide Step0/DAG2 compiler behavior, not L2/L3
proof results.

Solid arrows in the Mermaid diagrams are `claim_decomposition_edges`: they
carry Boolean rollup operators. Dotted arrows are `claim_relations`: they show
biological order, refinement, or branch relationships and do not roll up parent
truth.

Participant convention: participants should be role-labeled KG node ids. When a
node is not known to exist yet, it is written as `PROPOSED-*` with the intended
KG type in parentheses and should be inserted into `entities` before accepting
the claim row. Core gene participants in these examples were checked against the
current KG where possible. ADAR1 maps to the canonical HGNC gene `HGNC:ADAR`;
MDA5 maps to `HGNC:IFIH1`; PKR maps to `HGNC:EIF2AK2`.

## 1. ADAR1 Blockade / dsRNA Sensing / PD-1 Sensitization

Input hypothesis:

```text
ADAR1 blockade will sensitize tumors to PD-1 therapy by allowing endogenous
double-stranded RNA to activate antiviral sensing and tumor inflammation.
```

Copy-paste claim bullets:
- ADAR blockade sensitizes tumors to anti-PD-1 therapy by increasing endogenous dsRNA sensing, antiviral inflammatory output, and tumor immune visibility.
- ADAR loss or blockade increases unedited endogenous dsRNA available for antiviral sensor recognition in tumor cells.
- In ADAR-blocked tumor cells, either the IFIH1/MDA5-MAVS-IFNB1 arm or the EIF2AK2/PKR antiviral-stress arm links unedited endogenous dsRNA accumulation to anti-PD-1-relevant tumor immune control.
- Unedited endogenous dsRNA activates IFIH1/MDA5 signaling in ADAR-blocked tumor cells.
- IFIH1/MDA5 signaling requires MAVS to induce IFNB1 or type-I-interferon output in ADAR-blocked tumor cells.
- IFNB1 or type-I-interferon output increases tumor inflammatory visibility, antigen-presentation programs, chemokine output, or CD8 T-cell recognition.
- Unedited endogenous dsRNA activates EIF2AK2/PKR signaling in ADAR-blocked tumor cells.
- EIF2AK2/PKR activation drives antiviral stress or growth-control output in ADAR-blocked tumor cells.
- EIF2AK2/PKR-dependent stress output increases tumor-cell vulnerability to immune-mediated control or growth inhibition in the ADAR-blockade context.
- ADAR loss or blockade increases anti-PD-1 response in immune-competent tumor contexts.

Mechanism group colors in the DAG: parent red, shared substrate blue,
branch-choice purple, MDA5/MAVS green, PKR amber, therapeutic endpoint gray.

Corrected construction note: the sensor branch should not be a flat ALL_OF
chain where both MDA5 and PKR are mandatory. It also should not have a separate
parent-level "sensor output increases immune visibility" child that restates
the sensor module. Instead, each sufficient branch should be a complete route
from endogenous dsRNA sensing to a downstream immune-visibility or tumor-control
phenotype, and the alternative bridge claim should explicitly name the
MDA5/MAVS-IFNB1 arm and the PKR antiviral-stress arm. Generic wording such as
"one dsRNA route reaches immune visibility" is too broad. The therapeutic PD-1
endpoint remains a separate required claim so that proximal sensor activation
alone does not automatically prove anti-PD-1 sensitization.

Formula:

```text
P_ADAR_PD1_SENSITIZATION =
  F_ADAR_BLOCKADE_INCREASES_UNEDITED_DSRNA AND
  M_ADAR_MDA5_OR_PKR_PD1_BRIDGE AND
  F_ADAR_BLOCKADE_SENSITIZES_TO_ANTI_PD1

M_ADAR_MDA5_OR_PKR_PD1_BRIDGE =
  M_MDA5_MAVS_IFN_VISIBILITY_ARM OR
  M_PKR_STRESS_VISIBILITY_ARM

M_MDA5_MAVS_IFN_VISIBILITY_ARM =
  F_DSRNA_ACTIVATES_MDA5 AND
  F_MDA5_MAVS_INDUCES_IFNB1 AND
  F_IFNB1_INCREASES_TUMOR_IMMUNE_VISIBILITY

M_PKR_STRESS_VISIBILITY_ARM =
  F_DSRNA_ACTIVATES_PKR AND
  F_PKR_DRIVES_ANTIVIRAL_STRESS_OUTPUT AND
  F_PKR_OUTPUT_INCREASES_TUMOR_IMMUNE_CONTROL
```

Source context: local `ADAR1paper.pdf`; DOI reported in the earlier audit as
`10.1038/s41586-018-0768-9`.

### Claim Rows

| ID | claim_text | participants | relation_name | polarity | context/properties |
|---|---|---|---|---|---|
| `P_ADAR_PD1_SENSITIZATION` | ADAR blockade sensitizes tumors to anti-PD-1 therapy by increasing endogenous dsRNA sensing, antiviral inflammatory output, and tumor immune visibility. | target_gene:`HGNC:ADAR` (Gene); therapy_context:`PROPOSED-THR-anti_PD1` (TherapyRegimen); therapy_target_gene:`HGNC:PDCD1` (Gene); phenotype:`PROPOSED-PHENO-ICB_sensitization` (Phenotype); cell_context:`PROPOSED-TME-tumor_intrinsic` (TMECompartment) | `sensitizes_to_therapy` | `positive` | parent hypothesis; ADAR1 alias resolved to ADAR |
| `M_ADAR_MDA5_OR_PKR_PD1_BRIDGE` | In ADAR-blocked tumor cells, either the IFIH1/MDA5-MAVS-IFNB1 arm or the EIF2AK2/PKR antiviral-stress arm links unedited endogenous dsRNA accumulation to anti-PD-1-relevant tumor immune control. | target_gene:`HGNC:ADAR` (Gene); substrate:`PROPOSED-unedited_endogenous_dsRNA` (RNAEntity); sensor_gene:`HGNC:IFIH1` (Gene); adaptor_gene:`HGNC:MAVS` (Gene); sensor_kinase_gene:`HGNC:EIF2AK2` (Gene); output_gene:`HGNC:IFNB1` (Gene); phenotype:`PROPOSED-PHENO-immune_mediated_tumor_control` (Phenotype); therapy_context:`PROPOSED-THR-anti_PD1` (TherapyRegimen) | `describes_mechanism` | SQL `NULL` | module=true; alternative complete routes |
| `M_MDA5_MAVS_IFN_VISIBILITY_ARM` | The IFIH1/MDA5-MAVS arm converts unedited endogenous dsRNA into IFNB1-linked tumor immune-visibility biology. | sensor_gene:`HGNC:IFIH1` (Gene); adaptor_gene:`HGNC:MAVS` (Gene); output_gene:`HGNC:IFNB1` (Gene); phenotype:`PROPOSED-PHENO-tumor_immune_visibility` (Phenotype) | `drives_phenotype` | `positive` | module=true; MDA5/MAVS route |
| `M_PKR_STRESS_VISIBILITY_ARM` | The EIF2AK2/PKR arm converts unedited endogenous dsRNA into antiviral stress biology that increases tumor vulnerability to immune control. | sensor_kinase_gene:`HGNC:EIF2AK2` (Gene); substrate:`PROPOSED-unedited_endogenous_dsRNA` (RNAEntity); phenotype:`PROPOSED-PHENO-immune_mediated_tumor_control` (Phenotype) | `drives_phenotype` | `positive` | module=true; PKR route |
| `F_ADAR_BLOCKADE_INCREASES_UNEDITED_DSRNA` | ADAR loss or blockade increases unedited endogenous dsRNA available for antiviral sensor recognition in tumor cells. | target_gene:`HGNC:ADAR` (Gene); substrate:`PROPOSED-unedited_endogenous_dsRNA` (RNAEntity); process:`PROPOSED-BP-antiviral_sensor_exposure` (BiologicalProcess); cell_context:`PROPOSED-TME-tumor_intrinsic` (TMECompartment) | `increases` | `positive` | shared substrate anchor |
| `F_DSRNA_ACTIVATES_MDA5` | Unedited endogenous dsRNA activates IFIH1/MDA5 signaling in ADAR-blocked tumor cells. | substrate:`PROPOSED-unedited_endogenous_dsRNA` (RNAEntity); sensor_gene:`HGNC:IFIH1` (Gene); cell_context:`PROPOSED-TME-tumor_intrinsic` (TMECompartment) | `activates` | `positive` | MDA5 branch |
| `F_MDA5_MAVS_INDUCES_IFNB1` | IFIH1/MDA5 signaling requires MAVS to induce IFNB1 or type-I-interferon output in ADAR-blocked tumor cells. | sensor_gene:`HGNC:IFIH1` (Gene); adaptor_gene:`HGNC:MAVS` (Gene); output_gene:`HGNC:IFNB1` (Gene); cell_context:`PROPOSED-TME-tumor_intrinsic` (TMECompartment) | `requires` | `positive` | MDA5/MAVS output |
| `F_IFNB1_INCREASES_TUMOR_IMMUNE_VISIBILITY` | IFNB1 or type-I-interferon output increases tumor inflammatory visibility, antigen-presentation programs, chemokine output, or CD8 T-cell recognition. | output_gene:`HGNC:IFNB1` (Gene); phenotype:`PROPOSED-PHENO-tumor_immune_visibility` (Phenotype); immune_cell:`PROPOSED-CT-CD8_TCELL` (CellType); cell_context:`PROPOSED-TME-tumor_intrinsic` (TMECompartment) | `increases` | `positive` | MDA5/MAVS downstream visibility bridge |
| `F_DSRNA_ACTIVATES_PKR` | Unedited endogenous dsRNA activates EIF2AK2/PKR signaling in ADAR-blocked tumor cells. | substrate:`PROPOSED-unedited_endogenous_dsRNA` (RNAEntity); sensor_kinase_gene:`HGNC:EIF2AK2` (Gene); cell_context:`PROPOSED-TME-tumor_intrinsic` (TMECompartment) | `activates` | `positive` | PKR branch |
| `F_PKR_DRIVES_ANTIVIRAL_STRESS_OUTPUT` | EIF2AK2/PKR activation drives antiviral stress or growth-control output in ADAR-blocked tumor cells. | sensor_kinase_gene:`HGNC:EIF2AK2` (Gene); pathway:`PROPOSED-PATHWAY-integrated_stress_response` (Pathway); phenotype:`PROPOSED-PHENO-antiviral_stress_output` (Phenotype); cell_context:`PROPOSED-TME-tumor_intrinsic` (TMECompartment) | `drives_phenotype` | `positive` | PKR output |
| `F_PKR_OUTPUT_INCREASES_TUMOR_IMMUNE_CONTROL` | EIF2AK2/PKR-dependent stress output increases tumor-cell vulnerability to immune-mediated control or growth inhibition in the ADAR-blockade context. | sensor_kinase_gene:`HGNC:EIF2AK2` (Gene); phenotype:`PROPOSED-PHENO-tumor_cell_growth_inhibition` (Phenotype); phenotype:`PROPOSED-PHENO-immune_mediated_tumor_control` (Phenotype); cell_context:`PROPOSED-TME-tumor_intrinsic` (TMECompartment) | `increases` | `positive` | PKR downstream tumor-control bridge |
| `F_ADAR_BLOCKADE_SENSITIZES_TO_ANTI_PD1` | ADAR loss or blockade increases anti-PD-1 response in immune-competent tumor contexts. | target_gene:`HGNC:ADAR` (Gene); therapy_context:`PROPOSED-THR-anti_PD1` (TherapyRegimen); therapy_target_gene:`HGNC:PDCD1` (Gene); phenotype:`PROPOSED-PHENO-ICB_sensitization` (Phenotype) | `sensitizes_to_therapy` | `positive` | therapeutic endpoint |

### Decomposition Edges

| source -> target | operator | source_role | group_id |
|---|---|---|---|
| `F_ADAR_BLOCKADE_INCREASES_UNEDITED_DSRNA -> P_ADAR_PD1_SENSITIZATION` | `ALL_OF` | `shared_anchor` | `adar_parent` |
| `M_ADAR_MDA5_OR_PKR_PD1_BRIDGE -> P_ADAR_PD1_SENSITIZATION` | `ALL_OF` | `required_step` | `adar_parent` |
| `F_ADAR_BLOCKADE_SENSITIZES_TO_ANTI_PD1 -> P_ADAR_PD1_SENSITIZATION` | `ALL_OF` | `context_bridge` | `adar_parent` |
| `M_MDA5_MAVS_IFN_VISIBILITY_ARM -> M_ADAR_MDA5_OR_PKR_PD1_BRIDGE` | `ANY_OF` | `sufficient_module` | `adar_sensor_choice` |
| `M_PKR_STRESS_VISIBILITY_ARM -> M_ADAR_MDA5_OR_PKR_PD1_BRIDGE` | `ANY_OF` | `sufficient_module` | `adar_sensor_choice` |
| `F_DSRNA_ACTIVATES_MDA5 -> M_MDA5_MAVS_IFN_VISIBILITY_ARM` | `ALL_OF` | `required_step` | `mda5_mavs_arm` |
| `F_MDA5_MAVS_INDUCES_IFNB1 -> M_MDA5_MAVS_IFN_VISIBILITY_ARM` | `ALL_OF` | `required_step` | `mda5_mavs_arm` |
| `F_IFNB1_INCREASES_TUMOR_IMMUNE_VISIBILITY -> M_MDA5_MAVS_IFN_VISIBILITY_ARM` | `ALL_OF` | `required_step` | `mda5_mavs_arm` |
| `F_DSRNA_ACTIVATES_PKR -> M_PKR_STRESS_VISIBILITY_ARM` | `ALL_OF` | `required_step` | `pkr_arm` |
| `F_PKR_DRIVES_ANTIVIRAL_STRESS_OUTPUT -> M_PKR_STRESS_VISIBILITY_ARM` | `ALL_OF` | `required_step` | `pkr_arm` |
| `F_PKR_OUTPUT_INCREASES_TUMOR_IMMUNE_CONTROL -> M_PKR_STRESS_VISIBILITY_ARM` | `ALL_OF` | `required_step` | `pkr_arm` |

### Semantic Claim Relations

| source -> target | relation_kind | notes |
|---|---|---|
| `F_ADAR_BLOCKADE_INCREASES_UNEDITED_DSRNA -> F_DSRNA_ACTIVATES_MDA5` | `enables` | Increased unedited dsRNA supplies the ligand for the MDA5 branch. |
| `F_ADAR_BLOCKADE_INCREASES_UNEDITED_DSRNA -> F_DSRNA_ACTIVATES_PKR` | `enables` | Increased unedited dsRNA supplies the ligand for the PKR branch. |
| `F_DSRNA_ACTIVATES_MDA5 -> F_MDA5_MAVS_INDUCES_IFNB1` | `enables` | MDA5 activation is upstream of MAVS-dependent IFNB1 output. |
| `F_MDA5_MAVS_INDUCES_IFNB1 -> F_IFNB1_INCREASES_TUMOR_IMMUNE_VISIBILITY` | `enables` | IFNB1/type-I-IFN output is upstream of tumor immune-visibility programs. |
| `F_DSRNA_ACTIVATES_PKR -> F_PKR_DRIVES_ANTIVIRAL_STRESS_OUTPUT` | `enables` | PKR activation is upstream of stress or antiviral output. |
| `F_PKR_DRIVES_ANTIVIRAL_STRESS_OUTPUT -> F_PKR_OUTPUT_INCREASES_TUMOR_IMMUNE_CONTROL` | `enables` | PKR stress output must be shown to affect tumor vulnerability or immune control before it supports the PD-1 mechanism. |
| `M_MDA5_MAVS_IFN_VISIBILITY_ARM -> M_PKR_STRESS_VISIBILITY_ARM` | `parallel_to` | Distinct complete dsRNA-to-visibility routes. |
| `F_IFNB1_INCREASES_TUMOR_IMMUNE_VISIBILITY -> F_ADAR_BLOCKADE_SENSITIZES_TO_ANTI_PD1` | `enables` | MDA5/MAVS immune visibility is one mechanistic bridge into checkpoint response. |
| `F_PKR_OUTPUT_INCREASES_TUMOR_IMMUNE_CONTROL -> F_ADAR_BLOCKADE_SENSITIZES_TO_ANTI_PD1` | `enables` | PKR-linked tumor control is the parallel bridge into checkpoint response. |

### Relation-Labeled DAG2 Visualization

```mermaid
flowchart TD
  P["P_ADAR_PD1_SENSITIZATION<br/>ADAR blockade sensitizes tumors to anti-PD-1"]
  SENSOR["M_ADAR_MDA5_OR_PKR_PD1_BRIDGE<br/>Either MDA5-MAVS-IFNB1 or PKR links dsRNA to PD-1-relevant tumor control"]
  MDA5["M_MDA5_MAVS_IFN_VISIBILITY_ARM<br/>MDA5-MAVS-IFNB1 route"]
  PKR["M_PKR_STRESS_VISIBILITY_ARM<br/>PKR stress-control route"]
  DSRNA["F_ADAR_BLOCKADE_INCREASES_UNEDITED_DSRNA<br/>ADAR blockade exposes unedited endogenous dsRNA"]
  A1["F_DSRNA_ACTIVATES_MDA5<br/>Unedited dsRNA activates IFIH1/MDA5"]
  A2["F_MDA5_MAVS_INDUCES_IFNB1<br/>MDA5 requires MAVS to induce IFNB1"]
  A3["F_IFNB1_INCREASES_TUMOR_IMMUNE_VISIBILITY<br/>IFNB1/type-I-IFN increases tumor immune visibility"]
  B1["F_DSRNA_ACTIVATES_PKR<br/>Unedited dsRNA activates EIF2AK2/PKR"]
  B2["F_PKR_DRIVES_ANTIVIRAL_STRESS_OUTPUT<br/>PKR drives antiviral stress output"]
  B3["F_PKR_OUTPUT_INCREASES_TUMOR_IMMUNE_CONTROL<br/>PKR output increases tumor vulnerability/control"]
  PD1["F_ADAR_BLOCKADE_SENSITIZES_TO_ANTI_PD1<br/>ADAR blockade improves anti-PD-1 response"]

  DSRNA -- "DAG2 ALL_OF shared_anchor" --> P
  SENSOR -- "DAG2 ALL_OF required_step" --> P
  PD1 -- "DAG2 ALL_OF context_bridge" --> P
  MDA5 -- "DAG2 ANY_OF sufficient_module" --> SENSOR
  PKR -- "DAG2 ANY_OF sufficient_module" --> SENSOR
  A1 -- "DAG2 ALL_OF" --> MDA5
  A2 -- "DAG2 ALL_OF" --> MDA5
  A3 -- "DAG2 ALL_OF" --> MDA5
  B1 -- "DAG2 ALL_OF" --> PKR
  B2 -- "DAG2 ALL_OF" --> PKR
  B3 -- "DAG2 ALL_OF" --> PKR

  DSRNA -. "claim_relations: enables" .-> A1
  DSRNA -. "claim_relations: enables" .-> B1
  A1 -. "claim_relations: enables" .-> A2
  A2 -. "claim_relations: enables" .-> A3
  B1 -. "claim_relations: enables" .-> B2
  B2 -. "claim_relations: enables" .-> B3
  MDA5 -. "claim_relations: parallel_to" .-> PKR
  A3 -. "claim_relations: enables" .-> PD1
  B3 -. "claim_relations: enables" .-> PD1

  classDef parent fill:#fee2e2,stroke:#b91c1c,color:#111827;
  classDef shared fill:#dbeafe,stroke:#1d4ed8,color:#111827;
  classDef choice fill:#ede9fe,stroke:#6d28d9,color:#111827;
  classDef mda5 fill:#dcfce7,stroke:#15803d,color:#111827;
  classDef pkr fill:#fef3c7,stroke:#b45309,color:#111827;
  classDef endpoint fill:#f3f4f6,stroke:#374151,color:#111827;
  class P parent;
  class DSRNA shared;
  class SENSOR choice;
  class MDA5,A1,A2,A3 mda5;
  class PKR,B1,B2,B3 pkr;
  class PD1 endpoint;
```

## 2. RBMS1 / dsRNA Shielding / Cell-Intrinsic Immune Suppression

Input hypothesis:

```text
RBMS1 binds endogenous dsRNA hairpins and shields them from MDA5 and PKR
recognition, preventing activation of antiviral interferon signaling and thereby
reducing cell-intrinsic immune activation.
```

Copy-paste claim bullets:
- RBMS1 shields endogenous dsRNA hairpins from MDA5 and PKR recognition, reducing antiviral interferon signaling and cell-intrinsic immune activation.
- RBMS1 physically binds endogenous dsRNA hairpin structures.
- RBMS1 shielding reduces MDA5/MAVS interferon signaling from endogenous dsRNA hairpins.
- RBMS1 occupancy on endogenous dsRNA hairpins reduces IFIH1/MDA5 access or recognition.
- Reduced MDA5 recognition lowers MAVS-dependent type-I-interferon or ISG signaling.
- RBMS1 shielding reduces PKR-dependent stress or antiviral signaling from endogenous dsRNA hairpins.
- RBMS1 occupancy on endogenous dsRNA hairpins reduces EIF2AK2/PKR access or recognition.
- Reduced PKR recognition lowers PKR-dependent stress signaling or antiviral immune activation.
- Shielding endogenous dsRNA from MDA5 and PKR reduces antiviral interferon signaling and cell-intrinsic immune activation.
- RBMS1 loss unmasks endogenous dsRNA hairpins and increases MDA5 or PKR sensor activation.

Mechanism group colors in the DAG: parent red, shared binding blue,
MDA5/MAVS green, PKR amber, endpoint gray, loss-of-function discriminator pink.

Construction note: this hypothesis explicitly names both MDA5 and PKR. Unless
the user rewrites it as "one of several sensors," DAG2 should require both
shielding arms. The arms are separate modules because MDA5/MAVS interferon
signaling and PKR stress signaling have different readouts.

Formula:

```text
P_RBMS1_DSRNA_SHIELDING =
  F_RBMS1_BINDS_DSRNA_HAIRPINS AND
  M_RBMS1_MDA5_SHIELDING_ARM AND
  M_RBMS1_PKR_SHIELDING_ARM AND
  F_SENSOR_SHIELDING_REDUCES_IFN_SIGNALING AND
  F_RBMS1_LOSS_UNMASKS_SENSOR_ACTIVATION

M_RBMS1_MDA5_SHIELDING_ARM =
  F_RBMS1_REDUCES_MDA5_DSRNA_ACCESS AND
  F_MDA5_ACCESS_REDUCTION_REDUCES_MAVS_IFN

M_RBMS1_PKR_SHIELDING_ARM =
  F_RBMS1_REDUCES_PKR_DSRNA_ACCESS AND
  F_PKR_ACCESS_REDUCTION_REDUCES_STRESS_IFN
```

Source context: lab hypothesis; direct primary literature attachment is still
needed before any child is treated as known evidence.

### Claim Rows

| ID | claim_text | participants | relation_name | polarity | context/properties |
|---|---|---|---|---|---|
| `P_RBMS1_DSRNA_SHIELDING` | RBMS1 shields endogenous dsRNA hairpins from MDA5 and PKR recognition, reducing antiviral interferon signaling and cell-intrinsic immune activation. | effector_gene:`HGNC:RBMS1` (Gene); substrate:`PROPOSED-endogenous_dsRNA_hairpin` (RNAEntity); sensor_gene:`HGNC:IFIH1` (Gene); sensor_kinase_gene:`HGNC:EIF2AK2` (Gene); phenotype:`PROPOSED-PHENO-cell_intrinsic_immune_activation` (Phenotype) | `suppresses` | `negative` | parent hypothesis |
| `M_RBMS1_MDA5_SHIELDING_ARM` | RBMS1 shielding reduces MDA5/MAVS interferon signaling from endogenous dsRNA hairpins. | effector_gene:`HGNC:RBMS1` (Gene); sensor_gene:`HGNC:IFIH1` (Gene); adaptor_gene:`HGNC:MAVS` (Gene); substrate:`PROPOSED-endogenous_dsRNA_hairpin` (RNAEntity) | `suppresses` | `negative` | module=true; MDA5 arm |
| `M_RBMS1_PKR_SHIELDING_ARM` | RBMS1 shielding reduces PKR-dependent stress or antiviral signaling from endogenous dsRNA hairpins. | effector_gene:`HGNC:RBMS1` (Gene); sensor_kinase_gene:`HGNC:EIF2AK2` (Gene); substrate:`PROPOSED-endogenous_dsRNA_hairpin` (RNAEntity) | `suppresses` | `negative` | module=true; PKR arm |
| `F_RBMS1_BINDS_DSRNA_HAIRPINS` | RBMS1 physically binds endogenous dsRNA hairpin structures. | effector_gene:`HGNC:RBMS1` (Gene); substrate:`PROPOSED-endogenous_dsRNA_hairpin` (RNAEntity) | `binds` | `positive` | substrate anchor |
| `F_RBMS1_REDUCES_MDA5_DSRNA_ACCESS` | RBMS1 occupancy on endogenous dsRNA hairpins reduces IFIH1/MDA5 access or recognition. | effector_gene:`HGNC:RBMS1` (Gene); substrate:`PROPOSED-endogenous_dsRNA_hairpin` (RNAEntity); sensor_gene:`HGNC:IFIH1` (Gene) | `blocks_recognition_by` | `negative` | MDA5 branch |
| `F_MDA5_ACCESS_REDUCTION_REDUCES_MAVS_IFN` | Reduced MDA5 recognition lowers MAVS-dependent type-I-interferon or ISG signaling. | sensor_gene:`HGNC:IFIH1` (Gene); adaptor_gene:`HGNC:MAVS` (Gene); pathway:`PROPOSED-PATHWAY-type_I_interferon` (Pathway); process:`PROPOSED-BP-ISG_expression` (BiologicalProcess) | `reduces` | `negative` | MDA5 downstream |
| `F_RBMS1_REDUCES_PKR_DSRNA_ACCESS` | RBMS1 occupancy on endogenous dsRNA hairpins reduces EIF2AK2/PKR access or recognition. | effector_gene:`HGNC:RBMS1` (Gene); substrate:`PROPOSED-endogenous_dsRNA_hairpin` (RNAEntity); sensor_kinase_gene:`HGNC:EIF2AK2` (Gene) | `blocks_recognition_by` | `negative` | PKR branch |
| `F_PKR_ACCESS_REDUCTION_REDUCES_STRESS_IFN` | Reduced PKR recognition lowers PKR-dependent stress signaling or antiviral immune activation. | sensor_kinase_gene:`HGNC:EIF2AK2` (Gene); pathway:`PROPOSED-PATHWAY-integrated_stress_response` (Pathway); phenotype:`PROPOSED-PHENO-antiviral_immune_activation` (Phenotype) | `reduces` | `negative` | PKR downstream |
| `F_SENSOR_SHIELDING_REDUCES_IFN_SIGNALING` | Shielding endogenous dsRNA from MDA5 and PKR reduces antiviral interferon signaling and cell-intrinsic immune activation. | sensor_gene:`HGNC:IFIH1` (Gene); sensor_kinase_gene:`HGNC:EIF2AK2` (Gene); phenotype:`PROPOSED-PHENO-cell_intrinsic_immune_activation` (Phenotype); pathway:`PROPOSED-PATHWAY-antiviral_RNA_sensing` (Pathway) | `reduces` | `negative` | endpoint bridge |
| `F_RBMS1_LOSS_UNMASKS_SENSOR_ACTIVATION` | RBMS1 loss unmasks endogenous dsRNA hairpins and increases MDA5 or PKR sensor activation. | effector_gene:`HGNC:RBMS1` (Gene); substrate:`PROPOSED-endogenous_dsRNA_hairpin` (RNAEntity); sensor_gene:`HGNC:IFIH1` (Gene); sensor_kinase_gene:`HGNC:EIF2AK2` (Gene) | `increases_when_lost` | `positive` | perturbation discriminator |

### Decomposition Edges

| source -> target | operator | source_role | group_id |
|---|---|---|---|
| `F_RBMS1_BINDS_DSRNA_HAIRPINS -> P_RBMS1_DSRNA_SHIELDING` | `ALL_OF` | `shared_anchor` | `rbms1_parent` |
| `M_RBMS1_MDA5_SHIELDING_ARM -> P_RBMS1_DSRNA_SHIELDING` | `ALL_OF` | `required_step` | `rbms1_parent` |
| `M_RBMS1_PKR_SHIELDING_ARM -> P_RBMS1_DSRNA_SHIELDING` | `ALL_OF` | `required_step` | `rbms1_parent` |
| `F_SENSOR_SHIELDING_REDUCES_IFN_SIGNALING -> P_RBMS1_DSRNA_SHIELDING` | `ALL_OF` | `required_step` | `rbms1_parent` |
| `F_RBMS1_LOSS_UNMASKS_SENSOR_ACTIVATION -> P_RBMS1_DSRNA_SHIELDING` | `ALL_OF` | `required_step` | `rbms1_parent` |
| `F_RBMS1_REDUCES_MDA5_DSRNA_ACCESS -> M_RBMS1_MDA5_SHIELDING_ARM` | `ALL_OF` | `required_step` | `rbms1_mda5_arm` |
| `F_MDA5_ACCESS_REDUCTION_REDUCES_MAVS_IFN -> M_RBMS1_MDA5_SHIELDING_ARM` | `ALL_OF` | `required_step` | `rbms1_mda5_arm` |
| `F_RBMS1_REDUCES_PKR_DSRNA_ACCESS -> M_RBMS1_PKR_SHIELDING_ARM` | `ALL_OF` | `required_step` | `rbms1_pkr_arm` |
| `F_PKR_ACCESS_REDUCTION_REDUCES_STRESS_IFN -> M_RBMS1_PKR_SHIELDING_ARM` | `ALL_OF` | `required_step` | `rbms1_pkr_arm` |

### Semantic Claim Relations

| source -> target | relation_kind | notes |
|---|---|---|
| `F_RBMS1_BINDS_DSRNA_HAIRPINS -> F_RBMS1_REDUCES_MDA5_DSRNA_ACCESS` | `enables` | Binding is the physical substrate anchor for MDA5 shielding. |
| `F_RBMS1_BINDS_DSRNA_HAIRPINS -> F_RBMS1_REDUCES_PKR_DSRNA_ACCESS` | `enables` | Binding is the physical substrate anchor for PKR shielding. |
| `F_RBMS1_REDUCES_MDA5_DSRNA_ACCESS -> F_MDA5_ACCESS_REDUCTION_REDUCES_MAVS_IFN` | `enables` | Less sensor access lowers downstream signaling. |
| `F_RBMS1_REDUCES_PKR_DSRNA_ACCESS -> F_PKR_ACCESS_REDUCTION_REDUCES_STRESS_IFN` | `enables` | Less sensor access lowers downstream signaling. |
| `F_MDA5_ACCESS_REDUCTION_REDUCES_MAVS_IFN -> F_SENSOR_SHIELDING_REDUCES_IFN_SIGNALING` | `enables` | MDA5 branch contributes to endpoint suppression. |
| `F_PKR_ACCESS_REDUCTION_REDUCES_STRESS_IFN -> F_SENSOR_SHIELDING_REDUCES_IFN_SIGNALING` | `enables` | PKR branch contributes to endpoint suppression. |
| `F_RBMS1_LOSS_UNMASKS_SENSOR_ACTIVATION -> P_RBMS1_DSRNA_SHIELDING` | `refines` | Loss-of-function is the key reversal test for the parent mechanism. |

### Relation-Labeled DAG2 Visualization

```mermaid
flowchart TD
  P["P_RBMS1_DSRNA_SHIELDING<br/>RBMS1 shields dsRNA and reduces immune activation"]
  MDA5["M_RBMS1_MDA5_SHIELDING_ARM<br/>RBMS1 blocks MDA5/MAVS signaling"]
  PKR["M_RBMS1_PKR_SHIELDING_ARM<br/>RBMS1 blocks PKR stress signaling"]
  BIND["F_RBMS1_BINDS_DSRNA_HAIRPINS<br/>RBMS1 binds endogenous dsRNA hairpins"]
  A1["F_RBMS1_REDUCES_MDA5_DSRNA_ACCESS<br/>RBMS1 reduces IFIH1/MDA5 access"]
  A2["F_MDA5_ACCESS_REDUCTION_REDUCES_MAVS_IFN<br/>Less MDA5 access lowers MAVS/IFN output"]
  B1["F_RBMS1_REDUCES_PKR_DSRNA_ACCESS<br/>RBMS1 reduces EIF2AK2/PKR access"]
  B2["F_PKR_ACCESS_REDUCTION_REDUCES_STRESS_IFN<br/>Less PKR access lowers stress/antiviral output"]
  END["F_SENSOR_SHIELDING_REDUCES_IFN_SIGNALING<br/>Sensor shielding reduces cell-intrinsic immune activation"]
  LOF["F_RBMS1_LOSS_UNMASKS_SENSOR_ACTIVATION<br/>RBMS1 loss unmasks dsRNA sensor activation"]

  BIND -- "DAG2 ALL_OF shared_anchor" --> P
  MDA5 -- "DAG2 ALL_OF required_step" --> P
  PKR -- "DAG2 ALL_OF required_step" --> P
  END -- "DAG2 ALL_OF required_step" --> P
  LOF -- "DAG2 ALL_OF required_step" --> P
  A1 -- "DAG2 ALL_OF" --> MDA5
  A2 -- "DAG2 ALL_OF" --> MDA5
  B1 -- "DAG2 ALL_OF" --> PKR
  B2 -- "DAG2 ALL_OF" --> PKR

  BIND -. "claim_relations: enables" .-> A1
  BIND -. "claim_relations: enables" .-> B1
  A1 -. "claim_relations: enables" .-> A2
  B1 -. "claim_relations: enables" .-> B2
  A2 -. "claim_relations: enables" .-> END
  B2 -. "claim_relations: enables" .-> END
  LOF -. "claim_relations: refines" .-> P

  classDef parent fill:#fee2e2,stroke:#b91c1c,color:#111827;
  classDef shared fill:#dbeafe,stroke:#1d4ed8,color:#111827;
  classDef mda5 fill:#dcfce7,stroke:#15803d,color:#111827;
  classDef pkr fill:#fef3c7,stroke:#b45309,color:#111827;
  classDef endpoint fill:#f3f4f6,stroke:#374151,color:#111827;
  classDef lof fill:#fce7f3,stroke:#be185d,color:#111827;
  class P parent;
  class BIND shared;
  class MDA5,A1,A2 mda5;
  class PKR,B1,B2 pkr;
  class END endpoint;
  class LOF lof;
```

## 3. PTPN2 Blockade / Anti-PD-1 Sensitization

Input hypothesis:

```text
PTPN2 blockade sensitizes tumors to PD-1 therapy.
```

Copy-paste claim bullets:
- PTPN2 blockade sensitizes tumors to anti-PD-1 therapy by amplifying interferon signaling and CD8-mediated tumor recognition.
- Loss or inhibition of PTPN2 phosphatase activity increases interferon-induced STAT/JAK-STAT signaling output in tumor cells.
- Amplified interferon-JAK-STAT signaling after PTPN2 blockade increases tumor-cell antigen-processing and MHC-I presentation machinery.
- Increased tumor-cell peptide-MHC-I presentation enables greater CD8 T-cell recognition.
- PTPN2 blockade increases CD8 T-cell-mediated tumor killing in immune-competent contexts.
- PTPN2 blockade increases tumor response to anti-PD-1 therapy.

Mechanism group colors in the DAG: parent red, proximal phosphatase/JAK-STAT
blue, MHC-I/APM visibility purple, CD8 biology green, therapeutic endpoint gray.

Construction note: this should not import the dual PTPN2/PTPN1 claim or the NK
arm unless the hypothesis explicitly asks for them. For a PD-1 sensitization
claim, the core chain should be PTPN2 inhibition -> interferon/JAK-STAT
amplification -> tumor antigen-presentation/MHC-I visibility -> CD8 recognition
or killing -> anti-PD-1 response. "PTPN2 blockade" is not a binding claim. It
means pharmacologic inhibition, genetic loss, or functional blockade of PTPN2
phosphatase activity, which removes a negative phosphatase constraint on
interferon-induced JAK-STAT/STAT1 signaling.

Formula:

```text
P_PTPN2_PD1_SENSITIZATION =
  F_PTPN2_BLOCKADE_AMPLIFIES_IFN_JAK_STAT AND
  F_IFN_JAK_STAT_UPREGULATES_MHC_I_APM AND
  F_MHC_I_APM_ENABLES_CD8_RECOGNITION AND
  F_PTPN2_BLOCKADE_INCREASES_CD8_TUMOR_KILLING AND
  F_PTPN2_BLOCKADE_SENSITIZES_TO_ANTI_PD1
```

Source context: PTPN2/PTPN1 primary paper in local folder
`s41586-023-06575-7.pdf`, DOI `10.1038/s41586-023-06575-7`. This focused
example intentionally tests the PTPN2-only version.

### Claim Rows

| ID | claim_text | participants | relation_name | polarity | context/properties |
|---|---|---|---|---|---|
| `P_PTPN2_PD1_SENSITIZATION` | PTPN2 blockade sensitizes tumors to anti-PD-1 therapy by amplifying interferon signaling and CD8-mediated tumor recognition. | target_gene:`HGNC:PTPN2` (Gene); therapy_context:`PROPOSED-THR-anti_PD1` (TherapyRegimen); therapy_target_gene:`HGNC:PDCD1` (Gene); immune_cell:`PROPOSED-CT-CD8_TCELL` (CellType); phenotype:`PROPOSED-PHENO-ICB_sensitization` (Phenotype); cell_context:`PROPOSED-TME-tumor_intrinsic` (TMECompartment) | `sensitizes_to_therapy` | `positive` | parent hypothesis |
| `F_PTPN2_BLOCKADE_AMPLIFIES_IFN_JAK_STAT` | Loss or inhibition of PTPN2 phosphatase activity increases interferon-induced STAT/JAK-STAT signaling output in tumor cells. | inhibited_target_gene:`HGNC:PTPN2` (Gene); inhibited_activity:`PROPOSED-MF-PTPN2_phosphatase_activity` (MolecularFunction); cytokine_gene_or_product:`HGNC:IFNG` (Gene); readout_gene_or_product:`HGNC:STAT1` (Gene); pathway:`PROPOSED-PATHWAY-interferon_JAK_STAT` (Pathway); process:`PROPOSED-BP-ISG_expression` (BiologicalProcess); cell_context:`PROPOSED-TME-tumor_intrinsic` (TMECompartment) | `loss_of_function_amplifies_pathway` | `positive` | proximal pathway; not a binding claim |
| `F_IFN_JAK_STAT_UPREGULATES_MHC_I_APM` | Amplified interferon-JAK-STAT signaling after PTPN2 blockade increases tumor-cell antigen-processing and MHC-I presentation machinery. | pathway:`PROPOSED-PATHWAY-interferon_JAK_STAT` (Pathway); target_gene:`HGNC:B2M` (Gene); target_gene:`PROPOSED-TAP1_GENE` (Gene); target_gene:`HGNC:HLA-A` (Gene); target_gene:`HGNC:HLA-B` (Gene); target_gene:`HGNC:HLA-C` (Gene); phenotype:`PROPOSED-PHENO-antigen_presentation` (Phenotype); cell_context:`PROPOSED-TME-tumor_intrinsic` (TMECompartment) | `upregulates` | `positive` | tumor visibility; `PROPOSED-TAP1_GENE` canonical_symbol=TAP1, insert before accepting |
| `F_MHC_I_APM_ENABLES_CD8_RECOGNITION` | Increased tumor-cell peptide-MHC-I presentation enables greater CD8 T-cell recognition. | phenotype:`PROPOSED-PHENO-antigen_presentation` (Phenotype); immune_cell:`PROPOSED-CT-CD8_TCELL` (CellType); cell_context:`PROPOSED-TME-tumor_intrinsic` (TMECompartment) | `enables_recognition_by` | `positive` | CD8 participant required |
| `F_PTPN2_BLOCKADE_INCREASES_CD8_TUMOR_KILLING` | PTPN2 blockade increases CD8 T-cell-mediated tumor killing in immune-competent contexts. | inhibited_target_gene:`HGNC:PTPN2` (Gene); immune_cell:`PROPOSED-CT-CD8_TCELL` (CellType); phenotype:`PROPOSED-PHENO-CD8_TCELL_killing` (Phenotype); cell_context:`PROPOSED-TME-tumor_intrinsic` (TMECompartment) | `increases` | `positive` | CD8 effector endpoint |
| `F_PTPN2_BLOCKADE_SENSITIZES_TO_ANTI_PD1` | PTPN2 blockade increases tumor response to anti-PD-1 therapy. | inhibited_target_gene:`HGNC:PTPN2` (Gene); therapy_context:`PROPOSED-THR-anti_PD1` (TherapyRegimen); therapy_target_gene:`HGNC:PDCD1` (Gene); phenotype:`PROPOSED-PHENO-ICB_sensitization` (Phenotype) | `sensitizes_to_therapy` | `positive` | therapeutic endpoint |

### Decomposition Edges

| source -> target | operator | source_role | group_id |
|---|---|---|---|
| `F_PTPN2_BLOCKADE_AMPLIFIES_IFN_JAK_STAT -> P_PTPN2_PD1_SENSITIZATION` | `ALL_OF` | `required_step` | `ptpn2_pd1_chain` |
| `F_IFN_JAK_STAT_UPREGULATES_MHC_I_APM -> P_PTPN2_PD1_SENSITIZATION` | `ALL_OF` | `required_step` | `ptpn2_pd1_chain` |
| `F_MHC_I_APM_ENABLES_CD8_RECOGNITION -> P_PTPN2_PD1_SENSITIZATION` | `ALL_OF` | `required_step` | `ptpn2_pd1_chain` |
| `F_PTPN2_BLOCKADE_INCREASES_CD8_TUMOR_KILLING -> P_PTPN2_PD1_SENSITIZATION` | `ALL_OF` | `required_step` | `ptpn2_pd1_chain` |
| `F_PTPN2_BLOCKADE_SENSITIZES_TO_ANTI_PD1 -> P_PTPN2_PD1_SENSITIZATION` | `ALL_OF` | `context_bridge` | `ptpn2_pd1_chain` |

### Semantic Claim Relations

| source -> target | relation_kind | notes |
|---|---|---|
| `F_PTPN2_BLOCKADE_AMPLIFIES_IFN_JAK_STAT -> F_IFN_JAK_STAT_UPREGULATES_MHC_I_APM` | `enables` | PTPN2 inhibition removes negative phosphatase regulation, increasing STAT/JAK-STAT output upstream of antigen-presentation gene induction. |
| `F_IFN_JAK_STAT_UPREGULATES_MHC_I_APM -> F_MHC_I_APM_ENABLES_CD8_RECOGNITION` | `enables` | MHC-I/APM is a CD8-recognition bridge, not an NK-killing claim. |
| `F_MHC_I_APM_ENABLES_CD8_RECOGNITION -> F_PTPN2_BLOCKADE_INCREASES_CD8_TUMOR_KILLING` | `enables` | CD8 recognition is upstream of CD8 cytotoxicity. |
| `F_PTPN2_BLOCKADE_INCREASES_CD8_TUMOR_KILLING -> F_PTPN2_BLOCKADE_SENSITIZES_TO_ANTI_PD1` | `enables` | The CD8 effector change is the biological bridge to PD-1 response. |

### Relation-Labeled DAG2 Visualization

```mermaid
flowchart TD
  P["P_PTPN2_PD1_SENSITIZATION<br/>PTPN2 blockade sensitizes tumors to anti-PD-1"]
  JAK["F_PTPN2_BLOCKADE_AMPLIFIES_IFN_JAK_STAT<br/>PTPN2 phosphatase inhibition increases IFN-induced STAT/JAK-STAT output"]
  MHC["F_IFN_JAK_STAT_UPREGULATES_MHC_I_APM<br/>Amplified IFN signaling increases MHC-I/APM machinery"]
  CD8REC["F_MHC_I_APM_ENABLES_CD8_RECOGNITION<br/>MHC-I/APM enables CD8 recognition"]
  CD8KILL["F_PTPN2_BLOCKADE_INCREASES_CD8_TUMOR_KILLING<br/>PTPN2 blockade increases CD8-mediated tumor killing"]
  PD1["F_PTPN2_BLOCKADE_SENSITIZES_TO_ANTI_PD1<br/>PTPN2 blockade improves anti-PD-1 response"]

  JAK -- "DAG2 ALL_OF required_step" --> P
  MHC -- "DAG2 ALL_OF required_step" --> P
  CD8REC -- "DAG2 ALL_OF required_step" --> P
  CD8KILL -- "DAG2 ALL_OF required_step" --> P
  PD1 -- "DAG2 ALL_OF context_bridge" --> P

  JAK -. "claim_relations: enables" .-> MHC
  MHC -. "claim_relations: enables" .-> CD8REC
  CD8REC -. "claim_relations: enables" .-> CD8KILL
  CD8KILL -. "claim_relations: enables" .-> PD1

  classDef parent fill:#fee2e2,stroke:#b91c1c,color:#111827;
  classDef proximal fill:#dbeafe,stroke:#1d4ed8,color:#111827;
  classDef visibility fill:#ede9fe,stroke:#6d28d9,color:#111827;
  classDef cd8 fill:#dcfce7,stroke:#15803d,color:#111827;
  classDef endpoint fill:#f3f4f6,stroke:#374151,color:#111827;
  class P parent;
  class JAK proximal;
  class MHC visibility;
  class CD8REC,CD8KILL cd8;
  class PD1 endpoint;
```

## 4. Ferroptosis / Lipid Peroxide and Radical Detox

Input hypothesis:

```text
Cells suppress ferroptosis by detoxifying lipid peroxides or lipid radicals.
```

Copy-paste claim bullets:
- Cells suppress ferroptosis through detoxification of lipid peroxides or lipid radicals.
- Lipid peroxide detoxification suppresses ferroptosis.
- GPX4 reduces lipid peroxides and suppresses ferroptotic death.
- DHODH reduces mitochondrial lipid peroxide accumulation and suppresses ferroptosis.
- Lipid radical quenching suppresses ferroptosis.
- AIFM2/FSP1 quenches lipid radicals through the CoQ axis and suppresses ferroptosis.
- GCH1-driven BH4 production quenches lipid radicals and suppresses ferroptosis.

Mechanism group colors in the DAG: parent red, peroxide-detox blue,
radical-detox amber.

Construction note: this should be represented as alternative sufficient detox
modules. A context may use GPX4, FSP1/AIFM2, DHODH, GCH1/BH4, or another
well-defined branch. No shared anchor should force all branches to be true.

Formula:

```text
P_FERROPTOSIS_LIPID_DETOX =
  M_LIPID_PEROXIDE_DETOX OR
  M_LIPID_RADICAL_DETOX

M_LIPID_PEROXIDE_DETOX =
  F_GPX4_REDUCES_LIPID_PEROXIDES OR
  F_DHODH_REDUCES_MITO_LIPID_PEROXIDES

M_LIPID_RADICAL_DETOX =
  F_AIFM2_FSP1_QUENCHES_LIPID_RADICALS OR
  F_GCH1_BH4_QUENCHES_LIPID_RADICALS
```

Source context: existing ferroptosis examples in this repo plus local review
context. Direct primary paper attachment should be added before using any child
as known evidence.

### Claim Rows

| ID | claim_text | participants | relation_name | polarity | context/properties |
|---|---|---|---|---|---|
| `P_FERROPTOSIS_LIPID_DETOX` | Cells suppress ferroptosis through detoxification of lipid peroxides or lipid radicals. | phenotype:`PROPOSED-PHENO-ferroptosis_suppression` (Phenotype); substrate:`PROPOSED-CHEBI-lipid_peroxide` (ChemicalEntity); substrate:`PROPOSED-lipid_radical` (ChemicalEntity); cell_context:`PROPOSED-CELL-generic` (CellContext) | `suppresses` | `negative` | parent hypothesis |
| `M_LIPID_PEROXIDE_DETOX` | Lipid peroxide detoxification suppresses ferroptosis. | substrate:`PROPOSED-CHEBI-lipid_peroxide` (ChemicalEntity); phenotype:`PROPOSED-PHENO-ferroptosis_suppression` (Phenotype); cell_context:`PROPOSED-CELL-generic` (CellContext) | `suppresses` | `negative` | module=true; peroxide detox |
| `M_LIPID_RADICAL_DETOX` | Lipid radical quenching suppresses ferroptosis. | substrate:`PROPOSED-lipid_radical` (ChemicalEntity); phenotype:`PROPOSED-PHENO-ferroptosis_suppression` (Phenotype); cell_context:`PROPOSED-CELL-generic` (CellContext) | `suppresses` | `negative` | module=true; radical detox |
| `F_GPX4_REDUCES_LIPID_PEROXIDES` | GPX4 reduces lipid peroxides and suppresses ferroptotic death. | effector_gene:`HGNC:GPX4` (Gene); substrate:`PROPOSED-CHEBI-lipid_peroxide` (ChemicalEntity); phenotype:`PROPOSED-PHENO-ferroptosis` (Phenotype) | `reduces` | `negative` | GPX4 branch |
| `F_DHODH_REDUCES_MITO_LIPID_PEROXIDES` | DHODH reduces mitochondrial lipid peroxide accumulation and suppresses ferroptosis. | effector_gene:`HGNC:DHODH` (Gene); substrate:`PROPOSED-CHEBI-lipid_peroxide` (ChemicalEntity); compartment:`PROPOSED-GO-mitochondrion` (CellularComponent); phenotype:`PROPOSED-PHENO-ferroptosis` (Phenotype) | `reduces` | `negative` | mitochondrial branch |
| `F_AIFM2_FSP1_QUENCHES_LIPID_RADICALS` | AIFM2/FSP1 quenches lipid radicals through the CoQ axis and suppresses ferroptosis. | effector_gene:`HGNC:AIFM2` (Gene); cofactor:`PROPOSED-CHEBI-coenzyme_Q10` (ChemicalEntity); substrate:`PROPOSED-lipid_radical` (ChemicalEntity); phenotype:`PROPOSED-PHENO-ferroptosis` (Phenotype) | `quenches` | `negative` | FSP1 branch |
| `F_GCH1_BH4_QUENCHES_LIPID_RADICALS` | GCH1-driven BH4 production quenches lipid radicals and suppresses ferroptosis. | effector_gene:`HGNC:GCH1` (Gene); cofactor:`PROPOSED-CHEBI-tetrahydrobiopterin` (ChemicalEntity); substrate:`PROPOSED-lipid_radical` (ChemicalEntity); phenotype:`PROPOSED-PHENO-ferroptosis` (Phenotype) | `quenches` | `negative` | GCH1/BH4 branch |

### Decomposition Edges

| source -> target | operator | source_role | group_id |
|---|---|---|---|
| `M_LIPID_PEROXIDE_DETOX -> P_FERROPTOSIS_LIPID_DETOX` | `ANY_OF` | `sufficient_module` | `ferroptosis_detox_choice` |
| `M_LIPID_RADICAL_DETOX -> P_FERROPTOSIS_LIPID_DETOX` | `ANY_OF` | `sufficient_module` | `ferroptosis_detox_choice` |
| `F_GPX4_REDUCES_LIPID_PEROXIDES -> M_LIPID_PEROXIDE_DETOX` | `INDEPENDENT_CAUSES` | `ordinary_child` | `peroxide_detox_alternatives` |
| `F_DHODH_REDUCES_MITO_LIPID_PEROXIDES -> M_LIPID_PEROXIDE_DETOX` | `INDEPENDENT_CAUSES` | `ordinary_child` | `peroxide_detox_alternatives` |
| `F_AIFM2_FSP1_QUENCHES_LIPID_RADICALS -> M_LIPID_RADICAL_DETOX` | `INDEPENDENT_CAUSES` | `ordinary_child` | `radical_detox_alternatives` |
| `F_GCH1_BH4_QUENCHES_LIPID_RADICALS -> M_LIPID_RADICAL_DETOX` | `INDEPENDENT_CAUSES` | `ordinary_child` | `radical_detox_alternatives` |

### Semantic Claim Relations

| source -> target | relation_kind | notes |
|---|---|---|
| `M_LIPID_PEROXIDE_DETOX -> M_LIPID_RADICAL_DETOX` | `parallel_to` | Distinct sufficient detox module classes. |
| `F_GPX4_REDUCES_LIPID_PEROXIDES -> F_DHODH_REDUCES_MITO_LIPID_PEROXIDES` | `parallel_to` | Both lower lipid peroxide burden through different compartments/systems. |
| `F_AIFM2_FSP1_QUENCHES_LIPID_RADICALS -> F_GCH1_BH4_QUENCHES_LIPID_RADICALS` | `parallel_to` | Both are radical-trapping routes. |

### Relation-Labeled DAG2 Visualization

```mermaid
flowchart TD
  P["P_FERROPTOSIS_LIPID_DETOX<br/>Cells suppress ferroptosis by detoxifying lipid damage"]
  PEROX["M_LIPID_PEROXIDE_DETOX<br/>Peroxide detoxification suppresses ferroptosis"]
  RAD["M_LIPID_RADICAL_DETOX<br/>Radical quenching suppresses ferroptosis"]
  GPX4["F_GPX4_REDUCES_LIPID_PEROXIDES<br/>GPX4 lowers lipid peroxides"]
  DHODH["F_DHODH_REDUCES_MITO_LIPID_PEROXIDES<br/>DHODH lowers mitochondrial lipid peroxides"]
  FSP1["F_AIFM2_FSP1_QUENCHES_LIPID_RADICALS<br/>AIFM2/FSP1 quenches lipid radicals through CoQ"]
  GCH1["F_GCH1_BH4_QUENCHES_LIPID_RADICALS<br/>GCH1/BH4 quenches lipid radicals"]

  PEROX -- "DAG2 ANY_OF sufficient_module" --> P
  RAD -- "DAG2 ANY_OF sufficient_module" --> P
  GPX4 -- "DAG2 INDEPENDENT_CAUSES" --> PEROX
  DHODH -- "DAG2 INDEPENDENT_CAUSES" --> PEROX
  FSP1 -- "DAG2 INDEPENDENT_CAUSES" --> RAD
  GCH1 -- "DAG2 INDEPENDENT_CAUSES" --> RAD

  PEROX -. "claim_relations: parallel_to" .-> RAD
  GPX4 -. "claim_relations: parallel_to" .-> DHODH
  FSP1 -. "claim_relations: parallel_to" .-> GCH1

  classDef parent fill:#fee2e2,stroke:#b91c1c,color:#111827;
  classDef peroxide fill:#dbeafe,stroke:#1d4ed8,color:#111827;
  classDef radical fill:#fef3c7,stroke:#b45309,color:#111827;
  class P parent;
  class PEROX,GPX4,DHODH peroxide;
  class RAD,FSP1,GCH1 radical;
```
