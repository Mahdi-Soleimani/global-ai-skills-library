# Phase 59 preparation — private release commit integrity

## Scope and baseline

Phase 58 implementation baseline `29df235b322a7df4c53cbcbbc439197fbbf751ee` was published on main. The [dedicated Windows/Ubuntu fixture workflow 45294465079](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45294465079) succeeded (Windows: 96 passed, one POSIX-only skip), and [native Windows workflow 45294465354](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45294465354) succeeded. The [broad matrix 45294464943](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45294464943) passed Ubuntu and macOS; Windows remained in progress at last observation. This is preparatory work, not an assertion that Phase 58 final acceptance has been closed.

## Defect and implementation

The original Phase 50 draft verifier compared archive bytes with its own manifest and sidecar. A consistent replacement of source bytes, manifest hashes and sidecar digest could therefore falsely claim the original commit. Tracked worktree bytes also were not intrinsically bound to the declared commit (Git filters and assume-unchanged can hide differences).

- `tools/release_draft.py`: derive file allowlist and sizes from the exact HEAD tree; compare included paths with the index; read committed blobs with Git replacement objects disabled; validate Git blob identities and SHA-256; build from committed object bytes instead of worktree contents. Check HEAD and tracked cleanliness before completion. Reject redirected source/output paths and hardlinked/oversized archive records; enforce bounded archive, manifest and decompressed inventory sizes, strict metadata fields and duplicate JSON rejection. Verify exact committed inventory, path ordering, file mode and bytes, not merely internal ZIP consistency. Read verification archive from the same bounded byte snapshot used for its digest. Cleanup only files this invocation created whose identity still matches. No extraction or third-party code execution.
- `tests/test_release_draft.py`: six new fixture tests for forged internally consistent ZIP, omitted file with recomputed digest, assume-unchanged local edit excluded, duplicate sidecar key, oversized compressed manifest and hardlinked ZIP. Existing ten tests retained.
- `.github/workflows/gasl-release-draft.yml`: check the new explicit commit-tree binding in actual-source read-only inspection.

## Validation

16/16 focused tests passed locally. Complete macOS regression: **859 passed, 40 skipped, 407 subtests passed**, 61.61 seconds. Compile and diff checks passed. Actual-source read-only inspection of the baseline: 80 allowlisted files, 17,060,712 uncompressed bytes, no project LICENSE, publication disallowed. No real release archive built or published during this increment.

## Acceptance / limitations

New code requires exact-commit CI acceptance. This is commit-integrity hardening, not cryptographic publisher authentication, hostile filesystem safety, legal review, real vendor Skill discovery, or authorization to distribute any third-party Skill. No public release, project-license selection, real user-profile writes or live third-party Skill execution. Phase 58 final broad Windows result must be confirmed; do not cancel its run simply to announce completion.

## Increment 2 — canonical stored ZIP and cross-platform reproducibility gate

Phase 58 final acceptance is confirmed: baseline `29df235b322a7df4c53cbcbbc439197fbbf751ee`, broad CI 45294464943, Windows 738 passed/7 skipped, macOS and Ubuntu 853 passed/40 skipped each. Phase 59 increment 1 commit `d8498f428fc564b7c8057188fb516e25bde0b87f` was intentionally held locally until that matrix completed.

- `tools/release_draft.py`: new drafts use ZIP_STORED with fixed entry order, timestamps, mode and Unix creator metadata to avoid zlib-version differences. Verification independently recreates canonical bytes from the already verified committed inventory, reports the exact canonical match, and continues to recognize verified noncanonical older compressed drafts without claiming byte reproducibility. Existing no-overwrite/publication gate remains intact.
- `tests/test_release_draft.py`: deterministic self-authored Git fixture uses SHA-1, explicit Git config, LF bytes, fixed commit identities and dates (subprocess environment only; no system clock changes). Golden fixture commit `84af3b801f3e8140671f0bddad12d8849ab6350d`, canonical SHA-256 `3ef32205ef59cc0994ef6412155279cf9f6eb0e6697bc92fa119a2f9eba8fd1b`. Two additional tests cover exact golden identity and compressed legacy compatibility.
- `.github/workflows/gasl-release-draft.yml`: Python 3.13 matrix on Ubuntu/macOS/Windows, same golden assertion per job, portable read-only real source inspection and no private draft artifacts in the checkout. No artifact upload, public release or Skill execution.
- README clarifies canonical encoding, commit binding, and Windows command. Phase 58 final acceptance recorded separately.
- Local validation: **18/18 release tests passed**, golden digest confirmed; full macOS regression **861 passed, 40 skipped, 407 subtests passed** in 59.85s. Compile and diff checks passed. Native cross-platform golden equality still requires CI on the new commit. The stored ZIP is larger than the former compressed encoding; bounded source/archive size limits remain enforced. No real private draft was created during this increment.
