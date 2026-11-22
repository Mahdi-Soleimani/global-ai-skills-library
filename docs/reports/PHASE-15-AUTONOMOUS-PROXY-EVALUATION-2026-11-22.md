# Phase 15 — Autonomous Proxy Evaluation and Usable Router Decisions

**Date:** 2026-11-22  
**Status:** Functional local implementation completed; heuristic decisions are explicitly uncalibrated.  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Environment:** macOS, Python 3.13.9, local SQLite FTS5, no model API.  
**Commit/Push:** Not performed. Pre-existing local work remains untouched outside the explicitly listed files.

## 1. Objective and decision

Remove the mandatory two-human-review bottleneck for *practical use* of GASL. Keep the strict independent-human Gold Dataset path as an **optional future verification**, not an operational dependency. Deliver an end-to-end automated internal evaluation and a usable provisional Router policy while preserving truthful quality claims and install/execute security gates.

The output of this phase is an **internal weak-label benchmark**, **not** a frozen human Gold Dataset. A separate independent accuracy claim would still require independent labels; GASL itself no longer waits for them.

## 2. Evidence sources and scope

- Active Phase 11B source-pinned V2 manifest: 26 queries / 13 bilingual task pairs / 385 unique pair-level candidates.
- Each candidate is matched against `private/skill-metadata-cache.json` using its Source Record ID, exact commit and path.
- Source text is a cached **first 1,800 characters** of the pinned Skill content plus name and description. This may omit useful details deeper in a Skill.
- `registry/source-catalog.json`: immutable Source ID/provenance verification.
- Search index: existing SQLite FTS5 and the unchanged retrieval engine.
- The earlier 10 simulated personas are internal stress cases; no independent reviewers or human authenticity are claimed.

## 3. Automated rubric evaluation

Added `tools/auto_review.py` with **13 task-specific independent-of-rank** concept rubrics. Each rubric specifies required core concepts and extra helpful capabilities (OAuth+PKCE, PostgreSQL+EXPLAIN+indexes, RAG/PDF/chunking, agent eval, native Android/SMS/BroadcastReceiver, Playwright, Kubernetes/Helm, ETL quality, prompt injection, WCAG/design system, SaaS unit economics, literature review, API technical documentation).

Two deterministic variants score every candidate on the same cached content:

- Regular: more permissive grade-2/3 cutoff.
- Strict: more conservative grade-2/3 cutoff.
- Recorded consensus proxy grade: the **minimum** of both scores, not a human adjudication.
- Original A/B human sheets remain blank, unmodified and available for optional later external validation.
- Provider-side Twilio webhook SMS does not pass the native Android `BroadcastReceiver` core requirement.
- A candidate scoring 0/1 from this rubric is an **automated proxy**; a relevant Skill can be missed due to truncated text or rigid vocabulary.

### Actual run results

| Metric | Result |
|---|---:|
| Candidate rows assessed | 385 |
| Unique task pairs | 13 |
| English/Persian queries assessed | 26 |
| Grade-0 candidates | 98 |
| Grade-1 candidates | 211 |
| Grade-2 candidates | 41 |
| Grade-3 candidates | 35 |
| Differences between regular/strict variants | 32 |
| Queries with grade-2/3 matches in pool (proxy) | 22 |
| Queries with no grade-2/3 proxy match (uncertain gap) | 4 |

The 22/4 split does **not** imply 22 verified answerable and 4 verified unanswerable queries. The four gaps remain uncertain rather than being mislabeled as catalog-wide absence.

### Retrieval metrics over *proxy-answerable* queries only

| Metric | Value |
|---|---:|
| Precision@5 | 0.4182 |
| Recall@5 | 0.3985 |
| MRR@10 | 0.7830 |
| NDCG@5 | 0.6046 |
| Queries included | 22 |

The metrics measure agreement with **internal cached-text proxy judgments**, not external performance. The same text contributes to both retrieval and proxy judgment, so this evaluation is **not statistically independent**. Unjudged sources are treated as non-relevant in the proxy benchmark.

Raw detailed evaluation (Git-ignored): `private/benchmark-review/AUTOMATED-PROXY-EVALUATION-V1.json`.
SHA-256 of private raw evaluation: `66113350723da43520ce2bbaa51071d48a2d449c7c38be16bb825275cc3e1809`.
Public-safe 26-query summary: `docs/reports/PHASE-15-PROXY-QUERY-RESULTS-2026-11-22.json` (explicitly labeled provisional).

## 4. Operational Router policy

Added `tools/answerability_policy.py`, version `0.2.0-experimental`, policy status `experimental_heuristic_not_calibrated`.

The Router now emits three operational decisions automatically:

- `recommend`: high lexical query coverage and no missing exact technical identifiers in the leading candidate pool. This is **only a candidate to inspect**.
- `abstain`: no eligible candidates; very low query coverage; or missing important exact technical identifiers in the leading candidates. This means **no confident retrieved match**, **not** proof of no matching Skill anywhere in the catalog.
- `undetermined`: partial or ambiguous evidence; results can still be inspected.

This is a rule-based **heuristic**, not a calibrated probability model. Its thresholds are provisional and were not optimized using the same proxy labels. The `answerability` object declares `prediction_basis`, `policy_status`, reason code, matched/unmatched technical identifiers, and `abstain_means` to keep clients from overstating evidence.

### End-to-end examples

- `WordPress plugin development`: `recommend`, with `provisional_candidate_to_inspect` status.
- `Implement OAuth 2.1 authorization-code flow with PKCE`: `recommend` (SaaS is a generic business context, not an indispensable exact technical identifier).
- `Android Kotlin BroadcastReceiver banking SMS transactions`: `abstain`, because `BroadcastReceiver` is missing from the leading candidate evidence. No catalog-wide absence is claimed.
- A generic low-evidence query may return `undetermined`, preserving candidate discovery.

Security status, license evidence, source pins, compatibility, installation approval, and execution permissions remain **separate** and unchanged. No Skill is installed or run by the Router.

## 5. CLI, MCP, API and health

- `./gasl auto-review`: run automated V2 proxy assessment and write local ignored JSON.
- `./gasl route --task '...' --json`: return the provisional decision with reasons.
- CLI human output explains the experimental status and unmatched technical identifiers.
- MCP `gasl_route_task` and REST `/v1/route` reuse the same Router code and decision contract.
- MCP instructions explicitly say `recommend` is not quality/security approval and `abstain` is not corpus absence.
- `/health`: displays `experimental_heuristic_not_calibrated`, policy version and `answerability_decisions_calibrated: false`.

The automatic evaluation is **optional** and requires the local, ignored enrichment cache and review manifest. Normal search/routing remains usable on a clean clone without those development artifacts, without requiring paid APIs, new Python packages, or human review.

## 6. Test results

- Full Python unit/integration suite, `ResourceWarning` promoted to error: **203 tests passed**, 0 failures and 0 errors (6.19 s).
- New `test_answerability_policy.py`: 7 tests passed.
- New `test_auto_review.py`: 5 tests passed.
- `compileall -q tools tests`: PASS.
- Live CLI smoke: WordPress `recommend`, Android `abstain`; no installation was performed.
- Existing CLI/REST/MCP, source provenance, no-execution/no-install, and benchmark compatibility tests pass.

## 7. Reproducibility and limitations

- Automated proxy labels are **not** independent or authoritative Gold labels.
- The two scoring variants use the same inputs, so their agreement is not inter-rater reliability.
- The heuristic may yield false positives or abstain on useful Skills; `decision` is an advisory routing signal only.
- Exact historical Phase 11B taxonomy bytes are absent from the active workspace; the manifest's original Taxonomy hash remains recorded and was not rewritten.
- No new independent answerability dataset or formal calibrated abstention threshold is claimed.
- The proxy evaluation is local and is not copied to public Git. Aggregate results, implementation and caveats are recorded in this report.

## 8. Files changed in this phase

- `tools/answerability_policy.py` — new experimental decision policy.
- `tools/auto_review.py` — new automated rubric evaluator.
- `tools/skill_router.py` — policy integration and machine-readable evidence.
- `tools/gasl.py` — auto-review CLI and human-readable route output.
- `tools/mcp_server.py` — revised downstream consumer guidance.
- `tests/test_answerability_policy.py` — new policy tests.
- `tests/test_auto_review.py` — new automated-rubric tests.
- `tests/test_skill_router.py`, `tests/test_api_server.py`, `tests/test_mcp_server.py`, `tests/test_gasl_service.py` — updated integration contracts.
- `README.md` and `docs/ROADMAP.md` — document practical automated workflow.
- `docs/reports/PHASE-13-ROUTER-ANSWERABILITY-GATE-2026-11-22.md` and `docs/reports/PHASE-14-HUMAN-REVIEW-INTAKE-2026-11-22.md` — historical supersession notices.
- `docs/reports/PHASE-15-AUTONOMOUS-PROXY-EVALUATION-2026-11-22.md` — this report.
- `docs/reports/PHASE-15-PROXY-QUERY-RESULTS-2026-11-22.json` — per-query public-safe summary.
- `private/benchmark-review/AUTOMATED-PROXY-EVALUATION-V1.json` — raw local evaluation (ignored).

## 9. Acceptance and handoff

**PASS — Working autonomous evaluation and experimental routing are complete**: no human reviewers, model API, Docker, paid service, Skill execution or manual grading is needed to obtain provisional decisions and an internal regression baseline.

**Not claimed**: external accuracy certification, Gold Dataset status, exhaustive absence proof, or production-calibrated confidence. The old A/B human packets may be archived; they are not blockers for this working system.

Next work is ordinary product improvement (search relevancy/coverage, optional user feedback and deployment), not a mandatory human-review gate.
