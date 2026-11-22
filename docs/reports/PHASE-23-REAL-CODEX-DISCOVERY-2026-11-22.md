# Phase 23 — Real Codex Skill discovery in an isolated, credential-free profile

**Date:** 2026-11-22  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Scope:** Prove that the **real Codex Host** can discover an inert GASL-authored local Skill through its supported JSON-RPC App Server interface, instead of inferring compatibility from folder names or a mocked Host. Do not modify user Agent profiles or execute third-party Skill content.

## 1. Baseline and source of truth

In Phase 22, `codex`, `cursor` and `claude` CLI binaries were **not visible on `PATH`** on the Mac, and no real Host discovery was observed. Phase 21 checked only documented path conventions using disposable inert files.

The official Codex App Server protocol documents `initialize`, the `initialized` notification and `skills/list` with `cwds` and `forceReload`:

- <https://learn.chatgpt.com/docs/app-server> (official protocol, read 2026-11-22).
- `skills/list` returns per-working-directory `skills` entries with `name`, `path`, `enabled` and discovery errors.
- No model turn, authentication, install or Skill invocation is required to request the local Skill list. A successful `skills/list` response is genuine **discovery metadata**, not actual execution or proof that an arbitrary Skill is safe.

The isolated CI test targets `@openai/codex@0.162.1`, whose package and CLI entry point `bin/codex.js` were verified via the npm registry. The package is installed in the runner's temporary workspace **with `--ignore-scripts`**, not globally and not on the user's Mac.

## 2. Implementation

- New `tools/codex_discovery_probe.py`: creates a fresh disposable `project/.agents/skills/gasl-discovery-probe/SKILL.md` containing **only self-authored inert text**; a separate empty `HOME`, `CODEX_HOME`, XDG config/cache and temp directories.
- The child process environment passes only PATH and those fresh directories; **no inherited API keys, account tokens, real HOME, or project configuration** are forwarded.
- Starts a trusted Codex CLI file as `app-server` using stdio (never `codex exec` or any AI model turn), sends JSONL `initialize`, waits for the handshake, sends `initialized` and then `skills/list` with `forceReload=true`.
- Accepts discovery **only** when there is exactly one matching Skill, enabled, at the exact canonical path of the generated temporary fixture. Missing, duplicate, disabled, wrong-path or malformed results fail closed. Uses bounded response size and execution time; terminates the child afterward.
- The published JSON result contains only verification booleans/status codes, **never user executable paths, auth fields, raw messages or Skill content**.
- `tests/test_codex_discovery_probe.py`: 10 unit tests using a GASL-authored standalone fake JSON-RPC Host to test the protocol handshake and all fail-closed conditions. Those tests are **not counted as real Host proof**.
- `.github/workflows/gasl-codex-real-discovery.yml`: dedicated lightweight Ubuntu workflow, read-only repository permission, credential-free checkout, exact Codex npm version under `$RUNNER_TEMP`, `--ignore-scripts`, then genuine Host `skills/list` verification. No artifact includes source packages, credentials or local paths.
- `.github/workflows/gasl-refresh.yml`: excludes changes confined to the new Host probe module from full-library metadata refreshes, avoiding redundant API work when refining only this isolated test.

## 3. Safety and evidence distinction

The CI probe **does not** execute a Skill, install GASL packages into a real user Host, start a model turn, change any Host configuration on the Mac, or validate Cursor/Claude Code. The Codex runtime is installed and started **only on the disposable GitHub-hosted Ubuntu runner**; its clean local test profile has no account credentials. The npm installation itself necessarily retrieves the published Codex package, but downloaded Skill content is never used as a test input.

No production Skill installer was enabled. Prior integrity scanning, user approval gates and sandbox limitations remain unchanged. An arbitrary Host process could still have its own telemetry/network behavior; the explicit guarantee here is that GASL passes no account keys and requests only the local Skill list, not that the entire third-party Host runtime has zero background network traffic.

## 4. Local tests before CI

- `python3 -m unittest tests.test_codex_discovery_probe -q`: **10 passing tests** with synthetic Host interactions.
- Full test suite: **299 tests + 85 subtests passed**, zero failures.
- Python compilation and `git diff --check`: pass.
- Actual Codex CLI availability on the Mac remains **unverified**, and no real Host was launched on the Mac.

## 5. Live CI status and next steps

The real Linux workflow completed successfully. Codex (the actual `@openai/codex@0.162.1` CLI) returned an exact matching, enabled, inert `gasl-discovery-probe/SKILL.md` via App Server `skills/list`. This is **real Codex Skill discovery in that ephemeral Linux profile only**—not Mac Host availability, model invocation, real installation, or approval of downloaded Skills.

After real Codex discovery, extend the same controlled approach to other actual Host CLIs where supported, using new disposable profiles. Do not install downloaded Skills or touch a user's existing Agent configuration without a separate, explicit real-install approval and rollback integration tests.

**Phase 23 PASS:** live Codex App Server discovery verified; real Skill installation and execution remain disabled.

## 6. Observed real GitHub Actions evidence

- Source commit: [`4171b0e`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/4171b0e3ed1b9379e1da2839625f07f1665b6e57) (only seven allowlisted code/test/report/CI files; staged secret scan found **0 sensitive matches**).
- Actual Host workflow: [`45055665888`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45055665888) — **completed / SUCCESS** on Ubuntu 24.04.
- Executed, in order: checkout with `persist-credentials=false`; Node setup; mocked-protocol unit tests; npm installation of exact `@openai/codex@0.162.1` **under runner temp** with lifecycle scripts disabled; then `python3 tools/codex_discovery_probe.py` against the **real CLI**.
- The live result JSON contained `status=verified_isolated_codex_discovery`, `reason_code=exact_inert_skill_discovered`, `isolated_skill_discovery_verified=true`.
- All safe-operation flags remained **false**: `authenticated_user_profile_accessed`, `model_turn_started`, `third_party_skill_executed`, `real_host_files_modified`, `production_installation_enabled`. CI additionally asserted these flags independently.
- No model prompt or turn was sent: only `initialize`, `initialized` and `skills/list`. No user account was connected and no downloaded third-party Skill was executed or installed.
- This result establishes that the documented project Skill location is **actually discoverable by the tested Codex CLI version** on an ephemeral Linux Host. It does **not** test Cursor, Claude Code, Windows or a Codex app on the user's Mac.

## 7. Routine metadata refresh and safe publication

- The separate catalog refresh [run `45055665873`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45055665873) **completed / SUCCESS**, including Python regressions, source rediscovery, search vocabulary, index/router checks and allowlisted metadata-only publication.
- Refresh commit [`6173730`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/6173730) changed only the existing machine-generated registry and reconciliation outputs. It was fetched for safe non-destructive reconciliation with the Phase-23 report update.
- Phase 23's actual Host CI remains independently SUCCESS; the refresh is not used as a substitute for `skills/list` evidence.
