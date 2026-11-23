# Phase 40 — Opt-in Codex project Skill installation, removal and recovery

**Date:** 2026-11-23  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Base:** `ddf377ae5977ee5eae1596e8eafe6b9594cbba5b` on `main`.

## Goal

Take one narrow, testable step beyond Phase 39's disposable-profile-only ZIP lifecycle: implement **explicit, real filesystem installation** into a **caller-selected existing Codex Git project**, with strict source/ZIP verification, a read-only binding preview, local TTY confirmation, a persisted ownership receipt, collision refusal, uninstall and journal-based recovery. Do not automatically install any third-party Skill into the developer's real projects or personal Codex profile.

This Phase 40 slice supports only **fresh installs into an absent project-scope target**. Replacing an existing Skill, backing up an existing unmanaged Skill, unattended/scheduled installation, real user-scope HOME installation and executing a downloaded Skill remain **not implemented**. A fresh install has no previous version to back up; rollback means removing only the matching newly installed files.

## Implementation and exact CLI

New module: `tools/codex_project_install.py`. CLI commands:

```bash
# 1. Prepare a project-scoped, pinned reviewed ZIP first (previous GASL capability).
./gasl install-plan --id YOUR_SOURCE_RECORD_ID --agent codex --scope project
./gasl install-bundle --id YOUR_SOURCE_RECORD_ID --agent codex --scope project --acknowledge-plan-id EXACT_PLAN_ID

# 2. Pure read-only preview: no path writes or consent inference.
./gasl codex-project-install --action preview --plan-id EXACT_PLAN_ID --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT

# 3. A fresh real project install with exact preflight state binding.
# An *interactive local terminal* requests a source-and-target-bound phrase.
./gasl codex-project-install --action install --plan-id EXACT_PLAN_ID --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --state-binding-id EXACT_PREVIEW_BINDING

# 4. Removal of only GASL-managed, byte-for-byte unchanged Skill files,
# with a separate interactive terminal phrase.
./gasl codex-project-install --action uninstall --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name EXACT_SKILL_NAME

# 5. Recover an interrupted journaled transaction (only on selected project).
./gasl codex-project-install --action recover --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name EXACT_SKILL_NAME
```

There is deliberately **no** `--yes`, `--force`, `--replace`, `--scope user`, or `--execute-skill` option on this installer. The public CLI always demands a live local TTY and exact typed phrase for install and uninstall. Tests inject synthetic confirmation callbacks **only from in-process test code**; this does not constitute real human consent.

### Installation contract

- The selected root must be an existing, explicit absolute nonsymlink directory with a nonsymlink `.git` file or directory. The actual user `HOME` is refused. This is a Git-marker check, not an independent VCS provenance certification.
- The project-scope private ZIP must match the immutable Plan ID and current on-disk pinned catalog/source, current static scan and verified ZIP hashes. Malformed or complex Skill metadata fails closed.
- `host_target_preflight` checks destination absence and returns a state binding. Fresh install requires its exact prior value, rechecked again inside a POSIX advisory lock.
- Any existing same-name Skill, a differently-cased directory collision, unexpected symlink, unreadable state, pending transaction or target drift blocks install, **without overwriting or backing up existing files**.
- Stage the exact ZIP files under the selected project’s `.gasl-managed/stage` directory (outside `.agents/skills`, so Codex does not discover partially staged Skills); verify file inventory and hashes, create a fsynced transaction journal, atomically rename the verified directory to `.agents/skills/SKILL_NAME`, then write the exclusive receipt in `.gasl-managed/receipts`.
- The JSON receipt binds plan identity, target name, transaction ID, prior preflight state and exact file inventory. This hidden state folder is project-local and may show as untracked in Git; projects can add `.gasl-managed/` to `.gitignore` if desired.
- Uninstall checks the receipt and exact installed file inventory under the lock; if the user changed or added any file, uninstall refuses to delete it. Removal also uses a journal.
- Recovery validates pending journal and file inventory before finalizing an install receipt or removing a partly activated fresh install. An interrupted uninstall attempts to restore the original managed directory. Ambiguous or changed state fails closed for manual review.
- The process only copies bytes; it never runs them. It **does not automatically ask Codex to load or execute the installed Skill**. Users must separately choose what to do with installed content.

### Scope limitations

No protection against a hostile process that ignores the advisory lock and mutates the target in the narrow window between a final filesystem check and rename. State receipts are local filesystem metadata, not cryptographically authenticated against a malicious same-account attacker. No Windows installation yet (POSIX lock required). The fresh-only flow is not a replacement/upgrade workflow. A reviewed clean static scan is not a blanket proof that Skill instructions are safe to execute.

## Local tests and real-host observation

- `python3 -m unittest tests.test_codex_project_install -q`: **14 tests PASS**, using isolated temporary synthetic Git-marked project directories only.
- Tested preview-no-writes, install/uninstall, exact consent mismatch, stale state binding, unmanaged collision, symlink rejection, tampered ZIP/source rejection, preserved user edits, missing receipt, interrupted install rollback and interrupted uninstall restoration.
- **Real macOS Codex CLI `0.167.0` integration PASS**: a self-authored, inert two-file ZIP was prepared in a synthetic bundle fixture; `install_fresh` placed it in a temporary project scope; Codex `skills/list` reported exactly one enabled Skill at the correct path; after `uninstall`, Codex no longer discovered it. The process used an isolated empty HOME/CODEX_HOME, not the developer's account/profile, and no third-party code was executed.
- No live real user project was selected for installation, so no real user-project Skill files were installed or changed.
- Both the ZIP safety GitHub Actions workflow and Codex real-host workflow have been extended to test the new project installer with synthetic inputs only. Record their live run identifiers/results in a follow-up section **after** publication.

## Files changed

- `tools/codex_project_install.py`: opt-in fresh project install/uninstall/recovery.
- `tools/gasl.py`: `codex-project-install` CLI with preview/install/uninstall/recover.
- `tests/test_codex_project_install.py`: deterministic synthetic regression tests.
- `.github/workflows/gasl-private-install-bundle.yml`: synthetic project installer regressions.
- `.github/workflows/gasl-codex-transaction-e2e.yml`: real vendor Codex observation for synthetic fresh project install and uninstall.
- `README.md`, `docs/ROADMAP.md`, and this report.

## Next slice

Add safe **replace/upgrade** of an existing Skill with explicit separate per-action consent, immutable backup of the previous directory, and restoration after interruption, tested under forced failures. After that, make account/user-scope deployment an independent, explicit feature with unambiguous target-role validation and opt-in. Do not weaken preflight, execution or license-review boundaries to achieve automatic activation.
