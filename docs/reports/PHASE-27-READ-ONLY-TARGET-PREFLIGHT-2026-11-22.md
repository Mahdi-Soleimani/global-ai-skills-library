# Phase 27 — Read-only, exact Host target preflight and state-drift detection

**Date:** 2026-11-22  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Scope:** Prepare the destination-selection and state-binding step needed by a future real selective installer, without modifying or automatically inspecting any live user Agent installation.

## 1. Position in the lifecycle

Phase 25 produced an immutable-plan-identified, locally private ZIP with original Skill files, integrity and license warnings. Phase 26 demonstrated actual ZIP filesystem materialization, backup, and verified rollback, **only in disposable GASL-created Host fixtures**. Phase 27 adds a **read-only Host target preflight** for a destination root **explicitly supplied by the caller**. It is not a production installer; it does not create consent or use the temporary fixture's approval as permission to modify the user's actual Codex, Cursor or Claude Code directories.

## 2. Usage

```bash
./gasl target-preflight \
  --plan-id YOUR_EXACT_PLAN_ID \
  --agent codex --scope project \
  --selected-root /ABSOLUTE/SELECTED/PROJECT

# Reinspect and reject changes since the previous read-only scan:
./gasl target-preflight \
  --plan-id YOUR_EXACT_PLAN_ID \
  --agent codex --scope project \
  --selected-root /ABSOLUTE/SELECTED/PROJECT \
  --expect-state-binding-id PRIOR_STATE_BINDING_ID
```

The `selected-root` argument must name an existing absolute, non-symlink directory. The CLI **never** automatically chooses a home or project folder. For `scope=user`, the caller must explicitly supply the intended user root; **GASL does not claim it has proven that it is a real Host home/profile directory**. Only documented filesystem adapters (`codex`, `cursor`, `claude-code`) are supported; Claude Desktop ZIP upload and generic MCP have no invented file-based install destination.

## 3. Implementation and fail-closed boundaries

- New `tools/host_target_preflight.py` validates an exact 64-hex Plan ID and calls the existing strict private-ZIP reader. The reader rechecks SHA-256, source identity, pinned main Git Blob, ZIP path/type constraints, Host and Scope, without extracting content or executing it.
- The target directory is computed only as `<explicit selected root>/<documented Host skill directory>/<sanitized Skill slug>`. No user-provided arbitrary target path or auto-discovered environment variable is accepted. Path components are inspected read-only to reject symlinks and non-directory parents. An existing sibling whose name differs only in case is treated as a collision on both case-sensitive and case-insensitive filesystems.
- For an existing Skill, a bounded inventory checks regular files and expected parent directories, rejects symlinks, empty/untracked directories, collisions, and out-of-limit file sizes/counts. Existing bytes are **read locally only to compute hashes**, never printed or exported. Existing file names, content and actual selected-root path are omitted from the returned JSON.
- The result reports `target_absent` or `existing_skill_collision`, existing file count, an inventory SHA-256 and the `state_binding_id` computed from the canonical target pathname digest, Host, Scope, Plan ID, archive SHA-256 and current existing-file inventory hash. A second read-only call with `--expect-state-binding-id` fails closed if the target root, target files, or private ZIP have changed.
- The binding is a **local state fingerprint, not an authentication token, user consent receipt, trusted signature or permission to install**. A real installer would need to revalidate this state immediately before any mutation and independently obtain explicit authorization for exact target, source version, permissions and replacement choice.
- Output includes `installation_allowed=false`, `actual_install_enabled=false`, `real_host_files_modified=false`, `third_party_skill_executed=false`, `state_binding_is_authorization=false`. Source license warnings, missing old Git Blob evidence and unverified Host compatibility remain visible.
- Existing Agent installations were **not** inspected by the assistant. This phase's positive tests used a generated disposable root selected explicitly during testing. Read-only scanning of an actual user's existing target would read its file bytes locally for hashing, which must be understood before choosing to invoke the CLI against private directories.

### Files

| File | Purpose |
|---|---|
| `tools/host_target_preflight.py` | Explicit root selection, bounded existing-target inventory, canonical path/state binding, drift verification |
| `tools/gasl.py` | New `./gasl target-preflight` CLI command |
| `tests/test_host_target_preflight.py` | Synthetic selected-root fixtures: unchanged, collisions, symlinks, missing root, change detection, privacy and Host/Scope mismatch |
| `.github/workflows/gasl-target-preflight.yml` | Dedicated Linux CI, read-only repository permission, tests with **synthetic private ZIPs** and no personal Agent profiles |
| `.github/workflows/gasl-refresh.yml` | Excludes isolated preflight implementation-only changes from expensive daily-source refresh triggers |
| `README.md`, `docs/ROADMAP.md`, this report | User guidance, evidence and remaining gates |

## 4. Actual local checks and results

The 20 test methods in `tests/test_host_target_preflight.py` cover absent/occupied targets; all three filesystem Hosts and both scopes; explicit Plan ID binding; source/target drift; wrong Host and Scope; path normalization; target/root symlinks; regular-file parent; case-insensitive directory collision; added untracked directory; corrupt ZIP; and absolute-path/content redaction. Existing files are never overwritten, moved, installed, or executed.

A separate local CLI smoke run used the actual private `academy-guide` ZIP from Phase 25 (`GASL-SRC-ce593c8b9b3fd34f44d6`) and a **new disposable selected root**. It confirmed:

1. Absent target returned `target_absent`, `existing_file_count=0`, no new directory and no installation permission.
2. A second read-only preflight with the first `state_binding_id` matched and succeeded.
3. Creating an inert `SKILL.md` in the **temporary target** invalidated the old binding, with the content unchanged by GASL.
4. Re-running preflight returned `existing_skill_collision`, one existing hashed file and **no path or file content in result JSON**.

**Local acceptance:** **365 tests and 139 subtests passed**, Python compilation and whitespace checks passed. The raw private ZIP remained Git-ignored; no ZIP, source file, local selected root, private paths or sensitive account data are part of this public report. Dedicated Linux CI should be observed separately after publication; local success is not silently treated as a completed remote CI test.

## 5. Remaining work before any real user-profile installation

- **Explicit user consent:** bind a separate, authenticated real-install approval to the exact source SHA-256, Host, scope, canonical path, action (`install` versus `replace`), and permission boundaries. A read-only `state_binding_id` or simulation acknowledgement **cannot** be repurposed as approval.
- **Durable transaction:** implement state-revalidated, mutually exclusive real installation with filesystem-safe versioned backup and post-crash recovery before changing anything in a user directory. Preserve user edits and prevent concurrent installer collisions.
- **Host-specific discovery and policy:** live Codex Skill discovery was verified only with an inert fixture on Linux; Cursor ACP and Claude Code CLI readiness do not yet prove actual Skill discovery. Third-party Skill safety and licensing are independent prerequisites.
- **Windows and real profiles:** inspect disposable real Host accounts with explicit permission; this phase does not modify the user's personal Mac Agent directories or invoke any Skill code.

**Phase 27 acceptance scope: read-only, version/path/state-bound preflight is implemented and locally tested. Real user installation remains disabled.**
