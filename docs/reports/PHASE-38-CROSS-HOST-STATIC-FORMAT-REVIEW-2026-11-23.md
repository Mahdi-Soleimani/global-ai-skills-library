# Phase 38 — Cross-Host static Skill format review from an exact pinned private ZIP

**Date:** 2026-11-23  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Starting commit:** `5e139b5f09d5daf6d6b9e53a2ff8a126c0063a89` (`main`)  
**Scope:** Read-only ZIP/format inspection and Host mapping; no Skill activation or account access.

## 1. Why this phase and why it does not claim live Cursor/Claude Code discovery

Phase 37 validated an exact third-party `SKILL.md` appearing and disappearing through a **real Codex** App Server in isolated HOME directories on macOS and Linux. It did not prove that Cursor or Claude Code discover the same Skill.

Official vendor documents still do not expose a confirmed, credential-free `skills/list` API analogous to Codex:
- Cursor ACP documents `initialize → authenticate → session/new → session/prompt`; `initialize` alone is **not** Skill discovery: https://cursor.com/docs/cli/acp
- Claude Code documents file-based project/user Skill discovery and interactive `/skills`, but no equivalent standalone, credential-free Skill-list JSON command: https://code.claude.com/docs/en/skills and https://code.claude.com/docs/en/cli-reference

No account authorization, model/API call, or new Host binary installation was attempted. The development Mac had Codex on PATH; `agent`, `cursor`, and `claude` were not present on PATH. Phase 24's real Cursor ACP initialization and Claude CLI version checks remain **readiness**, not live discovery evidence.

## 2. Implemented operation

`tools/host_format_review.py` adds an explicit **offline cross-Host metadata check** on a previously prepared private ZIP. A new CLI command exposes it:

```bash
./gasl host-format-review --plan-id YOUR_EXACT_PLAN_ID --host codex --scope user
./gasl host-format-review --plan-id YOUR_EXACT_PLAN_ID --host cursor --scope user
./gasl host-format-review --plan-id YOUR_EXACT_PLAN_ID --host claude-code --scope project
```

The command:
1. Re-verifies the exact private ZIP hash and all per-file SHA-256 entries, using the existing trusted ZIP reader.
2. Reconstructs the pinned install-plan identity against the current Source Catalog and downloaded local package; rejects stale/tampered package state or actionable static-scan findings.
3. Extracts **only `SKILL.md` bytes into memory** from the verified ZIP, with a 256 KiB size bound; there is no filesystem extraction, no model interpretation and no script execution.
4. Verifies the `SKILL.md` Git Blob against the pinned source identity, checks a deliberately narrow simple YAML-frontmatter subset, a portable Skill name and description, and the name/bundle-folder match.
5. Displays the documented Skill directory for the selected Host and scope without resolving, reading, creating or modifying any actual Agent destination.
6. Emits a warning when the upstream `compatibility` field contains runtime requirements rather than an actual tested Host declaration.

The `simple_frontmatter_shape_detected` result means the **minimal inspected metadata shape** is recognizable, **not** that all YAML, Host features, behavioral compatibility, runtime dependencies, model invocation or Skill execution are verified. Nested/complex YAML, malformed names, missing metadata or conflicting keys are marked for manual review rather than asserted compatible.

The output always keeps `host_discovery_verified_by_this_check=false`, `cross_host_compatibility_proven=false`, `installation_allowed=false`, `third_party_skill_executed=false` and `real_host_files_modified=false`.

## 3. Real local package evidence

Source: `github/awesome-copilot` at pinned commit `f10fdb8b2660ce85c98f220b2f1ca24653768a5c`; Skill `python-mcp-server-generator`, ID `GASL-SRC-4231997ac2c731ce1fe3`.

- Verified private Plan ID: `ce160707029a12b300269ceafcd4f8c9414db3436819724090fe7ae6ee36e343`.
- Verified ZIP SHA-256: `8870d46717fe6a44589020556432f3c79c10cbb07364c4de48d0fe21c1f05367`.
- Pinned `SKILL.md` Git Blob: `2af91072828c27eec9f758262be17745982f7a3e`.
- Minimal `name` and `description` metadata shape detected in all three review modes.
- Static documented destinations: Codex `.agents/skills`, Cursor `.cursor/skills`, Claude Code `.claude/skills` (with explicit user/project scope; these are **relative conventions**, never live paths).
- Upstream `compatibility` describes `uv`, Python and Node requirements. It does not state verified Agent Host support.
- No new third-party ZIP was downloaded, mirrored, installed or published.
- Only prior Phase 37 has actual Codex Host discovery evidence. Cursor and Claude Code discovery **remain unverified**.

## 4. Changed files

- `tools/host_format_review.py` — bounded source-pinned, non-executing ZIP review.
- `tools/gasl.py` — `host-format-review` command.
- `tests/test_host_format_review.py` — synthetic-package regression tests.
- `.github/workflows/gasl-private-install-bundle.yml` — run new tests and compilation on Linux, in addition to existing ZIP tests, without third-party content in the checkout.
- `README.md`, `docs/ROADMAP.md`, this report — capability, evidence and explicit limitations.

## 5. Local tests and acceptance

- `python3 -m unittest tests.test_host_format_review tests.test_install_bundle -q`: **33 tests PASS** (11 new).
- `python3 -m pytest -q --ignore=tests/test_mcp_server.py`: **450 tests + 232 subtests PASS**.
- `python3 -m compileall -q tools tests`: PASS.
- `git diff --check`: PASS.
- CLI smoke on the real ZIP: `codex`, `cursor`, `claude-code` all produce `read_only_format_review_completed` with `simple_frontmatter_shape_detected` and false installation/discovery claims.

**Environment limitation:** System Python 3.13.9 lacks the optional `mcp` dependency, so the existing MCP integration test module was excluded from the local broad run. This is not a new test regression. The independent GitHub Actions source-refresh run installed test dependencies and subsequently passed its full **456-test** regression suite.

## 6. GitHub CI and remaining work

The existing private ZIP safety workflow now includes this phase's module and synthetic regression suite in its triggers and test command. Its live Ubuntu run and the independent full-suite source-refresh workflow both completed successfully; exact Run IDs, outcomes and scope are recorded in Section 7 below.

**Acceptance:** source-pinned, no-execution format review is implemented and locally validated. Real Cursor/Claude Code Skill discovery and installation into live profiles are **NOT** implemented, performed or approved. The next step requires an officially supported, verifiable Host discovery route and appropriate account consent if necessary. Production selective installation remains a distinct permission/transaction gate.

## 7. Live publication and observed CI acceptance

- Source publication: commit [`08f883a`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/08f883a4dff95df30f87865c8bb62e9b727b57a4), normal non-forced push to `main` after a seven-file public-only diff and staged sensitive-pattern check (0 matches).
- [Private Skill ZIP preparation safety — run `45170331891`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45170331891): **completed / SUCCESS** on `08f883a`; actual Linux log confirms **33 passing synthetic unittest cases** and `PRIVATE_BUNDLE_TESTS=PASS; THIRD_PARTY_CONTENT_EXPORTED=FALSE`.
- [Real Codex inert Skill install/discover/rollback — run `45170331901`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45170331901): **completed / SUCCESS** on the same commit. This tests GASL-authored inert content, not third-party execution or Cursor/Claude Code discovery.
- [Daily source catalog refresh — run `45170331957`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45170331957): **completed / SUCCESS** on `08f883a`. All refresh steps passed, including **456 full pytest tests**, discovery of 57 repositories, public source-catalog refresh, search/route smoke tests, and metadata-only publication. Automatic metadata commit [`19171fe`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/19171fe) was fetched and safely fast-forwarded onto local `main` without overwriting the uncommitted report update or rewriting Git history.

No new third-party package text, private ZIP, account data, device-specific path or credential was pushed.
