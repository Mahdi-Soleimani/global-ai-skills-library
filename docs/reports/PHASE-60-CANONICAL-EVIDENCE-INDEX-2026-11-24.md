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

## Increment 3 — repository lineage and exact commit ancestry metadata

Baseline c247bcbd180233c8ca80b25218bca639dbd879a8 published. Broad CI 45355156604: Ubuntu passed, Windows/macOS still running at last observation. Dedicated private release CI 45355156705: Ubuntu/macOS passed, Windows still running. No cancellation or forced push.

- tools/canonical_lineage.py: explicit read-only public GitHub API inspection for a selected recorded pair. Requires same repository/path or matching non-null recorded blob. No redirects, bounded JSON response, duplicate-key rejection, endpoint and response SHA-256 evidence. Distinct repository names are validated against returned full_name and numeric repository ID. Direct fork relationship requires explicit fork flag and matching parent name and numeric ID. Mirror evidence requires an exact explicit HTTPS github.com mirror URL for the other repository, not inferred similarity. For same-repository pairs, validate exact commit responses and compare status, merge-base pin and ahead/behind counts before reporting observed ancestry; never infer Skill supersession, publisher authenticity, or full package equivalence. Reject catalog drift. No network calls from normal lookup, search or index generation. No GitHub tokens or account changes.
- tools/gasl.py: canonical-index --lineage ID_A ID_B adds explicit online metadata-only inspection.
- tests/test_canonical_lineage.py: seven tests cover parent identity, mirror URL validation, compare consistency, pin verification and no writes, absence of relation and catalog drift, unrelated-pair refusal before network, redirect and duplicate JSON rejection. 26 combined canonical/lineage/reconciliation tests passed; compile and diff checks passed.

Actual observations from catalog SHA-256 a4118fa0fece61e0a911227b440a6cfd3b5bca153ee17aafca47e26f86254669:
1. microsoft/azure-skills (repository ID 1167823778) and microsoft/skills (1135891523), previously verified equal SKILL.md bytes: API reported fork=false for both and no matching mirror URL. No direct relationship asserted. Response SHA-256 d0b3441fdd24a490116d6ab6c4cf34f4722cdb7c59b3fc9161d775766123219b and 8dfd910f5b4111448228fd989d192004c46a822211fdae00165501e9e06c9380.
2. adobe/skills (repository ID 1150753215), records GASL-SRC-6d267906c5406b6944f1 and GASL-SRC-37facf4d4fb1c100b0d6: exact GitHub commit endpoints and compare indicate 04e80589cd60aedc22ea791afac5603d95eeae98 is an ancestor of 23f5ea4c680013542990f2b03970b8064139752b. Compare response SHA-256 504d454b946372f8e7a47969625e4b2950e15be22aa4d2f958ebfccf017e379c. Older record lacks a catalog blob pin, so no content comparison or Skill supersession claim. Observed 2026-11-24 UTC. No content downloaded for execution, no persistent cache, no source records changed. Metadata observations are not independent Git graph reconstruction; absence is not proof of no relation.

Full local regression after increment 3: **881 passed, 40 skipped, 423 subtests passed**, 79.89s, zero failures. Prior broad CI Ubuntu and macOS succeeded; Windows remains in progress. Fast-forwarded catalog-only update 45e3063 (seven generated files). Hold publication of this increment until prior broad Windows CI finishes.

## Increment 4 — exact pinned directory tree comparison

Previous c247bcb acceptance confirmed: broad matrix 45355156604, private release 45355156705, locked fixture 45355156557 and native Windows 45355156548 succeeded. Published increment 3 commit 12688853cf978e4fc1527aa6455f6071093f2cd0 (push exit 0).

- tools/canonical_package.py: explicit read-only comparison of entire containing upstream Skill directories, including nested Skills. Resolve repository identity and exact commit-to-tree API metadata, cross-check any catalog tree pin, traverse the directory components, reconstruct each nonrecursive Git tree object using byte-order Git sorting and SHA-1, reject incomplete or mismatched trees, and compare complete relative paths, modes and Git blob IDs. Reject symlinks, gitlinks, case/Unicode collisions, nonportable names, excessive depth/size/count/request budgets, catalog drift and mismatched SKILL.md pin. A historical missing blob pin remains explicitly missing; do not rewrite it. No Git blob requests, script execution, local package storage or installation. External licenses and runtime dependencies are outside this directory scope. Commit-to-tree binding is reported API evidence rather than independently reconstructed commit objects. Size metadata is not part of the tree hash.
- tools/gasl.py: canonical-index --package-compare ID_A ID_B.
- tests/test_canonical_package.py: eight tests, including independently generated real Git tree using Git write-tree, equal nested directories, differing file/mode inventory, missing historical pin, tampered/truncated/duplicate tree, unsafe file types and names, pin mismatch/drift/request cap, unrelated pair rejected before API. 34 combined tests passed; compile and whitespace checks passed.

Actual comparison of Microsoft records GASL-SRC-58c1d955dc8eaeca0fd4 and GASL-SRC-65124ab362904889e2f0 against catalog SHA-256 1d504e38388e1e02620dcbbedf2377ed6ee3f8d07bae36a5e5971f13685e1a8b. Both complete upstream directory trees reconstructed and matched 9abe51b3cbdf48bcb9783700021c78063c0b020b; each contained 5 ordinary files, reported 31,082 bytes, identical relative paths, modes and blob IDs; no changed/added/removed files. 17 read-only GitHub API requests; no blob content downloaded. Equality is of Git tree identity and inventory, not an independently verified full install bundle, external license, runtime dependencies, or a statement of trust. No source records modified or merged.

## Increment 5 — ancestor license and dependency context evidence

Prior 12688853cf978e4fc1527aa6455f6071093f2cd0 broad CI 45356121138 and private package CI 45356120816 passed on Windows, macOS and Ubuntu. Increment 4 full local regression passed: 889 passed, 40 skipped, 432 subtests, 76.21s.

Extended pinned tree comparison in tools/canonical_package.py to inspect direct ancestor entries from the already hash-verified trees, plus filenames within the selected Skill directory. Recognize license/notice filenames and common Python, JavaScript, Rust, Go, Ruby, Java, PHP, container and environment dependency manifest filenames. Record exact repository-relative path, distance, mode, object SHA and regular-file status, without fetching content. Compare ancestor candidates by distance, filename, mode and object identity, separately for licenses and manifests. Empty candidate sets are unknown, not equality. Catalog SPDX remains recorded evidence, not a legal conclusion. No claim of license applicability, complete dependency discovery/resolution, external reference completeness or install approval. No additional network requests beyond the existing tree comparison. Three new regression tests exercise identical directory with different ancestor license, absent candidates and nonregular license candidate. 37 combined tests passed.

Actual Microsoft pair on catalog SHA-256 1d504e38388e1e02620dcbbedf2377ed6ee3f8d07bae36a5e5971f13685e1a8b: equal Skill directory tree, both catalog SPDX MIT. Left root LICENSE blob 356b112bcc4f07e03b6e57569eedf9d79978d2d5 (distance 2); right plugin LICENSE same blob and distance, plus root LICENSE blob 79656060de00aa4659ad2c276d5be8830664d544 (distance 5). Ancestor license candidate inventories differ. No recognized dependency manifest filename observed in inspected directories or ancestors, which does not imply dependency-free operation. No Skill or license content downloaded, no source records modified or merged. No legal applicability conclusion.

Full local regression after increment 5: **892 passed, 40 skipped, 432 subtests passed**, 74.99s, zero failures. README now documents offline and explicit online canonical evidence commands and their limits. Fast-forwarded catalog-only update 6d48fba (seven generated files). Package comparison/context increments 4 and 5 are ready for publication and exact-revision three-platform CI.

## Increment 6 — offline REST and Explorer relation lookup

Published baseline 44bcc06b811631d4c25344f7b5a86e412ed1078c. Private release matrix 45358581061 and dedicated Explorer 45358581153 passed; broad 45358581155 Ubuntu/macOS passed, Windows still running at last observation.

- tools/api_server.py: GET /v1/skills/{exact-source-id}/relations exposes canonical_index.lookup only, no upstream or install operations; existing bearer authorization applies. Strict 20-hex immutable identity, reject query parameters, 400 invalid request, 404 unknown ID, 503 invalid/unavailable canonical catalog, without leaking paths or malformed data. Existing API unchanged.
- web/index.html: explicit “مشاهده روابط و نسخه‌ها” in details, render local recorded equal-blob groups and same-path revision groups with commit/path and navigation to exact related record. Distinguish empty evidence from proof of absence, warn that equality is not package/security/license approval. All dynamic data uses textContent; no automatic remote content retrieval. Detail revision guard invalidates late responses on new detail, content, close or new search.
- tests/test_api_server.py: two tests for bearer enforcement, exact immutable IDs, offline/no mutation, online parameter rejection, unknown source, invalid catalog fail-closed. 23 API/canonical tests passed. tests/explorer_workflow_smoke.js tests explicit loading, no automatic fetch, untrusted text, related record navigation, empty evidence and no content request; DOM simulation passed. tests/release_package_smoke.py adds offline relation endpoint to standalone REST smoke. Explorer CI path triggers and focused tests now include canonical module and API tests. Compile/diff passed.
- Full regression pending at this observation. First Git fetch failed SSL_ERROR_SYSCALL, normal retry succeeded without settings changes; remote catalog-only update e73ba31 touches eight generated metadata files. No records merged, Skill installed or executed. Actual browser rendering is not claimed from DOM simulation.

Full local regression after increment 6: **894 passed, 40 skipped, 432 subtests passed** in 77.87s, zero failures. Fast-forwarded catalog-only update e73ba31. Hold push until previous Windows broad CI completes.

## Increment 7 — pairwise Explorer comparison and bounded exact-content cache

Previous baseline 44bcc06 broad CI 45358581155 passed all three platforms. Published 4c129ff31f2316f4d559feca598b56cbb9fc3a92 successfully; Explorer CI 45360060634 passed; broad 45360060395 and private package 45360060553 still running at observation.

- tools/canonical_index.py: single bounded in-memory snapshot for catalog files up to 16 MiB, thread-safe construction, SHA-256 of actual bytes read on every request (not mtime or size), direct ID-to-group mapping, deep copies of public results and selected records. Invalid or changed data is not served from an older cache. No disk cache or network. Batch comparison evidence from one validated snapshot for all 2–3 selected records; identity mismatch fails closed. Distinguishes missing, equal, and different recorded blobs and same repository/path; no package/ancestry or installation approval.
- tools/skill_compare.py: additive relation_evidence field, explicitly unavailable when canonical catalog cannot validate the compared identities. Existing comparison remains available; no changes to ranking or selection.
- web/index.html: pairwise recorded relations in comparison panel with clear limits. No online request or automatic installation.
- tests/test_canonical_index.py: two additional methods verify cache isolation and same-size/same-mtime content change invalidation, invalid JSON refusal, three pairs and identity mismatch. 31 focused canonical tests and Explorer DOM simulation passed, including visible relation summary.

Local actual catalog benchmark (8 sequential calls per operation, same Mac and selected Microsoft records): relation lookup median 78.42 ms before and 7.00 ms after; cold/worst observed 252.62 and 75.51 ms respectively. Approximate 11.2x improvement in measured warm-median lookup, not a universal performance claim. Comparison median 29.78 ms before vs 40.65 ms after including new evidence; initial baseline cold index build 4484.06 ms, post-change already warm max 48.49 ms, not directly comparable. Actual pair output same_recorded_blob, distinct paths; catalog SHA-256 b4ed46966b18c8397e865f86b70d528981f5366f74d07728213d0e0e751a7d39. No source modifications or merge. Full regression pending.

## Increment 7 acceptance evidence and remaining roadmap boundaries

Full macOS regression: **896 passed, 40 skipped, 432 subtests passed**, 86.12s, zero failures. Fast-forwarded catalog-only update 2775695 (seven generated metadata files). After refresh, 71 focused canonical/comparison tests and Explorer DOM flow passed. Actual authenticated loopback HTTP smoke on the refreshed 4,434-record catalog: 64 relation GET requests with 8 concurrent workers, all HTTP 200, correct exact record ID, matching catalog digest b3e3725eb7113a8e770b4f6ff7dca2b7500f046ed6a7f6133df46d393ffda687 and no installation approval; median 290.20 ms, maximum 419.59 ms under this particular concurrent local load. Actual POST /v1/compare passed and returned the same recorded blob evidence with the same digest. Server stopped after the test. These are local measurements, not throughput guarantees.

Published predecessor 4c129ff: dedicated private package matrix 45360060553 passed all three OS; broad 45360060395 macOS and Ubuntu succeeded, Windows still running at observation. Exact final revision CI is required before closing Phase 60. No push cancellation or force push.

### Remaining roadmap review (based on docs/ROADMAP.md and Phases 54–60)

- Original research datasets: original row-level CSV/JSON/XLSX artifacts remain unavailable; four independent source manifests and original reports retained. Do not reconstruct or invent missing source rows.
- Canonical evidence: implemented candidate index, direct lookup, pairwise comparison, optional pinned SKILL.md, repository/commit and tree evidence, filename-based license/manifest context and offline REST/Explorer. Acceptance is scoped to these evidence features, not global deduplication or all relations independently verified.
- Search: lexical FTS5 default remains intentional. Full vector retrieval is optional research; no independently judged relevance or calibrated accuracy claim.
- Validation: synthetic fixture and transactional tests are separate from real vendor-host compatibility, controlled third-party execution and independent behavioral evaluation. Do not run downloaded Skills on the real host; user-deferred actual vendor tests and human adjudication remain explicitly deferred.
- Packaging: Phase 59 verified canonical private metadata-only ZIP and six MCP tools on three OS. Public release remains blocked by unselected project LICENSE and separate redistribution review. Do not publish a release or select a license on behalf of the owner.
- After exact-revision Phase 60 CI: audit actual cross-platform launcher/setup and clean-install paths against the packaged runtime; prioritize actionable defects rather than adding unsupported features. Root-level or exceptional packages, independently verified external dependencies and production legacy migration remain distinct scope/approval gates.

## Final Phase 60 acceptance

Published 085505ddcddc34461ffe05e2e1d8b1054bb43a12. Broad [45360971264](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45360971264) completed successfully: Ubuntu job 138330665118 and macOS 138330665553 each 896 passed/40 skipped, Windows 138330665423 781 passed/7 skipped. Explorer job 138330664196 in run 45360970994 succeeded. Actual local private draft 87 files, SHA-256 4fa69cb058a14fa8d216699b735bcae3648aa6be06502c597a774296228b2602, content bound to commit and canonical encoding verified. Standalone CLI, bilingual route, REST/Explorer including relation endpoint passed; that local smoke did not request MCP. Prior exact 4c129ff private package matrix passed all three platforms. Phase 60 accepted within evidence-only index, comparison, offline REST/Explorer and bounded cache scope, not global deduplication, full legal equivalence, all relations independently verified or runtime trust. No source records merged. Next: Phase 61 runtime setup and launch.
