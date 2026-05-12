# Claim Decomposition DAG Architecture

## Target Model

| Table | Job | Used by proof rollup? |
|---|---|---|
| `claims` | Durable biological assertions. | No |
| `claim_relations` | Semantic relations between claims. | No |
| `claim_decomposition_edges` | Agent-consumed proof/decomposition DAG. | Yes |

Removed from core reasoning:

```text
claim_type
```

If `claim_type` exists during migration, it is legacy/derived metadata only.
The agent reasons from claim content, context, evidence state, and
decomposition edges.

## `claims`

A claim is an assertion. It does not know whether it is a parent, module,
anchor, or leaf in any particular DAG.

| Field | Meaning |
|---|---|
| `claim_id` | Stable id. |
| `claim_text` | Full assertion text. |
| `participants` | `claim_participants` rows. Every participant is a KG node id from `entities`. |
| `relation_name` | Canonical predicate, e.g. `drives_phenotype`, `regulates_activity`, `binds`. |
| `relation_polarity` | `positive`, `negative`, `bidirectional`, `null`, `unknown`, or SQL `NULL` when the predicate has no sign. |
| `context_set_json` | Where/when the claim holds. |
| `cell_states_json` | Cell-state qualifiers. |
| `context_operator` | How context predicates compose. |
| `participant_combinator` | How participant sets compose. |
| `evidence_status` | `unchecked`, `evidenced`, `refuted`, `inconclusive`. |
| `prior_art_status` | `new`, `literature_supported`, `literature_refuted`. |
| `review_status` | `draft`, `under_review`, `accepted`, `retired`. |
| `confidence_summary` | Evidence summary for this exact claim. |
| `rollups` | Materialized counts/scores. |
| `edge_signature` | Canonical dedup hash. |
| `full_data` | Extra structured JSON, not DAG role. |

## `claim_relations`

Semantic relations. These do not contribute to Boolean proof rollup.

| Field | Meaning |
|---|---|
| `relation_id` | Stable relation id. |
| `source_claim_id` | Source claim. |
| `target_claim_id` | Target claim. |
| `relation_kind` | Relation label. |
| `relation_strength` | Optional confidence/weight. |
| `relation_status` | `proposed`, `active`, `retired`. |
| `notes` | Rationale. |

Recommended `relation_kind` values:

| relation_kind | Meaning |
|---|---|
| `same_as` | Same assertion. |
| `refines` | Source is a finer/corrected version of target. |
| `contradicts` | Claims conflict. |
| `corroborates` | Convergent support, not load-bearing proof composition. |
| `enables` | Temporal/mechanistic ordering. |
| `parallel_to` | Related alternative. |

## `claim_decomposition_edges`

Proof DAG edges. Stored direction is child-to-target:

```text
source_claim_id -> target_claim_id
child/module    -> parent/module being satisfied
```

| Field | Meaning |
|---|---|
| `edge_id` | Stable edge id. |
| `source_claim_id` | Child claim or child module. |
| `target_claim_id` | Parent claim or mechanism module. |
| `support_operator` | Local Boolean operator at the target. |
| `support_operator_params` | JSON params, e.g. `{"min_required": 3}`. |
| `source_role` | How source is used in this target's DAG. |
| `target_role` | How target is used in this DAG. |
| `group_id` | Mechanism/pathway grouping. |
| `edge_status` | `proposed`, `active`, `retired`. |
| `created_at` / `retired_at` | Lifecycle timestamps. |
| `notes` | Rationale. |

Recommended values:

| Field | Values |
|---|---|
| `support_operator` | `ALL_OF`, `ANY_OF`, `K_OF_N`, `INDEPENDENT_CAUSES`, `MUTUALLY_EXCLUSIVE_ALTERNATIVES` |
| `source_role` | `shared_anchor`, `required_step`, `sufficient_module`, `context_bridge`, `ordinary_child` |
| `target_role` | `parent_claim`, `mechanism_module` |

## Invariants

No mixed operators at one active target:

```text
all active edges with the same target_claim_id must have one support_operator
```

Mixed logic must be reified:

```text
bad:  P = (A AND B) OR (C AND D)
good: M_AB = A AND B
      M_CD = C AND D
      P = M_AB OR M_CD
```

Roles live on edges:

```text
F_SETDB1_H3K9ME3 can be shared_anchor in one DAG
and ordinary_child in another DAG.
```

Module/leaf status is DAG-local:

```text
active incoming decomposition children -> acts as module
no active incoming decomposition children -> acts as leaf
```

Participant invariant:

```text
claim_participants.entity_id must resolve to entities.entity_id.
Do not store prose phrases as participants.
Use participant properties for alteration/dose/state qualifiers.
Use context_set_json for scope when no biological node is needed.
```

`enables` remains a semantic relation:

```text
F_A enables F_B
```

It is useful ordering information, not proof rollup.

## Operators

| Operator | Target semantics | Example |
|---|---|---|
| `ALL_OF` | All active children required. | Statin LDL chain. |
| `ANY_OF` | Any one active child sufficient. | GPX4 or FSP1 suppresses ferroptosis. |
| `K_OF_N` | At least `min_required` children required. | Senescence markers. |
| `INDEPENDENT_CAUSES` | One cause can support target; multiple may be true. | Diabetes etiology. |
| `MUTUALLY_EXCLUSIVE_ALTERNATIVES` | Exactly one should win per context. | T helper fate. |

## Target DDL

```sql
CREATE TABLE claims (
  claim_id TEXT PRIMARY KEY,
  claim_text TEXT NOT NULL,
  relation_name TEXT NOT NULL,
  relation_polarity TEXT DEFAULT NULL,
  context_set_json TEXT DEFAULT '{}',
  cell_states_json TEXT DEFAULT '[]',
  context_operator TEXT DEFAULT 'AND',
  participant_combinator TEXT DEFAULT '',
  evidence_status TEXT DEFAULT 'unchecked',
  prior_art_status TEXT DEFAULT 'new',
  review_status TEXT DEFAULT 'draft',
  confidence_summary TEXT DEFAULT '{}',
  rollups TEXT DEFAULT '{}',
  edge_signature TEXT DEFAULT '',
  full_data TEXT DEFAULT '{}'
);

CREATE TABLE claim_participants (
  claim_id TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  role TEXT NOT NULL,
  properties TEXT DEFAULT '{}',
  FOREIGN KEY (claim_id) REFERENCES claims(claim_id),
  FOREIGN KEY (entity_id) REFERENCES entities(entity_id)
);

CREATE TABLE claim_relations (
  relation_id TEXT PRIMARY KEY,
  source_claim_id TEXT NOT NULL,
  target_claim_id TEXT NOT NULL,
  relation_kind TEXT NOT NULL,
  relation_strength REAL DEFAULT NULL,
  relation_status TEXT DEFAULT 'proposed',
  notes TEXT DEFAULT '',
  created_at TEXT DEFAULT '',
  retired_at TEXT DEFAULT ''
);

CREATE TABLE claim_decomposition_edges (
  edge_id TEXT PRIMARY KEY,
  source_claim_id TEXT NOT NULL,
  target_claim_id TEXT NOT NULL,
  support_operator TEXT NOT NULL,
  support_operator_params TEXT DEFAULT '{}',
  source_role TEXT DEFAULT 'ordinary_child',
  target_role TEXT DEFAULT 'parent_claim',
  group_id TEXT DEFAULT '',
  edge_status TEXT DEFAULT 'proposed',
  created_at TEXT DEFAULT '',
  retired_at TEXT DEFAULT '',
  notes TEXT DEFAULT ''
);

CREATE INDEX idx_claim_relations_source ON claim_relations(source_claim_id);
CREATE INDEX idx_claim_relations_target ON claim_relations(target_claim_id);
CREATE INDEX idx_claim_relations_kind ON claim_relations(relation_kind);
CREATE INDEX idx_claim_participants_claim ON claim_participants(claim_id);
CREATE INDEX idx_claim_participants_entity ON claim_participants(entity_id);

CREATE INDEX idx_claim_decomp_source ON claim_decomposition_edges(source_claim_id);
CREATE INDEX idx_claim_decomp_target ON claim_decomposition_edges(target_claim_id);
CREATE INDEX idx_claim_decomp_status ON claim_decomposition_edges(edge_status);
```

Writer code and migration tests enforce the no-mixed-operators invariant.

## Agent Actions

Structural:

| Action | Effect |
|---|---|
| `propose_decomposition(parent, children, operator)` | Draft decomposition edges. |
| `instantiate_claim(claim_object)` | Create a claim with `evidence_status = unchecked`. |
| `add_decomposition_edge(child, parent, role, operator, group)` | Wire the proof DAG. |
| `mark_edge(edge, status)` | Move `proposed` / `active` / `retired`. |
| `refine_claim(coarse, finer)` | Add finer claims plus `claim_relations.refines`. |

Evidence:

| Action | Effect |
|---|---|
| `gather_evidence(claim)` | Fetch evidence chunks. |
| `interpret_evidence(claim, evidence)` | Decide support/refute/null/inconclusive. |
| `attach_evidence(claim, evidence_id)` | Persist interpretation. |
| `update_confidence(claim, summary)` | Update `confidence_summary`. |

Traversal:

| Action | Effect |
|---|---|
| `select_frontier(parent)` | Pick next unresolved child. |
| `descend(claim)` | Focus child. |
| `ascend(claim)` | Focus parent. |
| `revisit_anchor(claim)` | Reuse cached shared-anchor confidence. |
| `rollup_parent(parent)` | Recompute parent from active children. |

UCT2 state is scoped to:

```text
(focal_claim, target_claim, action_path_hash)
```

Share interpreted evidence and claim confidence across focal claims. Do not
share visit counts.

## Operator-Aware Frontier Policy

| Operator | Frontier preference |
|---|---|
| `ALL_OF` | Test high-risk child first; one refuted child can kill target. |
| `ANY_OF` | Test most likely supported child first; one supported child can satisfy target. |
| `K_OF_N` | Stop after `min_required` supported children. |
| `MUTUALLY_EXCLUSIVE_ALTERNATIVES` | Prefer discriminating evidence. |
| `INDEPENDENT_CAUSES` | Prefer cause most plausible in current context. |

## Migration Plan

1. Add `claim_decomposition_edges`.
2. Dual-write old structural `claim_relations.relation_type = claim_dag_of`
   into `claim_decomposition_edges`.
3. Move frontier selection, parent rollup, and UCT2 traversal to
   `claim_decomposition_edges`.
4. Stop writing structural proof edges into `claim_relations`.
5. Keep `claim_relations` for semantic relations only.
6. Demote `claim_type`: nullable or move to `full_data.legacy_claim_type`.
7. Backfill old structural rows.
8. Run invariants.

Mapping from old structural relation rows:

| Old | New |
|---|---|
| `claim_relations.source_claim_id` | `claim_decomposition_edges.source_claim_id` |
| `claim_relations.target_claim_id` | `claim_decomposition_edges.target_claim_id` |
| `properties.parent_support_operator` | `support_operator` |
| `properties.min_required` | `support_operator_params.min_required` |
| `properties.claim_dag_node_kind` / `node_kind` | `source_role` / `target_role` |
| `properties.dag_edge_status` | `edge_status` |
| `properties.support_group_id` / `path_ids` | `group_id` |

Invariant checks:

```sql
SELECT target_claim_id, COUNT(DISTINCT support_operator) AS n_ops
FROM claim_decomposition_edges
WHERE edge_status = 'active'
GROUP BY target_claim_id
HAVING COUNT(DISTINCT support_operator) > 1;
```

Cycle checks should run in migration tooling with a recursive CTE or graph
library.
