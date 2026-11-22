# Phase 8–10 — Local-first Core, CLI, MCP and Explorer

**Date:** 2026-11-20  
**Repository:** Mahdi-Soleimani/global-ai-skills-library  
**Branch:** main (local working tree only; no push performed)  
**Scope:** Continue the Search, Router and Adapter phases with a strict no-hosted-server/no-paid-API requirement.

## 1. Goal and architectural decision

GASL is an open-source, local-first project. Normal use must not depend on a server operated or paid for by the maintainer.

The primary Agent integration is MCP over STDIO:

MCP Host → local gasl launcher → MCP adapter → shared GASL services → local SQLite/source catalog

The REST API and Explorer are optional local developer interfaces. They are not a hosted service and bind to 127.0.0.1 by default.

No paid LLM API, external embedding service, Docker, cloud account, or dedicated server is required for normal use.

## 2. Shared core

Added tools/gasl_service.py as the shared service layer used by adapters:

- Health and capability reporting.
- Search through the existing SQLite FTS5 index.
- Task routing through the existing router.
- Domain taxonomy.
- Skill details and provenance.
- On-demand retrieval of a pinned SKILL.md.

The CLI, MCP and REST adapter call the same functions. Search/routing logic is not duplicated between interfaces.

The health response explicitly reports that semantic search is not configured. The current search engine is lexical SQLite FTS5; the project does not claim semantic retrieval is already available.

## 3. MCP adapter

Added tools/mcp_server.py with six tools:

1. gasl_search_skills
2. gasl_get_skill_details
3. gasl_get_skill_content
4. gasl_route_task
5. gasl_list_domains
6. gasl_health

STDIO is the default and primary transport. Streamable HTTP remains an optional local/private mode, not a required deployment target.

Third-party content is returned as untrusted text. The adapter never installs or executes a Skill.

### STDIO integration test

A real MCP client subprocess test now performs:

- Server initialization.
- Tool listing.
- gasl_health invocation.
- Assertion that the catalog and non-execution status are returned.

This is not only a direct Python function test; it exercises the actual STDIO protocol.

## 4. Optional local REST API and Explorer

Added:

- tools/api_server.py — Python standard-library HTTP server.
- web/index.html — responsive Persian RTL Explorer.

Endpoints:

- GET /health
- GET /v1/domains
- GET /v1/search
- POST /v1/route
- GET /v1/skills/{source_record_id}
- GET /v1/skills/{source_record_id}/content

The local API supports optional bearer-token protection and refuses non-local binding without a token. Default use is localhost only.

## 5. On-demand content and safety

tools/gasl_service.py resolves content in this order:

1. Existing eligible local/public package content.
2. Private cache for the exact source identity and commit.
3. On-demand retrieval from raw.githubusercontent.com using the immutable 40-character commit SHA.

The retrieval path:

- Requires a valid repository identity and pinned commit.
- Requires a safe SKILL.md source path.
- Rejects path traversal and unapproved redirects.
- Limits content size to 256 KiB.
- Requires UTF-8 text.
- Caches retrieved content under ignored private/.
- Returns the SHA-256 and source identity.
- Marks all returned instructions as untrusted and never executes them.

## 6. Metadata enrichment

Added tools/enrich_skill_metadata.py and the gasl enrich CLI command.

It fetches only pinned SKILL.md files and extracts compact search metadata. It does not execute any Skill code.

Full bounded-batch enrichment completed for the current 4,405-record source universe:

| Metric | Result |
|---|---:|
| Source records | 4,405 |
| Metadata cache records | 4,405 |
| Successful pinned fetches | 4,404 |
| Skipped by 256 KiB safety cap | 1 |
| Fetch/network errors remaining | 0 |
| Records with descriptions | 4,372 |
| Records with search text | 4,405 |
| Search engine | SQLite FTS5 |

The one oversized source is retained as a reference record and marked skipped with reason safety_size_limit; GASL does not bypass the size limit. The cache is private/skill-metadata-cache.json, covered by .gitignore. It is local-only and is not automatically published or added to the public source catalog.

## 7. CLI and two-command quick start

Added the root gasl launcher and install.sh.

The documented user flow is:

~~~bash
git clone https://github.com/Mahdi-Soleimani/global-ai-skills-library.git && cd global-ai-skills-library && ./install.sh
~~~

~~~bash
./gasl mcp
~~~

install.sh creates a local .venv and installs only the optional MCP SDK. CLI search and local Explorer use the Python standard library and do not require MCP.

Added:

- requirements-mcp.txt
- requirements-dev.txt
- MCP_CONFIG.example.json
- MCP_CONFIG.codex.example.toml

No model weights are required or included. An incomplete optional model download was removed; semantic search remains a future optional local capability.

## 8. Router ranking correction

The router ranks by task relevance, phrase-level concept coverage, and weighted technology terms. Multi-token translated phrases must match as a phrase; a generic token such as “plugin” cannot fully satisfy “WordPress plugin”. Incidental mentions in the full Skill body carry less weight than the Skill name and frontmatter description. Query coverage and matched/unmatched term groups are exposed separately. Metadata completeness and provenance remain independent evidence fields, not proxies for Skill quality. The Persian/English taxonomy is now schema 1.3.0 and duplicate normalized expansion rules have been consolidated.

Search results also collapse identical pinned copies from the same repository/commit/content hash for display only. All source IDs, paths, and research leads remain visible; the source registry is not merged or mutated.

## 9. Bilingual search benchmark

Added benchmarks/search-gold-v1.json with 26 English/Persian queries and 148 provisional graded judgments, plus tools/search_benchmark.py and the ./gasl benchmark CLI command. The benchmark reports Precision@5, Recall@5, MRR@10, and NDCG@5 overall and by language. The current run is recorded in docs/reports/SEARCH-BENCHMARK-2026-11-20.md and its JSON companion. Labels remain provisional and require independent review.

## 10. CI and documentation

Updated GitHub Actions to install both development test requirements and the optional MCP SDK before running tests. This ensures MCP integration tests also run in CI.

Updated:

- README.md — local-first architecture, no paid server, two-command setup, MCP configuration, local-only Explorer, and security boundaries.
- docs/ROADMAP.md — corrected phases 8–10 and updated the remaining acceptance work.

## 11. Validation

- python3 -m compileall -q tools tests: PASS.
- python3 -m pytest -q: **132 passed** (plus 6 subtests).
- bash -n gasl install.sh: PASS.
- YAML parsing for both GitHub Actions workflows: PASS.
- git diff --check: PASS.
- MCP STDIO: a real MCP client initialized the root launcher, listed all six tools, called health, and completed a Persian WordPress search: PASS.
- MCP Streamable HTTP: a real MCP client initialized the local server, listed all six tools, and called health: PASS.
- Local REST API: health returned 4,405 records; Explorer HTML loaded; Persian WordPress search returned the expected top result: PASS.
- Search benchmark: 26 queries / 148 provisional judgments; Precision@5 0.5308, Recall@5 0.6651, MRR@10 1.0000, NDCG@5 0.7762. Persian NDCG@5 0.7648. See the separate report.
- Local API authentication and input validation tests: PASS.
- On-demand content tests for local cache, pinned upstream fetch, private cache, and unsafe source path: PASS.
- No Skill was installed or executed.
- No remote GASL server was deployed or purchased.
- No API key or paid service was used.

## 12. Files added or changed in this phase

Added:

- config/taxonomy.json
- tools/gasl_service.py
- tools/mcp_server.py
- tools/api_server.py
- tools/enrich_skill_metadata.py
- tools/safe_http.py
- tools/skill_search.py
- tools/skill_router.py
- tools/skill_evaluation.py
- tools/search_benchmark.py
- web/index.html
- gasl
- install.sh
- requirements-mcp.txt
- requirements-dev.txt
- MCP_CONFIG.example.json
- MCP_CONFIG.codex.example.toml
- registry/skill-evaluations.json (derived evidence metadata; no behavioral quality score)
- tests/test_gasl_service.py
- tests/test_api_server.py
- tests/test_mcp_server.py
- tests/test_skill_search.py
- tests/test_skill_router.py
- tests/test_skill_evaluation.py
- tests/test_enrich_skill_metadata.py
- tests/test_safe_http.py
- tests/test_search_benchmark.py
- benchmarks/search-gold-v1.json
- docs/reports/SEARCH-BENCHMARK-2026-11-20.md
- docs/reports/SEARCH-BENCHMARK-2026-11-20.json
- .github/workflows/ci.yml
- docs/reports/PHASE-8-10-LOCAL-FIRST-MCP-2026-11-20.md

Updated:

- tools/gasl.py
- .github/workflows/gasl-refresh.yml
- .gitignore
- README.md
- CONTRIBUTING.md
- docs/ROADMAP.md

The public-catalog description enrichment and its tests/build changes were already in the working tree from the preceding catalog phase; they remain local and are not included in the scope of this phase report. Metadata cache and SQLite index are generated locally and remain excluded from Git.

## 13. Open items and acceptance gates

1. PASS: a clean export of the current working tree, excluding ignored private data, installed MCP 2.3.0 into a fresh Python 3.13.9 virtual environment and passed independent STDIO tool calls. This tests the local candidate, not an already published release. See HOST-COMPATIBILITY-AND-INTEGRITY-2026-11-20.md.
2. Verify MCP configuration and tool calls in at least two real MCP hosts.
3. Refresh local metadata only when source pins change; current 4,405-record snapshot is fully processed, with one intentionally skipped oversized SKILL.md.
4. Obtain independent domain review of the provisional 26-query/148-judgment benchmark; expand the query set using real anonymized user search tasks.
5. Evaluate optional local semantic search only after measuring memory, CPU, retrieval quality, and model distribution/licensing. It must remain optional and must not add paid API dependencies.
6. Select and add a license for GASL's own code. The current repository has no root LICENSE file; public visibility alone does not grant an open-source license.
7. Review the complete public diff and run CI before pushing.

**Acceptance:** Local core, CLI entry point, MCP STDIO adapter, local REST/Explorer, full local metadata enrichment, query-coverage ranking, duplicate display grouping, and bounded safe retrieval are implemented and pass the current 132-test suite. Clean local installation now passes; real application host compatibility remains an open gate. See the follow-up compatibility and integrity report.
