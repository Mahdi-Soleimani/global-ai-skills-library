# GASL — Installation, compatibility and integrity follow-up

Date: 2026-11-20
Scope: local working tree, main, before publication; base commit 7e616c0.

## Results

| Check | Status |
|---|---|
| Clean export (237 tracked/unignored candidate files; no original private cache) | PASS |
| Standalone Python 3.13.9 / macOS virtual environment | PASS |
| install.sh / PyPI MCP SDK 2.3.0 and dependencies | PASS |
| CLI search without MCP or metadata enrichment | PASS |
| Fresh environment STDIO initialize, list six tools, health, search, route | PASS |
| Real MCP SDK / Streamable HTTP | PASS in prior local integration |
| Claude Desktop actual host | Not tested, not found at standard app paths |
| Cursor actual host | Not tested, not found at standard app paths |
| Codex actual host | Not tested, CLI not found on PATH; app not found at standard paths |
| ChatGPT desktop | App found, no local GASL connection claimed |
| Windows/Linux | Not tested in this local session |
| Public mirror SKILL.md byte integrity | 9/9 Git blob SHAs match |
| Real pinned metadata read | PASS, source GASL-SRC-d605f3b2264991f893aa |
| Regression suite | 137 passed, 6 subtests passed |
| git diff --check | PASS |

The test copy had no inherited Commandrix site-packages in sys.path. The previous PyPI TLS blocker did not recur. No live application configuration was modified, and no third-party Skill was executed or installed.

## Changes

- tools/skill_router.py: preserve search ordering after eligibility filtering; expose per-concept coverage. Prevent a generic, higher lexical score from undoing specific concept priority.
- tools/gasl_service.py: verify original Git blob bytes against the catalog's SHA, enforce UTF-8 and byte limit, preserve BOM/CRLF in cache, and return exact-byte SHA-256 and verified Git blob SHA. Fail closed on mismatch or missing blob evidence.
- tools/enrich_skill_metadata.py: check newly retrieved inputs before extracting metadata; record verified blob evidence.
- tools/search_benchmark.py: record dataset hash, exact search-input fingerprint, ranking code SHA-256 and cache presence.
- tests/test_skill_router.py, tests/test_gasl_service.py, tests/test_mcp_server.py, tests/test_api_server.py, tests/test_enrich_skill_metadata.py: regression tests and actual Git hashes for fixture bytes.
- docs/reports/SEARCH-BENCHMARK-CLEAN-2026-11-20.json: same development judgment set on the isolated public-input workspace.

## Limitations / decisions

- The 4,404 successful metadata records from the earlier run have not been retroactively verified against Git blob hashes; only new reads use the new gate. No bulk re-download was performed.
- A prior normalized cache entry that fails byte integrity is rejected, not silently trusted or overwritten.
- New installs have lower retrieval quality; optional enrichment improves available evidence, but the fresh versus enriched comparison is not an isolated causal experiment.
- Benchmark was tuned iteratively and is provisional, not a held-out quality claim. No behavioral Skill effectiveness or runtime security approval is inferred.
- No root project LICENSE has been selected. No remote publish, release, or Git push was performed in this follow-up.

## Acceptance

PASS for standalone installation, actual isolated protocol integration, router consistency, exact-byte integrity and a paired reproducible search-development benchmark. Real application hosts, cross-platform CI, independent benchmark review, complete security triage and project license remain open.
