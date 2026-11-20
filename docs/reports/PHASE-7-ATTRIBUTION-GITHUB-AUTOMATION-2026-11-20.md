# Phase 7 — Third-party attribution and GitHub Actions automation

Date: 2026-11-20
Repository: Mahdi-Soleimani/global-ai-skills-library
Baseline commit: f83c45b

## Goal

Keep every discovered skill represented in GASL regardless of its license, preserve upstream attribution and provenance, and automate safe public mirroring of package contents only when a redistribution gate passes. The automation must not claim authorship or exclusive ownership and must not require the user's Mac to remain online.

## Implemented

### 1. Complete source index

- Expanded discovery targets to 57 canonical repository targets: 55 historical canonical sources plus two newly selected sources. A historical redirected alias was merged into its canonical repository.
- Rebuilt a public-safe discovery state from the historical 56-entry repository verification snapshot, preserving the union of all 4,214 historical paths. Historical entries without a live Commit SHA are explicitly unpinned.
- Added registry/source-catalog.json, registry/source-catalog.csv, and registry/source-catalog-summary.json.
- The current source catalog contains 4,277 records: 4,214 historical repository/path references plus 63 immutable downloaded-package revisions. It is not a count of globally unique skills.
- Every record carries source repository, publisher/owner, original path, direct source URL, observed license metadata, commit/tree/blob identifiers when available, source status, content status, third-party ownership, and an explicit no-exclusive-ownership flag.
- Individual original authors are not inferred from repository ownership. original_author remains null unless there is actual evidence.
- All 4,214 historical paths remain represented regardless of license. Two new repositories are present as refresh targets pending their first successful live tree enumeration.

### 2. License and attribution model

- Updated config/policy.json with a documented SPDX allowlist for automated public mirroring, required upstream license/notice evidence, and explicit unknown-license handling.
- The discovery pipeline records repository license metadata, root/nested LICENSE/COPYING/NOTICE paths, exact license-file blob SHAs, and commit-pinned source links.
- The package planner now bundles applicable ancestor and in-package license/notice files into the package while preserving their original bytes and recording original source paths.
- Each downloaded package records ownership=third_party, original_author=null unless evidenced, gasl_claims_exclusive_ownership=false, source_url, license URL, and license evidence.
- Unknown, missing, proprietary, custom, and non-allowlisted licenses remain in the complete source catalog. They are not automatically copied into the public content mirror. Attribution and a public source URL alone are not treated as redistribution permission.

### 3. Public GitHub catalog

- Added tools/build_public_catalog.py.
- Public mirror requires an allowlisted SPDX identifier, bundled applicable license/notice evidence, complete pinned package inventory, exact local hashes, and a completed static scan.
- Original files are copied unchanged. Each public package receives ATTRIBUTION.md and ATTRIBUTION.json with repository, original path, commit, license, license evidence, and a no-ownership disclaimer.
- Public package versions are immutable and indexed by repository/path/commit. Older versions remain in the catalog.
- Security status is displayed in the catalog index but is not described as installation approval. No package is installed or executed.
- The existing 63 local packages did not pass the new evidence gate: 20 were outside the public-mirror allowlist and 43 did not have applicable license evidence bundled. Consequently the current public content mirror has zero packages; all source records remain in the complete source index.

### 4. GitHub Actions automation

Added .github/workflows/gasl-refresh.yml:

- Daily schedule at 07:23 UTC and manual workflow_dispatch.
- Runs the regression suite.
- Refreshes all configured repositories with GITHUB_TOKEN, retry handling, and Commit/Tree/Blob pins.
- Processes a bounded public-redistributable batch: at most two packages per repository, 120 files, and 50 MiB per run.
- Runs static scan, rebuilds the metadata registry, builds the public content mirror and source catalog, then commits/pushes changed metadata and eligible package files to main.
- Uses contents: write; no R2 credentials or Mac availability are required.
- Preserves historical registry metadata when running on an ephemeral GitHub Actions runner where local-only catalog files are absent.
- The runner is ephemeral: the complete source index and public-catalog content are tracked; local catalog/quarantine files are not uploaded.

### 5. CI and registry resilience

- discover.py now retries transient GitHub API network/rate-limit failures and accepts a 1–100 repository refresh limit.
- Successful discovery observations persist commit/tree/path/blob/license evidence in registry/discovery-state.json.
- Failed refreshes retain previous queue entries as stale fallbacks, which the downloader explicitly refuses to ingest.
- pending queue completion is based on locally present packages or actual public-catalog index entries, not merely stale registry metadata.
- build_registry.py preserves historical package metadata on clean CI runners instead of erasing records whose ignored local package files are not present there.
- build_public_catalog.py is idempotent and fails closed on hash, inventory, license-evidence, or attribution conflicts.

## Current measured state

| Metric | Result |
|---|---:|
| Configured source repositories | 57 |
| Historical canonical repositories | 55 |
| Historical skill paths | 4,214 |
| Source catalog records | 4,277 |
| Immutable downloaded revisions | 63 |
| Local package files | 640 |
| Local package bytes | 13,583,889 |
| Local skill candidates | 59 |
| Evaluation fixtures | 4 |
| Packages requiring manual security review | 10 |
| High-confidence static signals | 2 |
| Publicly mirrored packages | 0 |
| Install-approved / installed / executed | 0 / 0 / 0 |
| Regression tests | 55 passed |

The four independent research report archives were re-hashed and remain byte-identical to their recorded SHA-256 values. No original research dataset was merged, rewritten, or reconstructed.

## Validation

- 55/55 project tests passed.
- Python compilation passed for discovery, queue ingestion, registry builder, source catalog builder, and public catalog builder.
- GitHub Actions YAML parsed successfully; schedule, workflow_dispatch, contents:write, and refresh job were verified.
- Static scan completed for all 63 local packages. All package file integrity checks passed. Heuristic scanner still reports ten packages for manual review and two high-confidence signals; no code was executed.
- Public catalog builder completed and correctly skipped all 63 local packages under the new license/evidence gate.
- Source catalog invariants verified: 4,277 records, 4,214 distinct historical repository/path references, 63 immutable revisions, and 57 configured targets.
- Four independent original research archive hashes passed.

## Known limitations / next gate

- The last local Mac API refresh attempt verified Microsoft (215 paths) but failed on nine other targets with TLS EOF errors. The remaining 47 targets were not attempted in that local run. The GitHub Actions runner is expected to perform the full refresh with its token; the first real Actions run is still required to validate network, token permissions, branch push, and end-to-end commit.
- Repository-level license metadata is not a per-file legal determination. The public mirror gate preserves upstream license evidence and records this limitation; per-file exceptions or extra third-party assets may still require manual review.
- Unknown or restricted content is indexed with its upstream source URL, not republished as a copied public package.
- Public content mirroring is not security approval, installation approval, or execution approval.
- Private persistent storage and broader non-English/niche source research remain separate future work.

## Acceptance

Local implementation and regression acceptance passed. Phase 7 is implementation-complete locally but remains operationally pending until the first GitHub Actions run succeeds and pushes its generated source-index update to main.
