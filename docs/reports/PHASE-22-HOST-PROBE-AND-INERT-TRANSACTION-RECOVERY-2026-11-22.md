# Phase 22 — Read-only Host probe and inert interrupted-transaction recovery

**Date:** 2026-11-22  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Work scope:** Implement an actual read-only check of Host CLI availability, then exercise version-safe staging and interrupted installation/upgrade recovery **only on generated, disposable GASL fixtures**. No third-party Skill execution, real Host configuration access or installation is authorized.

## 1. Actual Host availability observed (not invented)

On the authorized development Mac, the commands `command -v codex`, `command -v cursor`, and `command -v claude` all returned **missing from `PATH`** at the time of inspection. Consequently no real Host binary was launched and no real Host Skill discovery was tested. This is not proof that a GUI application is uninstalled, only that those CLIs were not visible through the environment's `PATH`.

Added `tools/host_probe.py` and `./gasl host-probe`. The probe uses only executable-name lookup, reports availability as a boolean **without disclosing private executable paths**, and never reads Host configurations or launches programs. Even an available CLI results in `binary_detected_not_executed`, **never** `host_skill_discovery_verified=true`. Claude Desktop remains a manual account ZIP upload target and generic MCP has no universal local Skill directory/CLI.

## 2. Implementation: fail-closed, fixture-only transaction state machine

Added `tools/host_transaction_fixture.py` and the CLI command:

```bash
./gasl host-transaction-rehearsal \
  --agent cursor --scope project --kind upgrade \
  --interrupt-after new_activated
```

- **Scope:** `codex`, `cursor`, `claude-code`, with `user` or `project` scope; `fresh` or `upgrade` of a **fixed GASL-authored inert `SKILL.md`**. No real downloaded packages, scripts, secrets or user-supplied destination paths are accepted.
- **Filesystem boundary:** create a new OS temporary directory with a distinctive `gasl-host-fixture-*` name and internal marker, validate that directory and all relative target components are non-symlink paths within the fixture. Real home, workspaces and Agent directories are never opened or altered.
- **Safe preparation:** stage deterministic inert bytes, record their SHA-256 and an opaque random transaction identifier in an atomically replaced, fsynced **fixture-local journal**. No production permission or user profile is read.
- **Replacement rehearsal:** when upgrading, move the prior inert version and its *user-edit sentinel* to a separate fixture backup with filesystem rename, then move the staged inert version into the target.
- **Interruption boundaries:** `prepared`, `old_backed_up`, `new_activated`. The transaction stops at each checkpoint and the local repair routine derives expected paths from a strictly validated journal; it does not trust journal-provided arbitrary file paths.
- **Fail-closed rollback:** before deleting a staged/new fixture, verify its complete expected contents and confirm the backup matches the original inert version and edit sentinel. If any file has changed, if a target is a symlink, or if the journal is invalid, **refuse automatic overwrite**, preserving the conflicting fixture data for inspection. A successful rollback restores the exact prior fixture state (or empty target on a fresh install).
- **Cleanup:** dispose of the entire temporary fixture after the controlled rehearsal; no real Agent files or downloaded content are modified. No production installer is enabled.

**Important limits:** These are staged *simulations* of interruptions, **not real power cuts, kernel-crash tests, production atomicity certification or cross-process concurrency authorization**. Journal/fsync semantics on real user filesystems must be validated separately. A malicious process with the same user privileges manipulating the temporary fixture concurrently remains outside this proof. Recovery does not restore a real installation because there is no real installation.

## 3. Real local results

Executed a **36-case** matrix: 3 filesystem Host layouts (Codex, Cursor, Claude Code) × 2 logical scopes × 2 inert modes (`fresh`, `upgrade`) × 3 interruption checkpoints. All **36/36** returned `inert_fixture_recovery_verified` and restored the expected fixture version. No externally installed Skill was used or executed, no real Host files were touched, and all temp fixtures were removed.

The private row-level result is retained only under ignored `reports/host-adapters/PHASE22-INERT-RECOVERY-MATRIX-2026-11-22.json`, not included in GitHub. This public report contains only aggregated counts and documented controls.

### Negative/security cases exercised

- Editing the activated inert `SKILL.md` after interruption: automatic recovery refuses to overwrite it and retains the backup.
- Editing the backed-up inert user sentinel: recovery refuses to replace the target.
- Editing staged bytes or corrupting the transaction journal: fail closed.
- Injecting a symlink pointing at a separate inert sentinel: fail closed, sentinel preserved.
- Passing a non-fixture root or unsupported Claude Desktop/generic MCP filesystem target: rejected without accessing actual Host files.
- Attempting two unresolved transactions in one fixture: rejected.
- A Host CLI being present (mocked) is correctly **not counted** as proof of Skill discovery.

## 4. Code, tests and continuous integration

| New / changed path | Role |
|---|---|
| `tools/host_probe.py` | Real read-only name lookup, no executable invocation or path disclosure |
| `tools/host_transaction_fixture.py` | Fixed inert package, staging/backup/interruption/recovery, strict fixture-only path guard |
| `tools/gasl.py` | New CLI commands `host-probe`, `host-transaction-rehearsal` |
| `tests/test_host_transaction_fixture.py` | 15 tests with a 36-case subtest matrix and negative cases |
| `.github/workflows/gasl-host-transaction-fixtures.yml` | Dedicated `contents: read` Ubuntu runner job; only inert self-authored tests, no external Skill code or package installation |
| `README.md`, `docs/ROADMAP.md` | Capabilities, restrictions and next work |

Local acceptance: **289 tests + 79 subtests passed**, Python compilation passed. The full 36-case matrix and CLI smoke also passed on macOS. The separate GitHub Actions workflow must be observed after publication to confirm Linux fixture behavior; its result is **not assumed** from local tests.

## 5. Sensitive-data publication policy

Before pushing to the public repository:

1. Stage only the exact Phase-22 code, tests, workflow and generalized documentation files.
2. Ensure no ignored paths (`private/`, `catalog/`, `reports/`, local database, package cache or user/Host configuration) are staged.
3. Examine staged path list and staged contents for API tokens, private-key blocks, credentials, sensitive endpoints and identifying local absolute paths. Do not echo any actual match value into CI logs or public reports.
4. Use a normal, **non-force** Git push; abort and reconcile concurrent remote updates non-destructively. Check the resulting public commit and CI result.

## 6. Remaining work / next gate

- **Host discovery:** install or attach a compatible Host test executable into a **separate temporary test profile**, then verify it actually loads only an inert self-authored Skill. Real Codex/Cursor/Claude Code integration has **not** been performed here; do not infer support from path conventions alone.
- **Production transaction:** bind explicit real-user consent to exact destination, version and permissions; test interruptions on real target filesystems in isolated disposable accounts/containers; resolve conflicts without losing user edits.
- **Security:** never convert a clean static scan or a benign Docker canary into blanket permission to run untrusted Skill code. Seven source packages with actionable static findings remain gated.
- **Cross-platform:** Windows and actual Host versions remain to be tested; these local fixture tests were run on the authorized macOS computer and the new CI job targets Linux.

**Acceptance:** Phase 22 read-only Host capability discovery and inert interruption/recovery rehearsal **implemented and locally verified**; actual Host Skill recognition, real installation, real rollback of user files, and execution of third-party code remain **disabled or unverified**.
