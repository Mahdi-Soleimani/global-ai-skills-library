# Phase 8 — Search Feature Coverage Completion

**Date:** 2026-11-22  
**Status:** Completed with one policy-based size exclusion  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Branch / base HEAD:** `main` / `7e616c0f5a8b6ba906bea59a0ade3fc163d9e418`

## 1. Goal and scope

Complete incremental Search Feature extraction for the Public, Commit-pinned Source Catalog without storing Skill bodies, changing source records, weakening integrity checks, or executing third-party content.

## 2. Baseline

- Public eligible universe reported by the feature runner: **4,405** records with `snapshot_status=verified_commit_pinned` and a Git Blob SHA.
- Existing Feature Index: **1,282** verified records.
- Existing Failure Ledger: **9** records.
- Taxonomy vocabulary: **236** terms.
- Vocabulary SHA-256: `4036e0e13fced0b2820aa13fbd8b367a48ffed3ea172ec104fa3f335afc05ef9`.
- Working Tree at start: 24 tracked files modified, 49 untracked, zero staged. HEAD and `origin/main` matched.
- No Git reset, clean, checkout, stage, commit, push, or destructive operation was performed.
- The four archived research originals (`EN-675`, `FA-234`, `AUX-FA-750PLUS`, `AUX-FA-438`) were re-hashed at final verification; all four SHA-256 values matched the handoff manifest exactly.

## 3. Execution

Commands were run serially; one Feature Worker process at a time. Batch size was capped at 500 and worker count at 4. The final retry used 2 workers. The implementation retained its repository round-robin ordering, unattempted-first policy, 25-request atomic checkpoints, Commit/Blob verification, and failure ledger.

| Run | Attempted | Newly verified | Failed attempts |
|---|---:|---:|---:|
| 1 | 200 | 200 | 0 |
| 2 | 500 | 495 | 5 |
| 3 | 500 | 490 | 10 |
| 4 | 500 | 491 | 9 |
| 5 | 500 | 496 | 4 |
| 6 | 500 | 497 | 3 |
| 7 | 454 | 448 | 6 |
| 8 (retry) | 6 | 5 | 1 |
| **Total** | **3,160** | **3,122** | **38** |

The 454-record run included the 414 still-unattempted records and retried the 40 records accumulated in the Failure Ledger. Across the run, 40 distinct Source IDs entered the ledger; 39 were subsequently recovered. Transient `URLError` and `RemoteDisconnected` failures were cleared by retries.

## 4. Final Feature Index

- Eligible Public, Commit-pinned records: **4,405**.
- Verified Feature records: **4,404**.
- Coverage: **99.9773%** (4,404 / 4,405).
- Remaining Failure Ledger entries: **1**.
- Feature schema: `1.1.0`.
- Source scope: `verified_pinned_frontmatter_vocabulary_only`.
- Feature Index size: **2,159,498 bytes**.
- Feature Index SHA-256: `f4a9ad2ea88e6a0912f7f6ab3ad747abfd778f20e7ac4cc1ec149850bfff8727`.

### Sole remaining record

- Source ID: `GASL-SRC-496a3feefdf82dd567ff`
- Repository: `github/awesome-copilot`
- Path: `skills/quality-playbook/SKILL.md`
- Commit: `f10fdb8b2660ce85c98f220b2f1ca24653768a5c`
- Git Blob SHA: `3f0901f3670a03cdbc30f745d22a09ce35e7b548`
- The direct, read-only fetch confirmed the reason as `SKILL.md exceeds byte limit`. The pipeline now raises the dedicated `FeatureSizeLimitError` for this policy exclusion.
- The enforced limit is `MAX_SKILL_BYTES = 256 * 1024`.

This record remains excluded. The size limit was not raised, integrity checks were not bypassed, and the record was not deleted. Its ledger attempts count remains 3. A follow-up run after the pipeline fix returned `attempted=0`, `permanent_exclusions=1`, `verified_records=4404`, and `remaining=1`; therefore the deterministic size exclusion will not be downloaded again on subsequent runs with the same Source pin and taxonomy. The current result is **99.9773% coverage**, not 100%.

## 5. Search index and benchmark

The local FTS5 index was rebuilt after Feature extraction:

- Command: `./gasl index --check`
- Index schema: `1.2.1`
- Indexed local Source Records: **4,429** (the local/historical universe; not the 4,405 Public Feature denominator).
- Smoke query results: **3**.

A post-coverage regression run was saved to:

`docs/reports/SEARCH-BENCHMARK-POST-FEATURE-COVERAGE-2026-11-22.json`

- Status: `provisional`
- Queries: **26**
- Judgments: **148**
- Precision@5: **0.4692**
- Recall@5: **0.6266**
- MRR@10: **0.9551**
- NDCG@5: **0.7102**

Language averages:

| Language | Precision@5 | Recall@5 | MRR@10 | NDCG@5 |
|---|---:|---:|---:|---:|
| English | 0.4615 | 0.6529 | 0.9103 | 0.6968 |
| Persian | 0.4769 | 0.6004 | 1.0000 | 0.7236 |

This is the existing internal development set, not an independent or blind benchmark. Its dataset SHA-256 is `c0adb1f411797db9c189db6e65a2697b672d427f75cd023ba77d5b2180eb39f4`. The Source Catalog and ranking-code hashes differ from the 2026-11-20 benchmark snapshot; therefore the metric change must not be attributed to Feature coverage alone or treated as a direct apples-to-apples comparison. No public quality claim is justified.

Benchmark output SHA-256 after the final pipeline update: `2ae32c0016a3dd6f9b76b0129dcda0ca202e5c0842ad3625f8520ce96339ca23`.

## 6. Validation

- Before data refresh: `python3 -m pytest -q` — **152 passed, 6 subtests passed**.
- After Feature refresh, targeted search tests: `python3 -m pytest -q tests/test_search_features.py tests/test_skill_search.py` — **30 passed**.
- After adding the permanent-exclusion regression test: `python3 -m pytest -q tests/test_search_features.py` — **6 passed**.
- Final full suite after the pipeline fix and index rebuild: `python3 -m pytest -q` — **153 passed, 6 subtests passed**.
- `./gasl index --check` — successful; 3 smoke-query results.
- `git diff --check` — successful; only existing CRLF-to-LF warnings for three CSV files.

## 7. Files and side effects

- Updated derived data: `registry/search-features.json` (was already untracked at baseline); the exact size-limited failure is now typed as `FeatureSizeLimitError`.
- Updated `tools/search_features.py` to keep deterministic size exclusions in the Failure Ledger but remove them from future retry queues.
- Added a regression test in `tests/test_search_features.py` proving the oversized record is attempted once and then retained without repeated fetches.
- Rebuilt local derived SQLite index: `registry/gasl-search.sqlite3` (ignored by Git).
- Added benchmark output: `docs/reports/SEARCH-BENCHMARK-POST-FEATURE-COVERAGE-2026-11-22.json`.
- This report: `docs/reports/PHASE-8-SEARCH-FEATURE-COVERAGE-2026-11-22.md`.
- `docs/ROADMAP.md` receives a narrowly scoped status update.
- No Source Catalog, original research dataset, taxonomy, ranking code, or Skill package was modified in this phase.
- No Skill script was installed or executed. No model, embedding dependency, paid API, server, or Docker requirement was added.
- No Commit or Push was made.

## 8. Acceptance and remaining work

**Accepted:** Feature extraction is complete for all records that pass the existing 256 KiB limit and exact Commit/Blob integrity checks. The single oversized record remains explicitly accounted for.

**Still open:**
1. Build a new frozen bilingual benchmark with independently authored/reviewed judgments; keep the current 26-query set as a development regression set.
2. Evaluate ranking changes only on the independent set; do not tune weights to the existing provisional set.
3. Continue Full-corpus Vector Retrieval research separately from the current lexical + Feature Index.
4. Continue the outstanding Security Manual Reviews and source/research reconciliation as separate workstreams.
