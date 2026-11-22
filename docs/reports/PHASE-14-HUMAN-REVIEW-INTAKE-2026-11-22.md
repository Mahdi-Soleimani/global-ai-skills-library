> **Subsequent implementation (2026-11-22):** Phase 15 introduced an operational autonomous proxy evaluation and an explicitly experimental Router recommend/abstain/undetermined heuristic. The human-review workflow described below is optional for independent quality claims, not a prerequisite for using the Router. See `PHASE-15-AUTONOMOUS-PROXY-EVALUATION-2026-11-22.md`. This report remains a historical record of its phase.

# Phase 14 — Independent Human Review Intake Hardening

**Date:** 2026-11-22  
**Status:** Implemented locally; packet audit PASS with one documented taxonomy-drift warning. Human reviews have not started.  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Branch:** `main`  
**Commit / Push:** Not performed.

## 1. Objective

Harden the Phase 11B independent reviewer workflow before distribution. The goal is to make the human-review evidence auditable and machine-checkable without generating or inferring any human labels.

This phase does not grade Skills, adjudicate query answerability, freeze qrels, or tune Router thresholds.

## 2. Baseline audit

The active V2 workspace contained:

- 26 bilingual queries across 13 English/Persian task pairs;
- 385 pair-level Source ID candidates per reviewer;
- 13 answerability rows per reviewer;
- 385 candidate-level adjudication rows;
- separate blind Reviewer A and Reviewer B ZIPs;
- no relevance grades and no answerability labels entered.

The original candidate pools and source IDs were retained. The active Source Catalog contains 4,429 records; the manifest's Source Catalog SHA-256 and record count match the current catalog. Candidate source IDs resolve to the current Source Catalog and their repository/path/commit/Git-Blob pins validate.

The original reviewer packets did not contain an explicit `out_of_pool_reviewed` field, separate `search_formulations` and `search_method` fields, or an independent-human attestation. The previous answerability sheet therefore could not capture every evidence item required by schema 1.1.0.

## 3. Intake V2 artifacts

New versioned files were created so earlier packet files remain intact for traceability. Only files carrying `INTAKE-V2` are current:

- `private/benchmark-review/SEARCH-GOLD-V2-REVIEWER-A-PACKET-INTAKE-V2.zip`
- `private/benchmark-review/SEARCH-GOLD-V2-REVIEWER-B-PACKET-INTAKE-V2.zip`
- `SEARCH-GOLD-V2-REVIEWER-A-INTAKE-V2.csv` / `...-B-INTAKE-V2.csv` — 385 candidate rows each.
- `SEARCH-GOLD-V2-ANSWERABILITY-REVIEWER-A-INTAKE-V2.csv` / `...-B-INTAKE-V2.csv` — 13 query-pair rows each.
- `SEARCH-GOLD-V2-REVIEWER-A-ATTESTATION-INTAKE-V2.csv` / `...-B-ATTESTATION-INTAKE-V2.csv` — one-row attestation forms.
- `SEARCH-GOLD-V2-ADJUDICATION-TEMPLATE-INTAKE-V2.csv` — candidate-level adjudication.
- `SEARCH-GOLD-V2-ANSWERABILITY-ADJUDICATION-TEMPLATE-INTAKE-V2.csv` — query-level answerability adjudication.

The new ZIPs contain only the assigned reviewer's candidate sheet, answerability sheet, reviewer-specific instructions, and attestation form. The other reviewer, hidden manifest, Android coverage audit, and adjudication templates are excluded. ZIP member bytes are checked against the corresponding local files.

The previous `...-PACKET.zip` files without `INTAKE-V2` are superseded and must not be distributed.

## 4. Answerability evidence contract

The new answerability sheets explicitly separate:

- `full_catalog_reviewed` — yes/no;
- `out_of_pool_reviewed` — yes/no;
- `search_formulations` — at least two distinct formulations for any no-relevant claim, separated by semicolons;
- `search_method` — how the catalog and pinned bodies were searched;
- `rationale` — why the selected status follows from the evidence.

Status semantics are now operationally aligned with the relevance rubric:

- `direct_match_found`: at least one grade-3 direct match, listed in `direct_match_source_ids`;
- `partial_match_only`: no grade-3 direct match, but at least one grade-2 useful/actionable Skill, listed in `partial_match_source_ids`;
- `no_relevant_skill_found`: no grade-2/3 candidate after documented full-catalog and out-of-pool review;
- `uncertain`: evidence is insufficient for the other statuses.

A no-relevant label is rejected unless both catalog and out-of-pool review are explicitly `yes`, at least two distinct search formulations exist, and search method and rationale are supplied. A grade-2/3 candidate conflicts with a no-relevant label.

## 5. Independent-human attestation

Each reviewer must return a separate one-row attestation with:

- a unique pseudonymous reviewer ID (no legal name or contact details required);
- `reviewer_type=independent_human`;
- an explicit independence confirmation;
- confirmation they did not see the other reviewer's material or the private manifest/audit;
- confirmation that model-generated grades/rationales were not used;
- conflict-of-interest declaration;
- UTC completion timestamp and attestation text.

Reviewer A and Reviewer B IDs must differ. The 10 model-simulated Phase 12 personas do not satisfy this gate.

## 6. Intake validator

Added `tools/benchmark_review.py` with two commands:

### `audit`

Checks:

- manifest candidate/pair counts and per-pair pool sizes;
- current Source Catalog record count and SHA-256;
- Source ID and immutable source-pin integrity in both candidate sheets;
- identical A/B candidate sets and task/source metadata;
- independently randomized A/B row ordering;
- absence of retrieval ranks/scores and pool-origin fields in reviewer sheets;
- answerability row counts and candidate counts;
- exact reviewer-specific ZIP entries, CRC integrity, and ZIP/local-file byte equality;
- exclusion of private review data from public Git.

### `validate`

Checks completed returns for:

- grades 0–3, rationales for grades 1–3, and `content_checked=yes/no`;
- answerability statuses and source-ID references;
- direct/partial/no-relevant consistency with candidate grades;
- full-catalog and out-of-pool evidence for no-relevant labels;
- unique independent-human reviewer IDs and valid attestations;
- reviewer candidate-set parity and language-specific exceptions.

Exit code `2` means the packets are incomplete; exit code `1` means validation failed. A passing validation does not itself freeze the Gold Dataset.

When a reviewer adds a relevant out-of-pool source, `validate --create-addenda` creates a grade-free, reviewer-specific addendum for the other reviewer. It deliberately omits the discovering reviewer's grade, rationale, and identity. The recipient must append and independently grade the row before the two candidate sets can pass parity validation.

## 7. Taxonomy fingerprint drift

The preflight found:

- V2 manifest taxonomy SHA-256 at packet creation: `3c16e787ccc6ad0f481f69e3683330801d9ba745578ca9476d26c6f37116174f`;
- current taxonomy SHA-256: `6058ff0193d5c44b12d346c008eb1e3a4a61d2225d1aa5797cf218507d16cd18`.

Phase 12 RUN-01 through RUN-03 retain the earlier hash; later Phase 12 runs record the newer taxonomy. The current taxonomy file is timestamped after the V2 query manifest. The exact historical taxonomy bytes are not present in the active workspace.

This is recorded as a reproducibility warning, not silently repaired. The manifest was not rewritten, candidate pools were not rebuilt, and the Source Catalog fingerprint still matches. Human reviewers assess the exact source-pinned candidates already in their sheets; the taxonomy mismatch does not change those pinned Skill bodies. Exact reproduction of the original retrieval/pool-generation process remains limited until the historical taxonomy bytes can be recovered.

## 8. Tests and validation

- New `tests/test_benchmark_review.py`: **9 tests passed**.
- Full Python suite with `ResourceWarning` promoted to errors: **191 tests passed**, 0 failures/errors (5.95 seconds).
- `compileall` for `tools/` and `tests/`: passed.
- `git diff --check`: passed; only existing CRLF-to-LF advisory messages for three CSV files were emitted.
- Tests cover prepared packet audit, incomplete review state, successful independent review validation, full-catalog/out-of-pool no-answer requirements, distinct reviewer IDs, source-pin mismatch, blinded addenda without grade leakage, and language-specific exception gating.
- Actual workspace preflight: **PASS**, 0 errors, 1 documented taxonomy-drift warning.
- Strict returned-review validation on the currently blank sheets: **INCOMPLETE** (exit code 2), 0 validation errors, 814 expected incomplete fields (770 grades, 26 answerability statuses, 18 attestation fields).
- Current candidate sheets: 385 rows each; answerability sheets: 13 rows each; 0 grades and 0 answerability labels entered.
- Both intake-v2 ZIPs: integrity PASS; exact expected contents; no reviewer cross-leakage; member bytes match local files.
- Source Catalog fingerprint: PASS; all candidate Source IDs and source pins validate.
- `private/` remains excluded by `.gitignore`.
- Current reviewer packet and intake artifact hashes are recorded in `docs/reports/PHASE-14-HUMAN-REVIEW-INTAKE-2026-11-22-SHA256SUMS.txt`.

## 9. Non-actions and safety

- No relevance grade, answerability label, reviewer identity, or adjudication result was generated.
- No candidate pool was rebuilt or re-ranked.
- The historical manifest and older packet artifacts were not overwritten.
- No source catalog, taxonomy, ranking formula, or Skill content was changed by this phase.
- No Skill was installed or executed.
- No commit, push, staging, or production deployment was performed.

## 10. Next gate

1. Distribute only the A intake-v2 ZIP to Reviewer A and only the B intake-v2 ZIP to Reviewer B.
2. Receive both candidate sheets, answerability sheets, and attestations separately.
3. Run `python3 tools/benchmark_review.py validate`.
4. If candidate sets differ because of out-of-pool discoveries, run `python3 tools/benchmark_review.py validate --create-addenda`, send each blinded addendum to its intended reviewer, and revalidate after return.
5. Resolve grade and answerability disagreements using the separate adjudication templates.
6. Freeze qrels and schema 1.1.0 answerability only after reviewer IDs, evidence, source pins, language equivalence, and adjudication are complete.
7. Only then run independent benchmark metrics and begin any calibration/holdout work.

**Acceptance:** Intake preparation and machine validation are complete. Human review, adjudication, Gold Dataset freeze, and calibrated Router decisions remain pending.
