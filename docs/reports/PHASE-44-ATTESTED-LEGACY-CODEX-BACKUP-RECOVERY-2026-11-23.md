# Phase 44 — Attested recovery of pre-Phase-43 orphan Codex project Skill backups

**Date:** 2026-11-23  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Starting main:** `7678d2a73d11022568e190f5748a942bd45b2a71`.

## Problem and historical compatibility

Phases 41–42 preserved old Skill directories in `.gasl-managed/backups/SKILL/BACKUP_ID`, but their completed Uninstall deleted the active GASL receipt without recording a durable ownership marker. As a result, historical archive files can survive while their project/Skill ownership is no longer attested by the application. Phase 43 adds such a marker to **new** Uninstalls, but it cannot retroactively invent one for pre-Phase-43 history.

**Fundamental limitation:** A matching manifest, SHA-256 inventory, upstream reference and version chain prove internal *consistency*, not that the backed-up files originally belonged to the selected project. A user can copy valid archives between projects. This phase does **not** claim cryptographically verified historical ownership and does **not** auto-adopt legacy archives.

## Implemented commands

```bash
# READ-ONLY: enumerate coherent orphaned backups
./gasl codex-project-install --action audit-legacy-backups \
  --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL

# READ-ONLY: receive path/history-bound preflight ID for a specific backup
./gasl codex-project-install --action preview-legacy-reinstall \
  --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL \
  --backup-id EXACT_32_HEX_ID

# Real install: local interactive exact attestation required
./gasl codex-project-install --action reinstall-legacy-backup \
  --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL \
  --backup-id EXACT_32_HEX_ID --state-binding-id EXACT_PREVIEW_BINDING

# Only for a journaled interruption
./gasl codex-project-install --action recover \
  --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL
```

The attestation challenge includes the Skill name, selected Backup ID and exact binding and ends with `REINSTALL-ONLY-IN-THIS-PROJECT`. Neither the preview nor any previous user message authorizes a real project write. A non-interactive CLI invocation is refused.

## Read-only audit and binding

- Explicit **existing Git project root**, separate from the real user HOME, already required by previous phases.
- Destination `.agents/skills/SKILL` must be absent, including no symlink; there must be no active receipt, pending journal or Phase-43 uninstalled ownership marker.
- Enumerates the project's own `.gasl-managed/backups/SKILL` directory only. Every entry must be a unique 32-hex Backup directory paired with its exact JSON Manifest; no unexplained files, symlinks or excess entries.
- Each manifest and its contents must validate against the existing GASL record schema and complete SHA-256 inventory. Root `SKILL.md` is required, with simple frontmatter naming the exact selected Skill.
- Determines ordered ancestry from `previous_receipt.backup_ids`. The chain must contain **all** archived IDs, with each successive manifest referencing precisely its preceding version IDs in order. Missing/foreign/cyclic/ambiguous histories are rejected; no best-guess adoption.
- The preflight binding hashes the canonical selected target path, the chosen Backup ID, every verified Manifest's identity and inventory, and explicit absence of active ownership. Before writing, the same evidence is rechecked under the project-local POSIX lock.
- The audit reports `historical_project_ownership_verified=false` and `manual_ownership_attestation_required=true`. It emits no local absolute path or full file contents.

## Explicit opt-in installation and durability

1. The chosen verified backup is **copied** from historical storage into a private staging directory outside Codex discovery, checking every file hash and final inventory. All original Backup directories remain untouched.
2. After the exact local human TTY attestation, a durable journal records selected Backup/Manifest, full historical ID chain and its digest, exact preflight binding and new receipt.
3. With target still unoccupied and every historical file/Manifest unchanged, the stage directory is atomically renamed into the project Skill location.
4. A new GASL-managed receipt is persisted. It always identifies this origin as `source_kind=unmanaged` and an explicitly synthetic local Plan ID. It records `manual_ownership_attested=true`, `legacy_identity_derived=true`, `historical_project_ownership_verified=false` and the selected Backup ID. Historical upstream Plan IDs, if present, remain *informational only* and are never recertified.
5. The receipt inherits the **entire exact historical Backup chain**. Future explicit Uninstall archives the currently active version and creates a genuine Phase-43 ownership marker for the **newly managed lifecycle**, without retroactively proving earlier ownership.

### Crash recovery

- If activation or receipt writing was interrupted and the journal is intact, `recover` checks all original Backup manifests, ancestry, inventory SHA-256, journal identity, target and stage.
- **Before commit:** removes only an exactly verified activated/staged copy; original archives remain unchanged.
- **After commit:** verifies new receipt and activated files, then finalizes the transaction and clears journal.
- Unexpected user edits, modified manifests, mismatched history, nonregular target entries and competing receipts cause a fail-closed refusal. No unknown content is deleted.

### Guard against accidental bypass

Normal `preview`/`install` returns ineligible when unclaimed legacy Backup evidence exists, even if the install destination is empty. Ordinary replacement of an unmanaged directory is likewise refused when unclaimed historical Backup files remain. This prevents silently bypassing the very Backup history the user may want to preserve.

## Files and boundaries

- `tools/codex_legacy_reconcile.py`: standalone read-only audit, preview, manual attestation, controlled reinstatement and journaled recovery.
- `tools/codex_project_install.py`: distinct legacy receipt/journal schema branches, recovery route, fresh-install and replace guards.
- `tools/gasl.py`: three explicit CLI actions.
- `tests/test_codex_legacy_reconcile.py`: positive recovery, historical managed/unmanaged source, missing/foreign/ambiguous chains, symlinks, frontmatter mismatch, stale bindings, noninteractive denial, crash injection and edit preservation.
- `.github/workflows/gasl-private-install-bundle.yml`: synthetic tests and compiler coverage.
- `.github/workflows/gasl-codex-transaction-e2e.yml`: real Codex App Server discovery lifecycle using a synthetic, manually orphaned fixture in an isolated temporary project.
- `README.md`, `docs/ROADMAP.md`, this Phase 44 report.

Nothing runs an archived Skill, its scripts, external dependencies, MCP server or model request. This feature remains **Codex project scope only**, for POSIX macOS/Linux. It does not import files from another user's project, infer ownership from a license, or support unattended installs. Content may be untrusted despite passing byte-integrity checks.

## Local acceptance

- **123 focused tests PASS**, covering the new 20-test Phase-44 suite and relevant phases 40–43.
- **549 Python tests and 236 subtests PASS** locally (excluding only optional `tests/test_mcp_server.py` because the Mac's system Python lacks the `mcp` package). All workflow YAML parsing, Python compile checks, and whitespace validation passed.
- **Real Codex macOS E2E PASS:** the exact GitHub Actions project lifecycle script ran with the real Codex CLI in disposable Git/HOME/CODEX_HOME. After standard uninstall/reinstall tests, the script constructed an inert legacy-style orphan, audited it, explicitly attested through a test-only reader, installed it, observed the restored inert Skill via actual `skills/list`, and removed it with the new Phase-43 ownership marker. No personal Codex profile or real user project changed. Tests do not claim real-user approval.
- No third-party Skill payload was executed and no private ZIP was published.

## CI/publication

GitHub CI run IDs, conclusions, final commit SHA and any automatic metadata commit will be added **after live publication and checks**. Local successes are not presented as remote verification.

## Suggested next work

Prefer auditing and improving the lineage/ownership UI and creating a clear user-facing manual review guide, rather than introducing unrestricted backups imports, hidden installation or automatic provenance claims. Any future user-scope Codex writes require an independent approval and safety review.

## Verified GitHub publication and Linux CI

- Feature commit: [`d090a97e3def79b99f452f770097dc641ecdc146`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/d090a97e3def79b99f452f770097dc641ecdc146), pushed to `main` after a nine-file scope allowlist, staged whitespace check, sensitive-pattern scan and full local tests. No private ZIP, personal filesystem path, credentials, or user Skill payload was published.
- [Real Codex lifecycle — Run `45201198006`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45201198006): **completed / SUCCESS**. Linux job `Exercise real Codex project restore plus attested legacy backup recovery` passed against inert disposable content. Real Codex App Server observed the manually attested legacy backup after controlled reinstallation, and the following removal. No third-party code or real user profile was involved.
- [Private ZIP and Installer safety — Run `45201197796`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45201197796): **completed / SUCCESS**, including Phase 44 synthetic reconciliation and refusal tests.
- [Full catalog Refresh and regression — Run `45201197849`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45201197849): **completed / SUCCESS**, with **555 passed** reported in the dependency-equipped GitHub runner. The metadata summary confirmed **57 source repositories** and **4,431 source records**. The source refresh published a separate metadata-only commit [`c7e9b15`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/c7e9b15d280c0163d9156c3c621ce936e7b1709a).
- That metadata-only commit was fetched and fast-forwarded into the local `main`, preserving project code and a clean working tree without force-pushing.

**Phase 44 acceptance:** manual-attestation legacy recovery and its fail-closed safeguards are implemented and verified on macOS and Linux with real inert Codex discovery. Historical ownership remains **unproven**; the product makes no contradictory ownership claim or inference.
