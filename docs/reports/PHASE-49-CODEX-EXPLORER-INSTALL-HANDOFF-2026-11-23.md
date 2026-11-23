# Phase 49 — Explorer → Codex project interactive install handoff

**Date:** 2026-11-23
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`
**Starting main:** `49c7bbae17d24f7d15854bd79d57c0084795cc57`

## Decision and scope

Per product direction, **manual usability testing and independent relevance adjudication are deferred**. Implementation proceeds on the missing product capabilities. Phase 49 addresses the highest-impact integration gap: a chosen Skill in the Explorer can lead into the existing *actual, transactional Codex project installer* through **one copyable local terminal command**.

The browser is still search/read-only; no HTTP endpoint is authorized to modify Agent files. The local CLI remains the only installation entry point and performs independent interactive approvals.

## New local CLI

From the GASL repository:

```bash
export GASL_SELECTED_PROJECT="/absolute/path/to/existing/git/project"

# Read-only: inspect the source identity, package readiness and safety warnings
./gasl codex-install-wizard \
  --id GASL-SRC-EXACT_ID \
  --selected-root "$GASL_SELECTED_PROJECT" \
  --action preview

# Real Codex PROJECT-only installation: local TTY required
./gasl codex-install-wizard \
  --id GASL-SRC-EXACT_ID \
  --selected-root "$GASL_SELECTED_PROJECT" \
  --action install --download-if-missing

# Separately requested full-backup replacement, never implicit
./gasl codex-install-wizard \
  --id GASL-SRC-EXACT_ID \
  --selected-root "$GASL_SELECTED_PROJECT" \
  --action replace --download-if-missing
```

`--download-if-missing` is an **explicit opt-in**, not a default. The wizard cannot use it without a real local TTY and a dedicated exact phrase identifying the selected pinned Skill and Commit. Download is done through the existing pinned downloader and static scan. If the package remains missing, corrupt or statically blocked, the transaction stops before touching any Agent path.

If the complete pinned private ZIP does not exist, the wizard prints the source Plan ID and requests a second exact TTY approval to create the private ZIP. Existing ZIPs must pass independent manifest/hash integrity verification and are never silently overwritten. Missing ZIPs are never automatically rebuilt after an integrity failure.

The selected project must be an **explicit absolute existing Git root**, not the user HOME. The project target, source Plan, content inventory and path/ZIP state binding are checked by the existing `preview_install` or `preview_replace`. Final installation or replacement invokes the original `install_fresh` or `replace_existing` with their own **third, exact TTY confirmation**. Those installers revalidate under the same project lock, preserve a managed receipt, require Backup on replacement and retain crash-recovery support. No Skill code or model is executed.

## Explorer integration

The existing selection view now shows two commands for Codex: the traditional read-only `install-plan` and a new TTY-only project-install command with an explicit project-root environment variable. It provides a read-only source link and a copy action. Invalid/untrusted source IDs do not generate executable shell commands.

Cursor and Claude Code remain preview-only. The interface does not mislabel their installation as working; it explicitly states which Host supports real project installation. No new JavaScript framework, browser-execution bridge, model API or network-bound installation endpoint was introduced.

## Files changed

- `tools/codex_explorer_handoff.py`: read-only source/project inspection; locally interactive optional download, private ZIP preparation, integrity verification, binding and install/replace dispatch.
- `tools/gasl.py`: `codex-install-wizard` subcommand with explicit `preview|install|replace` and `--download-if-missing`.
- `web/index.html`: next step and copyable command for the selected Codex Skill; no browser write.
- `tests/test_codex_explorer_handoff.py`: disposable Git/Skill fixture-only tests for exact TTY requirement, wrong approvals, optional download refusal, valid/invalid ZIP, collision, normal install, full-backup replace, and read-only preview.
- `tests/explorer_workflow_smoke.js`: verifies selection produces the correct terminal command, never an HTTP install request, and selection resets.
- `.github/workflows/gasl-explorer-ux.yml`: local synthetic wizard tests added to the existing CI.
- `README.md`, `docs/ROADMAP.md`, and this report.

## Safety, testing and non-goals

The requester explicitly deferred **real-user testing, human judgments and live Host install trials**. Automated tests with inert, disposable project roots are retained as engineering gates; they do not make any claims about practical functionality on an actual user's project. No third-party Skill scripts were executed.

No Agent User Profile installation, Cursor/Claude actual installation, full Windows support, runtime sandbox, independent upstream authentication, license selection, or full release packaging was implemented in Phase 49. Those are separate future development steps; **none is represented as complete**.

## Verification

Local synthetic tests and the existing Explorer workflow script were successful. Full regression and GitHub Actions results will be recorded only after they are observed.

## GitHub publication and automated verification

- Feature commit: [`83806ba7637a72eb0c760622313c23733b46d28e`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/83806ba7637a72eb0c760622313c23733b46d28e), pushed on `main` after exact nine-file scope audit and sensitive-pattern scan. No private ZIP or token entered version control.
- [Explorer workflow run 45235640862](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45235640862): **completed SUCCESS**, including all synthetic wizard/HTTP/DOM tests.
- [ZIP preparation safety run 45235641025](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45235641025): **completed SUCCESS**.
- [Existing inert Codex fixture lifecycle run 45235640907](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45235640907): **completed SUCCESS**. It tests only disposable inert Skills; this feature did not perform a new real user installation or execute a third-party Skill.
- [Full catalog refresh and regression run 45235641044](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45235641044): **completed SUCCESS**, with **671 automated tests passed** and **57 source repositories / 4,430 attributed source records** after source refresh.
- Automatic catalog-only commit [`d55060fc3dd19de3a3d4d6e35bbe651dc92c0223`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/d55060fc3dd19de3a3d4d6e35bbe651dc92c0223) was fetched and fast-forwarded into the local `main` without force-pushing.
- Local test evidence: **665 tests, 258 subtests PASS**, plus `EXPLORER_NEED_COMPARE_SELECT_WORKFLOW=PASS`. Python compilation and YAML parsing passed.
- No manual user test, no live untrusted Skill run, no human relevance adjudication and no actual Codex user project install were conducted.
