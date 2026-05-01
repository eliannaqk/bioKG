# Claim Object

The `claims` table is the central unit of the GBD knowledge graph.
This document is the field-by-field schema reference plus two
worked examples: a bifurcated Signor curated claim, and a
parent-child mechanism pair. Every field is shown for every
example, even when empty.

---

## 1. The claim row — every field

`claims` carries 59 columns. Listed in storage order with type,
default, and what each column means.

### Identity

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 0 | `claim_id` | TEXT | — | Unique stable id (PRIMARY KEY). |
| 1 | `claim_type` | TEXT | — | Enum value from `ClaimType` (e.g. `GeneGeneCorrelationClaim`, `MechanismHypothesisClaim`, `CausalChainLinkClaim`, …). |
| 2 | `status` | TEXT | `''` | Free-text legacy status; superseded by `evidence_status` / `review_status`. |

### Content — what the claim asserts

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 20 | `claim_text` | TEXT | `''` | Atomic statement in natural language. |
| 14 | `description` | TEXT | `''` | Long-form description (often empty). |
| 3 | `human_readable` | TEXT | `''` | One-liner for logs and paper sections. |
| 30 | `relation_name` | TEXT | `''` | Typed predicate from the relation registry (e.g. `regulates_mrna_stability`, `phosphorylates`, `binds`, `drives_phenotype`). |
| 31 | `relation_polarity` | TEXT | `''` | `positive` / `negative` / `bidirectional` / `null` / `unknown` / `''` (= NOT_APPLICABLE — the predicate carries no sign, e.g. `binds`). |

### Status — three orthogonal axes

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 17 | `evidence_status` | TEXT | `'draft'` | Where on the evidence ladder: `draft` / `observed` / `replicated` / `causal` / `mechanistic` / `externally_supported`. |
| 18 | `prior_art_status` | TEXT | `'unsearched'` | PubMed adjudication: `unsearched` / `canonical` / `related_prior_art` / `context_extension` / `evidence_upgrade` / `plausibly_novel` / `ambiguous`. |
| 19 | `review_status` | TEXT | `'clean'` | Lifecycle: `clean` / `in_review` / `contradicted` / `superseded` / `needs_experiment`. |
| 15 | `superseded_by` | TEXT | `''` | If superseded, the `claim_id` that replaces this one. |

### Proof + cross-evidence aggregates

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 4 | `proof_level` | INTEGER | `2` | 1=ontology_fact, 2=observational_assoc, 3=model_prediction, 4=perturbational_molecular, 5=perturbational_phenotypic, 6=orthogonal_reproduction, 7=published_established. |
| 8 | `n_studies` | INTEGER | `0` | How many independent studies. |
| 9 | `n_modalities` | INTEGER | `0` | How many distinct evidence modalities. |
| 39 | `n_supporting_results` | INTEGER | `0` | COUNT(`biological_results.outcome='positive'`). |
| 40 | `n_refuting_results` | INTEGER | `0` | COUNT(`outcome='negative'`). |
| 41 | `n_null_results` | INTEGER | `0` | COUNT(`outcome='null'`). |
| 42 | `n_inconclusive` | INTEGER | `0` | COUNT(`outcome='inconclusive'`). |
| 43 | `n_assays` | INTEGER | `0` | DISTINCT(`biological_results.assay`). |
| 44 | `n_datasets` | INTEGER | `0` | DISTINCT(`biological_results.source_dataset`). |
| 45 | `n_supporting_pmids` | INTEGER | `0` | Literature supporting count. |
| 46 | `polarity_consistency` | REAL | `0.0` | Fraction of results whose polarity matches the claim's. |
| 47 | `decisive_coverage` | REAL | `0.0` | (n_supporting + n_refuting) / total_results. |
| 48 | `proxy_coverage` | REAL | `0.0` | Coverage of proxy assays. |

### Categorical confidence + narrative

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 36 | `confidence_summary` | TEXT | `'unknown'` | 5-level ordinal: `unknown` / `weak` / `moderate` / `strong` / `established`. Derived from `evidence_status`, `prior_art_status`, `review_status`, `proof_level`, `n_studies`, `n_modalities`. |
| 37 | `narrative` | TEXT | `''` | LLM-rendered prose summary. |
| 38 | `narrative_updated_at` | TEXT | `''` | ISO timestamp of last narrative regeneration. |

### Context

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 21 | `context_set_json` | TEXT | `'{}'` | Typed graph projection of biological context (cell type / cancer type / immune state / therapy / cell line). |
| 34 | `cell_states_json` | TEXT | `'[]'` | List of `CellStateCondition` (e.g. exhausted CD8, IFNγ-exposed). |
| 27 | `context_operator` | TEXT | `'AND'` | How participants combine: `AND` / `OR`. |
| 49 | `participant_combinator` | TEXT | `''` | For composite multi-effector claims (`OR` for pathway redundancy). |

### Identity dedup + entity index

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 22 | `edge_signature` | TEXT | `''` | SHA-256 of (subject\|relation\|object) — cross-source dedup key. Polarity intentionally NOT in the signature (opposite-polarity claims about the same triple are the same biological assertion under contention). |
| 32 | `candidate_gene` | TEXT | `''` | HGNC effector index (mirrors `claim_participants[role=effector_gene]`). |
| 33 | `candidate_id` | TEXT | `''` | Mirror of `claim_id`. |

### Lineage (also represented as `claim_relations` edges)

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 50 | `parent_claim_id` | TEXT | `''` | Parent's `claim_id`. The structural parent edge is also written into `claim_relations`. |
| 51 | `refinement_type` | TEXT | `''` | `branches_from` / `chain_link` / `context_split` / `mediator_specific` / `polarity_inverse` / `narrow` / `pivot` / `expand`. |
| 52 | `refinement_rationale` | TEXT | `''` | Free-text justification. |
| 53 | `refinement_confidence` | REAL | NULL | Judge's confidence in the refinement (0–1). |
| 54 | `splits_on_dimension` | TEXT | `''` | Dimension claim was split on (e.g. `tissue`, `residue`). |
| 55 | `is_general` | INTEGER | `0` | `1` if this claim has been split into polarity-bucket children; derivable from outbound `branches_from` edges. |
| 56 | `target_mechanism_ids` | TEXT | `'[]'` | JSON list of mechanism IDs this claim targets. |
| 57 | `inherited_evidence_ids` | TEXT | `'[]'` | Evidence IDs inherited from parent. |

### Provenance

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 28 | `source` | TEXT | `''` | Pipeline origin: `kg_traversal` / `literature_gap` / `contradiction_gap` / `signor_curated` / etc. |
| 10 | `source_dataset` | TEXT | `''` | E.g. `DepMap_24Q2`, `GSE91061`, `CPTAC_PDC000127`, `OmniPath_v2`. |
| 23 | `source_release` | TEXT | `''` | Release tag. |
| 11 | `assay_type` | TEXT | `''` | E.g. `CRISPR_Chronos`, `RNA-seq`, `mass_spec`. |
| 24 | `model_name` | TEXT | `''` | E.g. `ElasticNet`, `DerSimonian-Laird`. |
| 25 | `model_version` | TEXT | `''` | Version string. |
| 26 | `artifact_id` | TEXT | `''` | Hash of raw data that produced this claim. |
| 29 | `kg_evidence` | TEXT | `'[]'` | JSON list of `backbone_edges.edge_id` values that suggested this claim. |

### Run state

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 16 | `full_data` | TEXT | `'{}'` | Serialised `StructuredClaim` payload (parsed ontology output). |
| 35 | `last_wave_completed` | INTEGER | `0` | Highest wave that touched this claim. |
| 58 | `uct2` | TEXT | `''` | UCT-2 score for the planner's bandit ranking. |

### Audit

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 12 | `created_at` | TEXT | `''` | ISO timestamp of insertion. |
| 13 | `created_by` | TEXT | `''` | Actor: `gbd_agent`, `manual`, `signor_curated_import`, etc. |

### Flat statistics (kept for legacy readers)

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 5 | `p_value` | REAL | NULL | Flat p-value summary (one winner across attached results). |
| 6 | `q_value` | REAL | NULL | Flat q-value. |
| 7 | `confidence_interval` | TEXT | NULL | Flat CI string. |

> Per-row flat statistics pick an arbitrary winner when many
> `biological_results` rows are attached. The authoritative
> per-evidence statistics live on `biological_results`. Keeping the
> flat columns gives older code paths a fast read without joining.

---

## 2. Satellite tables

### `claim_participants` — entity-graph linkage

| Column | Type | Default | Meaning |
|---|---|---|---|
| `claim_id` | TEXT | — | Foreign key. |
| `entity_id` | TEXT | — | Resolved canonical id (HGNC, UniProt, MONDO, CL, …) via `entity_aliases`. |
| `role` | TEXT | — | `subject` / `object` / `effector_gene` / `target_gene` / `phenotype_gene` / `regulator_tf` / `protein` / `pathway` / `outcome` / `disease` / `alteration_carrier` / `cohort_outcome` / `context_mutation` / `context_cancer_type` / `context_cell_type` / `context_immune_state` / `context_cell_state` / `context_therapy` / `context_cell_line`. |
| `properties` | TEXT | `'{}'` | JSON: `{"principal": True/False, "compartment": "...", "alteration": "...", "required_state": "..."}`. |

### `biological_results` — per-tool result rows

| Column | Type | Default | Meaning |
|---|---|---|---|
| `result_id` | TEXT | — | Unique result id (PRIMARY KEY). |
| `claim_id` | TEXT | — | Which claim the result targets. |
| `result_type` | TEXT | — | `analysis` / `lookup` / `meta_analysis` / etc. |
| `assay` | TEXT | `''` | E.g. `Pearson correlation (DepMap CRISPR)`, `actinomycin-D mRNA decay`, `CLIP-seq`. |
| `provider` | TEXT | `''` | Tool / agent that produced the result. |
| `context` | TEXT | `'{}'` | JSON of the assay's context. |
| `outcome` | TEXT | `''` | `positive` / `negative` / `null` / `inconclusive` / `data_available`. |
| `effect_direction` | TEXT | `''` | Legacy direction string. |
| `effect_size` | REAL | `0.0` | Numeric effect (units vary by assay; check `assay`). |
| `confidence_interval` | TEXT | `'(0.0, 0.0)'` | "(low, high)". |
| `p_value` | REAL | `1.0` | Two-sided p-value. |
| `n` | INTEGER | `0` | Sample size. |
| `statistical_test_performed` | INTEGER | `0` | `1` = a real test ran; `0` = qualitative observation. |
| `evidence_category` | TEXT | `'statistical_test'` | `statistical_test` / `frequency_observation` / `qualitative_finding`. |
| `depends_on` | TEXT | `'[]'` | JSON list of upstream `result_id`s. |
| `validity_scope` | TEXT | `''` | When the result holds. |
| `timestamp` | TEXT | `''` | ISO timestamp. |
| `agent_run_id` | TEXT | `''` | Wave / run id. |
| `artifact_paths` | TEXT | `'[]'` | JSON list of paths to raw artifacts. |

`result_to_claim` is a separate gating table: `(result_id, claim_id, attached: 0/1, quality_verdict, rejection_reason, confidence, attached_at, attached_by)`. A result counts toward the claim's belief only when its `result_to_claim.attached = 1` (or no `result_to_claim` row exists).

### `claim_relations` — claim ↔ claim edges

| Column | Type | Default | Meaning |
|---|---|---|---|
| `relation_id` | TEXT | — | Deterministic SHA-256(source\|relation_type\|target). |
| `source_claim_id` | TEXT | — | Child / proposing claim. |
| `target_claim_id` | TEXT | — | Parent / target claim. |
| `relation_type` | TEXT | — | See §4 — 9 values (5 structural-parent + 4 non-structural). |
| `rationale` | TEXT | `''` | Free-text justification. |
| `confidence` | REAL | `0.5` | Judge's confidence in the edge (0–1). |
| `source_run_id` | TEXT | `''` | Wave / run id that wrote the edge. |
| `judge_model` | TEXT | `''` | LLM that authored the edge. |
| `created_at` | TEXT | — | ISO timestamp. |
| `properties` | TEXT | `'{}'` | Typed metadata payload (varies by relation_type). |

### `support_sets` — AND-grouped evidence bundles

| Column | Type | Default | Meaning |
|---|---|---|---|
| `support_set_id` | TEXT | — | Unique bundle id. |
| `claim_id` | TEXT | — | Which claim this bundle supports. |
| `label` | TEXT | `''` | Human label (e.g. "DepMap co-essentiality"). |
| `logic` | TEXT | `'AND'` | `AND` (every evidence_id required) / `OR`. |
| `evidence_ids` | TEXT | `'[]'` | JSON list of `result_id`s and/or `evidence_id`s. |
| `confidence` | REAL | `0.0` | Bundle-level confidence (0–1). |
| `proof_level` | INTEGER | `2` | Maturity tier reached by the bundle. |
| `stance` | TEXT | `'supports'` | `supports` / `contradicts` / `refines`. |
| `description` | TEXT | `''` | Free text. |

### `claim_events` — append-only audit trail

| Column | Type | Default | Meaning |
|---|---|---|---|
| `event_id` | INTEGER | autoincrement | Unique. |
| `claim_id` | TEXT | — | Which claim transitioned. |
| `axis` | TEXT | — | Which axis transitioned: `evidence_status` / `review_status` / `narrative` / etc. |
| `old_value` | TEXT | NULL | Previous value. |
| `new_value` | TEXT | NULL | New value. |
| `reason` | TEXT | NULL | Free-text explanation. |
| `actor` | TEXT | NULL | Who made the change. |
| `agent_run_id` | TEXT | `''` | Wave / run id. |
| `wave` | INTEGER | `0` | Wave number. |
| `timestamp` | TEXT | — | ISO timestamp. |

---

## 3. The 9 `claim_relations.relation_type` values

```
STRUCTURAL-PARENT EDGES (every non-root claim has exactly one
                          inbound edge of one of these types):

  branches_from         — mechanism alternative
                          ("MH-1 is one way the parent could be true")
  chain_link_of         — step within a composite causal chain
                          ("link 2 of 4 in the parent's mechanism")
  context_split_of      — per-context decomposition
                          ("the melanoma slice of the pan-cancer claim")
  mediator_specific_of  — alt-mechanism specific to one chain link
                          ("alternative effector for the same link")
  polarity_inverse_of   — auto-disproof inverse claim

NON-STRUCTURAL EDGES (a claim can have many, in any direction):

  refines               — supersession
  competes_with         — mutual-exclusion (alternative under joint investigation)
  contradicts           — open polarity / refutation conflict
  corroborates          — extra support without supersession
  enables               — PTM event → consequence linkage
                          (e.g. phosphorylation_event ENABLES regulates_activity)
```

`properties` JSON shape per relation_type:

```python
# branches_from
{"mechanism_id": "MH-1", "plausibility": "high",
 "layer": "post_transcriptional", "eager_seeded": True}

# chain_link_of
{"step": 2, "step_role": "molecular_consequence",
 "is_canonical_backbone": True}

# context_split_of
{"dimension": "tissue", "scope_value": "melanoma"}

# mediator_specific_of
{"mediator_entity_id": "HGNC:RC3H1",
 "alt_for_link_id": "parent...__link-2-2"}

# polarity_inverse_of
{"auto_created_at": "2026-04-29T...",
 "trigger_posterior": 0.12,
 "inherited_evidence_ids": [...]}
```

The structural-parent invariant: a claim may have multiple
inbound structural edges only if they all point to the **same**
parent (e.g. `branches_from` + `mediator_specific_of` to the same
parent — both are valid metadata). Multiple structural edges to
**different** parents is rejected at write time.

---

## 4. Worked example A — bifurcated claim (Signor curated)

The Signor curated import produces three sibling claim rows for
each (subject, object, mechanism) triple where the curated
literature reports both polarity directions: a parent **general**
claim plus two polarity-bucket children. The parent is not directly
provable; one of its two children is correct in any specific
context.

### 4.1 Parent — `signor:CSNK2A1__ATF1__phos__general`

```
─── claims row ─────────────────────────────────────────────────────
claim_id                = 'signor:CSNK2A1__ATF1__phos__general'
claim_type              = 'PhosphorylationClaim'
status                  = ''
human_readable          = 'CSNK2A1 phosphorylates ATF1 (mechanism — polarity context-dependent)'
proof_level             = 7    (published_established)
p_value                 = NULL
q_value                 = NULL
confidence_interval     = NULL
n_studies               = 59
n_modalities            = 1
source_dataset          = 'Signor_v3.1'
assay_type              = 'curated_literature'
created_at              = '2026-04-21T14:32:00Z'
created_by              = 'signor_curated_import'
description             = ''
superseded_by           = ''
full_data               = '{}'
evidence_status         = 'externally_supported'
prior_art_status        = 'canonical'
review_status           = 'clean'
claim_text              = 'CSNK2A1 phosphorylates ATF1'
context_set_json        = '{}'
edge_signature          = '8a7c…' (SHA-256 of HGNC:CSNK2A1|phosphorylates|HGNC:ATF1)
source_release          = 'Signor_2025_Q1'
model_name              = ''
model_version           = ''
artifact_id             = 'signor_v3.1_2025-01-15.tsv#sha256:…'
context_operator        = 'AND'
source                  = 'signor_curated'
kg_evidence             = '[]'
relation_name           = 'phosphorylates'
relation_polarity       = ''                  ← polarity_kind=NOT_APPLICABLE
                                                (phosphorylation is a PTM event;
                                                 the +/- consequence on ATF1 activity
                                                 is the bifurcation, not the PTM itself)
candidate_gene          = 'HGNC:CSNK2A1'
candidate_id            = 'signor:CSNK2A1__ATF1__phos__general'
cell_states_json        = '[]'
last_wave_completed     = 0
confidence_summary      = 'established'
narrative               = ''
narrative_updated_at    = ''
n_supporting_results    = 0
n_refuting_results      = 0
n_null_results          = 0
n_inconclusive          = 0
n_assays                = 0
n_datasets              = 0
n_supporting_pmids      = 59
polarity_consistency    = 0.0
decisive_coverage       = 0.0
proxy_coverage          = 0.0
participant_combinator  = ''
parent_claim_id         = ''                  ← root of its triplet
refinement_type         = ''
refinement_rationale    = ''
refinement_confidence   = NULL
splits_on_dimension     = 'polarity'           (the dimension this claim has been split on)
is_general              = 1                   ← has been split into __positive / __negative
target_mechanism_ids    = '[]'
inherited_evidence_ids  = '[]'
uct2                    = ''
```

### 4.2 Positive bucket — `signor:CSNK2A1__ATF1__phos__positive`

```
─── claims row ─────────────────────────────────────────────────────
claim_id                = 'signor:CSNK2A1__ATF1__phos__positive'
claim_type              = 'PhosphorylationClaim'
status                  = ''
human_readable          = 'CSNK2A1 phosphorylates ATF1 → activates ATF1 transcriptional activity'
proof_level             = 7
p_value                 = NULL
q_value                 = NULL
confidence_interval     = NULL
n_studies               = 47
n_modalities            = 1
source_dataset          = 'Signor_v3.1'
assay_type              = 'curated_literature'
created_at              = '2026-04-21T14:32:00Z'
created_by              = 'signor_curated_import'
description             = ''
superseded_by           = ''
full_data               = '{}'
evidence_status         = 'externally_supported'
prior_art_status        = 'canonical'
review_status           = 'clean'
claim_text              = 'CSNK2A1 phosphorylation of ATF1 increases its transcriptional activity'
context_set_json        = '{}'
edge_signature          = 'b5c9…'
source_release          = 'Signor_2025_Q1'
model_name              = ''
model_version           = ''
artifact_id             = 'signor_v3.1_2025-01-15.tsv#sha256:…'
context_operator        = 'AND'
source                  = 'signor_curated'
kg_evidence             = '[]'
relation_name           = 'regulates_activity'
relation_polarity       = 'positive'
candidate_gene          = 'HGNC:CSNK2A1'
candidate_id            = 'signor:CSNK2A1__ATF1__phos__positive'
cell_states_json        = '[]'
last_wave_completed     = 0
confidence_summary      = 'established'
narrative               = ''
narrative_updated_at    = ''
n_supporting_results    = 0
n_refuting_results      = 0
n_null_results          = 0
n_inconclusive          = 0
n_assays                = 0
n_datasets              = 0
n_supporting_pmids      = 47
polarity_consistency    = 1.0
decisive_coverage       = 0.0
proxy_coverage          = 0.0
participant_combinator  = ''
parent_claim_id         = 'signor:CSNK2A1__ATF1__phos__general'
refinement_type         = 'context_split'
refinement_rationale    = 'positive polarity bucket of bifurcated curated mechanism'
refinement_confidence   = 1.0
splits_on_dimension     = 'polarity'
is_general              = 0
target_mechanism_ids    = '[]'
inherited_evidence_ids  = '[]'
uct2                    = ''
```

### 4.3 Negative bucket — `signor:CSNK2A1__ATF1__phos__negative`

```
─── claims row ─────────────────────────────────────────────────────
(identical shape to the __positive sibling, with these differences:)

claim_id                = 'signor:CSNK2A1__ATF1__phos__negative'
human_readable          = 'CSNK2A1 phosphorylates ATF1 → inhibits ATF1 / DNA binding'
n_studies               = 12
relation_polarity       = 'negative'
n_supporting_pmids      = 12
claim_text              = 'CSNK2A1 phosphorylation of ATF1 decreases DNA-binding activity'
candidate_id            = 'signor:CSNK2A1__ATF1__phos__negative'
parent_claim_id         = 'signor:CSNK2A1__ATF1__phos__general'
refinement_type         = 'context_split'
refinement_rationale    = 'negative polarity bucket of bifurcated curated mechanism'
```

### 4.4 The participants for all three claims

```
─── claim_participants ─────────────────────────────────────────────
claim_id                                  entity_id          role           properties
signor:CSNK2A1__ATF1__phos__general       HGNC:CSNK2A1       subject        {"principal": true}
signor:CSNK2A1__ATF1__phos__general       HGNC:ATF1          object         {"principal": true}
signor:CSNK2A1__ATF1__phos__positive      HGNC:CSNK2A1       subject        {"principal": true}
signor:CSNK2A1__ATF1__phos__positive      HGNC:ATF1          object         {"principal": true}
signor:CSNK2A1__ATF1__phos__negative      HGNC:CSNK2A1       subject        {"principal": true}
signor:CSNK2A1__ATF1__phos__negative      HGNC:ATF1          object         {"principal": true}
```

### 4.5 The structural edges between them

```
─── claim_relations ────────────────────────────────────────────────
relation_id        source_claim_id                              target_claim_id                            relation_type     confidence  rationale            properties
rel_split_of_…     signor:CSNK2A1__ATF1__phos__positive         signor:CSNK2A1__ATF1__phos__general        context_split_of  1.0         polarity bucket      {"dimension":"polarity","scope_value":"positive"}
rel_split_of_…     signor:CSNK2A1__ATF1__phos__negative         signor:CSNK2A1__ATF1__phos__general        context_split_of  1.0         polarity bucket      {"dimension":"polarity","scope_value":"negative"}
rel_competes_…     signor:CSNK2A1__ATF1__phos__positive         signor:CSNK2A1__ATF1__phos__negative       competes_with     0.9         opposite-polarity    {}
                                                                                                                                          siblings under the
                                                                                                                                          same general parent
```

### 4.6 The support sets

```
─── support_sets ───────────────────────────────────────────────────
support_set_id              claim_id                                       label                          stance     logic  evidence_ids        confidence  proof_level
ss-csnk2a1-atf1-pos-1       signor:CSNK2A1__ATF1__phos__positive           Signor curated PMIDs           supports   AND    ['ev-pmid-…',…×47]  0.95        7
ss-csnk2a1-atf1-neg-1       signor:CSNK2A1__ATF1__phos__negative           Signor curated PMIDs           supports   AND    ['ev-pmid-…',…×12]  0.92        7
```

### 4.7 No `biological_results` rows

The Signor curated import produces no `biological_results` rows;
all evidence is literature-grounded and lives in `support_sets`
(via `evidence_ids` referencing `evidence` table publication rows).
A typical Signor claim has `n_supporting_results = 0` but
`n_supporting_pmids` ≥ 1.

### 4.8 The shape of the bifurcation

```
                   signor:CSNK2A1__ATF1__phos__general
                   relation_name      = 'phosphorylates'
                   relation_polarity  = ''  (NOT_APPLICABLE — PTM event)
                   is_general         = 1
                   confidence_summary = 'established'
                   /                              \
                  / context_split_of              \ context_split_of
                 /  (dimension=polarity)           \ (dimension=polarity)
                ▼                                   ▼
   …__phos__positive                            …__phos__negative
   relation_name     = 'regulates_activity'     relation_name     = 'regulates_activity'
   relation_polarity = 'positive'               relation_polarity = 'negative'
   n_supporting_pmids = 47                      n_supporting_pmids = 12
                ◄────────  competes_with  ────────►
```

The general parent encodes "this PTM event happens"; the two
children encode "and the consequence on ATF1's activity is +" vs
"and the consequence is −". Curated literature backs both — the
correct bucket in any given context is determined by the cell
state / co-factors, which is why both are kept rather than one
superseding the other.

---

## 5. Worked example B — parent / chain-link child mechanism pair

A composite mechanism claim plus one of the chain-link leaves
inside its causal chain. This pattern is the typical
hypothesis-then-decompose flow: the parent asserts a high-level
phenotype consequence; the chain-link children name each
mechanistic step that has to hold for the parent to be true.

### 5.1 Parent (composite) — `mh:PTEN-loss-AKT-glioma-proliferation`

```
─── claims row ─────────────────────────────────────────────────────
claim_id                = 'mh:PTEN-loss-AKT-glioma-proliferation'
claim_type              = 'MechanismHypothesisClaim'
status                  = ''
human_readable          = 'PTEN loss drives PI3K/AKT-dependent proliferation in glioblastoma'
proof_level             = 5     (perturbational_phenotypic)
p_value                 = NULL
q_value                 = NULL
confidence_interval     = NULL
n_studies               = 4
n_modalities            = 3
source_dataset          = ''
assay_type              = ''
created_at              = '2026-04-29T10:18:42Z'
created_by              = 'gbd_agent'
description             = ''
superseded_by           = ''
full_data               = '{...StructuredClaim payload...}'
evidence_status         = 'replicated'
prior_art_status        = 'related_prior_art'
review_status           = 'clean'
claim_text              = 'PTEN loss in glioblastoma derepresses the PI3K/AKT axis, driving cell-cycle entry and proliferation. The composite asserts the cohort-level outcome; the four chain links assert each mechanistic step.'
context_set_json        = '{"cancer_type":"MONDO:glioblastoma_multiforme","cell_compartment":"tumor_intrinsic"}'
edge_signature          = '4f2a…'
source_release          = ''
model_name              = ''
model_version           = ''
artifact_id             = ''
context_operator        = 'AND'
source                  = 'literature_gap'
kg_evidence             = '["bb-pten-pi3k","bb-akt-mtor","bb-mki67-proliferation"]'
relation_name           = 'drives_phenotype'
relation_polarity       = 'positive'
candidate_gene          = 'HGNC:PTEN'
candidate_id            = 'mh:PTEN-loss-AKT-glioma-proliferation'
cell_states_json        = '[]'
last_wave_completed     = 3
confidence_summary      = 'moderate'
narrative               = ''
narrative_updated_at    = ''
n_supporting_results    = 5
n_refuting_results      = 1
n_null_results          = 0
n_inconclusive          = 2
n_assays                = 4
n_datasets              = 3
n_supporting_pmids      = 12
polarity_consistency    = 0.83
decisive_coverage       = 0.75
proxy_coverage          = 0.50
participant_combinator  = ''
parent_claim_id         = ''                  ← root of its tree
refinement_type         = ''
refinement_rationale    = ''
refinement_confidence   = NULL
splits_on_dimension     = ''
is_general              = 0
target_mechanism_ids    = '[]'
inherited_evidence_ids  = '[]'
uct2                    = '0.71'
```

### 5.2 Child (chain-link leaf) — `mh:PTEN-loss-AKT-glioma-proliferation__link-1-pten-phosphatase`

The first link in the parent's causal chain: PTEN's lipid-phosphatase
activity dephosphorylates PIP3 to PIP2, terminating PI3K signaling.

```
─── claims row ─────────────────────────────────────────────────────
claim_id                = 'mh:PTEN-loss-AKT-glioma-proliferation__link-1-pten-phosphatase'
claim_type              = 'CausalChainLinkClaim'
status                  = ''
human_readable          = 'PTEN dephosphorylates PIP3 to PIP2 (lipid phosphatase activity)'
proof_level             = 4     (perturbational_molecular)
p_value                 = NULL
q_value                 = NULL
confidence_interval     = NULL
n_studies               = 2
n_modalities            = 2
source_dataset          = ''
assay_type              = ''
created_at              = '2026-04-29T10:18:43Z'
created_by              = 'gbd_agent'
description             = ''
superseded_by           = ''
full_data               = '{...}'
evidence_status         = 'mechanistic'
prior_art_status        = 'canonical'
review_status           = 'clean'
claim_text              = 'PTEN protein dephosphorylates phosphatidylinositol-3,4,5-trisphosphate (PIP3) at the 3 position to produce PIP2'
context_set_json        = '{}'
edge_signature          = 'c91d…'
source_release          = ''
model_name              = ''
model_version           = ''
artifact_id             = ''
context_operator        = 'AND'
source                  = 'kg_traversal'
kg_evidence             = '["bb-pten-pip3"]'
relation_name           = 'dephosphorylates'
relation_polarity       = ''                  ← NOT_APPLICABLE (enzymatic event)
candidate_gene          = 'HGNC:PTEN'
candidate_id            = 'mh:PTEN-loss-AKT-glioma-proliferation__link-1-pten-phosphatase'
cell_states_json        = '[]'
last_wave_completed     = 3
confidence_summary      = 'strong'
narrative               = ''
narrative_updated_at    = ''
n_supporting_results    = 3
n_refuting_results      = 0
n_null_results          = 0
n_inconclusive          = 0
n_assays                = 2
n_datasets              = 2
n_supporting_pmids      = 8
polarity_consistency    = 1.0
decisive_coverage       = 1.0
proxy_coverage          = 0.0
participant_combinator  = ''
parent_claim_id         = 'mh:PTEN-loss-AKT-glioma-proliferation'
refinement_type         = 'chain_link'
refinement_rationale    = 'Step 1 of the parent mechanism: lipid phosphatase activity'
refinement_confidence   = 0.95
splits_on_dimension     = ''
is_general              = 0
target_mechanism_ids    = '[]'
inherited_evidence_ids  = '[]'
uct2                    = '0.62'
```

### 5.3 Their participants

```
─── claim_participants ─────────────────────────────────────────────
claim_id                                                              entity_id            role               properties
mh:PTEN-loss-AKT-glioma-proliferation                                 HGNC:PTEN            effector_gene      {"principal": true, "alteration":"loss"}
mh:PTEN-loss-AKT-glioma-proliferation                                 MONDO:GBM            outcome            {"principal": true}
mh:PTEN-loss-AKT-glioma-proliferation                                 HGNC:AKT1            mediator           {"principal": false, "compartment":"tumor_intrinsic"}
mh:PTEN-loss-AKT-glioma-proliferation                                 MONDO:glioblastoma   context_cancer_type{"principal": false}
mh:PTEN-loss-…__link-1-pten-phosphatase                               HGNC:PTEN            subject            {"principal": true}
mh:PTEN-loss-…__link-1-pten-phosphatase                               CHEBI:PIP3           object             {"principal": true}
```

### 5.4 The edge between them

```
─── claim_relations ────────────────────────────────────────────────
relation_id        source_claim_id                                                         target_claim_id                            relation_type    confidence  rationale                                              properties
rel_chain_link_…   mh:PTEN-loss-AKT-glioma-proliferation__link-1-pten-phosphatase         mh:PTEN-loss-AKT-glioma-proliferation      chain_link_of    0.95        Step 1: PTEN's lipid-phosphatase activity hydrolyses    {"step":1,"step_role":"perturbation","is_canonical_backbone":true}
                                                                                                                                                                  PIP3 — without this, the rest of the chain doesn't fire
```

The parent has its own structural-parent edges to its other three
chain links (`__link-2-akt-activation`, `__link-3-mtor-engagement`,
`__link-4-cell-cycle-entry`); each one carries
`properties.step` = 1, 2, 3, 4 respectively. Together the four
links AND together to support the parent.

### 5.5 Their evidence

The parent carries cohort-level evidence (TCGA GBM survival, scRNA
proliferation signatures, IHC); the leaf carries direct enzymatic
evidence (in-vitro lipid phosphatase assay, NMR of PIP3 conversion).

```
─── biological_results — PARENT (mh:PTEN-loss-AKT-glioma-proliferation) ─────────
result_id            claim_id                        result_type   assay                                       provider             outcome      effect_size  p_value     n      statistical_test_performed  evidence_category    timestamp
br-pten-coxhr-1      mh:PTEN-loss-AKT-…              analysis      Cox proportional hazards (TCGA GBM)         provider:tcga        positive     2.4          1.2e-7      144    1                           statistical_test     2026-04-29T09:50Z
br-pten-tide-1       mh:PTEN-loss-AKT-…              analysis      TIDE proliferation signature                 provider:tide        positive     0.81         3.4e-5      288    1                           statistical_test     2026-04-29T10:01Z
br-pten-mki67-1      mh:PTEN-loss-AKT-…              analysis      MKI67 IHC tissue array                       provider:ihc_tcga    positive     1.6          0.004       62     1                           statistical_test     2026-04-29T10:08Z
br-pten-tcga-meta-1  mh:PTEN-loss-AKT-…              meta_analysis Pearson correlation across CPTAC GBM         provider:cptac       inconclusive 0.18         0.061       19     1                           statistical_test     2026-04-29T10:14Z
br-pten-depmap-1     mh:PTEN-loss-AKT-…              analysis      DepMap CRISPR co-essentiality (PTEN, MTOR)   provider:depmap      negative     -0.12        0.028       1115   1                           statistical_test     2026-04-29T10:17Z
                                                                                                                                                                                                                                  ↑ this row contradicts the parent's
                                                                                                                                                                                                                                    polarity → fed into n_refuting_results

─── biological_results — CHILD (…__link-1-pten-phosphatase) ─────────────────────
result_id            claim_id                                          result_type   assay                                       provider              outcome   effect_size  p_value     n      statistical_test_performed  evidence_category    timestamp
br-pten-lipid-1      …__link-1-pten-phosphatase                        analysis      In-vitro lipid phosphatase assay (PIP3→PIP2) provider:in_vitro     positive  0.71         1.4e-9      6      1                           statistical_test     2026-04-29T10:18Z
br-pten-nmr-1        …__link-1-pten-phosphatase                        analysis      31P-NMR of PIP3 conversion                  provider:nmr_assay    positive  1.0          5e-6        4      1                           statistical_test     2026-04-29T10:19Z
br-pten-clinvar-1    …__link-1-pten-phosphatase                        lookup        ClinVar PTEN catalytic-domain variants      provider:clinvar      positive  1.0          NULL        47     0                           qualitative_finding  2026-04-29T10:21Z
                                                                                                                                                                                                                                  ↑ all three results agree — this leaf
                                                                                                                                                                                                                                    is the most directly-supported piece
                                                                                                                                                                                                                                    of the parent's mechanism
```

### 5.6 The two evidence buckets

The parent's `n_supporting_results = 5` counts only the parent's
own attached results (the 5 rows above); the leaf's `n_supporting_results = 3`
counts only the leaf's own. Neither claim's row shows the other's
count.

To answer "what is the total evidence supporting the parent
mechanism?" — you walk `claim_relations` from the parent down,
collecting each descendant's `biological_results`. The parent has
its own 5 rows plus its 4 chain-link descendants' rows (3 from
the example leaf + however many the other 3 leaves have). Same
SQL pattern as in §6.2 below.

---

## 6. Edge access patterns

### 6.1 Direct evidence on a claim

```sql
-- Every result attached to one specific claim
SELECT br.*
  FROM biological_results br
  LEFT JOIN result_to_claim rtc
         ON rtc.result_id = br.result_id
        AND rtc.claim_id  = br.claim_id
 WHERE br.claim_id = :cid
   AND (rtc.result_id IS NULL OR rtc.attached = 1);
```

### 6.2 Subtree evidence — every result attached to any descendant

```sql
WITH RECURSIVE tree(claim_id, depth) AS (
    SELECT source_claim_id AS claim_id, 0
      FROM claim_relations
     WHERE target_claim_id = :composite_id
       AND relation_type IN ('chain_link_of','context_split_of',
                             'mediator_specific_of','polarity_inverse_of',
                             'branches_from')
    UNION ALL
    SELECT cr.source_claim_id, t.depth + 1
      FROM claim_relations cr JOIN tree t ON cr.target_claim_id = t.claim_id
     WHERE cr.relation_type IN ('chain_link_of','context_split_of',
                                'mediator_specific_of','polarity_inverse_of',
                                'branches_from')
       AND t.depth < 10
)
SELECT br.*
  FROM tree t
  JOIN biological_results br ON br.claim_id = t.claim_id
  LEFT JOIN result_to_claim rtc
         ON rtc.result_id = br.result_id AND rtc.claim_id = br.claim_id
 WHERE rtc.result_id IS NULL OR rtc.attached = 1;
```

### 6.3 Promotion — leaf becomes a `backbone_edges` row

When a leaf claim graduates (`evidence_status = 'externally_supported'`,
sufficient `n_supporting_results`, no open `contradicts` edges), its
content already matches the encoding of `backbone_edges` exactly:

```
LEAF claim:                                  backbone_edges row:
  participants[role=subject].entity_id  ─→     source_id
  participants[role=object].entity_id   ─→     target_id
  relation_name + relation_polarity     ─→     relation_name + relation_polarity
  edge_signature                        ─→     edge_id (or stable hash)
```

This is why every leaf's structure is locked to "exactly one
SUBJECT participant + exactly one OBJECT participant" — that's
what makes a leaf isomorphic to a typed graph edge.
