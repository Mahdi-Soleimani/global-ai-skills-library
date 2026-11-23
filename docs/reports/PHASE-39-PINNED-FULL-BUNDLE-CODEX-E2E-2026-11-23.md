# Phase 39 — Full pinned Skill ZIP transaction, real Codex discovery and rollback

**Date:** 2026-11-23  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Starting main:** `87fd5f6b00c352bbdd190da2c7b18ae99f51f233`  
**Outcome:** Real macOS Codex E2E succeeded with a pinned, reviewed three-file third-party ZIP; synthetic two-file E2E and negative tests also passed. Linux CI evidence is recorded in the subsequent section once the actual workflow completes.

## Objective and gap addressed

Phase 37 confirmed a selected third-party `SKILL.md` appeared in real Codex and disappeared after removal. Phase 38 added offline, source-pinned cross-Host format review. Separately, previous phases had implemented exact ZIP inventory, a read-only target preflight, state-bound fixture consent, locked staging, atomic activation and checked rollback. **These operations had not been observed together on one real third-party full ZIP by the real Codex App Server.**

Phase 39 connects those existing mechanisms without enabling a production user-profile installer.

## Implemented flow

New `tools/codex_pinned_bundle_e2e.py` and CLI `codex-pinned-bundle-e2e`:

1. Require an **absolute regular (nonsymlink) Codex executable**, exact 64-hex Plan ID and the explicit fixture-only acknowledgement `GASL_DISPOSABLE_CODEX_BUNDLE_ONLY`.
2. Run Phase 38's `review_host_format`: verify private ZIP archive and entries, pinned Source Catalog/commit/blob, current downloaded package integrity and current static-scan status. Reject incompatible/complex metadata.
3. Read the full ZIP with the existing `fixture_bundle_install._read_bundle`, demanding exact **Codex / user** bundle binding and matching pinned `SKILL.md` name. No extraction to user-selected destinations.
4. Create a **new, marked, disposable fixture** with separate `HOME`, `CODEX_HOME`, workspace/cache/tmp roots; the actual user profile is never a target.
5. Check target is absent via `inspect_selected_target`, hold the prior `state_binding_id` and revalidate it with `verify_target_unchanged`.
6. Ask real Codex App Server **only** `initialize` + `skills/list`; target Skill must be absent.
7. Compute fixture-only state-bound challenge and invoke `enact_fixture_transaction`; use the existing exclusive lock, recheck state before activation, stage **every pinned ZIP entry**, verify SHA-256 inventory, atomically activate the temporary directory.
8. Ask the real Codex App Server `skills/list` again; require **exactly one enabled Skill at the expected temporary path**.
9. Run the preexisting locked `recover_fixture_transaction`; verify original absent state restored, then query real Codex a final time to confirm no Skill remains.
10. Delete the entire temporary profile. On failed/malformed Host observations, attempt locked fixture recovery before cleanup and never mark success.
11. Emit a bounded JSON result containing booleans/IDs, not local real-user paths or Skill source text.

**Important boundary:** Even the verified full third-party ZIP is merely *placed* under an isolated temporary skill directory while Codex lists its metadata. No model turn, Skill instruction, code generator, package install, MCP server, authentication, actual project/user Agent directory or runtime dependency is executed or modified. The explicit acknowledgement is fixture-only, **not** actual human authorization to install in a real profile. `production_installation_enabled=false` remains mandatory.

## Selected real third-party source

| Field | Value |
|---|---|
| Skill | `python-mcp-server-generator` |
| Source | `github/awesome-copilot` |
| Source ID | `GASL-SRC-4231997ac2c731ce1fe3` |
| Pinned commit | `f10fdb8b2660ce85c98f220b2f1ca24653768a5c` |
| `SKILL.md` Git Blob | `2af91072828c27eec9f758262be17745982f7a3e` |
| Exact private ZIP Plan ID | `ce160707029a12b300269ceafcd4f8c9414db3436819724090fe7ae6ee36e343` |
| Private ZIP SHA-256 | `8870d46717fe6a44589020556432f3c79c10cbb07364c4de48d0fe21c1f05367` |
| Actual ZIP files in transaction | **3** |

Real macOS Codex CLI version: `0.167.0`. The exact executable resolved to a regular file before use. User-scope Host paths existed only under the marked disposable fixture.

Observed result: `real_codex_pinned_full_bundle_discovery_and_rollback_verified`; all `pinned_package_and_format_checked`, `target_preflight_state_bound`, `absent_before_install`, `full_pinned_zip_temporarily_staged_and_activated`, `exact_skill_discovered_and_enabled`, `fixture_rollback_verified`, `absent_after_rollback`, and `temporary_profile_deleted` were **true**. All real-user installation / authentication / model turn / third-party execution flags were **false**.

## CLI usage (disposable test only)

```bash
./gasl codex-pinned-bundle-e2e \
  --codex-bin /ABSOLUTE/REAL/PATH/TO/CODEX/CLI \
  --plan-id EXACT_ALREADY_REVIEWED_PLAN_ID \
  --acknowledge-fixture-only GASL_DISPOSABLE_CODEX_BUNDLE_ONLY
```

The command never accepts a destination root or `--install` flag and never acts as a production installer.

## Changes

- `tools/codex_pinned_bundle_e2e.py`: source-pinned full bundle + read-only preflight + locked fixture transaction + real Host verification + rollback.
- `tools/gasl.py`: expose the guarded fixture-only command.
- `tests/test_codex_pinned_bundle_e2e.py`: nine synthetic tests for success, absence/disabled/wrong-path/stale Host, malformed protocol, wrong acknowledgement, missing/symlinked Codex, tampered ZIP, changed source and wrong Host binding.
- `.github/workflows/gasl-codex-transaction-e2e.yml`: run regression tests and test the **same complete pipeline with real Codex** against a self-authored, synthetic ZIP in disposable Ubuntu CI. No third-party ZIP or real profile is provided to the runner.
- `README.md`, `docs/ROADMAP.md`, this report: updated status, controls, scope and limitations.

## Local acceptance

- Actual macOS real third-party three-file ZIP end-to-end: **PASS**.
- Actual macOS real Codex against self-authored synthetic two-file bundle: **PASS**.
- `python3 -m unittest tests.test_codex_pinned_bundle_e2e tests.test_codex_transaction_e2e -q`: **22 tests PASS**.
- Broad local `python3 -m pytest -q --ignore=tests/test_mcp_server.py`: **459 passed, 236 subtests passed**, with no failures.
- `python3 -m compileall -q tools tests` and `git diff --check`: **PASS**.
- The local global Python lacks the optional `mcp` module; full dependency-equipped suite is checked by the separately triggered source-refresh CI.

## Limitations and next step

This phase proves an isolated Codex *metadata discovery lifecycle* for an exact full ZIP, **not** Skill behavioral correctness or arbitrary-code safety. Cursor/Claude Code real Skill discovery, real-user installation, permanent activation, automatic upgrade, untrusted code execution and production consent are still **not enabled**. A user-profile installer would require a separate explicit opt-in action, fresh target-role confirmation, conflict/backups, versioned immutable receipts, security policy and failure recovery guarantees. Do not infer authorization from a test-only acknowledgement.

## Verified GitHub Actions evidence (actual completed runs)

- Published code on `main` in commit [`bb66032`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/bb6603284556fdb7324af5b8ad251ce52570861d) with an ordinary non-force push, after a seven-file staged source check, whitespace validation and no sensitive-pattern matches.
- [Real Codex inert Skill lifecycle — run `45172898331`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45172898331): **completed / SUCCESS**. The exact new full-ZIP test step logged `PINNED_FULL_ZIP_CODEX_REAL_HOST_CI=PASS; THIRD_PARTY_EXECUTED=FALSE`, confirming a two-file GASL-authored ZIP with **real Codex CLI 0.162.1** in an isolated Ubuntu profile. The independent existing Codex install/discover/rollback and user-scope tests also passed. All nine new synthetic Host tests passed.
- [Private Skill ZIP safety — run `45172898397`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45172898397): **completed / SUCCESS**; bundle regressions continue to pass without publishing or executing downloaded Skill files.
- [Daily source-catalog refresh — run `45172898207`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45172898207): **completed / SUCCESS**, including **465 passing full pytest tests**, refresh of **57 repositories**, **4,431 attributed source records**, and a metadata-only commit to `main`.
- Automated metadata commit [`b5beba0`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/b5beba0) was fetched and fast-forwarded locally without a force push; the project remained clean and in sync.

**Final scope:** Full-pinned-ZIP Codex discovery and rollback is verified in disposable macOS and Linux environments, with no model invocation, third-party code execution or real-user installation. Production installation is still disabled.
