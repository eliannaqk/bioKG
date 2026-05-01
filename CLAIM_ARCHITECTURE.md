# Claim Object

Final schema for `claims` and its satellites. The claim object is the
reified edge in the biological KG: it connects participant entities
through a typed relation, carries context and status, and can itself be
connected into a claim DAG of mechanistic child claims. Analysis work is
stored once and linked to any number of claims through claim-specific
interpretations.

---

## 1. Where the data lives

A claim's persistence is split across **nine logical stores**. Each
store owns one axis; content, DAG structure, analysis work, and
claim-specific evidence interpretation are not duplicated.

```
                       ┌────────────────────────────────────┐
                       │               CLAIMS               │
                       │                                    │
                       │  Content:                          │
                       │    claim_text, relation_name,      │
                       │    relation_polarity               │
                       │  Context scope:                    │
                       │    context_set_json,               │
                       │    cell_states_json,               │
                       │    context_operator,               │
                       │    participant_combinator          │
                       │  Status and confidence:            │
                       │    evidence_status,                │
                       │    prior_art_status,               │
                       │    review_status,                  │
                       │    confidence_summary              │
                       │  Rollups from interpretations:     │
                       │    n_supporting_results,           │
                       │    n_refuting_results,             │
                       │    n_null_results, n_datasets, ... │
                       │  Identity + run state:             │
                       │    edge_signature, full_data,      │
                       │    last_wave_completed, uct2       │
                       └─────────────────┬──────────────────┘
                                         │
            ┌────────────────────────────┼────────────────────────────┐
            ▼                            ▼                            ▼
   ┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
   │ claim_participants   │    │ claim_relations      │    │ result_to_claim      │
   │                      │    │ (claim DAG edges)    │    │ / interpretations    │
   │ entity_id, role,     │    │                      │    │                      │
   │ properties JSON      │    │ child/source claim,  │    │ claim_id, result_id, │
   │                      │    │ parent/target claim, │    │ stance, relevance,   │
   │ principal flags,     │    │ relation_type,       │    │ rationale_text,      │
   │ role groups,         │    │ rationale,           │    │ context_fit,         │
   │ required/optional    │    │ confidence,          │    │ proof_node_id,       │
   │                      │    │ relation_context,    │    │ attached             │
   │ Roles: subject-side, │    │ properties JSON      │    │                      │
   │ object-side,         │    │                      │    │ Claim-specific       │
   │ mediator, context    │    │ See §3.              │    │ evidence meaning.    │
   └──────────────────────┘    └──────────────────────┘    └──────────┬───────────┘
                                                                      │
                                                                      ▼
   ┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
   │ analysis_runs        │    │ biological_results   │    │ support_sets         │
   │ (reusable work)      │    │ (result rows from    │    │ (AND-grouped         │
   │                      │    │  reusable work)      │    │  interpreted results)│
   │ analysis_id, tool,   │    │                      │    │                      │
   │ dataset/cohort ids,  │◄───┤ result_id,           │    │ stance: supports /   │
   │ params_hash, code    │    │ analysis_id, assay,  │    │   contradicts /      │
   │ version, artifacts,  │    │ outcome, effect_size,│    │   refines            │
   │ status, timestamps   │    │ p_value, n, context, │    │ logic = AND          │
   │                      │    │ statistics JSON      │    │ confidence (0-1)     │
   └──────────────────────┘    └──────────────────────┘    └──────────────────────┘

   ┌──────────────────────┐    ┌──────────────────────┐
   │ publication_support  │    │ claim_events         │
   │ (per-claim lit       │    │ (append-only audit   │
   │  rollup)             │    │  trail)              │
   │                      │    │                      │
   │ authority_level,     │    │ axis, old_value,     │
   │ n_supporting,        │    │ new_value, reason,   │
   │ n_contradicting,     │    │ actor, wave,         │
   │ pmids                │    │ timestamp            │
   └──────────────────────┘    └──────────────────────┘
```

- **claims**: content + status only.
- **claim_participants**: which KG entities participate in the claim, their roles, and principal edge anchors.
- **claim_relations**: claim DAG edges between parent and child claim objects, with relation-scoped context.
- **analysis_runs**: reusable computational work over datasets/cohorts.
- **biological_results**: reusable result rows produced by analysis runs; not owned by one claim.
- **result_to_claim**: claim-specific interpretation of a result: support/refute/null, relevance, context fit, and text rationale.
- **support_sets**: AND-grouped bundles of result interpretations.
- **publication_support**: per-claim literature rollup.
- **claim_events**: append-only audit trail.

---

## 1.1 Claim as a KG edge

Entities in the biological KG are not connected by a bare predicate row.
They are connected through a claim object:

```
entity participant(s) ──► Claim(relation_name, polarity, context) ──► entity participant(s)
```

The claim is therefore a reified KG edge or hyperedge. For a binary
claim, the principal subject-side participant and principal object-side
participant define the familiar edge:

```
SETDB1 --[Claim: regulates_expression, positive, melanoma/IFNg context]--> ERV_expression
```

For multi-participant biology, the claim remains one assertion with many
typed participants. The participant table records each entity with a
role, role group, and properties:

- **Subject-side roles**: `subject`, `effector_gene`, `regulator_tf`, `compound`, `perturbation`, `pathway`.
- **Object-side roles**: `object`, `target_gene`, `regulatee`, `outcome`, `phenotype`, `therapy_response`.
- **Mechanistic roles**: `mediator`, `complex_member`, `cofactor`, `substrate`, `product`.
- **Context roles**: `context_cancer_type`, `context_cell_type`, `context_cell_state`, `context_therapy`, `context_mutation`, `context_cell_line`, `context_species`, `confounder`.

`claim_participants.properties` must mark whether a participant is a
principal edge anchor, optional qualifier, required cofactor, or context
qualifier. When there are more than two principal biological entities,
the claim is an n-ary hyperedge. `context_operator` and
`participant_combinator` define whether the participant set is interpreted
as AND, OR, or a named role-group combination.

Load-bearing mechanistic steps should not be hidden as extra participants
inside one flat parent claim. They should be represented as child claims
in the claim DAG, linked back to the parent with a relation-scoped
context saying when that child helps make the parent true.

---

## 2. The claim row — every field

41 columns, listed in storage order.

### Identity

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 0 | `claim_id` | TEXT | — | Unique stable id (PRIMARY KEY). |
| 1 | `claim_type` | TEXT | — | Enum value from `ClaimType` (e.g. `GeneGeneCorrelationClaim`, `MechanismHypothesisClaim`, `CausalChainLinkClaim`, `PhosphorylationClaim`, …). |
| 2 | `status` | TEXT | `''` | Free-text legacy status; superseded by `evidence_status` / `review_status`. |

### Content — what the claim asserts

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 18 | `claim_text` | TEXT | `''` | Atomic statement in natural language. |
| 12 | `description` | TEXT | `''` | Long-form description (often empty). |
| 3 | `human_readable` | TEXT | `''` | One-liner for logs and paper sections. |
| 22 | `relation_name` | TEXT | `''` | Typed predicate from the relation registry (e.g. `regulates_mrna_stability`, `phosphorylates`, `binds`, `drives_phenotype`). |
| 23 | `relation_polarity` | TEXT | `''` | `positive` / `negative` / `bidirectional` / `null` / `unknown` / `''` (= NOT_APPLICABLE — the predicate carries no sign, e.g. `binds`). |

### Status — three orthogonal axes

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 15 | `evidence_status` | TEXT | `'draft'` | Where on the evidence ladder: `draft` / `observed` / `replicated` / `causal` / `mechanistic` / `externally_supported`. |
| 16 | `prior_art_status` | TEXT | `'unsearched'` | PubMed adjudication: `unsearched` / `canonical` / `related_prior_art` / `context_extension` / `evidence_upgrade` / `plausibly_novel` / `ambiguous`. |
| 17 | `review_status` | TEXT | `'clean'` | Lifecycle: `clean` / `in_review` / `contradicted` / `superseded` / `needs_experiment`. |
| 13 | `superseded_by` | TEXT | `''` | If superseded, the `claim_id` that replaces this one. |

### Proof + cross-evidence aggregates

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 4 | `proof_level` | INTEGER | `2` | 1=ontology_fact, 2=observational_assoc, 3=model_prediction, 4=perturbational_molecular, 5=perturbational_phenotypic, 6=orthogonal_reproduction, 7=published_established. |
| 8 | `n_studies` | INTEGER | `0` | How many independent studies. |
| 9 | `n_modalities` | INTEGER | `0` | How many distinct evidence modalities. |
| 29 | `n_supporting_results` | INTEGER | `0` | COUNT attached `result_to_claim.stance='supports'`. |
| 30 | `n_refuting_results` | INTEGER | `0` | COUNT attached `result_to_claim.stance='refutes'`. |
| 31 | `n_null_results` | INTEGER | `0` | COUNT attached `result_to_claim.stance='null'`. |
| 32 | `n_inconclusive` | INTEGER | `0` | COUNT attached `result_to_claim.stance='inconclusive'`. |
| 33 | `n_assays` | INTEGER | `0` | DISTINCT assays from attached `biological_results`. |
| 34 | `n_datasets` | INTEGER | `0` | DISTINCT datasets/cohorts from attached `analysis_runs`. |
| 35 | `n_supporting_pmids` | INTEGER | `0` | Literature supporting count. |
| 36 | `polarity_consistency` | REAL | `0.0` | Fraction of results whose polarity matches the claim's. |
| 37 | `decisive_coverage` | REAL | `0.0` | (n_supporting + n_refuting) / total_results. |
| 38 | `proxy_coverage` | REAL | `0.0` | Coverage of proxy assays. |

### Categorical confidence + narrative

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 26 | `confidence_summary` | TEXT | `'unknown'` | 5-level ordinal: `unknown` / `weak` / `moderate` / `strong` / `established`. Derived from `evidence_status`, `prior_art_status`, `review_status`, `proof_level`, `n_studies`, `n_modalities`. |
| 27 | `narrative` | TEXT | `''` | LLM-rendered prose summary. |
| 28 | `narrative_updated_at` | TEXT | `''` | ISO timestamp of last narrative regeneration. |

### Context

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 19 | `context_set_json` | TEXT | `'{}'` | Typed graph projection of biological context (cell type / cancer type / immune state / therapy / cell line). |
| 24 | `cell_states_json` | TEXT | `'[]'` | List of `CellStateCondition` (e.g. exhausted CD8, IFNγ-exposed). |
| 21 | `context_operator` | TEXT | `'AND'` | How participants combine: `AND` / `OR`. |
| 39 | `participant_combinator` | TEXT | `''` | For composite multi-effector claims (`OR` for pathway redundancy). |

### Identity dedup

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 20 | `edge_signature` | TEXT | `''` | SHA-256 of (subject\|relation\|object) — cross-source dedup key. Polarity intentionally NOT in the signature (opposite-polarity claims about the same triple are the same biological assertion under contention). |

### Run state

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 14 | `full_data` | TEXT | `'{}'` | Serialised `StructuredClaim` payload (parsed ontology output). |
| 25 | `last_wave_completed` | INTEGER | `0` | Highest wave that touched this claim. |
| 40 | `uct2` | TEXT | `''` | Serialized UCT2 proof-search state: `EvidenceCoverageMatrix` plus `DynamicProofDAG` nodes/edges, proof-node gaps, visit/value counts, and selected work history. |

### Audit

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 10 | `created_at` | TEXT | `''` | ISO timestamp of insertion. |
| 11 | `created_by` | TEXT | `''` | Actor: `gbd_agent`, `manual`, `signor_curated_import`, etc. |

### Flat statistics (kept for legacy readers)

| # | Column | Type | Default | Meaning |
|---|---|---|---|---|
| 5 | `p_value` | REAL | NULL | Flat p-value summary (one winner across attached results). |
| 6 | `q_value` | REAL | NULL | Flat q-value. |
| 7 | `confidence_interval` | TEXT | NULL | Flat CI string. |

> Authoritative per-result statistics are on `biological_results`. Claim-specific support/refutation lives on `result_to_claim`; these row-level columns are fast reads for legacy callers.

---

## 3. Claim DAG: `claim_relations` edges

`claim_relations` stores edges between claim objects. Structural edges
form the claim DAG: child claims are possible mechanistic, contextual, or
polarity-specific ways a parent claim could become true or false.
Non-structural edges capture comparison, contradiction, corroboration, or
supersession.

```
STRUCTURAL CLAIM-DAG EDGES:

  claim_dag_of          - canonical child-in-parent-DAG edge.
                          A child claim is a node in one or more
                          possible mechanism paths for the parent.
                          Within a path the nodes AND; across paths
                          they OR. One complete supported path can
                          satisfy the parent.

  branches_from         - mechanism alternative.
                          "MH-1 is one way the parent could be true."

  context_split_of      - per-context decomposition.
                          "The melanoma slice of the pan-cancer claim."

  mediator_specific_of  - alternative mechanism specific to one DAG node.
                          "Alternative effector for the same step."

  polarity_inverse_of   - auto-disproof inverse claim.

NON-STRUCTURAL EDGES:

  refines               - supersession.
  competes_with         - mutual exclusion under joint investigation.
  contradicts           - open polarity or refutation conflict.
  corroborates          - extra support without supersession.
  enables               - PTM event -> consequence linkage
                          (e.g. phosphorylation_event enables regulates_activity).
```

`chain_dag_of` is the legacy name for `claim_dag_of`. Readers should
accept both during migration; writers should emit `claim_dag_of`.

`properties` JSON shape per relation_type:

```python
# claim_dag_of - DAG topology plus parent-scoped context
{
    "path_ids": ["p1", "p2"],             # paths this child lies on
    "step_in_path": {"p1": 2, "p2": 1},   # position per path
    "predecessor_claim_ids": [            # immediate upstream claims
        "claim_id_a",
        "claim_id_b"
    ],
    "step_role": "molecular_consequence", # perturbation /
                                          # molecular_consequence /
                                          # cellular_phenotype /
                                          # human_relevance / intermediate
    "aggregation_logic": "AND_WITHIN_PATH_OR_ACROSS_PATHS",
    "is_canonical_backbone": True,
    "dag_generation_method": "dynamic_planner",
    "mechanism_hypothesis_id": "MH-1",

    # Edge-scoped context: when this child helps this parent.
    # This is separate from the child's intrinsic context_set_json.
    "relation_context_set_json": {
        "cancer_type": "melanoma",
        "therapy": "anti-PD1",
        "perturbation": "SETDB1 overexpression",
        "immune_context": "IFNg-exposed tumor microenvironment"
    },
    "context_inheritance": "narrow_parent",
    "supports_parent_under_context": True,
    "context_rationale": "ERV regulation is relevant to PD1 resistance only in the anti-PD1 melanoma context."
}

# branches_from
{"mechanism_id": "MH-1", "plausibility": "high",
 "layer": "post_transcriptional", "eager_seeded": True}

# context_split_of
{"dimension": "tissue", "scope_value": "melanoma"}

# mediator_specific_of
{"mediator_entity_id": "HGNC:RC3H1",
 "alt_for_claim_id": "parent...__step-2"}

# polarity_inverse_of
{"auto_created_at": "2026-04-29T...",
 "trigger_posterior": 0.12,
 "inherited_interpretation_ids": [...]}
```

**Claim DAG semantics:** AND within a path (`path_ids[i]`), OR across
paths. Any one complete supported path can satisfy the parent. A child
claim can appear in multiple paths and under multiple parents, but each
parent edge carries its own relation context and rationale.

**Lineage:** DAG, not tree. Multi-parent and multi-edge-to-one-parent are
allowed; cycles are rejected at write time.

### 3.1 Context on child claims vs DAG edges

A child claim has its own intrinsic context in `claims.context_set_json`.
The relation from child to parent also has edge-scoped context in
`claim_relations.properties.relation_context_set_json`.

Example:

```
Parent claim:
  SETDB1 overexpression causes anti-PD1 resistance in melanoma

Child claim:
  SETDB1 positively regulates ERV expression

Child intrinsic context:
  tumor cells, SETDB1-high state

DAG edge context:
  anti-PD1-treated melanoma where ERV/interferon signaling is a proposed
  mechanism connecting SETDB1 overexpression to resistance
```

The child is not globally sufficient for the parent. It supports the
parent only under the DAG edge context. This lets the same child claim be
reused under a different parent with a different rationale, or not reused
when the parent context makes the mechanism irrelevant.

### 3.2 How the claim DAG is created

When a parent claim is created, the system should create or update a
claim DAG as part of claim initialization:

1. Parse the parent into a structured claim: `relation_name`,
   `relation_polarity`, participants, and context.
2. Normalize participants and choose principal edge anchors for
   `edge_signature`.
3. Build the parent context set from explicit context participants and
   parsed qualifiers.
4. Ask the dynamic claim-DAG planner for possible mechanism paths,
   context splits, polarity inverses, and alternative mediator branches.
5. Persist each proposed child as a normal claim row with its own
   participants, relation, polarity, and intrinsic context.
6. Persist `claim_relations` rows from child claim to parent claim using
   `claim_dag_of` or the more specific structural relation type. Store
   path metadata and relation-scoped context on the edge.
7. Initialize UCT2 on the parent and each child so proof search has a
   `DynamicProofDAG` and evidence coverage matrix from the start.
8. Let UCT1 choose which claim/subtree to spend the next wave on; let
   UCT2 choose which proof node or evidence gap inside the focal claim to
   execute.

The DAG may be dynamic. Later results, contradictions, or planner waves
can add children, mark paths inactive, create context splits, or attach
new parent edges to an existing child claim.

---

## 4. Worked example A — bifurcated claim (Signor curated)

A general parent + two polarity-bucket children, written when curated literature reports both signs of the same triple. `context_set_json` on each bucket records the residue / co-factor / cell state that distinguishes them.

### 4.1 Parent — `signor:CSNK2A1__ATF1__phos__general`

```
─── claims row ─────────────────────────────────────────────────────
claim_id                = 'signor:CSNK2A1__ATF1__phos__general'
claim_type              = 'PhosphorylationClaim'
status                  = ''
human_readable          = 'CSNK2A1 phosphorylates ATF1 (mechanism — polarity context-dependent)'
proof_level             = 7        (published_established)
p_value                 = NULL
q_value                 = NULL
confidence_interval     = NULL
n_studies               = 59
n_modalities            = 1
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
edge_signature          = '8a7c…'   (SHA-256 of HGNC:CSNK2A1|phosphorylates|HGNC:ATF1)
context_operator        = 'AND'
relation_name           = 'phosphorylates'
relation_polarity       = ''        ← polarity_kind=NOT_APPLICABLE
                                     (phosphorylation is a PTM event;
                                      the +/- consequence on ATF1 activity
                                      is the bifurcation, not the PTM itself)
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
created_at              = '2026-04-21T14:32:00Z'
created_by              = 'signor_curated_import'
description             = ''
superseded_by           = ''
full_data               = '{}'
evidence_status         = 'externally_supported'
prior_art_status        = 'canonical'
review_status           = 'clean'
claim_text              = 'CSNK2A1 phosphorylation of ATF1 increases its transcriptional activity'
context_set_json        = '{"residue":"Ser63",
                            "co_factors":["HGNC:CREB1"],
                            "downstream_assay":"CRE_promoter_luciferase",
                            "cell_state":"proliferative"}'
                          ← THIS is why the bucket exists: phosphorylation of
                            Ser63 in the kinase-inducible domain (KID), in
                            cells where CREB1 is the dimerisation partner,
                            increases ATF1 transactivation. Different from the
                            negative bucket's residue + cell context.
edge_signature          = 'b5c9…'
context_operator        = 'AND'
relation_name           = 'regulates_activity'
relation_polarity       = 'positive'
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
context_set_json        = '{"residue":"Thr184",
                            "co_factors":["HGNC:JUN"],
                            "downstream_assay":"EMSA_DNA_binding",
                            "cell_state":"differentiated"}'
                          ← phosphorylation of a DIFFERENT residue (in the
                            DNA-binding domain rather than the KID), with a
                            different dimer partner, in a differentiated
                            cell state — the same PTM event has the opposite
                            consequence on ATF1 function.
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

Signor curated claims carry no `biological_results`. All evidence is literature, in `support_sets.evidence_ids` → `evidence` table. `n_supporting_results = 0`, `n_supporting_pmids ≥ 1`.

### 4.7.1 The `evidence` table — the actual PMIDs

`support_sets.evidence_ids` is a JSON list pointing at rows in
the `evidence` table, one row per cited publication. Schema:

```
evidence_id, evidence_type, description, source,
statistic_name, statistic_value, p_value, effect_size,
sample_size, confidence_interval,
pmid, doi, year, title, accession,
n_samples, organism, perturbation_type, perturbed_gene,
readout, cell_line, model_name, model_version,
cv_metric, cv_value, artifact_path, artifact_hash,
created_at, full_data
```

A handful of rows for the **negative bucket's 12 PMIDs**
(`evidence_ids = ['ev-pmid-15159389', 'ev-pmid-12477932', …×12]`):

```
─── evidence — negative bucket sample ──────────────────────────────
evidence_id        evidence_type  pmid       doi                            year  title                                                                       organism      perturbation_type  perturbed_gene  readout                       cell_line   source                       created_at
ev-pmid-15159389   publication    15159389   10.1074/jbc.M403673200         2004  CK2-mediated phosphorylation of ATF1 modulates DNA-binding affinity         human         knockdown          CSNK2A1         EMSA on CRE element            HeLa        Signor curated literature    2026-04-21T14:32Z
ev-pmid-12477932   publication    12477932   10.1006/bbrc.2002.6722         2002  Casein kinase II phosphorylation reduces ATF1 transcriptional activity     human         pharmacological    CSNK2A1         CRE-luciferase reporter        HEK293      Signor curated literature    2026-04-21T14:32Z
ev-pmid-19124467   publication    19124467   10.1074/jbc.M807762200         2009  CK2 phosphorylation in the bZIP domain abrogates ATF1 DNA binding          human         in_vitro_kinase    CSNK2A1         in-vitro DNA binding          (cell-free) Signor curated literature    2026-04-21T14:32Z
ev-pmid-22113613   publication    22113613   10.1038/onc.2011.553           2012  Threonine-184 phosphorylation of ATF1 by CK2 inhibits CRE engagement       human         site_mutagenesis   CSNK2A1         ChIP-qPCR on CRE                MCF7        Signor curated literature    2026-04-21T14:32Z
…  (8 more rows)
```

A handful of rows for the **positive bucket's 47 PMIDs**:

```
─── evidence — positive bucket sample ──────────────────────────────
evidence_id        evidence_type  pmid       doi                            year  title                                                                                  organism  perturbation_type  perturbed_gene  readout                            cell_line     source                       created_at
ev-pmid-9398070    publication    9398070    10.1074/jbc.272.50.31515       1997  Phosphorylation of ATF1 at Ser-63 by protein kinase CK2 stimulates CRE-binding…       human     point_mutation     CSNK2A1         CRE-luciferase reporter            COS-7         Signor curated literature    2026-04-21T14:32Z
ev-pmid-10867028   publication    10867028   10.1074/jbc.M001775200         2000  Cooperation of CSNK2A1 with CREB1 on activation of CRE-driven transcription           human     coimmunoprecipitation CSNK2A1      CRE-luciferase + co-IP             HEK293        Signor curated literature    2026-04-21T14:32Z
ev-pmid-15604296   publication    15604296   10.1158/0008-5472.CAN-04-2459   2005  CK2-dependent ATF1 Ser63 phosphorylation drives proliferative gene expression in… human    knockdown          CSNK2A1         RNA-seq in CK2 KD              MCF7          Signor curated literature    2026-04-21T14:32Z
…  (44 more rows)
```

> The 47 vs. 12 split mirrors the curated literature: more
> publications find Ser63-mediated activation than Thr184-mediated
> repression. The ratio is informational, not a vote — both buckets
> are independently supported.

### 4.7.2 The `publication_support` rollup

For each polarity bucket, a single `publication_support` row
summarises its citation profile:

```
─── publication_support ────────────────────────────────────────────
claim_id                                    authority_level    authority_score  novelty       n_total_articles  n_direct_evidence  n_tier1_papers  n_with_perturbation  n_supporting  n_contradicting  publications
signor:CSNK2A1__ATF1__phos__positive        established        0.97             canonical     47                47                 18              31                   47            0                ['9398070','10867028','15604296',…×47]
signor:CSNK2A1__ATF1__phos__negative        established        0.91             canonical     12                12                  4               9                   12            0                ['15159389','12477932','19124467','22113613',…×12]
```

### 4.8 The shape of the bifurcation

```
                   signor:CSNK2A1__ATF1__phos__general
                   relation_name      = 'phosphorylates'
                   relation_polarity  = ''  (NOT_APPLICABLE — PTM event)
                   confidence_summary = 'established'
                   context_set_json   = '{}'  (no context narrows the parent)
                   /                              \
                  / context_split_of              \ context_split_of
                 /  (dimension=polarity)           \ (dimension=polarity)
                ▼                                   ▼
   …__phos__positive                            …__phos__negative
   relation_name     = 'regulates_activity'     relation_name     = 'regulates_activity'
   relation_polarity = 'positive'               relation_polarity = 'negative'
   context_set_json:                            context_set_json:
     residue            = Ser63                   residue            = Thr184
     co_factors         = [CREB1]                 co_factors         = [JUN]
     downstream_assay   = CRE_luciferase          downstream_assay   = EMSA_DNA_binding
     cell_state         = proliferative           cell_state         = differentiated
   n_supporting_pmids   = 47                    n_supporting_pmids   = 12
                ◄────────  competes_with  ────────►
```

- Parent: "PTM happens" (polarity NOT_APPLICABLE).
- Children: "PTM consequence on activity is +" vs "is −".
- Selection between buckets is context-driven (residue + co-factor + cell state); both kept, neither supersedes the other.

---

## 5. Worked example B — parent / claim-DAG child mechanism pair

Composite parent (cohort-level phenotype) + claim-DAG child leaf (one mechanistic step). The DAG child claims AND together within a path and OR across alternative paths to support the parent.

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
created_at              = '2026-04-29T10:18:42Z'
created_by              = 'gbd_agent'
description             = ''
superseded_by           = ''
full_data               = '{...StructuredClaim payload...}'
evidence_status         = 'replicated'
prior_art_status        = 'related_prior_art'
review_status           = 'clean'
claim_text              = 'PTEN loss in glioblastoma derepresses the PI3K/AKT axis, driving cell-cycle entry and proliferation. The composite asserts the cohort-level outcome; the child DAG claims assert each mechanistic step.'
context_set_json        = '{"cancer_type":"MONDO:glioblastoma_multiforme","cell_compartment":"tumor_intrinsic"}'
edge_signature          = '4f2a…'
context_operator        = 'AND'
relation_name           = 'drives_phenotype'
relation_polarity       = 'positive'
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
uct2                    = '{"coverage":{...},"dynamic_proof_dag":{...}}'
```

### 5.2 Child DAG claim — `mh:PTEN-loss-AKT-glioma-proliferation__link-1-pten-phosphatase`

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
context_operator        = 'AND'
relation_name           = 'dephosphorylates'
relation_polarity       = ''                  ← NOT_APPLICABLE (enzymatic event)
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
uct2                    = '{"coverage":{...},"dynamic_proof_dag":{...}}'
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

### 5.4 The parent's mechanism DAG

```
                            ┌── link-2 (AKT) ──── link-3 (mTOR) ──┐
                            │                                       ▼
   link-1 (PIP3 hydrolysis)─┤                                     parent
                            │                                       ▲
                            └── link-4 (FOXO) ─── link-5 (CDKN1B) ─┘
```

`link-1` lies on both paths (`path_ids: ["p1","p2"]`); `p1` and `p2` independently AND their nodes; either path satisfies the parent.

```
─── claim_relations — PARENT's claim_dag_of edges ──────────────────
source_claim_id              confidence  properties
…__link-1-pten-phosphatase   0.95        {"path_ids":["p1","p2"], "step_in_path":{"p1":1,"p2":1},
                                          "predecessor_claim_ids":[],
                                          "step_role":"perturbation",          "is_canonical_backbone":true}
…__link-2-akt-activation     0.92        {"path_ids":["p1"],      "step_in_path":{"p1":2},
                                          "predecessor_claim_ids":["…__link-1-pten-phosphatase"],
                                          "step_role":"molecular_consequence", "is_canonical_backbone":true}
…__link-3-mtor-engagement    0.90        {"path_ids":["p1"],      "step_in_path":{"p1":3},
                                          "predecessor_claim_ids":["…__link-2-akt-activation"],
                                          "step_role":"cellular_phenotype",    "is_canonical_backbone":true}
…__link-4-foxo-derepression  0.85        {"path_ids":["p2"],      "step_in_path":{"p2":2},
                                          "predecessor_claim_ids":["…__link-1-pten-phosphatase"],
                                          "step_role":"molecular_consequence", "is_canonical_backbone":true}
…__link-5-cdkn1b-down        0.83        {"path_ids":["p2"],      "step_in_path":{"p2":3},
                                          "predecessor_claim_ids":["…__link-4-foxo-derepression"],
                                          "step_role":"cellular_phenotype",    "is_canonical_backbone":true}
```

(All five rows have `target_claim_id = mh:PTEN-loss-AKT-glioma-proliferation`, `relation_type = claim_dag_of`.)

### 5.5 Reusable analysis work and claim-specific interpretations

Parent: cohort-level (TCGA Cox HR, TIDE, IHC). Leaf: direct enzymatic (lipid phosphatase assay, ³¹P-NMR, ClinVar).

```
─── analysis_runs — reusable work, not claim-owned ───────────────────────────────
analysis_id           tool/provider       dataset_or_cohort      params_hash  status     artifact_uri
ar-pten-coxhr-1       provider:tcga       TCGA-GBM clinical      h_tcga_01    complete   s3://.../pten_coxhr.json
ar-pten-depmap-1      provider:depmap     DepMap CRISPR 24Q1     h_dep_04     complete   s3://.../pten_mtor_depmap.json
ar-pten-lipid-1       provider:in_vitro   lipid phosphatase set  h_lip_02     complete   s3://.../pten_lipid_assay.json

─── biological_results — result rows produced by reusable work ───────────────────
result_id            analysis_id          result_type   assay                                      outcome       effect_size  p_value   n     statistics_json
br-pten-coxhr-1      ar-pten-coxhr-1      analysis      Cox proportional hazards (TCGA GBM)        positive      2.4          1.2e-7    144   {"endpoint":"survival"}
br-pten-depmap-1     ar-pten-depmap-1     analysis      DepMap CRISPR co-essentiality (PTEN,MTOR)  negative     -0.12        0.028     1115  {"screen":"CRISPR"}
br-pten-lipid-1      ar-pten-lipid-1      analysis      In-vitro lipid phosphatase assay           positive      0.71         1.4e-9    6     {"substrate":"PIP3"}

─── result_to_claim — claim-specific interpretation of each result ───────────────
interpretation_id   result_id         claim_id                                 stance    relevance   attached  rationale_text
rtc-coxhr-parent    br-pten-coxhr-1   mh:PTEN-loss-AKT-glioma-proliferation    supports  decisive    1         "PTEN loss associates with the parent phenotype in the specified GBM cohort."
rtc-depmap-parent   br-pten-depmap-1  mh:PTEN-loss-AKT-glioma-proliferation    refutes   supportive  1         "The PTEN-MTOR co-essentiality direction conflicts with the positive parent polarity."
rtc-lipid-child     br-pten-lipid-1   ...__link-1-pten-phosphatase             supports  decisive    1         "Direct substrate conversion supports the enzymatic child claim."
```

#### Parent's literature side — `evidence` table sample (12 PMIDs)

```
─── evidence — PARENT (mh:PTEN-loss-AKT-glioma-proliferation) ──────
evidence_id        evidence_type  pmid       doi                              year  title                                                                                       organism  perturbation_type  perturbed_gene  readout                            cell_line       source                created_at
ev-pmid-9072974    publication    9072974    10.1126/science.275.5308.1943    1997  PTEN, a putative protein tyrosine phosphatase gene mutated in human brain, breast and… human     —                  PTEN            positional cloning                  patient_tissue  literature_mining     2026-04-29T09:48Z
ev-pmid-9853615    publication    9853615    10.1126/science.282.5396.1943    1998  PTEN/MMAC1/TEP1 dephosphorylates PIP3 and antagonises PI 3-kinase signalling           human     biochemical        PTEN            in-vitro lipid phosphatase          (cell-free)     literature_mining     2026-04-29T09:48Z
ev-pmid-12048243   publication    12048243   10.1038/nrg814                   2002  PTEN: a tumour suppressor with lipid- and protein-phosphatase activity                  multiple  review             PTEN            review                              n/a             literature_mining     2026-04-29T09:49Z
ev-pmid-18927578   publication    18927578   10.1158/0008-5472.CAN-08-1559    2008  Loss of PTEN function correlates with poor outcome in glioblastoma multiforme         human     observational      PTEN            survival outcome (TCGA)             patient_tissue  literature_mining     2026-04-29T09:49Z
ev-pmid-23945592   publication    23945592   10.1158/0008-5472.CAN-13-1100    2013  PI3K/AKT pathway activation drives proliferation in PTEN-null GBM xenografts          mouse     pharmacological    AKT1            xenograft growth                    U87, U251       literature_mining     2026-04-29T09:49Z
ev-pmid-27270579   publication    27270579   10.1158/2159-8290.CD-15-1352     2016  Genomic landscape and survival in glioblastoma — TCGA pan-glioma study                 human     observational      multiple        TCGA WES + clinical                  patient_tissue  literature_mining     2026-04-29T09:50Z
…  (6 more rows)
```

#### Parent's `publication_support` rollup

```
─── publication_support ────────────────────────────────────────────
claim_id                                  authority_level    authority_score  novelty               n_total_articles  n_direct_evidence  n_tier1_papers  n_with_perturbation  n_supporting  n_contradicting  publications
mh:PTEN-loss-AKT-glioma-proliferation     established        0.84             related_prior_art     12                10                 5               4                    11            1                ['9072974','9853615','12048243','18927578','23945592','27270579',…×12]
```

> 1 contradicting publication corresponds to a paper showing
> PTEN-low GBM cohorts where AKT activation does not predict
> proliferation - the same biological result can be interpreted
> as refuting this parent while remaining reusable elsewhere.

### 5.6 The two evidence buckets

- Parent `n_supporting_results = 5` counts attached `result_to_claim` interpretations for the parent.
- Leaf `n_supporting_results = 3` counts attached interpretations for the leaf.
- "Total evidence for the parent mechanism" = walk descendants via `claim_relations`, union each descendant's attached result interpretations (§6.2).

### 5.7 Multi-parent: one biological fact, many composite parents

"PTEN dephosphorylates PIP3" is context-free biology and reused as a `claim_dag_of` child for many composites (glioma, TNBC, melanoma...). One leaf, multiple parent DAG edges - no claim duplication and no evidence fragmentation:

```
   ┌──────────────────────────────────────────────────────────────┐
   │ COMPOSITE A — mh:PTEN-loss-AKT-glioma-proliferation           │
   │   context_set_json = {"cancer_type":"MONDO:GBM",              │
   │                        "cell_compartment":"tumor_intrinsic"}  │
   └──────────────┬───────────────────────────────────────────────┘
                  │ claim_dag_of
                  │ properties = {"step":1,
                  │               "step_role":"perturbation"}
                  ▼
              ┌────────────────────────────────────────────┐
              │ LEAF — …__link-1-pten-phosphatase           │
              │   relation_name     = 'dephosphorylates'    │
              │   relation_polarity = ''  (NOT_APPLICABLE)  │
              │   subject = HGNC:PTEN                       │
              │   object  = CHEBI:PIP3                      │
              │   context_set_json = '{}'  (the biology     │
              │     does not depend on cancer type)         │
              │   n_supporting_results = 3 (lipid-phosph    │
              │     assay + 31P-NMR + ClinVar variant set)  │
              └────────────────────────────────────────────┘
                  ▲
                  │ claim_dag_of
                  │ properties = {"step":1,
                  │               "step_role":"perturbation"}
   ┌──────────────┴───────────────────────────────────────────────┐
   │ COMPOSITE B — mh:PTEN-loss-AKT-TNBC-metastasis                │
   │   context_set_json = {"cancer_type":"MONDO:triple_negative_   │
   │                                      breast_carcinoma",       │
   │                        "outcome":"metastasis"}                │
   └──────────────────────────────────────────────────────────────┘
```

#### 5.7.1 The second composite — `mh:PTEN-loss-AKT-TNBC-metastasis`

```
─── claims row ─────────────────────────────────────────────────────
claim_id                = 'mh:PTEN-loss-AKT-TNBC-metastasis'
claim_type              = 'MechanismHypothesisClaim'
status                  = ''
human_readable          = 'PTEN loss drives PI3K/AKT-mediated metastasis in TNBC'
proof_level             = 5
p_value                 = NULL
q_value                 = NULL
confidence_interval     = NULL
n_studies               = 3
n_modalities            = 2
created_at              = '2026-04-29T11:02:14Z'
created_by              = 'gbd_agent'
description             = ''
superseded_by           = ''
full_data               = '{...}'
evidence_status         = 'observed'
prior_art_status        = 'related_prior_art'
review_status           = 'clean'
claim_text              = 'PTEN loss in triple-negative breast carcinoma derepresses PI3K/AKT signalling and promotes lung-tropic metastasis'
context_set_json        = '{"cancer_type":"MONDO:triple_negative_breast_carcinoma",
                            "outcome":"distant_metastasis",
                            "site_tropism":"lung",
                            "cell_compartment":"tumor_intrinsic"}'
edge_signature          = 'a204…'
context_operator        = 'AND'
relation_name           = 'drives_phenotype'
relation_polarity       = 'positive'
cell_states_json        = '[]'
last_wave_completed     = 2
confidence_summary      = 'weak'
narrative               = ''
narrative_updated_at    = ''
n_supporting_results    = 2
n_refuting_results      = 0
n_null_results          = 0
n_inconclusive          = 1
n_assays                = 2
n_datasets              = 2
n_supporting_pmids      = 7
polarity_consistency    = 1.0
decisive_coverage       = 0.67
proxy_coverage          = 0.0
participant_combinator  = ''
uct2                    = '{"coverage":{...},"dynamic_proof_dag":{...}}'
```

Its participants:

```
─── claim_participants — COMPOSITE B ───────────────────────────────
claim_id                                       entity_id            role               properties
mh:PTEN-loss-AKT-TNBC-metastasis               HGNC:PTEN            effector_gene      {"principal": true, "alteration":"loss"}
mh:PTEN-loss-AKT-TNBC-metastasis               MONDO:TNBC           outcome            {"principal": true}
mh:PTEN-loss-AKT-TNBC-metastasis               UBERON:lung          context_anatomy    {"principal": false}
mh:PTEN-loss-AKT-TNBC-metastasis               HGNC:AKT1            mediator           {"principal": false}
```

Its own cohort-level result interpretations, distinct from Composite A:

```
─── result_to_claim — COMPOSITE B ───────────────────────────────────
interpretation_id       result_id               claim_id                            stance        relevance   rationale_text
rtc-pten-tnbc-coxhr     br-pten-tnbc-coxhr      mh:PTEN-loss-AKT-TNBC-metastasis    supports      decisive    "METABRIC TNBC DMFS association matches the metastasis parent context."
rtc-pten-tnbc-ciber     br-pten-tnbc-cibersort  mh:PTEN-loss-AKT-TNBC-metastasis    inconclusive  proxy       "Macrophage infiltration is a proxy and does not decide the tumor-intrinsic claim."
rtc-pten-tnbc-ihc       br-pten-tnbc-ihc-mki67  mh:PTEN-loss-AKT-TNBC-metastasis    supports      supportive  "MKI67 supports proliferation but is one step removed from metastasis."
```

#### 5.7.2 The shared leaf carries TWO parent-scoped `claim_dag_of` edges

```
─── claim_relations ────────────────────────────────────────────────
relation_id          source_claim_id                                  target_claim_id                            relation_type  confidence  properties
rel_claim_dag_of_…   mh:PTEN-loss-…__link-1-pten-phosphatase         mh:PTEN-loss-AKT-glioma-proliferation      claim_dag_of   0.95        {"path_ids":["p1","p2"],
                                                                                                                                            "step_in_path":{"p1":1,"p2":1},
                                                                                                                                            "predecessor_claim_ids":[],
                                                                                                                                            "step_role":"perturbation",
                                                                                                                                            "is_canonical_backbone":true,
                                                                                                                                            "relation_context_set_json":{"cancer_type":"MONDO:GBM"}}
rel_claim_dag_of_…   mh:PTEN-loss-…__link-1-pten-phosphatase         mh:PTEN-loss-AKT-TNBC-metastasis           claim_dag_of   0.93        {"path_ids":["p1"],
                                                                                                                                            "step_in_path":{"p1":1},
                                                                                                                                            "predecessor_claim_ids":[],
                                                                                                                                            "step_role":"perturbation",
                                                                                                                                            "is_canonical_backbone":true,
                                                                                                                                            "relation_context_set_json":{"cancer_type":"MONDO:TNBC","outcome":"distant_metastasis"}}
```

- The same leaf is on the GBM parent's two-path DAG AND the TNBC parent's single-path DAG.
- `path_ids` are scoped per parent; `["p1","p2"]` for GBM and `["p1"]` for TNBC are independent namespaces.
- `kg.structural_parents(leaf_id)` returns both parents.
- Leaf's three result interpretations are shared for the leaf itself; no duplicate child claim is created.
- New evidence attached to the leaf flows into both parents' subtree rollups (§6.2).
- Leaf's `context_set_json = '{}'`; each parent edge carries the cancer-type relation context.

---

## 6. Edge access patterns

### 6.1 Direct evidence on a claim

```sql
-- Every interpreted result attached to one specific claim
SELECT
    br.*,
    rtc.stance,
    rtc.relevance,
    rtc.rationale_text,
    rtc.context_fit,
    ar.tool_id,
    ar.dataset_or_cohort,
    ar.artifact_uri
  FROM result_to_claim rtc
  JOIN biological_results br ON br.result_id = rtc.result_id
  LEFT JOIN analysis_runs ar ON ar.analysis_id = br.analysis_id
 WHERE rtc.claim_id = :cid
   AND rtc.attached = 1;
```

### 6.2 Subtree evidence — every result attached to any descendant

```sql
WITH RECURSIVE tree(claim_id, depth) AS (
    SELECT source_claim_id AS claim_id, 0
      FROM claim_relations
     WHERE target_claim_id = :composite_id
       AND relation_type IN ('claim_dag_of','chain_dag_of','context_split_of',
                             'mediator_specific_of','polarity_inverse_of',
                             'branches_from')
    UNION ALL
    SELECT cr.source_claim_id, t.depth + 1
      FROM claim_relations cr JOIN tree t ON cr.target_claim_id = t.claim_id
     WHERE cr.relation_type IN ('claim_dag_of','chain_dag_of','context_split_of',
                                'mediator_specific_of','polarity_inverse_of',
                                'branches_from')
       AND t.depth < 10
)
SELECT
    t.claim_id AS evidence_claim_id,
    br.*,
    rtc.stance,
    rtc.relevance,
    rtc.rationale_text,
    ar.dataset_or_cohort,
    ar.artifact_uri
  FROM tree t
  JOIN result_to_claim rtc ON rtc.claim_id = t.claim_id AND rtc.attached = 1
  JOIN biological_results br ON br.result_id = rtc.result_id
  LEFT JOIN analysis_runs ar ON ar.analysis_id = br.analysis_id;
```

### 6.3 Promotion — leaf becomes a `backbone_edges` row

On graduation (`evidence_status='externally_supported'`, no open `contradicts`), a leaf maps directly to a backbone edge:

```
LEAF claim:                                  backbone_edges row:
  participants[role=subject].entity_id  ─→     source_id
  participants[role=object].entity_id   ─→     target_id
  relation_name + relation_polarity     ─→     relation_name + relation_polarity
  edge_signature                        ─→     edge_id
```

Lock: exactly one SUBJECT + one OBJECT principal participant per leaf — the leaf-edge invariant.

---

## 7. Implementation plan

This is the plan to make the code and database match the final claim
object above while staying compatible with the dynamic DAG system.
In this repository, the first concrete targets are
`schema/table_schemas.sql`, `schema/schema.py`, and the ingest writers
under `ingest/`. The proof-search runtime changes belong in the dynamic
planner/UCT code that reads and writes this KG.

### 7.1 Schema migration

1. Add an `analysis_runs` table:
   - `analysis_id` primary key.
   - tool/provider metadata: `tool_id`, `provider`, `analysis_type`.
   - data scope: dataset ids, cohort ids, sample filters, context JSON.
   - reproducibility: params JSON, `params_hash`, code version, run command,
     artifact URIs, status, timestamps, agent/run id.
2. Move claim ownership out of `biological_results`:
   - add `analysis_id`.
   - keep result-level fields: assay, outcome, effect direction/size,
     confidence interval, p/q values, n, statistics JSON, context JSON.
   - deprecate `biological_results.claim_id`; keep it only as a nullable
     legacy/backfill field during migration.
3. Expand `result_to_claim` into the authoritative interpretation table:
   - `interpretation_id`, `result_id`, `claim_id`.
   - `stance`: `supports`, `refutes`, `null`, `inconclusive`,
     `contextual`, `misleading`.
   - `relevance`: `decisive`, `supportive`, `proxy`, `irrelevant`.
   - `rationale_text`, `context_fit`, `polarity_alignment`,
     `proof_node_id`, `attached`, audit fields.
4. Update `support_sets` so result-based support sets reference
   interpretation ids, not raw result ids. Literature-only support sets
   can continue to reference publication evidence ids.
5. Add relation context support to `claim_relations`:
   - either add `properties` JSON if missing in the live schema, or migrate
     existing relation metadata into that column.
   - emit `claim_dag_of` for new DAG edges while accepting legacy
     `chain_dag_of`.
   - require structural DAG edges to include path metadata and, when
     relevant, `relation_context_set_json`.

### 7.2 Claim object and participant model

1. Update claim serialization/deserialization so content is understood as
   `claim_text + relation_name + relation_polarity + participants +
   context`.
2. Make participant roles explicit and validated:
   - principal subject-side anchor.
   - principal object/outcome-side anchor.
   - mediator/mechanism participants.
   - context participants.
3. Add invariant checks:
   - binary backbone-promotable claims must have exactly one principal
     subject-side and one principal object-side participant.
   - n-ary claims must declare role groups and participant combinator
     semantics.
   - mechanisms that are load-bearing causal steps should be child claims,
     not unstructured participant decorations.
4. Update `edge_signature` generation to use principal anchors,
   `relation_name`, normalized context, and the documented polarity policy.

### 7.3 Claim DAG creation

1. Add a claim-initialization hook after parent claim creation.
2. Feed the parsed parent claim into the dynamic claim-DAG planner.
3. Create proposed child claims as normal `claims` rows with participants,
   relation, polarity, and intrinsic context.
4. Create `claim_relations` structural edges from child to parent:
   - `relation_type = claim_dag_of` or a more specific structural type.
   - path ids, step index, predecessor ids, step role.
   - relation-scoped context and rationale.
5. Enforce acyclicity and allow multi-parent child claims.
6. Backfill existing `chain_dag_of` rows to `claim_dag_of` or support both
   behind one helper API.

### 7.4 UCT1, UCT2, and dynamic planner compatibility

1. Treat the claim DAG as the inter-claim search graph.
2. Keep UCT1/RunState responsible for choosing which claim, subtree, or
   unresolved DAG branch gets the next wave.
3. Keep UCT2 responsible for proof search inside one focal claim:
   `EvidenceCoverageMatrix`, `DynamicProofDAG`, proof nodes, evidence gaps,
   and visit/value counts.
4. When a new child claim is added to a parent DAG, initialize UCT2 for the
   child and update the parent's UCT2 proof nodes so the new mechanism path
   can be selected.
5. Make planner prompts include:
   - parent claim content and participants.
   - parent context.
   - existing child DAG paths.
   - relation-scoped context requirements for proposed children.
   - reusable analysis/results already available through
     `result_to_claim`.

### 7.5 Backfill

1. Create `analysis_runs` rows for existing result-producing work by
   grouping legacy `biological_results` on provider, assay, dataset,
   parameters, artifacts, and agent run.
2. For every legacy `biological_results.claim_id`, create a
   `result_to_claim` interpretation with a conservative rationale:
   `"Migrated legacy claim-owned result; rationale requires review."`
3. Preserve legacy rollups, then recompute them from `result_to_claim`.
4. Convert existing relation metadata into `claim_relations.properties`.
5. Rename new structural writes to `claim_dag_of`; keep legacy reads for
   `chain_dag_of` until all historical rows are migrated.

### 7.6 Tests and acceptance criteria

1. Schema tests:
   - one `analysis_run` can produce many `biological_results`.
   - one `biological_result` can attach to many claims with different
     `stance` and `rationale_text`.
   - claim rollups count interpretations, not raw result rows.
2. DAG tests:
   - child claim can support multiple parents with different
     `relation_context_set_json`.
   - cycles are rejected.
   - `claim_dag_of` and legacy `chain_dag_of` reads return the same
     structural descendants during migration.
3. UCT tests:
   - parent creation initializes a dynamic claim DAG.
   - child creation initializes UCT2.
   - adding a new child updates parent proof search without losing existing
     UCT2 state.
4. Query tests:
   - direct evidence query returns rationale and analysis artifact metadata.
   - subtree evidence query returns descendant interpretations, not
     duplicate raw result rows.
