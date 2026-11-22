# Phase 31 — Real Codex user-scope discovery inside an isolated HOME

**Date:** 2026-11-22  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Objective:** Extend the Phase-29 real Codex App Server transaction test from project-local Skills to Codex's user-wide Skill directory, while using a newly created empty HOME and CODEX_HOME. This validates actual Host discovery and rollback without reading or writing the developer's existing profile.

## 1. Verified target convention

The current OpenAI CLI Skill installation guide documents these Codex destinations:

- Project scope: `.agents/skills/`
- User scope: `~/.agents/skills/`

Official source: [OpenAI CLI — Install a Skill](https://developers.openai.com/api/reference/cli) (accessed 2026-11-22). The test deliberately uses the user directory under its private temporary HOME; it does not infer or use the machine's real home directory.

## 2. Implementation

- `tools/codex_transaction_e2e.py` now accepts `scope=project|user` and includes the scope in the synthetic immutable Plan ID and ZIP manifest.
- For `project`, the target remains `<fixture>/workspace/.agents/skills/gasl-discovery-probe/`.
- For `user`, the target is `<temporary-HOME>/.agents/skills/gasl-discovery-probe/`. The Host process receives a dedicated `HOME` and `CODEX_HOME`, isolated XDG cache/config and TMPDIR. The project CWD remains `<fixture>/workspace` so Codex must discover the user-wide Skill from its isolated HOME.
- The Host protocol is still limited to `initialize` and `skills/list`. It never performs authentication, starts a model turn, invokes a Skill, or reads the user's actual home.
- The same three real Host observations are required: absent before installation, present and enabled at the exact user-scope fixture path after installation, absent after rollback.
- `--test-one-time-receipt` adds the Phase-30 receipt lifecycle and consumes the exact receipt under the transaction lock. CI-generated confirmation is explicitly synthetic and `human_confirmation_verified=false`.
- `gasl codex-transaction-e2e --codex-bin ... --scope user --test-one-time-receipt` exposes the test path for a trusted local CLI. It creates and destroys only its own disposable profile.

## 3. Local test evidence

- **422 tests and 223 subtests PASS** on the Mac after implementation.
- New tests cover project and user scope, user-scope receipt consumption, invalid-scope rejection, exact isolated HOME path, separation from CODEX_HOME, and fixture rollback.
- The developer Mac did not have a Codex CLI executable available on PATH. A large native platform package was not installed persistently; the local user's `~/.codex` and `~/.agents/skills` were not read, modified, or used. Real Codex user-scope proof is delegated to the already pinned CLI inside GitHub Actions.
- Python compilation, CLI help and `git diff --check` pass locally.

## 4. Real Codex CI evidence — PASS

- [Phase-31 real Codex workflow run `45073141936`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45073141936) completed **SUCCESS** on `ubuntu-24.04` using pinned `@openai/codex@0.162.1` from `$RUNNER_TEMP`.
- The workflow ran fake-Host regressions, receipt tests, then actual Codex project-scope and user-scope App Server lifecycles. The project lifecycle and prior one-time receipt lifecycle remained green.
- The actual user-scope log output reports `scope=user`, `isolated_home_profile_used=true`, `real_home_or_codex_profile_accessed=false`, `absent_before_install=true`, `inert_skill_discovered_after_install=true`, `absent_after_rollback=true`, `fixture_rollback_verified=true`, and **`one_time_fixture_receipt_consumed=true`**.
- It also explicitly reports **`human_confirmation_verified=false`**, `model_turn_started=false`, `authentication_performed=false`, `third_party_skill_installed_or_executed=false`, `real_host_files_modified=false`, and `production_installation_enabled=false`. The CI summary prints `REAL_CODEX_USER_SCOPE_ISOLATED_HOME=PASS; HUMAN_APPROVAL=NOT_TESTED`.
- The [daily source catalog refresh run `45073141767`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45073141767) was still running when this report was first updated; its final result is independent of the Phase-31 acceptance test.

Unit/fake-Host tests are supplementary; the acceptance evidence above comes from the real pinned Codex App Server process.


## 5. Scope and non-goals

This phase validates the *user-scope directory convention and discovery* using a genuine Codex CLI process with an isolated HOME. It is not an installation into the developer's real home, is not persistent, does not run downloaded third-party Skills, does not assess any Skill's license or trustworthiness, and does not prove real-human consent. The target remains a disposable profile owned by GASL. Production installation, persistent profile changes and third-party execution remain disabled.

**Phase 31 acceptance: PASS.** Local regression suite and clean public checkout pass (422 tests, 223 subtests); real pinned Codex project- and user-scope App Server lifecycles, receipt consumption and rollback all pass in GitHub Actions run `45073141936`. Human-approved installation into a real user profile remains out of scope and is not implemented.
