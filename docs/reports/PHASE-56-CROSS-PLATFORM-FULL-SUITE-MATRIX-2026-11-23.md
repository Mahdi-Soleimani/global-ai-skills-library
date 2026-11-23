# Phase 56 — Cross-platform full-suite regression matrix

**Date:** 2026-11-23  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Baseline:** `461d9c2` (fast-forwarded after the CI-generated source metadata refresh).  
**Status:** CI workflow implemented; native macOS/Linux/Windows matrix results pending.

## Goal
Cover all 60 Python test modules in a single portable regression pipeline on GitHub-hosted **Ubuntu, macOS and Windows** using Python 3.13, rather than treating the dedicated Windows Project/Profile workflow as proof of full cross-platform compatibility. Do not run third-party Skills, install into a real Agent HOME, grant approval from static-scan results, or claim Windows power-loss durability.

## Current CI coverage before this phase
- `.github/workflows/ci.yml`: Ubuntu-only, Python 3.10–3.13, for PR/manual events.
- `.github/workflows/gasl-windows-project-install.yml`: selected native Windows transaction and queue tests, previously accepted on run `45279746011`.
- `.github/workflows/gasl-user-profile-install.yml`: Ubuntu-only selected account/profile lifecycle tests.
- Local macOS full suite before this phase: `798 passed, 28 skipped, 337 subtests passed`.
- Daily Source Refresh passed on run `45279746200`, and generated metadata commit `461d9c2`.

## Changes
New `.github/workflows/gasl-cross-platform.yml`:
1. Trigger on meaningful code/tests/config/benchmark/web changes to `main` and PRs, or manually; metadata-only commits do not waste three CI runners.
2. Use a three-OS matrix (`ubuntu-latest`, `macos-latest`, `windows-latest`) at Python 3.13 with `fail-fast: false`, so one OS failing does not conceal results from others.
3. Checkout full Git history (`fetch-depth: 0`) for pinned historical Git catalog tests.
4. Install the repository's pinned dev/MCP dependencies; compile `tools` and `tests`; run `python -m pytest -q` without adding new skip rules.
5. Check that no in-repository `.agents`, `.cursor`, or `.claude` folder appeared and no tracked source file changed.
6. Use read-only GitHub Actions token permissions; cancel superseded runs on the same branch to conserve runner time.

## Safety and decisions
- New CI does **not** set the Windows User Profile production or CI-only feature gate.
- All filesystem lifecycle tests must continue using the test suite's pre-existing isolated fixtures; do not use real-user HOME paths.
- No third-party runtime is launched by this workflow.
- Existing native Windows security CI and its strict ACL checks are unchanged.
- No ranking, benchmark judgments, License policy, Registry Source IDs or Skill approval states are edited.
- This stage intentionally executes the complete existing test suite on each OS; any OS-specific test errors must be analyzed and repaired without masking them behind broad skips.

## Verification and acceptance
- Local: validate workflow YAML parser, Python syntax, full suite and Git diff hygiene before Git commit.
- Remote: require success for **all three** OS jobs. Record job IDs, test counts, known skips and an explanation for any platform-specific divergence.
- Recheck working-tree cleanliness, staged allowlist, secret patterns, fast-forward ancestry and non-force Git push.
- After acceptance, keep Windows User Scope writes disabled until a separate explicit security review; this matrix is not a live host certification.

## Remaining work
- Observe matrix; fix any platform errors narrowly; re-run until all jobs are green.
- Add native cross-host discovery separately if required; full Python test coverage does not establish live Cursor/Claude Code integration or third-party sandbox readiness.

## Development findings from the first local Phase 56 regression

After fast-forwarding the CI-produced metadata commit `461d9c2`, the full macOS test run originally failed on the **expected fail-closed behavior** of `tools/benchmark_reconcile.py`: one pinned historical Skill now has a different Git Blob. This is **content drift**, not merely a source-ID remap.

- Historical ID: `GASL-SRC-91218ab531241df1d0a6` — `coreyhaines31/marketingskills/skills/seo-audit/SKILL.md`.
- Previous current source: `GASL-SRC-e69f6e5eff3b644e6690`, commit `8a0c22d677e6`, blob `1a4fd7536e099e24f841444f621497fc8fd1d768`.
- Refreshed current source: `GASL-SRC-26492c8e53144afa4be6`, commit `8fd2fcade2fd`, blob `8e969c81b41f5ebc820de2ecd51a7c8ab85847c0`.
- **Exactly one of 72** pinned historical judged sources failed exact same-blob matching in the refreshed catalog. It must **not** inherit the prior provisional grade; the old 148-judgment reconciled report is not valid for this catalog.

**Conservative test repair:** `tests/test_benchmark_reconcile.py` now validates that the full 26-query/148-judgment historical input is still intact; if any pinned blob changes or becomes ambiguous, it requires `reconcile()` to raise a clear fail-closed `ValueError` and asserts no mutation of source or label data. When all pinned blobs are unchanged, the original full 148-grade audit and same-blob assertions still run. There is **no skip** or synthetic new relevance grade.

**Platform guard:** `tests/test_user_profile_install.py` also accepts the exact expected **disabled** Windows User Profile gate error, in addition to its existing non-writable Fake HOME errors. The broad matrix explicitly sets `GASL_ENABLE_WINDOWS_USER_PROFILE_CI=0` to avoid enabling User Scope writes even on disposable runners. The narrower native Windows security workflow retains its previous specialized fixture-only gate.

**Verified local:** `python3 -m unittest tests.test_benchmark_reconcile tests.test_search_ranking_lab -q`: **18 OK**; `python3 -m pytest -q`: **798 passed, 28 skipped, 337 subtests passed**.

**Outstanding:** The separate provisional Search Quality pipeline still cannot generate a *new* full 148-judgment ranking report until the content-drift eligibility is resolved. Do not interpret a green general CI matrix as valid current-catalog search-quality metrics. Keep production ranking unchanged and do not relabel the changed Skill automatically.
