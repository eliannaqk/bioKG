# Claim Architecture

The Claim object is the central unit of the GBD knowledge graph.
This document is a schema reference for the post-Phase-T production
layout (2026-04-29): what a claim is, what's persisted where, how
parent-child relationships are encoded as edges, how a leaf becomes
a canonical-biology edge on graduation, and where the direct vs.
subtree evidence physically lives.

The plan that produced this shape is in
`REMOVE_CLAIM_DIRECTION_FIELD_PLAN.md`.

---

## 1. What a claim is

A **claim** is an assertion about biology that is *contextual* (true
in some scope and not others), *typed* (carries a relation predicate,
not a free-text verb), and *graduating* (moves through an evidence
ladder from `draft` to `externally_supported` based on what gets
attached to it).

Two shapes exist:

```
LEAF            One typed edge between two entities.
                Subject —[relation_name, polarity]→ Object  (in some context)
                Has its own evidence.
                Promotable to backbone_edges on graduation.

COMPOSITE       Higher-level assertion ("X drives phenotype Y in
                cohort Z"). Decomposes into chain_link / branch /
                context-split children. Has its own cohort/scRNA
                evidence AND derives belief from its leaves.
```

The **leaf-edge invariant** (§38 of the plan): every leaf claim has
exactly one principal `SUBJECT` participant and exactly one principal
`OBJECT` participant. That makes a leaf isomorphic to a typed edge —
which is why "claims are edges, never claims" is enforceable and why
graduated leaves can promote into the canonical `backbone_edges`
table without re-encoding.

---

## 2. Where the claim's data lives

A claim's persistence is split across **eight tables** in the SQLite
KG. Each table holds one axis; nothing is duplicated.

```
                       ┌───────────────────────────────────┐
                       │              CLAIMS               │
                       │  (56 columns, 881 660 rows)       │
                       │                                   │
                       │  WHAT the claim says:             │
                       │    claim_text, relation_name,     │
                       │    relation_polarity              │
                       │  HOW MATURE the evidence is:      │
                       │    evidence_status, proof_level,  │
                       │    n_studies, n_modalities,       │
                       │    direction_consistency,         │
                       │    confidence_summary  (§47)      │
                       │  CONTEXT scope:                   │
                       │    context_set_json,              │
                       │    cell_states_json               │
                       │  IDENTITY + AUDIT (minimal):      │
                       │    edge_signature  (dedup hash)   │
                       │    created_at, created_by         │
                       │  NARRATIVE (Part VIII):           │
                       │    narrative,                     │
                       │    narrative_updated_at           │
                       └─────────────────┬─────────────────┘
                                         │
            ┌────────────────────────────┼────────────────────────────┐
            │                            │                            │
            ▼                            ▼                            ▼
   ┌────────────────┐         ┌──────────────────────┐    ┌──────────────────────┐
   │ claim_         │         │ biological_results    │    │ claim_relations      │
   │ participants   │         │ (per-tool result)     │    │ (claim ↔ claim edges)│
   │                │         │                       │    │                      │
   │ entity_id, role│         │ result_id, claim_id,  │    │ source_claim_id,     │
   │ properties JSON│         │ assay, outcome,       │    │ target_claim_id,     │
   │                │         │ effect_size, p_value, │    │ relation_type,       │
   │ Resolved via   │         │ statistical_test_     │    │ rationale, confidence│
   │ entity_aliases │         │ performed             │    │ properties JSON      │
   │                │         │                       │    │                      │
   │ Roles:         │         │ Gated by              │    │ See §4 for the 9     │
   │   SUBJECT,     │         │ result_to_claim       │    │ relation_type values │
   │   OBJECT,      │         │ (attached=1 to count) │    │                      │
   │   CONTEXT_*    │         │                       │    │                      │
   └────────────────┘         └──────────────────────┘    └──────────────────────┘

   ┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
   │ support_sets         │    │ publication_support  │    │ claim_events         │
   │ (AND-grouped         │    │ (per-claim lit       │    │ (append-only audit   │
   │  evidence bundles)   │    │  rollup)             │    │  trail)              │
   │                      │    │                      │    │                      │
   │ stance: supports /   │    │ authority_level,     │    │ axis, old_value,     │
   │   contradicts /      │    │ n_supporting,        │    │ new_value, reason,   │
   │   refines            │    │ n_contradicting,     │    │ actor, wave,         │
   │ logic = AND          │    │ pmids                │    │ timestamp            │
   │ confidence (0-1)     │    │                      │    │                      │
   └──────────────────────┘    └──────────────────────┘    └──────────────────────┘
```

The `claims` row holds **content + status + minimal audit**.
Everything else hangs off it through one of the satellites:

- **claim_participants** — who/what is involved (entity-graph
  linkage). Replaces the legacy `candidate_gene` column.
- **biological_results** — direct evidence rows, one per tool
  invocation. Joined back to claims by `claim_id`, gated by
  `result_to_claim`. **Provenance of HOW the evidence was produced
  lives here**: `assay`, `provider`, `source_dataset`,
  `source_release`, `model_name`, `model_version`, `artifact_id`.
  Not on the claim row.
- **claim_relations** — every relationship between two claims,
  including the structural-parent edge (Phase T).
- **support_sets** — AND-grouped evidence bundles. Carries
  publication / curated-source provenance for the bundle.
- **publication_support** — literature rollup per claim.
- **claim_events** — append-only audit trail. Every state
  transition (review status, evidence status, narrative
  regeneration, graduation) writes one row with actor + reason +
  timestamp. **This is where "who changed this and why" lives** —
  not on the claim row.

### 2.0.1 What's NOT useful on the claim row

A handful of column groups currently persist on `claims` but are
either redundant with satellite tables or used only at one
transient point in the pipeline. They're slated for retirement
under future plan parts:

- **DAG-1 ranking scores** (`tractability_score`,
  `kg_connectivity_score`, `priority_score`) — computed once during
  candidate selection, never re-read once the claim enters DAG-2.
  Belong on a `dag1_candidates` log table, not the persisted
  claim. Phase T did NOT retire these; the columns still exist on
  the row but are dead weight for any post-DAG-1 reader.
- **Per-row provenance scalars** (`source`, `source_dataset`,
  `source_release`, `assay_type`, `model_name`, `model_version`,
  `artifact_id`) — these describe HOW the claim came to be, which
  is a property of the evidence that built it, not the assertion
  itself. The same claim ("RBMS1 destabilises CXCL9 mRNA") can be
  supported by evidence from CPTAC + DepMap + a perturbation screen,
  each with its own dataset version. Putting one set of source
  attributes on the claim row picks an arbitrary winner. The
  satellite shape — provenance per evidence row in
  `biological_results`, per support bundle in `support_sets`, per
  state transition in `claim_events` — is more honest. The flat
  scalars on the row should be retired alongside Part IV's flat
  statistics.

The minimal audit kept on the row (`created_at`, `created_by`,
`edge_signature`) is structurally load-bearing:
- `edge_signature` is the cross-source dedup hash; it has to be on
  the row to support the WHERE-clause in reconciliation.
- `created_at` / `created_by` answer "when did this assertion first
  enter the KG?", which `claim_events` doesn't because it only
  records *state transitions*, not the initial insert.

### 2.1 Population numbers in production

```
claims              881 660 rows  (56 columns)
backbone_edges    5 557 464 rows  (relation_name + relation_polarity populated)
entities            137 705 rows  (canonical, resolvable via entity_aliases)
claim_participants    ~1.7 M rows
biological_results    3 257 rows  (sparse — only attached to active claims)
claim_relations         158 rows  (95 are structural-parent edges)
```

ConfidenceSummary distribution: `ESTABLISHED` 24 005 / `STRONG` 75 131
/ `MODERATE` 1 906 / `WEAK` 780 515 / `UNKNOWN` 103.

---

## 3. The categorical confidence ordinal (§47)

Every claim row carries a single 5-level `confidence_summary` derived
purely from already-populated fields:

```python
def confidence_summary(claim) -> ConfidenceSummary:
    es = (claim.evidence_status or "draft").lower()
    pa = (claim.prior_art_status or "unsearched").lower()
    rs = (claim.review_status or "clean").lower()
    pl = int(claim.proof_level or 2)
    n_studies, n_modalities = int(claim.n_studies or 0), int(claim.n_modalities or 0)

    # Hard knockouts
    if rs == "contradicted":         return WEAK
    if rs == "superseded":           return UNKNOWN

    # ESTABLISHED — published / canonical / orthogonally reproduced
    if es == "externally_supported": return ESTABLISHED
    if pa == "canonical":            return ESTABLISHED
    if pl >= 7:                      return ESTABLISHED
    if pl >= 6 and n_modalities>=2:  return ESTABLISHED

    # STRONG — causal mechanism + replication
    if es in ("causal","mechanistic"):       return STRONG
    if pl >= 5 and n_modalities>=2:          return STRONG
    if pl >= 5 and n_studies>=3:             return STRONG

    # MODERATE — observed across modalities OR replicated
    if es == "replicated":                   return MODERATE
    if es == "observed" and n_studies>=2:    return MODERATE
    if pl == 5 and n_modalities>=1:          return MODERATE
    if pl == 4:                              return MODERATE

    # WEAK / UNKNOWN
    if es == "observed" and n_studies==1:    return WEAK
    if pl == 3:                              return WEAK
    if n_studies >= 1:                       return WEAK
    return UNKNOWN
```

**No posterior, no Bayesian numbers.** Calibrating a posterior across
heterogeneous biological evidence (CRISPR + scRNA + IHC + cohort
survival) is hard and surfacing an uncalibrated number gives readers
false precision. The categorical ordinal is the source of truth;
it's auto-recomputed on every write that touches its inputs and
indexed via `idx_claims_confidence` for queries like "all MODERATE
claims with ≥1 contradiction".

---

## 4. Parent–child via `claim_relations` (Phase T)

Before Phase T, each claim row carried 8 lineage columns:
`parent_claim_id`, `refinement_type`, `refinement_rationale`,
`refinement_confidence`, `splits_on_dimension`,
`target_mechanism_ids`, `inherited_evidence_ids`, `is_general`. That
worked but mixed structure into content; the row no longer tells you
"what this claim says" without filtering.

Post Phase T, all eight fields live on `claim_relations` rows. The
`claims` row is **content only**. Lineage is **typed edges**.

### 4.1 The relation_type vocabulary (9 values)

```
STRUCTURAL-PARENT EDGES (every non-root claim has exactly one
                          inbound edge of one of these types):

  branches_from         — mechanism alternative
                          ("MH-1 is one way the parent could be true")
  chain_link_of         — step within a composite
                          ("link 2 of 4 in the parent's causal chain")
  context_split_of      — per-context decomposition
                          ("the melanoma slice of the pan-cancer claim")
  mediator_specific_of  — alt-mechanism for one chain link
                          ("RC3H1 instead of RBMS1 at link 2-2")
  polarity_inverse_of   — auto-disproof inverse claim
                          ("the negative-polarity sibling created when the
                           original was refuted")

NON-STRUCTURAL EDGES (claim can have many, in any direction):

  refines               — supersession ("this newer claim replaces that one")
  competes_with         — mutual-exclusion ("alt-mechanism, both being investigated")
  contradicts           — open polarity / refutation conflict
  corroborates          — extra support without supersession
  enables               — PTM event → consequence linkage
                          (Part VII §37.3 — phosphorylation_event enables
                           regulates_activity downstream)
```

### 4.2 The `properties` JSON blob

Each edge carries a typed metadata payload per §51:

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
 "alt_for_link_id": "rbms1...__link-2-2"}

# polarity_inverse_of
{"auto_created_at": "2026-04-28T...",
 "trigger_posterior": 0.12,
 "inherited_evidence_ids": [...]}
```

The same metadata that used to spread across 8 row columns now lives
on the edge that means it.

### 4.3 The `validate_lineage` CI gate

`gbd.knowledge_graph.lineage_phase_t.validate_lineage(conn, claim_id)`
runs after every `add_claim_relation` call and rejects:

- **Multiple inbound structural-parent edges to *different* parents**
  — a claim has one parent. Multiple structural edges to the *same*
  parent are fine and additive (e.g. `branches_from` +
  `mediator_specific_of` to the same parent stack as metadata
  richness — the more-specific type wins for parent resolution).
- **Cycles** in the structural-parent chain — walking parent →
  parent's parent → … must terminate (depth-bounded at 32).

A failed gate rolls the just-written edge back so the table never
holds a corrupt state.

### 4.4 Read helpers

`KnowledgeGraph` exposes four lineage methods:

```python
kg.structural_parent(claim_id)        # str | None — direct parent ID
kg.structural_parent_edge(claim_id)   # dict | None — full edge row
kg.lineage_property(claim_id, key)    # any — read one key from
                                      #       edge.properties JSON
kg.is_general_claim(claim_id)         # bool — derived: ≥2 outbound
                                      #       branches/splits = "general"
```

When multiple structural edges point at the same parent, the
most-specific type wins:
`chain_link_of > context_split_of > mediator_specific_of >
polarity_inverse_of > branches_from`.

### 4.5 PROPOSED — chain-DAG composites (multiple parallel paths)

The current `chain_link_of` model assumes a **linear** chain
A → B → C → D where every link is required (AND). That's a
faithful encoding of one mechanism story but not of how mechanism
hypotheses actually look in biology — most composites are reachable
through several parallel paths, only one of which needs to hold.

A typical RBMS1 → reduced CD8 infiltration composite might
decompose into:

```
                              ┌──── B1 (CXCL9 mRNA decay) ────┐
                              │                                ▼
   A (RBMS1↑) ─────────────── ├──── B2 (CXCL10 mRNA decay) ── D (less CD8 infiltration)
                              │                                ▲
                              └──── C  (IDO1 upregulation) ───┘
```

Three paths from A to D:
- A → B1 → D                  (chemokine path 1)
- A → B2 → D                  (chemokine path 2 — redundant with B1)
- A → C  → D                  (alternative metabolic path)

Within a path, every link is required (AND). Across paths, **any
one path being supported is sufficient** for D (OR). The current
schema can't express this cleanly: putting all five intermediates
as `chain_link_of` siblings of D implies every link is required,
which is wrong; making them `branches_from` siblings loses the
within-path AND structure.

Two ways to fix this. **Recommended is Option B** — it composes
existing primitives instead of adding a new edge type.

**Option A — new `chain_dag_of` edge type**

Add `chain_dag_of` to the structural-parent vocabulary, with
`properties.path_id` grouping links into AND-bundles:

```python
# Each leaf gets:
{
    "path_id": "p1",            # "p1" / "p2" / "p3"
    "step": 1,                  # position within the path (AND)
    "is_required_in_path": True,
}
```

Composite belief becomes
`OR(path) AND(link in path) believe(link)`.

**Option B — pure existing primitives, with one intermediate composite per path**

Use the existing `branches_from` (= OR — any branch sufficient) and
`chain_link_of` (= AND — every link required) edges to express the
DAG natively. Each path becomes a path-composite that is itself a
branch of the parent:

```
   composite D ("RBMS1 OE → reduced CD8 infiltration")
   │
   ├─ branches_from ─── path-composite p1 ("via CXCL9 decay")
   │                    │
   │                    ├── chain_link_of ── A (RBMS1↑)
   │                    └── chain_link_of ── B1 (CXCL9 mRNA destab.)
   │
   ├─ branches_from ─── path-composite p2 ("via CXCL10 decay")
   │                    │
   │                    ├── chain_link_of ── A
   │                    └── chain_link_of ── B2 (CXCL10 mRNA destab.)
   │
   └─ branches_from ─── path-composite p3 ("via IDO1")
                        │
                        ├── chain_link_of ── A
                        └── chain_link_of ── C (IDO1↑)
```

Semantics fall out for free:
- `branches_from` from D's perspective is OR — D needs *any* one
  of its branches to hold.
- `chain_link_of` within a path-composite is AND — that path needs
  *every* link to hold.
- Each path-composite can carry its own cohort-level evidence
  (e.g. "TCGA SKCM survival HR for high-RBMS1 + low-CXCL9" is
  evidence specific to path p1, not to the parent D).
- The shared upstream node A is referenced from each path; sharing
  is an entity-level property (same `claim_id`), not a schema
  feature.

**Why Option B over Option A:**

| | Option A (`chain_dag_of` + path_id) | Option B (path-composites) |
|---|---|---|
| Edge types in the registry | +1 (`chain_dag_of`) | 0 |
| Belief computation | new path-aggregation rule | reuses Part VI §30's `noisy_or(own, children_p)` recursively |
| Wet-lab gate | new "any path closed" rule | a path-composite is closed when its leaves are — same gate as any composite |
| Per-path own evidence | needs another edge type or another column | path-composite has its own row; own evidence attaches the same way as any composite |
| Structural-parent invariant | needs a special case (multiple `chain_dag_of` edges to one parent are fine if same path_id) | already handled — multiple `chain_link_of` to the same path-composite is the ordinary case |

Option B is structurally cleaner because the OR / AND logic is
already what `branches_from` and `chain_link_of` mean. The "DAG-ness"
emerges from the entity-level reuse of upstream nodes (A in the
example), not from a new edge type.

**Migration cost**: zero new schema. Today's linear-chain
composites either:
1. Stay as-is (single path, no parallelism) — the current
   `chain_link_of` rooted directly at the parent is exactly
   "one path, every link required". This is just Option B with
   one branch.
2. Get re-rooted under a path-composite when a second alternative
   mechanism is added. The conversion is mechanical: insert a
   path-composite, re-point the existing leaves' `chain_link_of`
   edges at it, add a `branches_from` edge from the path-composite
   up to the original parent.

**Open questions**:
- *Naming.* If we ship Option B, do path-composites need a typed
  marker (e.g. `claim_type = MECHANISM_PATH`) so readers can tell
  them apart from "ordinary" composites? The L1 header already
  shows `claim_type`, so this falls out for free if we add a new
  ClaimType value.
- *When to split.* Today the wave orchestrator emits MH-1, MH-2,
  MH-3 as direct `branches_from` siblings of the parent. That's
  the "OR with no within-path AND" case — which is Option B
  degenerate. The work is only when a single MH itself decomposes
  into a multi-link chain that has alternative routes.

This proposal is **not yet implemented.** No code, no schema
change, no plan-part number assigned. It's recorded here as the
canonical answer to "how do we encode parallel mechanism paths
without adding a new edge type to the registry."

---

## 5. Edge creation paths

Two ways an edge enters `claim_relations`:

### 5.1 Direct call: `kg.add_claim_relation`

```python
kg.add_claim_relation(
    source_claim_id="rbms1-mh-2",       # child
    target_claim_id="rbms1-composite",  # parent
    relation_type="chain_link_of",
    rationale="Step 2: RBMS1 destabilises the chemokine mRNAs",
    confidence=0.85,
    judge_model="dispatch",
    properties={
        "step": 2,
        "step_role": "molecular_consequence",
        "is_canonical_backbone": True,
    },
)
```

The function:
1. Validates `relation_type` against `KnowledgeGraph.CLAIM_RELATION_TYPES`.
2. Computes a deterministic `relation_id` (SHA-256 of
   `source|relation_type|target`) so re-asserting the same edge is
   idempotent.
3. INSERT-OR-REPLACE the row with `properties` JSON-serialised.
4. Calls `validate_lineage(conn, source_claim_id)` — if the new edge
   creates a structural conflict (multiple parents / cycle), it
   raises `LineageError` and the row is deleted.

### 5.2 Dual-write inside `add_claim`

When `add_claim(claim)` is called and the `Claim` instance carries
the legacy `parent_claim_id` attribute, `add_claim` automatically
writes the corresponding structural-parent edge:

```python
# Inside add_claim, after the row INSERT:
legacy_pid = (getattr(claim, "parent_claim_id", "") or "").strip()
if legacy_pid and legacy_pid != claim.claim_id:
    rtype = _legacy_refinement_to_relation_type(
        getattr(claim, "refinement_type", "") or ""
    )
    edge_props = _properties_blob({
        "splits_on_dimension":   getattr(claim, "splits_on_dimension", "") or "",
        "target_mechanism_ids":  json.dumps(...),
        "inherited_evidence_ids":json.dumps(...),
    })
    self.conn.execute(
        "INSERT OR IGNORE INTO claim_relations (...) VALUES (...)",
        (..., edge_props),
    )
```

Why this matters: existing code that constructs a `Claim` with
`parent_claim_id="..."` still works — the row no longer carries that
column, but the dual-write block lifts the value off the dataclass
field and persists the equivalent edge. Source-compatibility is
preserved while the schema cuts cleanly.

### 5.3 The "claims become edges" path: graduation → `backbone_edges`

When a leaf claim graduates to `EXTERNALLY_SUPPORTED`, its content
matches the encoding of `backbone_edges` exactly:

```
LEAF claim (post-graduation):                      promotes to:
  source_id  = claim.participants[role=SUBJECT]    backbone_edges row:
  target_id  = claim.participants[role=OBJECT]       source_id, target_id,
  relation_name + relation_polarity                  edge_type (legacy alias),
  evidence: gathered into a SupportSet               relation_name,
                                                     relation_polarity (Phase Q)
```

The leaf-edge invariant (one SUBJECT + one OBJECT) is what makes
this clean. Phase Q populated `relation_name` + `relation_polarity`
on every existing `backbone_edges` row using a deterministic 24 → 18
mapping; new graduated leaves slot into that namespace without
translation. Composites are NOT promoted — their leaves are.

---

## 6. Evidence: own vs. subtree

A claim's evidence sits in two physically distinct places.

### 6.1 Own evidence — directly on the claim

Every `biological_results` row carries a `claim_id`. **Direct
evidence for a claim is the set of `biological_results` rows whose
`claim_id` matches**, gated through the `result_to_claim` table:

```sql
SELECT br.*
  FROM biological_results br
  LEFT JOIN result_to_claim rtc
         ON rtc.result_id = br.result_id
        AND rtc.claim_id  = br.claim_id
 WHERE br.claim_id = :cid
   AND (rtc.result_id IS NULL OR rtc.attached = 1);
```

The `result_to_claim` row is the gate: when present with
`attached=0`, the result is rejected (e.g. quality-verdict failed).
When absent, the result is included by default. This separation
lets `biological_results` capture every tool invocation while
`result_to_claim` records the audit trail of which ones actually
count toward this claim's belief.

Both **leaves and composites** can carry their own evidence:
- a leaf's own evidence is typically mechanistic (CLIP-seq peak,
  mRNA decay assay, IP/MS) — one assay can prove one edge
- a composite's own evidence is typically cohort-level (Cox HR on
  TCGA, scRNA differential, IHC tissue array) — one assay reads on
  the phenotype, not the mechanism

A leaf with no own evidence raises the `unevidenced_leaf` review
flag. A composite with no own evidence is fine if its decomposition
children carry the load.

### 6.2 Subtree evidence — via `claim_relations` traversal

A composite's belief also derives from its descendants. The
"evidence for this composite" question is answered by walking the
structural-parent edges *downward* from the composite to every
leaf:

```sql
-- All descendants of one composite (recursive CTE), then their evidence
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

That gives the **subtree evidence**: every result attached to any
descendant of the composite.

### 6.3 The split

The data model deliberately keeps the two evidence buckets distinct:

| | Lives on | Read via | Counts toward |
|---|---|---|---|
| Own evidence | `biological_results.claim_id == cid` | direct JOIN | this claim's count rollups (`n_supporting`, `n_refuting`, `n_assays`, `decisive_coverage`) |
| Subtree evidence | descendants' `biological_results` | recursive CTE through `claim_relations` | the composite's `*_subtree` derived rollups (Part VI §30.3) |

Neither overrides the other. The composite sees both
simultaneously. This is what enables the
`composite_evidence_disagreement` review flag (Part VI §30.1): when
the own-evidence verdict diverges sharply from the subtree-evidence
verdict, the claim is flagged for review rather than auto-resolved.

---

## 7. Worked example — RBMS1 composite + MH-1 leaf

Live data from prod (`rbms1-cl-fanout-20260427-214931` family,
`gbd_knowledge_graph.db`, 2026-04-29):

### 7.1 Parent (composite)

```
claim_id           = rbms1-cl-fanout-20260427-214931
claim_type         = PathwayRedundancyHypothesis
claim_text         = RBMS1 overexpression causes reduced immune signaling
relation_name      = ''   (Phase R didn't fill — aborted_for_refinement_pivot
                           isn't in the verb-alias map)
relation_polarity  = ''
evidence_status    = aborted_for_refinement_pivot
proof_level        = 2 (observational_association)
confidence_summary = unknown   (the §47 catch-all for aborted/anomaly states)

biological_results count: 0    (this composite carries no own evidence —
                                belief comes from its 12 children)
inbound structural-parent children: 12
```

### 7.2 Child (mechanism-hypothesis leaf MH-1)

```
claim_id           = rbms1-cl-fanout-20260427-214931-MH-1-eager
claim_type         = PathwayRedundancyHypothesis
claim_text         = RBMS1 acts via CXCL9 and CXCL10 mRNAs (destabilises_mrna)
                     to produce the phenotype asserted in the parent claim ...
evidence_status    = observed
proof_level        = 2
confidence_summary = unknown

claim_participants:
  effector_gene  → HGNC:RBMS1
  regulatee      → HGNC:CXCL9
  regulatee      → FT:cxcl10_mrnas

biological_results: 2 rows
contradicting siblings: 0
grandchildren: 8
```

### 7.3 The edge between them

```
relation_id    = rel_branches_from_b69d37fbe69c4d6d
relation_type  = branches_from
source_claim_id = rbms1-cl-fanout-20260427-214931-MH-1-eager     (the child)
target_claim_id = rbms1-cl-fanout-20260427-214931                (the parent)
rationale      = Eager-seeded from generate_mechanism_hypotheses:
                 RBMS1-destabilizes-CXCL9-10-mRNAs
                 (layer=post_transcriptional, plausibility=high)
confidence     = 0.7
judge_model    = dispatch
properties     = {}
created_at     = 2026-04-28T01:51:11.194254+00:00
```

### 7.4 An edge with populated `properties` JSON

A sibling claim shows the typed-properties shape:

```
relation_type   = mediator_specific_of
source_claim_id = rbms1-cl-fanout-20260427-214931__alt-link-2-2
target_claim_id = rbms1-cl-fanout-20260427-214931
properties      = {"target_mechanism_ids":
                     ["rbms1-cl-fanout-20260427-214931__link-2-2"]}
```

This claim is an alternative mechanism *specifically* for chain link
2-2 of the parent's causal chain — the property tells future readers
which link this alt-mechanism is replacing.

### 7.5 Promotion outcome

If MH-1 graduates (its 2 attached results plus children's evidence
reach `EXTERNALLY_SUPPORTED`), it becomes a `backbone_edges` row:

```
backbone_edges row:
  source_id          = HGNC:RBMS1
  target_id          = HGNC:CXCL9
  edge_type          = (legacy alias retained for one release)
  relation_name      = regulates_mrna_stability    (Phase Q: leaf-domain
                                                    polarised predicate)
  relation_polarity  = negative                    (Phase R reverse-alias
                                                    map: "destabilises" →
                                                    regulates_mrna_stability
                                                    + NEGATIVE)
```

Phase Q populated this `relation_name` + `relation_polarity`
namespace on every existing `backbone_edges` row, so the leaf claim
slots into the canonical biology layer with no translation step. The
parent composite is NOT promoted — its leaves are.

---

## 8. Schema summary table

After Parts I-IX of `REMOVE_CLAIM_DIRECTION_FIELD_PLAN.md`, the
`claims` row carries 56 columns. The columns split into a **load-
bearing core** that the runtime reads on every wave, and a
**retirement queue** of fields that are persisted today but slated
to move off the row.

### 8.1 Load-bearing core (kept on the row)

| Axis | Columns |
|---|---|
| Identity & type | `claim_id`, `claim_type`, `created_at`, `created_by` |
| Content (what it asserts) | `claim_text`, `relation_name`, `relation_polarity`, `human_readable`, `description` |
| Status (3 axes — orthogonal) | `evidence_status`, `prior_art_status`, `review_status`, `superseded_by` |
| Proof ladder + replication | `proof_level`, `n_studies`, `n_modalities`, `direction_consistency` |
| Confidence (categorical) | `confidence_summary`, `narrative`, `narrative_updated_at` |
| Context & dedup | `context_set_json`, `cell_states_json`, `context_operator`, `cancer_type_scope`, `edge_signature` |
| Live-run state | `kg_evidence`, `tools_to_prioritise`, `embedding_text`, `last_wave_completed`, `full_data` |

### 8.2 Retirement queue

| Group | Columns | Why retire | Where it lives instead |
|---|---|---|---|
| Lineage (Phase T — DONE) | `parent_claim_id`, `refinement_type`, `refinement_rationale`, `refinement_confidence`, `splits_on_dimension`, `target_mechanism_ids`, `inherited_evidence_ids`, `is_general` | Mixed structure into content; one parent in 8 columns | `claim_relations.relation_type` + `properties` JSON |
| DAG-1 ranking (proposed) | `tractability_score`, `kg_connectivity_score`, `priority_score` | Computed once at candidate selection, never re-read after the claim enters DAG-2 | A `dag1_candidates` log table — keep the score for audit, off the persisted claim |
| Per-row provenance scalars (proposed) | `source`, `source_dataset`, `source_release`, `assay_type`, `model_name`, `model_version`, `artifact_id` | Describe HOW one piece of evidence was produced, not what the claim asserts; one claim can be backed by evidence from multiple datasets each with its own version | `biological_results` (per evidence row) + `support_sets` (per bundle) + `claim_events` (per state transition) |
| Flat statistics (Part IV — pending) | `effect_size`, `effect_unit`, `p_value`, `q_value`, `confidence_interval` | One claim, many results, each with its own statistics — the row picks an arbitrary winner | `biological_results.effect_size` / `p_value` / etc. per row |
| Identity aliases (Part III — pending) | `candidate_gene`, `candidate_id` | Duplicate `claim_participants[role=effector_gene]` and `claim_id` respectively | Already in those tables |

Each retirement happens in its own gated drop call (same recipe as
Phase T's `drop_legacy_lineage_columns`): write the audit gate, run
the rebuild, fix any reader/writer that touches the dropped column.

---

## 9. References

- `REMOVE_CLAIM_DIRECTION_FIELD_PLAN.md` — the master plan (Parts I-IX)
- `gbd/knowledge_graph/claim_digest.py` — L0–L5 layered API +
  categorical `confidence_summary` (§47)
- `gbd/knowledge_graph/lineage_phase_t.py` — structural-parent
  helpers, validate_lineage gate, gated column-drop
- `gbd/knowledge_graph/relation_backfill.py` — Phase Q backbone
  re-typing + Phase R reverse-alias map
- `gbd/knowledge_graph/graph.py` — KnowledgeGraph class with the
  schema migrations and `kg.structural_parent` / `is_general_claim`
  read methods
- `claim_examples/` — seven concrete walkthroughs of real prod claims
  (one per ConfidenceSummary level + a Phase T multi-edge example)
