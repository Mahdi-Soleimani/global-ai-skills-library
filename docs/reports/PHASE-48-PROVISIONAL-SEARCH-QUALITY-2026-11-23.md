# Phase 48 — Search quality: pinned-identity benchmark recovery and provisional ranking experiments

**Date:** 2026-11-23  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Starting branch:** `main` at `5c12cde` (Phase 47)  
**Scope:** Local search-quality measurement, preservation of original judgments, controlled A/B experiments. **No production ranking update.**

## 1. Problem found by real baseline execution

The existing `benchmarks/search-gold-v1.json` is a **26-query / 148-judgment provisional internal dataset**, not an independently human-adjudicated search benchmark. Directly running `python3 tools/search_benchmark.py` against the current 4,431-record source catalog **failed** because some historical `source_record_id` values are missing.

Audit against the exact, locally available old catalog at Git revision `7e616c0f5a8b6ba906bea59a0ade3fc163d9e418` revealed:

- **72** distinct source IDs in the historical judgments.
- **48** IDs still exist; **24** changed when upstream pinned Commits advanced.
- **All 24** missing IDs had a single current match under the same `repository/source_path`, **with the same non-empty 40-hex Git Blob SHA** as the historical Skill file. Their upstream Commit SHA changed, but the recorded file blob did not.
- Some unrelated public source records have duplicate repository/path across distinct pinned Commit snapshots. The crosswalk explicitly allows those irrelevant rows, but rejects *ambiguous matches for any judged Skill*.

This is an exact local source-identity reconciliation, **not** a new human judgment and **not** an independent verification of the publisher's identity. An absent path, changed/missing blob, duplicate matching current records, hijacked reused ID or missing historical evidence causes a hard failure requiring rejudgment. Original benchmark records, upstream source catalog, raw research datasets and historical snapshots were **not modified**.

## 2. Reproducible, pin-bound recovery

New CLI helper: `tools/benchmark_reconcile.py`.

```bash
# Derive a complete, reviewer-auditable old-ID → current-ID mapping from local Git history.
python3 tools/benchmark_reconcile.py \
  --historical-revision 7e616c0f5a8b6ba906bea59a0ade3fc163d9e418 \
  --write-map benchmarks/search-gold-v1-crosswalk.json \
  --report docs/reports/PHASE-48-RECONCILED-PROVISIONAL-BASELINE-2026-11-23.json

# Repeat the provisional baseline without requiring old Git history in a shallow checkout.
python3 tools/benchmark_reconcile.py \
  --map benchmarks/search-gold-v1-crosswalk.json \
  --report /tmp/gasl-provisional-baseline.json
```

The crosswalk contains **all 72** old source identities with their original Commit, repository, Skill path and Git Blob SHA. The CLI uses a local `git show` of an **exact full revision**, never a web fetch, and stores output separately. During replay it checks **every** current source identity against the pinned stored blob, and remaps only the 24 changed IDs. The original source grades are preserved exactly. It emits `provisional_crosswalk_not_independent_gold`, never `verified` or `human_gold`.

Provenance hashes at baseline:

| Input | SHA-256 |
|---|---|
| Original provisional benchmark | `c0adb1f411797db9c189db6e65a2697b672d427f75cd023ba77d5b2180eb39f4` |
| Committed crosswalk | `f5989f2623b30e6ed35f5da46d788339278ec8bf204393478944ab38a521b3ff` |
| Current source-catalog snapshot | `0e1ff9acb938431bdddfb9a365e46a3464339f13538420ca8413185e999add8d` |

The catalog changes over time; if the Blob changes in future refreshes, replay **must refuse** instead of transferring an old grade to new content.

## 3. Measured provisional Baseline

**Same current catalog, same existing search index and policy, remapped judgments, k=5 and MRR@10.**

| Metric | Current production ranker |
|---|---:|
| Precision@5 | **0.4385** |
| Recall@5 (known judged relevant only) | **0.5818** |
| MRR@10 | **0.8987** |
| NDCG@5 | **0.6577** |

Language slices:

| Language | P@5 | Recall@5 | MRR@10 | NDCG@5 |
|---|---:|---:|---:|---:|
| English, 13 questions | 0.4308 | 0.5920 | 0.8590 | 0.6399 |
| Persian, 13 questions | 0.4462 | 0.5715 | 0.9385 | 0.6756 |

Hardest development-set examples include `github-actions-fa` (NDCG 0.0755), `data-viz-en` (0.2633), `github-actions-en` (0.3873), and `fastapi-en` (0.4080). These are diagnostics to investigate, **not** claims about user-wide performance.

The 2026-11-22 historical number (NDCG@5 0.7102) is **not comparable directly** because the catalog, ranker, metadata index, and source pins changed; this report does **not** attribute any apparent change to a single cause.

**Critical label gap:** across the current development queries, only **50% of top-five search results have any relevance judgment**. The current benchmark treats unjudged records as zero, a known source of bias. No full-catalog no-answer Gold or independent blind adjudication exists.

## 4. Controlled, same-pool ranking experiments

New `tools/search_ranking_lab.py` reranks **only the exact same top-10 candidates already returned by production**. It runs with no new network, model, or embedding dependency and does **not modify** `tools/skill_search.py`, Router production rank or Agent behavior.

```bash
python3 tools/search_ranking_lab.py \
  --output docs/reports/PHASE-48-PROVISIONAL-RANKING-ABLATION-2026-11-23.json
```

| Development-only variant | P@5 | Recall@5 | MRR@10 | NDCG@5 |
|---|---:|---:|---:|---:|
| **Production baseline** | 0.4385 | 0.5818 | 0.8987 | 0.6577 |
| Relevance score before coverage | 0.4692 | 0.6209 | 0.9263 | 0.6770 |
| Core fields before feature terms | 0.4231 | 0.5623 | 0.8987 | 0.6325 |
| Named technology/entity first | 0.4308 | 0.5754 | 0.9179 | 0.6652 |

For the `score_first` variant, NDCG was higher on **7** development queries, lower on **3**, and unchanged on **16**. The apparent gain of **+0.0193 NDCG@5** may reflect incomplete/biased judgments. The evaluation tool explicitly reports `ranker_winner_selected=false` and `production_ranker_changed=false`.

**Decision:** **Do not ship an experimental ranker based only on an already-seen provisional dataset.** Improvement must first hold on an independently graded and frozen bilingual test set (including out-of-pool negatives and answerability).

## 5. Automated reproducibility and regression gates

New, lightweight workflow: `.github/workflows/gasl-search-quality.yml`.

- Validates fixed historical-pinned mapping and fail-closed behavior with synthetic tests.
- Replays the current **26-query / 148-judgment** provisional baseline against the current catalog and index.
- Runs all four variants against identical candidates and requires the baseline row to match the independent baseline execution exactly.
- Ensures the report remains marked provisional, **no ranker is promoted**, and no “independent Gold” or validated no-answer status is invented.
- Records file/source digests and checks a clean working tree.
- Requires no external model/API subscription and no third-party Skill execution.
- The source-refresh CI excludes changes limited to the new evaluation-only tools, preventing unnecessary catalog refreshes on later benchmark experiments.

## 6. Test and security boundaries

Unit tests cover immutable input labels, exact 40-char source identities, remapped/unremapped grades, mismatched blobs/paths, ambiguous duplicate paths, reused source-ID hijacking, malformed crosswalks, refusal to upgrade provisional labels, CLI recovery using a shallow history and ranking-ablation isolation.

No new or existing third-party Skill was installed, executed, approved, or imported. No customer/Agent profiles changed. Only ignored local SQLite search-index derivations and explicitly named output reports were generated. Publisher attribution, license terms and Skill security are **not** newly authenticated by this offline benchmark.

## 7. Next acceptance gate: independent Gold

A genuine optimization phase requires **at least two independent human reviewers** for the pre-specified bilingual query set, documented search formulations and out-of-pool candidate review, adjudicated relevance grades, frozen source pins and query samples, and explicit no-answer labels only after full-catalog review. Separate discovery/tuning and untouched holdout queries before adopting new default scoring. Until then the current production ranking and the explicit "experimental" UI qualification remain unchanged.

## 8. Final local and GitHub verification

Local test counts, workflow Run IDs and final Commit SHA are appended only after live verification.
