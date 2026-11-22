# Phase 30 — Expiring, one-time, explicitly confirmed consent receipts for fixture-only Skill installation

**Date:** 2026-11-22  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Scope:** Introduce a distinct, version/target/action-bound approval step, reject reused or stale consent, and use it in the real Codex isolated discovery/rollback test. **This is not a real-user-profile installer and does not authorize execution of a third-party Skill.**

## 1. Starting point: GitHub branch history reconciled without data loss

At the beginning of this phase, GitHub connectivity from the Mac returned. The two independent Phase-29 commits and the latest generated source-catalog metadata were fetched and merged without `reset --hard` or force push. Local and GitHub `main` were synchronized at commit [`babfabc`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/babfabc5a5c45325affaf8da4555b391ccbef33c), with a clean working tree. The full Phase-29 regression suite passed again (**392 tests, 179 subtests**). The new Phase-30 work is based on this clean synchronized state.

## 2. User-reviewable consent contract

- A dedicated **pending receipt** is created with a randomly generated 128-bit request ID, `plan_id`, pinned archive SHA-256, canonical temporary destination binding, Host (`codex`, `cursor`, `claude-code`), scope (`project`/`user`) and `install`/`replace` action. The selected target must be in a newly created, marked GASL temporary fixture. No arbitrary user home or production Agent target is accepted.
- The request displays a distinct literal phrase including the operation, Host, scope and shortened unique receipt/binding fingerprints. An **independent confirmation call** must present the exact phrase while the ZIP and destination are unchanged. This is not the Phase-28 deterministic challenge re-entered by itself.
- The receipt expires 30–300 seconds after creation (default 180). State transitions are strictly `pending → approved → consumed`. A receipt cannot be confirmed twice or redeemed more than once. There is no transparent renewal or reset of a receipt in the same fixture.
- The receipt is signed with **HMAC-SHA256** using a fresh, local 256-bit random key stored with owner-only permissions in the private fixture. The private record is bounded, has strict schema validation, is rewritten through an `fsync`ed temporary file, and is read only after checking file type and link counts. This provides local modification detection, **not user authentication, non-repudiation or defense against a same-user attacker who can read the local signing key**.
- The receipt is consumed **before staging any ZIP data** and **while holding the same nonblocking exclusive POSIX lock** used by the Phase-28 transaction. If the transaction fails after consumption, the receipt stays consumed and cannot be replayed; it must not be re-authorized silently.
- Expired requests, changed ZIP content, changed target files, wrong Host/Scope/operation, tampered receipt or signing key, wrong phrase, wrong request ID, collision/symlink and unsupported platform fail closed.

### Interactive CLI (manual operation of a disposable test only)

```bash
./gasl consent-fixture-interactive \
  --plan-id YOUR_EXACT_PLAN_ID \
  --agent codex --scope project --action install \
  --acknowledge-fixture-only GASL_DISPOSABLE_FIXTURE_ONLY
```

This command **requires an interactive TTY**; without a TTY it exits before creating a fixture or installing any content. It prints the version and target binding, and stops until the operator types the full confirmation phrase. It then stages the selected private ZIP only in a new temporary GASL profile, verifies installation, performs rollback and destroys the profile. It never accepts a real Host destination. A typed phrase shows an explicit local user gesture but **does not prove identity** and **is not real production-install consent**.

## 3. Implemented files

| Path | Change |
|---|---|
| `tools/fixture_explicit_consent.py` | HMAC-protected, short-lived request/confirm/consume lifecycle with private fixture-only ledger and strict identity checks |
| `tools/fixture_transaction_v2.py` | Optional single-use consent redemption inside the existing exclusive transaction lock before ZIP staging |
| `tools/gasl.py` | New `consent-fixture-interactive` command with a hard TTY gate; optional `--test-one-time-receipt` on isolated Codex test CLI |
| `tools/codex_transaction_e2e.py` | Reuses genuine isolated Codex install/list/rollback but tests a **synthetic** one-time receipt before staging; result keeps `human_confirmation_verified=false` |
| `tests/test_fixture_explicit_consent.py` | Valid/invalid confirmation, expiry, signature/permission tamper, target/package drift, replay, cross-process replay, first/upgrade, 36-case matrix, non-TTY denial |
| `tests/test_codex_transaction_e2e.py` | Additional fake-Host tests of positive and negative one-time receipt enforcement |
| `.github/workflows/gasl-codex-transaction-e2e.yml` | Adds synthetic consent regressions and a **second real Codex 0.162.1 Host cycle** with receipt consumption assertions and explicit automated-not-human reporting |
| `README.md`, `docs/ROADMAP.md`, this report | Documentation and exact readiness boundaries |

No new Python runtime dependencies were introduced. POSIX `fcntl` remains mandatory for the fixture transaction; Windows fails closed until an explicitly tested lock implementation exists.

## 4. Local acceptance evidence

- **419 tests and 223 subtests PASS** on the Mac, including 25 Phase-30 consent test methods, 2 additional Codex integration unit cases, and a 36-case action/scope/Host/checkpoint matrix using synthetic pinned packages.
- Tested missing/incorrect/expired approval, changed ZIP, source drift, stale or changed target, HMAC tampering, signing-key tampering and owner-only permissions, symlinked files, failed staging after consumption, repeated use after rollback, cross-process confirmation and reuse refusal, and hardlinked receipt rejection. No real personal Host directory is read or written.
- The new interactive CLI **refuses a piped or otherwise noninteractive confirmation**. No automated test is claimed as a human interaction.
- Independently used the real locally private `academy-guide` ZIP (pinned Phase-25 `plan_id` `f52f11b345714191c780bd63b6e18e1d05a9f2ed3257c3b791a9e2fa00e45fcb`) in a freshly marked temporary Codex project. Both `install` and `replace` cases consumed a simulated test receipt once, copied original ZIP files as data, verified the installed file, rolled back, and preserved the previous inert fixture content. This test **did not launch Codex or run `academy-guide`**. The private archive, original license text and receipt key never enter public Git.
- Source compilation and `git diff --check` PASS. A full clean public Git archive and real Linux Codex CI must be observed and recorded separately after the new source commit is published; local fake-Host tests are not proof of real Host integration.

## 5. Real Codex CLI and Linux CI evidence — observed SUCCESS

- [Real Codex workflow run `45069553527`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45069553527) completed **SUCCESS** on `ubuntu-24.04`, using actual pinned `@openai/codex@0.162.1` installed under `$RUNNER_TEMP` with npm lifecycle scripts disabled.
- Synthetic unit tests ran first. Two **independent actual Codex App Server** cycles then passed. In the second, the CI programmatically supplied the exact simulated confirmation phrase to the test-only receipt system, and consumed that receipt under the same POSIX lock as staging.
- The actual job logs report `status=real_codex_inert_install_discovery_rollback_verified`, with `absent_before_install=true`, `inert_skill_discovered_after_install=true`, `absent_after_rollback=true`, `fixture_rollback_verified=true`, **`one_time_fixture_receipt_consumed=true`**, and **`human_confirmation_verified=false`**. CI printed `REAL_CODEX_ONE_TIME_FIXTURE_RECEIPT=PASS; HUMAN_APPROVAL=NOT_TESTED`.
- [Locked-fixture transaction workflow run `45069553602`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45069553602) also completed **SUCCESS** independently. Neither job used real user Agent profiles, account credentials, a model turn, downloaded third-party Skill ZIPs or a real-user install permission.
- The successful real Host validation proves that the test-only receipt does not break Codex Skill discovery/rollback. **It does not prove a human authorized any installation**, that actual user profiles are protected against adversarial external writers, or that unreviewed Skills are safe.


## 6. Public Git commit, privacy audit and source verification

- The Phase-30 source commit [`5dc90c9`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/5dc90c9b0a45e7e7e4bb5be6c2a844e9046ab692) was published to `main` by a **normal non-force Git push** after validating a clean local worktree and confirming that the remote branch had not advanced at push time.
- Exactly **10 allowlisted first-party files** (code, tests, workflow, README, roadmap and report) were staged. A staged search for private keys, API/GitHub tokens, bearer credentials, actual user-home paths, personal email/telephone values and credential-bearing URLs returned **zero findings**.
- Locally downloaded Skills and original license text remained under ignored `private/install-bundles/` and were not included in the Git commit or CI artifacts. No real user-profile paths or signing keys were published.
- A completely clean `git archive HEAD` checkout, with `.git`, `private`, `catalog`, `storage` and `reports` absent, passed **419 tests, 223 subtests**, Python byte-compilation, both CLI-help checks and the catalog index smoke (**4,431 skills**). No private assets were created in that checkout.

## 7. Residual production gates

1. **Identity and scope:** this phase proves a local test action and one-time receipt only; it does not authenticate a real human, authorize production, or establish organization/policy ownership of the target directory.
2. **Real Host installation:** no user profile installation endpoint was added. The only write target is a GASL-marked disposable profile. Runtime/Host verification currently covers Codex and only a self-authored harmless Skill.
3. **Filesystem durability:** cooperative `flock` + `fsync` + fixture rollback is not a power-loss durability guarantee or protection against noncooperating external filesystem writers.
4. **Untrusted content:** passing static checks, metadata pinning and file transfer never grants permission to run third-party Skill instructions or scripts. The original package license and provenance require separate review.
5. **Other systems:** Cursor and Claude Code need independent real Skill discovery/rollback checks, and Windows needs a dedicated tested lock/transaction implementation before production rollout.

**Phase 30 implementation, local regressions, and real isolated Codex/Linux CI: PASS. Human-approved real Agent installation: NOT IMPLEMENTED and NOT TESTED.**
