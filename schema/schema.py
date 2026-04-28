"""Knowledge Graph Schema — DAG 2 entry layer (claims + study contract).

This is the public, partial schema for the **first layer of DAG 2** — the
data structures that DAG 1 emits and that DAG 2 consumes when it begins
proving a candidate claim. It contains:

  * Claim taxonomy            — ClaimType
  * Three orthogonal axes     — EvidenceStatus, PriorArtStatus,
                                ReviewStatus, PublicationStatus
  * Intake contract           — PhenotypeDefinition, ConfounderDeclaration,
                                ResearchQuestionContract
  * Candidate claim node      — CandidateNode + NodeTypeInClaim/NodeRoleInClaim
  * Wave-1 typed output       — StudyResult, ClaimUpdate, ProvingNodeResult

Not included (intentional):
  * Layer-1 entity primitives — see ``schema_private.py`` (gitignored) and
    ``entity_types.tsv`` / ``edge_types.tsv``.
  * Evidence layer (Layer 3)  — Dataset, Assay, StatisticalTest, ModelRun, …
  * Logic layer (Layer 4)     — SupportSet (AND/OR), ContradictionCase
  * Meta-analysis, wet-lab proposal, frontier operators, claim families —
    later proving waves and orchestration.

Mandatory rules a wave-1 implementation must respect:
  1. No node may emit a free-text conclusion without ≥1 StudyResult.
  2. No multi-study summary without pooled meta-analysis.
  3. No claim promotion without KG write-back.
  4. No verdict without a machine-readable L1–L7 coverage map.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════
# CLAIM TAXONOMY (Layer 2 — what DAG 2 proves)
# ═══════════════════════════════════════════════════════════════════════════

class ClaimType(str, Enum):
    """All claim types DAG 2 can be asked to prove."""
    # Essentiality
    OBSERVED_ESSENTIALITY = "ObservedEssentialityClaim"
    PREDICTED_ESSENTIALITY = "PredictedEssentialityClaim"
    CONDITIONAL_SYNTHETIC_LETHALITY = "ConditionalSyntheticLethalityClaim"

    # Perturbation
    PERTURBATION_SIGNATURE = "PerturbationSignatureClaim"       # LINCS KGene/OGene
    CRISPR_PHENOTYPE = "CRISPRPhenotypeClaim"                   # KO → phenotype

    # Regulatory
    TF_REGULATORY = "TFRegulatoryClaim"                         # Taiji TF→target
    TF_ACTIVITY_STATE = "TFActivityStateClaim"                  # Taiji PageRank
    UPSTREAM_REGULATOR = "UpstreamRegulatorClaim"

    # Immune
    IMMUNE_STATE_DEPENDENCY = "ImmuneStateDependencyClaim"      # gene essential in state
    IMMUNE_STATE_MARKER = "ImmuneStateMarkerClaim"              # gene marks state
    STATE_INTERVENTION_WINDOW = "StateInterventionWindowClaim"  # therapeutic window

    # Expression / localization
    DIFFERENTIAL_EXPRESSION = "DifferentialExpressionClaim"
    RNA_PROTEIN_DISCORDANCE = "RNAProteinDiscordanceClaim"
    PROTEIN_LOCALIZATION_CHANGE = "ProteinLocalizationChangeClaim"
    LINEAGE_RESTRICTION = "LineageRestrictionClaim"

    # Genomic
    SOMATIC_MUTATION = "SomaticMutationClaim"
    MUTATION_PROTEIN_ASSOCIATION = "MutationProteinAssociationClaim"

    # Multi-omics (CPTAC patient tumors)
    PROTEOMICS_ABUNDANCE = "ProteomicsAbundanceClaim"
    PHOSPHORYLATION = "PhosphorylationClaim"
    ACETYLATION = "AcetylationClaim"
    UBIQUITYLATION = "UbiquitylationClaim"
    PTM_STOICHIOMETRY = "PTMStoichiometryClaim"

    # Inferred activity
    PATHWAY_ACTIVITY = "PathwayActivityClaim"
    KINASE_ACTIVITY = "KinaseActivityClaim"
    SIGNATURE_ACTIVITY = "SignatureActivityClaim"
    COMPLEX_DYSREGULATION = "ComplexDysregulationClaim"

    # Advanced dependency (DepMap)
    SELECTIVE_DEPENDENCY = "SelectiveDependencyClaim"
    BUFFERING = "BufferingClaim"
    MUTATION_COOCCURRENCE = "MutationCoOccurrenceClaim"
    MUTATION_HOTSPOT = "MutationHotspotClaim"
    BIMODALITY = "BimodalityExpressionClaim"

    # Correlation / association
    PATHWAY_CORRELATION = "PathwayCorrelationClaim"
    GENE_GENE_CORRELATION = "GeneGeneCorrelationClaim"
    CONFOUNDER_ADJUSTED_ASSOCIATION = "ConfounderAdjustedAssociationClaim"

    # Clinical
    THERAPY_RESPONSE = "TherapyResponseClaim"
    BIOMARKER = "BiomarkerClaim"
    PROGNOSTIC_MARKER = "PrognosticMarkerClaim"

    # Compound
    COMPOUND_SENSITIVITY = "CompoundSensitivityClaim"
    DRUG_TARGET = "DrugTargetClaim"

    # Meta
    CROSS_MODALITY_AGREEMENT = "CrossModalityAgreementClaim"
    PATHWAY_REDUNDANCY_HYPOTHESIS = "PathwayRedundancyHypothesis"
    CONTRADICTION = "ContradictionClaim"
    NOVELTY_ASSESSMENT = "NoveltyAssessmentClaim"

    # Composite-claim decomposition: each step is its own first-class claim
    # with parent_claim_id pointing at the composite.
    CAUSAL_CHAIN_LINK = "CausalChainLinkClaim"


# ═══════════════════════════════════════════════════════════════════════════
# THREE ORTHOGONAL CLAIM AXES
#
# Biology requires separating evidence maturity, novelty, and review state.
# A claim can be replicated + plausibly_novel + clean, or
# causal + canonical + clean (successful replication of known biology).
# ═══════════════════════════════════════════════════════════════════════════

class EvidenceStatus(str, Enum):
    """How mature is the evidence supporting this claim?

    Promotion rules (hard gates enforced by DAG 2):
      draft → observed:                  ≥1 Wave 1 association test passed
      observed → replicated:             ≥2 independent datasets, consistent direction
      replicated → causal:               ≥1 perturbation result (LOF or GOF)
      causal → mechanistic:              orthogonal phenotype confirms mechanism
      mechanistic → externally_supported: functional consequence demonstrated
    """
    DRAFT = "draft"
    OBSERVED = "observed"
    REPLICATED = "replicated"
    CAUSAL = "causal"
    MECHANISTIC = "mechanistic"
    EXTERNALLY_SUPPORTED = "externally_supported"


class PriorArtStatus(str, Enum):
    """What does the literature say about this claim?

    Adjudicated by DAG 1 prior-art review before DAG 2 invests compute.
    """
    UNSEARCHED = "unsearched"
    CANONICAL = "canonical"                  # textbook — skip unless benchmarking
    RELATED_PRIOR_ART = "related_prior_art"  # similar finding published, not exact
    CONTEXT_EXTENSION = "context_extension"  # known gene, new context (worth pursuing)
    EVIDENCE_UPGRADE = "evidence_upgrade"    # known association, need causation
    PLAUSIBLY_NOVEL = "plausibly_novel"
    AMBIGUOUS = "ambiguous"                  # unclear, flag for human review


class ReviewStatus(str, Enum):
    """Is there an active issue with this claim?"""
    CLEAN = "clean"
    IN_REVIEW = "in_review"
    CONTRADICTED = "contradicted"            # open contradiction case
    SUPERSEDED = "superseded"                # replaced by newer claim
    NEEDS_EXPERIMENT = "needs_experiment"    # public data insufficient → wet-lab


class PublicationStatus(str, Enum):
    """Has the claim been published in peer-reviewed literature?"""
    UNPUBLISHED = "unpublished"              # not found in literature (NOVEL)
    PARTIALLY_PUBLISHED = "partially_published"
    PUBLISHED = "published"
    PREPRINT = "preprint"
    TEXTBOOK = "textbook"                    # established knowledge — don't pursue
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════════════════
# INTAKE CONTRACT — scopes what DAG 1 emits and what DAG 2 will accept
# ═══════════════════════════════════════════════════════════════════════════

class PhenotypeType(str, Enum):
    """Machine-readable phenotype classification for contracts."""
    BINARY_COHORT = "binary_cohort"              # discordant-low vs concordant-high
    CONTINUOUS_SCORE = "continuous_score"        # IFN score, protein abundance
    RESIDUALIZED_SCORE = "residualized_score"    # HLA protein residual after RNA adj
    TRAJECTORY_STATE = "trajectory_state"        # exhausted vs memory
    COMPOSITIONAL = "compositional"              # cell-type fraction
    OUTCOME = "outcome"                          # survival, treatment response


@dataclass
class PhenotypeDefinition:
    """Machine-readable phenotype specification.

    Every claim must define what phenotype it's about in a way that
    can be computed from data, not described in prose.
    """
    phenotype_id: str
    name: str
    phenotype_type: PhenotypeType
    genes: list[str] = field(default_factory=list)
    formula: str = ""                              # residualization or scoring formula
    normalization: str = ""                        # "log2(TPM+1)", "z-score", …
    thresholds: dict[str, float] = field(default_factory=dict)
    cohort_inclusion: list[str] = field(default_factory=list)
    cohort_exclusion: list[str] = field(default_factory=list)


@dataclass
class ConfounderDeclaration:
    """Confounders that must be adjusted for before claiming association."""
    confounder_id: str
    name: str                   # "tumor_purity", "covariate_score", "cell_cycle"
    measurement: str = ""
    adjustment_method: str = "" # "partial_correlation", "regression_covariate", "stratification"
    mandatory: bool = True      # always-adjust vs. optional enrichment


@dataclass
class ResearchQuestionContract:
    """Scopes what DAG 1 is allowed to look for.

    Without this, candidate-claim suggestion drifts toward hub genes
    and generic biology. The phenotype + context + scope triple
    anchors KG traversal.
    """
    question_id: str
    phenotype: PhenotypeDefinition
    context: list[str] = field(default_factory=list)        # ["solid tumors", "melanoma"]
    scope: str = ""                                          # "post-translational regulators"
    novelty_criterion: str = ""                              # "not canonical in Janeway 10th ed"
    acceptable_evidence_layers: list[str] = field(default_factory=list)
    forbidden_proxies: list[str] = field(default_factory=list)
    anchor_genes: list[str] = field(default_factory=list)
    excluded_claims: list[str] = field(default_factory=list)
    confounders: list[ConfounderDeclaration] = field(default_factory=list)
    minimum_independent_datasets: int = 2
    minimum_total_samples: int = 50

    # ── Exploration policy (controls DAG 1 iteration) ──
    exploration_modes: list[str] = field(default_factory=lambda: [
        "unexplained_module", "bridge_node", "contradiction",
        "modality_discordance", "context_transfer", "anti_hub",
    ])
    frontier_quotas: dict[str, int] = field(default_factory=lambda: {
        "contradiction": 3,
        "modality_discordance": 3,
        "bridge_node": 3,
    })
    diversity_constraints: dict[str, float] = field(default_factory=lambda: {
        "max_per_pathway_family": 2,
        "max_per_gene_family": 1,
    })
    saturation_rule: str = "stop when <10% new claim families in last 3 rounds"
    max_hops_from_anchor: int = 3


# ═══════════════════════════════════════════════════════════════════════════
# CANDIDATE CLAIM — the atomic unit DAG 1 outputs and DAG 2 proves
# ═══════════════════════════════════════════════════════════════════════════

class NodeTypeInClaim(str, Enum):
    """Type of an entity participating in a CandidateClaim.

    Mirrors the Layer-1 entity types but is duplicated here so the DAG-2
    contract does not import the full core schema. Stay in sync.
    """
    GENE = "gene"
    PROTEIN = "protein"
    PROTEIN_COMPLEX = "protein_complex"
    PATHWAY = "pathway"
    CELL_POPULATION = "cell_population"
    METABOLITE = "metabolite"
    EPIGENETIC_MARK = "epigenetic_mark"
    IMMUNE_STATE = "immune_state"


class NodeRoleInClaim(str, Enum):
    """Role a node plays inside a CandidateClaim."""
    PRIMARY = "primary"                          # the node the claim is fundamentally about
    MEDIATOR = "mediator"                        # required intermediate
    UPSTREAM_REGULATOR = "upstream_regulator"    # drives the primary node
    DOWNSTREAM_TARGET = "downstream_target"      # read-out of the primary node
    PARTNER = "partner"                          # interaction partner / complex member
    SUBSTRATE = "substrate"                      # enzymatic substrate
    CONTEXT_MARKER = "context_marker"            # defines a conditional state


@dataclass
class CandidateNode:
    """One entity that participates in a CandidateClaim.

    A claim can name multiple involved entities of mixed types
    (gene, complex, pathway, cell population, mark, immune state, …).

    Constraint: exactly one CandidateNode per claim has role==PRIMARY.
    """
    node_id: str                                  # HGNC symbol or KG entity_id
    node_type: NodeTypeInClaim = NodeTypeInClaim.GENE
    role_in_claim: NodeRoleInClaim = NodeRoleInClaim.PRIMARY
    display_name: str = ""
    required: bool = True                          # load-bearing for claim truth?
    compartment: str = ""                          # tumor_intrinsic | immune_effector | myeloid | …
    notes: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# WAVE-1 OUTPUT CONTRACT — typed result every DAG 2 node must emit
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class StudyResult:
    """Structured output from a single study within a proving node.

    Every node emits one or more of these. Negative and null results
    are stored — claim status is derived from the result graph,
    not written as a side effect of one positive analysis.
    """
    question_id: str
    study_id: str
    evidence_family: str              # "in_vitro_association", "tumor_multiomics", …
    cohort_name: str = ""
    context: dict[str, str] = field(default_factory=dict)
    assay: str = ""                   # "expression_correlation", "crispr_ko", "meta_analysis"
    comparison: str = ""              # "discordant_low vs concordant_high"
    model_type: str = ""              # "welch_t", "linear_regression", "deseq2", …
    covariates: list[str] = field(default_factory=list)
    n: int = 0
    effect_size: float | None = None
    standard_error: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    p_value: float | None = None
    q_value: float | None = None
    direction: str = ""               # "positive", "negative", "enriched", …
    classification: str = ""          # "support", "null", "contradict"
    quality_flags: list[str] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)


@dataclass
class ClaimUpdate:
    """Proposed claim state change from a proving node."""
    claim_id: str | None = None
    claim_text: str = ""
    question_id: str = ""
    proposed_evidence_status: str = ""   # an EvidenceStatus value
    proposed_prior_art_status: str | None = None
    contradiction_targets: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)  # study_result IDs
    reasoning: str = ""


@dataclass
class ProvingNodeResult:
    """Standard output from every DAG 2 node.

    Rule 1: No node may emit a free-text conclusion without ≥1 StudyResult.
    Rule 2: No multi-study summary without pooled meta-analysis.
    Rule 3: No claim promotion without KG write-back.
    """
    node_id: str
    wave: int                          # 1–4
    question_id: str
    passed: bool
    blocking: bool                     # is this a hard-gate dependency?
    study_results: list[StudyResult] = field(default_factory=list)
    claim_updates: list[ClaimUpdate] = field(default_factory=list)
    summary: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
