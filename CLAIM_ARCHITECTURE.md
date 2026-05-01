# Claim Object

Field-by-field schema for `claims` and its satellites, plus two
worked examples (bifurcated Signor curated claim; parent-child
mechanism pair with a multi-parent leaf).

---

## 1. Where the data lives

A claim's persistence is split across **eight tables**. Each table
holds one axis; nothing is duplicated.

```
                       ┌───────────────────────────────────┐
                       │              CLAIMS               │
                       │  41 columns, 881 660 rows         │
                       │                                   │
                       │  Content — what the claim says:   │
                       │    claim_text, relation_name,     │
                       │    relation_polarity              │
                       │  Status — three orthogonal axes:  │
                       │    evidence_status,               │
                       │    prior_art_status,              │
                       │    review_status                  │
                       │  Proof + replication:             │
                       │    proof_level, n_studies,        │
                       │    n_modalities                   │
                       │  Cross-evidence rollups:          │
                       │    n_supporting_results,          │
                       │    n_refuting_results,            │
                       │    n_null_results,                │
                       │    n_inconclusive, n_assays,      │
                       │    n_datasets, n_supporting_pmids,│
                       │    polarity_consistency,          │
                       │    decisive_coverage,             │
                       │    proxy_coverage                 │
                       │  Categorical belief:              │
                       │    confidence_summary             │
                       │  Context scope:                   │
                       │    context_set_json,              │
                       │    cell_states_json,              │
                       │    context_operator,              │
                       │    participant_combinator         │
                       │  Identity dedup:                  │
                       │    edge_signature                 │
                       │  Audit:                           │
                       │    created_at, created_by         │
                       │  Narrative:                       │
                       │    narrative,                     │
                       │    narrative_updated_at           │
                       │  Run state:                       │
                       │    full_data,                     │
                       │    last_wave_completed, uct2      │
                       └─────────────────┬─────────────────┘
                                         │
            ┌────────────────────────────┼────────────────────────────┐
            ▼                            ▼                            ▼
   ┌────────────────┐         ┌──────────────────────┐    ┌──────────────────────┐
   │ claim_         │         │ biological_results   │    │ claim_relations      │
   │ participants   │         │ (per-tool result)    │    │ (claim ↔ claim edges)│
   │                │         │                      │    │                      │
   │ entity_id,     │         │ result_id, claim_id, │    │ source_claim_id,     │
   │ role,          │         │ assay, outcome,      │    │ target_claim_id,     │
   │ properties JSON│         │ effect_size, p_value,│    │ relation_type,       │
   │                │         │ n,                   │    │ rationale,           │
   │ Resolved via   │         │ statistical_test_    │    │ confidence,          │
   │ entity_aliases │         │ performed,           │    │ properties JSON      │
   │                │         │ evidence_category,   │    │                      │
   │ Roles: SUBJECT,│         │ source_dataset,      │    │ See §3 for the 9     │
   │ OBJECT,        │         │ assay_type, ...      │    │ relation_type values │
   │ CONTEXT_*      │         │                      │    │                      │
   │                │         │ Gated by             │    │                      │
   │                │         │ result_to_claim      │    │                      │
   │                │         │ (attached=1 to count)│    │                      │
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
   │ confidence (0–1)     │    │                      │    │                      │
   └──────────────────────┘    └──────────────────────┘    └──────────────────────┘
```

- **claims**: content + status only.
- **claim_participants**: which entities (subject / object / context).
- **biological_results**: per-tool evidence rows (assay, outcome, p, n, etc.).
- **claim_relations**: claim ↔ claim edges (lineage + non-structural).
- **support_sets**: AND-grouped evidence bundles.
- **publication_support**: per-claim literature rollup.
- **claim_events**: append-only audit trail.

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
| 29 | `n_supporting_results` | INTEGER | `0` | COUNT(`biological_results.outcome='positive'`). |
| 30 | `n_refuting_results` | INTEGER | `0` | COUNT(`outcome='negative'`). |
| 31 | `n_null_results` | INTEGER | `0` | COUNT(`outcome='null'`). |
| 32 | `n_inconclusive` | INTEGER | `0` | COUNT(`outcome='inconclusive'`). |
| 33 | `n_assays` | INTEGER | `0` | DISTINCT(`biological_results.assay`). |
| 34 | `n_datasets` | INTEGER | `0` | DISTINCT(`biological_results.source_dataset`). |
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
| 40 | `uct2` | TEXT | `''` | UCT-2 score for the planner's bandit ranking. |

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

> Authoritative per-evidence statistics are on `biological_results`. These row-level columns are a fast read for legacy callers.

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

**Lineage shape: DAG, not tree.** A claim can have:

- multiple inbound structural-parent edges to the **same** parent (e.g. `branches_from` + `mediator_specific_of`);
- multiple inbound structural-parent edges to **different** parents (one biological fact reused across many composites — see §5.7).

Only **cycles** are rejected at write time. `add_claim_relation` runs a BFS upward; any path re-entering the source raises.

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

## 5. Worked example B — parent / chain-link child mechanism pair

Composite parent (cohort-level phenotype) + chain-link leaf (one mechanistic step). The four chain links AND together to support the parent.

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
claim_text              = 'PTEN loss in glioblastoma derepresses the PI3K/AKT axis, driving cell-cycle entry and proliferation. The composite asserts the cohort-level outcome; the four chain links assert each mechanistic step.'
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

The parent's three other chain links (`__link-2-akt-activation`, `__link-3-mtor-engagement`, `__link-4-cell-cycle-entry`) carry `properties.step` = 2, 3, 4.

### 5.5 Their evidence

Parent: cohort-level (TCGA Cox HR, TIDE, IHC). Leaf: direct enzymatic (lipid phosphatase assay, ³¹P-NMR, ClinVar).

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
> proliferation — same row that the DepMap co-essentiality
> `biological_result` flagged.

### 5.6 The two evidence buckets

- Parent `n_supporting_results = 5` counts only the parent's own attached results.
- Leaf `n_supporting_results = 3` counts only the leaf's own.
- "Total evidence for the parent mechanism" = walk descendants via `claim_relations`, union each descendant's `biological_results` (§6.2).

### 5.7 Multi-parent: one biological fact, many composite parents

"PTEN dephosphorylates PIP3" is context-free biology and reused as a `chain_link_of` for many composites (glioma, TNBC, melanoma…). One leaf, multiple inbound `chain_link_of` edges — no duplication, no evidence fragmentation:

```
   ┌──────────────────────────────────────────────────────────────┐
   │ COMPOSITE A — mh:PTEN-loss-AKT-glioma-proliferation           │
   │   context_set_json = {"cancer_type":"MONDO:GBM",              │
   │                        "cell_compartment":"tumor_intrinsic"}  │
   └──────────────┬───────────────────────────────────────────────┘
                  │ chain_link_of
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
                  │ chain_link_of
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
uct2                    = '0.45'
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

Its own evidence (cohort-level, distinct from Composite A):

```
─── biological_results — COMPOSITE B ───────────────────────────────
result_id            claim_id                            result_type   assay                                       provider              outcome      effect_size  p_value     n      statistical_test_performed  evidence_category    timestamp
br-pten-tnbc-coxhr   mh:PTEN-loss-AKT-TNBC-metastasis    analysis      Cox proportional hazards (METABRIC TNBC DMFS) provider:metabric    positive     1.9          0.003       208    1                           statistical_test     2026-04-29T11:00Z
br-pten-tnbc-cibersort mh:PTEN-loss-AKT-TNBC-metastasis  analysis      CIBERSORTx tumor-infiltrating macrophages    provider:cibersort   inconclusive 0.21         0.087       144    1                           statistical_test     2026-04-29T11:01Z
br-pten-tnbc-ihc-mki67 mh:PTEN-loss-AKT-TNBC-metastasis  analysis      MKI67 IHC (TNBC TMA)                          provider:ihc_tnbc    positive     1.4          0.012       58     1                           statistical_test     2026-04-29T11:02Z
```

#### 5.7.2 The shared leaf carries TWO inbound `chain_link_of` edges

```
─── claim_relations ────────────────────────────────────────────────
relation_id        source_claim_id                                                  target_claim_id                            relation_type   confidence  properties
rel_chain_link_…   mh:PTEN-loss-…__link-1-pten-phosphatase                         mh:PTEN-loss-AKT-glioma-proliferation      chain_link_of   0.95        {"step":1,"step_role":"perturbation","is_canonical_backbone":true}
rel_chain_link_…   mh:PTEN-loss-…__link-1-pten-phosphatase                         mh:PTEN-loss-AKT-TNBC-metastasis           chain_link_of   0.93        {"step":1,"step_role":"perturbation","is_canonical_backbone":true}
```

- `kg.structural_parents(leaf_id)` returns both parents.
- Leaf's 3 evidence rows shared by both composites; no duplication.
- New evidence attached to the leaf flows into both parents' subtree rollups (§6.2).
- Leaf's `context_set_json = '{}'`; composites carry the cancer-type context.

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

On graduation (`evidence_status='externally_supported'`, no open `contradicts`), a leaf maps directly to a backbone edge:

```
LEAF claim:                                  backbone_edges row:
  participants[role=subject].entity_id  ─→     source_id
  participants[role=object].entity_id   ─→     target_id
  relation_name + relation_polarity     ─→     relation_name + relation_polarity
  edge_signature                        ─→     edge_id
```

Lock: exactly one SUBJECT + one OBJECT principal participant per leaf — the leaf-edge invariant.
