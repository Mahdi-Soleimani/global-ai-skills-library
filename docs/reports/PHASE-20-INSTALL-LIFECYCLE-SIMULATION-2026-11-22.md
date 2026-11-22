# Phase 20 — Version-pinned installation preview and simulated lifecycle

**Date:** 2026-11-22  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Branch:** `main`  
**Status:** Implemented and locally tested, **without enabling Skill installation, execution or host modification**.

## 1. Goal, architectural scope and safety boundary

Following the 18/18 benign isolation canary success in Phase 19, create a **safe, testable installation lifecycle** *before* any host-specific Agent installer exists. The simulated workflow must preserve an exact source pin, display license and security evidence, distinguish claimed from verified Agent compatibility, require an explicit simulation acknowledgement, record reversible events and safely reject conflicts/tampering.

**Non-goals:** installing or executing third-party Skill code; writing into Codex, Cursor, Claude Desktop or other host configuration paths; assuming a clean static scan is a real security approval; enabling dynamic Skill execution after a benign Canary test; distributing third-party packages to GitHub.

## 2. Changes made

- `tools/install_lifecycle.py`: deterministic **read-only** `plan_install(...)`, fail-closed offline package inspection, `simulate(...)` and `simulation_status(...)` with transactional private SQLite ledger.
- `tools/static_scan.py`: `scan_package(..., persist=False)` performs the same static scan but does not rewrite the local `source.json`; original behavior (`persist=True`) for explicit security audits remains unchanged.
- `tools/gasl.py`: CLI commands `install-plan`, `install-simulate`, `install-status`; existing CLI/MCP/REST search/routing behavior untouched.
- `tests/test_install_lifecycle.py`: 22 new test cases for pinned version, source identity, package integrity, missing content, tampering, unknown/declared Agent compatibility, unknown license, explicit simulation acknowledgement, duplicate apply/rollback, concurrent operations, symlinked ledger rejection, event hash chain, historical simulated rollback and zero host modification.
- `README.md` and `docs/ROADMAP.md`: describe correct use and sharply distinguish simulated state from real installation.

### New CLI preview

```bash
./gasl install-plan --id GASL-SRC-ce593c8b9b3fd34f44d6 --agent codex --scope project
```

`plan_id = SHA-256(canonical JSON of source ID, repo/path, commit, pinned SKILL.md Git Blob, Agent and scope)`. This binds the plan to an **immutable source version** and specific logical target. Accepted logical Agent labels: `codex`, `cursor`, `claude-desktop`, `generic-mcp`. Accepted scopes: `user`, `project`.

The planner rechecks downloaded local package inventory and the original immutable Git Blob of `SKILL.md` **without writing package metadata**. It detects missing/unlisted files and actionable static findings. If the package is absent, identity/unpinned, or tampered, the plan remains incomplete or is rejected; it will never imply installation permission. The plan reports host compatibility as `not_declared`, `declared_match_unverified` or `declared_nonmatching_unverified`: an upstream string match never proves the Host actually accepts a Skill.

Even when source integrity is valid and no actionable static signal is found, every plan includes `actual_install_enabled=false`, `installation_allowed=false`, `installed=false`, `executed=false`, `destination_modified=false`. Conceptual backup/restore steps are shown **but not performed**.

### Simulation-only state machine

```bash
./gasl install-simulate --action apply \
  --id GASL-SRC-ce593c8b9b3fd34f44d6 --agent codex --scope project \
  --plan-id PLAN_SHA256 --acknowledge-plan-id PLAN_SHA256
./gasl install-status --plan-id PLAN_SHA256
./gasl install-simulate --action rollback \
  --plan-id PLAN_SHA256 --acknowledge-plan-id PLAN_SHA256
```

An `apply` event requires **exact ID acknowledgement** and a newly checked, locally downloaded package with full pinned integrity and **zero actionable static findings**. This is an **approval to simulate** the transition only, never permission to install. A plan with no declared compatibility or uncertain license can still demonstrate this *non-executing* simulation, but must retain all real-install warnings.

A `rollback` event requires a previously `simulated_active` plan and the same explicit plan ID. It can be recorded after a source catalog refresh, so an older simulated event is not stranded by a new source pin. It **only records a simulated reversal**, never removes or restores actual files.

- Transactional SQLite, `BEGIN IMMEDIATE`, and a strictly private ignored file `private/install-simulation/events.sqlite3` (created only on simulation).
- Event sequence + previous-event SHA-256 + canonical payload SHA-256 detect accidental/simple tampering and inconsistent histories. A local administrator who can change both data and hashes can still forge this ledger; it is **not a digitally signed audit log**.
- History validation fails closed on wrong schema, invalid states, duplicate active installs, double rollback or hash-chain mismatch.
- Logical target is a label such as `preview:codex:project`, **not a guessed real host directory**.
- No code path reads actual Agent configuration or modifies any Host files; there is no Skill execution, container launch, package installation, process hook or real backup creation.

## 3. Real local end-to-end smoke test

Selected current pinned local package: `academy-guide`, Source ID `GASL-SRC-ce593c8b9b3fd34f44d6`; Codex / project logical scope.

| Check | Observed result |
|---|---|
| Plan ID | `f52f11b345714191c780bd63b6e18e1d05a9f2ed3257c3b791a9e2fa00e45fcb` |
| Original pinned package inspection | `downloaded_verified`; original pinned Git Blob matched |
| Local scan | `no_obvious_static_flags_not_approved`; zero actionable flags |
| License status | Unknown (`null`), `license_terms_require_review` warning preserved |
| Codex host compatibility | `not_declared`; not validated |
| Preview read-only | Original downloaded `source.json` byte content unchanged; no simulation directory created |
| Simulated apply | `simulated_active`, event sequence 1 |
| Simulated rollback | `simulated_rolled_back`, event sequence 2 |
| Final status | `simulated_rolled_back` |
| Real installation / Skill execution / Agent modification | **0 / 0 / 0** |

The actual events are stored locally and excluded by `.gitignore`. Source metadata, Skill code and raw local audit records were **not** copied into this report.

## 4. Acceptance tests and evidence

- `python3 -m unittest tests.test_install_lifecycle -q`: **22 passing tests**.
- Complete suite: **257 tests + 6 subtests passing**, zero failures.
- Version pin mismatch, tampered main Git Blob, unlisted package contents and actionable static findings fail closed.
- Simulations reject missing/wrong plan-ID acknowledgement, a duplicate apply, invalid rollback and corrupt ledger history.
- Two concurrent simulated applies are serialized: exactly one event and one duplicate rejection.
- A symlink from the private ledger path to an external file is rejected without overwriting the external sentinel.
- The `install-status` ledger reader opens SQLite in read-only mode, without creating a ledger for an unknown plan.

## 5. Remaining gates before **real** Agent installation

1. Implement and verify host-specific adapter discovery for each Agent, supported directory formats, update semantics and cross-platform paths, with consent. The current Agent strings are **labels only**.
2. Design explicit, per-Skill **real** authorization with plan identity, destination and permission scope, plus secure cancellation/revocation. Simulated acknowledgement must never unlock a real installer.
3. Build atomic versioned backup and restore for any **real** host directory, with rollback after interruption, unchanged files and user edits preserved.
4. Implement a proper runtime policy for real Skill content (outside this no-execution phase); 18 benign Canary tests do not prove arbitrary downloaded code is safe.
5. Add integration tests in disposable Host fixtures on macOS/Windows/Linux; no real user Agent directory should be modified by tests.
6. Keep full package licenses, original attribution and untrusted instructions separate; avoid auto-running installers or downloaded tests.

## 6. Final acceptance statement

**PASS: deterministic read-only install preview, explicit simulation acknowledgement, private transactional event logging, simulated rollback and regression tests.** The workflow has **not** installed or executed a Skill. The implementation is an intermediate safety/UX step, **not a production Agent installer**.
