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
