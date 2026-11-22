# Phase 33 — Review and prepare the first practical MCP-building Skill

**Date:** 2026-11-22  
**Candidate:** `mcp-server-builder`  
**Source:** [`alirezarezvani/claude-skills`](https://github.com/alirezarezvani/claude-skills), pinned commit `5909a72e62b5fbb809935fb6a55b58bdbe175074`, path `engineering/skills/mcp-server-builder/`  
**Proposed target:** Codex user scope inside a separately isolated HOME. The user's normal Codex profile is excluded.

> **Superseded by Phase 34:** This Phase-33 report preserves the original historical review, including the initial scanner's zero findings. A later manual review discovered unsafe interpolation of OpenAPI descriptions into generated Python and TypeScript source. The upgraded scanner now reports **two high-severity signals** for this exact pinned package, and a fresh `install-plan` blocks new bundle preparation. The previously created private ZIP remains unapproved and must not be installed or executed. See [Phase 34](PHASE-34-STATIC-CODEGEN-CORS-NETWORK-BIND-2026-11-22.md).

## 1. Why this candidate was selected

The Phase-32 `academy-guide` candidate is safe-looking but narrowly focused on recommending Claude Academy learning content. For a first practical integration test, `mcp-server-builder` is a better functional match: it scaffolds MCP servers from OpenAPI contracts and validates the resulting tool manifest. It directly supports Python and TypeScript, which makes it a more useful first test for GASL's MCP-building workflow.

Two other `mcp-builder` results were inspected as alternatives:

- `microsoft/skills` (`mcp-builder`, MIT) includes an evaluation harness that creates Anthropic API requests and connects to user-specified MCP servers. Its optional evaluation script can invoke tools, send test questions/tool results to Anthropic, and incur API cost. It was not selected as the first low-side-effect test.
- `anthropics/skills` (`mcp-builder`, Apache-2.0) also includes an Anthropic-powered evaluation harness and MCP connection code. It was not selected for the first test for the same reason.

The selected `mcp-server-builder` package contains only two local utility scripts; neither has a network client or subprocess runner.

## 2. Exact source, license and bundle evidence

| Item | Evidence |
|---|---|
| GASL Source Record | `GASL-SRC-588962e88c75e1440e8c` |
| Private Plan ID | `1afa4cb9503d718f164a794de7fe35e97d776b31fc57744af837c14dbf468a80` |
| Upstream commit | `5909a72e62b5fbb809935fb6a55b58bdbe175074` |
| `SKILL.md` Git blob | `cbab6c96f3212c6e41fdac1865d4d890f16244f9` |
| `LICENSE` Git blob | `c3e30bcc287d6a1ebdb4ab29c10d344fd1053639` |
| License | MIT |
| Copyright | Copyright (c) 2025 Alireza Rezvani |
| Private ZIP SHA-256 | `98da88cfbe90af907f4d64badfef8210d5dcf4bf0bca4647cf84377b7e8df7cb` |
| ZIP entries | 10 files; 27,454 uncompressed bytes |

All 10 downloaded package files match their recorded upstream Git blob IDs. The full upstream MIT license is included in the package under `__upstream_licenses__/`. The private ZIP was created using the exact acknowledged plan and read back successfully. It is under ignored `private/install-bundles/`; it was not added to Git or uploaded to CI.

Upstream references: [SKILL.md at pinned commit](https://github.com/alirezarezvani/claude-skills/blob/5909a72e62b5fbb809935fb6a55b58bdbe175074/engineering/skills/mcp-server-builder/SKILL.md), [LICENSE at pinned commit](https://github.com/alirezarezvani/claude-skills/blob/5909a72e62b5fbb809935fb6a55b58bdbe175074/LICENSE).

## 3. Security and behavior review

GASL's offline audit reports:

- `integrity_ok=true`, `pinned_skill_blob_ok=true`;
- `security_status=no_obvious_static_flags_not_approved`;
- **0 findings, 0 actionable findings, 0 high-confidence signals**;
- Python AST parsing passed for both scripts; neither script was executed.

### `scripts/openapi_to_mcp.py`

- Reads a caller-supplied OpenAPI JSON or YAML file, or stdin.
- YAML uses `yaml.safe_load` if PyYAML is installed; no dynamic YAML object construction.
- Generates `tool_manifest.json` and a Python or TypeScript server scaffold under the explicit `--output-dir` (default `.`; the Skill's example uses `./out`).
- No HTTP/network client, subprocess execution, shell invocation, environment/credential access, `eval`, `exec` or pickle use was found.
- File writes are confined to the caller-selected output directory; review that path before invoking the generator.

### `scripts/mcp_validator.py`

- Reads a local JSON tool manifest or stdin and checks naming, schema structure, required properties and descriptions.
- Uses Python standard-library modules only.
- No network, subprocess, credential access, dynamic execution or file writes found.

### Package-level notes

- No `requirements.txt`, `package.json`, executable binary or external runtime dependency is bundled.
- The Skill does not itself call an MCP server or make an API request. It recommends local generation and validation commands.
- The scripts are executable code, so installing the package does not authorize running them. During the initial Host compatibility test, **neither script will be executed**; the only operation will be Codex `initialize` and `skills/list`.
- Upstream does not declare Codex compatibility. Phase-31 verified Codex's user-scope path with a GASL-authored inert fixture, not this third-party Skill.

## 4. Host adapter metadata correction

After Phase 31, the install-plan output still said `host_adapter_not_implemented` for Codex. That was stale: real Codex App Server had already verified project/user discovery and fixture rollback. `HOST_LAYOUTS['codex']` now records the verified capabilities and links to the Phase-31 evidence, while explicitly retaining `actual_install_enabled=false` and `verification_scope=disposable_home_only`. Other Hosts remain unverified. The plan now distinguishes `host_discovery_verified_in_disposable_profile_only` from `real_user_profile_installation_not_enabled` instead of claiming the Codex adapter is wholly unimplemented.

## 5. Public CI verification of the adapter metadata correction

After the Codex adapter evidence fields and install-plan warnings were reconciled, the public workflows on commit `1189202` completed successfully:

- [Real Codex App Server lifecycle — run `45074583955`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45074583955): **SUCCESS**.
- [Private ZIP Host fixture transaction — run `45074583859`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45074583859): **SUCCESS**.
- [Private Skill ZIP preparation safety — run `45074583807`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45074583807): **SUCCESS**.
- [Inert Host transaction recovery — run `45074583777`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45074583777): **SUCCESS**.

The real Codex run again covers both project and user-scope fixture discovery. It uses GASL-authored inert content, not the third-party candidate. The clean public `git archive` checkout passed **422 tests and 223 subtests**; private `catalog`, `reports`, `storage` and `private` data were absent.

## 6. Current state and exact next action

<status>HISTORICAL PHASE-33 STATE — SUPERSEDED: SECURITY REVIEW REQUIRED, INSTALL BLOCKED</status>

- The package is downloaded, pinned, statically reviewed, MIT license included, and packaged into a verified private ZIP.
- No Skill was installed, invoked, or executed. No Codex profile was modified.
- The only remaining authorization is the user's explicit approval for this exact third-party Skill and destination.

If approved, the next operation is limited to a separate temporary Codex HOME at user scope, with the exact ZIP and one-time receipt. Run only `initialize` and `skills/list` to confirm Codex sees `mcp-server-builder` at the expected path. Do not run `openapi_to_mcp.py`, `mcp_validator.py`, a generated MCP server, or any model turn. Then roll back and verify the isolated profile is empty again. The user's existing `~/.agents/skills` and `~/.codex` must remain untouched.

**This report is a technical review, not legal advice or a security guarantee. A clean static scan is not an installation or execution approval.**
