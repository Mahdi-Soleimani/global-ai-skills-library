# Phase 51 — Cursor and Claude Code project Skill lifecycle

**Date:** 2026-11-23
**Repository:** Mahdi-Soleimani/global-ai-skills-library
**Starting revision:** 739c44184ae50a4c2d718641fd0b0369489cf2e7
**Scope:** real POSIX project-scope filesystem transaction adapters, verified with isolated synthetic tests. No real-user Host testing or untrusted Skill execution.

## 1. Goal, official paths and scope

After Phase 49 connected Codex's transactional installer to the Explorer, Cursor and Claude Code remained preview-only. Phase 51 adds real project filesystem installation, version replacement, backup, restore, uninstall, archived reinstatement, and recovery for those two Hosts.

Official current documentation:
- Cursor: https://cursor.com/docs/skills — project directory .cursor/skills/<slug>/SKILL.md
- Claude Code: https://code.claude.com/docs/en/skills — project directory .claude/skills/<slug>/SKILL.md

A documented directory is not proof that a real running Host will discover or safely use a Skill. The user's instruction to skip manual/real-user testing and human relevance adjudication remains in effect.

## 2. Independent Host ownership

The engine tools/host_project_install.py supports only host=cursor or host=claude-code, project scope, an explicitly selected existing absolute Git root, and local POSIX fcntl locks. It does not reuse or alter Codex's receipts.

- Cursor: project/.gasl-managed/hosts/cursor/{receipts,journals,stage,backups,uninstalled}
- Claude Code: project/.gasl-managed/hosts/claude-code/{receipts,journals,stage,backups,uninstalled}
- Codex: unchanged project/.gasl-managed/ state and existing transaction module.

Target paths are taken from checked Host adapter declarations. No symlink, non-directory, unknown Agent, user HOME target, unsafe slug or path escape is accepted.

## 3. Implemented actions

| Operation | Behavior |
|---|---|
| Fresh install preview | Read-only, checks actual target path, verified pinned ZIP and static SKILL.md format |
| Fresh install | Exact local TTY phrase; rechecks target/ZIP binding under Host lock; write-ahead journal, staged copy, atomic rename and ownership receipt |
| Replace preview | Refuses unmanaged or modified existing Skills; verifies all backups |
| Replace | Requires explicit action and TTY; archives complete previous Skill with manifest and ownership link; activates verified new version |
| Backup list | Checks full local lineage and file inventories, returns owned IDs with no claim of independent upstream provenance |
| Restore | Requires owned backup ID, fresh binding, exact TTY phrase; saves current active version in a new retained backup |
| Uninstall/archive | Saves final owned active version and marker; removes active receipt and target without destroying archives |
| Reinstall | Only from marker-linked retained backup ID with exact TTY approval, rehashes and stages full files |
| Recover | Detects completed journal or reverts incomplete journal **only if exact contents match**, preserving unexpected user edits |

All file inventories are SHA-256 checksums of regular files. The target/backup state binding includes all current retained backup manifest evidence as well as target and receipt; changing archived provenance between preview and action invalidates the binding. ZIP reader, source Git Blob verification, static scan and Host format gates are shared with established modules.

### Crash-recovery boundaries

Durable journal precedes rename of the active Skill. Explicit recover verifies the journal's Host identity, operation, ownership receipts, backup history, target state, staged files, manifests and Uninstall marker before any removal/rollback.

Recovery test cases include interruption before a backup manifest exists, after new activation, after ownership commit, and during uninstall/reinstall, plus refusal to delete modified user files. If a process dies before a journal is durably written, an orphan pre-journal staging folder may require review rather than automatic cleanup; the system never guesses ownership or deletes unknown files.

The POSIX advisory lock coordinates GASL processes, not arbitrary external editors. No claim of transactional protection against hostile concurrent filesystem actors is made.

## 4. Explorer and terminal workflow

tools/host_project_wizard.py connects Explorer selection to a **local terminal command**, never to an HTTP installation endpoint. Supported host options: cursor or claude-code. Exact project root is required.

Run from the GASL repository:

    export GASL_SELECTED_PROJECT="/absolute/path/to/existing/git/project"

    # Read-only preview, no ZIP creation
    ./gasl host-project-wizard --host cursor --id GASL-SRC-EXACT_SOURCE_ID --selected-root "$GASL_SELECTED_PROJECT" --action preview

    # Actual project files can be written only with exact local TTY consent
    ./gasl host-project-wizard --host cursor --id GASL-SRC-EXACT_SOURCE_ID --selected-root "$GASL_SELECTED_PROJECT" --action install --download-if-missing

Use --host claude-code for Claude Code. For a separately approved replacement, use --action replace.

Three independent TTY consent gates apply when needed: optional explicit pinned download, optional new private ZIP preparation, and final real installation. ZIP tampering, static findings, incomplete source packages, source drift, occupied/unmanaged target and stale bindings block the transaction. No Skill code or Host is executed.

Low-level commands provide the complete lifecycle:

    ./gasl host-project-install --host cursor --selected-root "$GASL_SELECTED_PROJECT" --action list-backups --skill-name exact-slug
    ./gasl host-project-install --host cursor --selected-root "$GASL_SELECTED_PROJECT" --action preview-restore --skill-name exact-slug --backup-id EXACT_ID
    ./gasl host-project-install --host cursor --selected-root "$GASL_SELECTED_PROJECT" --action restore --skill-name exact-slug --backup-id EXACT_ID --state-binding-id EXACT_BINDING
    ./gasl host-project-install --host cursor --selected-root "$GASL_SELECTED_PROJECT" --action preview-uninstall --skill-name exact-slug
    ./gasl host-project-install --host cursor --selected-root "$GASL_SELECTED_PROJECT" --action recover --skill-name exact-slug

The original Codex project command remains unchanged. Browser selection for all three filesystem Hosts now offers an explicit copyable local TTY command, and never performs an HTTP write.

## 5. Changed files

- tools/host_project_install.py: separate transactional Host engine and conservative receipt/backup/journal recovery
- tools/host_project_wizard.py: local Explorer-selected preparation and consent flow
- tools/gasl.py: two new subcommands, project-scoped actions and selected Host
- web/index.html: Cursor and Claude Code terminal handoff while the browser remains read-only
- tools/host_adapters.py: explicitly distinguishes real project filesystem transaction support from **unverified live Host discovery**
- tests/test_host_project_install.py: full inert multi-Host lifecycle, fault injection and fail-closed guards
- tests/test_host_project_wizard.py: local TTY consent, private ZIP and download fixture behavior
- tests/test_host_adapters.py and tests/explorer_workflow_smoke.js: accurate capability matrix and browser-only simulation
- .github/workflows/gasl-host-project-install.yml: lightweight CI for the above tests, without executing Skill content or logging into a real Host
- README.md, docs/ROADMAP.md, this report

## 6. Remaining unimplemented capabilities

- Genuine user-profile / HOME-scope installation, backup, rollback and recovery.
- Windows write-capable transactional installer and cross-platform filesystem locking.
- Controlled third-party Skill execution Sandbox beyond the existing inert canary.
- Independent upstream publisher/source validation and any separately needed license interpretation.
- Project owner must choose GASL's own License before public publication; current private MVP draft remains non-public.
- Real application discovery and manual trial for Cursor/Claude Code deliberately skipped by user, **not** claimed passed.
- Quality Gold adjudication deliberately deferred by user.

## 7. Verification

Local tests and GitHub Actions results plus commit SHA will be appended only after confirmed. No real Host binaries were launched, no user-owned projects/profiles changed and no third-party Skill instructions/scripts were executed.

## 8. Verified feature delivery and automated acceptance

- **Feature Commit:** [95fa7d16a54d54b66cc0071de9b0817e8e1ada29](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/95fa7d16a54d54b66cc0071de9b0817e8e1ada29). The 13-file staged allowlist and sensitive-pattern scan both passed before the normal, non-forced push to main. No private ZIP, account secret or personal HOME path was committed.
- **Host transaction CI:** [Run 45242143735](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45242143735), **completed SUCCESS**. Includes tests for both Hosts' fresh install, full backup replace, restore, uninstall/reinstall, interruption/recovery and local TTY approval.
- **Explorer UX CI:** [Run 45242143942](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45242143942), **completed SUCCESS**. Browser selection produces Cursor/Claude Code terminal commands; no HTTP installation route exists.
- **Existing Codex, ZIP/Host fixture and release-draft workflows** also completed successfully on the same feature commit: Runs 45242143715, 45242143646, 45242143569, 45242143482 and 45242143427.
- **Full source refresh and regression:** [Run 45242143810](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45242143810), **completed SUCCESS**, **724 passing tests** on Linux, **57 source repositories and 4,431 attributed records**.
- **Mac local regression before publication:** **718 passing tests and 290 subtests** (excluding only the optional MCP-server suite from local Python). Focused Host/adapter tests: **58 passing tests**. JavaScript DOM workflow, Python compilation, YAML parsing and Git whitespace check passed.
- **Automatic catalog-only metadata commit:** 16b46cdef3c0704d88169033b57305360e33fb6f, fetched and fast-forwarded locally without force-push or overwriting code.
- **No real-user/manual Host verification was performed**. Passing CI tests confirm the inert filesystem transaction mechanics, not runtime discovery/operation by Cursor or Claude Code. No third-party Skill code was executed.

**Engineering acceptance:** the requested Cursor and Claude Code **project filesystem transaction implementation and automated regression** are complete. User HOME, Windows, dynamic third-party execution sandbox, independent upstream authenticity evidence and choice of project License remain separate development tasks.

**Private release draft:** The existing release-draft command remains private-only with public_release_allowed=false. Its historical blocker label about other Host scopes means **live Host behavior has not been verified**; it must not be read as saying the new project filesystem installers do not exist.
