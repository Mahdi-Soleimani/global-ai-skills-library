# Phase 26 — Private bundle: real filesystem install/upgrade/rollback in a disposable Host fixture

**Date:** 2026-11-22  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Target:** Connect the Phase-25 verified, private ZIP artifact to a concrete filesystem installation transaction **without modifying any user's actual Codex, Cursor, Claude Code or other Agent configuration**.

## 1. What is actually new (versus earlier simulations)

Phase 20 recorded a *logical*, simulated install/rollback event; Phase 21 rehearsed only hardcoded inert files; Phase 22 exercised interrupted dummy transactions; Phase 25 generated the **real version-pinned private Skill ZIP**. Phase 26 now physically writes **the ZIP's actual file bytes** into a temporary `.agents/skills`, `.cursor/skills` or `.claude/skills` structure, checks content, performs renames and backups, and restores prior fixture files. It **does not** activate any real Agent Host or execute the source content. A fixture directory is deleted after each CLI rehearsal. This is a test of ZIP-driven file operations, not a production Skill install.

### CLI

```bash
./gasl bundle-fixture --plan-id YOUR_EXACT_PLAN_ID \
  --acknowledge-plan-id YOUR_EXACT_PLAN_ID \
  --agent codex --scope project \
  --scenario upgrade --stop-after activated
```

Parameters: `--agent codex|cursor|claude-code`, `--scope project|user`, `--scenario fresh|upgrade|conflict`, `--stop-after staged|backed_up|activated`. An explicitly matching SHA-256 Plan ID is required. These arguments select a **logical temporary Host fixture only**; arbitrary writable roots, home directories, production Host targets, Claude Desktop account upload and generic MCP installation are not supported.

## 2. Implemented code and safety boundaries

- New `tools/fixture_bundle_install.py` physically stages bytes from a Phase-25 ZIP, with fixed private source path `private/install-bundles/{plan_id}.zip` and sidecar. It validates the complete ZIP SHA-256, pinned sidecar identity/Host/Scope, every ZIP entry's SHA-256, file/total size bounds, duplicate and case-fold collision, common ZIP symlink/unix-mode flags, relative paths, Zip Slip and `SKILL.md` Git Blob evidence. Content is **read as data**, never run as scripts or evaluated as prompt instructions.
- It creates **only a fresh, marked** temporary GASL fixture under the OS temp directory. A source ZIP can contain code, but such bytes are never copied to real project directories and no Host/model runtime is invoked. The temporary profile mimics the Host's documented Skill directory layout without being configured as a real Agent profile.
- If `fresh`, the target must not exist. If `upgrade`, the prior **fixture-owned** Skill is present and its complete file inventory—including all nested directories—is verified before moving it to a separate temporary backup. If `conflict`, the target is preserved and no replacement occurs.
- Staging, backup and activation use same-filesystem directory renames, recorded by a fixture-local, bounded JSON journal with exact plan ID, Host, Scope, random transaction ID and file SHA-256 inventory. No production approval flag is set. Three checkpoints (`staged`, `backed_up`, `activated`) enable deterministic tests of cleanup and rollback.
- Rollback verifies both the new and old inventories **before removing or restoring anything**. A tampered ZIP, edited activated file, added empty directory, changed backup, unexpected target or symlink causes a **fail-closed refusal** so fixture edits are not lost. The entire temporary fixture is removed after CLI completion; any conflict is returned as a separate non-installation outcome.
- New `./gasl bundle-fixture` CLI command. Existing `install-bundle`, `install-plan`, `install-simulate`, `download`, search, REST API and MCP behaviors remain unchanged.
- New `.github/workflows/gasl-bundle-fixture-transaction.yml`: lightweight Ubuntu CI with read-only Git contents and credential-free checkout, compiling the fixture module, running **only synthetic pinned ZIP test data** and asserting no persistent `catalog/` or private bundle data exists in the checkout. No original third-party Skill ZIP is uploaded or run in CI.

**Scope of protection:** these are strong fail-closed controls on **self-created, temporary fixtures**, not a proof of adversarial filesystem race safety in a shared real Host profile, nor a power-cut durability certification. The JSON journal is a local fixture marker, not a digitally signed tamper-proof audit log. No launch of Codex, Cursor or Claude Code is included.

## 3. Actual Mac end-to-end evidence using a previously downloaded real ZIP

Used the already locally verified, private `academy-guide` ZIP from Phase 25, source ID `GASL-SRC-ce593c8b9b3fd34f44d6`, plan ID `f52f11b345714191c780bd63b6e18e1d05a9f2ed3257c3b791a9e2fa00e45fcb`. It contains **two source files**, `academy-guide/SKILL.md` and `academy-guide/LICENSE.txt`. The entire ZIP remained in `private/install-bundles/` and is Git-ignored; neither it nor its source content was committed.

| Test | Observed result |
|---|---|
| Fresh install to newly created, temporary Codex project layout | `fixture_bundle_rollback_verified`; both files materialized and then removed |
| Upgrade over a pre-existing *inert fixture version* | `fixture_bundle_rollback_verified`; prior fixture content backed up, then restored |
| Existing Skill conflict with replacement not explicitly enabled | `existing_fixture_skill_preserved`, original unchanged |
| ZIP already verified by Phase 25 | Original SHA-256 and required `SKILL.md` Git Blob checked again; no execution |
| Live host files changed | **0** |
| Third-party Skill executed | **0** |
| Permanent third-party file installed on Mac | **0** |
| Production installer enabled | **false** |

The initial real ZIP demonstration deliberately invoked only a **temporary fixture**; it was not sent to, installed in or discovered by the running Agent application. The ZIP's own license remained unknown in the registry, so it continues to require review before any actual deployment; this stage cannot imply license approval.

## 4. Regression coverage

Added `tests/test_fixture_bundle_install.py` with **19 tests and a 36-case matrix**: 3 Host layouts × 2 scopes × 2 fixture install types × 3 checkpoints. Checks cover actual byte-for-byte materialization, prior version and user-note restoration, all checkpoints, overwrite conflict, explicit Plan ID, cross-Host/Scope identity mismatch, blocked Claude Desktop, duplicate concurrent local journal, modifications to activated files and backup, user-created empty directory preservation, symlink boundary, corrupt archive SHA, main Blob mismatch, ZIP symlink mode and Zip Slip. 

Local acceptance: **345 tests + 130 subtests PASS**; Python compilation and `git diff --check` PASS. A dedicated CI workflow will provide separate Linux proof after the source commit is pushed. The matrix uses **synthetic ZIPs** only; the real archive is tested exclusively on the local Mac and never published.

## 5. Sensitive-data and publication policy

- Commit **only** the new fixture installer module, its tests, CLI dispatch, small scoped README/roadmap updates, this public report and the CI YAML.
- Review all staged files for private keys, API secrets, access tokens, local absolute user paths, phone/email values and non-public originals. Do not print secret matches into output.
- The actual `private/install-bundles/*.zip` and `.json` artifacts, package cache, raw security evidence and temporary fixture directories remain Git-ignored and out of the published repository.
- Use a non-force Push and reconcile any automated metadata-refresh Commit non-destructively.

## 6. What remains before a **real** user-profile install

1. An explicitly approved version-target-scope user consent flow for the *real* Host directory, separate from test-only Plan acknowledgement.
2. Host-specific adapter detection and validation in actual Codex/Cursor/Claude Code profiles; Codex's separate inert discovery proof does not certify all packages.
3. Durable, race-safe backup/rollback with collision handling, ownership tracking, change preservation, and interruption recovery across supported OS/filesystems.
4. Licensing and code-risk review before any untrusted package is loaded into a real Host; a passing static scan and benign isolated file transfer do not certify third-party Skill instructions or scripts as safe.
5. Additional Windows and live Host integration tests with disposable accounts/profiles. No production Skill installer or execution is enabled by Phase 26.

**Phase 26 locally accepted: actual ZIP file materialization and verified rollback in a disposable temp profile. No user Agent profile was modified.**
