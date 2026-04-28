-- Live CREATE TABLE / CREATE INDEX statements from the GBD KG SQLite DB.
-- Source: gbd_knowledge_graph.db

-- table: agent_runs
CREATE TABLE agent_runs (
            run_id TEXT PRIMARY KEY,
            timestamp TEXT DEFAULT '',
            query TEXT DEFAULT '',
            goal TEXT DEFAULT '',
            hypothesis TEXT DEFAULT '',
            tools_used TEXT DEFAULT '[]',
            claims_created TEXT DEFAULT '[]',
            contradictions_found TEXT DEFAULT '[]',
            outcome TEXT DEFAULT '',
            elapsed_seconds REAL DEFAULT 0.0,
            n_claims_added INTEGER DEFAULT 0,
            n_contradictions_found INTEGER DEFAULT 0,
            n_textbook_filtered INTEGER DEFAULT 0,
            full_data TEXT DEFAULT '{}'
        );

-- table: backbone_edges
CREATE TABLE backbone_edges (
            edge_id TEXT PRIMARY KEY,
            edge_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            properties TEXT DEFAULT '{}',
            source_db TEXT DEFAULT '',
            confidence REAL DEFAULT 1.0,
            FOREIGN KEY (source_id) REFERENCES entities(entity_id),
            FOREIGN KEY (target_id) REFERENCES entities(entity_id)
        );

-- table: biological_results
CREATE TABLE biological_results (
            result_id TEXT PRIMARY KEY,
            claim_id TEXT NOT NULL,
            result_type TEXT NOT NULL,
            assay TEXT DEFAULT '',
            provider TEXT DEFAULT '',
            context TEXT DEFAULT '{}',
            outcome TEXT DEFAULT '',
            effect_direction TEXT DEFAULT '',
            effect_size REAL DEFAULT 0.0,
            confidence_interval TEXT DEFAULT '(0.0, 0.0)',
            p_value REAL DEFAULT 1.0,
            n INTEGER DEFAULT 0,
            depends_on TEXT DEFAULT '[]',
            validity_scope TEXT DEFAULT '',
            timestamp TEXT DEFAULT '',
            agent_run_id TEXT DEFAULT '',
            artifact_paths TEXT DEFAULT '[]', statistical_test_performed INTEGER DEFAULT 0, evidence_category TEXT DEFAULT 'statistical_test',
            FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
        );

-- table: claim_embeddings
CREATE TABLE claim_embeddings (
            claim_id TEXT PRIMARY KEY,
            embedding_text TEXT DEFAULT '',
            embedding_vec_json TEXT DEFAULT '[]',
            embedding_model TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
        );

-- table: claim_events
CREATE TABLE claim_events (
    event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id      TEXT NOT NULL,
    axis          TEXT NOT NULL,
    old_value     TEXT,
    new_value     TEXT,
    reason        TEXT,
    actor         TEXT,
    agent_run_id  TEXT DEFAULT '',
    wave          INTEGER DEFAULT 0,
    timestamp     TEXT
);

-- table: claim_participants
CREATE TABLE claim_participants (
            claim_id TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            role TEXT NOT NULL,
            properties TEXT DEFAULT '{}',
            FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
        );

-- table: claim_relations
CREATE TABLE claim_relations (
            relation_id TEXT PRIMARY KEY,
            source_claim_id TEXT NOT NULL,
            target_claim_id TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            rationale TEXT DEFAULT '',
            confidence REAL DEFAULT 0.5,
            source_run_id TEXT DEFAULT '',
            judge_model TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            FOREIGN KEY (source_claim_id) REFERENCES claims(claim_id),
            FOREIGN KEY (target_claim_id) REFERENCES claims(claim_id)
        );

-- table: claims
CREATE TABLE claims (
            claim_id TEXT PRIMARY KEY,
            claim_type TEXT NOT NULL,
            status TEXT DEFAULT 'observed',
            direction TEXT DEFAULT '',
            effect_size REAL DEFAULT 0.0,
            effect_unit TEXT DEFAULT '',
            human_readable TEXT DEFAULT '',
            proof_level INTEGER DEFAULT 2,
            p_value REAL,
            q_value REAL,
            confidence_interval TEXT,
            n_studies INTEGER DEFAULT 0,
            n_modalities INTEGER DEFAULT 0,
            direction_consistency REAL DEFAULT 0.0,
            source_dataset TEXT DEFAULT '',
            assay_type TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            description TEXT DEFAULT '',
            superseded_by TEXT DEFAULT '',
            full_data TEXT DEFAULT '{}'
        , evidence_status TEXT DEFAULT 'draft', prior_art_status TEXT DEFAULT 'unsearched', review_status TEXT DEFAULT 'clean', claim_text TEXT DEFAULT '', context_set_json TEXT DEFAULT '{}', edge_signature TEXT DEFAULT '', source_release TEXT DEFAULT '', model_name TEXT DEFAULT '', model_version TEXT DEFAULT '', artifact_id TEXT DEFAULT '', context_operator TEXT DEFAULT 'AND', tractability_score REAL, kg_connectivity_score REAL, priority_score REAL, source TEXT DEFAULT '', kg_evidence TEXT DEFAULT '[]', relation_name TEXT DEFAULT '', relation_polarity TEXT DEFAULT '', parent_claim_id TEXT DEFAULT '', refinement_type TEXT DEFAULT '', refinement_rationale TEXT DEFAULT '', refinement_confidence REAL, splits_on_dimension TEXT DEFAULT '', is_general INTEGER DEFAULT 0, target_mechanism_ids TEXT DEFAULT '[]', inherited_evidence_ids TEXT DEFAULT '[]', tools_to_prioritise TEXT DEFAULT '[]', cancer_type_scope TEXT DEFAULT '', embedding_text TEXT DEFAULT '', candidate_gene TEXT DEFAULT '', candidate_id TEXT DEFAULT '', cell_states_json TEXT DEFAULT '[]', last_wave_completed INTEGER DEFAULT 0);

-- table: context_nodes
CREATE TABLE context_nodes (
            node_id TEXT PRIMARY KEY,
            dimension TEXT NOT NULL,
            canonical_name TEXT DEFAULT '',
            description TEXT DEFAULT '',
            aliases TEXT DEFAULT '[]',
            is_a TEXT DEFAULT '[]',
            resolved INTEGER DEFAULT 0,
            ontology_source TEXT DEFAULT '',
            ontology_id TEXT DEFAULT '',
            usage_count INTEGER DEFAULT 0,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            mapped_at TEXT DEFAULT ''
        );

-- table: contradiction_cases
CREATE TABLE contradiction_cases (
            case_id TEXT PRIMARY KEY,
            claim_a_id TEXT NOT NULL,
            claim_b_id TEXT NOT NULL,
            reason TEXT DEFAULT '',
            classification TEXT DEFAULT 'true_frontier',
            resolution TEXT DEFAULT 'open',
            resolution_action TEXT DEFAULT '',
            spawned_plans TEXT DEFAULT '[]',
            lineage_specific INTEGER,
            assay_specific INTEGER,
            modality_mismatch INTEGER,
            timepoint_dependent INTEGER,
            quality_failure_in TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            FOREIGN KEY (claim_a_id) REFERENCES claims(claim_id),
            FOREIGN KEY (claim_b_id) REFERENCES claims(claim_id)
        );

-- table: contradictions
CREATE TABLE contradictions (
            contradiction_id TEXT PRIMARY KEY,
            claim_id_a TEXT NOT NULL,
            claim_id_b TEXT NOT NULL,
            contradiction_type TEXT DEFAULT '',
            contradiction_class TEXT DEFAULT 'rectifiable',
            description TEXT DEFAULT '',
            severity TEXT DEFAULT 'medium',
            resolved INTEGER DEFAULT 0,
            resolution TEXT DEFAULT '',
            exploration_priority TEXT DEFAULT 'medium',
            exploration_rationale TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            FOREIGN KEY (claim_id_a) REFERENCES claims(claim_id),
            FOREIGN KEY (claim_id_b) REFERENCES claims(claim_id)
        );

-- table: credibility_assessments
CREATE TABLE credibility_assessments (
            assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id TEXT NOT NULL,
            wave INTEGER DEFAULT 0,
            edge_id TEXT DEFAULT '',
            evidence_hash TEXT NOT NULL,
            verdict TEXT NOT NULL,
            point_estimate REAL DEFAULT 0.0,
            interval_low REAL DEFAULT 0.0,
            interval_high REAL DEFAULT 1.0,
            weakest_axis TEXT DEFAULT '',
            rationale TEXT DEFAULT '',
            axis_scores TEXT DEFAULT '{}',
            source_notes TEXT DEFAULT '[]',
            suggested_followups TEXT DEFAULT '[]',
            meta_analysis_summary TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            UNIQUE(claim_id, wave, evidence_hash)
        );

-- table: edge_signature_migration
CREATE TABLE edge_signature_migration (
            claim_id  TEXT NOT NULL,
            old_sig   TEXT NOT NULL,
            new_sig   TEXT NOT NULL,
            ran_at    TEXT NOT NULL,
            PRIMARY KEY (claim_id, ran_at)
        );

-- table: entities
CREATE TABLE entities (
            entity_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            name TEXT NOT NULL,
            aliases TEXT DEFAULT '[]',
            properties TEXT DEFAULT '{}',
            xrefs TEXT DEFAULT '{}'
        );

-- table: entity_aliases
CREATE TABLE entity_aliases (
            alias               TEXT NOT NULL,
            namespace           TEXT NOT NULL,
            canonical_entity_id TEXT NOT NULL,
            confidence          REAL NOT NULL DEFAULT 1.0,
            source              TEXT NOT NULL,
            created_at          TEXT NOT NULL,
            PRIMARY KEY (alias, namespace, canonical_entity_id),
            FOREIGN KEY (canonical_entity_id) REFERENCES entities(entity_id)
        );

-- table: evidence
CREATE TABLE evidence (
            evidence_id TEXT PRIMARY KEY,
            evidence_type TEXT NOT NULL,
            description TEXT DEFAULT '',
            source TEXT DEFAULT '',
            statistic_name TEXT DEFAULT '',
            statistic_value REAL,
            p_value REAL,
            effect_size REAL,
            sample_size INTEGER DEFAULT 0,
            full_data TEXT DEFAULT '{}'
        , confidence_interval TEXT DEFAULT '', pmid TEXT DEFAULT '', doi TEXT DEFAULT '', year INTEGER DEFAULT 0, title TEXT DEFAULT '', accession TEXT DEFAULT '', n_samples INTEGER DEFAULT 0, organism TEXT DEFAULT 'Homo sapiens', perturbation_type TEXT DEFAULT '', perturbed_gene TEXT DEFAULT '', readout TEXT DEFAULT '', cell_line TEXT DEFAULT '', model_name TEXT DEFAULT '', model_version TEXT DEFAULT '', cv_metric TEXT DEFAULT '', cv_value REAL DEFAULT NULL, artifact_path TEXT DEFAULT '', artifact_hash TEXT DEFAULT '', created_at TEXT DEFAULT '');

-- table: evidence_attachment_audit
CREATE TABLE evidence_attachment_audit (
    audit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    wave          INTEGER,
    result_id     TEXT,
    claim_id      TEXT,
    decision      TEXT,
    reason        TEXT,
    quality_gate  TEXT,
    agent_run_id  TEXT,
    timestamp     TEXT
);

-- table: publication_support
CREATE TABLE publication_support (
            claim_id TEXT PRIMARY KEY,
            authority_level TEXT DEFAULT 'novel',
            authority_score REAL DEFAULT 0.0,
            novelty TEXT DEFAULT 'HIGH',
            n_total_articles INTEGER DEFAULT 0,
            n_direct_evidence INTEGER DEFAULT 0,
            n_tier1_papers INTEGER DEFAULT 0,
            n_with_perturbation INTEGER DEFAULT 0,
            n_supporting INTEGER DEFAULT 0,
            n_contradicting INTEGER DEFAULT 0,
            publications TEXT DEFAULT '[]',
            FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
        );

-- table: reconciliation_attempts
CREATE TABLE reconciliation_attempts (
            attempt_id TEXT PRIMARY KEY,
            contradiction_id TEXT NOT NULL,
            timestamp TEXT DEFAULT '',
            hypothesis TEXT DEFAULT '',
            test_result TEXT DEFAULT '',
            resolution_type TEXT DEFAULT '',
            resolution_detail TEXT DEFAULT '',
            promoted_to_frontier INTEGER DEFAULT 0,
            FOREIGN KEY (contradiction_id) REFERENCES contradictions(contradiction_id)
        );

-- table: result_to_claim
CREATE TABLE result_to_claim (
    result_id        TEXT NOT NULL,
    claim_id         TEXT NOT NULL,
    attached         INTEGER NOT NULL DEFAULT 1,
    quality_verdict  TEXT NOT NULL,
    rejection_reason TEXT DEFAULT '',
    confidence       REAL DEFAULT 1.0,
    attached_at      TEXT NOT NULL,
    attached_by      TEXT DEFAULT '',
    PRIMARY KEY (result_id, claim_id)
);

-- table: study_results
CREATE TABLE study_results (
            study_result_id TEXT PRIMARY KEY,
            question_id TEXT NOT NULL,
            study_id TEXT NOT NULL,
            evidence_family TEXT DEFAULT '',
            cohort_name TEXT DEFAULT '',
            context TEXT DEFAULT '{}',
            assay TEXT DEFAULT '',
            comparison TEXT DEFAULT '',
            model_type TEXT DEFAULT '',
            covariates TEXT DEFAULT '[]',
            n INTEGER DEFAULT 0,
            effect_size REAL,
            standard_error REAL,
            ci_low REAL,
            ci_high REAL,
            p_value REAL,
            q_value REAL,
            direction TEXT DEFAULT '',
            classification TEXT DEFAULT '',
            quality_flags TEXT DEFAULT '[]',
            artifact_paths TEXT DEFAULT '[]',
            node_id TEXT DEFAULT '',
            wave INTEGER DEFAULT 0,
            timestamp TEXT DEFAULT ''
        );

-- table: support_sets
CREATE TABLE support_sets (
            support_set_id TEXT PRIMARY KEY,
            claim_id TEXT NOT NULL,
            label TEXT DEFAULT '',
            logic TEXT DEFAULT 'AND',
            evidence_ids TEXT DEFAULT '[]',
            confidence REAL DEFAULT 0.0,
            proof_level INTEGER DEFAULT 2, stance TEXT DEFAULT 'supports', description TEXT DEFAULT '',
            FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
        );

-- table: tool_cache
CREATE TABLE tool_cache (
            cache_key TEXT PRIMARY KEY,
            tool_id TEXT NOT NULL,
            input_hash TEXT NOT NULL,
            compartment_hash TEXT,
            fidelity_tier TEXT,
            result_json TEXT,
            reserved_by TEXT,
            reserved_at TEXT,
            completed_at TEXT
        );

-- table: transformations
CREATE TABLE transformations (
            transform_id TEXT PRIMARY KEY,
            input_artifact TEXT DEFAULT '',
            output_artifact TEXT DEFAULT '',
            method TEXT DEFAULT '',
            parameters TEXT DEFAULT '{}',
            timestamp TEXT DEFAULT ''
        );

-- index: idx_claim_rel_src
CREATE INDEX idx_claim_rel_src ON claim_relations(source_claim_id);

-- index: idx_claim_rel_tgt
CREATE INDEX idx_claim_rel_tgt ON claim_relations(target_claim_id);

-- index: idx_claim_rel_type
CREATE INDEX idx_claim_rel_type ON claim_relations(relation_type);

-- index: idx_claims_candidate_gene
CREATE INDEX idx_claims_candidate_gene ON claims(candidate_gene);

-- index: idx_claims_candidate_id
CREATE INDEX idx_claims_candidate_id ON claims(candidate_id);

-- index: idx_claims_edge_signature
CREATE INDEX idx_claims_edge_signature ON claims(edge_signature);

-- index: idx_claims_evidence_status
CREATE INDEX idx_claims_evidence_status ON claims(evidence_status);

-- index: idx_claims_parent
CREATE INDEX idx_claims_parent ON claims(parent_claim_id);

-- index: idx_claims_prior_art
CREATE INDEX idx_claims_prior_art ON claims(prior_art_status);

-- index: idx_claims_review
CREATE INDEX idx_claims_review ON claims(review_status);

-- index: idx_claims_status
CREATE INDEX idx_claims_status ON claims(status);

-- index: idx_claims_type
CREATE INDEX idx_claims_type ON claims(claim_type);

-- index: idx_contradiction_cases_open
CREATE INDEX idx_contradiction_cases_open ON contradiction_cases(resolution);

-- index: idx_contradictions_class
CREATE INDEX idx_contradictions_class ON contradictions(contradiction_class);

-- index: idx_cred_claim
CREATE INDEX idx_cred_claim ON credibility_assessments(claim_id);

-- index: idx_cred_claim_wave
CREATE INDEX idx_cred_claim_wave ON credibility_assessments(claim_id, wave);

-- index: idx_ctxnode_dim
CREATE INDEX idx_ctxnode_dim ON context_nodes(dimension);

-- index: idx_ctxnode_resolved
CREATE INDEX idx_ctxnode_resolved ON context_nodes(resolved, dimension);

-- index: idx_edge_sig_mig_new
CREATE INDEX idx_edge_sig_mig_new ON edge_signature_migration(new_sig);

-- index: idx_edges_source
CREATE INDEX idx_edges_source ON backbone_edges(source_id);

-- index: idx_edges_target
CREATE INDEX idx_edges_target ON backbone_edges(target_id);

-- index: idx_edges_target_type
CREATE INDEX idx_edges_target_type ON backbone_edges(target_id, edge_type);

-- index: idx_entity_alias_canon
CREATE INDEX idx_entity_alias_canon ON entity_aliases(canonical_entity_id);

-- index: idx_entity_alias_lookup
CREATE INDEX idx_entity_alias_lookup ON entity_aliases(alias);

-- index: idx_evidence_pmid
CREATE INDEX idx_evidence_pmid ON evidence(pmid);

-- index: idx_participants_entity
CREATE INDEX idx_participants_entity ON claim_participants(entity_id);

-- index: idx_result_to_claim_claim
CREATE INDEX idx_result_to_claim_claim ON result_to_claim(claim_id);

-- index: idx_result_to_claim_result
CREATE INDEX idx_result_to_claim_result ON result_to_claim(result_id);

-- index: idx_results_claim
CREATE INDEX idx_results_claim ON biological_results(claim_id);

-- index: idx_study_results_question
CREATE INDEX idx_study_results_question ON study_results(question_id);

-- index: idx_tool_cache_reserved
CREATE INDEX idx_tool_cache_reserved ON tool_cache(reserved_by);

-- index: idx_tool_cache_tool
CREATE INDEX idx_tool_cache_tool ON tool_cache(tool_id);

