# Phase 36 — Approval-gated third-party Skill discovery in a disposable Codex HOME

**Date:** 2026-11-22  
**Branch:** `main`  
**Candidate:** `python-mcp-server-generator`  
**Source record:** `GASL-SRC-4231997ac2c731ce1fe3`  
**Pinned commit:** `f10fdb8b2660ce85c98f220b2f1ca24653768a5c`  
**Pinned `SKILL.md` Git Blob:** `2af91072828c27eec9f758262be17745982f7a3e`

## 1. Objective and boundary

Phase 31 proved Codex user-scope Skill discovery using GASL-authored inert fixtures. This phase adds a separate, explicitly gated path to verify that the exact pinned third-party `SKILL.md` is discoverable by a real Codex App Server.

The probe installs **only the exact `SKILL.md` entry point** into a newly created temporary `HOME/.agents/skills/python-mcp-server-generator/` directory. It does not copy or execute the Skill's reference files, license, instructions, shell commands, or dependencies. This is sufficient to validate Host discovery and `skills/list`; it is not a full functional Skill test.

No actual test has been run yet. The workflow is intentionally `workflow_dispatch` only and requires the exact approval phrase as an input. It has no push, pull-request, or schedule trigger.

## 2. New local probe

`tools/codex_third_party_discovery.py` implements a bounded lifecycle:

1. Require an absolute regular Codex CLI executable, a regular UTF-8 `SKILL.md`, the exact source record ID, skill name, commit-pinned Git Blob SHA, and an exact approval phrase.
2. Verify the Git Blob and frontmatter `name` before launching Codex.
3. Create a new temporary root with separate `HOME`, `CODEX_HOME`, XDG cache/config, workspace and TMPDIR. The environment is allowlisted; user API keys and normal Agent profiles are not passed.
4. Start Codex App Server and send only `initialize` and `skills/list`; confirm the Skill is absent before copying.
5. Copy the verified `SKILL.md` into the temporary user-scope directory, then start a fresh Codex App Server and require exactly one enabled Skill with the exact expected name and file path.
6. Remove only the exact copied file after rechecking its bytes, query `skills/list` again, and require the Skill to be absent.
7. Delete the temporary root and report cleanup success.

The result explicitly records that no model turn, authentication, Skill execution, package/dependency execution, real HOME/profile access, persistent Host modification, or production installation occurred.

## 3. Manual GitHub Actions workflow

`.github/workflows/gasl-approved-third-party-codex-discovery.yml` is manual-only:

- Trigger: `workflow_dispatch` with a required `approval_phrase` input.
- Installs the previously validated exact Codex CLI `@openai/codex@0.162.1` under `$RUNNER_TEMP`, using `--ignore-scripts` and no persisted user profile.
- Fetches the candidate `SKILL.md` from its exact pinned public upstream commit into runner temp and verifies its Git Blob before the Host test.
- Calls the probe, checks all three observations and cleanup, and emits a metadata-only summary.
- Does not upload the Skill file, ZIP, logs containing Skill content, or any artifact. It does not start a model turn or execute any command from the Skill.

The full private review ZIP remains local under ignored `private/install-bundles/`; the workflow fetches only the public pinned `SKILL.md` needed for discovery. The user's actual `~/.agents/skills`, `~/.codex`, project directories and credentials are never read or modified.

## 4. Exact approval binding

The CLI and workflow require this exact phrase, which binds the approval to the one candidate and discovery-only scope:

`INSTALL PYTHON-MCP-SERVER-GENERATOR IN DISPOSABLE CODEX USER HOME FOR DISCOVERY ONLY GASL-SRC-4231997AC2C731CE1FE3 2AF91072828C`

The phrase is not a reusable installation token. The workflow has no other Skill ID, Host, scope, or action input. Approval would authorize only one temporary user-scope discovery/rollback run. It would not authorize a model turn, running any Skill command, installing Python dependencies, starting MCP Inspector, launching a generated server, or installing into a real user profile.

## 5. Tests

- **8 dedicated tests and 3 subtests pass** with a synthetic fake Codex process.
- Positive test verifies exact pinned Skill discovery and rollback in a disposable HOME.
- Negative tests cover Git Blob mismatch, frontmatter name mismatch, same-name preexisting Skill, no discovery, disabled Skill, wrong path, malformed protocol, and missing/symlinked Codex CLI.
- Fake Host tests assert that no API credentials are present in the environment.
- Full suite: **445 tests and 226 subtests passed**.
- Python compilation, workflow YAML parsing and `git diff --check` passed.
- The real Codex workflow has **not** been dispatched. Its result must not be described as PASS until a user explicitly approves and the manual run completes successfully.

## 6. Current state

- The Python Skill remains downloaded, MIT-licensed, pinned, integrity-verified and statically scanned with zero findings.
- Its full private ZIP is prepared and verified locally (SHA-256 `8870d46717fe6a44589020556432f3c79c10cbb07364c4de48d0fe21c1f05367`).
- `actual_install_enabled=false`; no third-party Skill is installed or executed.
- The local Mac has `uv 0.9.15`, Python 3.13.9 and Node 24.13.0, but no Codex CLI on PATH. The manual workflow will install the exact CLI in the ephemeral runner only.

**Phase 36 status:** harness and fake-Host tests PASS; real third-party Skill discovery remains pending explicit user approval and a manual GitHub Actions dispatch.
