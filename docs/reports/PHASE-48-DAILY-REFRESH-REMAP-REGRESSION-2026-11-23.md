# Phase 48 follow-up — Daily Source Refresh remap regression

**Date:** 2026-11-23  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Baseline HEAD:** `0d0831f31c907f7b40f46132f856bc0e308d655c`  
**Status:** local regression fixed; next Daily Source Refresh CI required.

## Objective / baseline failure
The Daily Refresh workflow, including [run 45267081985](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45267081985), failed `tests.test_benchmark_reconcile.ReconcileTests.test_full_real_reconciliation_26_queries_148_preserved` because a historical expectation `remapped_source_id_count == 24` no longer describes the refreshed pinned catalog (now `26`). The failure reproduces locally as `AssertionError: 26 != 24`.

The benchmark comprises 26 queries, 148 judgments, and 72 distinct judged IDs. It is **provisional** and is not independent human gold.

## Root cause verified against tracked source snapshots
A read-only comparison of `2573bfd:registry/source-catalog.json` and the current tracked `registry/source-catalog.json` with the existing pinned crosswalk found precisely **two additional remaps**:
1. `coreyhaines31/marketingskills` / `skills/ai-seo/SKILL.md`: `GASL-SRC-11b781b5c13bd506fe18` -> `GASL-SRC-51d0d781134b1f43bc81`; Git Blob remained `2869ca89116540ad34437c90888a9322553dc69d`.
2. `coreyhaines31/marketingskills` / `skills/seo-audit/SKILL.md`: `GASL-SRC-91218ab531241df1d0a6` -> `GASL-SRC-e69f6e5eff3b644e6690`; Git Blob remained `1a4fd7536e099e24f841444f621497fc8fd1d768`.

In both cases the source commit changed from `5b2b400eec1e7e1cec76245a715d0b0d4fd2a9c1` to `8a0c22d677e6031e8a5dd4b554b6ce059b753ffe`. Repository, exact Skill path, and content Git Blob remained unchanged. Existing `reconcile` fail-closed checks still reject missing, changed, duplicated, ambiguous or hijacked identities.

## Smallest corrective change
Only `tests/test_benchmark_reconcile.py` is changed:
- Replace the stale absolute count `24` with an independently computed count from the **actual current Source IDs** and the historical Crosswalk IDs.
- Assert all **72** pinned historical identities are represented in the audit and all have a matching current repository/path/Git Blob.
- Explicitly assert **148** original grades remain unchanged after ID remapping.
- Keep the existing rejection of the vanished historical ID in derived results.

This prevents a normal pinned-commit refresh from breaking CI solely because its source IDs changed, while keeping identity/content and grade-integrity assertions strict.

## Tests and evidence
- Before: `python3 -m unittest tests.test_benchmark_reconcile.ReconcileTests.test_full_real_reconciliation_26_queries_148_preserved -v`: **FAIL**, `26 != 24`.
- After: `python3 -m unittest tests.test_benchmark_reconcile -v`: **12 tests OK**.
- After: `python3 -m unittest tests.test_search_benchmark tests.test_benchmark_reconcile -q`: **29 tests OK**.
- `git diff --check`: **passed**.

## Invariants and limitations
- No new benchmark label or independent relevance assessment has been created.
- No changes to `benchmarks/search-gold-v1.json`, `benchmarks/search-gold-v1-crosswalk.json`, `registry/source-catalog.json`, ranking logic, production Search API, source mirror or third-party content.
- This change is test maintenance for expected catalog refresh drift; it does not validate Skill behavior, license permission, or security approval.
- New refresh CI success must be observed before closing the regression. No human review or third-party Skill execution is authorized.
- Stage only this test and report (plus the Phase 54 acceptance report amendment); scan for secrets; no force-push or unrelated change.

## Full local regression confirmation
- `python3 -m pytest -q`: **792 passed, 27 skipped, 337 subtests passed**, 43.26 s. No failure.
- A dedicated lightweight `gasl-search-quality.yml` CI job is configured to run on changes to `tests/test_benchmark_reconcile.py`; this verifies the crosswalk and ranking comparison without triggering a 57-repository refresh. The scheduled Daily Refresh still needs its next independent run before it can be declared green.
