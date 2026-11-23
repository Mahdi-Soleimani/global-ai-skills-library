# Phase 41 — Codex project Skill replacement, retained backup and recovery

**Date:** 2026-11-23  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Base:** `5a7b3acfea3be3cb6c3c06fe45eb87d8c0fb8974` on `main`.

## Objective

Extend Phase 40's explicit, project-only Codex installer to support a carefully bounded **replacement of an existing Skill**. The previous directory must survive as a verifiable backup; the new version must not become authoritative until activation and receipt commit succeed; interrupted operations must restore the exact previous directory or safely finish a fully committed replacement. No real user HOME or existing user project was selected.

## Implemented

New actions in the existing `codex-project-install` command:

```bash
# Read-only replacement preview
./gasl codex-project-install --action preview-replace \
  --plan-id EXACT_NEW_PLAN_ID \
  --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT

# Real replacement: exact preflight binding + local interactive TTY phrase
./gasl codex-project-install --action replace \
  --plan-id EXACT_NEW_PLAN_ID \
  --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT \
  --state-binding-id EXACT_PREVIEW_BINDING

# Recover an interrupted replacement
./gasl codex-project-install --action recover \
  --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT \
  --skill-name EXACT_SKILL_NAME
```

### Replacement and backup contract

- The selected target must be an existing regular project Skill directory with a regular root `SKILL.md`. The same explicit Git project-root rule and refusal of the actual user HOME from Phase 40 still apply.
- Preview validates the exact pinned source/ZIP, simple Skill frontmatter, current target inventory, GASL receipt if present, all prior backup manifests and all prior backup directory hashes. It is read-only and binds the approval to the exact current target state.
- A managed Skill with local changes, a symlink anywhere in its inventory, an invalid or missing prior backup, a same-version Plan ID, stale binding, or pending transaction is refused. Unmanaged existing Skills can be replaced only after explicit consent and receive a complete backup too.
- The entire old directory is atomically renamed to `.gasl-managed/backups/<slug>/<backup-id>` on the same filesystem. This preserves files not included in the new ZIP, including user notes. A separate manifest records the exact file inventory and the previous GASL receipt (if the old version was managed).
- The new ZIP is staged outside Codex discovery, checked against the pinned inventory, then atomically renamed into the Host path. Only after verifying the activated directory is the GASL receipt atomically replaced. The journal records both inventories, old receipt, new receipt, transaction and backup ID.
- The backup remains after successful replacement and is re-verified before future replacement or uninstall. Repeated upgrades preserve all prior backup IDs and manifests. Uninstall removes only the current unchanged Skill and reports/retains the verified backups.
- `recover` handles interruption before backup move, after old directory rename, after new directory activation, after receipt commit and before journal cleanup. It validates every existing tree and manifest **before** destructive operations. It restores the old version if the receipt is not committed; if the new receipt and both directory inventories are valid, it finalizes the commit and retains the backup. Ambiguous states, changed files, missing backups, and tampered manifests fail closed and preserve the available files.

### Deliberate limits

- This feature is **Codex project scope only**. It does not install into the real user HOME, other projects, Cursor or Claude Code.
- No downloaded Skill instructions, scripts, MCP servers or dependencies are executed.
- There is no explicit user-invoked restore-from-a-successfully-committed-backup command yet. Recovery restores a prior version only for an interrupted replacement. A retained backup is exposed by its returned ID and relative path.
- Backups are logically immutable: GASL never overwrites them and validates the complete hash inventory on future operations. They are not protected against a malicious same-account process with permission to edit the project filesystem.
- POSIX advisory locking remains required (macOS/Linux); no Windows write path was added.
- No backup retention/pruning policy was introduced; no backup is silently deleted.

## Tests and real Codex verification

- `python3 -m unittest tests.test_codex_project_install -q`: **29 tests PASS**.
- Tests include read-only preview, unmanaged replacement with user-note preservation, managed receipt retention, repeated upgrades and backup chain validation, explicit consent, stale target binding, local edits, symlink refusal, tampered backup refusal, uninstall retaining backups, and interrupted replacement at multiple transaction checkpoints.
- Forced failure after old-directory backup rename: recovery restored the exact old directory and cleared the journal.
- Forced failure after new-directory activation but before receipt commit: recovery removed only the exact new inventory and restored the old backup.
- Forced failure with modified new target or tampered backup: recovery refused to destroy unknown content or backup.
- Simulated failure after receipt commit: recovery finalized the valid replacement and retained its backup.
- **Real macOS Codex integration PASS** with the locally installed CLI: an inert existing Skill was discovered; a new pinned Skill replaced it; a forced interruption immediately after the previous-directory rename was recovered; Codex rediscovered the restored old version; a later replacement succeeded; Codex discovered the new version; uninstall removed it from discovery. The old user note was verified in the retained backup. The test used a temporary Git project and isolated HOME/CODEX_HOME only.
- No real user project, actual personal Codex profile, or downloaded third-party Skill was modified or executed.

## CI and publication

The dedicated real-Codex GitHub Actions step has been extended to run the same replace/backup/interrupted-recovery/re-discovery sequence in a disposable Git project with the actual Codex CLI. The private ZIP safety workflow already includes `tests/test_codex_project_install.py`; the new 29-test module remains synthetic and inert.

**CI status:** pending until the Phase 41 feature commit is pushed and both affected workflows finish. Add exact run IDs and conclusions here after observing them; do not infer success from local tests.

## Files changed

- `tools/codex_project_install.py`: replacement preview, atomic backup, manifest, receipt commit, replacement recovery and backup-history validation.
- `tools/gasl.py`: `preview-replace` and `replace` CLI actions.
- `tests/test_codex_project_install.py`: 15 new replacement/backup/recovery regressions (29 tests total).
- `.github/workflows/gasl-codex-transaction-e2e.yml`: actual Codex discovery test for replacement and interrupted recovery.
- `README.md`, `docs/ROADMAP.md`, and this report.

## Next step

Run the updated CI on Linux and record the exact results. Then implement a separate explicit `restore-backup` operation for reverting a **successfully committed** upgrade (preserving the currently active version as another backup). Only after that should user-scope installation be considered as a distinct feature with its own role validation and approval flow.

## Local acceptance after final safety checks

- Exact GitHub Actions step text was extracted from `.github/workflows/gasl-codex-transaction-e2e.yml` and executed locally with the installed Codex CLI. Result: **PASS** for existing Skill discovery, replacement, full backup preservation, injected interruption after the old-directory rename, recovery and rediscovery of the old version, successful second replacement, discovery of the new version, and uninstall/disappearance.
- Final local regression run: **488 passed, 236 subtests passed**; focused installer/bundle/format suite: **62 tests PASS**.
- Final project and CI workflow YAML parse checks: PASS. Python compilation and `git diff --check`: PASS.
- The exact E2E run used a disposable temporary Git project and isolated temporary Codex HOME/CODEX_HOME. `REAL_USER_PROFILE_MODIFIED=FALSE`; no third-party Skill code was executed.
