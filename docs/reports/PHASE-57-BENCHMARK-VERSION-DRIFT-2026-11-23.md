# Phase 57 — Benchmark source-version drift and rejudgment gating

**Date:** 2026-11-23  
**Baseline:** `efcb4f4dd66e4096de6bc3c02732faae9d6a8e8c` on `main`.  
**Status:** Implemented; local regression and live-catalog audit passed. CI acceptance pending.

## Objective and prior failure
The historical bilingual benchmark contains 26 queries, 148 provisional judgments and 72 unique judged source IDs. Refresh commit `461d9c2` replaced the pinned content of `coreyhaines31/marketingskills/skills/seo-audit/SKILL.md`. The strict Phase 48 evaluator correctly refused to relabel a different Git Blob, but stopped at the first failing identity. Dedicated Search Quality run [45282313905](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45282313905) therefore failed before producing ranking metrics. A successful software CI run must never imply that current-catalog search quality was independently evaluated.

## Implementation by file
- `tools/benchmark_reconcile.py`: shared `inspect_crosswalk()` classifies every historical pinned identity. It preserves repository, path, old commit/blob, candidate current IDs/commits/blobs and per-query blocked counts. Only an exact unique same-blob match may be eligible. Missing path or changed blob requires rejudgment. Ambiguous matches, reused/hijacked historical IDs, invalid current pins and many-to-one identities are integrity blocks; every participant in a many-to-one collision is blocked. Malformed maps or duplicate source IDs still raise hard errors.
- Strict `reconcile()` uses this same inspector and raises on **any** blocked identity before generating derived judgments; no partial ranking metrics are computed. The original report schema and successful same-blob behavior remain compatible with the existing ranking lab.
- New CLI option `--audit-report` produces a deterministic JSON identity audit without executing ranking. It records SHA-256 of input dataset/catalog snapshots and the canonical crosswalk. Expected content drift exits zero with an explicit `rejudgment_required` state; identity-integrity blocks write the audit and exit 2. Audit cannot overwrite input files or be combined with `--write-map`. Output is atomically replaced via a unique temporary file.
- `.github/workflows/gasl-search-quality.yml`: audit first, verify coverage arithmetic, publish a step summary and emit an explicit warning on drift. **Both** strict benchmark and ablation steps run only when all identities are eligible. Identity-integrity failures fail the job, not skip quality checks. Manual catalog changes are now included in the trigger.
- `.github/workflows/gasl-refresh.yml`: audit the newly generated catalog before metadata publication, including automatic bot-produced refreshes that do not trigger another Actions workflow. Expected content drift is reported without blocking metadata discovery; integrity failures block publication. No label or ranking update is made.
- `tests/test_benchmark_reconcile.py`: five new tests cover eligible/blocked counts, missing and ambiguous candidates, simultaneous integrity failures, many-to-one collisions, audit CLI output, input immutability, exit codes and strict metric refusal.
- `README.md`: documents audit usage, states and limitations.

## State machine
| Evaluation status | Meaning | Metrics | Audit exit |
| --- | --- | --- | --- |
| ready_provisional | Every historical ID uniquely resolves to exact pinned content | Existing strict provisional evaluation permitted | 0 |
| rejudgment_required | At least one changed blob or missing path, no integrity conflict | ALL aggregate metrics blocked | 0 (explicit warning/status) |
| integrity_blocked | Ambiguous/invalid identity or pin | ALL aggregate metrics blocked | 2 |

Malformed inputs are fatal, not converted into ordinary content drift. No new grade, zero-grade replacement, partial evaluation denominator, independent adjudication or ranker selection is introduced.

## Verified current-catalog audit at baseline
Command: `python3 tools/benchmark_reconcile.py --map benchmarks/search-gold-v1-crosswalk.json --audit-report /tmp/gasl-benchmark-drift.json`.

- 26 queries; 72 historical identities; 148 original judgments.
- **71** same-blob eligible identities, **146** eligible judgments.
- **1** blocked identity, **2** blocked judgments, **2** affected queries.
- State: `rejudgment_required`, `ranking_metrics_allowed=false`.
- Historical ID: `GASL-SRC-91218ab531241df1d0a6`; historical blob `1a4fd7536e099e24f841444f621497fc8fd1d768`; historical commit `5b2b400eec1e7e1cec76245a715d0b0d4fd2a9c1`.
- Current candidate: `GASL-SRC-26492c8e53144afa4be6`; current blob `8e969c81b41f5ebc820de2ecd51a7c8ab85847c0`; commit `8fd2fcade2fd6629026e9dfe6d133b55b36968b9`.
- `seo-en`: 3 of 4 judgments eligible; `seo-fa`: 5 of 6 eligible. No grades were copied to the changed candidate.
- Strict `--report` returned nonzero with the original Git Blob error and produced no metrics file.
- SHA-256 of all three original files remained byte-for-byte unchanged:
  - Dataset: `c0adb1f411797db9c189db6e65a2697b672d427f75cd023ba77d5b2180eb39f4`.
  - Crosswalk file: `f5989f2623b30e6ed35f5da46d788339278ec8bf204393478944ab38a521b3ff`.
  - Catalog: `ec99d29878a435acdd4f4257a1339ac556342a29f66be2f2cefb36854517883a`.

## Verification and limitations
- Dedicated reconciliation/ranking/benchmark suite: **40 passed**.
- Local complete pytest: **803 passed, 28 skipped, 337 subtests passed** (41.13s).
- YAML and embedded Python syntax checks, compilation and Git diff whitespace checks: passed.
- CI acceptance requires the dedicated quality workflow to report rejudgment status and skip the two actual metric steps, without treating those steps as successful quality evaluation. Daily refresh must run its new audit, with separate evidence for any metadata publication. Cross-platform CI must retain the Phase 56 explicit Windows legacy-module boundary.
- Original dataset remains provisional. Git Blob equality is local identity evidence, not independent relevance, source authenticity, legal approval or permission to install/execute.
- No human relevance review, actual Agent installation, third-party execution, production ranker change, system clock change, Windows scope gate change or public release.

## Remaining
Actual current-catalog quality measurement remains blocked until changed labels undergo real review under a newly pinned benchmark/version. No automatic rewriting of the historical crosswalk or grades. Safe native parity/retirement of 13 legacy POSIX modules remains a separate Phase 56 outstanding issue.

## Verified final Phase 57 CI evidence
- Tested commit `a04818138a4e0965a0f4a8efc23b29d04d2f9221`.
- [Quality CI 45286223706](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45286223706): SUCCESS, 40 tests passed; 146 same-blob eligible and two blocked historical judgments; both ranking metric steps SKIPPED by the explicit rejudgment gate.
- [Daily Refresh 45286223626](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45286223626): SUCCESS, including the new post-refresh identity audit (`rejudgment_required`, two blocked labels), smoke tests and metadata-only publication. Bot commit `31f8c4a` was synchronized with a fast-forward.
- [Cross-platform CI 45286223385](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45286223385): all jobs SUCCESS; Ubuntu/macOS each 803 passed, 28 skipped; Windows platform-eligible 585 passed, six skipped. Thirteen legacy module exclusions remain at this revision.
- **Phase 57 automated acceptance achieved.** Ranking metrics for the refreshed catalog remain unavailable until review; no grade, ranker, policy or user-scope approval was changed.
