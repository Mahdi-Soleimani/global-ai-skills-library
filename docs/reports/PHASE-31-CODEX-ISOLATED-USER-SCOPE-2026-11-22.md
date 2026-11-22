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

## 4. Real Codex CI evidence — pending initial Phase-31 run

The existing Ubuntu real-Codex workflow is extended with a third actual App Server lifecycle using `--scope user --test-one-time-receipt`. It uses pinned `@openai/codex@0.162.1` in `$RUNNER_TEMP` and asserts:

- `scope=user` and `isolated_home_profile_used=true`;
- `real_home_or_codex_profile_accessed=false`;
- `absent_before_install=true`;
- `inert_skill_discovered_after_install=true`;
- `absent_after_rollback=true` and `fixture_rollback_verified=true`;
- `one_time_fixture_receipt_consumed=true`;
- `human_confirmation_verified=false`, `model_turn_started=false`, `authentication_performed=false`, `third_party_skill_installed_or_executed=false`, `real_host_files_modified=false`, and `production_installation_enabled=false`.

Record the actual run ID and observed log result here only after the workflow completes successfully. Unit/fake-Host tests are not a substitute for this acceptance test.

## 5. Scope and non-goals

This phase validates the *user-scope directory convention and discovery* using a genuine Codex CLI process with an isolated HOME. It is not an installation into the developer's real home, is not persistent, does not run downloaded third-party Skills, does not assess any Skill's license or trustworthiness, and does not prove real-human consent. The target remains a disposable profile owned by GASL. Production installation, persistent profile changes and third-party execution remain disabled.

**Phase 31 acceptance:** local regression suite PASS; real Codex user-scope CI PASS is required before marking the phase complete.
