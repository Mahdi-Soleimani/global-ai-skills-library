# Phase 7 — Third-party attribution and GitHub Actions automation

Date: 2026-11-20
Repository: Mahdi-Soleimani/global-ai-skills-library
Baseline commit: f83c45b

## Goal

Keep every discovered skill represented in GASL regardless of its license, preserve upstream attribution and provenance, and automate safe public mirroring of package contents only when a redistribution gate passes. The automation must not claim authorship or exclusive ownership and must not require the user's Mac to remain online.

## Implemented

### 1. Complete source index

- Expanded discovery targets to 57 canonical repository targets: 55 historical canonical sources plus two newly selected sources. A historical redirected alias was merged into its canonical repository.
- Rebuilt a public-safe discovery state from the historical 56-entry repository verification snapshot, preserving the union of all 4,214 historical paths. The live GitHub Actions refresh subsequently verified all 57 repositories and pinned all 4,405 valid source records to exact commits.
- Added registry/source-catalog.json, registry/source-catalog.csv, and registry/source-catalog-summary.json.
- The successful live source catalog contains 4,405 commit-pinned repository/path records across 57 repositories. It is not a count of globally unique skills.
- Every record carries source repository, publisher/owner, original path, direct source URL, observed license metadata, commit/tree/blob identifiers when available, source status, content status, third-party ownership, and an explicit no-exclusive-ownership flag.
- Individual original authors are not inferred from repository ownership. original_author remains null unless there is actual evidence.
- All 4,214 historical paths remain represented regardless of license. Both newly selected repositories were included in the successful 57/57 live refresh.

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
- The earlier 63-package local pilot remains local-only. The first successful GitHub Actions batch mirrored nine packages from Apache-2.0, MIT, and MIT-0 repositories after bundling their applicable upstream license/notice evidence. All other discovered paths remain in the complete source index whether or not their content is mirrored.

### 4. GitHub Actions automation

Added .github/workflows/gasl-refresh.yml:

- Daily schedule at 07:23 UTC, manual workflow_dispatch, and push triggers when the workflow, downloader code, or source/license configuration changes.
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
| Source catalog records | 4,405 |
| Commit-pinned source records | 4,405 |
| Publicly mirrored packages | 9 |
| Public mirror files / bytes | 119 / 664,466 |
| Download manifest packages | 71 |
| Download manifest files / bytes | 757 / 14,229,883 |
| Local package files | 640 |
| Local package bytes | 13,583,889 |
| Local skill candidates | 59 |
| Evaluation fixtures | 4 |
| Packages requiring manual security review | 10 |
| High-confidence static signals | 2 |
| Install-approved / installed / executed | 0 / 0 / 0 |
| Regression tests | 57 passed |

The four independent research report archives were re-hashed and remain byte-identical to their recorded SHA-256 values. No original research dataset was merged, rewritten, or reconstructed.

## Validation

- 57/57 project tests passed.
- Python compilation passed for discovery, queue ingestion, registry builder, source catalog builder, and public catalog builder.
- GitHub Actions YAML parsed successfully; schedule, workflow_dispatch, contents:write, and refresh job were verified.
- Static scan completed for all 63 local packages. All package file integrity checks passed. Heuristic scanner still reports ten packages for manual review and two high-confidence signals; no code was executed.
- The earlier 63-package local pilot was not bulk-copied into the public repository. Nine new packages passed the license/evidence gate and were mirrored with original license/notice files and attribution.
- Source catalog invariants verified on GitHub: 4,405 records, 4,405 distinct repository/path references, 4,405 commit-pinned records, and 57 configured repositories.
- Public catalog contains nine immutable package revisions; all nine have ATTRIBUTION.md/JSON, third-party ownership, original source links, exact commits, and license evidence. No package is marked installed or executed.
- Four independent original research archive hashes passed.

## Known limitations / next gate

- A local Mac API refresh attempt encountered TLS EOF errors. GitHub Actions successfully bypassed that local network limitation: all 57 repositories were refreshed with zero repository errors and the generated index was committed. Daily automation no longer depends on the Mac being online.
- Repository-level license metadata is not a per-file legal determination. The public mirror gate preserves upstream license evidence and records this limitation; per-file exceptions or extra third-party assets may still require manual review.
- Unknown or restricted content is indexed with its upstream source URL, not republished as a copied public package.
- Public content mirroring is not security approval, installation approval, or execution approval.
- Private persistent storage and broader non-English/niche source research remain separate future work. Repository-level license metadata is still not a per-file legal determination.

## First live GitHub Actions runs and final acceptance

- Run 44745998519 passed tests and verified all 57 configured repositories with zero repository errors; 4,478 SKILL.md paths were observed and 4,405 entered the source queue. Its first bounded ingest exposed a legacy Manifest inventory mismatch after eight ephemeral downloads.
- Fixed manifest merging so a complete revalidated package at the same immutable repository/path/commit and deterministic package path can refresh file count and bytes, while conflicting package paths still fail closed.
- Run 44746633434 downloaded nine packages (119 files; 664,466 bytes), completed scanning and public catalog generation, then failed only because the commit step tried to stage registry/skills.json and registry/skills.csv, both intentionally ignored local-only files.
- Removed the two ignored paths from the workflow staging list.
- Run 44747234619 completed successfully. All 57 repositories refreshed, all 4,405 source records were commit-pinned, nine packages were mirrored with attribution and license evidence, and the generated source index/public catalog were committed automatically.
- The workflow commit is 83c103114540687c5ebb76d90318d623b12b65c2. The local working copy was fast-forward synchronized to this commit.

## Acceptance

Acceptance passed: 57 project tests; 57/57 source repositories refreshed with zero errors; 4,405 commit-pinned source records; nine attributed public packages; 119 mirrored files; automatic GitHub commit; local working copy synchronized. No downloaded code was installed or executed.
