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

## Windows full-suite failure analysis and platform eligibility correction

[First matrix run 45282313869](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45282313869) on `2fa01c7`:
- Ubuntu: **798 passed, 28 skipped**.
- macOS: **798 passed, 28 skipped**.
- Windows: **189 failed, 631 passed, 6 skipped**. This is **not a successful full-Windows-suite run**.
- Of the 189 Windows failures, **183** occurred inside thirteen **legacy POSIX-only** test modules, depending on `codex_project_install.py`'s original `fcntl`/legacy `.gasl-managed/` engine, POSIX `fixture_transaction_v2.py` with `flock`/directory `fsync`, or POSIX synthetic executable/host-protocol fixtures. Those engines are not Windows-native and **must not be enabled by bypassing their platform gates**; Phase 53 deliberately introduced a separate Windows Codex project state under `.gasl-managed/hosts/codex/` to avoid legacy receipt adoption.
- The other six failures are portable test expectation mismatches: Windows legitimately supports Codex in the new Host adapter, a Windows user-scope gate is disabled in the broad CI matrix, and native Windows User Profile tests need a *locally scoped, read-only* CI gate. Test assertions and temporary test scopes have been corrected; no production security validation is loosened.

**Explicit matrix policy after this finding:** Ubuntu/macOS continue to run the full original `pytest` suite without exclusions. Windows runs the full **Windows-supported** suite, explicitly excluding ONLY these thirteen modules in the workflow (no global test skipping or rewriting the legacy installer into an unsafe Windows mode):

1. `tests/test_codex_backup_review.py`
2. `tests/test_codex_legacy_reconcile.py`
3. `tests/test_codex_provenance_compare.py`
4. `tests/test_codex_uninstalled_restore.py`
5. `tests/test_codex_project_install.py`
6. `tests/test_codex_explorer_handoff.py`
7. `tests/test_fixture_explicit_consent.py`
8. `tests/test_fixture_transaction_v2.py`
9. `tests/test_codex_transaction_e2e.py`
10. `tests/test_codex_discovery_probe.py`
11. `tests/test_codex_pinned_bundle_e2e.py`
12. `tests/test_codex_third_party_discovery.py`
13. `tests/test_other_host_protocol_probe.py`

**Guard:** a dedicated Windows CI step asserts the two core POSIX legacy modules still lack `fcntl`, preventing these exclusions from silently persisting after a proper port. The existing separate native Windows test workflow is **not excluded** and continues full SID/ACL, Project Scope, User Profile fixture, Queue and lock tests. The broad matrix continues to set the User Profile gate to `0`; individual read-only Windows security fixtures may temporarily patch that flag in their own narrow test context.

**Honest acceptance boundary:** A green three-job platform-eligible matrix does **not** prove that these thirteen legacy POSIX modules are supported on Windows. Their safe Windows migration, if still necessary, remains distinct future work subject to the original Windows Codex state separation. No existing test is skipped simply because its ACL, SID, ownership or Lock assertion failed on a supported Windows path.

**Next verification:** rerun complete macOS local tests, then require the three platform-eligible CI jobs to pass. Capture Windows passed/skipped counts. Cross-platform *all-module* completeness remains open until legacy POSIX-only engines have safe native Windows replacements or have been explicitly retired.

## Final CI acceptance — platform-eligible matrix (2026-11-23)

**Code revision under test:** `3f2a67fcc28cd312488f64122e0cd210a1c92204`.

**Verified GitHub Actions run:** [45283916154](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45283916154), **all three jobs completed successfully**.

| Runner / Python | Job ID | Pytest result | Status |
| --- | --- | --- | --- |
| Ubuntu / 3.13 | `138075160377` | `798 passed, 28 skipped` (38.45s) | SUCCESS |
| macOS / 3.13 | `138075160251` | `798 passed, 28 skipped` (84.80s) | SUCCESS |
| Windows / 3.13 | `138075159825` | `580 passed, 6 skipped` (172.41s) | SUCCESS |

- Windows's 586 collected tests **exclude thirteen known legacy POSIX-only modules by explicit filename**. This is not a claim of all 826 collected tests running on Windows. The earlier comprehensive run `45282313869` (189 failures on Windows) remains documented, not erased.
- Native Windows Project/Profile/Queue security regression [run 45283915905](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45283915905) **SUCCESS**; separate [Cursor/Claude Project run 45283916024](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45283916024) **SUCCESS**; [User Profile lifecycle run 45283916376](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45283916376) **SUCCESS**.
- Native security and transaction tests were not removed from the platform-eligible matrix; the legacy fcntl and fsync-dependent modules have not been falsely ported or marked Windows-supported.
- Scope remained fixture-only. `GASL_ENABLE_WINDOWS_USER_PROFILE_CI=0` in the broad matrix; no actual user HOME writes, third-party Skill execution, License or publication approval.
- Search Quality run `45282313905` is separately **FAILED**, intentionally fail-closed on a changed pinned Git Blob for `seo-audit`. This does not permit transfer of the two old provisional grades (`seo-en`, `seo-fa`) to the new blob. Independent new-catalog search-quality measurements remain blocked, and no ranking production change was made.

**Phase 56 acceptance decision:** Automated cross-platform **platform-eligible** regression coverage is accepted. **Full parity of the 13 POSIX-only legacy test modules on Windows remains open**; do not label it complete. The content-drift quality benchmark review also remains open independently.
