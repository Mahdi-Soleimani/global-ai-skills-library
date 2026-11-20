# Phase 5 — Commit-pinned queue ingestion, batch 01

Baseline: 01e4387. Date: 2026-11-20.

## Implementation
- Added tools/queue_ingest.py, a bounded queue-based collector. Reads the existing discovery queue without updating its pinned commits. Verifies the commit-to-tree relationship and the tree-to-SKILL.md blob relationship before planning. Dry-run is the default.
- Per-batch limits: 5 MiB and 30 files for this pilot, one package from each of three repositories. The existing policy limits are enforced as well.
- Files are received into an isolated local quarantine staging directory. Exact byte count, Git blob object SHA and local SHA-256 are recorded. Atomic file publication; interrupted downloads resume at verified file boundaries. Complete directory inventory is checked before promotion into catalog. No scripts are executed.
- Unsafe paths, filesystem case/Unicode collisions, symlinks, nonregular files, blocked directories and oversized packages are rejected rather than marked complete. Root-level skill layouts and external or shared dependencies are deferred for explicit review. Nested skills are separate packages.
- A local ingestion lock prevents simultaneous queue ingestors. The existing legacy collector is not a participant in that lock; do not run both at once.
- Existing valid packages are skipped; --verify-existing rechecks the selected inventory and hashes without downloading content again.
- Corrected legacy collector manifest update behavior so a selected subset does not remove earlier package entries at the same revision.
- Rebuilt the static scan, derived registry, discovery queue and crosswalk. Four independent raw research archives and the historical source verification snapshot are unchanged. Third-party package content remains outside Git.

## Live pilot

| Repository | Skill | Commit | Files | Bytes |
|---|---|---|---:|---:|
| microsoft/skills | aks-cost-optimization | 0d60658e34d07c05a5cd0514d3e64ccd653e8539 | 14 | 45500 |
| awslabs/hcls-agent-skills | aws-genai-ml-architect | a4826bd6793a8522aab3f5f0410ef527b910cb7f | 2 | 18472 |
| phuryn/pm-skills | code-review | 9af7bfd0bc47fdad43c2eaa7a43cd13918e7aaef | 1 | 1120 |

Total: 3 packages, 17 files, 65,092 bytes. All 17 exact blob hashes, byte sizes and local SHA-256 hashes validated. All three package frontmatters passed the current parser. The heuristic static scanner reported zero findings for these three, not a safety guarantee.

The live repeat verification returned already_verified for all three packages, zero new content files and 17 reused files. All 60 existing manifest entries retained unchanged.

## Current state

- 63 catalog packages, 640 manifest source files, 13,583,889 bytes, across seven repositories.
- 59 candidates and four test fixtures. Static scan: 53 packages with no obvious flags (not approved), ten requiring manual review; two high-confidence signals remain from prior snapshot.
- Discovery queue: 2,018 total, three matched completed package metadata, 2,015 pending planning. Queue completion status does not imply security approval.
- 36/36 project tests passed, including injected network interruption and file-boundary recovery, bad hash, paths, symlinks, nested boundary, size and case collision tests.
- No third-party code installed, executed, globally enabled or republished.

## Remaining gates

Batch 01 passed its bounded acceptance tests. Phase 5 is not complete: the full queue remains pending; root-level layouts, shared and external dependencies, individual file licensing, damaged-checkpoint recovery policy and comprehensive rate-limit scheduling need further review. The scanner is heuristic; manual review and OS-enforced dynamic isolation remain separate gates. No package is approved for installation. Network interruption recovery was simulated in tests; file reuse was independently demonstrated on real downloads. A fresh API tree verification is still required for each invocation.
