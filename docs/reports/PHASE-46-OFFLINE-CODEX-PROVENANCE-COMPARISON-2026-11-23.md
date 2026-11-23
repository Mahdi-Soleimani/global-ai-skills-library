# Phase 46 — Offline Codex Skill Provenance Comparison

**Date:** 2026-11-23
**Repository:** Mahdi-Soleimani/global-ai-skills-library
**Baseline:** b5a7805806520278551a5dca1e686774e4d4bbca (Phase 45)

## Objective

Explain precisely which aspects of a Codex Skill version are **locally measured**, which are **claims in GASL-owned receipts or backup manifests**, and which require **independent upstream verification**. Compare the local bytes of any two existing versions without pretending that equal hashes or matching Plan IDs establish upstream authenticity, license rights, historical project ownership, or safety.

## CLI (read-only)

    ./gasl provenance-compare --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL

    ./gasl provenance-compare --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL --left active --right EXACT_32_HEX_BACKUP_ID

    ./gasl provenance-compare --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL --left EXACT_BACKUP_1 --right EXACT_BACKUP_2 --format json

The CLI requires an explicitly chosen, existing Git project root and a valid Skill name. It refuses the user HOME, invalid/missing version IDs, single-sided selections, identical selections, and comparing active when the Skill is uninstalled. Default output lists all versions and their recorded provenance and verification gaps. A pairwise comparison adds local content equality, added/removed/modified file **counts**, and equality of locally recorded Plan references. It emits neither per-file names, raw instructions, file contents nor absolute project paths.

## Evidence matrix

| Evidence | Local check | Correct interpretation |
|---|---|---|
| SHA-256 inventory of active and backed-up files | **Verified at review time** | Receipt/manifest agrees with files currently observed locally; does not prove origin or safety |
| Overall content-manifest SHA-256 | **Computed** | Equality of ordered relative path and file hash pairs, not a cryptographic source signature |
| GASL receipt and Plan ID | **Locally recorded** | Claim exists in local records; not independently verified at upstream |
| Backup ancestry and path-bound Uninstall marker | **Validated locally** | Local continuity evidence, not definitive historical owner proof |
| Old unmanaged Skill | **No prior local GASL receipt** | Verified local bytes do not prove previous management |
| Legacy/orphaned Backup | **Owner unverified** | Manual attestation is required; even a historical upstream Plan is only a claim |
| Upstream repository owner and publisher | **NOT CHECKED** | Independent authoritative source verification is needed |
| Git commit and SKILL.md Git blob | **NOT CHECKED** | Independent authoritative commit/blob comparison is needed |
| License terms, third-party notices | **NOT CHECKED** | Independently review the original source |
| Skill instructions, dependencies and runtime safety | **NOT CHECKED** | Separate security and behavior review required |

The machine-readable report includes explicit upstream_verification_performed=false, upstream_authenticity_verified=false, network_requests_performed=false, and false write/consent/execution flags. It does not label a Skill trusted merely because local hashes agree.

## Manual attestation through multiple restores

A historically manually reconciled Skill can pass through several committed restore or reinstall operations. Later receipts may omit the original historical-owner warning. Phase 46 follows the recorded restored_backup_id ancestry through verified manifests and file SHA-256 inventories, enforcing cycle and depth guards. If it encounters historical_project_ownership_verified=false, it maintains the **manual-attestation-does-not-verify-historical-ownership** label. This is a read-only inference, not new proof of ownership, and does not change or extend the deployment code.

## Changed files

- tools/codex_provenance_compare.py — independent read-only version inventory verification, provenance evidence classifier, two-version comparison, human-readable formatter and historical-attestation ancestry tracking.
- tools/gasl.py — new provenance-compare action, left/right version selection and text/json modes.
- tests/test_codex_provenance_compare.py — synthetic disposable Git-project tests for installed/uninstalled/legacy records, pinned/unmanaged origin, privacy, equality and difference, manually attested restore history, tampering, blockers, offline operation and CLI.
- .github/workflows/gasl-private-install-bundle.yml — new focused tests and compiler coverage.
- .github/workflows/gasl-codex-transaction-e2e.yml — real Codex App Server inert lifecycle comparisons across installed/owned/legacy states.
- README.md, docs/ROADMAP.md, this report.

## Scope and limits

- **Only** an explicitly chosen existing Git project and exact Skill, no user HOME or global Agent profile.
- No network, automatic source fetch, upstream license/identity claims, Skill execution, dependency installation, model invocation, backup write, staging or approval.
- The SHA-256 evidence is valid only for the local files observed at review time. A malicious same-account process able to change both manifests and files may fabricate locally consistent data. This is not an independent signed audit log.
- No new restore action, hidden installation or shortcut around the existing exact local interactive TTY approval.
- Local version references and matching hashes are **not proof of identical authoritative upstream origin**.

## Verified local evidence

- 20 Phase 46-focused tests PASS.
- The exact modified real-Codex CI step succeeded on macOS against inert Skill content in a disposable Git project with isolated HOME and CODEX_HOME:
  - CODEX_REAL_OFFLINE_PROVENANCE_EVIDENCE_LIFECYCLES=PASS
  - REAL_USER_PROFILE_MODIFIED=FALSE; THIRD_PARTY_EXECUTED=FALSE
- Complete local regression results and GitHub Linux CI links will be recorded after observed execution, not assumed.

## Next technical direction

Consider an **optional, independent read-only upstream verification plan** for publisher and Git commit/blob checks. It must remain a separate source-validation workflow and never automatically turn a local receipt claim into trusted publisher identity or grant deployment authorization.
