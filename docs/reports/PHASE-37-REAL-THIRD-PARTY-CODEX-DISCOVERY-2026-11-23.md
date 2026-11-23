# Phase 37 — Real pinned third-party Codex Skill discovery and rollback

**Date:** 2026-11-23  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Base commit:** `76a07c3ff23aca56c9cd432a4e972d6f6c4fb9ac` on `main`  
**Outcome:** PASS on real macOS Codex CLI and on isolated Ubuntu GitHub Actions.

## 1. Objective and fixed boundary

Close Phase 36's remaining real-Host evidence gap by checking that an unmodified third-party `SKILL.md` is discoverable and enabled in **a newly created, disposable Codex user HOME**, and that Codex no longer discovers it after verified removal.

The operation is **discovery-only**, not a production installation or functional execution of a Skill. The prior user instruction to proceed with the specifically described Phase 37 test was the operational go-ahead; a source-bound technical acknowledgement string was supplied to the CLI/manual workflow. This acknowledgement is not a digital signature, identity proof, or an assertion that the user personally typed the literal approval phrase.

No existing Codex user HOME, real `~/.agents/skills`, account configuration, authentication, model turn, untrusted Skill command, Python dependency, MCP server, or public package distribution was involved.

## 2. Exact source and integrity evidence

| Item | Verified value |
|---|---|
| Skill | `python-mcp-server-generator` |
| Source record | `GASL-SRC-4231997ac2c731ce1fe3` |
| Repository | `github/awesome-copilot` |
| Commit | `f10fdb8b2660ce85c98f220b2f1ca24653768a5c` |
| `SKILL.md` Git Blob | `2af91072828c27eec9f758262be17745982f7a3e` |
| License evidence | MIT, as reviewed in Phase 35 |
| Private bundle Plan ID | `ce160707029a12b300269ceafcd4f8c9414db3436819724090fe7ae6ee36e343` |
| Private ZIP SHA-256 | `8870d46717fe6a44589020556432f3c79c10cbb07364c4de48d0fe21c1f05367` |
| Private ZIP file count | 3; only `SKILL.md` was copied during discovery |
| Static scan | zero actionable findings at this pinned revision; **not** a security approval |

The local `./gasl install-bundle --verify-plan-id` returned `private_bundle_integrity_verified`. A separate `shasum -a 256` matched the expected ZIP digest, and the extracted `SKILL.md` independently matched the immutable Git Blob. `./gasl install-plan --id ... --agent codex --scope user` reported `actual_install_enabled=false` and `installation_allowed=false`; this phase did not alter these gates.

## 3. Actual macOS Host observation

- Environment: macOS on the connected development Mac, Python `3.13.9`, Codex CLI `0.167.0`.
- Clean Git baseline before the test: local `main` and `origin/main` both at `76a07c3`, with no tracked or untracked changes.
- Used the exact, regular (not symlink) Codex CLI executable obtained by resolving the installed launcher.
- Extracted only the verified `SKILL.md` from the preexisting ignored ZIP into an OS temporary directory.
- Invoked `tools/codex_third_party_discovery.py` with the exact source ID, Skill name, Git Blob and source-bound acknowledgement.
- The probe made only `initialize` and `skills/list` protocol requests, created a separately isolated `HOME`/`CODEX_HOME`, and removed the temporary Skill and test profile.

Actual result:

```json
{
  "status": "verified_temporary_third_party_codex_discovery_and_rollback",
  "source_git_blob_verified": true,
  "absent_before_install": true,
  "third_party_skill_temporarily_installed": true,
  "exact_skill_discovered_and_enabled": true,
  "absent_after_rollback": true,
  "temporary_profile_deleted": true,
  "model_turn_started": false,
  "authentication_performed": false,
  "third_party_skill_executed": false,
  "skill_commands_or_dependencies_executed": false,
  "real_home_or_codex_profile_accessed": false,
  "real_host_files_modified": false,
  "production_installation_enabled": false
}
```

The probe exited with code 0. Git status remained clean immediately after the test.

## 4. Actual GitHub Actions confirmation

Manual-only workflow: `.github/workflows/gasl-approved-third-party-codex-discovery.yml`.

- [Run `45166176466`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45166176466)
- Event: `workflow_dispatch` on commit `76a07c3`.
- Job `137663591414`: `completed / success`.
- OS: GitHub-hosted Ubuntu 24.04, isolated runner.
- Host: exact `@openai/codex@0.162.1` under runner temp, npm lifecycle scripts disabled.
- Input: only pinned public `SKILL.md`, fetched to runner temp with its Git Blob independently verified.
- Observed log markers: `PINNED_THIRD_PARTY_SKILL_BLOB=PASS` and `TEMPORARY_THIRD_PARTY_CODEX_SKILL_DISCOVERY=PASS`.
- The workflow verified discovery, exact path, enabled state, post-removal absence, disposable-profile cleanup, and all non-execution/non-real-profile flags.
- No third-party content or private ZIP was published as a workflow artifact.

**Evidence distinction:** This is a real, credential-free Codex App Server `skills/list` compatibility check. It does not validate a model's use of the Skill, Python MCP generation, package installation, production user-profile writes, or safety of future code execution.

## 5. Test suite and environment notes

- The default system Python does not have the optional `mcp` package installed, so unconstrained `python3 -m pytest -q` stopped at collection with `ModuleNotFoundError: mcp` in `tests/test_mcp_server.py`.
- Running all tests except that optional MCP integration module passed: **439 tests + 226 subtests**, 0 failures.
- `python3 -m compileall -q tools tests` passed.
- `git diff --check` passed.
- No runtime dependencies, project source code, actual Agent profiles, or packages were modified to work around the missing optional dependency.
- Previous Phase 36 Linux CI had already run the full 445-test/226-subtest suite on the then-published source. This report does not misrepresent the current Mac's excluded-module run as a complete suite.

## 6. Accepted scope and next engineering work

**PASS:** Third-party pinned `SKILL.md` discovery and verified rollback in real Codex on macOS **and** Linux, using disposable user-scope profiles.

**Still disabled:** real user-profile installation, persistent Skill activation, running untrusted Skill instructions, running generated MCP servers, auto-install/auto-update, and granting security approval from a clean static scan.

Next priorities: test an independent real Host's Skill-discovery path (Cursor or Claude Code, only where the vendor exposes a verifiable mechanism); design a separately consented production target transaction without weakening the current security gates; run the full project suite in a clean environment with optional MCP dependencies; and select a root license before claiming a formal open-source release.

All prior reports remain intact. This report contains public-safe metadata and observations, not Skill source contents, credentials, local HOME paths, or private ZIP bytes.
