# Phase 29 — Real Codex Host sees a transaction-installed Skill and its verified removal

**Date:** 2026-11-22  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Scope:** Close the gap between Phase-23 isolated *existing Skill discovery* and Phase-28 disposable *actual ZIP filesystem transaction*. Use the **real** pinned Codex CLI to observe the same inert Skill before installation, after transaction-based installation, and after verified rollback, without touching any real user Agent profile or installing a third-party Skill.

## 1. Exact test flow

1. `tools/codex_transaction_e2e.py` creates a new `gasl-host-fixture-*` temporary directory with the GASL fixture marker, empty `workspace`, `home`, `codex-home`, and XDG/cache/temp directories. It does not discover or access the user's actual Codex home.
2. It builds an **inert, GASL-authored** private ZIP containing only `gasl-discovery-probe/SKILL.md` (safe YAML frontmatter, descriptive text, no scripts or instructions to run tools), plus a test-only private integrity sidecar with exact SHA-256 and main Git Blob evidence. The test ZIP is **not a downloaded package** and is automatically deleted after the check.
3. The real Codex CLI is launched in `app-server` mode, with a strict allowlist of environment variables and an empty isolated `CODEX_HOME`. The tester sends JSONL `initialize`, `initialized`, and `skills/list` with `forceReload=true`. It asserts the self-authored Skill is **absent before installation**.
4. GASL invokes its Phase-28 `preview_fixture_consent` and `enact_fixture_transaction` with the exact ZIP, Host `codex`, project Scope and temporary target identity. The transaction stages the actual ZIP bytes under `workspace/.agents/skills/`, holds the fixture-only POSIX lock, verifies hashes, fsyncs staged contents and commits the rename.
5. The test verifies the installed `SKILL.md` byte-for-byte, starts a **new** Codex App Server under the same isolated profile, and requires exactly one enabled `gasl-discovery-probe` Skill at the canonical installed `SKILL.md` path.
6. GASL invokes the Phase-28 `recover_fixture_transaction`, verifies rollback removed the target, starts **another** clean Codex App Server and requires the Skill to be **absent again**. Any missing/disabled/wrong-path Skill, protocol failure, incorrect filesystem bytes or remaining Skill after rollback causes a non-success report and nonzero CLI exit.
7. The whole temporary tree is destroyed regardless of successful or unsuccessful checks. Only sanitized booleans and reason codes are emitted to stdout or CI, **never the actual paths, Skill contents or Host authentication state**.

### Command

```bash
# On a disposable/test environment with a trusted vendor Codex CLI binary:
./gasl codex-transaction-e2e --codex-bin /ABSOLUTE/PATH/TO/CODEX/CLI
```

## 2. Implementation changes

- Added `tools/codex_transaction_e2e.py`, reusing the official JSON-RPC protocol helper from `tools/codex_discovery_probe.py` and the existing secure fixture-only transaction in `tools/fixture_transaction_v2.py`.
- Added `./gasl codex-transaction-e2e --codex-bin ...` dispatcher. Only an **absolute, nonsymlink, existing binary** is accepted. The command has no destination argument, credentials, prompt or ability to operate on an Agent's real home or project.
- Added `tests/test_codex_transaction_e2e.py` with eight local synthetic-Host unit tests checking all three discovery observations, exact ZIP and fixture-only consent binding, missing/wrong/disabled Host discovery, malformed vendor response, unsupported binary paths and absence of persistent local project effects. These fake-Host tests are deliberately **not** evidence of real vendor integration.
- Added `.github/workflows/gasl-codex-transaction-e2e.yml`, a dedicated ephemeral `ubuntu-24.04` job with read-only repository permissions and no persisted checkout token. It installs **exact `@openai/codex@0.162.1`** only under `$RUNNER_TEMP` with `--ignore-scripts`, runs the independent synthetic protocol checks, then the **actual Codex App Server** for three fresh observations. The workflow asserts no account/model use, user-profile writes, or third-party Skills and no privately downloaded package is present in the published repository.
- Updated README and roadmap with these narrow semantics. Existing production installation, license-review and third-party execution restrictions are unchanged.

## 3. Local validation (before real Linux run)

- `python3 -m unittest tests.test_codex_transaction_e2e -q`: **8 passing synthetic-Host tests**.
- Full suite: **392 tests and 179 subtests passed**; Python compilation and whitespace checks passed.
- Neither the Mac's real Codex Host nor any user/Agent home was used. The actual vendor `skills/list` proof must come from the new GitHub Actions workflow, not from fixture-only output.

## 4. Privacy, security, and limitation statement

This test launches a trusted vendor Host process, which may have its own telemetry/network behavior, but **GASL provides it no keys, login context, user home, personal project files or downloaded third-party Skill instructions**. No model thread/turn is started, so the test is not a benchmark of model behavior. The source Skill is self-authored inert documentation; it does not install or invoke malicious/unreviewed code. This test only shows that Codex can discover the file in the tested Linux fixture after transaction-based installation, then stops seeing it after rollback. It does **not** prove Cursor/Claude Code discovery, arbitrary Skill safety, prompt-injection resistance, or a production installer with user approval and durable recovery.

The real user-profile installer remains disabled. A separate explicit user consent receipt and actual Host/OS transaction ownership/recovery validations are still needed before allowing any personal Agent directory mutations.

## 5. Live CI evidence

**Pending initial first live run.** Record exact workflow run ID, actual result, any protocol/packaging corrections and the final published commit only after observing the GitHub Actions execution. If the vendor CLI cannot see the Skill after install or continues seeing it after rollback, treat that as an integration failure rather than replacing the runtime with a fake.
