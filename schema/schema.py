"""Knowledge Graph Schema — complete ontology for cancer immunology.

This is the full data model. Four layers, each with explicit types.
The graph is stored in SQLite (entities + claims + evidence + logic)
with raw matrices in Parquet/DuckDB.

Design principles:
  - Stable facts are backbone edges (Gene-encodes-Protein)
  - Context-dependent assertions are claim nodes with participants
  - Every claim has evidence with 4D uncertainty
  - AND/OR logic via SupportSets
  - Contradictions are first-class objects
  - The agent adds to the graph every time it runs
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, InitVar
from enum import Enum
from typing import Any, ClassVar, Literal


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 1: CORE ENTITIES
# ═══════════════════════════════════════════════════════════════════════════

class EntityType(str, Enum):
    """All entity types in the knowledge graph."""
    # Molecular
    GENE = "Gene"
    PROTEIN = "Protein"
    VARIANT = "Variant"           # HGVS or gene-level mutation event

    # Functional
    PATHWAY = "Pathway"
    BIOLOGICAL_PROCESS = "BiologicalProcess"
    MOLECULAR_FUNCTION = "MolecularFunction"
    CELLULAR_COMPONENT = "CellularComponent"

    # Biological context
    CELL_TYPE = "CellType"
    IMMUNE_FUNCTIONAL_STATE = "ImmuneFunctionalState"  # naive, effector, exhausted, memory, TRM
    TME_COMPARTMENT = "TMECompartment"  # tumor_intrinsic, t_cell, myeloid, stromal
    ANATOMY = "Anatomy"           # tissue/organ

    # Disease & therapy
    CANCER_TYPE = "CancerType"    # OncoTree-like, maps to Disease
    DISEASE = "Disease"
    THERAPY_REGIMEN = "TherapyRegimen"  # anti-PD1, anti-CTLA4, combo, CAR-T
    COMPOUND = "Compound"

    # Experimental
    CELL_LINE = "CellLine"        # DepMap ID
    STUDY = "Study"               # GEO accession, CPTAC study, publication
    COHORT = "Cohort"             # patient cohort within a study

    # Structural
    PROTEIN_DOMAIN = "ProteinDomain"
    PROTEIN_FAMILY = "ProteinFamily"
    EC = "EC"                     # enzyme commission number
    REACTION = "Reaction"

    # Genomic
    NEOANTIGEN = "Neoantigen"     # HLA-peptide binding prediction
    HLA_ALLELE = "HLAAllele"


@dataclass
class Entity:
    """A node in the knowledge graph."""
    entity_id: str               # canonical ID (HGNC symbol, UniProt accession, etc.)
    entity_type: EntityType
    name: str                    # human-readable name
    aliases: list[str] = field(default_factory=list)  # alternative IDs
    properties: dict[str, Any] = field(default_factory=dict)

    # Cross-references (the xref table)
    xrefs: dict[str, str] = field(default_factory=dict)
    # e.g., {"entrez": "1499", "uniprot": "P35222", "hgnc": "2514", "ensembl": "ENSG00000168036"}


# ═══════════════════════════════════════════════════════════════════════════
# BACKBONE EDGES (stable biological facts)
# ═══════════════════════════════════════════════════════════════════════════

class BackboneEdgeType(str, Enum):
    """Stable edges that don't need claim reification."""
    # Gene → Protein
    GENE_ENCODES_PROTEIN = "Gene-encodes-Protein"
    # Gene → Function
    GENE_PARTICIPATES_PATHWAY = "Gene-participates-Pathway"
    GENE_PARTICIPATES_BIOLOGICAL_PROCESS = "Gene-participates-BiologicalProcess"
    GENE_PARTICIPATES_MOLECULAR_FUNCTION = "Gene-participates-MolecularFunction"
    GENE_PARTICIPATES_CELLULAR_COMPONENT = "Gene-participates-CellularComponent"
    # Protein → Protein
    PROTEIN_INTERACTS_PROTEIN = "Protein-interacts-Protein"
    # Protein → Function
    PROTEIN_LOCALIZES_CELLULAR_COMPONENT = "Protein-localizes-CellularComponent"
    PROTEIN_HAS_DOMAIN = "Protein-has-ProteinDomain"
    PROTEIN_REGULATES_GENE = "Protein-regulates-Gene"  # TFLink TF→target
    # Gene → Expression
    GENE_EXPRESSED_IN_CELL_TYPE = "Gene-expressedIN-CellType"
    GENE_EXPRESSED_IN_ANATOMY = "Gene-expressedIN-Anatomy"
    # Disease
    DISEASE_ASSOCIATES_GENE = "Disease-associates-Gene"
    DISEASE_LOCALIZES_ANATOMY = "Disease-localizes-Anatomy"
    # Compound
    COMPOUND_BINDS_PROTEIN = "Compound-binds-Protein"
    COMPOUND_TREATS_DISEASE = "Compound-treats-Disease"
    # Hierarchy
    PATHWAY_CONTAINS_PATHWAY = "Pathway-contains-Pathway"
    DISEASE_CONTAINS_DISEASE = "Disease-contains-Disease"
    CELL_TYPE_ISA_CELL_TYPE = "CellType-isa-CellType"
    # Gene → Gene (stable from SPOKE)
    GENE_ENCODES_MIRNA = "Gene-encodes-MiRNA"
    # Perturbation (LINCS L1000)
    KGENE_REGULATES_GENE = "KGene-regulates-Gene"  # CRISPR KO → downstream effect
    KGENE_UPREGULATES_GENE = "KGene-upregulates-Gene"
    KGENE_DOWNREGULATES_GENE = "KGene-downregulates-Gene"
    # Tissue expression (HPA)
    ANATOMY_EXPRESSES_GENE = "Anatomy-expresses-Gene"  # reverse of Gene-expressedIN-Anatomy

    # ── REFERENCE GRAPH: stable curated edges ──
    # Pathway/complex membership (Reactome, KEGG, CORUM)
    MEMBER_OF_COMPLEX = "Protein-memberOf-Complex"         # protein → complex
    SUBUNIT_OF = "Protein-subunitOf-Complex"               # with stoichiometry
    # Enzymatic relationships (PhosphoSitePlus, iPTMnet)
    PHOSPHORYLATES = "Kinase-phosphorylates-Substrate"     # kinase → substrate (with site)
    ACETYLATES = "Enzyme-acetylates-Substrate"
    UBIQUITINATES = "E3Ligase-ubiquitinates-Substrate"
    DEPHOSPHORYLATES = "Phosphatase-dephosphorylates-Substrate"
    # Signaling (Reactome, SignaLink)
    ACTIVATES = "Gene-activates-Gene"                      # upstream → downstream
    INHIBITS = "Gene-inhibits-Gene"                        # upstream ⊣ downstream
    LIGAND_FOR = "Protein-ligandFor-Receptor"
    RECEPTOR_FOR = "Protein-receptorFor-Ligand"
    # Transcription (ENCODE, CollecTRI)
    TF_BINDS_PROMOTER = "TF-bindsPromoter-Gene"            # ChIP-seq validated
    ENHANCER_REGULATES = "Enhancer-regulates-Gene"
    # Synthetic lethality (DepMap)
    GENE_SYNTHETICLETHAL_GENE = "Gene-syntheticLethal-Gene"
    # Immune-specific
    TME_COMPARTMENT_SIGNATURE_GENE = "TME-signatureGene-Gene"
    IMMUNE_FUNCTIONAL_STATE_MARKED_BY_GENE = "ImmuneState-markedBy-Gene"


@dataclass
class BackboneEdge:
    """A stable biological fact edge in the REFERENCE GRAPH.

    Reference edges are curated, versioned, and slow-moving. They represent
    biological FACTS (pathway membership, enzymatic substrates, physical
    interactions) rather than context-dependent observations.
    """
    edge_id: str
    edge_type: BackboneEdgeType
    source_id: str               # entity ID
    target_id: str               # entity ID
    properties: dict[str, Any] = field(default_factory=dict)
    source_db: str = ""          # e.g., "UniProt", "Reactome", "STRING"
    confidence: float = 1.0      # 0-1


# ═══════════════════════════════════════════════════════════════════════════
# EVIDENCE TIER — curated vs observed vs inferred
# ═══════════════════════════════════════════════════════════════════════════

class EvidenceTier(str, Enum):
    """Three-tier evidence classification for the EVIDENCE GRAPH.

    Separates:
    - CURATED: manually reviewed, gold-standard databases (Reactome,
      PhosphoSitePlus), or publication authority ≥ "well_supported"
    - OBSERVED: directly measured from data (CPTAC, DepMap), n ≥ threshold,
      p < threshold, direction consistent across replicates
    - INFERRED: computationally derived — LASSO predictions, PROGENy pathway
      activity, KSEA kinase activity, ssGSEA signatures, model outputs
    """
    CURATED = "curated"
    OBSERVED = "observed"
    INFERRED = "inferred"


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 2: CLAIMS — the EVIDENCE GRAPH (context-dependent assertions)
# ═══════════════════════════════════════════════════════════════════════════

class ClaimType(str, Enum):
    """All claim types in the knowledge graph."""
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
    RNA_PROTEIN_DISCORDANCE = "RNAProteinDiscordanceClaim"      # post-translational
    PROTEIN_LOCALIZATION_CHANGE = "ProteinLocalizationChangeClaim"  # trafficking
    LINEAGE_RESTRICTION = "LineageRestrictionClaim"

    # Genomic
    SOMATIC_MUTATION = "SomaticMutationClaim"                    # mutation frequency per gene × context
    MUTATION_PROTEIN_ASSOCIATION = "MutationProteinAssociationClaim"  # mutation → protein/phospho change

    # Multi-omics (CPTAC patient tumors)
    PROTEOMICS_ABUNDANCE = "ProteomicsAbundanceClaim"            # protein abundance per gene × cancer
    PHOSPHORYLATION = "PhosphorylationClaim"                     # phospho-site levels per cancer
    ACETYLATION = "AcetylationClaim"                             # protein acetylation per cancer
    UBIQUITYLATION = "UbiquitylationClaim"                       # protein ubiquitylation per cancer
    PTM_STOICHIOMETRY = "PTMStoichiometryClaim"                  # phospho/acetyl normalized by total protein

    # Inferred activity (EVIDENCE GRAPH — inferred tier)
    PATHWAY_ACTIVITY = "PathwayActivityClaim"                    # PROGENy/ssGSEA inferred pathway activity
    KINASE_ACTIVITY = "KinaseActivityClaim"                      # KSEA/VIPER inferred kinase activity
    SIGNATURE_ACTIVITY = "SignatureActivityClaim"                # EMT/IFN/exhaustion signature scores
    COMPLEX_DYSREGULATION = "ComplexDysregulationClaim"          # stoichiometric imbalance in complexes

    # Advanced dependency (DepMap)
    SELECTIVE_DEPENDENCY = "SelectiveDependencyClaim"            # essential ONLY in specific molecular context
    BUFFERING = "BufferingClaim"                                 # gene B rescues loss of gene A
    MUTATION_COOCCURRENCE = "MutationCoOccurrenceClaim"          # mutual exclusivity or co-occurrence
    MUTATION_HOTSPOT = "MutationHotspotClaim"                    # domain/site-level recurrent mutation
    BIMODALITY = "BimodalityExpressionClaim"                     # bimodal expression distribution

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
    CONTRADICTION = "ContradictionClaim"                         # first-class contradiction
    NOVELTY_ASSESSMENT = "NoveltyAssessmentClaim"

    # Composite-claim decomposition: each step in a CausalChain is its
    # own first-class claim with parent_claim_id pointing at the composite.
    # Lets sibling sbatches lock supported links and surgically retest only
    # the under-determined or contradicted ones (see hypothesis_refinement).
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

    Promotion rules (hard gates):
      draft → observed:     ≥1 Wave 1 association test passed
      observed → replicated: ≥2 independent datasets with consistent direction
      replicated → causal:   ≥1 perturbation result (LOF or GOF)
      causal → mechanistic:  orthogonal phenotype confirms mechanism
      mechanistic → externally_supported: functional consequence demonstrated
    """
    DRAFT = "draft"                          # hypothesis exists, no data yet
    OBSERVED = "observed"                    # measured in single study/modality
    REPLICATED = "replicated"                # reproduced in ≥2 independent datasets
    CAUSAL = "causal"                        # supported by perturbation (LOF or GOF)
    MECHANISTIC = "mechanistic"              # orthogonal phenotype confirms mechanism
    EXTERNALLY_SUPPORTED = "externally_supported"  # functional consequence demonstrated


class PriorArtStatus(str, Enum):
    """What does the literature say about this claim?

    Adjudicated by DAG 1 prior-art review before DAG 2 invests compute.
    """
    UNSEARCHED = "unsearched"                # PubMed not yet checked
    CANONICAL = "canonical"                  # textbook knowledge — skip unless benchmarking
    RELATED_PRIOR_ART = "related_prior_art"  # similar finding published, not exact
    CONTEXT_EXTENSION = "context_extension"  # known gene, new context (worth pursuing)
    EVIDENCE_UPGRADE = "evidence_upgrade"    # known association, need causation
    PLAUSIBLY_NOVEL = "plausibly_novel"       # not found in literature
    AMBIGUOUS = "ambiguous"                  # unclear, flag for human review


class ReviewStatus(str, Enum):
    """Is there an active issue with this claim?"""
    CLEAN = "clean"                          # no outstanding issues
    IN_REVIEW = "in_review"                  # under investigation
    CONTRADICTED = "contradicted"            # open contradiction case
    SUPERSEDED = "superseded"                # replaced by newer claim
    NEEDS_EXPERIMENT = "needs_experiment"    # public data insufficient, propose wet-lab


class PublicationStatus(str, Enum):
    """Whether a claim has been published in peer-reviewed literature.

    This is the novelty dimension — the KG can identify findings that
    are supported by data but not yet published, making them candidates
    for new research or publications.
    """
    UNPUBLISHED = "unpublished"           # not found in literature (NOVEL)
    PARTIALLY_PUBLISHED = "partially_published"  # related work exists but not this specific finding
    PUBLISHED = "published"               # directly reported in peer-reviewed paper
    PREPRINT = "preprint"                 # on bioRxiv/medRxiv but not peer-reviewed
    TEXTBOOK = "textbook"                 # established knowledge (don't pursue)
    UNKNOWN = "unknown"                   # literature search not yet performed


# ═══════════════════════════════════════════════════════════════════════════
# INTAKE CONTRACT — scopes what DAG 1 is allowed to look for
# ═══════════════════════════════════════════════════════════════════════════

class PhenotypeType(str, Enum):
    """Machine-readable phenotype classification for contracts."""
    BINARY_COHORT = "binary_cohort"              # e.g., discordant-low vs concordant-high
    CONTINUOUS_SCORE = "continuous_score"          # e.g., IFN score, protein abundance
    RESIDUALIZED_SCORE = "residualized_score"      # e.g., HLA protein residual after RNA adj
    TRAJECTORY_STATE = "trajectory_state"           # e.g., exhausted vs memory
    COMPOSITIONAL = "compositional"                # e.g., cell-type fraction
    OUTCOME = "outcome"                            # e.g., survival, treatment response


@dataclass
class PhenotypeDefinition:
    """Machine-readable phenotype specification.

    Every claim must define what phenotype it's about in a way that
    can be computed from data, not described in prose.
    """
    phenotype_id: str
    name: str                                     # descriptive name of the phenotype
    phenotype_type: PhenotypeType
    genes: list[str] = field(default_factory=list)  # genes defining the phenotype
    formula: str = ""                              # residualization or scoring formula
    normalization: str = ""                        # "log2(TPM+1)", "z-score", etc.
    thresholds: dict[str, float] = field(default_factory=dict)  # cutoffs for binary
    cohort_inclusion: list[str] = field(default_factory=list)
    cohort_exclusion: list[str] = field(default_factory=list)


@dataclass
class ConfounderDeclaration:
    """Confounders that must be adjusted for before claiming association."""
    confounder_id: str
    name: str                   # "tumor_purity", "covariate_score", "cell_cycle"
    measurement: str = ""       # how to measure it
    adjustment_method: str = "" # "partial_correlation", "regression_covariate", "stratification"
    mandatory: bool = True      # must always adjust, vs. optional enrichment


@dataclass
class ResearchQuestionContract:
    """Scopes what DAG 1 is allowed to look for.

    Without this, suggest_candidate_claims() drifts toward hub genes
    and generic biology. The phenotype + context + scope triple
    anchors KG traversal.
    """
    question_id: str
    phenotype: PhenotypeDefinition
    context: list[str] = field(default_factory=list)  # ["solid tumors", "melanoma", "kidney"]
    scope: str = ""                                    # "post-translational regulators"
    novelty_criterion: str = ""                        # "not canonical in Janeway 10th ed"
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

    Mirrors claim_ontology.EntityCategory but lives here to avoid the
    Layer-1 schema importing from core. The two enums must stay in sync.
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
    CONTEXT_MARKER = "context_marker"            # defines a conditional state, not the claim


@dataclass
class CandidateNode:
    """One entity that participates in a CandidateClaim.

    Generalises the legacy single ``candidate_gene: str`` field so a claim
    can name multiple involved entities of mixed types (gene, complex,
    pathway, cell population, mark, immune state, …).

    Constraint: exactly one CandidateNode per claim has role==PRIMARY.
    """
    node_id: str                                  # HGNC for genes, KG entity_id otherwise
    node_type: NodeTypeInClaim = NodeTypeInClaim.GENE
    role_in_claim: NodeRoleInClaim = NodeRoleInClaim.PRIMARY
    display_name: str = ""
    required: bool = True                          # load-bearing for claim truth?
    compartment: str = ""                          # tumor_intrinsic | immune_effector | myeloid | …
    notes: str = ""



# ═══════════════════════════════════════════════════════════════════════════
# STUDY RESULT — typed output from every analysis node
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
    evidence_family: str              # "in_vitro_association", "tumor_multiomics", etc.
    cohort_name: str = ""
    context: dict[str, str] = field(default_factory=dict)
    assay: str = ""                   # "expression_correlation", "crispr_ko", "meta_analysis"
    comparison: str = ""              # "discordant_low vs concordant_high"
    model_type: str = ""              # "welch_t", "linear_regression", "deseq2", etc.
    covariates: list[str] = field(default_factory=list)
    n: int = 0
    effect_size: float | None = None
    standard_error: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    p_value: float | None = None
    q_value: float | None = None
    direction: str = ""               # "positive", "negative", "enriched", etc.
    classification: str = ""          # "support", "null", "contradict"
    quality_flags: list[str] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)


@dataclass
class ClaimUpdate:
    """Proposed claim state change from a proving node."""
    claim_id: str | None = None
    claim_text: str = ""
    question_id: str = ""
    proposed_evidence_status: str = ""   # EvidenceStatus value
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
    wave: int                          # 1-4
    question_id: str
    passed: bool
    blocking: bool                     # is this a hard-gate dependency?
    study_results: list[StudyResult] = field(default_factory=list)
    claim_updates: list[ClaimUpdate] = field(default_factory=list)
    summary: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# META-ANALYSIS OUTPUT — required when ≥2 studies answer the same question
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MetaAnalysisResult:
    """Standard meta-analysis output. Required by policy whenever
    multiple independent studies answer the same explicit question.
    """
    question_id: str
    pooled_effect_size: float
    ci_low: float
    ci_high: float
    p_value: float
    i_squared: float                   # heterogeneity
    tau_squared: float
    n_studies: int
    total_n: int
    support_count: int
    null_count: int
    contradict_count: int
    method: str = "DerSimonian_Laird"  # or "REML", "Paule_Mandel"
    subgroup_results: list[dict[str, Any]] = field(default_factory=list)
    direction_supports_claim: bool = False
    heterogeneity_explanation: str = ""
    contradiction_explanation: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# CONTRADICTION CASE — biology-native, not fail-stop
# ═══════════════════════════════════════════════════════════════════════════

class ContradictionClassification(str, Enum):
    """How to classify a biological contradiction."""
    ENTITY_MISMATCH = "entity_mismatch"       # different gene/protein isoform, naming
    ASSAY_MISMATCH = "assay_mismatch"         # different readout measuring different things
    CONTEXT_SPLIT = "context_split"           # true in context A, false in context B
    TRUE_FRONTIER = "true_frontier"           # genuine biological disagreement


class ContradictionResolution(str, Enum):
    """Status of contradiction resolution."""
    OPEN = "open"
    NARROWED = "narrowed"          # claim scope narrowed to resolve
    RESOLVED = "resolved"          # fully resolved
    HALTED = "halted"              # blocks escalation, cannot resolve


@dataclass
class ContradictionCase:
    """First-class contradiction with classification and resolution tracking.

    In biology, contradictions are often context splits, assay mismatches,
    or entity-resolution problems — not just logical errors.
    """
    case_id: str
    claim_a_id: str
    claim_b_id: str
    reason: str

    classification: ContradictionClassification = ContradictionClassification.TRUE_FRONTIER

    resolution: ContradictionResolution = ContradictionResolution.OPEN
    resolution_action: str = ""        # "narrowed claim A scope to kidney only"
    spawned_plans: list[str] = field(default_factory=list)

    # Resolution investigation
    lineage_specific: bool | None = None
    assay_specific: bool | None = None
    modality_mismatch: bool | None = None
    timepoint_dependent: bool | None = None
    quality_failure_in: str = ""       # which source has the quality issue

    created_at: str = ""
    created_by: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# BIOLOGICAL RESULT — typed outcome persisted after every analysis
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class BiologicalResult:
    """Typed outcome of a single analysis step.

    Claim evidence_status is DERIVED from the result graph,
    not written as a single-step side effect of one positive analysis.
    Negative and null results are stored.
    """
    result_id: str
    claim_id: str
    result_type: str              # "association", "replication", "perturbation", "functional"
    assay: str                    # "expression_correlation", "crispr_ko", "meta_analysis"
    provider: str                 # "in_vitro_association", "tumor_multiomics", etc.
    context: dict[str, str] = field(default_factory=dict)

    # Outcome (including negatives)
    outcome: str = ""             # "positive", "negative", "null", "data_available", "inconclusive"
    effect_direction: str = ""    # "negative_correlation", "enriched", "no_effect"
    effect_size: float = 0.0
    confidence_interval: tuple[float, float] = (0.0, 0.0)
    p_value: float | None = None  # None = no statistical test performed
    n: int = 0
    statistical_test_performed: bool = False  # explicit flag: was a real test run?

    # Evidence category — controls which VERIF hard constraints apply
    # "statistical_test": requires p-value, effect size, CI (default)
    # "frequency_observation": genomic mutation rates, CNV frequencies —
    #     no p-value required, uses biologically meaningful thresholds
    # "qualitative_finding": pathway membership, literature — no statistics
    evidence_category: str = "statistical_test"

    # Dependencies
    depends_on: list[str] = field(default_factory=list)  # result_ids
    validity_scope: str = ""      # "kidney RCC cell lines", "pan-cancer CPTAC"

    # Composite-claim decomposition: which CausalChainLink claim this
    # result targets. Empty string means the result is a root/whole-claim
    # test (e.g., entity-level existence). Stamped by the wave executor
    # from the orchestrator's TaskAssignment.target_link_id.
    target_link_id: str = ""

    # Metadata
    timestamp: str = ""
    agent_run_id: str = ""
    artifact_paths: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# WET-LAB PROPOSAL — literature-aware experiment suggestion
#
# Rule 5: No wet-lab proposal without a named public-data gap.
# The agent proposes experiments only when public evidence leaves a
# causal or mechanistic gap that matters to verdict.
# ═══════════════════════════════════════════════════════════════════════════

class PriorExperimentQuality(str, Enum):
    """Quality assessment of a prior published experiment."""
    ADEQUATE = "adequate"          # well-powered, correct controls, replicable
    POOR = "poor"                  # underpowered, missing controls, or single replicate
    PARTIAL = "partial"            # tested related question but not exact claim
    NOT_FOUND = "not_found"        # no prior experiment found in literature


@dataclass
class WetLabProposal:
    """A proposed experiment to close a specific evidence gap.

    Literature-aware: checks whether this exact experiment has been done,
    and if the prior execution was adequate.
    """
    proposal_id: str
    claim_id: str

    # What gap this fills
    unanswered_question: str           # exact question, not a theme
    why_public_data_insufficient: str  # named gap, not "more data needed"
    evidence_gap_level: int            # which proof level (4-7) this fills
    claim_state_if_successful: str     # what EvidenceStatus changes

    # Experiment design
    model_system: str = ""             # "A498 kidney RCC line", "C57BL/6 mice"
    perturbation: str = ""             # "CRISPR KO of TMEM127 (2 guides)"
    primary_readout: str = ""          # primary readout description
    control_readout: str = ""          # control readout description
    expected_direction: str = ""       # expected phenotype change direction
    acceptance_criterion: str = ""     # "p < 0.05, paired t-test, n=3 lines × 2 guides"
    controls: list[str] = field(default_factory=list)
    backup_option: str = ""            # alternative if primary fails
    estimated_timeline: str = ""
    feasibility: str = "medium"        # "high", "medium", "low"

    # ── Literature awareness ──
    has_been_done_before: bool = False
    prior_experiment_pmids: list[str] = field(default_factory=list)
    prior_experiment_quality: PriorExperimentQuality = PriorExperimentQuality.NOT_FOUND
    prior_experiment_summary: str = "" # what the prior paper did and found
    should_redo: bool = False
    should_redo_reason: str = ""       # "underpowered (n=1), no non-targeting control"
    novelty_of_experiment: str = ""    # "novel", "replication", "improved_design"

    # What makes this specific to the claim
    why_readout_matches_mechanism: str = ""  # "surface protein change while transcript
                                             # stays stable proves post-translational"


# ═══════════════════════════════════════════════════════════════════════════
# EVIDENCE PROVIDER INTERFACE — abstract layer over data sources
# ═══════════════════════════════════════════════════════════════════════════

EVIDENCE_FAMILIES = [
    "in_vitro_association",        # DepMap
    "tumor_multiomics",            # CPTAC, TCGA/GDC
    "external_replication",        # GEO, independent cohorts
    "human_genomic_outcome",       # UK Biobank, GWAS Catalog, Open Targets, gnomAD, ClinVar
    "perturbation",                # DepMap CRISPR, GEO KO/KD/OE, LINCS, scPerturb
    "mouse_organismal",            # IMPC, MGI, ImmGen
    "single_cell_perturbation",    # scPerturb, Perturb-seq, CROP-seq
    "orthogonal_phenotype",        # microscopy, colocalization, biochemistry
    "functional_consequence",      # co-culture, killing assays, clinical outcome
    "literature",                  # PubMed, Tavily
    "foundation_model",            # Geneformer, AlphaFold — auxiliary, never final proof
]


# ═══════════════════════════════════════════════════════════════════════════
# DAG 1 EXPLORATION POLICY — iterative, coverage-guaranteed exploration
#
# DAG 1 should not ask only "What promising claims can I generate?"
# It should ask "Have I explored enough distinct frontier types, contexts,
# and claim families that my shortlist is a fair representation of the
# unexplained biology around this question?"
# ═══════════════════════════════════════════════════════════════════════════

class FrontierOperator(str, Enum):
    """How DAG 1 discovers candidate claims — multiple lenses."""
    UNEXPLAINED_MODULE = "unexplained_module"       # phenotype strong, canonical explanation insufficient
    BRIDGE_NODE = "bridge_node"                     # connects two usually-separate modules
    CONTRADICTION = "contradiction"                 # two accepted signals disagree
    MODALITY_DISCORDANCE = "modality_discordance"   # RNA-protein, total-surface, dependency-expression
    CONTEXT_TRANSFER = "context_transfer"           # known in one lineage, untested in user's context
    LOW_CLAIM_HIGH_BACKBONE = "low_claim_high_backbone"  # strong KG structure, few claims
    ANTI_HUB = "anti_hub"                          # intentionally non-central nodes


@dataclass
class ClaimFamily:
    """A cluster of near-duplicate candidate claims about the same mechanism.

    Before prior-art adjudication, cluster raw candidates into families.
    One representative per family goes through the literature gate.
    This prevents wasting budget on near-duplicates and mistaking
    redundancy for breadth.
    """
    family_id: str
    representative_claim_id: str    # the best claim to send through lit gate
    member_claim_ids: list[str] = field(default_factory=list)
    gene_family: str = ""           # "TMEM127", "HLA complex", "JAK-STAT"
    pathway_family: str = ""        # "antigen_presentation", "IFN_signaling"
    frontier_type: FrontierOperator = FrontierOperator.LOW_CLAIM_HIGH_BACKBONE
    n_members: int = 0
    mean_priority: float = 0.0


@dataclass
class CoverageReport:
    """Audit of DAG 1 exploration adequacy.

    Required before DAG 1 can terminate. Makes "adequately explored"
    testable rather than intuitive.
    """
    n_claim_families: int = 0
    n_frontier_classes_represented: int = 0
    frontier_classes: list[str] = field(default_factory=list)
    n_biological_contexts: int = 0
    fraction_from_contradictions: float = 0.0
    fraction_from_discordances: float = 0.0
    pathway_concentration_score: float = 0.0      # 0=diverse, 1=all same pathway
    hub_concentration_score: float = 0.0           # 0=diverse, 1=all hub genes
    novelty_yield: float = 0.0                     # fraction plausibly_novel after adjudication
    near_duplicate_pct: float = 0.0                # fraction that were clustered away

    # Thresholds (configurable via ResearchQuestionContract)
    min_frontier_classes: int = 4
    max_pathway_concentration: float = 0.25        # no >25% from one pathway family
    max_claims_per_gene_family: int = 2
    min_novelty_yield: float = 0.1

    def meets_thresholds(self) -> bool:
        """Does this exploration pass coverage requirements?"""
        return (
            self.n_frontier_classes_represented >= self.min_frontier_classes
            and self.pathway_concentration_score <= self.max_pathway_concentration
            and self.novelty_yield >= self.min_novelty_yield
        )


@dataclass
class ExplorationRound:
    """One iteration of the exploration loop."""
    round_number: int
    frontier_operator: FrontierOperator
    seeds_used: list[str] = field(default_factory=list)
    hops: int = 2
    raw_claims_generated: int = 0
    new_families_found: int = 0
    elapsed_seconds: float = 0.0


@dataclass
class ExplorationLedger:
    """Full audit trail of DAG 1 exploration.

    Every DAG 1 run should write this. When a good claim is missed later,
    the ledger reveals whether it was absent from the graph, filtered by
    diversity rules, killed by prior-art, or never reached.
    """
    exploration_id: str
    question_id: str
    rounds: list[ExplorationRound] = field(default_factory=list)
    total_raw_claims: int = 0
    total_families: int = 0
    coverage: CoverageReport | None = None
    saturated: bool = False
    saturation_reason: str = ""
    final_shortlist_size: int = 0
    final_shortlist_ids: list[str] = field(default_factory=list)


@dataclass
class SaturationCheck:
    """Result of checking whether DAG 1 should stop exploring.

    Saturated when the last 2-3 rounds add very few new families
    AND coverage thresholds are met.
    """
    is_saturated: bool = False
    new_family_rates: list[float] = field(default_factory=list)  # per-round
    reason: str = ""
    coverage_met: bool = False
    rounds_since_last_new_family: int = 0


# Extend ResearchQuestionContract with exploration policy
# (The fields are optional additions via the existing dataclass)
# Users set these on ResearchQuestionContract:
#   exploration_modes: list[str]       — which FrontierOperators to use
#   frontier_quotas: dict[str, int]    — min claims per frontier type
#   diversity_constraints: dict        — max_per_pathway_family, etc.
#   saturation_rule: str               — when to stop
#   max_hops_from_anchor: int          — how far to traverse


class ParticipantRole(str, Enum):
    """Role of an entity in a claim."""
    EFFECTOR_GENE = "effector_gene"
    TARGET_GENE = "target_gene"
    CONTEXT_MUTATION = "context_mutation"
    CONTEXT_CANCER_TYPE = "context_cancer_type"
    CONTEXT_CELL_TYPE = "context_cell_type"
    CONTEXT_IMMUNE_STATE = "context_immune_state"
    CONTEXT_CELL_STATE = "context_cell_state"   # exhausted / IFNγ-exposed / senescent / anergic / …
    CONTEXT_THERAPY = "context_therapy"
    CONTEXT_CELL_LINE = "context_cell_line"
    PHENOTYPE_GENE = "phenotype_gene"
    PATHWAY = "pathway"
    COMPOUND = "compound"
    OUTCOME = "outcome"
    CONFOUNDER = "confounder"
    REGULATOR_TF = "regulator_tf"
    REGULATEE = "regulatee"


@dataclass
class ClaimParticipant:
    """An entity participating in a claim with a specific role."""
    entity_id: str
    role: ParticipantRole
    properties: dict[str, Any] = field(default_factory=dict)


class ProofLevel(int, Enum):
    """Proof ladder — what kind of evidence supports this claim."""
    ONTOLOGY_FACT = 1            # curated biological fact
    OBSERVATIONAL_ASSOCIATION = 2  # correlation, co-expression
    MODEL_PREDICTION = 3         # predicted from trained model
    PERTURBATIONAL_MOLECULAR = 4  # LINCS KO/OE → molecular readout
    PERTURBATIONAL_PHENOTYPIC = 5  # DepMap CRISPR → viability
    ORTHOGONAL_REPRODUCTION = 6  # reproduced across studies/modalities
    PUBLISHED_ESTABLISHED = 7    # published in high-impact peer-reviewed literature


# ═══════════════════════════════════════════════════════════════════════════
# PUBLICATION AUTHORITY — Axis 5 of uncertainty
# ═══════════════════════════════════════════════════════════════════════════

class JournalTier(str, Enum):
    """Journal impact tier for weighting publication authority."""
    TIER1 = "tier1"   # Nature, Science, Cell, NEJM, Lancet (IF > 30)
    TIER2 = "tier2"   # Nature Genetics, Nature Medicine, Cancer Cell, Immunity (IF 15-30)
    TIER3 = "tier3"   # PNAS, JCI, Cancer Research, eLife, Genome Biology (IF 8-15)
    TIER4 = "tier4"   # Good journals (IF 4-8): PLoS Genetics, Nucleic Acids Res, Oncogene
    TIER5 = "tier5"   # Solid journals (IF 2-4)
    PREPRINT = "preprint"  # bioRxiv, medRxiv — not peer reviewed


# Journal → tier mapping (curated, expandable)
JOURNAL_TIER_MAP = {
    # Tier 1
    "nature": JournalTier.TIER1,
    "science": JournalTier.TIER1,
    "cell": JournalTier.TIER1,
    "the new england journal of medicine": JournalTier.TIER1,
    "the lancet": JournalTier.TIER1,
    "nature medicine": JournalTier.TIER1,
    "nature biotechnology": JournalTier.TIER1,
    # Tier 2
    "nature genetics": JournalTier.TIER2,
    "nature immunology": JournalTier.TIER2,
    "nature cell biology": JournalTier.TIER2,
    "nature methods": JournalTier.TIER2,
    "nature communications": JournalTier.TIER2,
    "cancer cell": JournalTier.TIER2,
    "immunity": JournalTier.TIER2,
    "cancer discovery": JournalTier.TIER2,
    "journal of clinical oncology": JournalTier.TIER2,
    "journal of experimental medicine": JournalTier.TIER2,
    "molecular cell": JournalTier.TIER2,
    "cell reports": JournalTier.TIER2,
    "science immunology": JournalTier.TIER2,
    "science translational medicine": JournalTier.TIER2,
    # Tier 3
    "proceedings of the national academy of sciences": JournalTier.TIER3,
    "pnas": JournalTier.TIER3,
    "journal of clinical investigation": JournalTier.TIER3,
    "cancer research": JournalTier.TIER3,
    "elife": JournalTier.TIER3,
    "genome biology": JournalTier.TIER3,
    "genome research": JournalTier.TIER3,
    "nucleic acids research": JournalTier.TIER3,
    "blood": JournalTier.TIER3,
    "cancer immunology research": JournalTier.TIER3,
    "clinical cancer research": JournalTier.TIER3,
    "embo journal": JournalTier.TIER3,
    "annals of oncology": JournalTier.TIER3,
    # Tier 4
    "plos genetics": JournalTier.TIER4,
    "oncogene": JournalTier.TIER4,
    "molecular cancer": JournalTier.TIER4,
    "bmc genomics": JournalTier.TIER4,
    "frontiers in immunology": JournalTier.TIER4,
    # Preprint
    "biorxiv": JournalTier.PREPRINT,
    "medrxiv": JournalTier.PREPRINT,
}


# ═══════════════════════════════════════════════════════════════════════════
# TEXTBOOK KNOWLEDGE — established biology the agent should never "discover"
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TextbookFact:
    """An established biological fact that should not be treated as a hypothesis.

    These are things every immunology/cancer biology textbook states.
    If the agent "discovers" one of these, it should recognize it as
    known biology and not present it as a novel finding.

    The agent uses these to:
    1. Filter out textbook correlations from hypothesis testing
    2. Provide biological context when interpreting results
    3. Identify when a finding is CONTRADICTING textbook knowledge (important!)
    4. Build baseline expectations before running experiments
    """
    fact_id: str
    category: str              # "immunology", "cancer_biology", "cell_biology", "genetics"
    statement: str             # the fact in plain language
    mechanism: str = ""        # brief mechanistic explanation
    genes_involved: list[str] = field(default_factory=list)
    pathways_involved: list[str] = field(default_factory=list)

    # How to detect if the agent is "discovering" this
    detection_gene_pairs: list[tuple[str, str]] = field(default_factory=list)
    detection_keywords: list[str] = field(default_factory=list)

    # Source
    textbook: str = ""         # "Janeway's Immunobiology", "Molecular Biology of the Cell"
    first_discovered: str = "" # year/author of original discovery


# Textbook facts are loaded dynamically from the knowledge graph or
# external sources at runtime — no hardcoded biology.
TEXTBOOK_FACTS: list[TextbookFact] = []


def is_textbook_fact(
    gene1: str,
    gene2: str,
    keywords: list[str] | None = None,
) -> tuple[bool, TextbookFact | None]:
    """Check if a gene-gene association is a known textbook fact.

    Returns (is_textbook, matching_fact_or_None).
    The agent should call this BEFORE presenting any finding as novel.
    """
    g1, g2 = gene1.upper(), gene2.upper()

    for fact in TEXTBOOK_FACTS:
        # Check gene pair match
        for pair in fact.detection_gene_pairs:
            p1, p2 = pair[0].upper(), pair[1].upper()
            if (g1 == p1 and g2 == p2) or (g1 == p2 and g2 == p1):
                return True, fact

        # Check if both genes are in the same fact's gene list
        fact_genes = {g.upper() for g in fact.genes_involved}
        if g1 in fact_genes and g2 in fact_genes:
            return True, fact

    # Keyword-based detection (if provided)
    if keywords:
        kw_text = " ".join(k.lower() for k in keywords)
        for fact in TEXTBOOK_FACTS:
            kw_matches = sum(1 for dk in fact.detection_keywords if dk in kw_text)
            gene_matches = sum(1 for g in fact.genes_involved
                               if g.upper() in (g1, g2))
            if kw_matches >= 2 and gene_matches >= 1:
                return True, fact

    return False, None


def get_textbook_context(genes: list[str]) -> list[TextbookFact]:
    """Get all textbook facts relevant to a set of genes.

    The agent should call this at the START of any investigation
    to understand what is already known about these genes.
    """
    gene_set = {g.upper() for g in genes}
    relevant = []
    for fact in TEXTBOOK_FACTS:
        fact_genes = {g.upper() for g in fact.genes_involved}
        overlap = gene_set & fact_genes
        if len(overlap) >= 2:  # at least 2 genes overlap
            relevant.append(fact)
    return relevant


def print_textbook_context(genes: list[str]) -> None:
    """Print textbook knowledge relevant to a gene set.

    The agent runs this first to understand baseline biology
    before forming hypotheses.
    """
    facts = get_textbook_context(genes)
    if not facts:
        print("No textbook facts found for these genes — potentially novel biology.")
        return

    print(f"TEXTBOOK KNOWLEDGE ({len(facts)} known facts):")
    print("These are established biological facts — do NOT hypothesize about them.")
    print()
    for fact in facts:
        overlap = {g.upper() for g in genes} & {g.upper() for g in fact.genes_involved}
        print(f"  [{fact.fact_id}] {fact.statement}")
        print(f"    Category: {fact.category}")
        print(f"    Mechanism: {fact.mechanism[:120]}")
        print(f"    Your genes involved: {sorted(overlap)}")
        print(f"    Source: {fact.textbook}")
        print()



def classify_journal_tier(journal_name: str) -> JournalTier:
    """Classify a journal into a tier based on curated mapping."""
    j = journal_name.lower().strip()
    # Exact match
    if j in JOURNAL_TIER_MAP:
        return JOURNAL_TIER_MAP[j]
    # Partial match (e.g., "Nature Genetics" matches "nature genetics")
    for key, tier in JOURNAL_TIER_MAP.items():
        if key in j or j in key:
            return tier
    return JournalTier.TIER5  # default


@dataclass
class PublicationEvidence:
    """A single publication supporting or contradicting a claim.

    This is what the geo_agent literature search populates.
    The discovery agent queries PubMed, scores relevance, and
    extracts these structured records.
    """
    pmid: str
    title: str
    authors: str = ""            # first author + et al.
    journal: str = ""
    year: int = 0
    doi: str = ""

    # Journal quality
    journal_tier: JournalTier = JournalTier.TIER5
    impact_factor: float = 0.0   # if known

    # Relevance to the claim
    relevance_score: float = 0.0  # 0-1, from geo_agent score_relevance()
    is_direct_evidence: bool = False  # mechanism + phenotype + association in abstract

    # What the paper shows
    study_type: str = ""         # "experimental", "meta-analysis", "review", "case_report"
    sample_size: int = 0         # if reported
    organism: str = ""           # "human", "mouse", "in_vitro"
    key_finding: str = ""        # one-sentence summary of what it proves

    # Evidence strength within the paper
    has_perturbation: bool = False   # does the paper do KO/KD/overexpression?
    has_clinical_data: bool = False  # does it include patient data?
    has_functional_assay: bool = False  # FACS, killing assay, etc.
    n_independent_experiments: int = 0  # biological replicates

    # Direction: does this paper support or contradict?
    supports_claim: bool | None = None  # True/False/None
    contradiction_note: str = ""


@dataclass
class PublicationSupport:
    """Aggregated publication authority for a claim — Axis 5 of uncertainty.

    This is the 5th dimension of uncertainty, separate from:
      1. Statistical (p/q/CI)
      2. Predictive (fold variance, bootstrap)
      3. Provenance (dataset quality)
      4. Reproducibility (n_studies, n_modalities)
      5. Publication authority (THIS) — what the peer-reviewed literature says

    High-impact papers proving a mechanism should elevate the claim
    to near-fact status. The discovery agent populates this by running
    the geo_agent's run_literature_search() on each claim.

    Scoring:
      ESTABLISHED: ≥3 tier1/2 papers with direct experimental evidence → treat as fact
      WELL_SUPPORTED: ≥2 tier1-3 papers with some experimental evidence
      MODERATELY_SUPPORTED: 1-2 papers or lower-tier journals
      WEAKLY_SUPPORTED: only preprints or tangential mentions
      NOVEL: 0 direct prior art — genuinely new finding
      CONTRADICTED_IN_LITERATURE: published papers explicitly disagree
    """
    # Individual publications
    publications: list[PublicationEvidence] = field(default_factory=list)

    # Aggregate scores
    n_total_articles: int = 0
    n_direct_evidence: int = 0   # papers with direct mechanism + phenotype evidence
    n_tier1_papers: int = 0      # Nature, Science, Cell level
    n_tier2_papers: int = 0      # Nature Genetics, Cancer Cell level
    n_tier3_papers: int = 0
    n_with_perturbation: int = 0  # papers that do KO/KD/OE
    n_with_clinical: int = 0     # papers with patient data
    n_supporting: int = 0
    n_contradicting: int = 0

    # Overall publication authority
    authority_level: str = "novel"  # established, well_supported, moderately_supported, weakly_supported, novel, contradicted
    authority_score: float = 0.0   # 0-1, composite of above
    authority_note: str = ""       # human-readable explanation

    # Novelty (inverse of authority — high authority = low novelty)
    novelty: str = "HIGH"        # HIGH, MODERATE, LOW (from geo_agent)
    novelty_note: str = ""

    # Search provenance
    n_queries_run: int = 0       # how many PubMed queries were executed
    search_date: str = ""        # when the search was done
    search_exhaustive: bool = False  # did we use all 15 query strategies?

    def compute_authority(self) -> None:
        """Compute authority level from publication evidence.

        Called after publications are populated by the discovery agent.
        """
        self.n_total_articles = len(self.publications)
        self.n_direct_evidence = sum(1 for p in self.publications if p.is_direct_evidence)
        self.n_tier1_papers = sum(1 for p in self.publications
                                  if p.journal_tier == JournalTier.TIER1 and p.is_direct_evidence)
        self.n_tier2_papers = sum(1 for p in self.publications
                                  if p.journal_tier == JournalTier.TIER2 and p.is_direct_evidence)
        self.n_tier3_papers = sum(1 for p in self.publications
                                  if p.journal_tier == JournalTier.TIER3 and p.is_direct_evidence)
        self.n_with_perturbation = sum(1 for p in self.publications
                                       if p.has_perturbation and p.is_direct_evidence)
        self.n_with_clinical = sum(1 for p in self.publications
                                    if p.has_clinical_data and p.is_direct_evidence)
        self.n_supporting = sum(1 for p in self.publications if p.supports_claim is True)
        self.n_contradicting = sum(1 for p in self.publications if p.supports_claim is False)

        # Compute authority level
        high_impact_direct = self.n_tier1_papers + self.n_tier2_papers

        if self.n_contradicting >= 2 and self.n_contradicting >= self.n_supporting:
            self.authority_level = "contradicted_in_literature"
            self.authority_score = 0.1
            self.authority_note = (
                f"{self.n_contradicting} publications contradict this claim. "
                f"Published evidence argues against this mechanism."
            )
        elif high_impact_direct >= 3 and self.n_with_perturbation >= 1:
            self.authority_level = "established"
            self.authority_score = 0.95
            self.authority_note = (
                f"{high_impact_direct} high-impact papers (tier 1-2) with direct evidence, "
                f"including {self.n_with_perturbation} with perturbation data. "
                f"Treat as established fact."
            )
        elif high_impact_direct >= 2 or (self.n_direct_evidence >= 3 and self.n_with_perturbation >= 1):
            self.authority_level = "well_supported"
            self.authority_score = 0.80
            self.authority_note = (
                f"{self.n_direct_evidence} papers with direct evidence "
                f"({high_impact_direct} high-impact). Well-supported mechanism."
            )
        elif self.n_direct_evidence >= 2 or high_impact_direct >= 1:
            self.authority_level = "moderately_supported"
            self.authority_score = 0.55
            self.authority_note = (
                f"{self.n_direct_evidence} papers with direct evidence. "
                f"Moderately supported — additional validation would strengthen."
            )
        elif self.n_direct_evidence >= 1 or self.n_total_articles >= 3:
            self.authority_level = "weakly_supported"
            self.authority_score = 0.30
            self.authority_note = (
                f"{self.n_direct_evidence} paper(s) with direct evidence, "
                f"{self.n_total_articles} total articles. Weakly supported."
            )
        else:
            self.authority_level = "novel"
            self.authority_score = 0.0  # no authority = must prove from scratch
            self.authority_note = (
                f"No publications found with direct evidence for this mechanism. "
                f"This is a novel finding — requires de novo proof."
            )

        # Novelty is inverse of authority
        if self.authority_level == "established":
            self.novelty = "LOW"
            self.novelty_note = "Well-established in literature — not novel"
        elif self.authority_level in ("well_supported", "moderately_supported"):
            self.novelty = "MODERATE"
            self.novelty_note = "Some prior work exists — novel angle possible"
        else:
            self.novelty = "HIGH"
            self.novelty_note = "No direct prior art — genuinely novel finding"


@dataclass
class PriorArt:
    """LLM-context-economy view of a Claim's prior-art bookkeeping.

    NOT a Claim field. ``Claim`` keeps the flat ``prior_art_status``,
    ``prior_art_pmids``, … fields directly (the dataclass + property
    pattern fought Python's class-attribute resolution; see commit
    history for the rollback). ``Claim.prior_art_view()`` returns a
    PriorArt instance for callers (LLM serialisers, report templates)
    that want the nested form so prompts don't carry 50+ PMIDs at
    the top level by default.

    `status` is the only PriorArt field that drives lifecycle gates
    (CANONICAL → skip, PLAUSIBLY_NOVEL → pursue).
    """
    status: PriorArtStatus = PriorArtStatus.UNSEARCHED
    pmids: list[str] = field(default_factory=list)
    dois: list[str] = field(default_factory=list)
    search_done: bool = False
    search_query: str = ""
    reasoning: str = ""        # why this classification was chosen


@dataclass
class Claim:
    """A context-dependent assertion — the core unit of the knowledge graph.

    Every claim that the agent discovers gets stored here.
    Claims are NOT naked edges — they have participants, evidence,
    uncertainty, and lifecycle status across three orthogonal axes.

    Critical rule: the hypothesis verdict and the claim lifecycle are
    not the same object. A claim can be validated while the overall
    mechanism verdict is still only PARTIALLY_SUPPORTED.
    """
    # P3/P4: defaults so legacy `Claim(candidate_id=...)` works without
    # passing claim_id positionally. __post_init__ mirrors candidate_id
    # → claim_id when claim_id is empty.
    claim_id: str = ""
    claim_type: ClaimType = ClaimType.GENE_GENE_CORRELATION

    # ── Three orthogonal axes ──
    # prior_art_status sits as a flat field directly on Claim; the
    # nested ``PriorArt`` form is built on demand via prior_art_view()
    # for serialisation callers that want the compact representation.
    evidence_status: EvidenceStatus = EvidenceStatus.DRAFT
    review_status: ReviewStatus = ReviewStatus.CLEAN

    # What the claim says
    # `direction` is a presentation field, derived from relation_polarity
    # in __post_init__. Do not pass it in new code; `relation_polarity`
    # is the canonical source of truth. Kept on the dataclass so legacy
    # callers passing direction= still work; SQL no longer writes it.
    claim_text: str = ""         # atomic statement in natural language
    direction: str = ""          # DERIVED from relation_polarity in __post_init__
    relation_name: str = ""       # typed predicate from relation_registry.py
                                  # e.g. "destabilizes", "phosphorylates", "represses"
    relation_polarity: str = ""   # "positive" | "negative" | "bidirectional" | "null" | "unknown"
    effect_size: float = 0.0
    effect_unit: str = ""        # "CERES", "log2FC", "Pearson_r", "hazard_ratio"

    # Graph linkage — fast index back to Layer-1 entities and to the
    # CandidateClaim lineage (literature profile, KG enrichment).
    candidate_gene: str = ""     # HGNC symbol, indexed
    candidate_id: str = ""       # CandidateClaim.candidate_id this was promoted from

    # Context
    context_operator: str = "AND"  # how participants combine
    participants: list[ClaimParticipant] = field(default_factory=list)

    # ── Cell state characterization ──
    # Many claims only hold in a specific cell state (exhausted CD8,
    # IFNγ-exposed tumour cell, senescent fibroblast, anergic T cell, …).
    # Stored as JSON list of CellStateCondition (see claim_ontology.py).
    # Transient representation lives on StructuredClaim.cell_states; this
    # field is the persisted JSON projection.
    cell_states_json: str = "[]"

    # ── ContextSet (typed-graph projection of biological context) ──
    # JSON-serialised gbd.core.context_provenance.ContextSet. Built from
    # StructuredClaim.context + cell_states + effector_compartment +
    # immune_cell_subtype at add_claim time. The free-text fields above
    # (cell_states_json) and on StructuredClaim.context are still kept
    # so existing readers don't break, but new code should query through
    # this field — it is queryable via ancestor traversal and is what
    # EdgeView.context surfaces.
    context_set_json: str = "{}"

    # Provenance
    source_dataset: str = ""     # e.g., "DepMap_24Q2", "GSE91061", "CPTAC_PDC000127"
    source_release: str = ""
    assay_type: str = ""         # "CRISPR_Chronos", "RNA-seq", "mass_spec"
    model_name: str = ""         # e.g., "ElasticNet", "DerSimonian-Laird"
    model_version: str = ""
    artifact_id: str = ""        # hash of raw data that produced this

    # Proof level
    proof_level: ProofLevel = ProofLevel.OBSERVATIONAL_ASSOCIATION

    # Per-result statistics (Axis 1 statistical, Axis 2 predictive)
    # now live on BiologicalResult. The Claim records only aggregate
    # reproducibility and publication authority.

    # Axis 4: Reproducibility (aggregated across results)
    n_studies: int = 0
    n_modalities: int = 0
    direction_consistency: float = 0.0  # fraction of studies with same direction

    # Axis 5: Publication authority
    publication_support: PublicationSupport | None = None

    # ── Prior-art adjudication (nested) ──
    # Single nested PriorArt object instead of 6 flat fields.
    # Readers do `claim.prior_art.status`, `claim.prior_art.pmids`, etc.
    # LLM serialisers get the compact form for free — top-level
    # claim dumps show one `prior_art` key, not 6 prior_art_* keys.
    prior_art: PriorArt = field(default_factory=PriorArt)
    novelty_score: float | None = None   # 0 = textbook, 1 = completely novel — top-level, drives ranking
    kg_suggested: bool = False           # True if suggested by KG traversal

    # ── DAG 1 ranking (P1 — was on CandidateClaim) ──
    # All None until DAG 1 has ranked the candidate. None ≠ 0.0 — None
    # means "not yet ranked" while 0.0 means "ranked, score is zero".
    tractability_score: float | None = None
    kg_connectivity_score: float | None = None
    priority_score: float | None = None

    # ── Source provenance (P1 — was on CandidateClaim) ──
    source: str = ""                 # "kg_traversal" / "literature_gap" / "contradiction_gap"
    kg_evidence: list[str] = field(default_factory=list)
                                      # backbone edge IDs that suggested this claim

    # ── Legacy CandidateClaim shape, kept on Claim so the old shape
    #    keeps constructing (P3/P4 collapse — CandidateClaim = Claim).
    #    Readers (paper.py, report.py, literature_grounded_hypotheses.py,
    #    plan_frontmatter.py, providers/external_replication.py,
    #    post_report_review.py, claim_reasoning.py) all read
    #    claim.phenotype.name; keeping the field avoids 13+ rewrites.
    phenotype: Any = None             # PhenotypeDefinition | None
    context: dict[str, str] = field(default_factory=dict)
                                      # legacy free-form context dict; the
                                      # canonical typed projection is
                                      # context_set_json. __post_init__
                                      # serialises this into context_set_json
                                      # when caller didn't pass one.
    candidate_nodes: list[Any] = field(default_factory=list)
                                      # legacy multi-entity field. Mapped
                                      # into participants in __post_init__
                                      # if participants is empty.

    # ── Hierarchy / refinement / context-split (P1) ──
    # Three reasons a claim has a parent: (a) it refines a more general
    # claim (RefinedClaim lineage), (b) it was born from a context split
    # (P9 splitter — splits_on_dimension is set), (c) it is a child of a
    # claim flagged is_general=True. parent_claim_id is the single link.
    parent_claim_id: str = ""
    refinement_type: str = ""              # narrow|branches_from|pivot|expand|""
    refinement_rationale: str = ""
    refinement_confidence: float | None = None  # judge confidence in the refinement
    splits_on_dimension: str = ""          # "residue" / "cell_type" / … when born from a split
    is_general: bool = False               # True on a parent that has been split into children
    target_mechanism_ids: list[str] = field(default_factory=list)
    inherited_evidence_ids: list[str] = field(default_factory=list)
    tools_to_prioritise: list[str] = field(default_factory=list)
    cancer_type_scope: str = ""            # narrowed type from RefinedClaim (was list[str])
    embedding_text: str = ""               # text used to compute claim embedding

    # ── Supersession ──
    superseded_by: str = ""       # claim_id of the claim that replaces this one

    # ── Contradiction tracking ──
    contradiction_case_ids: list[str] = field(default_factory=list)

    # ── Serialised StructuredClaim — JSON projection of the parsed
    # ontology produced by analyze_claim (entity_id, alteration,
    # latent_state, cell_states, context, etc.).
    # Written into the claims.full_data SQLite column on add_claim.
    structured_claim_json: str = ""

    # ── Cross-source dedup primitive ──
    # SHA256(subject_node_id|relation_name|object_node_id), computed at
    # add_claim time when participants + relation_name are resolvable.
    # Polarity is intentionally NOT in the signature: claims with the
    # same subject/relation/object but opposite polarities are the same
    # *biological assertion* under contention, and reconciliation routes
    # the conflicting evidence into a stance="contradicts" SupportSet on
    # the existing claim instead of creating a duplicate. Empty string
    # means the signature could not be computed (incomplete claim) —
    # such claims are skipped by reconciliation.
    edge_signature: str = ""

    # Metadata
    created_at: str = ""
    created_by: str = ""              # "gbd_agent", "manual", "geo_agent"
    human_readable: str = ""          # one-liner for logs, e.g. "CTNNB1 is essential in APC-mutant COAD"

    # ── Transient runtime decoration (P1) ──
    # These fields are NOT persisted to SQL. They carry live Python
    # objects (StructuredClaim, CausalChain, CompetingExplanation list,
    # HypothesisContext) used by DAG 2 mid-run. `to_kg_row()` excludes
    # them. `repr=False` keeps them out of dataclass.__repr__ so debug
    # prints stay readable; `compare=False` keeps them out of equality
    # checks so two Claims with the same persisted state compare equal
    # regardless of attached runtime caches.
    structured_claim: Any = field(default=None, repr=False, compare=False)
    causal_chain: Any = field(default=None, repr=False, compare=False)
    competing_explanations: list = field(
        default_factory=list, repr=False, compare=False,
    )
    literature_profile: Any = field(default=None, repr=False, compare=False)
    mechanism_hypotheses: list = field(
        default_factory=list, repr=False, compare=False,
    )
    kg_context: dict = field(default_factory=dict, repr=False, compare=False)
    children_claim_ids: list[str] = field(
        default_factory=list, repr=False, compare=False,
    )
    _hypothesis_context: Any = field(default=None, repr=False, compare=False)
    _claim_reasoning_obj: Any = field(default=None, repr=False, compare=False)
    _evidence_profile: dict = field(
        default_factory=dict, repr=False, compare=False,
    )

    # ── Persistence helper ──
    # Names of the fields above that are transient runtime decoration
    # and MUST NOT be written to SQLite. `to_kg_row()` excludes them;
    # the curated importer + add_claim use only persisted fields.
    _TRANSIENT_FIELDS: "ClassVar[frozenset[str]]" = frozenset({
        "structured_claim", "causal_chain", "competing_explanations",
        "literature_profile", "mechanism_hypotheses", "kg_context",
        "children_claim_ids",
        "_hypothesis_context", "_claim_reasoning_obj", "_evidence_profile",
    })

    def to_kg_row(self) -> dict[str, Any]:
        """Return the persisted subset of this Claim as a plain dict.

        Excludes transient runtime fields (live StructuredClaim,
        CausalChain, etc.). Used by add_claim and the curated importer
        to write only what the SQL schema knows about.
        """
        return {
            f.name: getattr(self, f.name)
            for f in fields(self)
            if f.name not in self._TRANSIENT_FIELDS
        }

    def __post_init__(self):
        """Derive direction from relation_polarity (legacy presentation field).

        After P1.5 `direction` is no longer a source of truth. Legacy
        callers may still pass direction="up" / "down" / etc., in which
        case we project that into relation_polarity ONCE if polarity was
        empty. relation_polarity then drives the displayed direction.
        Unusual legacy values (e.g. "essential", "codependent",
        "lof_intolerant") that don't map cleanly to polarity stay on
        the direction field unchanged — caller migration in P3 picks a
        better home for them.
        """
        _DIR_TO_POL = {
            "up": "positive", "positive": "positive", "enriched": "positive",
            "essential": "positive",
            "down": "negative", "negative": "negative", "depleted": "negative",
            "resistant": "negative", "inverse": "negative",
            "abolished": "null", "unchanged": "null",
            "bidirectional": "bidirectional", "context_dependent": "bidirectional",
            "": "", "unknown": "unknown",
        }
        _POL_TO_DIR = {
            "positive": "positive", "negative": "negative",
            "bidirectional": "context_dependent",
            "null": "unchanged", "unknown": "unknown", "": "",
        }
        if self.direction and not self.relation_polarity:
            mapped = _DIR_TO_POL.get(self.direction.lower())
            if mapped is not None:
                self.relation_polarity = mapped
        # Always rederive direction from polarity when polarity is set,
        # so polarity is the single source of truth. If polarity is empty
        # OR direction's value is one of the unusual legacy strings we
        # don't have a canonical projection for, leave direction alone.
        if self.relation_polarity and self.relation_polarity in _POL_TO_DIR:
            self.direction = _POL_TO_DIR[self.relation_polarity]

        # ── P3/P4 — candidate_id ↔ claim_id sync (legacy alias) ──
        # Legacy callers used Claim(candidate_id=X) without setting claim_id.
        # Mirror in both directions so either field is the single point of
        # truth for any one Claim.
        if self.candidate_id and not self.claim_id:
            self.claim_id = self.candidate_id
        elif self.claim_id and not self.candidate_id:
            self.candidate_id = self.claim_id

        # ── P3/P4 — legacy CandidateClaim shape projection ──
        # context: dict → context_set_json (only when caller didn't
        # pass an explicit context_set_json). The dict form keeps
        # working for legacy readers via the unchanged `self.context`
        # attribute; the JSON form is what edge_signature and
        # claim_splitter consume.
        if self.context and (not self.context_set_json or self.context_set_json == "{}"):
            try:
                import json as _json
                self.context_set_json = _json.dumps(dict(self.context))
            except (TypeError, ValueError):
                pass

        # candidate_nodes → participants. Only project when participants
        # is empty so we don't clobber an explicit participant list.
        if self.candidate_nodes and not self.participants:
            for n in self.candidate_nodes:
                role_attr = getattr(n, "role_in_claim", None)
                role_name = getattr(role_attr, "value", "") or "effector_gene"
                # Map NodeRoleInClaim → ParticipantRole defensively.
                # Unknown / unhandled roles default to EFFECTOR_GENE so
                # the claim still has a subject anchor.
                role_map = {
                    "primary": ParticipantRole.EFFECTOR_GENE,
                    "mediator": ParticipantRole.PATHWAY,
                    "upstream_regulator": ParticipantRole.REGULATOR_TF,
                    "downstream_target": ParticipantRole.TARGET_GENE,
                    "partner": ParticipantRole.PATHWAY,
                    "substrate": ParticipantRole.TARGET_GENE,
                    "context_marker": ParticipantRole.CONTEXT_CELL_STATE,
                }
                role = role_map.get(role_name, ParticipantRole.EFFECTOR_GENE)
                eid = getattr(n, "node_id", "") or ""
                if not eid:
                    continue
                props: dict[str, Any] = {}
                cmp = getattr(n, "compartment", "")
                if cmp:
                    props["compartment"] = cmp
                self.participants.append(
                    ClaimParticipant(entity_id=eid, role=role, properties=props),
                )

        # ── PZ — anchor on participants, derive candidate_gene index ──
        # The legacy single-string `candidate_gene` field is being phased
        # out in favour of `participants[role=EFFECTOR_GENE]`. For
        # backwards compat with the 13+ readers that still touch
        # `claim.candidate_gene`, auto-populate from the primary
        # participant when the caller didn't set it. Callers that DO
        # pass candidate_gene continue to win — the field is not
        # rewritten if already set.
        if not self.candidate_gene and self.participants:
            for p in self.participants:
                role_val = getattr(p.role, "value", None) or str(p.role)
                if role_val == "effector_gene" and p.entity_id:
                    self.candidate_gene = p.entity_id
                    break


# ── P4: CandidateClaim is now a pure alias for Claim ──────────────────
# The legacy class is gone (P3 migrated all callers). External imports
# of `CandidateClaim` continue to work via this alias. New code should
# import `Claim` directly. The alias can be deleted in a future release
# once external dependencies migrate.
CandidateClaim = Claim


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 3: EVIDENCE
# ═══════════════════════════════════════════════════════════════════════════

class EvidenceType(str, Enum):
    """Types of evidence supporting claims."""
    DATASET = "Dataset"
    ASSAY = "Assay"
    STATISTICAL_TEST = "StatisticalTest"
    MODEL_RUN = "ModelRun"
    PERTURBATION_EXPERIMENT = "PerturbationExperiment"
    REPLICATION_SET = "ReplicationSet"
    LITERATURE_SUPPORT = "LiteratureSupport"
    ARTIFACT = "Artifact"        # raw file, model checkpoint


@dataclass
class Evidence:
    """A piece of evidence supporting a claim."""
    evidence_id: str
    evidence_type: EvidenceType

    # What it is
    description: str = ""
    source: str = ""             # "DepMap", "GEO", "CPTAC", "PubMed"

    # Statistical result (if applicable)
    statistic_name: str = ""     # "Pearson_r", "Welch_t", "CERES_score"
    statistic_value: float | None = None
    p_value: float | None = None
    effect_size: float | None = None
    sample_size: int = 0
    confidence_interval: tuple[float, float] | None = None

    # For model runs
    model_name: str = ""
    model_version: str = ""
    cv_metric: str = ""
    cv_value: float | None = None

    # For literature
    pmid: str = ""
    doi: str = ""
    year: int = 0
    title: str = ""

    # For datasets
    accession: str = ""          # GSE, PDC, SRA
    n_samples: int = 0
    organism: str = "Homo sapiens"

    # For perturbation experiments
    perturbation_type: str = ""  # "CRISPR_KO", "shRNA", "overexpression", "drug"
    perturbed_gene: str = ""
    readout: str = ""            # "viability", "surface_HLA", "RNA-seq"
    cell_line: str = ""

    # Provenance
    artifact_path: str = ""      # path to raw data file
    artifact_hash: str = ""      # SHA256 for reproducibility
    created_at: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 4: LOGIC (SupportSets + Contradictions)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SupportSet:
    """An AND-group of evidence supporting a claim.

    A claim can have multiple SupportSets (OR logic).
    Each SupportSet is a conjunction (AND) of evidence items.

    Example:
      Claim: "APC loss creates CTNNB1 dependency in COAD"
      SupportSet A: DepMap differential CERES AND sufficient mutant lines AND q < 0.05
      SupportSet B: LASSO SL coefficient AND held-out stability
      SupportSet C: LINCS KGene CTNNB1 signature AND WNT pathway enrichment
      SupportSet D: CPTAC RNA-seq prediction AND proteomics prediction agreement
    """
    support_set_id: str
    claim_id: str                # which claim this supports
    label: str = ""              # human-readable label, e.g., "DepMap direct evidence"
    logic: str = "AND"           # how evidence items combine within this set

    # Stance — does this evidence pile SUPPORT or REFUTE the claim?
    # When the cross-source importer finds an existing claim with the
    # same edge_signature but opposite polarity, the new evidence is
    # appended as a stance="contradicts" SupportSet rather than as a
    # new Claim. The credibility assessor reads both stances and weighs
    # them appropriately — supporting raises the point estimate and
    # tightens the interval; contradicting widens the interval and may
    # downgrade the verdict. Default "supports" for backward compat.
    stance: str = "supports"     # "supports" | "contradicts" | "ambiguous"

    # Evidence items in this set
    evidence_ids: list[str] = field(default_factory=list)

    # Set-level confidence (calibrated)
    confidence: float = 0.0      # 0-1, calibrated from evidence
    proof_level: ProofLevel = ProofLevel.OBSERVATIONAL_ASSOCIATION

    # Metadata
    description: str = ""


@dataclass
class Contradiction:
    """DEPRECATED — kept for migration. Use ContradictionCase instead.

    ContradictionCase provides biology-native classification
    (entity_mismatch, assay_mismatch, context_split, true_frontier)
    and structured resolution tracking.
    """
    contradiction_id: str
    claim_id_a: str
    claim_id_b: str

    contradiction_type: str = ""
    description: str = ""
    dimension: str = ""
    value_a: str = ""
    value_b: str = ""

    resolved: bool = False
    resolution: str = ""
    resolution_claim_id: str = ""

    exploration_priority: str = "medium"
    exploration_rationale: str = ""

    created_at: str = ""
    created_by: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# CONFIDENCE COMPUTATION
# ═══════════════════════════════════════════════════════════════════════════

def noisy_or_confidence(support_sets: list[SupportSet]) -> float:
    """Compute claim confidence via noisy-OR over support sets.

    P(claim) = 1 - ∏(1 - P(support_set_i))

    Intuition:
    - One strong support set may be enough
    - Multiple independent support sets raise confidence
    - Each support set's confidence is calibrated from its evidence
    """
    if not support_sets:
        return 0.0

    # Filter to non-zero confidence
    confidences = [ss.confidence for ss in support_sets if ss.confidence > 0]
    if not confidences:
        return 0.0

    # Noisy-OR
    prob_none = 1.0
    for c in confidences:
        prob_none *= (1.0 - min(c, 0.999))  # cap to avoid log(0)

    return round(1.0 - prob_none, 4)


def compute_support_set_confidence(
    evidence_items: list[Evidence],
    proof_level: ProofLevel,
    publication_support: PublicationSupport | None = None,
) -> float:
    """Compute confidence for a single support set from its evidence.

    5-axis calibrated heuristic:
    1. Proof level (perturbational > observational > predicted)
    2. Statistical significance of evidence
    3. Sample size
    4. Effect size magnitude
    5. Publication authority — high-impact papers can elevate to near-certainty
    """
    if not evidence_items:
        return 0.0

    base = 0.0

    # Proof level base
    level_base = {
        ProofLevel.ONTOLOGY_FACT: 0.95,
        ProofLevel.OBSERVATIONAL_ASSOCIATION: 0.3,
        ProofLevel.MODEL_PREDICTION: 0.2,
        ProofLevel.PERTURBATIONAL_MOLECULAR: 0.6,
        ProofLevel.PERTURBATIONAL_PHENOTYPIC: 0.7,
        ProofLevel.ORTHOGONAL_REPRODUCTION: 0.85,
        ProofLevel.PUBLISHED_ESTABLISHED: 0.93,
    }
    base = level_base.get(proof_level, 0.2)

    # Adjust for statistical significance (best p-value)
    p_values = [e.p_value for e in evidence_items if e.p_value is not None and e.p_value > 0]
    if p_values:
        best_p = min(p_values)
        if best_p < 1e-10:
            base = min(base + 0.3, 0.95)
        elif best_p < 1e-5:
            base = min(base + 0.2, 0.90)
        elif best_p < 0.001:
            base = min(base + 0.1, 0.80)
        elif best_p < 0.05:
            base = min(base + 0.05, 0.70)

    # Adjust for sample size
    total_n = sum(e.sample_size for e in evidence_items if e.sample_size > 0)
    if total_n > 1000:
        base = min(base + 0.1, 0.95)
    elif total_n > 100:
        base = min(base + 0.05, 0.90)

    # Adjust for effect size
    effects = [abs(e.effect_size) for e in evidence_items if e.effect_size is not None]
    if effects:
        max_effect = max(effects)
        if max_effect > 0.8:
            base = min(base + 0.1, 0.95)
        elif max_effect > 0.5:
            base = min(base + 0.05, 0.90)

    # Axis 5: Publication authority
    # High-impact papers proving this mechanism can elevate to near-certainty
    if publication_support is not None:
        pub = publication_support
        if pub.authority_level == "established":
            # ≥3 tier1/2 papers with perturbation data = treat as fact
            base = max(base, 0.93)
        elif pub.authority_level == "well_supported":
            base = max(base, min(base + 0.20, 0.90))
        elif pub.authority_level == "moderately_supported":
            base = max(base, min(base + 0.10, 0.75))
        elif pub.authority_level == "contradicted_in_literature":
            # Published contradictions actively lower confidence
            base = min(base, 0.15)

    return round(base, 4)


# ═══════════════════════════════════════════════════════════════════════════
# FULL ONTOLOGY SUMMARY
# ═══════════════════════════════════════════════════════════════════════════

ONTOLOGY_SUMMARY = """
GBD KNOWLEDGE GRAPH ONTOLOGY — Two-DAG Architecture
═══════════════════════════════════════════════════════════════════════

ARCHITECTURE
────────────
  Intake Contract:  ResearchQuestionContract scopes the search space
  DAG 1:            Candidate Claim Discovery and Novelty Adjudication
  DAG 2:            Evidence Accumulation and Claim Verification (4 waves)

LAYER 1: CORE ENTITIES (19 types)
─────────────────────────────────
  Molecular:     Gene, Protein, Variant
  Functional:    Pathway, BiologicalProcess, MolecularFunction, CellularComponent
  Context:       CellType, ImmuneFunctionalState, TMECompartment, Anatomy
  Disease:       CancerType, Disease, TherapyRegimen, Compound
  Experimental:  CellLine, Study, Cohort
  Structural:    ProteinDomain, ProteinFamily, EC, Reaction
  Genomic:       Neoantigen, HLAAllele

LAYER 2: CLAIMS (24 types, 3 orthogonal axes)
──────────────────────────────────────────────
  Types: Essentiality, Perturbation, Regulatory, Immune, Expression,
         Correlation, Clinical, Compound, Meta (see ClaimType enum)

  THREE ORTHOGONAL AXES on every claim:
    evidence_status:   draft → observed → replicated → causal → mechanistic → externally_supported
    prior_art_status:  unsearched | canonical | related_prior_art | context_extension |
                       evidence_upgrade | plausibly_novel | ambiguous
    review_status:     clean | in_review | contradicted | superseded | needs_experiment

  5D uncertainty:
    1. Statistical (p/q/CI/test_type)
    2. Predictive (fold_variance/bootstrap/CV_R²)
    3. Provenance (dataset_quality/assay_quality)
    4. Reproducibility (n_studies/n_lineages/n_modalities/direction_consistency)
    5. Publication authority (n_tier1_papers/n_perturbation/authority_level)

LAYER 3: EVIDENCE (8 types)
───────────────────────────
  Dataset, Assay, StatisticalTest, ModelRun,
  PerturbationExperiment, ReplicationSet, LiteratureSupport, Artifact

LAYER 4: LOGIC
──────────────
  SupportSet:        AND-group of evidence (multiple SupportSets = OR logic)
  ContradictionCase: Biology-native contradiction with classification:
                       entity_mismatch | assay_mismatch | context_split | true_frontier
                     Resolution: open → narrowed | resolved | halted

DAG 2 WAVES (Hypothesis Proving)
─────────────────────────────────
  Wave 1: Association (L1+L2) — in vitro + tumor multiomics
  Wave 2: External Validation (L3) — replication + literature + textbook gate
  Wave 3: Causation (L4+L5) — LOF, GOF, rescue
  Wave 4: Orthogonal Consequence (L6+L7) — mechanism + function + clinical

  Hard gates:  claim escalation (observed→replicated→causal→mechanistic)
  Soft gates:  enrichment (extra cohorts, clinical, microscopy)

EVIDENCE FAMILIES (pluggable providers)
────────────────────────────────────────
  in_vitro_association, tumor_multiomics, external_replication,
  human_genomic_outcome, perturbation, mouse_organismal,
  orthogonal_phenotype, functional_consequence, literature,
  foundation_model (auxiliary only)

HYPOTHESIS-LEVEL VERDICT
─────────────────────────
  INSUFFICIENT:        No robust association
  OBSERVED:            Wave 1 passed only
  REPLICATED:          Wave 2 passed, no causal support
  VALIDATED:           Cross-modality or independent agreement
  SUPPORTED:           Necessity or sufficiency + ≥1 orthogonal/consequence
  STRONGLY_SUPPORTED:  Both necessity and sufficiency + orthogonal + functional
  CONTRADICTED:        Dominant evidence opposes or unresolved contradiction

MANDATORY RULES
────────────────
  1. No node may emit a free-text conclusion without ≥1 StudyResult
  2. No multi-study summary without pooled meta-analysis
  3. No claim promotion without KG write-back
  4. No Wave 3/4 escalation while contradictions remain unresolved
  5. No wet-lab proposal without a named public-data gap
  6. No verdict without a machine-readable L1-L7 coverage map
"""


def print_ontology():
    """Print the full ontology for review."""
    print(ONTOLOGY_SUMMARY)
