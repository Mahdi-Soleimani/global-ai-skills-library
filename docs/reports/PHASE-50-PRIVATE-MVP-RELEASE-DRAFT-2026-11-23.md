# Phase 50 — Deterministic private MVP release draft

**Date:** 2026-11-23  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Feature scope:** deterministic offline internal draft packaging, read-only readiness and ZIP verification. No public publication.

## Goal

Prepare a reproducible CLI + Explorer draft from **strictly Git-tracked, allowlisted source and attribution files**, while preventing accidental publication before the project owner chooses a project license and the remaining Host/distribution gates are completed. The user's explicit instruction to skip manual/real-user testing and relevance adjudication remains in force. The implementation uses only synthetic Git repositories in automated tests.

## CLI

```bash
./gasl release-draft --action inspect
./gasl release-draft --action build
./gasl release-draft --action verify
```

The inspect command is read-only and reports the exact local source Commit, selected tracked-file count/bytes, presence or absence of an actual tracked project LICENSE, and explicit publication blockers. The build command requires a clean tracked Git worktree and creates an ignored local `private/release-drafts/gasl-mvp-COMMIT12.zip` with a SHA-256 sidecar. The verify command checks that archive against its sidecar and every embedded file's SHA-256/size **without extracting or executing anything**.

The ZIP is deterministic: sorted file order, fixed 1980 ZIP timestamps, consistent POSIX permissions, canonical manifest JSON and no environment/time-dependent metadata. A second build of the same tracked sources produces the same SHA-256. Overwriting existing artifacts fails closed.

### Allowlisted contents

- Entrypoint: `gasl` (shell wrapper).
- Python standard-library runtime: tracked `tools/*.py`.
- Explorer: `web/index.html`.
- Required JSON settings from `config/*.json`.
- Selected source-catalog metadata: `registry/source-catalog.json`, `registry/search-features.json`, `registry/skill-evaluations.json`, `registry/source-catalog-summary.json`, and `public-catalog/index.json`.
- `README.md`, `ATTRIBUTION.md`, `THIRD_PARTY_NOTICES.md`, `docs/ATTRIBUTION-AND-REDISTRIBUTION-POLICY.md` and `docs/ROADMAP.md`.
- An author-supplied tracked `LICENSE` / `LICENSE.md` / `COPYING`, if one later exists.

Files under `private/`, downloaded third-party Skill packages, secrets, local `.env` files, user Agent profiles, tests, runtime SQLite artifacts and all untracked files **never enter the ZIP**. Missing required files, symlinks, uncommitted tracked changes and size/count violations block construction.

### License and public-release boundary

**No GASL project license is presently selected.** The source repository is visible on GitHub, but its code has no general open-source permission grant until the owner chooses an appropriate license. Third-party Skill licenses remain independent. The draft's manifest and readiness report therefore include:

- `public_release_allowed=false`
- `private_artifact_only=true`
- `project_license_not_selected` in the blockers when no tracked License is present
- Separate blockers for other Host scopes and independent redistribution review

Even when an author-supplied license exists, these gates do not auto-publish or claim a legally complete distribution. No GitHub Release, package registry publish, or external file upload is performed.

## Implementation

- `tools/release_draft.py`: tracked-file selection, Git cleanliness gate, manifest/hash generation, deterministic ZIP writing and strict read-only verification.
- `tools/gasl.py`: `release-draft --action inspect|build|verify`.
- `tests/test_release_draft.py`: 10 synthetic Git repository tests for no-license blockers, deterministic bytes, private-file exclusion, package integrity, edited ZIP refusal, symlink rejection, dirty worktree refusal, untracked-file exclusion, optional author LICENSE inclusion and missing required runtime entry.
- `.github/workflows/gasl-release-draft.yml`: lightweight CI; synthetic tests plus read-only actual-source inspection; it never builds or publishes a ZIP on GitHub.
- `README.md`, `docs/ROADMAP.md` and this report.

## Acceptance / remaining gates

The module and tests are written. Local and GitHub CI outcomes, final source SHA and draft-archive SHA will be added after they are observed. A public release remains **blocked** until a project LICENSE is selected and relevant redistribution and Host-support policy is reviewed. User Profile/Windows/Cursor/Claude Code/Sandbox features remain separate implementation work and are **not claimed complete**.

No manual user test, independent human relevance adjudication, live third-party Skill execution, or real Host installation was performed.
