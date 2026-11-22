# Phase 18 — Security Triage and Sandbox Readiness Gate

**Date:** 2026-11-22  
**Project:** GASL — Global AI Skills Library  
**Scope:** Explain the eight Phase-17 static warnings, distinguish informational test-only signals, and add a non-executing, fail-closed isolation-readiness check.  
**Behavioral execution:** Not performed. No third-party scripts, tests, installers, or Skill instructions ran.

## 1. Starting point

Phase 17 audited 38 downloaded packages still matching the current pinned source catalog: 30 packages had no obvious static signals and eight required further inspection. All 38 passed integrity checks; all remained unapproved for install/execute. Raw findings remain in the ignored local `reports/security/on-demand/` directory.

The static scanner previously set `manual_review_required` whenever it found any heuristic finding, even if the finding's severity was explicitly `info` because it came from a test harness. This conservatism caused one misleading actionable review status for the already manually inspected Cloudflare `security-audit` package.

## 2. Source-oriented review of all eight flagged packages

Source code was inspected at the **exact flagged locations in the locally stored pinned package**, without executing any of it. This is contextual static triage, **not** a complete behavioral audit or proof of safety.

| Skill (pinned package) | Phase 17 signals | Context and triage conclusion | Remaining action |
|---|---|---|---|
| `claude-api` | 9 (one high-confidence heuristic) | Two `.ssh/` mentions occur in comments describing defensive symlink handling; `drop_block_probe.py:406-435` reads `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`, puts the credential in an HTTP **header**, serializes the request body separately, and sends a POST to a configurable `base_url`. The high-confidence `SECRET_TO_HTTP_BODY` regex spans adjacent header/body code rather than showing direct body exfiltration. Still, a configurable destination combined with real credential headers is a meaningful network/secret boundary risk. | **Keep manual review required.** Forbid network and production credentials in any future sandbox; investigate endpoint allowlisting and redirect policy before approval. |
| `docx` | 5 | `accept_changes.py` and `soffice.py` invoke subprocesses; `soffice.py` also copies process environment into its LibreOffice invocation. These operations are consistent with document conversion but carry subprocess/environment propagation risks. | **Keep manual review required** until command targets, inputs and environment are restricted and tested. |
| `pptx` | 4 | The LibreOffice wrapper copies environment and spawns a process; thumbnail generation uses subprocesses. | **Keep manual review required** until restricted resource/filesystem/process testing is available. |
| `skill-creator` | 5 | The tooling launches Claude as a subprocess and copies most environment variables while excluding `CLAUDECODE`. Passing a largely inherited environment to a model-capable child process is not automatically safe. | **Keep manual review required**; isolate environment, credentials, child processes and network before use. |
| `web-artifacts-builder` | 3 | `bundle-artifact.sh` and `init-artifact.sh` install npm/pnpm dependencies, including a possible global `npm install -g pnpm`. These commands change the filesystem and may access registries. | **Keep manual review required**; no installer may run on the host, and package installation must not run in a network-denied sandbox without explicit, separate policy. |
| `webapp-testing` | 2 | The `with_server.py` helper starts/stops subprocesses for application/server testing. | **Keep manual review required**; child-process and network isolation must be verified. |
| `xlsx` | 5 | Recalculation uses subprocesses; the LibreOffice helper copies the environment. | **Keep manual review required**; apply the same process and environment controls as for `docx`/`pptx`. |
| `security-audit` | 12 **informational only** | All 12 spawn-call findings come from `validate-coverage-ledger.test.cjs` and `validate-findings.test.cjs` and are explicitly tagged `test_harness_context=true` with severity `info`. This agrees with the prior manual source review in `PHASE-2-CLOUDFLARE-SECURITY-REVIEW-2026-11-20.md`; no tests were executed. | Reclassify *static triage* to `no_obvious_static_flags_not_approved`; keep 12 informational findings in the evidence and **retain installation/execution prohibition**. |

These conclusions **do not** make the seven remaining packages malicious, nor do they assert that the Cloudflare Skill is safe to run. Each finding is only a reason to constrain or test behavior before future deployment.

## 3. Scanner correction

Modified `tools/static_scan.py` to distinguish:

- `finding_count`: every preserved signal, including info-level test harness occurrences;
- `actionable_finding_count`: non-informational findings that require deeper review;
- `informational_finding_count`: informational signals that remain visible but do not alone trigger `manual_review_required`.

`integrity_failed` retains absolute precedence. A verified package with no actionable findings is labeled `no_obvious_static_flags_not_approved` — **never approved** for installation or execution.

`tools/security_gate.py` now returns the separate counts in its CLI result. No finding is deleted or hidden.

## 4. Verified offline batch results (same 38-package cohort)

| Metric | Phase 18 result |
|---|---:|
| Packages re-audited | 38 |
| Passed full local hash and pinned main `SKILL.md` Git Blob verification | 38 |
| No actionable static findings, still **not approved** | 31 |
| Retained `manual_review_required` due to actionable findings | 7 |
| Actionable heuristic finding instances | 33 |
| Informational test-only instances | 12 |
| High-confidence heuristic signals | 1 (Claude API header/body adjacency; see above) |
| Integrity failures | 0 |
| Installed, executed or dynamically validated third-party Skills | 0 |

The unchanged Phase-17 result (30/8) is kept as historical evidence; this 31/7 result reflects the corrected actionable-vs-informational rubric. The exact private summary is `reports/security/on-demand/PHASE18-REVIEW-COHORT-2026-11-22.json` and per-package raw evidence remains Git-ignored.

The 25 older package identities not matching the **current** source catalog were not silently re-pinned, copied, or included in the 38-package current-pin validation cohort.

## 5. Sandbox readiness is fail-closed

Added `tools/sandbox_gate.py` and a read-only CLI diagnostic:

```bash
./gasl sandbox
```

This command **never runs or pulls containers or any third-party code**. It checks only Docker CLI/Daemon availability and returns the isolation requirements as a machine-readable JSON object. The status is **always blocked for execution**, even if a Docker daemon responds, until separate isolation canaries and policy enforcement are implemented and tested. The host `sandbox-exec` command is not accepted as a proven containment boundary just because it exists.

Real macOS development environment findings:

- Docker CLI: available (`/usr/local/bin/docker`).
- Docker daemon: **unreachable** (Docker socket absent); no container was launched.
- Isolation canary verification: **not performed**.
- `sandbox_execution_enabled`, `installation_allowed`, and `third_party_code_executed`: all **false**.
- Reason code: `docker_daemon_unreachable`.

The missing enforcement gates include: immutable local image digest (no image pull), network denied and canary-tested, empty credential environment, no host home/Docker socket mounts, read-only root/input, unprivileged UID, dropped capabilities, strict CPU/RAM/PID/scratch/wall-time limits, symlink/escape canaries and explicit per-Skill consent with cleanup.

**Availability ≠ safety:** merely starting Docker is not enough to declare an OS-enforced sandbox secure. GASL must not attempt to execute untrusted Skills on the host as a fallback.

## 6. Tests / acceptance

- Added `tests/test_sandbox_gate.py`: **five** synthetic/fake-Docker tests validating fail-closed client-missing/daemon-missing/timeout/daemon-present cases and non-execution behavior.
- Added `tests/test_security_gate.py` info-only fixture test: informational findings stay visible while `manual_review_required` is no longer incorrectly applied; no install/execute approval follows.
- Full Python regression suite: **223 tests and 6 subtests passed**, zero failures.
- `python3 -m compileall -q tools tests`: pass.
- Offline re-audit of 38 pinned packages: complete, 0 integrity failures, 0 package executions.

**Acceptance: PASS** for improved static triage and a truthful machine-readable readiness gate. **Not complete:** a canary-verified sandbox runner, any dynamic execution, approval lifecycle, or selective Agent installation/uninstallation. These remain future phases requiring a real isolated runtime and explicit authorization.
