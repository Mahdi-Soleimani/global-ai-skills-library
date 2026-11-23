# Phase 52 — Transactional Skill installation in the current OS User Profile

**Date:** 2026-11-23  
**Repository:** Mahdi-Soleimani/global-ai-skills-library  
**Starting revision:** 9622ba9bee6afdb876e14cbeba8578fc1c03c3b5  
**Scope:** POSIX local filesystem implementation for Codex, Cursor and Claude Code User Profile only. Automated synthetic fixtures, no real-home writes or live Agent invocation.

## 1. Why a separate user-profile engine

Project-scope installations (Phases 49 and 51) use selected existing Git project roots. User-scope Skills can influence **all projects for the current OS account**; their trust and ownership boundaries must not inherit a project Git-root assumption.

The new engine in tools/user_profile_install.py is intentionally separated from the established Codex and Cursor/Claude project installers. It reuses only verified low-level staging, ZIP parsing, SHA-256 inventory, Host format and target preflight primitives. Existing project transaction code and persisted receipts are unchanged.

### Supported filesystem destinations

| Host | Native user-level Skill destination | Dedicated GASL state |
|---|---|---|
| Codex | ~/.agents/skills/SLUG/ | ~/.gasl-managed/user/hosts/codex/ |
| Cursor | ~/.cursor/skills/SLUG/ | ~/.gasl-managed/user/hosts/cursor/ |
| Claude Code | ~/.claude/skills/SLUG/ | ~/.gasl-managed/user/hosts/claude-code/ |

Relevant official sources:
- OpenAI user-scope Skill path: https://developers.openai.com/api/reference/cli
- Cursor native Skill paths, discovery and Sync Skills: https://cursor.com/docs/skills
- Claude Code user Skills: https://code.claude.com/docs/en/skills

Paths correspond to the **current local OS user**. Other OS accounts' HOME directories, cloud accounts and shared Agent organization profiles are not supported.

## 2. Mandatory account and profile boundary

All real operations require the caller to provide an existing absolute selected-home. In production the engine checks:

- POSIX-only with fcntl locking; root, elevated effective UID and sudo are refused.
- The supplied HOME must exactly equal **both** the passwd record's HOME for the actual OS UID and the current Python HOME (after canonical resolution). A changed HOME environment variable cannot impersonate another account.
- HOME must be owned by the current UID and must not be world-writable.
- Existing Host Skill directories and GASL state directories must not be symlinks and must be owned by the current UID without world-write permissions.
- The chosen Host and Skill slug must match the exact supported allowlist; any path collision, unsafe ZIP component or unexpected user file fails closed.
- A deterministic **profile identity SHA-256** binds the UID, canonical HOME path, filesystem device and inode. New ownership receipts, backup manifests, uninstall markers and transaction journals carry this account identity. The read path compares every saved identity against the current account and refuses copied/relocated history.

**Account isolation is OS-identity based, not a virtual multi-login system.** The tool does not permit editing another user's HOME even if its path is known. If HOME is moved or device/inode changes, the saved ownership state must be reconciled manually; it is not silently re-adopted.

## 3. Supported user-wide lifecycle

- Read-only Source, private ZIP and selected-target preview.
- New pinned Skill install with exact local TTY phrase, lock, verified staging, atomic activation and managed ownership receipt.
- Explicit **replace** only for unmodified GASL-managed Skills. Full retained backup, SHA-256 manifest and previous receipt.
- Read-only backup history listing with ownership and content rechecks.
- Restore a selected owned backup while preserving the currently active version as a **new** archive.
- Uninstall with retained current-version archive, uninstall marker and removal of the active receipt.
- Reinstall from a marker-linked backup with exact consent, never from an arbitrary unmanaged directory.
- Recovery following interrupted install, replace, restore, uninstall or reinstall, rolling back only when staged/target/backup bytes match the journal and preserving committed changes when verified.

Each write requires the exact TTY phrase **USER PROFILE ALL PROJECTS**, bound to selected Host, Skill name, Plan or backup identity and state binding. The Cursor phrase also contains **CURSOR-SYNC-RISK**. Every optional pinned download and private ZIP creation is separately approved before the final install approval. The HTTP Explorer never gains write access.

## 4. User-facing flow

From the GASL repository:

    # Read only — checks current OS HOME, Skill source and package
    ./gasl user-profile-wizard --host cursor --id GASL-SRC-EXACT_ID --selected-home "$HOME" --action preview

    # Explicit global installation with local TTY and separate approval steps
    ./gasl user-profile-wizard --host cursor --id GASL-SRC-EXACT_ID --selected-home "$HOME" --action install --download-if-missing

    # Managed version history and preview of uninstall
    ./gasl user-profile-install --host cursor --selected-home "$HOME" --action list-backups --skill-name exact-slug
    ./gasl user-profile-install --host cursor --selected-home "$HOME" --action preview-uninstall --skill-name exact-slug

For Codex or Claude Code change --host. To actually uninstall/restore/reinstall, request a preview first and copy its exact state_binding_id into the separate action with the necessary backup ID; the operation requires another local TTY phrase. Full usage is available through:

    ./gasl user-profile-install --help

The Explorer selected-Skill panel now offers **separate project-level and global user-level commands** for each supported filesystem Agent. Selection only creates text for copying; no local service POST endpoint can install.

## 5. Important Scope and synchronization warnings

- User-level Skills may influence every project opened by that Agent, **not just one selected workspace**.
- According to Cursor's current docs, Cursor may also discover Skills inside the user Codex or Claude Code directories. GASL can isolate receipts and backups by Host, but cannot guarantee isolated *visibility* inside a third-party Agent.
- Cursor's **Sync Skills for Cloud Agents** setting may transmit local Cursor user Skills to its cloud when enabled. GASL neither changes that setting nor uploads the Skill itself. A local file installation cannot guarantee data remains local if another app syncs the path.
- No downloaded third-party Skill script, dependency or prompt is executed by GASL's installer. But the installed Skill may later be consumed by a running Agent; selection and approval remain the user's responsibility.
- No claims of independently verified publisher identity, licensing compliance or live Cursor/Claude runtime discovery are made.

## 6. Implementation and test scope

Files:
- tools/user_profile_install.py — isolated user-profile ownership, exact account binding, transactional lifecycle, recovery and checks
- tools/user_profile_wizard.py — source readiness, per-step local TTY consent and user-scope private ZIP preparation
- tools/gasl.py — user-profile-install and user-profile-wizard commands with --selected-home
- tools/host_adapters.py — accurate project + current-user POSIX capability reporting, with live Host discovery caveat
- web/index.html — copyable current-user command and explicit Sync/visibility warnings
- tests/test_user_profile_install.py — account and backup lifecycle, HOME spoof refusal, cross-profile archive tampering, owner/mode, symlinks and failure recovery using only fake HOME roots
- tests/test_user_profile_wizard.py — existing/missing private ZIP, optional pinned download, decline/tamper and exact consent; always fake HOME
- tests/test_host_adapters.py, tests/explorer_workflow_smoke.js — new capability matrix and read-only browser behavior
- .github/workflows/gasl-user-profile-install.yml — isolated Linux CI that never writes to the real runner's HOME
- README.md, docs/ROADMAP.md, this report

Test fixtures temporarily patch only the internal profile-root validator to point into disposable directories and restore it afterwards. Separate tests call the genuine validator and prove it refuses an arbitrary temporary HOME and environment HOME spoofing. **No real user's HOME, running Agent, account or project Skill is changed during tests.**

## 7. Remaining work and limitations

- Windows: real writable installer and its transaction/locking implementation remain absent.
- Dynamic sandbox: only existing inert canaries, not general third-party Skill execution.
- Independent upstream repository/publisher/commit/blob/license verification remains separate.
- Public release is still blocked by the owner's unselected GASL project License and redistribution review.
- Cursor and Claude Code runtime discovery/manual tests are deferred at the user's request.
- OS filesystem ACLs, privilege escalation by hostile external processes and cloud synchronization behavior are **not certified** by local directory checks or POSIX locks.
- A process crash *before* the first durable journal may leave an orphan staging directory; automatic recovery does not delete arbitrary unknown files.

## 8. Verification evidence

Local targeted/full test outcomes, CI workflow run IDs, exact Git commit and public source-refresh status are appended only after observed.
