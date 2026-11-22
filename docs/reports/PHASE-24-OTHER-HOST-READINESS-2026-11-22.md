# Phase 24 — Cursor ACP and Claude Code readiness using real, credential-free CLI processes

**Date:** 2026-11-22  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Goal:** Extend the Phase-23 real Codex Host discovery work to the next two local Agent ecosystems, without inventing an unauthenticated Skill-listing API, starting a paid model turn, logging in, or installing a third-party Skill.

## 1. Exact capability boundary

Phase 23 verified **real Skill discovery** with Codex CLI `0.162.1` via `app-server` `skills/list`, using a generated inert GASL Skill in a disposable Linux profile. For Cursor and Claude Code, official documentation describes Skills but does **not** expose an equivalent, confirmed credential-free listing protocol with the same semantics. Cursor documents ACP `initialize`, which advertises protocol capabilities before authentication; the normal ACP session flow includes authentication and subsequent model-facing operations. Claude Code CLI supports `--version` without invoking the model.

This phase deliberately verifies **real CLI/protocol readiness** only:

| Host | Probe that can be performed without login | What it actually proves | What it does not prove |
|---|---|---|---|
| Cursor | Real `agent acp` process, protocol v1 `initialize`, validate `agentCapabilities` object | ACP server is launched and answers initialization in isolated test environment | `session/new`, `/skills`, any Skill discovery, authenticated account support or model execution |
| Claude Code | Real CLI `claude --version`, parse numeric semver from stdout | Vendor CLI is runnable in an isolated test environment without authentication | `.claude/skills` discovery, account setup, a Claude model turn or Skill invocation |

**Vendor references (inspected 2026-11-22):** Cursor ACP <https://cursor.com/docs/cli/acp>, Cursor CLI installer <https://cursor.com/docs/cli/installation>, Claude Code <https://code.claude.com/docs/en/skills> and CLI version reference <https://code.claude.com/docs/en/troubleshooting>.

## 2. New code

- `tools/other_host_protocol_probe.py`: accepts only two Host types and an absolute, nonsymlink local executable. Creates a fresh temporary work directory with empty `HOME`, `XDG_CONFIG_HOME`, `XDG_CACHE_HOME` and `TMPDIR`. The child receives a limited environment with **no inherited API keys or credential paths**; stdout is bounded and stderr discarded rather than exposed in public results.
- Cursor probe: sends exactly one ACP `initialize` request with filesystem and terminal capabilities set to false; validates JSON-RPC response `protocolVersion == 1` and an `agentCapabilities` object, then terminates the Host without authenticating, creating a Session or sending a Prompt.
- Claude Code probe: launches only `--version`, parses `major.minor.patch`, and terminates. No user profile or repository configuration is loaded from the developer's Mac.
- Both output sanitized status JSON. The result always contains `skill_discovery_verified=false`, `authentication_performed=false`, `model_turn_started=false`, `third_party_skill_executed=false`, `real_host_files_modified=false`, `production_installation_enabled=false`, irrespective of readiness result. This is intentional.
- `tests/test_other_host_protocol_probe.py`: eight synthetic subprocess tests, including correct ACP handshake, malformed/failed responses, isolated environment, real CLI version output, invalid executable paths, symlink refusal and unsupported Host rejection.
- `.github/workflows/gasl-other-host-readiness.yml`: separate Ubuntu jobs that install official Cursor CLI under a **runner-only temporary home** via the vendor install script, and the official Claude Code **native installer with pinned release `2.1.330`** under a separate temporary HOME. The install scripts are downloaded from the vendors' official domains and run only on the disposable GitHub runner. No account tokens or project Skills are supplied. These vendor install mechanisms are executed on a throwaway CI runner, **not the user's Mac**; the Cursor installer is vendor-distributed rather than artifact-content-pinned and therefore has normal upstream supply-chain risk.
- `README.md`, `docs/ROADMAP.md` and `.github/workflows/gasl-refresh.yml`: document narrow readiness semantics and avoid a redundant full metadata refresh for changes to the standalone probe only.

## 3. Security and privacy rules

- No real user profile, user-installed Skill, downloaded Skill content, personal files or machine credentials used.
- No `session/new`, `session/prompt`, Claude `--print`, login, MCP tool, or remote model API call.
- The probe is **not** a general-purpose Host execution API, installer, plugin manager or consent mechanism; no production Agent installation capability is activated.
- The external official CLI installation is restricted to GitHub-hosted, disposable Linux CI jobs. Workflow credentials are not preserved in Git checkout. No CI artifact contains Host stdout, credential values or raw executable paths.
- A clean ACP handshake and `--version` response are not accepted as real Skill discoverability. That remains a separate integration task requiring suitable authenticated testing or a documented read-only discovery API.

## 4. Baseline local checks

- `python3 -m unittest tests.test_other_host_protocol_probe -q`: **8 passing tests** using self-authored fake Host processes; these are not real Cursor or Claude Code integration evidence.
- Full test suite: **307 tests, 91 subtests PASS**; Python compilation and whitespace checks PASS.
- This report must be updated only after inspecting the actual GitHub Actions run, not by inferring success from the mock fixtures.

## 5. Next actions / caveats

1. Verify the two Linux jobs against actual vendor binaries and record their real success or failure. If packaging or installer startup fails, investigate and fix it; don't replace the actual Host probe with a fake while claiming live validation.
2. Keep Cursor/Claude Code **Skill discovery unverified** until an exact documented discovery procedure succeeds. The previously verified Codex Skill discovery remains valid only for the tested CLI/version and disposable Ubuntu profile.
3. Advance the separate install-plan transaction and explicit user approval flow only with a trustworthy host-specific adapter, versioned backup/rollback and no execution of untrusted Skill content. Do not enable production install implicitly after a readiness check.

**Phase 24 PASS:** real Cursor ACP readiness and real Claude Code CLI version verified on separate ephemeral Linux runners; 307 local tests passed. Neither Host's Skill discovery is verified; production installation remains disabled.

### CI iteration 1 — packaging fixes, no readiness claim

The first real workflow [run `45057215100`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45057215100) completed with **two failures** before either supported protocol could be exercised. Cursor's official installer created a symlinked launcher; the fail-closed probe requires the final binary path rather than following user-controlled symlinks. The official npm metadata for the selected Claude Code package exposed a `bin/claude.exe` target on Linux and the probe refused to run it. Both fail-closed behaviors were correct. The CI workflow now resolves the Cursor launcher to its real, executable target and uses the vendor's documented **native Linux installer** for Claude Code release `2.1.330` instead of the mismatched npm binary. The next real CI run must independently verify both Host readiness checks.

### CI iteration 2 — both actual Host readiness jobs PASS

- Workflow [run `45057489934`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45057489934), triggered by non-force publication of the corrected workflow, **completed / SUCCESS** with **two successful jobs** on ephemeral `ubuntu-24.04`.
- Cursor: official installer created the test-only CLI, its launcher was resolved to a regular executable without weakening the probe's symlink guard, and the **actual Cursor ACP server** returned `protocolVersion=1` and `agentCapabilities` at `initialize`. Recorded `status=real_host_readiness_verified`, `reason_code=cursor_acp_initialized_without_authentication`, `real_host_protocol_verified=true`, **`skill_discovery_verified=false`**.
- Claude Code: official native Linux installer installed version **`2.1.330`** into an isolated temporary HOME and the **actual vendor CLI** responded successfully to `--version` with `host_version=2.1.330`. Recorded `status=real_host_readiness_verified`, `reason_code=claude_cli_version_verified_without_authentication`, `real_host_protocol_verified=true`, **`skill_discovery_verified=false`**.
- In both jobs, CI asserted `authentication_performed=false`, `model_turn_started=false`, `third_party_skill_executed=false`, `real_host_files_modified=false` and `production_installation_enabled=false`. No API key, account login, model prompt, Skill installation, Skill invocation or actual developer Host configuration was used.
- The first failed run remains documented above. The corrected fix commit `9c2f247` was safely merged with the separately generated metadata refresh commit `9df13ab` and published through a normal non-force push in merge commit `8f67925`.
- All source and report changes were screened for sensitive data; the public Commit includes **no private local Skill packages, account credentials, user Home directories, or raw private audit ledgers**.

**Explicit residual gap:** This success cannot be extrapolated to `skills/list`, Host model execution, real local installation or support for every downloaded Skill. The Phase-23 Codex `skills/list` result is stronger than this Phase-24 readiness result and remains the only independently verified Host-side Skill discovery test.
