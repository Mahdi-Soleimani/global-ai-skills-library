# Phase 60 — Canonical evidence index, increment 1

## Goal and baseline

Phase 59 accepted at published commit 9e4e4780eea755f6af603e332bc410536449a2e6, exact three-platform release and broad regression CI (see Phase 59 final acceptance). Begin the open canonical-index requirement in roadmap phase 8 without deleting, consolidating or rewriting independent research or source records. Local main subsequently fast-forwarded to catalog-only commit 3588cf8 (eight generated metadata files).

## Implementation

- tools/canonical_index.py: bounded read-only catalog parser with duplicate JSON key rejection, catalog SHA-256, strict repository/path/commit/blob validation, deterministic immutable source ID recomputation, duplicate revision refusal. Groups equal non-null recorded SKILL.md Git blob IDs and same-repository/path multiple revisions; separates same recorded blob, different recorded blobs and incomplete evidence. Sorts memberships deterministically. No network, local package content read, catalog write, ranking change, or installation.
- tools/gasl.py: canonical-index --summary returns counts and input identity; canonical-index returns exact group membership. Neither command modifies the catalog.
- tests/test_canonical_index.py: seven synthetic tests cover cross-repo equal blob without equivalence, revision states, missing evidence, deterministic ordering/nonmutation, duplicate identity, invalid pins/IDs and duplicate JSON rejection. Existing reconciliation tests remain intact.

## Observed actual catalog

Input SHA-256 a4118fa0fece61e0a911227b440a6cfd3b5bca153ee17aafca47e26f86254669 (post-refresh 3588cf8), 4,434 source records, 4,429 distinct repository/path pairs, 247 equal recorded blob groups with 755 total members, five path revision groups, five records without blob evidence. Same counts before refresh. Missing blob IDs are excluded from equal-blob grouping. These are counts of recorded evidence, not globally unique Skills, verified full-package identities or security decisions.

## Acceptance

7/7 new tests and 15/15 combined canonical/reconciliation tests passed locally; compile and whitespace checks passed. Full regression and publication evidence recorded separately. No same_as, fork_of, mirror_of, supersedes or conflicts_with relation asserted without independent evidence. Do not deduplicate search results automatically, transfer licenses/security approvals, infer ancestry, or change pinned identity. Next increment: independently validate versioned evidence for selected relation candidates and design an explicit read-only lookup/comparison interface. No public release, real-profile writes or third-party Skill execution.

## Increment 2 — targeted relation lookup and exact upstream blob evidence

Increment 1 full local regression: 870 passed, 40 skipped, 412 subtests passed in 77.04s. No failure.

- `canonical-index --id EXACT_ID` returns only direct recorded groups of one known immutable record. Unknown IDs fail explicitly; singleton records correctly return no groups. No inference from transitive relations.
- `canonical-index --compare ID_A ID_B` compares recorded path and blob evidence for two distinct IDs without network access. Optional explicit `--verify-online` is limited to a same-path or equal-recorded-blob relation candidate, with both valid recorded pins. It retrieves both exact commit/path SKILL.md files independently from raw.githubusercontent.com, checks the final URL, bounds size, verifies Git blob identities, then compares actual bytes and reports per-source SHA-256 and size. It never stores or returns instructions, writes caches, executes Skills, transfers permission, or asserts package equivalence or ancestry. Refuses a catalog change during verification. Duplicate source ID collision check added.
- Four additional test methods cover offline lookup/no network, invalid pair gates, two independent verified reads/no cache writes, and rejection of modified bytes, changed URL, oversized responses and concurrent catalog drift. Combined canonical/reconciliation tests: 19 passed. Compile and diff checks passed.

Real read-only pair verification against the catalog at 3588cf8, SHA-256 a4118fa0fece61e0a911227b440a6cfd3b5bca153ee17aafca47e26f86254669:
- GASL-SRC-58c1d955dc8eaeca0fd4, microsoft/azure-skills, skills/azure-quotas/SKILL.md, commit 7847020998043c6231929b364c35393b7cdab270.
- GASL-SRC-65124ab362904889e2f0, microsoft/skills, .github/plugins/azure-skills/skills/azure-quotas/SKILL.md, commit 47eb3888eb42aef074fcb617931bf6e5934e9d9.

Both independent pinned HTTPS reads succeeded. Git blob 00eb182af5ceb6861ee0df92d8c3c9986af652ad matched both; exact bytes equal, length 12,065 each, SHA-256 82ac42524b655f947bdd6bbd6b86a670145d296a3447555f510e37ea2d377733. This proves equality of these retrieved SKILL.md bytes against the recorded pins, not whole-package equivalence, repository fork/mirror status, license transfer, historical ancestry, or publisher authenticity. No upstream file modification or Skill execution. All existing identities remain intact.

Full macOS regression after increment 2: **874 passed, 40 skipped, 416 subtests passed** in 73.94s, zero failures. The complete current code is ready for cross-platform CI; final acceptance remains tied to published revision.
