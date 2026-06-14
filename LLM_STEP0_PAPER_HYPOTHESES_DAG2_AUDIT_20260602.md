# LLM Step0 DAG2 Audit For Five Paper-Derived Hypotheses

Date: 2026-06-02

Source code under test: `/home/eqk3/coscientist/biologyDone/get-biology-done-proof-dag`

Local paper directory: `/home/eqk3/coscientist/biologyDone/reports/papers`

Run artifact: `/tmp/step0_five_hypotheses_llm_results.json`

## Run Policy

This audit used the live Stage0 DAG2 LLM compiler, not the deterministic fallback.

- `.env` loaded from `/home/eqk3/coscientist/biologyDone/.env`.
- `OPENAI_API_KEY` was present but not printed.
- `GBD_STAGE0_REQUIRE_DAG2_LLM=1`.
- All five outputs reported `dag2_generation.mode = llm_claim_specific_dag2_decomposition`.
- The fallback run was treated only as a diagnostic and is not used below.

The goal was to test whether the system can create specific DAG2 child claims from the supplied hypothesis plus literature/KG/expert/testability context, without hardcoded biology templates.

## Local References Inspected

| File | Local title / citation anchor | DOI |
| --- | --- | --- |
| `ADAR1paper.pdf` | Loss of ADAR1 in tumours overcomes resistance to immune checkpoint blockade | not present in PDF metadata |
| `nature23465.pdf` | CDK4/6 inhibition triggers anti-tumour immunity | `10.1038/nature23465` |
| `s41586-020-2229-5.pdf` | Autophagy promotes immune evasion of pancreatic cancer by degrading MHC-I | `10.1038/s41586-020-2229-5` |
| `s41586-023-06575-7.pdf` | The PTPN2/PTPN1 inhibitor ABBV-CLS-484 unleashes potent anti-tumour immunity | `10.1038/s41586-023-06575-7` |
| `s41580-024-00768-2.pdf` | Profiling cell identity and tissue architecture with single-cell and spatial transcriptomics | `10.1038/s41580-024-00768-2` |
| `cellTree.pdf` | A reference cell tree will serve science better than a reference cell atlas | `10.1016/j.cell.2023.02.016` |
| `cellstates.pdf` | Establishing a conceptual framework for holistic cell states and state transitions | `10.1016/j.cell.2024.04.035` |

Important caveat: the local PDF set contains a direct primary paper for the PTPN2/PTPN1 hypothesis. For the CIN/cGAS-STING, mitochondrial transfer, beta-catenin/DC exclusion, and IFNg/ferroptosis hypotheses, the local PDFs used here are mostly general cell-state, spatial, or immune-context references, not direct primary proof papers for those exact mechanisms.

## Overall Assessment

The LLM compiler produced meaningful and precise DAG2s for all five hypotheses. The outputs are much stronger than the deterministic fallback because they preserve the causal order and separate measurable biological steps instead of collapsing everything into broad immune-function facets.

Remaining gap: Step0 should record the exact compiler prompt/context and the expert-board mode in this audit output. The JSON captures selected expert/testability context, but `experts_consulted` is empty in these runs, so the report should not claim live expert consult rows were completed. The DAG2 compiler itself was live and required.

## Hypothesis 1: CIN -> Micronuclei -> cGAS-STING -> Metastasis

Input one-liner:

> Chromosomal instability causes micronuclei formation and chronic cGAS-STING signaling, which rewires tumor inflammation toward metastasis rather than immune clearance.

References supplied to Step0:

- `s41586-023-06575-7.pdf`: PTPN2/PTPN1 inhibitor paper; indirect immune inflammation context.
- `s41580-024-00768-2.pdf`: single-cell/spatial transcriptomics review; context for tumor microenvironment state measurement.
- `cellstates.pdf`: holistic cell-state framework; context for state-transition framing.

Grounded hypothesis:

> Chromosomal instability causes micronuclei formation and chronic cGAS-STING signaling, which rewires tumor inflammation toward metastasis rather than immune clearance.

DAG2 child claims:

1. `mechanism_cin_to_micronuclei`
   - Claim: Chromosomal instability in tumor cells increases formation of micronuclei containing missegregated chromosomal DNA.
   - Truth condition: When chromosomal instability is increased in tumor cells, the fraction of cells with DNA-positive micronuclei rises relative to chromosomally stable matched controls.

2. `mechanism_micronuclear_dna_exposure`
   - Claim: Micronuclei formed during chromosomal instability undergo envelope rupture or instability that exposes micronuclear DNA to the cytosol.
   - Truth condition: Micronuclei in chromosomally unstable tumor cells show increased envelope disruption together with cytosol-accessible DNA compared with intact primary nuclei.

3. `mechanism_micronuclei_to_sting_activation`
   - Claim: Cytosol-exposed micronuclear DNA activates the cGAS-STING pathway in tumor cells.
   - Truth condition: Cells containing ruptured or DNA-exposed micronuclei show increased cGAS pathway product formation and downstream STING1-TBK1-IRF3 signaling relative to matched cells lacking exposed micronuclei.

4. `mechanism_cin_to_chronic_sting`
   - Claim: Persistent chromosomal instability sustains chronic, rather than transient, cGAS-STING signaling in tumor cells.
   - Truth condition: Under ongoing chromosomal instability, STING1-pathway inflammatory signaling remains elevated across repeated timepoints instead of resolving after an acute pulse.

5. `mechanism_chronic_sting_to_inflammatory_rewiring`
   - Claim: Chronic STING1 signaling in tumor cells shifts inflammatory output from immune-clearing programs toward nonresolving pro-metastatic inflammatory programs.
   - Truth condition: Compared with acute or absent STING1 signaling, chronic STING1 activity produces a tumor-cell inflammatory state enriched for metastasis-associated cytokine or chemokine programs and reduced effective immune-clearance-associated programs.

6. `mechanism_inflammatory_rewiring_to_metastasis_bias`
   - Claim: The chronic STING1-driven inflammatory state increases metastatic dissemination or colonization more than it promotes immune-mediated tumor clearance.
   - Truth condition: In contexts with chronic STING1-associated inflammatory rewiring, tumors show increased invasion, dissemination, or metastatic outgrowth together with weaker effective immune elimination than matched controls lacking that rewired state.

Assessment: good DAG2. It correctly separates structural CIN, micronuclear DNA exposure, STING activation, chronicity, inflammatory state shift, and metastasis-biased outcome. The local PDF evidence set is weak for this exact claim, so L1 should prioritize direct CIN/cGAS-STING/metastasis literature before treating the mechanism as known.

## Hypothesis 2: Tumor-To-T-Cell Mitochondrial Transfer

Input one-liner:

> Tumor cells transfer damaged mitochondria into T cells, causing T-cell mitochondrial dysfunction and immune evasion; blocking mitochondrial transfer should restore T-cell cytotoxicity.

References supplied to Step0:

- `cellstates.pdf`: cell-state/state-transition conceptual framework.
- `s41580-024-00768-2.pdf`: single-cell/spatial transcriptomics review for resolving tumor/T-cell states.

Grounded hypothesis:

> Tumor cells transfer damaged mitochondria into T cells, causing T-cell mitochondrial dysfunction and immune evasion; blocking mitochondrial transfer should restore T-cell cytotoxicity.

DAG2 child claims:

1. `mechanism_intercellular_mitochondria_transfer`
   - Claim: Tumor cells transfer mitochondria into T cells in the tumor microenvironment.
   - Truth condition: In a tumor-T-cell context, mitochondria originating from tumor cells are directly detected inside recipient T cells at above-background frequency.

2. `mechanism_cargo_damage_state`
   - Claim: The mitochondria transferred from tumor cells into T cells are damaged or dysfunctional rather than healthy organelles.
   - Truth condition: Tumor-origin mitochondria found within recipient T cells show damage-associated features such as reduced membrane potential, elevated ROS, mtDNA damage, or impaired respiratory competence relative to intact donor mitochondria controls.

3. `mechanism_t_cell_mitochondrial_dysfunction`
   - Claim: Receipt of tumor-derived damaged mitochondria causes mitochondrial dysfunction in recipient T cells.
   - Truth condition: T cells that receive tumor-derived damaged mitochondria show worsened mitochondrial function, such as decreased membrane potential or oxidative phosphorylation and/or increased mitochondrial ROS, compared with matched T cells that do not receive such cargo.

4. `mechanism_cytotoxic_function_loss`
   - Claim: Mitochondrial dysfunction in T cells reduces their cytotoxic effector function against tumor cells.
   - Truth condition: Within the same T-cell context, mitochondrial dysfunction is accompanied by reduced tumor-cell killing and/or reduced effector outputs such as granzyme B, perforin, degranulation, or IFN-gamma production.

5. `mechanism_immune_evasion_outcome`
   - Claim: Loss of T-cell cytotoxic function permits increased tumor immune evasion or survival.
   - Truth condition: Contexts with impaired T-cell cytotoxicity show increased tumor-cell persistence, outgrowth, or resistance to immune-mediated elimination relative to matched contexts with preserved T-cell function.

6. `mechanism_transfer_blockade_rescue`
   - Claim: Blocking tumor-to-T-cell mitochondrial transfer restores T-cell mitochondrial fitness and cytotoxic function.
   - Truth condition: When the tumor-to-T-cell mitochondrial transfer process is inhibited, recipient T cells show reduced acquisition of tumor mitochondria together with improved mitochondrial function and increased cytotoxic effector activity relative to transfer-permissive controls.

Assessment: good DAG2. It correctly distinguishes transfer, damaged cargo, recipient T-cell mitochondrial dysfunction, cytotoxic impairment, tumor immune-evasion outcome, and blockade rescue. The local PDF evidence set is not direct for this exact mechanism, so L1 should find primary mitochondrial-transfer papers before considering this claim evidence-populated.

## Hypothesis 3: PTPN2/PTPN1 -> JAK-STAT IFN -> AP/NK/CD8 Killing

Input one-liner:

> PTPN2/PTPN1 act as brakes on JAK-STAT interferon signaling, so dual inhibition should amplify IFN response, antigen presentation, and NK/CD8 killing.

References supplied to Step0:

- `s41586-023-06575-7.pdf`: The PTPN2/PTPN1 inhibitor ABBV-CLS-484 unleashes potent anti-tumour immunity, DOI `10.1038/s41586-023-06575-7`.

Grounded hypothesis:

> PTPN2/PTPN1 act as brakes on JAK-STAT interferon signaling, so dual inhibition should amplify IFN response, antigen presentation, and NK/CD8 killing.

DAG2 child claims:

1. `mechanism_jak_stat_ifn_amplification`
   - Claim: Reduced PTPN2/PTPN1 phosphatase activity increases interferon-induced JAK-STAT signaling, including higher STAT1/STAT3 phosphorylation and interferon-stimulated gene transcription.
   - Truth condition: In a context-matched cell system, dual PTPN2/PTPN1 inhibition or loss causes a directional increase in IFN-triggered STAT phosphorylation and downstream ISG expression relative to matched controls.

2. `mechanism_antigen_presentation_upregulation`
   - Claim: Amplified interferon-JAK-STAT signaling after PTPN2/PTPN1 inhibition increases tumor-cell antigen-processing and MHC class I presentation machinery.
   - Truth condition: After PTPN2/PTPN1 inhibition in tumor cells, interferon-responsive antigen-presentation components such as HLA/MHC-I heavy chains, B2M, TAP1/2, or immunoproteasome genes increase in a STAT-dependent manner.

3. `mechanism_nk_visibility_or_susceptibility`
   - Claim: PTPN2/PTPN1 inhibition can make tumor cells more susceptible to NK-cell attack by increasing interferon-linked immune-visibility or cytotoxic-response programs.
   - Truth condition: Tumor cells with reduced PTPN2/PTPN1 activity show increased expression of NK-relevant activating ligands or increased sensitivity to NK-derived cytotoxic mechanisms under interferon-conditioned settings.

4. `mechanism_cd8_killing_gain`
   - Claim: Tumor-cell interferon and antigen-presentation changes caused by PTPN2/PTPN1 inhibition increase CD8 T-cell recognition and cytotoxic killing.
   - Truth condition: With antigen-specific or tumor-reactive CD8 T cells present, tumor cells lacking or inhibited for PTPN2/PTPN1 undergo greater T-cell activation-dependent killing than matched control tumor cells, alongside increased tumor-cell antigen-presentation state.

5. `mechanism_dual_paralog_additivity_or_synergy`
   - Claim: Concurrent inhibition of both PTPN2 and PTPN1 produces a larger increase in interferon signaling and immune-visibility programs than inhibition of either phosphatase alone.
   - Truth condition: Across matched perturbations, dual PTPN2/PTPN1 inhibition yields a stronger increase in IFN-JAK-STAT readouts and downstream antigen-presentation or immune-killing phenotypes than single-gene inhibition.

Assessment: excellent DAG2. It is precise, directly aligned with the local Nature paper, and includes the important dual-paralog truth condition instead of treating PTPN2 and PTPN1 as interchangeable.

## Hypothesis 4: Tumor-Intrinsic Beta-Catenin -> DC Recruitment -> T-Cell Exclusion

Input one-liner:

> Tumor-intrinsic beta-catenin signaling blocks dendritic-cell recruitment, causing T-cell exclusion; beta-catenin inhibition should restore DC recruitment and CD8 entry.

References supplied to Step0:

- `s41580-024-00768-2.pdf`: single-cell/spatial transcriptomics review.
- `cellTree.pdf`: reference cell tree / cell taxonomy perspective.
- `cellstates.pdf`: holistic cell-state framework.

Grounded hypothesis:

> Tumor-intrinsic beta-catenin signaling blocks dendritic-cell recruitment, causing T-cell exclusion; beta-catenin inhibition should restore DC recruitment and CD8 entry.

DAG2 child claims:

1. `mechanism_tumor_chemokine_suppression`
   - Claim: Tumor-cell-intrinsic CTNNB1 activation decreases expression or secretion of chemokines required for dendritic-cell recruitment into the tumor microenvironment.
   - Truth condition: In malignant tumor cells, increased CTNNB1 signaling is accompanied by reduced abundance of one or more dendritic-cell-recruiting chemokines at the RNA or protein level relative to matched lower-CTNNB1 states.

2. `mechanism_dc_recruitment_dependency`
   - Claim: Reduced tumor-derived dendritic-cell-recruiting chemokine signals lower intratumoral dendritic-cell recruitment or abundance.
   - Truth condition: Across matched tumors or perturbation states, lower levels of tumor-derived dendritic-cell-recruiting chemokines are associated with fewer recruited intratumoral dendritic cells.

3. `mechanism_dc_to_cd8_link`
   - Claim: Reduced intratumoral dendritic-cell abundance or presence leads to reduced CD8 T-cell priming, recruitment, or entry into tumors.
   - Truth condition: Tumors with fewer intratumoral dendritic cells show lower intratumoral CD8 T-cell abundance or exclusion of CD8 T cells from the tumor bed in the same biological context.

4. `mechanism_tumor_intrinsic_cd8_exclusion`
   - Claim: High tumor-cell-intrinsic CTNNB1 signaling is associated with a T-cell-excluded tumor microenvironment characterized by reduced intratumoral CD8 T-cell infiltration.
   - Truth condition: When CTNNB1 signaling is higher in malignant cells, intratumoral CD8 T-cell density or penetration into the tumor parenchyma is lower than in matched lower-CTNNB1 tumors.

5. `mechanism_chemokine_restoration_on_inhibition`
   - Claim: Inhibiting tumor-cell CTNNB1 signaling restores expression or secretion of dendritic-cell-recruiting chemokines.
   - Truth condition: After CTNNB1 pathway inhibition in tumor cells, dendritic-cell-recruiting chemokine RNA or protein levels increase relative to matched pre-inhibition or control conditions.

6. `mechanism_immune_infiltration_restoration_on_inhibition`
   - Claim: Inhibiting tumor-cell CTNNB1 signaling increases intratumoral dendritic-cell recruitment and permits CD8 T-cell entry into tumors.
   - Truth condition: In a context where tumor-cell CTNNB1 signaling is reduced, intratumoral dendritic-cell abundance increases and CD8 T cells show increased infiltration into the tumor bed relative to matched controls.

Assessment: excellent DAG2 decomposition, especially because it does not skip the chemokine mediator. Local PDF support is mostly methodological/contextual, so L1 should still retrieve direct WNT/CTNNB1 immune-exclusion papers.

## Hypothesis 5: CD8 IFNg -> Tumor Ferroptosis -> Immune Killing

Input one-liner:

> CD8 T-cell IFNg signaling induces tumor-cell ferroptosis by suppressing lipid antioxidant defenses; increasing tumor ferroptosis sensitivity should improve immune-mediated tumor killing.

References supplied to Step0:

- `s41580-024-00768-2.pdf`: single-cell/spatial transcriptomics review.
- `cellstates.pdf`: holistic cell-state framework.

Grounded hypothesis:

> CD8 T-cell IFNg signaling induces tumor-cell ferroptosis by suppressing lipid antioxidant defenses; increasing tumor ferroptosis sensitivity should improve immune-mediated tumor killing.

DAG2 child claims:

1. `mechanism_tumor_ifng_signal_transduction`
   - Claim: Tumor-cell exposure to IFNg activates tumor-intrinsic IFNGR-JAK-STAT1 signaling.
   - Truth condition: In tumor cells within the relevant context, IFNg increases proximal IFNGR pathway activity such as STAT1 phosphorylation or induction of canonical IFNg-response genes, and blocking IFNGR/JAK/STAT1 prevents this response.

2. `mechanism_system_xc_repression`
   - Claim: IFNg signaling represses the tumor-cell cystine import system xCT/SLC7A11-SLC3A2.
   - Truth condition: After IFNg signaling in tumor cells, SLC7A11 and/or SLC3A2 expression or transporter activity decreases, and this decrease depends on intact tumor-cell IFNGR pathway signaling.

3. `mechanism_glutathione_defense_loss`
   - Claim: Repression of tumor-cell cystine import lowers glutathione-dependent lipid peroxide detoxification capacity.
   - Truth condition: When tumor-cell system xc- activity is reduced, intracellular cysteine/cystine availability and glutathione pools fall, with corresponding loss of glutathione-dependent protection against lipid peroxidation.

4. `mechanism_ferroptosis_execution`
   - Claim: Loss of tumor-cell lipid antioxidant defense causes accumulation of lipid peroxides and ferroptotic death.
   - Truth condition: In tumor cells, reduced lipid antioxidant defense increases lipid ROS or phospholipid peroxidation together with ferroptosis-consistent death, and this death is suppressed by ferroptosis inhibitors or lipid peroxide scavengers.

5. `mechanism_ifng_to_ferroptosis_causality`
   - Claim: A component of IFNg-induced tumor-cell killing is ferroptosis-dependent rather than solely apoptosis or growth arrest.
   - Truth condition: Under IFNg exposure in tumor cells or CD8 T-cell co-culture, ferroptosis blockade selectively reduces the IFNg-associated tumor-cell death phenotype while non-ferroptotic death markers alone do not fully explain the effect.

6. `mechanism_ferroptosis_sensitization_improves_immune_killing`
   - Claim: Increasing tumor-cell ferroptosis sensitivity enhances immune-mediated tumor killing in the presence of cytotoxic lymphocytes.
   - Truth condition: Tumor cells made more ferroptosis-sensitive show greater killing during CD8 T-cell or immune-competent tumor challenge, and this enhancement is reduced when ferroptosis is pharmacologically or genetically blocked.

Assessment: excellent DAG2. It added the important system xc-/SLC7A11 and glutathione-defense mechanistic bridge, which makes the hypothesis testable rather than just naming ferroptosis. Local PDF support is contextual, not direct primary proof, so direct ferroptosis/IFNg papers should be retrieved in the next Step0 literature pass.

## System-Level Conclusions

1. The LLM DAG2 compiler is necessary for this task. The deterministic fallback was useful for offline safety but was too coarse for several mechanisms.
2. With `GBD_STAGE0_REQUIRE_DAG2_LLM=1`, the system produced specific DAG2s for all five hypotheses.
3. The DAG2s are generalizable because specificity came from the hypothesis, local paper text, KG seed claims, and generic Stage0 context. There was no hardcoded hypothesis branch.
4. The system should keep fallback available only for tests and should fail loudly for scientific Step0 runs when the LLM DAG2 compiler is unavailable.
5. The next improvement is literature completeness: for four of the five hypotheses, the local PDF folder did not include the direct primary paper most likely to prove the claim. Step0 should retrieve those papers before known-evidence prepopulation and before L1 planning.
