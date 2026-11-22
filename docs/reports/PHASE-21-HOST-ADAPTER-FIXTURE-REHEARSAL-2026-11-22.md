# Phase 21 — Host Adapter matrix and disposable inert Skill lifecycle rehearsals

**Date:** 2026-11-22  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Branch:** `main`  
**Scope:** Document real Host conventions; test local file operations in **isolated disposable GASL-only fixtures**, never in the user's actual Agents or projects.

## 1. Why this phase follows Phase 20

Phase 20 introduced `install-plan` and a private transactional apply/rollback **state simulation** but deliberately did not resolve Agent directories, back up real data or install untrusted Skill packages. Phase 19's 18/18 **benign Linux sandbox canary checks** likewise did not approve the execution of third-party code. To avoid conflating a generic MCP client or Claude Desktop account uploads with local Agent Skills, Phase 21 confirms different Host integration mechanisms and rehearses **only inert, self-authored fixture files**.

## 2. Official documentation and accurate Host types

| Host | Documented project Skill directory | Documented user Skill directory | Mechanism GASL can rehearse | Status |
|---|---|---|---|---|
| **Codex** | `.agents/skills/` | `~/.agents/skills/` | Local Skill folder with `SKILL.md` | Documented; not tested in a running Codex Host |
| **Cursor** | `.cursor/skills/` | `~/.cursor/skills/` | Local Skill folder with `SKILL.md` | Documented; not tested in a running Cursor Host |
| **Claude Code** | `.claude/skills/` | `~/.claude/skills/` | Local Skill folder with `SKILL.md` | Documented; not tested in running Claude Code |
| **Claude Desktop / Claude Chat** | **None** for automatic local filesystem installation | **None** for automatic local filesystem installation | Upload a Skill ZIP in **Customize > Skills** through the user's Claude account | Manual account UX only; no local installer or automatic upload provided |
| **Generic MCP host** | No universal standard | No universal standard | Discovery tools only; must integrate host-by-host | No filesystem adapter invented |

**Source references (vendor docs, inspected 2026-11-22):**

- Codex project/user path convention: <https://developers.openai.com/api/reference/cli> (installation table).
- Cursor Skill loading and scope: <https://cursor.com/help/customization/skills>.
- Claude Code Skills: <https://code.claude.com/docs/en/skills>.
- Claude Desktop/Chat upload: <https://support.claude.com/en/articles/12512180-use-skills-in-claude>.

These URLs describe published support, **not proof that a compatible Host binary is installed or loaded on the user's Mac**. Cursor also recognizes alternate `.agents/skills` and Claude directories, but the preferred explicit Cursor-owned path in this adapter is `.cursor/skills` to avoid duplicate discovery and ownership ambiguity. These are *layout conventions* only: no Agent files were inspected or modified on the development computer.

## 3. Implementation (no change to real installation gates)

- Added `tools/host_adapters.py`: read-only layout metadata for five Host labels, safe slug validation, and a **fixture-only** `rehearse_host_fixture(agent, scope, scenario)` entrypoint.
- Added `./gasl host-adapters`: a fully read-only JSON matrix; its top-level output includes `real_installation_available=false`, `real_host_probe_performed=false` and `third_party_skill_executed=false`.
- Added `./gasl host-rehearsal --agent ... --scope project|user --scenario fresh|upgrade|conflict|symlink`.
- Updated `tools/install_lifecycle.py` so `install-plan` now includes `host_adapter.kind`, `documented_relative_skill_directory`, official documentation URL, `verified_with_real_host=false`, `actual_install_enabled=false`. New `claude-code` preview label is distinct from `claude-desktop`. Existing `plan_id` derivation remains unchanged for existing Agents; still no actual target path resolution.
- Added `tests/test_host_adapters.py` and two additional Phase-20 integration regressions to verify that no plan can imply a real installation.

### Fixture-only write/recovery lifecycle

1. The CLI's rehearsal function creates its own OS `TemporaryDirectory(prefix="gasl-host-fixture-")` with a unique marker. No user-provided writable root is accepted, and the internal writer refuses paths outside the fixture or through a Symlink.
2. It uses a constant **self-authored, non-executable, inert `SKILL.md`**, never any downloaded Skill, archive, reference, script or credentials.
3. For `fresh`: write an inert fixture, verify its content SHA-256, and remove it again, returning to a fully empty Skill target.
4. For `upgrade`: create a prior inert version and a separate **user-edit sentinel**, perform a same-filesystem rename to an internal backup, write the new inert version, verify hash, then atomically restore the original backed-up directory and user-edit sentinel.
5. For `conflict`: preserve the existing fixture Skill, report a conflict, and refuse to overwrite without the separate planned backup workflow.
6. For `symlink`: deny an unsafe path and verify an external-to-target **fixture sentinel** remains unchanged.
7. The temporary fixture is deleted at the end, including when an exception occurs. The Host's real project/user directories are not read or modified.

These are **disposable fixture transactions only**, not crash-proof backups on user files, not evidence of permissions to modify Host directories, and not dynamic security checks on third-party Skills. A malicious local process with access to the same temporary directory is out of scope for this self-authored rehearsal.

## 4. Actual local matrix execution

A 5-agent × 2-scope × 4-scenario matrix, **40 separate executions**, was performed locally. A raw JSON summary is retained in ignored `reports/host-adapters/PHASE21-LOCAL-FIXTURE-MATRIX-2026-11-22.json` (not published in Git).

| Result | Count | Interpretation |
|---|---:|---|
| `fixture_rollback_verified` | **12** | 6 fresh and 6 upgrade rehearsals for Codex, Cursor and Claude Code, both scopes |
| `existing_target_requires_explicit_backup` | **6** | All pre-existing inert Skill targets preserved without unsafe overwrite |
| `blocked_symlink_target` | **6** | Symlink attack canaries rejected; fixture sentinels untouched |
| `no_filesystem_adapter` | **16** | Claude Desktop and generic MCP correctly use no guessed filesystem install location |
| **Total** | **40** | All actual results matched expected status; no third-party execution |

CLI smoke checks also verified:

- `./gasl install-plan --id GASL-SRC-ce593c8b9b3fd34f44d6 --agent claude-code --scope project` -> documented `.claude/skills`, `verified_with_real_host=false`, `actual_install_enabled=false`.
- The same plan with `--agent claude-desktop --scope user` -> `manual_account_zip_upload`, `documented_relative_skill_directory=null`, `actual_install_enabled=false`.

## 5. Test and publication acceptance

- `tests/test_host_adapters.py`: **15 test methods**, including project/user layout coverage, fresh/upgrade/conflict/symlink regression, marker validation, traversal protection, incorrect path and slug rejection, and temporary directory cleanup.
- `tests/test_install_lifecycle.py`: +2 test methods; all five Host types remain actual-install-disabled, with Claude Code and Claude Desktop generating different pinned plan IDs.
- Full project suite: **274 tests + 41 subtests passed** locally.
- No additional Python dependencies.
- Only `README.md`, `docs/ROADMAP.md`, this report, new adapter/test files and the two related CLI/preview modules should be staged. All ignored user packages, local simulations and raw Host fixture runs stay off public Git.

## 6. Remaining work (not certified by this phase)

- **Live Host integration checks:** install a target Host under a controlled, disposable test profile and confirm it discovers the inert Skill; this was **not performed** here. Do not touch a real user Host profile without a separate, explicit real-host approval.
- **Production install transaction:** design consent binding to exact destination/version and scope; atomic backup/restore of user files; interruption handling; uninstallation ownership boundaries and conflict resolution.
- **Claude Desktop:** manual ZIP packaging and account upload require a separate UX and policy. No automatic upload assumed, no account login or connection attempted.
- **Trust of unknown content:** dynamic review of real Skill behavior is still absent; nothing in this phase permits running packages, especially the seven with actionable security signals. The Sandbox canary is only a benign isolation self-test.
- **Cross-platform:** fixture tests run on macOS, but Windows and each real Agent Host remain to be exercised separately.

**Phase 21 acceptance: PASS for documentation-grounded layout matrix, 40 inert fixture exercises, 274 regression tests and zero real installs/executions. No production installer is enabled.**
