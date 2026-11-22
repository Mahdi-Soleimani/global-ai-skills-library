> **Subsequent implementation (2026-11-22):** Phase 15 introduced an operational autonomous proxy evaluation and an explicitly experimental Router recommend/abstain/undetermined heuristic. The human-review workflow described below is optional for independent quality claims, not a prerequisite for using the Router. See `PHASE-15-AUTONOMOUS-PROXY-EVALUATION-2026-11-22.md`. This report remains a historical record of its phase.

# Phase 13 — Router Answerability Gate

**Date:** 2026-11-22  
**Status:** Implemented locally; tests and CLI smoke checks passed. Calibrated `recommend` / `abstain` decisions remain intentionally disabled.  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Branch:** `main`  
**Commit / Push:** Not performed.

## 1. Objective

Make the Router's uncertainty explicit across CLI, shared service, REST API and MCP. Prevent downstream Agents or users from interpreting a ranked candidate list as an approved recommendation or an empty result set as proof that no relevant Skill exists.

This is a fail-closed contract change, not an answerability model and not a calibrated abstention implementation.

## 2. Router response contract

`route_task()` preserves the existing ranking, source evidence, candidate-level security decisions, installation restrictions and execution restrictions. It adds:

- `routing_decision: undetermined`;
- `recommendation_status: candidate_discovery_only`;
- `answerability.decision: undetermined`;
- `answerability.policy_status: not_calibrated`;
- `answerability.policy_version: 0.1.0`;
- `answerability.reason_code: independent_human_answerability_labels_pending`;
- candidate pool, eligible and returned candidate counts;
- `empty_results_prove_no_relevant_skill: false`;
- `human_review_required: true`;
- an explicit list of the decision vocabulary and the only decision currently emitted (`undetermined`).

The answerability decision is separate from each candidate's existing `decision` field. Candidate-level values such as `security_screen_required` and `manual_security_review_required` remain security/install lifecycle gates; they are not answerability predictions.

## 3. Safety semantics

- A high lexical relevance score does not authorize `recommend`.
- Zero results do not authorize `abstain` and do not prove corpus-wide absence.
- `recommend` and `abstain` are not emitted while the answerability policy is `not_calibrated`.
- Candidate discovery remains available so users can inspect source IDs, descriptions, provenance, license and security evidence.
- No Skill is installed or executed.
- No arbitrary score threshold, confidence value or hidden heuristic was introduced.

## 4. Surface integration

- CLI human-readable route output prints `Answerability: UNDETERMINED (not_calibrated)` and labels results as discovery leads.
- CLI JSON preserves the existing response and adds the answerability fields.
- REST `/v1/route` and MCP `gasl_route_task` inherit the shared response contract without duplicating ranking logic.
- MCP server instructions and tool description explicitly warn Agents not to treat ranked results as approved recommendations or an empty list as proof of absence.
- `/health` exposes answerability policy status/version and `answerability_decisions_calibrated: false`.
- README and roadmap document the current behavior and the human-label gate.

## 5. Android banking-SMS smoke test

Input: native Android Kotlin `BroadcastReceiver` for incoming banking SMS, with sender/body parsing and explicit exclusion of Twilio and per-bank parsers.

Observed route response:

- `routing_decision = undetermined`;
- `recommendation_status = candidate_discovery_only`;
- `retrieved_candidate_pool_size = 100` (the search result pool is capped at 100; this is not the full catalog);
- `eligible_candidate_count = 100`;
- `returned_candidate_count = 5`;
- `empty_results_prove_no_relevant_skill = false`.

The leading candidates were `zoom-virtual-agent-android`, `expo-brownfield`, and `expo-migrate-module`. They are adjacent Android/React Native integration Skills, not direct Android banking-SMS receiver implementations. The Router now explicitly communicates that these are discovery leads, not recommendations. This run does not establish that no suitable Skill exists in the full catalog.

## 6. Tests and validation

- Full Python test suite: **182 tests passed**, 0 failures, 0 errors (5.92 seconds) with `ResourceWarning` promoted to errors.
- `compileall` for `tools/` and `tests/`: passed.
- `git diff --check`: passed; only pre-existing CRLF-to-LF advisory messages were printed for CSV files.
- Router regression tests verify both populated and empty candidate sets remain `undetermined` until calibration.
- Shared service and health tests verify the policy status is exposed accurately.
- MCP and REST integration tests verify the new fields propagate to connected clients.
- CLI JSON smoke test parsed successfully and returned `undetermined` / `candidate_discovery_only`.
- CLI text smoke test visibly printed `Answerability: UNDETERMINED (not_calibrated)`.
- Existing security, provenance, source ordering, strict Agent compatibility, and no-install/no-execute tests passed.

The full test suite passes with `ResourceWarning` promoted to errors; no unclosed-SQLite-database warning remains. Root cause: SQLite's connection context manager commits/rolls back but does not close the connection. The three read-only connections in `ensure_index()`, `get_skill_by_id()` and `search_skills()` now use `contextlib.closing`; the index-builder already closes its write connection in `finally`. A regression test runs the read-only paths with `ResourceWarning` treated as an error and passes.

## 7. Files changed in this phase

- `tools/skill_router.py`
- `tools/gasl_service.py`
- `tools/skill_search.py`
- `tools/gasl.py`
- `tools/mcp_server.py`
- `tests/test_skill_router.py`
- `tests/test_skill_search.py`
- `tests/test_gasl_service.py`
- `tests/test_mcp_server.py`
- `tests/test_api_server.py`
- `README.md`
- `docs/ROADMAP.md`
- `docs/reports/PHASE-13-ROUTER-ANSWERABILITY-GATE-2026-11-22.md`
- `docs/reports/PHASE-13-ROUTER-ANSWERABILITY-GATE-2026-11-22-SHA256SUMS.txt`

No catalog records, source IDs, ranking formulas, taxonomy terms, Skill contents or candidate order were intentionally changed in this phase.

## 8. Remaining gates

1. Collect the completed independent reviews for the two existing Phase 11B reviewer packets and their answerability forms.
2. Validate reviewer independence, source pins, pair-language consistency, out-of-pool additions and full-catalog evidence for any `unanswerable` label.
3. Freeze adjudicated answerability and relevance data; retain `uncertain` where evidence is insufficient.
4. Build a calibration/holdout split and evaluate risk-versus-coverage trade-offs. Do not choose a threshold from the Android example or the ten simulated personas.
5. Only after calibration and holdout validation, enable a versioned policy that may emit `recommend` or `abstain`; otherwise keep `undetermined`.
6. Keep the SQLite connection-close regression test in CI; the previously observed read-connection leak is fixed.

## 9. Acceptance decision

**PASS:** The Router, CLI, REST, MCP and health surfaces now communicate uncertainty consistently and fail closed. Existing candidate ranking and security gates are preserved. Read-only SQLite connections are explicitly closed and covered by a strict ResourceWarning regression test.

**NOT PASSED / intentionally pending:** Calibrated answerability, production `recommend` / `abstain` decisions, and the independent-human benchmark gate. No claim of corpus-wide absence is made for Android banking SMS.
