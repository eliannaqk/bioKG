# Claim object — current architecture (post-Part-X)

This is the field-by-field reference for the **claim object** as it
exists in production today (Part X cut over 2026-04-29; 881k claim
rows migrated).

The doc has three parts:

- **Part A — `claims` table** (56 columns).
- **Part B — side-tables** that hold what `claims` used to carry
  inline: `claim_rankings`, `claim_participants`, `claim_relations`,
  `claim_embeddings`, plus the result/evidence tables.
- **Part C — `edge_signature`**: the new set-based, structural-role-driven
  derivation that makes the same biological assertion dedup across
  sources.

`CandidateClaim` and `Claim` collapsed into a single dataclass in
Part X. A "candidate" is just a `Claim` row with
`evidence_status = "draft"` and the typed ontology cached transiently.

---

# Part A — the `claims` table (56 columns)

Grouped by purpose. Source: `gbd/knowledge_graph/graph.py` CREATE
TABLE block + `_p1_claim_columns` ALTERs. Full DDL in
`schema/table_schemas.sql`.

## A.1 Identity (5)

| Column | Type | Notes |
|---|---|---|
| `claim_id` | TEXT PRIMARY KEY | canonical id |
| `claim_type` | TEXT NOT NULL | one of 40+ `ClaimType` values |
| `claim_text` | TEXT | atomic statement, natural language |
| `human_readable` | TEXT | one-liner for logs / reports |
| `edge_signature` | TEXT | set-based dedup primitive — see Part C |

## A.2 Typed assertion (2)

| Column | Type | Notes |
|---|---|---|
| `relation_name` | TEXT | typed predicate (`destabilizes`, `phosphorylates`, `represses`, …); NULL on composites |
| `relation_polarity` | TEXT | `positive` \| `negative` \| `bidirectional` \| `null` \| `unknown`; NULL on composites |

`direction` / `effect_size` / `effect_unit` were dropped in Part X.
Effect sizes are per-result on `biological_results` only.

## A.3 Three orthogonal axes (4)

| Column | Type | Values |
|---|---|---|
| `evidence_status` | TEXT | `draft` → `observed` → `replicated` → `causal` → `mechanistic` → `externally_supported` |
| `prior_art_status` | TEXT | `unsearched` \| `canonical` \| `related_prior_art` \| `context_extension` \| `evidence_upgrade` \| `plausibly_novel` \| `ambiguous` |
| `review_status` | TEXT | `clean` \| `in_review` \| `contradicted` \| `superseded` \| `needs_experiment` |
| `proof_level` | INTEGER | `1` ontology_fact \| `2` observational_association \| `3` model_prediction \| `4` perturbational_molecular \| `5` perturbational_phenotypic \| `6` orthogonal_reproduction \| `7` published_established |

A claim is `replicated + plausibly_novel + clean` (strong novel
finding) or `causal + canonical + clean` (validated replication of
known biology) — both useful, never collapsed into one number.

## A.4 Participants context (3)

The canonical participants live in `claim_participants` (Part B).
The fields below are the persisted projections used by readers.

| Column | Type | Notes |
|---|---|---|
| `cell_states_json` | TEXT (JSON) | list of `CellStateCondition` (state_type, state_name, markers, is_required, …) |
| `context_set_json` | TEXT (JSON) | typed-graph projection of `gbd.core.context_provenance.ContextSet`; queryable via ancestor traversal; what `EdgeView.context` surfaces |
| `context_operator` | TEXT | `AND` \| `OR` — how participants combine |

## A.5 Cross-evidence count rollups (12 — added in Part X)

Populated by a recomputed-on-attach hook over
`biological_results JOIN result_to_claim WHERE attached=1`. Confidence
summary reads from these without re-aggregating per read.

| Column | Type | Notes |
|---|---|---|
| `n_studies` | INTEGER | independent studies |
| `n_modalities` | INTEGER | independent modalities |
| `n_supporting_results` | INTEGER | added in Part X |
| `n_refuting_results` | INTEGER | added in Part X |
| `n_null_results` | INTEGER | added in Part X |
| `n_inconclusive` | INTEGER | added in Part X |
| `n_assays` | INTEGER | added in Part X |
| `n_datasets` | INTEGER | added in Part X |
| `n_supporting_pmids` | INTEGER | added in Part X |
| `polarity_consistency` | REAL | renamed from `direction_consistency` in Part X |
| `decisive_coverage` | REAL | fraction of `latent_state.decisive_observations` actually run |
| `proxy_coverage` | REAL | fraction of `latent_state.proxy_observations` actually run |

## A.6 Provenance (8)

| Column | Type | Notes |
|---|---|---|
| `source_dataset` | TEXT | e.g. `DepMap_24Q2`, `GSE91061`, `CPTAC_PDC000127` (per-result migration pending) |
| `source_release` | TEXT | dataset release tag |
| `assay_type` | TEXT | `CRISPR_Chronos`, `RNA-seq`, `mass_spec`, … (per-result migration pending) |
| `model_name` | TEXT | `ElasticNet`, `DerSimonian-Laird`, … |
| `model_version` | TEXT | model release tag |
| `artifact_id` | TEXT | hash of raw data that produced this |
| `source` | TEXT | `kg_traversal` \| `literature_gap` \| `contradiction_gap` |
| `kg_evidence` | TEXT (JSON list) | backbone-edge IDs that suggested this claim |

## A.7 Legacy candidate fields (2 — Part III pending)

Kept on the row as denormalised fast-index. New code reads
`claim_participants[role=EFFECTOR]`.

| Column | Type | Notes |
|---|---|---|
| `candidate_gene` | TEXT | HGNC symbol; legacy fast-index |
| `candidate_id` | TEXT | equals `claim_id` after Part X collapse |

## A.8 Audit / synthesis (7)

| Column | Type | Notes |
|---|---|---|
| `created_at` | TEXT | ISO timestamp |
| `created_by` | TEXT | `gbd_agent`, `manual`, `geo_agent` |
| `superseded_by` | TEXT | `claim_id` that replaces this one (single forward link) |
| `full_data` | TEXT (JSON) | grab-bag of serialised payload — being drained in Part IV-L |
| `confidence_summary` | TEXT | categorical ordinal — see §C.4 |
| `narrative` | TEXT | running synthesis (§46) |
| `narrative_updated_at` | TEXT | last-write timestamp for the narrative |

## A.9 What is **not** here

These were tried and rejected — they are **not** columns on `claims`
and Part X confirmed they will not be re-added:

- `posterior_probability`, `prior_probability`, `noisy_or_confidence`
  — categorical `confidence_summary` is the source of truth.
- `graduation_status`, `graduated_at`, `graduation_evidence_ids`,
  `inverse_claim_id` — never made it through migration.
- `tractability_score`, `kg_connectivity_score`, `priority_score`,
  `tools_to_prioritise`, `cancer_type_scope`, `embedding_text` —
  dropped in Part X. Rankings live in `claim_rankings` (Part B);
  embedding text lives in `claim_embeddings`; planner hints
  regenerated on demand.
- `direction`, `effect_size`, `effect_unit` — dropped in Part X.
  Effect sizes are per-result on `biological_results`; polarity is on
  `relation_polarity`.
- All hierarchy/refinement fields (`parent_claim_id`,
  `refinement_type`, `is_general`, `splits_on_dimension`, …) —
  moved to `claim_relations` in Phase T.

---

# Part B — side-tables

What `claims` rows used to carry inline now lives in dedicated tables.
Each has its own concerns and life-cycle.

## B.1 `claim_rankings` (DAG-1 ranking, per-run)

```
CREATE TABLE claim_rankings (
    claim_id          TEXT NOT NULL,
    run_id            TEXT NOT NULL,
    priority_score    REAL NOT NULL,
    kg_connectivity   REAL,
    novelty_component REAL,
    probe_signal      REAL,
    rank_in_run       INTEGER,
    computed_at       TEXT NOT NULL,
    rationale_json    TEXT DEFAULT '{}',
    PRIMARY KEY (claim_id, run_id),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
);
CREATE INDEX idx_rankings_run_priority
    ON claim_rankings(run_id, priority_score DESC);
CREATE INDEX idx_rankings_claim
    ON claim_rankings(claim_id);
```

Per-`(claim, run)` keying gives ranking history for free — you can ask
"how did this claim rank in last week's run vs. today's." Pre-Part-X
data was backfilled with `run_id='pre_phase_x'`.

Readers (`pipeline.py`, `portfolio_explorer.py`,
`literature_grounded_hypotheses.py`) all route through
`kg.get_ranking(claim_id, run_id)` / `kg.write_ranking(...)`.

## B.2 `claim_participants` (entity ↔ claim with role)

```
claim_id   TEXT FK, entity_id TEXT FK,
role       TEXT NOT NULL,   -- ParticipantRole
properties TEXT DEFAULT '{}'  -- JSON
INDEX idx_participants_entity ON claim_participants(entity_id)
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

Entity type is read from the `entity_id` namespace prefix (`HGNC:`,
`DRUG:`, `MONDO:`, `COMPLEX:`, `GO:`, `CL:`, `UBERON:`, `PWY:`, `FT:`),
not encoded in the role.

### Legacy 16-value roles (kept as aliases, never written by new code)

`EFFECTOR_GENE`, `TARGET_GENE`, `CONTEXT_MUTATION`,
`CONTEXT_CANCER_TYPE`, `CONTEXT_CELL_TYPE`, `CONTEXT_IMMUNE_STATE`,
`CONTEXT_CELL_STATE`, `CONTEXT_THERAPY`, `CONTEXT_CELL_LINE`,
`PHENOTYPE_GENE`, `PATHWAY`, `COMPOUND`, `CONFOUNDER`, `REGULATOR_TF`,
`REGULATEE`, `MEDIATOR`. Translated via
`normalize_role(claim_shape, role, properties)` into the six
structural values.

`participant_combinator` (`AND` \| `OR`) on the claim distinguishes
conjunctive co-requirement from disjunctive redundancy when a side has
> 1 entity.

## B.3 `claim_relations` (the tree — Phase T)

```
relation_id      TEXT PRIMARY KEY,
source_claim_id  TEXT FK, target_claim_id TEXT FK,
relation_type    TEXT NOT NULL,
rationale        TEXT,
confidence       REAL,
source_run_id    TEXT,
judge_model      TEXT,
created_at       TEXT,
properties       TEXT DEFAULT '{}'
```

Replaced the per-row hierarchy/refinement fields. Nine relation types,
split into structural (parent links) and non-structural (sibling
links):

### Structural — at most one parent edge of any given type per claim

| `relation_type` | Meaning |
|---|---|
| `chain_link_of` | source is a `CAUSAL_CHAIN_LINK` of the composite target — the four canonical levels (perturbation → molecular_consequence → cellular_phenotype → human_relevance) and any intermediates |
| `branches_from` | source is a refinement of target (sibling exploration of an alternative mechanism) |
| `context_split_of` | source was born from the P9 splitter when the target was flagged `is_general` and split on `splits_on_dimension` (`residue` / `cell_type` / `cancer_type` …) |
| `mediator_specific_of` | source narrows target to a specific mediator participant |
| `polarity_inverse_of` | source asserts the opposite polarity of the same `(subject, relation, object, context)` — drives the contradiction triage |

### Non-structural — sibling edges, can be many-to-many

| `relation_type` | Meaning |
|---|---|
| `refines` | source is a more-specific version of target (different from `branches_from` — no parent-child commitment) |
| `competes_with` | source and target are competing explanations for the same observation; planner maintains a posterior over the set |
| `contradicts` | source and target disagree at the evidence level; backed by a `contradiction_case` row |
| `enables` | source's truth is required for target's truth (mechanism prerequisite) |

A `MechanismHypothesis` and a `CompetingExplanation` are candidate
competitors — the planner promotes them to first-class `Claim` rows
with `relation_type='competes_with'` once they earn enough evidence to
be tested independently.

## B.4 `claim_embeddings` (text → vector cache)

```
claim_id           TEXT PRIMARY KEY,
embedding_text     TEXT,
embedding_vec_json TEXT,
embedding_model    TEXT,
created_at         TEXT
```

After Part X this is the **only** home for embeddable text — the
old `claims.embedding_text` column was dropped.

## B.5 Result graph

`claims` carries content; evidence lives separately and links through
`result_to_claim` or `support_sets`.

### `biological_results` — per-tool, per-claim raw output

```
result_id PK, claim_id FK,
result_type, assay, provider,
context (JSON), outcome, effect_direction, effect_size,
confidence_interval, p_value, n,
statistical_test_performed (0|1),
evidence_category   -- statistical_test | frequency_observation | qualitative_finding
depends_on (JSON), validity_scope, timestamp,
agent_run_id, artifact_paths (JSON)
INDEX idx_results_claim ON biological_results(claim_id)
```

Every CRISPR Chronos run, every Cox model, every scRNA-DE call lands
here. One claim → many results.

### `result_to_claim` — quality-gated edges

```
result_id, claim_id,
attached (0|1), quality_verdict, rejection_reason,
confidence, attached_at, attached_by
PRIMARY KEY (result_id, claim_id)
```

A single result can be evidence for multiple claims (cap = 5 via
`MAX_CLAIMS_PER_RESULT`). **Always join with `WHERE attached=1`** when
reading evidence; rejected attachments stay in the table for audit.

### `evidence` — per-publication / external

```
evidence_id PK, evidence_type, description, source,
statistic_name, statistic_value, p_value, effect_size,
sample_size, confidence_interval, pmid, doi, year, title,
accession, n_samples, organism, perturbation_type,
perturbed_gene, readout, cell_line,
model_name, model_version, cv_metric, cv_value,
artifact_path, artifact_hash, created_at, full_data
INDEX idx_evidence_pmid ON evidence(pmid)
```

External / curated evidence (literature, public datasets). Distinct
from `biological_results` (internal tool output). Linked into claims
via `support_sets.evidence_ids`.

### `support_sets` — bag-of-evidence groupings

```
support_set_id PK, claim_id FK,
label, logic (AND|OR), stance (supports|refutes),
evidence_ids (JSON list),
confidence, proof_level, description
```

A claim can have multiple distinct evidence sets that each
independently support or refute it. Internal logic (`AND`/`OR`) acts
within a set; multiple sets compose **OR** across them.

```
                       Claim
                  ┌──────┴─────┐
                  │            │
            SupportSet 1  SupportSet 2     ← OR between sets
            (AND inside)  (AND inside)
            stance=supports  stance=supports
            ┌───┼───┐    ┌────────┐
            ▼   ▼   ▼    ▼        ▼
          ev  ev  ev    ev       ev
```

A `contradicts`-stance set is the canonical home for evidence with
opposite polarity to an existing claim — see Part C for why
`edge_signature` deliberately excludes polarity.

### `study_results` — DAG-2 proving-node output

```
study_result_id PK, question_id, study_id, evidence_family,
cohort_name, context, assay, comparison, model_type,
covariates, n, effect_size, standard_error, ci_low, ci_high,
p_value, q_value, direction, classification,
quality_flags, artifact_paths, node_id, wave, timestamp
```

One row per study analysed for one proving question. Aggregated
upward into `biological_results` when the question's claim is touched.

### `contradiction_cases`

```
case_id PK, claim_a_id FK, claim_b_id FK,
reason, classification (true_frontier | …), resolution,
resolution_action, spawned_plans, lineage_specific,
assay_specific, modality_mismatch, timepoint_dependent, ...
```

Typed disagreements with classification (`entity_mismatch` |
`assay_mismatch` | `context_split` | `true_frontier`) and a
resolution path (`open` → `narrowed` | `resolved` | `halted`). When
a case resolves into `context_split`, the parent is flagged
`is_general` and child claims are emitted with `splits_on_dimension`
set — closing the loop with §B.3 (`context_split_of`).

---

# Part C — `edge_signature`

`edge_signature = SHA256(subject_node_id | relation_name | object_node_id [| context_hash])`

It is the cross-source dedup primitive: two claims share an
`edge_signature` iff they make the same biological assertion under
the same discriminating context. Importing a third source with the
same assertion lands its evidence on the existing claim instead of
creating a duplicate row; conflicting polarity goes into a
`stance="contradicts"` SupportSet on the same claim.

Pre-Part-X the signature was a flat `(subject, relation, object)`
triple read from denormalised columns. Part X §56 made it
**set-based, structural-role-driven, and type-agnostic**, and added
the **8-dimension context hash** so context-discriminating claims
no longer collide.

## C.1 The new derivation — `_derive_edge_signature(claim)`

Source: `gbd/knowledge_graph/graph.py:115`. Steps:

### Step 1 — collect the SUBJECT-side and OBJECT-side sets

For every `ClaimParticipant` on the claim, normalise its role through
`normalize_role(claim_shape, role, properties)` and bucket by side:

```
PRINCIPAL_SUBJECT_ROLES = { SUBJECT, EFFECTOR }
PRINCIPAL_OBJECT_ROLES  = { OBJECT,  OUTCOME }

subjects = { p.entity_id for p in claim.participants
             if normalize_role(...) in PRINCIPAL_SUBJECT_ROLES }
objects  = { p.entity_id for p in claim.participants
             if normalize_role(...) in PRINCIPAL_OBJECT_ROLES }
```

Type-agnostic: drugs (`DRUG:`), complexes (`COMPLEX:`), cell types
(`CL:`), pathways (`PWY:`), phenotypes (`GO:`/`HP:`) flow through
identically — the entity_id namespace prefix is the only thing that
distinguishes them, and the signature treats them all as opaque ids.

### Step 2 — fold each set into a stable string

Sort the set lexically to get a deterministic order:

```
sorted_subjects = sorted(subjects)
sorted_objects  = sorted(objects)
```

| Set size | Encoding | Why |
|---|---|---|
| 1 | the single id verbatim | the common case |
| > 1 on subject side | `",".join(sorted_subjects) + "|" + participant_combinator` | the combinator (`AND` / `OR`) is part of the assertion's identity — `"X AND Y → Z"` is a different claim from `"X OR Y → Z"` |
| > 1 on object side | `",".join(sorted_objects)` (no combinator) | object-side multi-entity is always conjunctive (`"RBMS1 destabilises {CXCL9, CXCL10} mRNAs"` — both targets affected) |

### Step 3 — fallbacks (preserved from pre-Part-X behaviour)

- **Empty subject side** → fall back to `claim.candidate_gene` (legacy
  denormalised; Part III drop pending).
- **Empty object side** → slug of
  `structured_claim_json.phenotype_statement`,
  written as `FT:phenotype.<slug>` (≤ 80 chars). Two claims pointing
  at the same free-text phenotype string then dedup to the same edge.
- **Relation** → prefer `claim.relation_name`, then
  `structured_claim_json.relation_name`; lowercased.
- **Missing any of subject/relation/object** → return `""`. Caller
  treats empty signature as "no dedup possible"; reconciliation skips
  the row.

### Step 4 — context hash (Part X §56.3, P7)

`context` is read from `claim.context_set_json` (canonical), falling
back to the `context` dict on the StructuredClaim payload. Eight
dimensions are hashed:

```
_CONTEXT_DIMENSIONS = (
    "residue",            # Ser63 / Ser44 — SIGNOR phosphorylation site
    "modification_type",  # phosphorylation / ubiquitination / acetylation / …
    "cell_type",          # CL: ID or free-form when unresolved
    "tissue",             # UBERON: ID or free-form
    "modulator_complex",  # which complex the modifier sits in
    "target_complex",     # which complex the target sits in
    "treatment",          # drug / cytokine / stress condition
    "disease",            # MONDO: / DOID: ID or free-form
)
```

Per dimension, values are normalised to a deterministic string via
`_normalise_context_value`:

- `None` / empty → `""`
- list / tuple / set → sorted, deduped, comma-joined
  (so `["Ser36","Ser63"]` and `["Ser63","Ser36"]` collapse to the same string)
- scalar → `str(v).strip()`

The 8-pair payload `"k1=v1|k2=v2|…|k8=v8"` is SHA-256'd and the first
**16 hex chars** are kept as `context_hash`.

### Step 5 — final signature

```python
if context_hash:
    payload = f"{subject_id}|{relation_name}|{object_id}|{context_hash}"
else:
    # Empty context (no discriminating dimensions set) → legacy
    # 3-component signature so legacy rows keep their precomputed values.
    payload = f"{subject_id}|{relation_name}|{object_id}"

edge_signature = sha256(payload).hexdigest()    # 64 hex chars
```

## C.2 Polarity is *not* in the signature

Deliberately. An "STAT1 activates IRF1" claim from Reactome and an
"STAT1 inhibits IRF1" claim from a hypothetical other source share
the same `edge_signature` — so the importer **finds the
contradiction** instead of writing a duplicate row. Polarity is
recorded on `support_sets.stance` (`supports` | `contradicts`), and
the P8 triage classifies the collision as one of:
`true_contradiction` / `context_split` / `duplicate` / `noise`.

## C.3 Worked example — multi-residue phosphorylation

A SIGNOR claim "CSNK2A1 phosphorylates ATF1 at Ser36/Ser38/Ser41/Ser44/Ser63"
(after function-bucket aggregation):

```
participants = [
    {entity_id: "HGNC:CSNK2A1", role: SUBJECT},
    {entity_id: "HGNC:ATF1",    role: OBJECT},
]
relation_name = "phosphorylates"
context_set_json = {
    "residue": ["Ser36", "Ser38", "Ser41", "Ser44", "Ser63"],
    "modification_type": "phosphorylation",
    "cell_type": "",
    "tissue": "", "modulator_complex": "",
    "target_complex": "", "treatment": "", "disease": "",
}

# Step 2
subjects = {"HGNC:CSNK2A1"}     → "HGNC:CSNK2A1"
objects  = {"HGNC:ATF1"}        → "HGNC:ATF1"
relation = "phosphorylates"

# Step 4 — context
context_payload = (
    "residue=Ser36,Ser38,Ser41,Ser44,Ser63"
    "|modification_type=phosphorylation"
    "|cell_type=|tissue=|modulator_complex=|"
    "target_complex=|treatment=|disease="
)
context_hash = sha256(context_payload)[:16]
# = (e.g.) "8a4f2c1b3e9d0a7f"

# Step 5
payload    = "HGNC:CSNK2A1|phosphorylates|HGNC:ATF1|8a4f2c1b3e9d0a7f"
edge_signature = sha256(payload).hexdigest()
```

Pre-Part-X, this claim collided with five distinct single-residue
SIGNOR rows — adding `residue` to the context hash split them out.
Two claims with the same residue list (regardless of insertion
order) hash identically, so a re-import doesn't duplicate.

## C.4 Categorical confidence — *not* probability

The system **does not** persist `posterior_probability`,
`prior_probability`, or `noisy_or_confidence` on `claims` rows. They
were tried and removed (Phase M rejected): they over-promised
precision the underlying evidence couldn't support and made claims
look more or less certain than they actually were.

`claims.confidence_summary` is one of a small set of categorical
labels (Phase VIII §47) backed by a **layered claim digest**:

| Layer | Reads from | What it digests |
|---|---|---|
| L0 | `biological_results` | raw per-tool rows |
| L1 | per-study | per-study summary |
| L2 | per-modality | per-modality across studies |
| L3 | per-evidence-family | per-evidence-family across modalities |
| L4 | cross-family / cross-modality | the headline confidence |

The 12 count rollups in §A.5 (`n_supporting_results`,
`n_refuting_results`, `n_assays`, `n_datasets`, `polarity_consistency`,
`decisive_coverage`, `proxy_coverage`, …) are the inputs the digest
reads. Numeric scores needed for ranking are re-derived on demand
from `claim_rankings`, never persisted on the claim row.

---

## Pointers

- `schema/schema.py` — public dataclasses: `ClaimType`,
  `EvidenceStatus`, `PriorArtStatus`, `ReviewStatus`,
  `PublicationStatus`, `PhenotypeDefinition`,
  `ConfounderDeclaration`, `ResearchQuestionContract`, `CandidateNode`.
- `schema/table_schemas.sql` — full DDL for `claims`,
  `claim_participants`, `claim_relations`, `claim_rankings`,
  `claim_embeddings`, `biological_results`, `result_to_claim`,
  `evidence`, `support_sets`, `study_results`, `contradiction_cases`.
- `INGEST.md` — how the backbone-edge layer the claim references
  was built.
- `ID_CONVENTIONS.md` — entity_id grammar (the namespace prefixes
  Part C reads).
