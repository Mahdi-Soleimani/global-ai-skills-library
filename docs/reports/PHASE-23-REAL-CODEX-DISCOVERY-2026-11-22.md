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

The real Linux workflow must **complete successfully** before reporting Codex as verified. If it fails, preserve failure evidence and fix the exact protocol/packaging cause without silently substituting a fake Host or relaxing path/enablement checks.

After real Codex discovery, extend the same controlled approach to other actual Host CLIs where supported, using new disposable profiles. Do not install downloaded Skills or touch a user's existing Agent configuration without a separate, explicit real-install approval and rollback integration tests.

**Local implementation complete; real CI result pending first actual workflow run.**
