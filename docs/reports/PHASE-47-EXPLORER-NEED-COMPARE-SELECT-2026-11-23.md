# Phase 47 — Explorer: need → compare → select

**Date:** 2026-11-23
**Repository:** Mahdi-Soleimani/global-ai-skills-library
**Baseline main:** `4962bb4` (Phase 46)
**Product priority decision:** Deferred independent upstream verification (formerly proposed Phase 47); prioritized **usable Skill discovery and selection** instead.

## User-facing objective and scope

Turn GASL from a list of indexed Skill sources into a usable selection workflow with **minimal additional architecture**. A person describes a task, receives provisional matching candidates, compares two or three relevant options, and picks one for independent source review / optional read-only installation planning.

Reuse the existing lexical FTS5 search, answerability-aware router, source catalog, local REST Explorer and independent Codex installation-preview safeguards. No new search engine, model provider, payment, Docker, AI API, cloud account or persistent choice database was introduced.

## Experience implemented

1. **Describe the task:** `./gasl serve` opens the existing Explorer at `http://127.0.0.1:8787`. The new primary `پیشنهاد برای نیاز` action calls `POST /v1/route` with the text, requested Agent, domain and public/content filters. The secondary `جست‌وجوی گسترده` action preserves `GET /v1/search`. Both use the existing ranking method and display the counts, relevance and evidence warnings. Router decisions `recommend`, `abstain` and `undetermined` are visible, with an explicit note that these are **uncalibrated lexical heuristics**.
2. **Compare:** each result has an accessible, labeled selection checkbox. Two to three choices activate the Compare button; attempting a fourth does not change selection. `POST /v1/compare` independently retrieves the **exact selected stable source record IDs** from the locally indexed catalog and returns a comparison of descriptions, repository, license/assessment, source security status, declared compatibility, content availability and pinned commit, with differing fields identified. No overall quality score, no “best/safest” claim, no unverified ranking adjustment.
3. **Select for independent review:** clicking the chosen column creates a selected-Skill summary, links only to a well-formed HTTPS GitHub source, offers the existing details view and the optional `./gasl install-plan --id ... --agent ... --scope project` **preview-only** command. The page does not invoke that command or any install/execute endpoint. Real installation remains a separate user-triggered and TTY-confirmed project-only process.
4. **State management:** starting another search cancels stale comparison display via request/revision counters, clears previous choices and selected preview, and does not reuse stale results. In-progress search buttons are disabled. Error and insufficient-evidence states use appropriate warnings. Small-screen layouts retain responsive cards and an independently horizontally scrollable comparison table.
5. **Progressive disclosure:** candidates first; side-by-side evidence only after selection; the exact next command only after selecting a comparison column. Source descriptions are displayed with `textContent` to prevent HTML injection.

## New / modified API

`POST /v1/compare` takes:

    {"ids":["GASL-SRC-EXACT_ID_A","GASL-SRC-EXACT_ID_B"]}

It validates a JSON list containing **exactly 2 or 3 distinct**, correctly formatted source IDs. Unknown valid IDs return HTTP 404; malformed/duplicate/cardinality violations return 400; existing bearer-token policy returns 401 when configured. The response contains the exact selected records in input order, differentiating evidence fields and explicit `winner_selected=false`, `quality_scoring_performed=false`, `installation_performed=false` and `execution_performed=false`. No upstream URL is fetched, no Skill file is evaluated, and no repository metadata is silently certified as authentic. The service reuses `skill_details`, rather than accepting untrusted comparison details from the browser.

The existing search, router, details and SKILL.md retrieval endpoints remain backwards-compatible.

## Files changed

- `web/index.html`: three-stage workflow, route/search actions, selection checkboxes, bounded comparison, responsive evidence matrix, selection preview and race/error safeguards.
- `tools/skill_compare.py`: read-only, validated 2–3 source-record comparison. No new dependency.
- `tools/api_server.py`: authenticated `POST /v1/compare` HTTP handling, 400/404 error boundaries, docs endpoint line.
- `tests/test_skill_compare.py`: local fixture and actual HTTP tests for validated IDs, access controls, provenance distinctions, absent winner, no remote/Skill execution and unchanged source files; HTML and JS syntax checks.
- `tests/explorer_workflow_smoke.js`: standalone, dependency-free simulated DOM/HTTP end-to-end test for recommendation, selecting two options, comparison, choice, preview command, safe source link, and reset on a new search.
- `.github/workflows/gasl-explorer-ux.yml`: targeted push/PR CI for the UI, REST/API, Python tests and Node flow test.
- `README.md`, `docs/ROADMAP.md`, this file: product guidance and explicit limitations.

## Test plan and acceptance criteria

- Python fixture comparison/API tests pass for 2/3 IDs, duplicate/unknown/malformed input, exact order, different license/security evidence, no execution, bearer auth, and existing route behavior.
- The JS simulated-browser flow prints `EXPLORER_NEED_COMPARE_SELECT_WORKFLOW=PASS` when recommendation → checkboxes → compare → select → preview command → reset succeeds.
- Source string/syntax checks prevent frontend regressions, and a real-catalog smoke test confirms the current 4,431-record index can route a task and compare two returned IDs.
- A full local pytest suite and Linux CI verification must pass before the feature is considered fully accepted.
- The core ranking method is **not** asserted accurate; examples of weakly related candidates are a reminder that user review remains necessary.

## Security, privacy and cost boundaries

- Localhost-only Explorer by default. The new endpoint respects existing REST token authentication.
- No remote fetch, download, install, execution, model prompts or state-changing host API in the new comparison flow.
- UI uses text nodes for untrusted catalog content; external links must be HTTPS `github.com`. The generated command includes only server-verified stable IDs and an explicitly chosen Agent. `install-plan` is **read-only**.
- Relevance ≠ quality; static security flags ≠ security approval; declared compatibility ≠ verified compatibility; repository license metadata ≠ verified license permission. The interface explicitly avoids these false claims.
- No new paid API, Docker, frontend build system, runtime dependency, account or hosting cost.
- No real personal Codex profile or any actual user project is modified during frontend/test work.

## Remaining limitations and next candidate work

The UX is local-first and currently uses the existing exploratory *lexical* router and its limited calibrated evidence. No personalized trained ranking, verified behavioral scores, independent publisher authentication, or direct one-click installation is claimed. A future iteration could add query reformulation and outcome feedback, but must keep the no-automatic-execution and provenance gates.

## Publication / final CI

To be completed **only after observed test results and GitHub publication**: test counts, commit hashes, exact CI run IDs/conclusions, and any source-catalog refresh metadata-only commit.

## Verified local test evidence

- **Complete local regression:** `python3 -m pytest -q --ignore=tests/test_mcp_server.py` — **632 passed, 258 subtests passed** (local Python environment lacks optional MCP dependency). Revalidated after the final direct-choice UX change.
- **Focused comparison / API:** `python3 -m unittest tests.test_skill_compare -q` — **40 passing tests** (some inherited fixture cases are intentionally exercised again with the authenticated HTTP server). Prior existing API/service regressions: **22 passing tests**.
- **Browser interaction simulation:** `node tests/explorer_workflow_smoke.js` — **EXPLORER_NEED_COMPARE_SELECT_WORKFLOW=PASS**. Checks provisional recommendations, direct single-result selection, checkbox comparison, choosing a comparison column, the preview-only CLI command, safe source URLs and resetting stale selections on a new search. This is a dependency-free DOM simulation, not a full visual browser accessibility audit.
- **Real catalog smoke:** existing router returned candidates for an API security task and the two selected source record IDs were successfully compared from the actual local attributed catalog. Results can include weakly related alternatives; this is why no calibrated quality or safety claim is made.
- Workflow YAML parse, inline JavaScript syntax, Python compilation and Git whitespace checks passed. Local search may build/refesh its SQLite index; no Skill or real Agent files are installed or executed.

## GitHub publication and CI

Pending live verification: final feature SHA, targeted Explorer workflow result, full catalog-refresh workflow result, and metadata-only automatic commit (if generated).

## Verified publication and CI acceptance — 2026-11-23

- Feature commit: [`1f5656779a5813422bb862f2b3033fa5d91e9db6`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/1f5656779a5813422bb862f2b3033fa5d91e9db6), pushed normally to `main` after a strict nine-file staging allowlist, secret-pattern scan and whitespace checks. No private Skill archive, secret, personal HOME path or unrelated code was published.
- [Explorer user-flow CI — Run `45217438649`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45217438649): **completed / SUCCESS**. The workflow verified API authentication/validation, Node-based simulated browser interactions, Python compilation and source whitespace.
- [Full Catalog Refresh and Regression — Run `45217438615`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45217438615): **completed / SUCCESS**. Python integration and regression suite on Linux reported **638 passed**. Source refresh confirmed **57 repositories** and **4,431 source records**. Metadata-only commit [`7ef61f37e9edafeb04d6bb34a7d520ae9d390cdd`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/7ef61f37e9edafeb04d6bb34a7d520ae9d390cdd) was published by GitHub Actions and then **fast-forwarded locally** without force-push.
- Final local regression after direct single-card selection: **632 passed, 258 subtests passed**, excluding only optional `tests/test_mcp_server.py` in local Python. Node workflow simulation **PASS**. No real Skill execution, installation, user Agent modification, external model calls or new infrastructure costs.
- The outcome is a **working local exploratory search-and-choice flow**, not a calibrated quality/safety recommender. Human review remains necessary.

**Acceptance status: PASS.**
