# Phase 3 — Evidence-scoped source reconciliation

Date: 2026-11-20. Baseline: GitHub commit e2641e39137f95225a828adbe73054f45484b182. The local and remote trees matched; the original independent local root was retained on a local backup branch before main was aligned with origin/main. No network settings changed.

## Implemented

- Added `tools/reconcile.py` and `python3 tools/gasl.py reconcile` using Python standard library.
- Validate manifest identity, source hash metadata, source IDs, reference ordering, canonical targets and snapshot path counts.
- Produce a public repository source crosswalk and aggregate summary. Detailed path-to-reference and downloaded-record crosswalks and duplicate candidate evidence stay local.
- Preserve aliases and every source reference; do not rewrite research manifests or raw archives.
- Distinguish recorded commits, reported tree references with commit unverified, and branch observations.
- Compare exact and normalized SKILL.md hashes; flag same-name/different-content and same-path/different-commit candidates without merging records or inferring ancestry.
- No downloaded code was executed.

## Snapshot results

| Metric | Value |
|---|---:|
| Independent source manifests | 4 |
| Source repository mentions | 87 |
| Distinct source references | 56 |
| Canonical repositories | 55 |
| Redirected source mentions | 1 |
| Unverified source mentions | 0 |
| Observed SKILL.md paths | 4,214 |
| Explicit test fixture paths | 6 |
| Paths with a recorded commit | 234 |
| Paths with only reported tree ref | 1,513 |
| Paths with branch observation only | 2,467 |
| Downloaded registry records | 60 |
| Records matching a snapshot path | 60 |
| Records matching the same recorded snapshot commit | 1 |
| Records matching only a path (commit unconfirmed) | 59 |
| Duplicate relationship groups in downloaded registry | 0 |
| Exact research skill-record matches | 0 |

Snapshot date: 2026-11-19. These are observations from the existing verification registry, not a new network crawl. Explicit fixture classification uses the existing conservative path rule, not comprehensive fixture detection. Recorded tree references were not independently confirmed as Git tree object IDs. Publisher account is not proof of official authorship.

## Outputs

- `reconciliation/source-crosswalk.csv` — 87 independent source-reference rows.
- `reconciliation/crosswalk-summary.json` — summary, input SHA-256 and limitations.
- Local-only: `reconciliation/skill-path-crosswalk.csv`, `reconciliation/downloaded-skill-crosswalk.csv`, `reconciliation/duplicate-candidates.json`.

## Acceptance and open gaps

- Repository-level crosswalk and historical path-level mapping: PASS.
- Deterministic regeneration of all five outputs: PASS.
- Four original archive SHA-256 checks: PASS.
- Regression tests: 22 PASS.
- Exact source-skill joins: BLOCKED by missing original row-level databases. Repository provenance is not source skill-row provenance.
- Global or full-package duplicate detection, fork/mirror equivalence and version ancestry: not established.
- Dynamic security validation and installation gates remain unchanged and unapproved.

Next bounded task: collect fresh commit-pinned discovery metadata without executing third-party content; preserve historical verification data and do not infer source skill rows.
