# Phase 17 — Selected Skill Offline Security Gate

**Date:** 2026-11-22

**Repository:** `Mahdi-Soleimani/global-ai-skills-library`

**Scope:** Extend the existing local-only, source-pinned downloader with automatic static scanning, pinned content verification, and safe offline re-audit. No third-party Skill is installed or executed.

## 1. Baseline problem

Prior to this phase, `gasl download --execute` verified upstream Git blob hashes and placed the selected package in the ignored local catalog, but did **not** trigger `static_scan.py`. The old static scanner also trusted `source.json` file references too broadly when opening local paths. As a result, local downloads and security reports were separate manual steps and an untrusted local manifest could in principle direct a scanner to inspect a file outside the package.

Security evaluation is deliberately distinct from installation approval. This phase does not add dynamic execution, a sandbox, an installer, or automated security approval.

## 2. Implementation

- `tools/security_gate.py` (new) implements `audit_local_package(source_record_id, root=...)`, requiring an existing verified commit-pinned source record and a previously downloaded package.
- `tools/on_demand.py` now calls this audit **after** successful selected-package ingestion while holding its existing local ingest lock. The dry-run planning mode makes no changes and does not scan files. A failed integrity audit returns `status=blocked_integrity_failure`.
- `tools/gasl.py` exposes `./gasl audit --id SOURCE_RECORD_ID` to recheck an already-downloaded package entirely offline.
- The audit verifies the selected repository, commit, exact Skill path, package completeness, and the actual `SKILL.md` bytes against the independent Git Blob SHA-1 in the current source catalog (not merely a self-declared SHA-256 from the package's metadata).
- `tools/static_scan.py` accepts an explicit workspace root, rejects manifest-referenced files outside the selected package, forbids symlinks and nonregular filesystem entries, checks declared file lengths and SHA-256 hashes, and detects additional files missing from the inventory. The scanner also rejects symlinked source manifests and unsafe parents.
- All results keep `installation_allowed=false`, `execution_allowed=false`, `manual_review_required=true` and `sandbox_executed=false`, irrespective of the static scan outcome. A scan without findings returns `no_obvious_static_flags_not_approved`, not an approval.
- Detailed security evidence is written to `reports/security/on-demand/`, which is ignored by Git; it is not redistributed in the public source catalog or GitHub Actions.

## 3. Legacy compatibility, without deleting or moving packages

The real local package audit exposed two historical formats requiring safe compatibility handling:

1. **Legacy download checkpoints:** 16 older Anthropic packages retained a local `.gasl-download-checkpoint.json` sidecar. The scanner initially (correctly, before recognition) treated these undeclared files as inventory failures. This sidecar is now recognized only when its filename is exact, it is a regular file no larger than 256 KiB, and its repository, commit, Skill path and entire file map match the authoritative `source.json` rows. A tampered or unmatched sidecar still fails inventory verification. These files are **not deleted** and are never executed.
2. **Legacy folder naming:** one locally downloaded Cloudflare package used the older directory name `<skill>@<commit>` instead of the current `<skill>__<path-hash>@<commit>`. The audit now accepts a **unique** earlier folder only when its `source.json` matches the exact repository, commit, Skill path and completeness requirements; multiple matches are rejected. No files are moved or replaced.

Older packages may omit `skill_md_blob_sha` in their stored metadata. This is no longer an automatic rejection: the audit checks the actual main SKILL.md bytes against the pinned catalog hash first, and backfills the verified field only after successful comparison. A mismatching blob cannot be accepted by rewriting the cached SHA-256.

## 4. Live offline audit results

A controlled, **offline, read-only-contents** audit was run on existing downloaded packages. (The scanner updates local `source.json` with the latest scan status, and writes private reports; it does not run Skill code.)

| Check | Result |
|---|---:|
| Existing local packages | 63 |
| Exact source identity still matches current pinned catalog | 38 |
| Historical packages with no matching current source identity | 25 (not scored as current-pin verified) |
| Current-pin packages audited | 38 |
| Successful integrity + pinned main Git Blob checks | 38/38 |
| Packages with no obvious static flags, **not approved** | 30 |
| Packages requiring manual security review | 8 |
| Integrity failures after compatibility fixes | 0 |
| Audit errors after compatibility fixes | 0 |
| Validated legacy downloader checkpoints | 16 |
| Static heuristic findings across 38 packages | 45 |
| High-confidence heuristic signals | 1 |
| Skill installations / executions / sandbox executions | 0 / 0 / 0 |

**Review-needed packages (signals, not adjudicated malicious behavior):**

| Package | Findings | Observed rule families |
|---|---:|---|
| claude-api | 9 | SECRET_STORE_ACCESS, SECRET_TO_HTTP_BODY, NETWORK_ACCESS |
| docx | 5 | SHELL_OR_PROCESS_SPAWN, SECRET_STORE_ACCESS |
| pptx | 4 | SHELL_OR_PROCESS_SPAWN, SECRET_STORE_ACCESS |
| skill-creator | 5 | SHELL_OR_PROCESS_SPAWN, SECRET_STORE_ACCESS |
| web-artifacts-builder | 3 | PACKAGE_INSTALL |
| webapp-testing | 2 | SHELL_OR_PROCESS_SPAWN |
| xlsx | 5 | SHELL_OR_PROCESS_SPAWN, SECRET_STORE_ACCESS |
| security-audit | 12 | SHELL_OR_PROCESS_SPAWN |

The single high-confidence rule signal is `SECRET_TO_HTTP_BODY` in `claude-api`. It is a **heuristic flag requiring contextual manual review**, not evidence of confirmed credential exfiltration. All eight remain unapproved. The other 30 are also unapproved; a clean static scan cannot prove runtime safety.

Raw per-package reports, including potentially untrusted snippets, are retained **only** under the ignored `reports/security/on-demand/` local directory. The batch summary is `reports/security/on-demand/PHASE17-OFFLINE-BATCH-2026-11-22.json` and is not committed.

## 5. Tests

- Added `tests/test_security_gate.py` with 14 test cases: verified and tampered Git blobs, missing/corrupt metadata, path escape, symlink, unlisted file, suspicious code, legacy pinned folder and downloader checkpoint verification, plus fail-closed behavior for modified checkpoint metadata.
- Updated `tests/test_on_demand.py` to assert the integrated static scan runs after actual selected ingestion, not in plan mode, and never permits installation or execution.
- Full Python suite: **217 tests passed, 6 subtests passed** with no failures.
- No new Python dependencies were introduced.

## 6. Limitations / next phases

1. **Dynamic sandbox remains blocked:** no enforced empty/network-denied sandbox is available or verified for untrusted Skill execution. None was simulated or claimed.
2. **Installation lifecycle remains gated:** creating a reviewable local package and report is distinct from approving/installing it. A later implementation needs explicit user consent, Agent compatibility, rollback/removal and continued policy checks before enabling installation.
3. **Historical local packages:** 25 old package identities cannot be attested against the refreshed current source catalog; they remain retained in the ignored local cache but were excluded from the current-pin verified tally. Do not silently migrate or re-pin them.
4. **Heuristic false positives/negatives:** static rules are triage only; inspect pinned content manually or through a verified sandbox. The current 8 flagged packages were *not* declared malicious.
5. **Platform testing:** the current full-package downloader uses `fcntl`/macOS or Linux semantics; Windows-specific behavior remains unverified.

## 7. Acceptance and provenance

**PASS — Phase 17 static gate:** selected downloads are automatically followed by local static verification; `gasl audit --id` works offline; path/hash/extra-file and legacy compatibility tests pass; all 38 current-pin packages were audited with zero integrity failures and zero execution. No package is approved or installed.

**NOT CLAIMED:** real sandbox execution, dynamic validation, absence of vulnerabilities, install approval, complete security coverage for the entire 4,431-record source catalog.

All changed code, tests, and summaries are versioned in Git; raw local third-party packages and detailed per-file evidence remain ignored under `catalog/` and `reports/`. Any future implementation must keep phase reports under `docs/reports/`.
