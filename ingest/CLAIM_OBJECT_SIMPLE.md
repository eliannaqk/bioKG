# Claim Object, Simple Version

## Stores

| Store | Job | Boolean rollup? |
|---|---|---|
| `claims` | Durable biological assertions. | No |
| `claim_relations` | Semantic relations: `same_as`, `refines`, `contradicts`, `enables`, `corroborates`. | No |
| `claim_decomposition_edges` | Proof/decomposition DAG edges consumed by the agent. | Yes |

`claim_type` is not core claim identity. If present during migration, treat it
as legacy or derived metadata.

Evidence path:

```text
analysis_runs -> biological_results -> result_to_claim -> claims
```

## Claim Row Key

| Field | Meaning |
|---|---|
| `claim_id` | Stable id. |
| `claim_text` | Free-text assertion. |
| `participants` | Free-text and/or entity ids for subject, object, context, phenotype. |
| `relation_name` | Predicate, e.g. `contributes_to`, `derepresses`, `associates_with`. |
| `relation_polarity` | `positive`, `negative`, `null_hypothesis`, or `unknown`. |
| `context_set_json` | Where the assertion holds. |
| `evidence_status` | `unchecked`, `evidenced`, `refuted`, `inconclusive`. |
| `prior_art_status` | `new`, `literature_supported`, `literature_refuted`. |
| `review_status` | `draft`, `under_review`, `accepted`, `retired`. |
| `confidence_summary` / `rollups` | Materialized evidence rollup. |
| `edge_signature` | Canonical dedup hash. |
| `full_data` | Extra structured JSON; not proof role. |

## Tiny Example

Parent:

```text
P_SETDB1_ICB_RESISTANCE:
SETDB1 amplification/overactivity contributes to immune-checkpoint-blockade
resistance by suppressing tumor-intrinsic immunogenicity.
```

### Claims

| ID | claim_text | participants | relation_name | relation_polarity | context/properties |
|---|---|---|---|---|---|
| `P_SETDB1_ICB_RESISTANCE` | SETDB1 amplification/overactivity contributes to immune-checkpoint-blockade resistance by suppressing tumor-intrinsic immunogenicity. | SETDB1 amplification/overactivity; tumor-intrinsic immunogenicity; immune-checkpoint-blockade resistance | `contributes_to` | `positive` | therapy=ICB; cell_type=tumor_cell |
| `F_SETDB1_H3K9ME3_TE_IMMUNE_DOMAINS` | SETDB1-dependent H3K9me3 domains are enriched for transposable elements and immune-related gene clusters. | SETDB1-dependent H3K9me3 domains; transposable elements; immune-related gene clusters; tumor cell | `is_enriched_for` | `positive` | shared anchor |
| `F_SETDB1_LOSS_DEREPRESSES_TE_REGULATORY_ELEMENTS` | SETDB1 loss derepresses latent TE-derived regulatory elements. | SETDB1 loss; latent TE-derived regulatory elements; tumor cell | `derepresses` | `positive` | perturbation=SETDB1_loss |
| `F_TE_REGULATORY_ELEMENTS_INCREASE_IMMUNE_GENES` | Derepressed TE-derived regulatory elements increase immunostimulatory gene expression. | TE-derived regulatory elements; immunostimulatory genes; tumor cell | `increases` | `positive` | tumor_intrinsic=true |
| `F_SETDB1_ASSOCIATES_WITH_ICB_RESISTANCE` | SETDB1 amplification or overactivity associates with immune exclusion or ICB resistance. | SETDB1 amplification/overactivity; immune exclusion; ICB resistance | `associates_with` | `positive` | human context |

### Decomposition Edges

| source_claim_id | target_claim_id | support_operator | source_role | target_role | group_id |
|---|---|---|---|---|---|
| `F_SETDB1_H3K9ME3_TE_IMMUNE_DOMAINS` | `P_SETDB1_ICB_RESISTANCE` | `ALL_OF` | `shared_anchor` | `parent_claim` | `setdb1_simple` |
| `F_SETDB1_LOSS_DEREPRESSES_TE_REGULATORY_ELEMENTS` | `P_SETDB1_ICB_RESISTANCE` | `ALL_OF` | `required_step` | `parent_claim` | `setdb1_simple` |
| `F_TE_REGULATORY_ELEMENTS_INCREASE_IMMUNE_GENES` | `P_SETDB1_ICB_RESISTANCE` | `ALL_OF` | `required_step` | `parent_claim` | `setdb1_simple` |
| `F_SETDB1_ASSOCIATES_WITH_ICB_RESISTANCE` | `P_SETDB1_ICB_RESISTANCE` | `ALL_OF` | `context_bridge` | `parent_claim` | `setdb1_simple` |

### Semantic Claim Relations

| source_claim_id | target_claim_id | relation_kind | notes |
|---|---|---|---|
| `F_SETDB1_LOSS_DEREPRESSES_TE_REGULATORY_ELEMENTS` | `F_TE_REGULATORY_ELEMENTS_INCREASE_IMMUNE_GENES` | `enables` | Temporal/mechanistic order only. |

### DAG

```mermaid
flowchart TD
  F1["F_SETDB1_H3K9ME3_TE_IMMUNE_DOMAINS"]
  F2["F_SETDB1_LOSS_DEREPRESSES_TE_REGULATORY_ELEMENTS"]
  F3["F_TE_REGULATORY_ELEMENTS_INCREASE_IMMUNE_GENES"]
  F4["F_SETDB1_ASSOCIATES_WITH_ICB_RESISTANCE"]
  P["P_SETDB1_ICB_RESISTANCE"]

  F1 -- "decomposition: ALL_OF" --> P
  F2 -- "decomposition: ALL_OF" --> P
  F3 -- "decomposition: ALL_OF" --> P
  F4 -- "decomposition: ALL_OF" --> P

  F2 -. "claim_relations: enables" .-> F3
```

Readout:

```text
P_SETDB1_ICB_RESISTANCE is satisfied only if all four active child claims are
supported.
The dotted enables edges do not count toward rollup.
```

## Query Shapes

Active proof children:

```sql
SELECT source_claim_id, target_claim_id, support_operator, source_role, group_id
FROM claim_decomposition_edges
WHERE target_claim_id = '<parent_claim_id>'
  AND edge_status = 'active';
```

Semantic relations:

```sql
SELECT source_claim_id, target_claim_id, relation_kind, relation_status, notes
FROM claim_relations
WHERE source_claim_id = '<claim_id>'
   OR target_claim_id = '<claim_id>';
```

Evidence for a claim:

```sql
SELECT claim_id, result_id, stance, rationale_text
FROM result_to_claim
WHERE claim_id = '<claim_id>'
  AND attached = 1;
```
