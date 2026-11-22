# Phase 16 — Git Preservation and Metadata-only GitHub Actions: Verified

**Date:** 2026-11-22  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Branch:** `main`  
**Result:** Priority 1 and Priority 2 acceptance passed: local development is committed and pushed, and the replacement metadata-only GitHub Actions workflow has completed successfully.

## 1. Original baseline and preservation

- Original local/remote `main`: `7e616c0f5a8b6ba906bea59a0ade3fc163d9e418`.
- Prior to changes: 22 tracked modified files, 109 individually untracked non-ignored files (13,805,705 bytes), displayed as 69 top-level untracked entries.
- Scanned 314 tracked and new candidate files for common embedded credential patterns. No private keys or matching GitHub/AWS/OpenAI/Slack/Google API tokens were detected; one synthetic test email was observed. This is a bounded pattern scan, not a formal secrets audit.
- Confirmed `private/`, ignored local metadata cache, private reviewer evidence and third-party Skill packages were not included in Git.
- No remote history was rewritten; no `git reset`, `git clean`, `force push`, or deletion of local research artifacts was performed.

## 2. Git commits

Three reviewed commits were pushed to `main` via a normal, non-forced `git push origin main`:

| Commit | Content |
|---|---|
| `2d6f91dc55b481fa186039cf53fb583e32ab6490` | Local-first search, Router and MCP, automated evaluation, tests, configuration and source catalog metadata |
| `caaefa91ee56d47baf4bf89104caef6d46f3e20c` | README/CONTRIBUTING, roadmap, historic reports and reproducibility evidence |
| `90cab66c7abf911b340419c8dbfdd6001b49ec0f` | GitHub Actions metadata-only refresh, separate PR CI workflow and Python 3.13 setup |

The documentation commit added a Markdown whitespace attribute to preserve intentional two-space hard line breaks while allowing `git show --check` and `git diff --check` to pass. The PR workflow also had two escaped `${{ ... }}` expressions corrected to valid GitHub Actions syntax.

### Clean-checkout acceptance

Recreated the pushed `90cab66` tree using `git archive` into a temporary directory **without `.git`, `private/`, `catalog/`, `reports/` or any ignored local cache**. The following commands passed in that fresh tree:

- `python3 -m pytest -q` — **203 tests and 6 subtests passed**;
- `python3 -m compileall -q tools tests` — success;
- `python3 tools/build_source_catalog.py --public-only` — success;
- `python3 tools/skill_evaluation.py` — success;
- `python3 tools/skill_search.py --check` — 4,405 source records indexed in the initial clean snapshot;
- CLI search and Router JSON smoke tests — success; the route returned 3 candidates and installation/execution remained false.

The temporary test directory was disposed after testing; no private test files were included.

## 3. Root cause of prior GitHub Actions failure

Previous scheduled workflow run: [44919341408](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/44919341408) on 2026-11-21. The legacy workflow failed during its bulk redistributable-package ingestion step. The logs recorded a manifest package path conflict for the immutable `cloudflare/security-audit-skill` source identity, followed by process exit code 1.

That workflow step has been **removed** from the active pipeline. The replacement refresh job no longer downloads or republishes complete third-party Skill packages.

## 4. Live GitHub Actions confirmation

- **Workflow:** `GASL — Daily source catalog refresh`
- **Run ID:** [`45037157171`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45037157171)
- **Event:** `push`
- **Trigger SHA:** `90cab66c7abf911b340419c8dbfdd6001b49ec0f`
- **Result:** `completed / success`
- **Python:** GitHub runner Python 3.13
- **All steps completed successfully:** Checkout, setup Python, install dependencies, regression tests, discover pinned repositories, build public source metadata, extract search vocabulary, build evidence-only evaluations, search/route smoke tests, diff validation and commit/push metadata allowlist.
- **Source discovery errors:** 0 (run log output); no failed targets.
- **GitHub Actions automatic metadata commit:** `a8f1e97e6d9e548237d746f1342ffc5a5724da0b` (`chore: refresh attributed skill catalog`). The workflow committed and pushed **8 metadata files only**, not a new Skill mirror.

After the run, fetched `origin/main` and advanced local `main` with `git merge --ff-only origin/main`. No conflicts or history rewrite occurred. Both branches matched at `a8f1e97` before this report-only commit.

### Post-refresh source evidence

| Metric | Current verified value |
|---|---:|
| Source repositories | 57 |
| Source catalog records | 4,431 |
| Commit-pinned source records | 4,431 |
| Legacy unpinned records | 0 |
| Search feature records | 4,426 |
| Evidence evaluation records | 4,431 |
| Previously allowed public mirrored records | 9 |
| Third-party packages newly bulk-downloaded by workflow | 0 (removed step) |

After fast-forwarding the metadata commit, the Mac ran `python3 -m pytest -q` again: **203 tests and 6 subtests passed**. The local CLI search returned results; a sample native Android banking-SMS Router query safely returned `abstain`, `installation_performed=false` and `execution_performed=false`.

## 5. Files and changes

- Modified: `.github/workflows/gasl-refresh.yml` (metadata-only, Python 3.13, searchable vocabulary, evaluation and smoke tests).
- Added: `.github/workflows/ci.yml` (PR checks; corrected GitHub expression syntax before publication).
- Committed 59 core/config/test/registry files and 71 project documentation/report files in separate commits.
- Added `.gitattributes` Markdown whitespace rule to preserve intentional Markdown hard line breaks.
- Created `docs/reports/PHASE-16-GIT-PRESERVATION-PRE-PUSH-2026-11-22.md` with the original audit details.
- Created this report to capture live GitHub evidence and source metrics.

## 6. Residual observations

- The successful Actions job emitted a **non-fatal Node 20 deprecation warning** from `actions/setup-python@v5`, which GitHub forced to run on Node 24. This did not fail the workflow and can be addressed at a later normal dependency-upgrade checkpoint.
- Source catalog size increased with live discovery, so snapshots and private legacy evaluation caches must continue to be identified by their own fingerprints; old benchmark numbers must not be presented as directly comparable with the new snapshot.
- The repository still has no selected project `LICENSE` file. This is a separate open task for the official public open-source release and is outside the two completed priorities.
- The saved code is publicly available on GitHub; ignored private artifacts remain on the user's Mac, not in the public repository.

## 7. Acceptance

**Priority 1 — PASS:** reviewed source, metadata, documentation, reports and tests committed/pushed; source and credentials checks performed; remote history preserved; clean checkout and test validation passed.

**Priority 2 — PASS:** old bulk-download failure path removed; replacement Metadata-only Actions workflow ran successfully, committed only the allowlisted metadata and pushed an automatic refresh; local working copy fast-forwarded to the resulting remote commit.

Next priorities per `docs/ROADMAP.md`: security-review backlog and sandbox gating, end-to-end selective install compatibility, Agent-host verification, and eventual release licensing. No human reviewer is required for the working search/Router flow.
