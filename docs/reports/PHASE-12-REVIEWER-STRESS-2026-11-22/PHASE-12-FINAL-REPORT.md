# Phase 12 — Ten-Persona Adversarial Stress Review

**Date:** 2026-11-22  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Worktree:** local only; no commit or push  
**Status:** 10-run internal stress review complete; independent human benchmark gate remains open.

> Important: the ten reviewers are ten domain-specific model-simulated personas executed by one model. They are not ten independent human reviewers or ten separately authenticated model agents. This work is a repeatable adversarial internal review, not a replacement for the independent human relevance/answerability review specified in Phase 11B.

## 1. Scope and workload

| Item | Count |
|---|---:|
| Domain-specific reviewer personas | 10 |
| Scenarios per round | 50 |
| Recorded rounds | 10 |
| Search/evaluation executions | 500 |
| Positive scenarios with expected families | 35 |
| Negative-constraint scenarios with expected families | 3 |
| Total expected-family cases | 38 |
| Exploratory coverage probes | 12 |
| Explicit exclusion cases | 5 |

Each reviewer has a distinct domain, adversarial pressure profile, and five scenarios. Scenarios include high, very-high, and extreme complexity, with one Persian-language scenario per reviewer. All retrieval was local; no Skill was installed or executed.

## 2. Final comparable results

| Metric | Baseline (mean RUN 01–03) | Final (RUN 09–10) |
|---|---:|---:|
| All expected-family hit@5 | 35/38 (92.11%) | 38/38 (100.00%) |
| Positive-scenario hit@5 | 33/35 (94.29%) | 35/35 (100.00%) |
| Negative-constraint expected hit@5 | 2/3 (66.67%) | 3/3 (100.00%) |
| Explicit exclusion violations | 5/5 | 0/5 |
| Top-5 source-pin integrity | 100% | 100% |
| Android direct-SMS candidate in Top 10 | 0 | 0 |
| Explicit router abstention | Not supported | Not supported |
| Average search latency | 154.2 ms | 214.1 ms |
| Average p95 search latency | 221.7 ms | 249.7 ms |

Baseline and final values are regraded against the same v1.2.0 expected-family rubric. The original v1.0 raw score is not used for before/after comparison because expected-family labels were corrected after inspecting actual candidate Skill bodies. This rubric correction is not counted as a search-engine improvement.

## 3. Ten-run execution matrix

| Run | Engine state | Expected hit@5 | Exclusion violations | Top-10 repeatability vs previous |
|---:|---|---:|---:|---:|
| 01 | Baseline engine | 35/38 | 5/5 | — |
| 02 | Baseline engine | 35/38 | 5/5 | 50/50 |
| 03 | Baseline engine | 35/38 | 5/5 | 50/50 |
| 04 | First remediation | 38/38 | 0/5 | 39/50 |
| 05 | First remediation | 38/38 | 0/5 | 50/50 |
| 06 | First remediation | 38/38 | 0/5 | 50/50 |
| 07 | First remediation | 38/38 | 0/5 | 50/50 |
| 08 | First remediation | 38/38 | 0/5 | 50/50 |
| 09 | Final taxonomy/rubric snapshot | 38/38 | 0/5 | 48/50 |
| 10 | Final taxonomy/rubric snapshot | 38/38 | 0/5 | 50/50 |

Runs 1–3 establish baseline repeatability. Run 4 records the first remediation impact; runs 5–8 reproduce the same Top-10 order across all 50 scenarios. Run 9 records the taxonomy/rubric update impact (48/50 unchanged); run 10 reproduces all 50 Top-10 orders exactly.

## 4. Reviewer verdicts

| Reviewer | Domain persona | Expected hit@5 | Verdict |
|---|---|---:|---|
| R01 | Red-Team Security Architect | 4/4 | PASS_WITH_COVERAGE_LIMIT |
| R02 | Principal Data Platform Engineer | 4/4 | PASS_WITH_COVERAGE_LIMIT |
| R03 | RAG and Agent Reliability Lead | 4/4 | PASS_WITH_COVERAGE_LIMIT |
| R04 | Android and Backend Principal Engineer | 2/2 | CRITICAL_COVERAGE_GAP |
| R05 | Automation SRE and Workflow Architect | 4/4 | PASS_WITH_COVERAGE_LIMIT |
| R06 | Cloud Platform and FinOps Engineer | 4/4 | PASS_WITH_COVERAGE_LIMIT |
| R07 | RTL Product Designer and Accessibility Auditor | 4/4 | PASS_WITH_COVERAGE_LIMIT |
| R08 | B2B SaaS CFO and Growth Strategist | 4/4 | PASS_WITH_COVERAGE_LIMIT |
| R09 | Systematic Review Methodologist and Educator | 4/4 | PASS_WITH_COVERAGE_LIMIT |
| R10 | Developer Documentation and Localization Editor | 4/4 | PASS_WITH_COVERAGE_LIMIT |

Per-reviewer details, baseline comparison, five scenario results and domain-specific adjudication are in `REVIEWERS/R01.md` through `REVIEWERS/R10.md`.

## 5. Remediation performed

1. Added conservative extraction of named technology/provider exclusions from English and Persian negative clauses. Explicitly excluded providers are removed from positive query terms and candidates containing the excluded entity are filtered from results. This corrected Pinecone/Databricks, AWS-only/Azure, Apple HIG and Twilio constraints in the test set.
2. Added punctuation-tolerant phrase matching and fixed phrase-overlap handling so multiword concepts survive punctuation and shared tokens.
3. Expanded Persian-to-English domain terminology for PostgreSQL query optimization, composite indexes, partitioning, incremental ETL, data quality, systematic reviews, WCAG, screen readers, focus, and form labels.
4. Added common Persian function-word stopwords without removing domain-bearing words such as `داده` and `کیفیت`.
5. Corrected the DES-04 expected-family rubric after inspecting pinned candidate bodies. `accessibility-and-inclusive-visualization` and `design-qa` are direct matches for the compound dashboard/WCAG task; `a11y-audit` remains a related specialist candidate but is not in the Top 5 for that compound query.
6. Added regression tests for negative constraints, Persian negation, phrase expansions, stopwords, and reviewer-suite rubric integrity.
7. Implemented answerability-aware benchmark dataset schema `1.1.0` while preserving legacy `1.0.0`: empty qrels are accepted only for final independent-human no-answer adjudication with full-catalog and out-of-pool evidence. Added separate no-answer precision/recall, false-abstention, answerable-coverage and decision-coverage metrics. The runner never infers abstention from ranking scores.

## 6. Coverage gaps and unresolved risks

### Critical: Android banking SMS

- DEV-01 and DEV-04 still return adjacent Skills such as Expo/Kotlin/MCP server generators, not a direct Android `BroadcastReceiver` / `SMS_RECEIVED` implementation.
- No direct Android SMS candidate was found in Top 10 in any recorded final run.
- The separate Phase 11B audit inspected all 12 Android/SMS-related metadata matches from the current pinned corpus; all 12 Git Blobs were verified and none contained direct Android SMS receiver implementation terms.
- The router has no explicit abstention prediction. It can return unrelated candidates even when no direct Skill exists.
- Do not label the query as a final `no_relevant_skill_found` gold qrel yet: the 4,404 feature-bearing Skills were not exhaustively fetched and reviewed.

### Other exploratory coverage probes

The 12 probe reviews cover secure boot/side channels, proprietary CNC telemetry, multimodal codecs, Android SMS, compiler backends, legacy banking desktop automation, air-gapped Kubernetes, braille/haptic interfaces, regulated microtransactions, zero-study meta-analysis and undocumented binary protocols. Eight are partial matches, two have no direct match in the reviewed top-three candidates, and two remain uncertain. These are provisional top-three body reviews, not full-catalog absence proofs.

### Latency trade-off

Average observed search latency increased from approximately 154.2 ms to 214.1 ms across the measured runs. Average p95 changed from 221.7 ms to 249.7 ms. This remains a local benchmark observation; no latency SLA was specified. Profile before attempting optimization.

### Reviewer independence

The original Phase 11B independent human review requirement remains open. This ten-persona suite does not grade the 385-row V2 candidate pools and answerability sheets as ten independent reviewers. If the goal is gold qrels, the candidate pool still needs independently completed review packets and adjudication.

### Answerability-aware benchmark compatibility

- Legacy benchmark `1.0.0`: 26 queries / 148 judgments executed successfully. Provisional averages: Precision@5 0.4692, Recall@5 0.6266, MRR@10 0.9551, NDCG@5 0.7102. These are internal regression metrics, not independent quality claims.
- Schema `1.1.0`: synthetic smoke fixture exercised answerable, unanswerable and uncertain paths; its perfect sample prediction metrics are test-only and are not evidence of real router performance.
- The router still has no calibrated abstention decision; this change prepares the benchmark and enforces gold-label safeguards without changing production routing.

## 7. Validation

- Full Python test suite: **178 tests passed**, 0 failures, 0 errors (5.98 seconds).
- `compileall` for `tools/` and `tests/`: passed.
- Artifact validation: 10/10 run pairs, 10/10 reviewer reports, 12/12 coverage probes and 36/36 pinned candidate bodies Git-Blob verified.
- SHA-256 manifest generated for the report bundle.
- Answerability benchmark tests: **17 passed**, including legacy compatibility, empty-qrels safeguards, human-review gates and explicit decision metrics.
- Python emitted non-fatal `ResourceWarning` messages for SQLite connections during the full test run; test exit code remained 0 and all 178 tests passed.
- Ten JSON and ten Markdown run artifacts are present; each run executes 50 scenarios.
- Top-5 source pin integrity is 100% in every recorded run.
- Router domain-filter checks: 3/3; install/execute safety: 3/3; filter invariants: 4/4; invalid-query rejection: 3/3.
- No Skill was installed or executed by this test harness.
- No commit, push, staging or production deployment was performed.

## 8. Artifact index

- `RUNS-INDEX.md` — index of all 10 run pairs.
- `RUN-01.json` … `RUN-10.json` and matching `.md` — complete execution records.
- `REVIEWERS/R01.md` … `REVIEWERS/R10.md` — individual persona adjudications.
- `BASELINE/RE-GRADE-ALL-RUNS-V1.2.json` — all runs regraded using the same current rubric.
- `COVERAGE-PROBE-ADJUDICATION.json` and `.md` — pinned-body review of 12 coverage probes.
- `ANSWERABILITY-SCHEMA-1.1-IMPLEMENTATION.md` — schema contract, adjudication gates and metric semantics.
- `SEARCH-BENCHMARK-LEGACY-COMPATIBILITY.json` — actual legacy v1.0 benchmark compatibility run (provisional labels).
- `BASELINE/manifest.json` — preserved original baseline artifacts and caveats.
- `SHA256SUMS.txt` — checksums for every report and run artifact.

## 9. Next work

1. Complete independent human review of answerability and relevance labels; the 10 simulated personas cannot satisfy this gate.
2. Connect an explicit, calibrated router abstention decision to schema `1.1.0` after collecting enough reviewed answerable and unanswerable queries.
3. Expand or acquire directly relevant Android device-side SMS Skills, with exact pinned-source evidence.
4. Complete independent review of the V2 candidate and answerability packets; preserve the 10-persona suite as a separate adversarial regression test.
5. Profile the observed latency increase before any optimization.
