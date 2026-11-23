# Phase 42 — Restore a committed Codex project Skill backup

**Date:** 2026-11-23  
**Repository:** Mahdi-Soleimani/global-ai-skills-library  
**Baseline:** 1e04ed322bff9a2521fdbc2bd9b98894dfac8088 (Phase 41, main)

## Objective

Complete the missing part of the Phase 41 lifecycle: allow a user to **restore a backup after the replacement succeeded**, not merely recover an interrupted transaction. Both the selected historical backup and the currently active version must survive the operation as separate verified backups.

## Scope and commands

Supported: an **explicit, existing Git project root** hosting project-scope Codex Skills under .agents/skills/SKILL. The real user HOME, arbitrary other projects, Cursor/Claude Code, unattended restore, Skill code/script execution and model turns remain excluded.

    ./gasl codex-project-install --action list-backups --selected-root /ABSOLUTE/GIT/PROJECT --skill-name SKILL

    ./gasl codex-project-install --action preview-restore --selected-root /ABSOLUTE/GIT/PROJECT --skill-name SKILL --backup-id EXACT_32_CHAR_ID

    ./gasl codex-project-install --action restore-backup --selected-root /ABSOLUTE/GIT/PROJECT --skill-name SKILL --backup-id EXACT_32_CHAR_ID --state-binding-id EXACT_PREVIEW_BINDING

    ./gasl codex-project-install --action recover --selected-root /ABSOLUTE/GIT/PROJECT --skill-name SKILL

Restore requires a real, local interactive TTY and an exact challenge including the Skill slug, selected Backup ID, current Plan ID and preview Binding. Programmatic tests provide a test-only reader; a noninteractive CLI invocation without a TTY is refused.

## Implemented behavior

### Read-only list and preview
- list-backups returns retained backup IDs in history order, file counts, source kind (pinned/unmanaged), an upstream Plan ID only when supported by managed history, and availability for restore. No absolute local paths or user file contents are emitted.
- preview-restore verifies the current GASL receipt, all active file hashes, every retained Backup manifest and directory, the selected Backup ID's membership in the current receipt history, and the presence of a regular root SKILL.md.
- The binding is derived from a hash of the exact selected target path, current receipt and file inventories, selected Backup ID, and the identities of **all** retained Backup manifests. The same binding is rechecked after interactive confirmation while holding an exclusive POSIX lock.
- Identical-to-current backups are not restored as no-op replacements; stale bindings, malformed IDs, modified files or metadata, symlinks, and pending transactions are refused.

### Restore transaction
1. Verify the selected original Backup without modifying or consuming it.
2. Copy every verified original Backup file to a private, distinct Stage directory outside Codex discovery; verify SHA-256 during streaming copy and after staging.
3. Write a durable Restore journal containing the exact previous receipt, next receipt, selected manifest, both inventories, transaction ID and binding.
4. Recheck the active and selected Backup directory inventories, then atomically rename the **current active Skill** into a **new** Backup ID under .gasl-managed/backups/SLUG/.
5. Persist the current-version Backup manifest including the previous receipt; atomically rename the restored Stage into the project Skill directory.
6. Verify the restored files and atomically replace the receipt. Its backup history appends the newly saved active version while preserving every earlier backup ID.
7. Delete the journal after a successful receipt commit.

The selected historic Backup is retained unchanged after success, so the user can restore or compare it again. A further restore can return to the just-saved formerly-current version.

### Provenance contract
- When the historical Backup has a GASL receipt, the restored version retains its original source Plan ID and pinned/unmanaged provenance.
- A historically **unmanaged** Skill is restorable. It receives a new GASL receipt with source_kind=unmanaged and an explicitly marked, **synthetic local identity** derived from that Backup inventory. It is **not** reported as an upstream pinned source.
- All restored versions are managed by GASL for subsequent explicit replacement or removal. No Skill instructions, scripts, package managers or dependency installation are run.

### Recovery and refusal
- Pre-receipt-commit interruption: recover checks all original and selected backups, journal, manifests and every existing tree **before** moving or removing any file. It removes only a still-unmodified staged/restored tree and renames the saved-current backup back into the target. The original active receipt stays.
- Post-receipt-commit interruption: recover verifies the restored target and saved-current Backup, restores a missing manifest if appropriate, and finalizes the valid commit; it does not revert the already committed version.
- Recovery refuses mutated current/selected Backup, edited restored target, symlink, ambiguous original/backup duplication, forged or mismatching receipt and missing/incomplete evidence. It preserves unknown edits and journal for manual inspection.
- The original Backup is never overwritten or deleted by this workflow; backup history is not automatically pruned.
- Backups are checked against hashes; same-account malicious filesystem write access remains outside this integrity guarantee.

## Files changed

- tools/codex_project_install.py: list_backups, preview_restore, restore_backup, recovery path, binding, local provenance, staged streaming copy and journal validation.
- tools/gasl.py: CLI actions list-backups / preview-restore / restore-backup and the required exact arguments.
- tests/test_codex_project_install.py: focused read-only, provenance, stale binding, invalid ID, symlink/tampering, no-op, TTY refusal, repeated restore, crash injection and recovery regressions.
- .github/workflows/gasl-codex-transaction-e2e.yml: extended real Codex isolated project test for committed Backup restore, crash injection, recovery and round-trip restore.
- README.md, docs/ROADMAP.md, this report.

## Acceptance evidence

- Local focused test suite: **52 tests PASS** in tests.test_codex_project_install.
- Related install/bundle/format suite: **85 tests PASS**.
- Full local regression: **511 tests PASS and 236 subtests PASS**; all Python compile checks, workflow YAML parse and git diff whitespace checks PASS.
- **Real Codex App Server on macOS: PASS**, executing the exact modified workflow test in a disposable Git project and disposable Codex HOME. An inert Skill was discovered; a pinned version was installed, replaced, then successfully restored from committed Backup; the previously active version was retained as a new Backup; an injected crash during a second restore recovered the last committed version; a subsequent round-trip restore and final uninstall were reflected correctly by real skills/list discovery.
- REAL_USER_PROFILE_MODIFIED=FALSE; THIRD_PARTY_EXECUTED=FALSE.
- No real user project was used for the restore/integration tests.

## Publication and CI

**Current status at drafting:** Local tests completed; GitHub Linux workflows will be checked after the commit is pushed. Record exact Linux run IDs, conclusions and any branch changes in a report follow-up rather than claiming them prematurely.

## Next phase candidates

- Explicit restore preview/list for previously uninstalled but still retained Backup histories, with a distinct ownership and consent model.
- Optional backup retention/export only after a separate proposal; never silently prune or overwrite historical snapshots.
- Separate user-scope Codex installer/recovery with independently validated role binding and permission boundaries.
- Real discovery lifecycle for additional Host adapters when supported by their verified CLIs.
