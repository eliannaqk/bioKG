#!/usr/bin/env python3
"""Populate KG with CPTAC patient tumor multi-omics — ALL modalities.

Creates research-question-agnostic IN VIVO claims from patient tumors:
  1. ProteomicsAbundanceClaim — protein abundance variance per gene × cancer
  2. PhosphorylationClaim — phospho-site variance per gene × cancer
  3. AcetylationClaim — acetylation variance per gene × cancer
  4. UbiquitylationClaim — ubiquitylation per gene × cancer
  5. DifferentialExpressionClaim — RNA-seq variance per gene × cancer

All claims tagged context_type="in_vivo" — these are PATIENT TUMORS.
They carry higher weight than DepMap cell line (in_vitro) claims.

Run:  python populate_kg_cptac.py
SLURM: sbatch --mem=16G --time=01:00:00 --wrap="python scripts/populate_kg_cptac.py"
"""
import csv
import gzip
import json
import logging
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("kg_cptac")

KG_PATH = Path(os.environ["KG_DATA_ROOT"]) / "gbd_knowledge_graph.db"
CPTAC_PDC = Path(os.environ["EXTERNAL_DATA_ROOT"]) / "cptac_all/pdc"
CPTAC_RNA = Path(os.environ["EXTERNAL_DATA_ROOT"]) / "cptac_rnaseq"

UTC = timezone.utc

# Map study name keywords to cancer types
CANCER_TYPE_MAP = {
    "ovarian": "OV", "breast": "BRCA", "colon": "COAD", "ccrcc": "CCRCC",
    "luad": "LUAD", "lscc": "LSCC", "ucec": "UCEC", "gbm": "GBM",
    "hnscc": "HNSCC", "pdac": "PDAC", "hepatocellular": "HCC",
    "gastric": "STAD", "pediatric": "PED", "kidney": "CCRCC",
    "aml": "AML", "sarcoma": "SAR", "melanoma": "SKCM",
}

# Map modality file to claim type
MODALITY_MAP = {
    "proteome.tsv": ("ProteomicsAbundanceClaim", "proteome"),
    "phosphoproteome.tsv": ("PhosphorylationClaim", "phosphoproteome"),
    "acetylome.tsv": ("AcetylationClaim", "acetylome"),
    "ubiquitylome.tsv": ("UbiquitylationClaim", "ubiquitylome"),
}


def _infer_cancer_type(study_name: str) -> str:
    """Infer cancer type from study directory name."""
    name_lower = study_name.lower()
    for keyword, cancer in CANCER_TYPE_MAP.items():
        if keyword in name_lower:
            return cancer
    return "UNKNOWN"


def _parse_tsv_matrix(filepath: Path) -> tuple[list[str], list[str], np.ndarray]:
    """Parse a CPTAC TSV matrix. Returns (genes, samples, data_matrix)."""
    genes = []
    rows = []
    samples = None

    with open(filepath) as f:
        header = f.readline().strip().split("\t")
        samples = header[1:]  # first column is gene name

        for line in f:
            parts = line.strip().split("\t")
            gene = parts[0].split("|")[0].strip()  # handle "GENE|site" format
            if not gene:
                continue

            vals = []
            for v in parts[1:]:
                try:
                    vals.append(float(v))
                except (ValueError, IndexError):
                    vals.append(np.nan)

            genes.append(gene)
            rows.append(vals)

    if not rows:
        return [], [], np.array([])

    # Pad rows to same length
    max_len = max(len(r) for r in rows)
    for i, r in enumerate(rows):
        if len(r) < max_len:
            rows[i] = r + [np.nan] * (max_len - len(r))

    return genes, samples or [], np.array(rows)


def main():
    now = datetime.now(UTC).isoformat()
    db = sqlite3.connect(str(KG_PATH))
    db.execute("PRAGMA journal_mode=WAL")

    all_genes = set(r[0] for r in db.execute(
        "SELECT entity_id FROM entities WHERE entity_type = 'Gene'"
    ).fetchall())
    log.info("%d genes in KG", len(all_genes))

    total_claims = 0

    # ══════════════════════════════════════════════════════════════════
    # Step 1: Process PDC proteomics studies (proteome, phospho, acetyl, ubiquityl)
    # ══════════════════════════════════════════════════════════════════

    for study_dir in sorted(CPTAC_PDC.iterdir()):
        if not study_dir.is_dir():
            continue

        study_name = study_dir.name
        pdc_id = study_name.split("_")[0]
        cancer_type = _infer_cancer_type(study_name)

        for data_file, (claim_type, modality) in MODALITY_MAP.items():
            filepath = study_dir / data_file
            if not filepath.exists():
                continue

            log.info("Processing %s / %s (%s)...", pdc_id, modality, cancer_type)

            try:
                genes, samples, matrix = _parse_tsv_matrix(filepath)
            except Exception as e:
                log.warning("Failed to parse %s: %s", filepath, e)
                continue

            if matrix.size == 0 or len(genes) == 0:
                log.warning("  Empty matrix for %s", filepath)
                continue

            n_samples = matrix.shape[1] if matrix.ndim == 2 else 0
            n_claims_study = 0

            for i, gene in enumerate(genes):
                # For phospho/acetyl/ubiquityl: gene might be "GENE|SITE"
                gene_symbol = gene.split("|")[0].split(":")[0].strip()
                if gene_symbol not in all_genes:
                    continue

                row = matrix[i]
                valid = row[~np.isnan(row)]
                if len(valid) < 5:
                    continue

                mean_val = float(np.mean(valid))
                std_val = float(np.std(valid))
                cv = std_val / abs(mean_val) if abs(mean_val) > 0.01 else 0

                # Only create claims for genes with meaningful variance
                # (top quartile by CV or abs mean > 0.5)
                if cv < 0.3 and abs(mean_val) < 0.5:
                    continue

                # For phospho, include site info
                site_info = gene if "|" in gene or ":" in gene else ""

                claim_id = f"CPTAC-{modality[:5].upper()}-{gene_symbol}-{pdc_id}"
                if site_info:
                    site_hash = hash(site_info) % 10000
                    claim_id = f"CPTAC-{modality[:5].upper()}-{gene_symbol}-{pdc_id}-{site_hash}"

                direction = "high_abundance" if mean_val > 0 else "low_abundance"

                db.execute("""
                    INSERT OR IGNORE INTO claims
                    (claim_id, claim_type, status, proof_level, effect_size, direction,
                     n_studies, source_dataset, assay_type,
                     created_at, description, full_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    claim_id, claim_type, "observed", 2,
                    mean_val, direction, n_samples,
                    f"CPTAC_{pdc_id}", modality, now,
                    (f"{gene_symbol} {modality} in {cancer_type}: "
                     f"mean={mean_val:.3f}, std={std_val:.3f}, CV={cv:.2f} "
                     f"({len(valid)} samples)"
                     + (f" site={site_info}" if site_info else "")),
                    json.dumps({
                        "context_type": "in_vivo",
                        "cancer_type": cancer_type,
                        "pdc_study": pdc_id,
                        "modality": modality,
                        "mean": round(mean_val, 4),
                        "std": round(std_val, 4),
                        "cv": round(cv, 3),
                        "n_samples": len(valid),
                        "site": site_info or None,
                    }),
                ))
                db.execute(
                    "INSERT OR IGNORE INTO claim_participants VALUES (?, ?, ?, ?)",
                    (claim_id, gene_symbol, "effector_gene", json.dumps({})),
                )
                n_claims_study += 1

            if n_claims_study > 0:
                db.commit()
                log.info("  %s/%s: %d claims (%d genes, %d samples)",
                         pdc_id, modality, n_claims_study, len(genes), n_samples)
                total_claims += n_claims_study

    # ══════════════════════════════════════════════════════════════════
    # Step 2: Process CPTAC RNA-seq
    # ══════════════════════════════════════════════════════════════════

    log.info("\nStep 2: Processing CPTAC RNA-seq...")

    # Load Ensembl → gene symbol mapping
    gene_map_path = CPTAC_RNA / "ensembl_gene_map.tsv"
    ensembl_to_gene = {}
    if gene_map_path.exists():
        with open(gene_map_path) as f:
            reader = csv.reader(f, delimiter="\t")
            next(reader, None)  # skip header
            for row in reader:
                if len(row) >= 2:
                    ensembl_to_gene[row[0].split(".")[0]] = row[1]
        log.info("  Loaded %d Ensembl→gene mappings", len(ensembl_to_gene))

    for rna_file in sorted(CPTAC_RNA.glob("*_transcriptomics.txt.gz")):
        cancer_type = rna_file.stem.split("_")[0].upper()
        log.info("  Processing RNA-seq: %s (%s)...", rna_file.name, cancer_type)

        genes = []
        rows = []
        n_samples = 0

        try:
            with gzip.open(rna_file, "rt") as f:
                header = f.readline().strip().split("\t")
                n_samples = len(header) - 2  # skip transcript_id, gene_id

                for line in f:
                    parts = line.strip().split("\t")
                    if len(parts) < 3:
                        continue

                    gene_id = parts[1].split(".")[0]  # ENSG ID
                    gene_symbol = ensembl_to_gene.get(gene_id, "")
                    if not gene_symbol or gene_symbol not in all_genes:
                        continue

                    vals = []
                    for v in parts[2:]:
                        try:
                            vals.append(float(v))
                        except ValueError:
                            vals.append(np.nan)

                    genes.append(gene_symbol)
                    rows.append(vals)
        except Exception as e:
            log.warning("  Failed to read %s: %s", rna_file.name, e)
            continue

        if not rows:
            continue

        # Aggregate by gene (sum transcript TPMs)
        gene_expr = {}
        for gene, vals in zip(genes, rows):
            arr = np.array(vals)
            if gene in gene_expr:
                gene_expr[gene] = np.nansum([gene_expr[gene], arr], axis=0)
            else:
                gene_expr[gene] = arr

        n_claims_rna = 0
        for gene, expr in gene_expr.items():
            valid = expr[~np.isnan(expr)]
            if len(valid) < 5:
                continue

            mean_val = float(np.mean(valid))
            std_val = float(np.std(valid))

            # Only genes with meaningful expression and variance
            if mean_val < 0.5 and std_val < 0.5:
                continue

            cv = std_val / max(abs(mean_val), 0.01)
            if cv < 0.3 and mean_val < 1.0:
                continue

            claim_id = f"CPTAC-RNA-{gene}-{cancer_type}"
            db.execute("""
                INSERT OR IGNORE INTO claims
                (claim_id, claim_type, status, proof_level, effect_size, direction,
                 n_studies, source_dataset, assay_type,
                 created_at, description, full_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                claim_id, "DifferentialExpressionClaim", "observed", 2,
                mean_val, "expressed" if mean_val > 1 else "low_expression",
                len(valid), f"CPTAC_{cancer_type}", "RNA-seq", now,
                (f"{gene} RNA in {cancer_type}: mean_TPM={mean_val:.2f}, "
                 f"std={std_val:.2f}, CV={cv:.2f} ({len(valid)} tumors)"),
                json.dumps({
                    "context_type": "in_vivo",
                    "cancer_type": cancer_type,
                    "modality": "rnaseq",
                    "mean_tpm": round(mean_val, 3),
                    "std": round(std_val, 3),
                    "cv": round(cv, 3),
                    "n_samples": len(valid),
                }),
            ))
            db.execute(
                "INSERT OR IGNORE INTO claim_participants VALUES (?, ?, ?, ?)",
                (claim_id, gene, "effector_gene", json.dumps({})),
            )
            n_claims_rna += 1

        db.commit()
        log.info("  %s: %d RNA claims (%d genes, %d samples)",
                 cancer_type, n_claims_rna, len(gene_expr), n_samples)
        total_claims += n_claims_rna

    # ══════════════════════════════════════════════════════════════════
    # Summary
    # ══════════════════════════════════════════════════════════════════
    log.info("\n=== KG CLAIM SUMMARY ===")
    for ct, n in db.execute(
        "SELECT claim_type, COUNT(*) FROM claims GROUP BY claim_type ORDER BY COUNT(*) DESC"
    ).fetchall():
        log.info("  %s: %d", ct, n)
    log.info("Total: %d", db.execute("SELECT COUNT(*) FROM claims").fetchone()[0])
    log.info("CPTAC claims added this run: %d", total_claims)

    db.close()
    log.info("Done.")


if __name__ == "__main__":
    main()
