# Claim object — complete architecture

This is the field-by-field reference for the **claim object**: the
atomic unit of work in the system. DAG 1 emits claims, DAG 2 proves
them, the KG stores them. Every belief in the system is one row in
the `claims` table, augmented at runtime with parsed ontology and a
view over the result graph.

The doc has two halves:

- **Part A — Fields.** Every column on the `claims` table; every
  Pydantic class in the typed-ontology layer; every enum.
- **Part B — Tree structure.** How claims connect to *other* claims
  (refinement, decomposition, competition, supersession, contradiction)
  and to the participants / evidence / contexts that scope them.

---

## Architecture in one picture

After Part X (April 2026), `CandidateClaim` and `Claim` collapsed into
a single dataclass: a "candidate" is just a `Claim` row with
`evidence_status = DRAFT` and the typed ontology attached as transient
runtime decoration. The three "layers" below describe **stages of the
same row's life**, not three separate types.

```
                            ┌──────────────────────────────┐
                            │  KG (entities + backbone     │
                            │       edges)  +  Literature  │
                            └──────────────┬───────────────┘
                                           │
                run_literature_grounded_hypothesis_generation()
                                           │
                                           ▼
        ┌──────────────────────────────────────────────────────────┐
        │  Stage 1: Claim row (DRAFT)                              │
        │  ─ candidate_id == claim_id                              │
        │  ─ claim_text, candidate_gene/participants               │
        │  ─ DAG-1 ranking: novelty, tractability, kg_connectivity │
        │  ─ source: kg_traversal | literature_gap | contradiction │
        └──────────────────────────┬───────────────────────────────┘
                                   │
                            analyze_claim()
                       (parse → typed ontology)
                                   │
                                   ▼
        ┌──────────────────────────────────────────────────────────┐
        │  Stage 2: Claim row + ClaimReasoning attached            │
        │  ─ structured_claim_json persisted                       │
        │  ─ structured_claim, causal_chain,                       │
        │    competing_explanations, mechanism_hypotheses          │
        │    attached as TRANSIENT decoration (not on disk)        │
        └──────────────────────────┬───────────────────────────────┘
                                   │
                             DAG-2 waves:
              observe → replicate → perturb → mechanise →
                          externally_support
                                   │
                                   ▼
        ┌──────────────────────────────────────────────────────────┐
        │  Stage 3: Claim row, fully evidenced                     │
        │  ─ axes promoted along hard gates                        │
        │  ─ confidence_summary recomputed from result graph       │
        │  ─ children, contradictions, competitors, supersedence   │
        │    materialised as separate Claim rows + edges           │
        └──────────────────────────────────────────────────────────┘
```

Below is every field, every enum, every relation.

---

# Part A — Fields

## A.1 The persisted `Claim` row

Schema: `gbd/knowledge_graph/schema.py`. SQLite DDL: `schema/table_schemas.sql`
(table `claims`, 56 columns post-Phase-T).

### A.1.1 Identity

| Field | Type | Notes |
|---|---|---|
| `claim_id` | `str` PRIMARY KEY | canonical id |
| `candidate_id` | `str` | filled to `claim_id` when none provided (Part X collapse) |
| `claim_type` | `ClaimType` | see §A.5 |
| `claim_text` | `str` | atomic statement in natural language |
| `human_readable` | `str` | one-liner for logs / reports |
| `edge_signature` | `str` | `SHA256(subject_node_id|relation_name|object_node_id)`; cross-source dedup primitive (polarity intentionally excluded — opposite-polarity claims with the same subject/relation/object are *the same biological assertion under contention* and route to a `stance="contradicts"` SupportSet) |
| `created_at` / `created_by` | `str` / `str` | provenance metadata |

### A.1.2 Typed assertion

| Field | Type | Notes |
|---|---|---|
| `relation_name` | `str` | typed predicate from `relation_registry.py` (e.g. `destabilizes`, `phosphorylates`, `represses`); empty on composites |
| `relation_polarity` | `str` | `positive` \| `negative` \| `bidirectional` \| `null` \| `unknown` |
| `direction` | `str` | DERIVED from `relation_polarity` in `__post_init__`; legacy presentation field, do not pass in new code |
| `effect_size` | `float` | aggregated only; per-result effects live on `BiologicalResult` |
| `effect_unit` | `str` | `CERES` / `log2FC` / `Pearson_r` / `hazard_ratio` / … |

### A.1.3 The three orthogonal axes (KG §4)

Independent categorical tags. Together they say *how mature*, *how
novel*, and *how clean* the claim is — without collapsing those
dimensions into one number.

| Field | Type / enum | Values |
|---|---|---|
| `evidence_status` | `EvidenceStatus` | `draft` → `observed` → `replicated` → `causal` → `mechanistic` → `externally_supported` |
| `prior_art_status` | `PriorArtStatus` (nested under `prior_art`) | `unsearched` \| `canonical` \| `related_prior_art` \| `context_extension` \| `evidence_upgrade` \| `plausibly_novel` \| `ambiguous` |
| `review_status` | `ReviewStatus` | `clean` \| `in_review` \| `contradicted` \| `superseded` \| `needs_experiment` |
| `proof_level` | `ProofLevel` (`int` enum) | `1` ontology_fact \| `2` observational_association \| `3` model_prediction \| `4` perturbational_molecular \| `5` perturbational_phenotypic \| `6` orthogonal_reproduction \| `7` published_established |

A claim can be `replicated + plausibly_novel + clean` (a strong, novel
finding) or `causal + canonical + clean` (a successful replication of
known biology) — both are useful, one drives discovery, one calibrates.

### A.1.4 Participants & context (canonical projection)

| Field | Type | Notes |
|---|---|---|
| `participants` | `list[ClaimParticipant]` | canonical participants — see §A.3 |
| `context_operator` | `str` | `AND` \| `OR` — how participants combine |
| `participant_combinator` | `str` | `AND` \| `OR` — combinator on the SUBJECT/EFFECTOR side when there are >1 entities (Part X §56.3) |
| `cell_states_json` | `str` (JSON) | persisted projection of `StructuredClaim.cell_states` |
| `context_set_json` | `str` (JSON) | typed-graph projection of `gbd.core.context_provenance.ContextSet`; queryable via ancestor traversal |
| `candidate_gene` | `str` | HGNC symbol; legacy fast-index field (read `participants[role=EFFECTOR]` in new code) |
| `candidate_nodes` | `list` | legacy multi-entity field; mapped into `participants` in `__post_init__` if `participants` is empty |
| `phenotype` | `PhenotypeDefinition \| None` | legacy free-form phenotype object kept for readers (paper.py, report.py, …) |
| `context` | `dict[str, str]` | legacy free-form context dict; new code reads `context_set_json` |

### A.1.5 Provenance

| Field | Type | Notes |
|---|---|---|
| `source_dataset` | `str` | e.g. `DepMap_24Q2` / `GSE91061` / `CPTAC_PDC000127` |
| `source_release` | `str` | dataset release tag |
| `assay_type` | `str` | `CRISPR_Chronos` / `RNA-seq` / `mass_spec` / … |
| `model_name` / `model_version` | `str` / `str` | `ElasticNet`, `DerSimonian-Laird`, … |
| `artifact_id` | `str` | hash of raw data that produced this |
| `source` | `str` | `kg_traversal` \| `literature_gap` \| `contradiction_gap` |
| `kg_evidence` | `list[str]` (JSON) | backbone-edge IDs that suggested this claim |
| `kg_suggested` | `bool` | True if suggested by KG traversal |

### A.1.6 DAG-1 ranking (was on `CandidateClaim` pre-Part-X)

All `None` until DAG 1 has ranked the candidate. **`None` ≠ `0.0`** —
`None` means "not yet ranked", `0.0` means "ranked, score is zero".

| Field | Type | Notes |
|---|---|---|
| `novelty_score` | `float \| None` | 0 = textbook, 1 = completely novel — drives ranking |
| `tractability_score` | `float \| None` | data availability at proof levels 1–3 |
| `kg_connectivity_score` | `float \| None` | KG structural support |
| `priority_score` | `float \| None` | composite sort key (sourced from `claim_rankings` table) |

### A.1.7 Cross-evidence aggregates (Axis-4)

Per-result statistics live on `BiologicalResult`; the claim only
records aggregate reproducibility.

| Field | Type | Notes |
|---|---|---|
| `n_studies` | `int` | independent studies |
| `n_modalities` | `int` | independent modalities |
| `direction_consistency` | `float` | fraction of studies with same direction (renamed → `polarity_consistency` in Part II) |

### A.1.8 Publication authority (Axis-5)

| Field | Type | Notes |
|---|---|---|
| `publication_support` | `PublicationSupport \| None` | nested object with all paper-level evidence — see §A.4 |
| `prior_art` | `PriorArt` | nested LLM-context-economy view: status + pmids + reasoning + n_papers |

### A.1.9 Hierarchy / refinement / context-split

Three reasons a claim has a parent — see §B.1 for tree structure.

| Field | Type | Notes |
|---|---|---|
| `parent_claim_id` | `str` | single link to the parent |
| `refinement_type` | `str` | `narrow` \| `branches_from` \| `pivot` \| `expand` \| `""` |
| `refinement_rationale` | `str` | LLM rationale for the refinement |
| `refinement_confidence` | `float \| None` | judge confidence in the refinement |
| `splits_on_dimension` | `str` | `"residue"` / `"cell_type"` / … when born from a context split (P9 splitter) |
| `is_general` | `bool` | True on a parent that has been split into children |
| `target_mechanism_ids` | `list[str]` | claim-ids of mechanism subgraph M(c) |
| `inherited_evidence_ids` | `list[str]` | evidence inherited from a more-general parent |
| `tools_to_prioritise` | `list[str]` | planner hint, regenerable from claim |
| `cancer_type_scope` | `str` | narrowed type from `RefinedClaim` |
| `embedding_text` | `str` | text used to compute the claim embedding |

### A.1.10 Supersession & contradiction

| Field | Type | Notes |
|---|---|---|
| `superseded_by` | `str` | `claim_id` that replaces this one |
| `contradiction_case_ids` | `list[str]` | open or resolved `ContradictionCase` ids |

### A.1.11 Persisted parse output

| Field | Type | Notes |
|---|---|---|
| `structured_claim_json` | `str` (JSON) | serialised `StructuredClaim` produced by `analyze_claim()` — persisted to `claims.full_data` |

### A.1.12 Transient runtime decoration

These fields are **not** persisted to SQL. They carry live Python
objects used by DAG 2 mid-run. `to_kg_row()` excludes them; `repr=False`
keeps them out of `dataclass.__repr__`; `compare=False` keeps them out
of equality so two `Claim`s with the same persisted state compare equal
regardless of attached caches.

| Field | Type | Notes |
|---|---|---|
| `structured_claim` | `StructuredClaim` | the parsed ontology, see §A.2 |
| `causal_chain` | `CausalChain` | typed perturbation→consequence→phenotype→relevance |
| `competing_explanations` | `list[CompetingExplanation]` | biology-native alternative explanations |
| `mechanism_hypotheses` | `list[MechanismHypothesis]` | granular "how" hypotheses |
| `literature_profile` | `CandidateLiteratureProfile` | DAG-1 grounding |
| `kg_context` | `dict` | enriched KG facts about the participants |
| `children_claim_ids` | `list[str]` | downward links materialised at runtime |
| `_hypothesis_context` | `HypothesisContext` | bridge to DAG-2 planner |
| `_claim_reasoning_obj` | `ClaimReasoning` | bundled output of `analyze_claim()` |
| `_evidence_profile` | `dict` | runtime evidence-coverage cache |

`_TRANSIENT_FIELDS` is a `frozenset` constant on the dataclass listing
exactly these names so the persistence helper can never accidentally
write them.

---

## A.2 Typed ontology — `ClaimReasoning`

Source: `gbd/core/claim_ontology.py`. Produced by `analyze_claim()` in
`gbd/core/claim_reasoning.py`. Persisted as `structured_claim_json`;
attached at runtime as `_claim_reasoning_obj`.

### A.2.1 `ClaimReasoning`

```python
class ClaimReasoning(BaseModel):
    ontology:               StructuredClaim
    evidence_strategy:      EvidenceRelevanceMap
    competing_explanations: list[CompetingExplanation]
    causal_chain:           CausalChain | None
    mechanism_hypotheses:   list[MechanismHypothesis]
```

### A.2.2 `StructuredClaim`

| Field | Type | Notes |
|---|---|---|
| `entity` | `str` | HGNC symbol or pathway name |
| `entity_id` | `str` | resolved KG `entity_id` (populated post-parse) |
| `entity_type` | `EntityCategory` | `gene` \| `protein` \| `protein_complex` \| `pathway` \| `cell_population` \| `metabolite` \| `epigenetic_mark` \| `immune_state` |
| `alteration` | `AlterationType` | 16-value enum — see §A.5 |
| `alteration_detail` | `str` | free-text disambiguator from the LLM |
| `phenotype_statement` | `str` | "resistance to anti-PD1 therapy" |
| `phenotype_direction` | `str` | `increased` \| `decreased` \| `abolished` |
| `relation_name` | `str` | typed predicate (canonical or LLM-proposed via `propose_relation()`) |
| `relation_polarity` | `str` | `positive` \| `negative` \| `bidirectional` \| `null` \| `unknown` |
| `context` | `ClaimContext` | full biological context — see §A.2.3 |
| `cell_states` | `list[CellStateCondition]` | conditional cell-state qualifiers — see §A.2.4 |
| `latent_state` | `LatentBiologicalState \| None` | the underlying biology vs. what assays measure — see §A.2.5 |
| `parse_confidence` | `float` ∈ [0, 1] | LLM self-rated parse quality |
| `parse_ambiguities` | `list[str]` | residual ambiguities the parser flagged |

### A.2.3 `ClaimContext`

| Field | Type | Notes |
|---|---|---|
| `tissue` | `str` | free-text |
| `cell_type` | `str` | free-text (canonical lookup is `mechanism_location.cell_type_id`) |
| `treatment_condition` | `str` | drug, cytokine, perturbation context |
| `timepoint` | `str` | hour-, day-, stage-resolved |
| `species` | `str` | default `"Homo sapiens"` |
| `disease` | `str` | indication |
| `microenvironment` | `str` | `tumor_core`, `invasive_margin`, … |
| `effector_compartment` | `EffectorCompartment` | `tumor_intrinsic` \| `immune_effector` \| `myeloid` \| `stromal` \| `multi_compartment` \| `unknown` — coarse routing fast-path |
| `compartment_entity_id` | `str` | canonical `entity_id` (`CL:0000084`, `UBERON:0002048`, `GO:0005886`, or `FT:<slug>` fallback) — DEPRECATED in Phase H, superseded by `mechanism_location` |
| `mechanism_location` | `MechanismLocation` | six-axis structured "where" — see §A.2.6 |
| `target_mechanism_location` | `MechanismLocation \| None` | for inter-cellular claims (LIGAND_RECEPTOR, JUXTACRINE, SECRETED_PARACRINE) — `mechanism_location` carries SOURCE, this carries TARGET |
| `mechanism_profile` | `MechanismProfile \| None` | LLM-derived snapshot for routing/narrative |
| `immune_cell_subtype` | `ImmuneCellSubtype` | 17-value enum — see §A.5 |
| `immune_cell_subtype_reasoning` | `str` | LLM justification for the subtype assignment |
| `valid_in_lineages` | `list[str]` | lineages where the claim holds |
| `not_valid_in` | `list[str]` | lineages where it doesn't |

### A.2.4 `CellStateCondition`

| Field | Type | Notes |
|---|---|---|
| `state_type` | `CellStateType` | `immune_functional` \| `cytokine_exposure` \| `stromal_state` \| `tumour_state` \| `metabolic` \| `differentiation` \| `cell_cycle` \| `stress_response` \| `activation_state` \| `other` |
| `state_name` | `str` | `"exhausted"`, `"IFNγ_exposed"`, `"senescent_CAF"` |
| `description` | `str` | free-text nuance |
| `is_required` | `bool` | must the cell be in this state for the claim to hold? |
| `markers` | `list[str]` | e.g. `["PD1+", "TIM3+", "TOX+"]` |
| `evidence_for_state` | `str` | how to verify cells are in this state (flow panel, IHC, phospho-Western, …) |

Multiple `CellStateCondition`s with `is_required=True` are **AND-combined**
(compound state: "exhausted CD8 + IFNγ-exposed").

### A.2.5 `LatentBiologicalState`

The bridge between "what the biology actually is" and "what an assay
can observe."

| Field | Type | Notes |
|---|---|---|
| `primary_layer` | `BiologicalLayer` | `genomic` \| `epigenomic` \| `transcriptomic` \| `post_transcriptional` \| `translational` \| `proteomic` \| `post_translational` \| `localization` \| `functional` \| `cell_composition` \| `organismal` |
| `state_description` | `str` | e.g. "B2M protein absent from tumor cell surface" |
| `possible_upstream_causes` | `list[UpstreamCause]` | ranked by prior frequency |
| `decisive_observations` | `list[AssayRelevance]` | directly observe the state |
| `supportive_observations` | `list[AssayRelevance]` | consistent but not proof |
| `proxy_observations` | `list[AssayRelevance]` | correlated, not the state itself |

`UpstreamCause`: `cause_layer`, `description`, `distinguishing_assay`,
`prior_frequency` ∈ {`common`, `uncommon`, `rare`, `unknown`}.

`AssayRelevance`: `assay_type`, `relevance` (`EvidenceRelevanceLevel`),
`reasoning`, `what_it_actually_measures`, `failure_modes: list[str]`.
The `what_it_actually_measures` field is what lets the planner
distinguish "mRNA abundance" from "protein surface level" when the
claim is about localisation.

### A.2.6 `MechanismLocation` — six orthogonal axes

Replaces the legacy 6-value `EffectorCompartment` enum + free-text
`compartment_entity_id` as the canonical "where" field. Each axis is
optional; empty means "unconstrained on that axis".

| Axis | Field | Namespace |
|---|---|---|
| 1. Subcellular site | `subcellular_site_ids: list[str]` | `GO:` \| `FT:` |
| 2. Cell type | `cell_type_id: str` | `CL:` \| `FT:` |
| 3. Cell state | `cell_state_id: str` | `CELL_STATE:` \| `FT:` |
| 4. Tissue / anatomical site | `tissue_id: str` | `UBERON:` \| `FT:` |
| 5. (more axes — treatment / lineage / disease) | … | … |

The entity resolver normalises free-form values to `FT:<slug>`;
established vocabularies (`CL:0000084`, `UBERON:0002048`, `GO:0005886`)
pass through unchanged.

### A.2.7 `MechanismHypothesis` — granular "how"

| Field | Type | Notes |
|---|---|---|
| `hypothesis_id` | `str` | `MH-1`, `MH-2`, … |
| `title` | `str` | short label (e.g. `"RBMS1-3'UTR-IFNB1"`) |
| `mediator_entity` | `str` | the proposed molecular intermediary |
| `interaction_type` | `str` | `binds_3utr` / `sequesters_mrna` / `phosphorylates` / `blocks_nuclear_translocation` / `induces_lineage_shift` / … |
| `proposed_mechanism` | `str` | 1–3 sentence molecular story |
| `predicted_signature` | `str` | what we'd expect to see in DATA |
| `distinguishing_assay` | `str` | the assay that DISCRIMINATES this from siblings |
| `falsification_criterion` | `str` | what result would falsify it |
| `prior_plausibility` | `str` | `high` \| `moderate` \| `low` |
| `layer` | `BiologicalLayer` | which layer the mechanism primarily operates at |
| `evidence_status` | `str` | `unverified` \| `supported` \| `refuted` \| `inconclusive` |
| `supporting_result_ids` | `list[str]` | from the wave loop |
| `refuting_result_ids` | `list[str]` | from the wave loop |

### A.2.8 `CompetingExplanation`

| Field | Type | Notes |
|---|---|---|
| `explanation_id` | `str` | identifier within the parent claim |
| `category` | `CompetingExplanationCategory` | 17-value biology-native confound enum (`tumor_purity_artifact`, `immune_infiltration_confound`, `batch_effect`, `cnv_driven_expression`, `proliferation_confound`, …) |
| `description` | `str` | what the alternative is |
| `how_to_test` | `str` | concrete probe |
| `how_to_rule_out` | `str` | criteria for elimination |
| `prior_plausibility` | `str` | `high` / `moderate` / `low` |
| `status` | `str` | `untested` \| `excluded` \| `plausible` \| `confirmed` |
| `test_result_ids` | `list[str]` | from the wave loop |
| `ruling_reasoning` | `str` | LLM rationale once the alternative is resolved |

### A.2.9 `CausalChain` and `CausalChainLink`

The four canonical levels: `perturbation` → `molecular_consequence` →
`cellular_phenotype` → `human_relevance`. Each is a `CausalChainLink`,
optionally augmented by `intermediate_steps`.

```python
class CausalChainLink(BaseModel):
    step: int
    layer: BiologicalLayer
    entity: str                          # free-text label
    entity_id: str = ""                  # resolved KG entity_id
    state_change: str                    # "B2M frameshift → protein truncation"
    evidence_required: str               # what would prove this step
    evidence_status: str = "unverified"  # unverified | supported | contradicted
    supporting_result_ids: list[str]
    supporting_pmids: list[str]
    claim_id: str = ""                   # = f"{composite_id}__link-{step}"
    parent_composite_claim_id: str = ""
    is_canonical_backbone: bool = True   # the 4 canonical levels are backbone
```

Each link is **also** persisted as a first-class `Claim` of type
`CAUSAL_CHAIN_LINK` with `parent_claim_id = parent_composite_claim_id`
— see §B.2 for the decomposition tree.

`CausalChain` derived properties:
- `all_links` — sorted by `step`
- `completeness` — fraction of canonical links with `evidence_status == "supported"`
- `weakest_link` — the canonical step with the weakest evidence

### A.2.10 `EvidenceRelevanceMap`

```python
class EvidenceRelevanceMap(BaseModel):
    claim_id: str
    provider_relevance: dict[str, ProviderRelevance]
```

Each `ProviderRelevance` carries `provider_type`, `relevance`
(`EvidenceRelevanceLevel`), `reasoning`, `what_positive_means`,
`what_negative_means`, `failure_modes`. Helpers:
`decisive_providers()`, `supportive_providers()`, `proxy_providers()`,
`misleading_providers()`, `get_tier(provider_type)`.

The wave executor reads this map to decide which providers to call,
in what order, and whether a null result counts.

---

## A.3 Participants — `ClaimParticipant` and `ParticipantRole`

```python
@dataclass
class ClaimParticipant:
    entity_id: str
    role: ParticipantRole
    properties: dict[str, Any]
```

### Six structural roles (Part X §55.2 — preferred)

| Role | Cardinality | Meaning |
|---|---|---|
| `SUBJECT` | exactly 1 per leaf | leaf principal subject |
| `OBJECT` | exactly 1 per leaf | leaf principal object |
| `EFFECTOR` | ≥ 1 per composite | composite principal subject |
| `OUTCOME` | ≥ 1 per composite | composite principal object |
| `MEDIATOR` | any | intermediate participant; not principal |
| `CONTEXT` | any | conditional participant — narrows when claim holds |

`participant_combinator` (`AND` \| `OR`) on the `Claim` distinguishes
conjunctive co-requirement from disjunctive redundancy when a side has
>1 entity.

### Legacy 16-value roles (deprecated; aliases)

`EFFECTOR_GENE`, `TARGET_GENE`, `CONTEXT_MUTATION`,
`CONTEXT_CANCER_TYPE`, `CONTEXT_CELL_TYPE`, `CONTEXT_IMMUNE_STATE`,
`CONTEXT_CELL_STATE`, `CONTEXT_THERAPY`, `CONTEXT_CELL_LINE`,
`PHENOTYPE_GENE`, `PATHWAY`, `COMPOUND`, `CONFOUNDER`, `REGULATOR_TF`,
`REGULATEE`, `MEDIATOR`. Translated by `normalize_role(claim_shape, role)`
into the six structural values; never used in new code. Entity type is
read from the `entity_id` namespace prefix (`HGNC:`, `DRUG:`, `MONDO:`,
`COMPLEX:`, `GO:`, `CL:`, `UBERON:`, `PWY:`, `FT:`), not encoded in the
role.

---

## A.4 Publication authority — `PublicationSupport`

Aggregated paper-level evidence (Axis-5 of uncertainty).

| Field | Type | Notes |
|---|---|---|
| `publications` | `list[PublicationEvidence]` | individual paper rows |
| `n_total_articles` | `int` | total found |
| `n_direct_evidence` | `int` | direct mechanism + phenotype |
| `n_tier1_papers` | `int` | Nature, Science, Cell, NEJM, Lancet |
| `n_tier2_papers` | `int` | Nature Genetics / Nature Medicine / Cancer Cell / Immunity tier |
| `n_tier3_papers` | `int` | PNAS / JCI / eLife / Genome Biology tier |
| `n_with_perturbation` | `int` | KO/KD/OE-supporting |
| `n_with_clinical` | `int` | patient-data-supporting |
| `n_supporting` / `n_contradicting` | `int` / `int` | direction of paper-level claim |
| `authority_level` | `str` | `established` \| `well_supported` \| `moderately_supported` \| `weakly_supported` \| `novel` \| `contradicted_in_literature` |
| `authority_score` | `float` | composite 0–1 |
| `authority_note` | `str` | human-readable explanation |
| `novelty` | `str` | `HIGH` \| `MODERATE` \| `LOW` (inverse of authority) |
| `n_queries_run` / `search_date` / `search_exhaustive` | provenance | how the lit search was done |

Authority levels are computed by `compute_authority()`:
- `established` ≥ 3 tier-1/2 with direct evidence + ≥ 1 with perturbation
- `well_supported` ≥ 2 tier-1/2 OR ≥ 3 direct + perturbation
- `moderately_supported` ≥ 2 direct OR ≥ 1 tier-1/2
- `weakly_supported` ≥ 1 direct OR ≥ 3 total
- `contradicted_in_literature` ≥ 2 contradicting AND contradicting ≥ supporting
- `novel` otherwise

### `PriorArt` (nested view)

Compact LLM-context-economy projection of prior-art bookkeeping —
returned by `Claim.prior_art_view()`:

```python
@dataclass
class PriorArt:
    status:    PriorArtStatus
    pmids:     list[str]
    reasoning: str
    n_papers:  int
```

The flat fields stay on `Claim`; the nested form exists so prompts
don't carry 50+ PMIDs at the top level by default.

---

## A.5 Enums (one place)

### `ClaimType` — what the claim asserts

40+ values; full list in `schema/schema.py` (already exported in this
repo). Organised by family:

`Essentiality` (3) | `Perturbation` (2) | `Regulatory` (3) |
`Immune` (3) | `Expression / localization` (4) | `Genomic` (2) |
`Multi-omics (CPTAC)` (5) | `Inferred activity` (4) |
`Advanced dependency (DepMap)` (5) | `Correlation / association` (3) |
`Clinical` (3) | `Compound` (2) | `Meta` (5) |
`Composite decomposition` (1: `CAUSAL_CHAIN_LINK`).

### `EvidenceStatus`, `PriorArtStatus`, `ReviewStatus`, `PublicationStatus`

Documented in §A.1.3 above. Promotion rules in §B.5.

### `ProofLevel` (1–7)

Ontology fact (1) → Observational association (2) → Model prediction
(3) → Perturbational molecular (4) → Perturbational phenotypic (5)
→ Orthogonal reproduction (6) → Published / established (7).

### `AlterationType` (16 values)

```
GENOMIC_DELETION       GENOMIC_AMPLIFICATION   TRUNCATING_MUTATION
MISSENSE_MUTATION      EPIGENETIC_SILENCING    TRANSCRIPTIONAL_UP
TRANSCRIPTIONAL_DOWN   POST_TRANSCRIPTIONAL_LOSS  TRANSLATIONAL_FAILURE
PROTEIN_DEGRADATION    PROTEIN_MISLOCALIZATION CELL_POPULATION_LOSS
GAIN_OF_FUNCTION_MUTATION  PHOSPHORYLATION_CHANGE  OVEREXPRESSION
UNKNOWN
```

Disambiguates "B2M loss" between four mechanistically different
claims, each requiring different evidence.

### `BiologicalLayer` (11 values)

`genomic` | `epigenomic` | `transcriptomic` | `post_transcriptional` |
`translational` | `proteomic` | `post_translational` | `localization`
| `functional` | `cell_composition` | `organismal`.

### `EvidenceRelevanceLevel` (5 values)

| Level | Meaning |
|---|---|
| `DECISIVE` | directly observes the asserted state — pass/fail rests on this |
| `SUPPORTIVE` | consistent with the claim, not proof on its own |
| `PROXY` | correlated, doesn't measure the state itself |
| `IRRELEVANT` | this assay cannot address this claim |
| `MISLEADING` | this assay may give the *wrong* answer (e.g. wrong compartment) |

### `EntityCategory` (8 values)

`gene` | `protein` | `protein_complex` | `pathway` | `cell_population`
| `metabolite` | `epigenetic_mark` | `immune_state`.

### `EffectorCompartment` (6 values)

`tumor_intrinsic` | `immune_effector` | `myeloid` | `stromal`
| `multi_compartment` | `unknown`. **Determined dynamically by LLM**
at parse time, not from a hardcoded gene→compartment lookup. The same
gene can operate in different compartments depending on context.

### `ImmuneCellSubtype` (17 values)

T-cell: `cd8_cytotoxic` | `cd8_exhausted` | `cd8_memory` | `cd4_helper`
| `cd4_treg` | `gamma_delta_t` | `nkt`. NK: `nk_cytotoxic` |
`nk_regulatory`. Myeloid: `macrophage_m1` | `macrophage_m2` |
`dendritic_cdc` | `dendritic_pdc` | `mdsc` | `monocyte`. Mixed:
`mixed_cd4_cd8` | `unresolved`.

`EffectorCompartment` controls **data-source routing**;
`ImmuneCellSubtype` controls **biological interpretation** (FOXA3 in
Tregs vs. CD8 effectors are opposite biological claims even though
both route to immune assays).

### `CellStateType` (10 values)

`immune_functional` | `cytokine_exposure` | `stromal_state` |
`tumour_state` | `metabolic` | `differentiation` | `cell_cycle` |
`stress_response` | `activation_state` | `other`.

### `CompetingExplanationCategory` (17 values)

Biology-native confounds: `cell_composition_shift` |
`tumor_purity_artifact` | `immune_infiltration_confound` |
`batch_effect` | `platform_artifact` | `treatment_history_confound` |
`clonality_effect` | `survivorship_bias` | `cytokine_coregulation` |
`lineage_restriction` | `temporal_confound` | `selection_bias` |
`measurement_ceiling_floor` | `gene_length_bias` |
`cnv_driven_expression` | `proliferation_confound` | `other`.

### `JournalTier` (6 values)

`tier1` (Nature, Science, Cell, NEJM, Lancet) | `tier2` (Nature
Genetics, Cancer Cell, Immunity) | `tier3` (PNAS, JCI, eLife) |
`tier4` (PLoS Genetics, NAR, Oncogene) | `tier5` | `preprint`
(bioRxiv, medRxiv).

### `NodeTypeInClaim` and `NodeRoleInClaim`

Already public in `schema/schema.py`. Mirrors `EntityCategory`
(Layer-1) and `ParticipantRole` (Layer-2) respectively but lives on
`CandidateNode` so the DAG-2 entry contract doesn't import the full
core schema.

---

# Part B — Tree structure

A claim is never a standalone object. It sits in **five overlapping
graphs**, each with its own edge type:

1. **Refinement / decomposition tree** — `parent_claim_id` (single parent, many children)
2. **Composite ↔ chain-link tree** — `parent_composite_claim_id` (special case via `CAUSAL_CHAIN_LINK`)
3. **Competition graph** — `COMPETES_WITH` edges (declared, can be many-to-many)
4. **Supersession chain** — `superseded_by` (single forward link)
5. **Contradiction registry** — `contradiction_case_ids` ↔ `ContradictionCase` rows

Plus the **participant graph** (claim ↔ entity, scoped by role) and
the **result graph** (claim ↔ `BiologicalResult`, via `SupportSet`s
that AND/OR over individual results).

## B.1 Refinement / decomposition tree

A claim has a parent for **three reasons**, distinguished by
`refinement_type`:

| `refinement_type` | Reason | Example |
|---|---|---|
| `narrow` | a more general claim was made specific | "B2M loss → ICB resistance" → "B2M frameshift in melanoma → anti-PD1 resistance" |
| `branches_from` | a child explores a sibling hypothesis | "Mechanism A: protein degradation" vs "Mechanism B: surface mislocalisation" |
| `pivot` | the claim's subject changed after evidence pushed elsewhere | "Hypothesis: STK11 drives X" → pivot → "Hypothesis: KEAP1 drives X" |
| `expand` | a sibling adds a context / participant the parent lacked | "X drives resistance" → "X drives resistance + requires IFNγ co-stimulation" |
| `""` (empty) | this is a root claim | DAG-1 emission, no parent |

A claim flagged `is_general=True` is a placeholder parent that has
been split into children — `splits_on_dimension` records the axis the
split was made on (`"residue"`, `"cell_type"`, `"cancer_type"`, …).

```
                     Claim "X reduces Y in solid tumors"
                       (is_general=True, splits_on_dimension="cancer_type")
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
  refinement_type=  refinement_type=  refinement_type=
  "narrow"          "narrow"          "narrow"
  cancer_type_scope=  cancer_type_scope=  cancer_type_scope=
   "melanoma"        "colon"            "lung"
```

`inherited_evidence_ids` lets a child claim re-use a parent's evidence
without copying it.

## B.2 Composite ↔ causal-chain-link tree

When a `CausalChain` is persisted, its 4 canonical links + any
intermediates are **each materialised as a separate Claim row** of
type `CAUSAL_CHAIN_LINK`. The composite parent links to them via
`target_mechanism_ids`; each link points back via `parent_claim_id`
and `parent_composite_claim_id`.

```
   composite Claim
   claim_type = (e.g.) PERTURBATION_SIGNATURE
   target_mechanism_ids = [<id>__link-1, <id>__link-2,
                            <id>__link-3, <id>__link-4]
        │
        ├── Claim claim_id="<id>__link-1"  type=CAUSAL_CHAIN_LINK
        │       parent_claim_id = <composite>
        │       parent_composite_claim_id = <composite>
        │       is_canonical_backbone = True
        │       step = 1, layer = GENOMIC
        │
        ├── Claim claim_id="<id>__link-2"  type=CAUSAL_CHAIN_LINK
        │       step = 2, layer = PROTEOMIC
        │
        ├── Claim claim_id="<id>__link-3"  step=3, layer=FUNCTIONAL
        │
        └── Claim claim_id="<id>__link-4"  step=4, layer=ORGANISMAL
```

Why decompose? Sibling sbatches can lock supported links and surgically
re-test only the under-determined or contradicted ones (`weakest_link`
points at which). Each link claim has its own `evidence_status` and
its own `BiologicalResult`s.

## B.3 Competition graph

Two claims that *would explain the same observations* are linked by
`COMPETES_WITH`. Unlike contradictions (open vs. resolved), competitors
are simultaneously evaluated and the system maintains a posterior
distribution over them.

```
    Claim A "RBMS1 destabilises IFNG mRNA via 3'UTR binding"
       │
       │  COMPETES_WITH
       │
    Claim A' "RBMS1 acts via TRIM25 ubiquitination of MAVS"
       │
       │  COMPETES_WITH
       │
    Claim A'' "RBMS1 phenotype is purity confound, not mechanism"
```

Each `MechanismHypothesis` and each `CompetingExplanation` are
candidate competitors — the planner promotes them to first-class Claim
rows when they earn enough evidence to be tested independently.

## B.4 Supersession

A single forward link: `claim.superseded_by = "<replacement_claim_id>"`.
Used when a new claim replaces an old one wholesale (e.g. after a
context split, or after a re-analysis with a corrected pipeline). The
old row stays for traceability with `review_status = "superseded"`.

## B.5 Three orthogonal axes — promotion rules

Hard gates enforced by DAG 2's wave executor.

```
EVIDENCE_STATUS:
  draft        → observed:                 ≥1 Wave-1 association test passed
  observed     → replicated:               ≥2 independent datasets, consistent direction
  replicated   → causal:                   ≥1 perturbation result (LOF or GOF)
  causal       → mechanistic:              orthogonal phenotype confirms mechanism
  mechanistic  → externally_supported:     functional consequence demonstrated

PRIOR_ART_STATUS:
  unsearched   → canonical:                ≥1 textbook source confirms the claim
               → related_prior_art:        prior work close but not exact
               → context_extension:        known gene, new context — pursue
               → evidence_upgrade:         known association, need causation
               → plausibly_novel:          no prior art found
               → ambiguous:                conflicting prior art — flag for review

REVIEW_STATUS:
  clean ↔ in_review ↔ contradicted ↔ needs_experiment
        ↘ superseded
```

Any claim with `review_status ∈ {contradicted, needs_experiment}`
**blocks** further evidence promotion. The wave executor refuses to
push such a claim along the evidence-status axis until the review state
clears.

## B.6 Contradiction registry

`contradiction_case_ids: list[str]` on the claim points at
`ContradictionCase` rows. Each case is a typed disagreement with a
classification (`entity_mismatch` | `assay_mismatch` | `context_split`
| `true_frontier`) and a resolution path
(`open → narrowed | resolved | halted`).

When a `ContradictionCase` resolves into a `context_split`, the parent
claim is flagged `is_general=True` and child claims are emitted with
`splits_on_dimension` set — closing the loop with §B.1.

## B.7 Result graph (claim ↔ evidence)

Every `BiologicalResult` is a typed measurement (assay, comparison,
model_type, n, effect_size, CI, p, q, direction, classification). Results
link to claims through `SupportSet`s rather than directly.

A `SupportSet` is an **AND-group** of evidence — multiple SupportSets
linking to the same claim form an **OR**. This lets the system express
"either replicate A through B, OR replicate C through D, will satisfy
the claim's `replicated` gate."

```
                 ┌────────────────────────────────┐
                 │  Claim                         │
                 └────────┬───────────┬───────────┘
                          │           │
                  SupportSet 1   SupportSet 2     ← OR between sets
                  (AND inside)   (AND inside)
                  ┌─────┼─────┐  ┌──────────┐
                  ▼     ▼     ▼  ▼          ▼
              Result  Result  Result   Result   Result
```

A SupportSet has `stance ∈ {supports, contradicts}`. Conflicting
evidence routes into a `contradicts`-stance SupportSet on the existing
claim instead of forming a duplicate row — that's why
`edge_signature` deliberately excludes polarity (see §A.1.1).

## B.8 Confidence — categorical, not probabilistic

The system **does not** persist `posterior_probability`,
`prior_probability`, or `noisy_or_confidence` on claim rows. Those
numbers were tried and removed (Phase M rejected): they over-promised
precision the underlying evidence couldn't support and made claims
look more or less certain than they actually were.

Instead, every claim carries a **layered claim digest** (L0–L4) plus
a categorical `confidence_summary`:

| Layer | What it digests |
|---|---|
| L0 | raw `BiologicalResult` rows |
| L1 | per-study summary |
| L2 | per-modality summary across studies |
| L3 | per-evidence-family summary across modalities |
| L4 | cross-family / cross-modality summary — the headline confidence |

`confidence_summary` is one of a small categorical set; numeric scores
needed for ranking are *re-derived on demand*, never persisted.

---

## Mandatory rules

1. No node may emit a free-text conclusion without ≥ 1 typed
   `BiologicalResult` backing it.
2. No multi-study summary without a pooled meta-analysis row.
3. No promotion past an `evidence_status` hard gate without the
   corresponding evidence type (see §B.5).
4. No verdict without a machine-readable L1–L7 coverage map (which
   evidence layers were observed, which were null, which are missing).
5. No claim promotion without KG write-back — the result graph is
   the ground truth, the row in `claims` is a *view* over it.

## Pointers

- `schema/schema.py` — public dataclasses for `ClaimType`,
  `EvidenceStatus`, `PriorArtStatus`, `ReviewStatus`,
  `PublicationStatus`, `PhenotypeDefinition`,
  `ConfounderDeclaration`, `ResearchQuestionContract`, `CandidateNode`.
- `schema/table_schemas.sql` — full DDL for `claims`,
  `claim_participants`, `evidence`, `support_sets`,
  `contradictions`.
- `INGEST.md` — how the backbone-edge layer the claim references
  was built.
- `ID_CONVENTIONS.md` — entity_id and edge_id grammar.
