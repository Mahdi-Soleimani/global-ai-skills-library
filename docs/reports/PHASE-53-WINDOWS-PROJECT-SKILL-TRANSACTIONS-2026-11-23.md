# Phase 53 — Native Windows project Skill transactions

**Date:** 2026-11-23  
**Repository:** Mahdi-Soleimani/global-ai-skills-library  
**Scope:** Windows project-level filesystem installation, using inert synthetic Skill packages and disposable Git roots. Real Windows user profiles and actual Agents are not used.

## 1. Goal and explicitly limited deliverable

Extend the already-shipped transactional project installer to Windows using native OS locking. Support fresh install, managed replacement with retained complete Backup, list/restore, archived uninstall/reinstall, and recovery of interrupted transactions for three project hosts:

- Codex: .agents/skills/SLUG/SKILL.md
- Cursor: .cursor/skills/SLUG/SKILL.md
- Claude Code: .claude/skills/SLUG/SKILL.md

On Windows, all three use the host-scoped transaction engine and store owned receipts, journals and backups under project/.gasl-managed/hosts/HOST/. **This does not overwrite or migrate** the existing legacy POSIX Codex receipts under project/.gasl-managed/. An existing same-name Skill without a verified host-scoped ownership receipt is refused, never silently adopted.

**Windows User Scope remains explicitly unsupported.** It requires Windows token SID, profile path and NTFS DACL/ownership checks separate from project Git-root checks. The existing POSIX current-user engine remains unchanged and refuses Windows execution. No real Host discovery, sandbox code execution, project License publication or privileged filesystem installation is attempted.

## 2. Platform-level changes

- tools/transaction_file_lock.py: standard-library cross-process exclusive lock using POSIX flock on macOS/Linux or Windows msvcrt.locking in an exact one-byte region. Windows uses bounded nonblocking retries, fails closed on lock conflict, preserves lockfile and file descriptor for the full transaction. No external package is introduced.
- tools/host_project_install.py: reuses the existing transaction path for Windows with a native project lock; permits Codex **only on Windows** while preserving POSIX Codex's established installer. No change to the format of existing POSIX receipts.
- tools/host_target_preflight.py: rejects Windows NTFS Junctions in target paths, alongside regular symlinks.
- tools/fixture_bundle_install.py: the full SHA-256 regular-file inventory and verified deletion path now reject Junctions. Private bundle extraction blocks Windows reserved device names, alternate-data-stream colon, forbidden characters and trailing dots/spaces.
- tools/codex_project_install.py: project-root and GASL-state path checks reject junctions, without relaxing its existing POSIX-only Codex installer.
- tools/queue_ingest.py: fcntl is now optional **for module import only**, so Windows ZIP validation works. Windows queue ingestion remains **disabled and fail-closed** because that command's separate lock was not ported. Local downloaded-package verification is still required before any transaction.
- tools/gasl.py: host-project-install and host-project-wizard allow host codex/cursor/claude-code at the parser; the underlying host gate only permits Codex through this engine on Windows.
- web/index.html and tests/explorer_workflow_smoke.js: Explorer provides an additional copyable Windows PowerShell command using Python, and clearly labels Windows User Profile as unavailable.

## 3. Windows CLI

In PowerShell, from the GASL repository:

    $env:GASL_SELECTED_PROJECT = "C:\path\to\an\existing\git-project"
    python tools/gasl.py host-project-wizard --host codex --id GASL-SRC-EXACT_ID --selected-root "$env:GASL_SELECTED_PROJECT" --action preview
    python tools/gasl.py host-project-wizard --host codex --id GASL-SRC-EXACT_ID --selected-root "$env:GASL_SELECTED_PROJECT" --action install --download-if-missing

Change --host to cursor or claude-code. The first command performs no write. Real installation requires separate explicit approvals for any missing pinned download, private ZIP preparation and final exact TTY phrase bound to the chosen destination/source state. No browser endpoint can write to the Host paths.

For already installed GASL-owned Skills:

    python tools/gasl.py host-project-install --host codex --selected-root "$env:GASL_SELECTED_PROJECT" --action list-backups --skill-name exact-slug
    python tools/gasl.py host-project-install --host codex --selected-root "$env:GASL_SELECTED_PROJECT" --action preview-restore --skill-name exact-slug --backup-id EXACT_ID

Use restore with the fresh state_binding_id from the preview and a local TTY phrase. Uninstall, reinstall and recovery use the same low-level CLI, protecting the complete saved inventory and previous receipt.

## 4. Windows security and operational limitations

The lock protects against **concurrent cooperating GASL processes**. It cannot prevent a separate application or privileged process from changing files. Every mutation revalidates target, hash-backed package and owner records under the lock. Windows rename into a missing target on a single filesystem is used for directory moves; the tool never silently overwrites a nonempty target. Content or archive drift causes fail-closed refusal and retained journal for explicit recovery.

**Crash consistency does not imply full power-loss durability:** Windows directory fsync is not available using the existing portable Python primitives, and NTFS, network-share and third-party sync behavior may vary. Network drive atomicity and cross-process external locking are not certified. A rename can also fail if another application holds handles open; journal recovery preserves the previous version when exact invariants still hold.

NTFS Junctions and unsafe ZIP component names are rejected. Windows ACL owner/protection checks for user-level HOME are **not implemented**, so that scope must not be enabled simply because project-scope tests pass. There is no change to real Agent configuration and no execution of third-party Skill instructions.

## 5. Automated tests and evidence

- tests/test_windows_project_transactions.py: native Windows-only tests using disposable Git roots, inert pinned private ZIPs, actual Windows filesystem operations, three Host destinations, retained backups, rollback, restored version, exact TTY challenge, retained user edits, cross-process msvcrt lock, Junction refusal and reserved filename rejection.
- .github/workflows/gasl-windows-project-install.yml: windows-latest / CPython 3.13 CI, native tests plus existing safe bundle/target fixtures and a check that no real Agent directory was created in the repository.
- Regression tests on macOS/Linux ensure no behavior change to earlier POSIX project and user transaction flows.
- Manual real-host testing and human relevance adjudication remain deferred at the user's request.

Windows CI outcome, final feature commit and source catalog status will be added only after observed. The milestone should not be marked confirmed until the native Windows runner passes the entire dedicated test suite.
