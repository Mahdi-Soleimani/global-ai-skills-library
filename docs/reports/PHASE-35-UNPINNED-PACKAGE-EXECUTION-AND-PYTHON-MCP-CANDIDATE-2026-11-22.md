# Phase 35 — Detect unpinned package runners and review a Python MCP generator

**Date:** 2026-11-22  
**Branch:** `main`  
**Purpose:** Extend the offline scanner to inspect executable package-runner instructions embedded in Markdown, then select a better-fit Python MCP server Skill candidate without installing or executing it.

## 1. New scanner coverage

The previous scanner reviewed most rules only in source-code files. A Skill can also instruct an Agent to download and execute a package manager command from its Markdown. That was an important blind spot: the TypeScript MCP generator contained `npx ...@latest` and unversioned `npx` commands, but the earlier static audit reported zero findings.

Added `UNPINNED_REMOTE_PACKAGE_EXECUTION` to `tools/static_scan.py`:

- Detects `npx`, `pnpm dlx`, `bunx`, `yarn dlx`, `npm exec`, and `npm create` when the package specification is not pinned to an exact SemVer version.
- Scans both Markdown instructions and supported code files.
- Accepts exact versions such as `package@1.2.3` (including explicit prerelease/build suffixes); local paths are not treated as remote package execution.
- Emits a medium-severity, medium-confidence manual-review signal. This is a supply-chain/reproducibility warning, not a claim that the command or package is malicious.
- The scanner still does not execute the command, download the package, install dependencies, or invoke the Skill.

Regression coverage includes scoped `npx` with `@latest`, bare `npx`, `pnpm dlx` with a version range, `npm create @latest`, `bunx`, exact-version positive controls, local-path exclusions, Markdown and TypeScript contexts, and private ZIP rejection.

## 2. Re-review of the TypeScript candidate

**Candidate:** `typescript-mcp-server-generator`  
**Source record:** `GASL-SRC-596271e7f01053809699`  
**Repository/commit:** `github/awesome-copilot@f10fdb8b2660ce85c98f220b2f1ca24653768a5c`  
**Pinned `SKILL.md` Git Blob:** `d7a98d272b5084874aff21a50f23c46139c5fe85`  
**License:** MIT; the upstream repository `LICENSE` was included and its Git Blob `89bc5e962c9944cdb050887062afdaaf89be504a` verified.

The downloaded package contains only `SKILL.md` and the MIT license: **2 files / 7,790 bytes**. No scripts, binaries, package manifests, or runtime dependencies are bundled.

The new scan finds three unpinned remote package-runner instructions:

| Location | Command | Review |
|---|---|---|
| `SKILL.md:94` | `npx @modelcontextprotocol/codemod@latest` | Explicit mutable `latest` tag; used only in the optional v1 migration section |
| `SKILL.md:100` | `npx tsx` | No exact version; may resolve a local dev dependency, but that cannot be established from this package alone |
| `SKILL.md:101` | `npx @modelcontextprotocol/inspector` | No exact version; may download the registry's current package if not already available locally |

These are legitimate-looking development/migration commands, not evidence of malware. They still require manual review before the Skill is used. The exact pinned source remains intact; GASL does not edit third-party content to remove these commands.

**New status:** `manual_review_required`, integrity PASS, pinned main Blob PASS, 3 actionable findings. `install-plan` now sets `simulation_apply_eligible=false`, keeps `actual_install_enabled=false`, and includes `static_security_review_required`.

A private ZIP had briefly been created before the new rule existed. Its integrity had been verified, but it was never installed or executed. After the re-audit, that candidate's ZIP and sidecar were deleted so an artifact created under the old scanner cannot be mistaken for an approved package. The source remains in the ignored local catalog for review.

## 3. Better-fit Python candidate selected

**Candidate:** `python-mcp-server-generator`  
**Source record:** `GASL-SRC-4231997ac2c731ce1fe3`  
**Repository/commit:** `github/awesome-copilot@f10fdb8b2660ce85c98f220b2f1ca24653768a5c`  
**Pinned `SKILL.md` Git Blob:** `2af91072828c27eec9f758262be17745982f7a3e`  
**License:** MIT; upstream `LICENSE` Blob `89bc5e962c9944cdb050887062afdaaf89be504a` verified.

The complete local package contains **3 files / 9,908 bytes**:

1. `SKILL.md` — Python MCP server generator instructions.
2. `references/streamable-http.md` — HTTP transport, loopback binding, Host/Origin validation, CORS and multi-worker guidance.
3. Original MIT license notice.

All three files are hash-verified and the exact main `SKILL.md` Git Blob matches the pinned source. The static scanner reports **zero findings**. No script or binary is bundled.

### Manual technical review

The Skill uses the official MCP Python SDK v2 and the `MCPServer` API, type-hinted `@mcp.tool()` handlers, in-memory `Client(mcp)` tests, `ToolError`, and the current Streamable HTTP transport. Its stdio instructions correctly keep stdout reserved for the JSON-RPC protocol and direct logs to stderr. The HTTP reference defaults to `127.0.0.1` and requires explicit `TransportSecuritySettings` for non-loopback/public binding; it does not recommend wildcard origins as a default.

Official documentation cross-check:

- The official Python SDK documents v2 as the stable line, renames `FastMCP` to `MCPServer`, and describes `Resolve` for user input: [Python SDK — What's new in v2](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/whats-new.md).
- The official PyPI project page confirms Python 3.10+, the `mcp[cli]` extra, `MCPServer`, and `uv run mcp dev server.py`: [MCP Python SDK on PyPI](https://pypi.org/project/mcp/).
- The official migration guide lists the v2 breaking changes, including constructor/transport changes and renamed fields: [Python SDK migration guide](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/migration.md).

The candidate's `uv add "mcp[cli]>=2,<3"` uses a compatible major-version range. A generated `uv.lock` should be retained and committed in any real project to lock the actual resolved dependency versions. No package installation was run as part of this review.

### Local prerequisite check

- `uv 0.9.15` — present.
- `Python 3.13.9` — satisfies the declared Python 3.10+ minimum.
- `Node.js 24.13.0` — present; the Skill needs Node only for the optional MCP Inspector.

Upstream does not explicitly declare Codex compatibility. GASL's Codex Host adapter and user-scope discovery were previously verified using inert GASL-authored fixtures only; that does not prove this third-party Skill has been installed in Codex.

## 4. Private review bundle

A deterministic private review ZIP was prepared and read back:

| Item | Value |
|---|---|
| Plan ID | `ce160707029a12b300269ceafcd4f8c9414db3436819724090fe7ae6ee36e343` |
| Archive SHA-256 | `8870d46717fe6a44589020556432f3c79c10cbb07364c4de48d0fe21c1f05367` |
| Entries | 3 |
| Integrity | PASS |
| License review required | No |
| Host installation approved | No |
| Third-party Skill executed | No |

The ZIP and metadata sidecar remain under ignored `private/install-bundles/`. They are not tracked or uploaded to GitHub. `verify_private_bundle` confirms only archive integrity; it does not grant installation approval.

## 5. Codex install plan and current state

The read-only plan targets Codex **user scope** (`~/.agents/skills/`) but resolves no real filesystem target. It reports:

- `simulation_apply_eligible=true` because the package is pinned, integrity-verified, and has zero actionable static findings.
- `actual_install_enabled=false`, `installation_allowed=false`, `installed=false`, `executed=false`.
- `destination_modified=false`.
- Warnings remain for dynamic execution not approved, upstream Host compatibility not declared/tested, no user approval, and real-user installation disabled.

**No Skill was installed, enabled, invoked, or executed.** No real `~/.agents/skills`, `~/.codex`, or other user profile was read or changed. No model turn was started and no package dependencies were installed.

## 6. Tests and acceptance evidence

- **437 pytest tests and 223 subtests passed** locally.
- The targeted scanner, bundle-gate and install-plan suite passed before the full run.
- `python3 -m compileall -q tools tests` passed.
- `git diff --check` passed.
- New regression tests prove that unpinned package-runner instructions are detected and that a package containing them cannot produce a new private review ZIP.
- A clean security scan is still only static evidence, never automatic installation/execution approval.

## 7. Next operation — requires explicit user approval

The next proposed test is limited to one temporary Codex HOME:

1. Create a disposable `HOME` and `CODEX_HOME`.
2. Copy this exact verified ZIP into the temporary `HOME/.agents/skills/python-mcp-server-generator/` directory.
3. Ask the real Codex App Server only for `initialize` and `skills/list` and verify the exact skill name/path is discovered and enabled.
4. Remove only the files created from this ZIP, query `skills/list` again, and verify the Skill is absent.
5. Delete the temporary HOME and confirm no real profile or project files changed.

This is a temporary installation of third-party **instructions**, even though no model turn or Skill command is run. It must not start until the user explicitly approves this exact Skill, ZIP hash, Codex user scope, and discovery-only/rollback operation. It must never invoke the Skill, execute `uv`, install its dependencies, open MCP Inspector, or start a generated server.

**Phase 35 status:** scanner enhancement and candidate review PASS; Python MCP candidate prepared privately; isolated third-party Codex discovery remains approval-pending.
