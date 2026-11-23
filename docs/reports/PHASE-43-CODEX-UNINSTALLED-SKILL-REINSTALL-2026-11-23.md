# Phase 43 — Verified reinstall after completed Codex project Skill uninstall

**Date:** 2026-11-23  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Starting main:** `cec4a81a69ce19daa87db8e29f6ce04077938656`.

## Objective

Extend the Phase 40–42 project-only Codex installer so that a completed, explicit Uninstall does **not** strand or erase previously retained backups. Installations performed before Phase 43 deleted their ownership receipt on uninstall, leaving no reliable evidence connecting their remaining backup directories to an authorized project/Skill. This phase adds a **project-bound uninstall ownership marker** and archives the currently active Skill as one additional backup so the last active version, as well as older versions, can be recovered.

No changes to a personal Codex HOME or any user-owned project were authorized or made. All real filesystem writes in development tests were to disposable, Git-marked temporary projects.

## Added commands

```bash
# Read-only listing after Uninstall
./gasl codex-project-install --action list-uninstalled-backups \
  --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL

# Read-only inspection of one retained Backup and a path/ownership-bound binding
./gasl codex-project-install --action preview-reinstall \
  --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL \
  --backup-id EXACT_32_HEX_BACKUP_ID

# Real, opt-in reinstall into an empty target; requires interactive TTY confirmation
./gasl codex-project-install --action reinstall-backup \
  --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL \
  --backup-id EXACT_32_HEX_BACKUP_ID --state-binding-id EXACT_PREVIEW_BINDING

# Recover an interrupted Uninstall or Reinstall transaction
./gasl codex-project-install --action recover \
  --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL
```

The old `uninstall` action remains. It now archives the last active directory under `.gasl-managed/backups/SKILL/ARCHIVE_ID/`, and stores its exact inventory and former receipt in a manifest; the original Codex Skill directory disappears from `.agents/skills/SKILL` as before.

## Explicit ownership and no implicit claims

- New per-project Uninstall Tombstone: `.gasl-managed/uninstalled/SKILL.json`, containing its schema, precise target-path hash, Skill name, unique Uninstall event ID, prior GASL receipt, archived-current backup ID and ordered full backup chain.
- Listing/preflight verify every retained backup manifest and file SHA-256, along with the project/Skill binding and the last active archive's inventory and receipt.
- If the user moves the project, changes a backup/manifest, swaps a symlink, forges a source ID, or changes the selected target after preview, the operation fails closed.
- A reinstalled Skill receives a fresh GASL ownership receipt whose backup history is **inherited unchanged** from the verified Uninstall Tombstone; its provenance is `pinned` only if the selected backup has a genuine prior GASL receipt. Restored unmanaged historical Skills receive a clearly marked **synthetic local ID**, not a fabricated pinned upstream record.
- Uninstall → Reinstall → Uninstall works repeatedly, appending a new current-archive ID without discarding older backups or losing the preceding ownership chain.
- A new fresh install cannot bypass a retained Uninstall marker; users must intentionally select a recoverable historical backup.
- Previous pre-Phase-43 Uninstalls that retained files but **did not create a Tombstone** cannot be auto-reconciled safely. GASL refuses their automatic reinstall; later manual reconciliation would need separate, explicit review and consent.

These are local filesystem integrity and consent checks, not protection against a fully malicious process already running with the same account's filesystem privileges.

## Transactional durability and failure isolation

**Uninstall:** after exact interactive approval, a journal records the previous receipt, prior marker and new Uninstall marker. The current Skill directory is atomically moved to its archive. A manifest is written, ownership marker created/atomically updated, receipt removed and journal cleared. The archived files remain in the project, not in Codex's discoverable Skill path.

**Reinstall:** after a separate interactive challenge binding the selected backup, Uninstall event and state digest, immutable backup files are copied and verified in an isolated private Stage. A journal binds the Uninstall marker, selected manifest, file inventory, new receipt and selected project. The stage is atomically moved to the absent destination. The transaction finishes only after writing and fsyncing the new receipt and deleting the journal. Neither selected Backup nor previous history is consumed.

**Recovery:** only hash-matching archives/targets/manifests are handled. Interruptions before receipt commit restore the old Uninstall or remove only the exact staged/reinstalled tree. If a new receipt was fully committed, Recovery finalizes the already-valid reinstall. Changes to an active target, archive, receipt or ownership marker cause refusal, not unsafe deletion. Legacy Uninstall transaction recovery remains backward-compatible.

## Security and product limits

- **Project-scoped Codex only**, on macOS/Linux with the existing POSIX advisory lock. No real user HOME, Cursor or Claude Code writes.
- Requires a selected existing Git project and exact backup ID; no search across unrelated project folders.
- Requires explicit local human TTY approval for real reinstallation and deletion; tests inject test-only readers and do not establish user authorization.
- No untrusted third-party Skill source, executable, dependency, MCP server, model request, network download or runtime installation is executed.
- No automatic backup deletion, overwrite, eviction, or license/safety inference. Backup bytes may consume disk space; this phase intentionally favors recoverability.

## Changed files

- `tools/codex_uninstalled_restore.py` — ownership marker validation, listing, bound preview, reinstall and recovery.
- `tools/codex_project_install.py` — atomic archival Uninstall, new receipt/journal actions, recovery delegation, fresh-install refusal for an unresolved Uninstall marker.
- `tools/gasl.py` — three CLI actions: list-uninstalled-backups, preview-reinstall, reinstall-backup.
- `tests/test_codex_uninstalled_restore.py` — synthetic positive/negative, provenance, collision, failure-injection and recovery tests.
- `tests/test_codex_project_install.py` — adapted backup-retention assertions for archival Uninstall.
- `.github/workflows/gasl-private-install-bundle.yml` — new synthetic checks and compiler targets.
- `.github/workflows/gasl-codex-transaction-e2e.yml` — real Codex App Server discovery/uninstall/reinstall/recovery tests in disposable Ubuntu profile/project.
- `README.md`, `docs/ROADMAP.md`, this report.

## Local evidence and acceptance

- Focused project install/uninstall/reinstall/bundle/format: **103 tests PASS**.
- Full local Python suite (system Python lacks optional `mcp` package): **529 tests PASS and 236 subtests PASS**, no failures; Python compileall and whitespace validation also passed.
- **Real macOS Codex E2E — PASS**: ran the exact changed GitHub Actions Skill lifecycle step with real Codex CLI in a newly created disposable Git project, isolated HOME and CODEX_HOME. The Skill disappeared on Uninstall, a deliberately interrupted Reinstall was rolled back, a successful Reinstall rediscovered the exact enabled Skill, and a second Uninstall again removed it while preserving complete history.
- No real user profile or real user project modified; no downloaded third-party Skill executed.

## GitHub Actions and publication

CI run URLs, final conclusions, revision hash and any automatic metadata refresh commit should be appended **only after live GitHub verification**; CI status is not inferred from passing local tests.

## Next technical work

The original pre-Phase-43 orphan-backup problem requires an explicit, human-reviewed reconciliation design, not automatic assumption of ownership. Other potential enhancements: optional/approved backup export and pruning, real user-scope Codex deployment with independently approved role checks, and discovery for other Hosts when officially supported.

## Publication and verified GitHub CI

- Feature commit: [`671755b`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/671755bac60f1a55b8f3a21ab90146ccbd15e1b6), pushed normally to `main`, following a staged ten-file allowlist, no-sensitive-pattern scan, whitespace checks and successful macOS regression tests. No private ZIP, device-specific path, real personal Skill or secret was published.
- [Real Codex lifecycle — run `45195556931`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45195556931): **completed / SUCCESS**. The Ubuntu step `Exercise real Codex project replace, restore, uninstall archive and reinstall` passed against a synthetic inert Skill using real Codex App Server, including interrupted-Reinstall rollback, successful rediscovery, second uninstall and preserved backup chain.
- [Private ZIP and installer safety — run `45195556905`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45195556905): **completed / SUCCESS**, including all new synthetic archive/reinstall regressions. No third-party content was exported or executed.
- [Source-catalog refresh and full regression — run `45195556925`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45195556925): **completed / SUCCESS**. The full dependency-equipped Python suite logged **535 passed**, and the refresh operated on the existing 57-repository catalog. The metadata-only automation published a separate `main` commit ([`4c1ef04`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/4c1ef04)).
- The updated remote metadata commit was fetched and **fast-forwarded** locally without a force push or modifications to unrelated project code. The local `main` and `origin/main` matched with a clean working tree before this evidence-only report update.

**Final technical acceptance:** Phase 43 functionality and Linux CI both pass. Actual reinstallation into a real user's own project was **not performed** and still requires selection of that project plus human TTY approval. Backup directories left by previous versions without ownership markers remain deliberately ineligible for unattended reconciliation.
