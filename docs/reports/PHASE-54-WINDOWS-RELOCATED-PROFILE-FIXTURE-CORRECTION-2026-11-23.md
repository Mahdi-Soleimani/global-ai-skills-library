# Phase 54 — Windows relocated-profile fixture ACL correction

**Date:** 2026-11-23  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Baseline HEAD:** `31c5d580267bc80fd9aa36aada2467e91a74b11c`  
**Status:** Native Windows CI fixture-regression acceptance passed; production Windows User Scope remains gated.

## Objective and observed failure
The Windows native workflow run [45269179260](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45269179260), job `138024092496`, failed exactly one test: `test_relocated_profile_cannot_reuse_foreign_receipt_even_if_files_copied`. Its expected `different user profile` rejection was preempted by `Trusted Windows profile owner lacks explicit current-user modify/delete ACL`. The remaining 15 Windows project tests and 18 Windows SID/ACL tests passed. This is a **test precondition failure candidate**, not permission to relax the security verifier.

## Files and changes
- `tests/test_user_profile_install.py`: only inside the relocated-profile test, the **second disposable fake HOME** now has inherited ACLs removed, a full-control inherited ACE granted explicitly to the **current test token SID**, and its owner assigned to that same SID. Each `icacls` operation is checked for success. The existing strict `windows_profile.verify_owned_path` then validates this root before the copied receipt is examined.
- No production security policy, Windows ACL parser, transaction engine, user account, live HOME, Agent directory, system time, or CI test selection was modified.
- The earlier `FILE_ALL_ACCESS` classification fix in commit `ea7be30` remains unchanged.

## Technical reasoning / threat boundary
The second fake HOME had been created via `mkdir()` without the explicit ACL hardening already applied to the first fake HOME. On Windows hosted runners, inherited ACL/OS ownership can prevent an unrelated *receipt identity* scenario from reaching its intended assertion. The correction is confined to a `TemporaryDirectory` test root; it does **not** introduce an Everyone/Users/Authenticated Users write grant and does **not** bypass SID, owner, DACL or reparse validation. Raw SID values and private paths are not added to this report.

The test still must reject a receipt copied to a different directory via the exact `different user profile` identity binding, leaving both original and relocated Skill trees intact. This is not a proof of production Windows User Scope safety and is not an approval for live user installations.

## Evidence prior to correction
- Windows workflow: `45269179260` (failure), test `test_relocated_profile_cannot_reuse_foreign_receipt_even_if_files_copied`.
- Runner trace: `tests/test_user_profile_install.py:414`; expected `different user profile`, observed missing explicit current-SID modify/delete ACL on relocated fixture.

## Verification after correction
On macOS:
- `python3 -m unittest tests.test_user_profile_install -q`: **25 tests, OK**.
- `python3 -m unittest tests.test_windows_user_profile.WindowsAclMaskClassificationTests -q`: **6 tests, OK**.
- `git diff --check`: **passed**.
- Windows-only `icacls` execution is **not testable on macOS**. Native Windows CI is required.

## Acceptance / outstanding
1. Native Windows CI must confirm the relocated-profile test reaches `different user profile`.
2. The entire Windows lifecycle suite, SID/ACL tests, project tests, and bundle/target/adapter regressions must pass without weakening the security policy.
3. Verify wrong-owner, Everyone-write, hard-link, junction, and real HOME safety protections remain enabled.
4. `GASL_ENABLE_WINDOWS_USER_PROFILE_CI` remains a **disposable CI-only gate**; Windows User Scope stays disabled for production until a separate explicit acceptance decision.
5. The independent Daily Source Catalog refresh regression (`26` remaps versus historical `24`) remains out of scope for this change.
6. No third-party Skill execution, real-user HOME write, manual relevance adjudication, public release, or clock change is authorized.

## Git and publication
Initial change is restricted to the single test file plus this report. Before pushing, verify allowlisted staged paths, secret patterns, `git diff --cached --check`, remote ancestry, and a normal non-force push. Record the new commit and native CI result in a follow-up report amendment only after observation.

## Verified native Windows acceptance (follow-up)
- Change committed and pushed on `main` as `0d0831f31c907f7b40f46132f856bc0e308d655c` (normal push, no force).
- [GitHub Actions run 45277306600](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45277306600), job `138052318204`: **SUCCESS**.
- Verified successful steps: Windows project transactions, actual SID/profile/ACL tests, disposable fake HOME lifecycle, private-bundle and adapter regressions, and no repository Agent directory/tracked-file modification check.
- The previously failing relocated-profile test is included in the successful lifecycle suite. **No test was skipped to conceal the failure**; the original platform-specific three lifecycle skips remain.
- Additional local macOS suite: `python3 -m unittest tests.test_user_profile_install tests.test_user_profile_wizard tests.test_host_adapters tests.test_host_target_preflight -q`: **97 tests, OK**.
- No live HOME, User Scope production feature flag, ACL policy or operating-system clock was changed.
- Production Windows User Scope enablement is deliberately a separate security/product decision; the temporary CI-only flag stays in place.
