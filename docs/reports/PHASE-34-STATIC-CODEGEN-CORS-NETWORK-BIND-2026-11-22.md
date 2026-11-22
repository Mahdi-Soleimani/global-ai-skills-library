# Phase 34 — Static scanning: unescaped code generation, wildcard CORS, and network binding

**Date:** 2026-11-22  
**Branch:** `main`  
**Purpose:** Correct an evidence gap identified in the Phase-33 manual review: a previously clean static scan missed code-generation injection and an exposed HTTP scaffold in two pinned third-party Skill packages.

## 1. Baseline and discovery

In Phase 33, the offline rule-based scanner reported **zero signals** for `mcp-server-builder` even though `scripts/openapi_to_mcp.py` embeds the untrusted OpenAPI `description` into generated Python and TypeScript source-code string literals. In the TypeScript scaffold, lines 203-206 directly interpolate the description into a single-quoted string without an escaping layer. The Python scaffold similarly interpolates the text into a generated docstring at lines 173-176. This creates a **potential source-code injection path when a caller later executes generated output**; exploitation was not attempted or claimed.

Another downloaded candidate, the OpenAI `chatgpt-apps` Skill, contains `scripts/scaffold_node_ext_apps.mjs` which templates a minimal Node HTTP server with `Access-Control-Allow-Origin: *` (lines 437 and 453) and `.listen(port, ...)` without specifying an explicit loopback bind address (line 480). These are production-exposure concerns in a development example, **not evidence of malicious code**.

## 2. Implemented detection changes

`tools/static_scan.py` now includes:

| Rule | Severity | Evidence it detects |
|---|---|---|
| `UNESCAPED_DESCRIPTION_CODE_TEMPLATE` | high / medium confidence | Direct `description` interpolation in a Python formatted-string code template without visible encoding |
| `WILDCARD_CORS_ORIGIN` | medium / high confidence | Literal `Access-Control-Allow-Origin` set to `*` in code or embedded code templates |
| `NODE_SERVER_IMPLICIT_ALL_INTERFACES` | medium / medium confidence | Node `.listen(port)` or `.listen(port, callback)` without a host argument (possible all-interface binding) |

JavaScript `.js`, `.jsx`, `.mjs`, `.cjs` and TypeScript `.ts`, `.tsx` are scanned as code. The Node listen rule applies only to JavaScript/TypeScript files. Findings include file, line, matched evidence and bounded context. All rules are static text heuristics: dynamic values, aliases, other generation paths and obfuscated code can evade them; false positives remain possible. No downloaded code is run by the scanner.

## 3. Real pinned local package results

Fresh `scan_package(source.json, persist=False)` was run without modifying the downloaded manifest:

| Candidate | Pinned repository/commit | Integrity | Old result | New result |
|---|---|---|---|---|
| `mcp-server-builder` | `alirezarezvani/claude-skills@5909a72e62b5fbb809935fb6a55b58bdbe175074` | PASS | 0 signals | **2** `UNESCAPED_DESCRIPTION_CODE_TEMPLATE` at lines **175, 204**; `manual_review_required` |
| `chatgpt-apps` | `openai/skills@49f948faa9258a0c61caceaf225e179651397431` | PASS | 0 signals | **2** `WILDCARD_CORS_ORIGIN` at lines **437, 453**, **1** `NODE_SERVER_IMPLICIT_ALL_INTERFACES` at **480**; `manual_review_required` |
| `microsoft/mcp-builder` | `microsoft/skills@47eb3888eb42aef074fcb617931bf6e5934e45d9` | PASS | 0 signals | 0 rule matches; not approved |
| `academy-guide` | `anthropics/skills@e4bb5d960d87126ff3b3a8af1a104b7db67560ba` | PASS | 0 signals | 0 rule matches; not approved |

All packages remained byte-for-byte unchanged by these scans. The first two contain risk patterns and are held for review; the absence of new findings for the other packages is **not** a security approval.

## 4. Installation preparation gate regression

`install-plan` rechecks the downloaded source at read time. For both flagged packages, `local_package.security_status=manual_review_required`, `simulation_apply_eligible=false`, `actual_install_enabled=false`, and `static_security_review_required` appears in the warnings.

Regression tests also prove `prepare_private_bundle` refuses to create a new private ZIP containing either an unescaped description template or a wildcard CORS/implicit bind combination. The failed attempts leave the private directory uncreated. Conversely, explicitly loopback-bound and specific-origin examples do not trigger these particular warnings.

**Historical ZIP caveat:** The `mcp-server-builder` private ZIP generated in Phase 33 still exists in the ignored local `private/install-bundles/` directory. Its immutable bytes can still pass an integrity-only readback. That result does **not** override the new security review, does **not** authorize installation, and does **not** make it eligible for a new bundle. Do not install or execute the old ZIP. No ZIP or downloaded source content is included in the Git commit.

## 5. Tests and observable outcomes

- **433 pytest tests and 223 subtests passed** locally.
- Scanner-specific tests cover positive code-generation detection, JSON-encoded negative control, two wildcard CORS forms, specific-origin negative control, Node/TypeScript implicit bind positive controls, explicit loopback negative control, TypeScript coverage, scan read-only operation and failure to execute an intentionally inert marker script.
- Private ZIP gate tests cover rejected code-generation templates and rejected wildcard-CORS-plus-implicit-bind packages.
- Python `compileall` and `git diff --check` passed.
- No model turn, third-party script, generated server, actual Agent profile, dynamic Skill execution, authentication or actual installation was touched.
- [GitHub Actions — Private Skill ZIP preparation safety, run `45076369975`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45076369975): **SUCCESS**, including both new end-to-end packaging-block regressions on Linux.
- [GitHub Actions — Daily source catalog refresh, run `45076369944`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45076369944): **SUCCESS**. The full regression suite passed and the metadata-only bot refresh committed `694fd30`; this commit was merged safely with the Phase-34 report update before publishing, with no force-push.

## 6. Modified files and decisions

- `tools/static_scan.py` — three new scanner signals and TypeScript/JSX coverage.
- `tests/test_static_scan.py` — new focused scanner regression suite.
- `tests/test_install_bundle.py` — two end-to-end packaging gate regressions.
- `README.md`, `docs/ROADMAP.md`, `docs/reports/PHASE-33-MCP-SERVER-BUILDER-CANDIDATE-REVIEW-2026-11-22.md` — supersede the prior clean-scan conclusion and record the new hold.
- This report — public, **metadata-only** review evidence (not third-party source code).

**Decision:** Both `mcp-server-builder` and `chatgpt-apps` stay **`manual_review_required`**; do not use either as the first real Codex third-party installation candidate. Continue only with a separately approved candidate after a fresh scan and manual review. A clean static result is insufficient to approve installation or execution.

**Acceptance criteria:** detection on exact real local pinned packages; no mutation during scan; packaging gates reject flagged synthetic fixtures; full tests pass; public-safe Git commit and GitHub workflow verification. Record CI run IDs only after successful completion.
