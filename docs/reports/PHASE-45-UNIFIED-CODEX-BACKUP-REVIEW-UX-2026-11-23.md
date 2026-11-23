# Phase 45 — Unified Codex Backup Review UX

**Date:** 2026-11-23  
**Repository:** Mahdi-Soleimani/global-ai-skills-library  
**Base main:** 265697d559c82e96015d9d5b6350db9deed204a3

## Goal

Make the existing Phase 40–44 backup lifecycle understandable and safer to operate by creating one consistent, **read-only** review, instead of requiring users to guess among different list / preview / recovery commands. Keep all existing exact TTY approval phrases, preflight binding, project root selection, POSIX lock, integrity validation, crash recovery, and provenance limits unchanged.

## CLI

    # Review a single explicitly selected existing Git project Skill
    ./gasl backup-review --selected-root /ABSOLUTE/GIT/PROJECT --skill-name SKILL

    # Select an exact verified backup; still READ-ONLY
    ./gasl backup-review --selected-root /ABSOLUTE/GIT/PROJECT --skill-name SKILL --backup-id EXACT_32_HEX_BACKUP_ID

    # Scriptable, machine-readable mode; still READ-ONLY
    ./gasl backup-review --selected-root /ABSOLUTE/GIT/PROJECT --skill-name SKILL --format json

The default output is concise human-readable text. Each reviewed Backup includes its exact ID, file count, cryptographic hash/inventory integrity status, **recorded** source reference (not independent upstream certification), ownership evidence category, whether it is eligible for recovery, and whether it was the last active Skill before Uninstall. A selected Backup also includes the exact state binding and the correct **existing** write action, with a reminder that a real local interactive TTY confirmation is mandatory.

The proposed command uses the explicit environment variable GASL_SELECTED_PROJECT rather than leaking the selected absolute root path. Users must set the variable to the intended existing Git project root before executing any write command. The reviewer never selects a project implicitly.

## Lifecycle decision table

| Detected lifecycle | Read-only source | Permitted follow-up (NOT executed by review) | Ownership note |
|---|---|---|---|
| Installed with GASL receipt | Existing list_backups + preview_restore | restore-backup | Local receipt evidence, not upstream safety proof |
| Uninstalled with Phase 43 marker | Existing list_uninstalled_backups + preview_reinstall | reinstall-backup | Locally project-bound marker, subject to file integrity validation |
| Pre-Phase-43 orphaned legacy backups | Existing audit_legacy_backups + preview_legacy_reinstall | reinstall-legacy-backup | Original project ownership **not proven**, independent human attestation required |
| No backups | Read-only explicit selected project paths | None | No recoverable Backup found |
| Pending transaction | Existence of local journal only, no guessing | Inspect journal and optional existing recover | Recover itself can fail closed |
| Unmanaged/occupied target, missing target with receipt, unsafe marker | No ownership/adoption inference | None | Manual investigation required |

The display never equates SHA-256 file integrity with project ownership or with remote upstream source authenticity. Even after a Phase 44 manual attestation created a new managed receipt, the reviewer still reports historical_project_ownership_verified=false.

## Data and privacy guarantees

- Scope remains **one explicitly selected existing Git project** and one valid Skill slug. No HOME scans, multi-project discovery or implicit global configuration.
- Read-only operation: never creates directories, writes receipts, stages ZIP content, copies archived files, executes a downloaded Skill, runs model turns, or invokes real install/restore/recover.
- Returns relative target names and **never emits the absolute project path** in either JSON or text.
- All displayed backup choices come exclusively from the existing proven list/audit implementations, not a second bypass of their hash and ancestry checks.
- A selected ID is validated against the full reviewed history. Byte-identical active/backed-up versions are not offered as pointless restore operations.
- A pending journal blocks all backup selection; unknown/foreign/edited files and invalid project paths fail closed. Existing receipts and Phase 43 markers are checked; the viewer refuses inconsistent retained ownership history.
- No approval is ever granted in a report. The next command must separately revalidate the exact state binding under lock, demand an exact live TTY phrase and obey existing historical-ownership requirements.

## Implementation and tests

Changed:
- tools/codex_backup_review.py — read-only state resolver, source and ownership classifications, decision policy and human-readable formatter.
- tools/gasl.py — a single backup-review CLI with optional backup-id and format=text|json.
- tests/test_codex_backup_review.py — 23 synthetic tests covering all lifecycle states, provenance, selected command, read-only behavior, privacy, invalid/foreign backups, tampering, exact TTY denial and unsafe or interrupted states.
- .github/workflows/gasl-private-install-bundle.yml — review module and tests in synthetic CI, triggers and compile targets.
- .github/workflows/gasl-codex-transaction-e2e.yml — same read-only review tested at installed, uninstalled and legacy states within a disposable Git project with the **actual** Codex App Server discovery lifecycle.
- README.md, docs/ROADMAP.md and this report.

Local evidence:
- 23 dedicated review unit tests PASS.
- The exact enhanced real-Codex CI lifecycle script executed successfully on macOS against an inert synthetic Skill in a disposable Git project and isolated Home/CODEX_HOME, including the legacy ownership warning.
- Full local regression, CI run IDs and final Git revision will be recorded below only after real verification.

## Deliberate non-goals

No TTY approval shortening, consent weakening, automatic restoration, automatic ownership inference, scanning of all stored Skills, browser UI, interactive form wizard, package execution, or real user profile installation was introduced. This phase is intentionally a small UX enhancement based on already safety-tested flows.

## Next improvement

Potential separate follow-up: a small, **read-only** provenance comparison explaining exactly which fields are verifiable locally and which require upstream source verification, with a compact documentation-first walkthrough for users handling multiple backups.

## Verified local test evidence

- **23 dedicated Phase-45 review tests PASS.** They cover all three historical lifecycle states, selection/preflight binding, text and JSON output, no project-path leak, historical provenance refusal, tampered files and ownership marker, failed/missing receipts, pending recovery journal, and a real noninteractive write-command denial.
- **146 focused installer + Backup review tests PASS** (`tests.test_codex_backup_review`, `tests.test_codex_legacy_reconcile`, `tests.test_codex_uninstalled_restore`, `tests.test_codex_project_install`, `tests.test_install_bundle`, `tests.test_host_format_review`).
- **572 local tests PASS, 236 subtests PASS** with `python3 -m pytest -q --ignore=tests/test_mcp_server.py`. The local macOS Python environment lacks the optional MCP dependency; the dependency-equipped GitHub CI will run that module too.
- The exact modified GitHub Actions E2E step was executed on macOS using the actual Codex CLI and **PASS**: it reviewed installed, uninstalled-owned, and orphaned legacy states, compared each preview to its underlying phase implementation, and verified Skill discovery through real `skills/list` before/after controlled inert fixture operations.
- Both GitHub Actions workflows parse as valid YAML; Python source compiles, and `git diff --check` passes.
- **All actual write operations in test setup occurred only in disposable Git project roots with temporary isolated HOME/CODEX_HOME**, never a user project or actual personal Agent profile.

**GitHub status at this point:** feature code and tests are validated locally. Do not infer a successful Linux workflow or published commit before live verification; record exact Run IDs and Commit SHA after publication.

## Verified GitHub publication and Linux CI

- Feature commit [a969e42fa19db865332b570cd64448a9540516c1](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/a969e42fa19db865332b570cd64448a9540516c1) was pushed normally to main after an eight-file staged scope audit, sensitive-pattern scan, whitespace check and successful macOS tests. No private bundle, personal Skill content or credentials were published.
- [Real Codex App Server lifecycle Run 45205397207](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45205397207): **completed / SUCCESS**. The Linux step exercising the **actual Phase-45 read-only reviewer** across installed, project-marker-owned and manually attested orphan states passed, including correct next-command selection and no absolute project path disclosure. The inert Skill was discovered via the real Host protocol.
- [Private Skill ZIP / Installer safety Run 45205396762](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45205396762): **completed / SUCCESS**, including all 23 new Phase-45 read-only, integrity and no-approval regressions.
- [Full source-catalog Refresh / Regression Run 45205396708](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45205396708): **completed / SUCCESS**, **578 passed** in the dependency-equipped GitHub runner. Catalog refresh confirmed **57 source repositories** and **4,431 source records**.
- The automatic metadata-only Refresh commit [b7e8f4efa75be86b116c9bf434ce881b938a80c3](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/b7e8f4efa75be86b116c9bf434ce881b938a80c3) was fetched and fast-forwarded locally without a force push, preserving the updated registry files, source code and a clean local working tree.

**Phase 45 acceptance:** The user-facing review is only a read-only presentation/selection layer. It **did not** add or exercise writes to a real user Agent profile, grant installation permission, execute Skill contents, certify upstream trust or claim historical ownership from local file hashes.
