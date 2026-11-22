# GASL — Phase 8: verified search vocabulary pilot

Date: 2026-11-20. Local working tree; no commit or push.

## Scope and decisions

The clean public catalog has 4,405 source records but only nine public mirrored packages with descriptions. Avoid heavyweight model downloads and new dependencies in the default installation. Keep the full source catalog independent of license classification. Index only terms selected from the GASL-maintained 236-token vocabulary; do not copy upstream descriptions, instructions or Skill bodies into the new index. No private centralized archive. No installation or execution.

## Implementation

- tools/search_features.py: bounded parallel retrieval from the pinned GitHub raw URL, exact Git blob verification before metadata extraction, frontmatter-derived standard vocabulary intersection, versioned deterministic output, exact repository/path/commit/blob matching, unchanged-blob reuse across commit changes with verified_at_commit provenance.
- registry/search-features.json: 291 actual verified source records, 146,237 bytes. Each entry links to the source catalog by its immutable source_record_id. Includes all eligible license classes without a license allowlist.
- tools/skill_search.py: index verified vocabulary terms in FTS, keep evidence separate in results and prioritize them below direct title/description evidence. Inferred domain labels remain a weaker signal, but no longer inject every unrelated domain keyword. Index version 1.2.1 and feature file fingerprint.
- tools/gasl.py: features command. tools/gasl_service.py: verified feature count in health. Current engine is lexical with curated cross-language concepts, not semantic embeddings.
- .github/workflows/gasl-refresh.yml: bounded 200-record incremental update after public-only catalog build; stage the generated vocabulary index. No new archive or external service.
- Regression tests cover unknown license, exact blob, rejected mutation/stale pin/unknown terms, no copied text, reuse without downloading the exact unchanged blob, domain evidence and local search.

## Live pilot

16/16 in the first batch; 275/300 in the next batch. Total 291/316 successful, 25 network errors (URLError/RemoteDisconnected). Only successful verified rows were promoted from a temporary public-only workspace. Actual file contents were not stored in the public index. 4,114 eligible records remain uncovered; retry on later bounded runs. The new Actions code has not run on GitHub yet.

## Development benchmark

Frozen 26-query / 148-judgment development set, same public-input source catalog and final ranking code, with and without the actual verified vocabulary tags. Original pre-change baseline is included separately for context.

| Metric | Original clean install | Domain-evidence correction, no tags | 291 verified tags |
|---|---:|---:|---:|
| Precision@5 | 0.2462 | 0.2692 | 0.3385 |
| Recall@5 | 0.2934 | 0.3092 | 0.3871 |
| MRR@10 | 0.6609 | 0.6282 | 0.5882 |
| NDCG@5 | 0.3923 | 0.3961 | 0.4391 |

Median warm query time 18.8 ms, maximum 22.4 ms on the tested Mac for these 26 queries. Not a hardware-independent performance guarantee. Full details: SEARCH-FEATURES-PILOT-2026-11-20.json.

An earlier experiment simulated 4,404 feature records using historical unverified local metadata: NDCG 0.6947 before correcting domain evidence, 0.6456 after that correction. This is not a verified public index and was not published. No unverified historical cache is promoted to the public vocabulary.

The live pilot improves top-five precision, recall, and NDCG while MRR declines. Partial coverage can bias the ranking toward enriched records. The development labels were previously tuned against results, are incomplete and not independently reviewed. No claim of universal improvement or measured behavioral Skill quality. Keep evaluating coverage and first-hit rank before stable release.

## Remaining

- Incremental verified vocabulary coverage, retry failed records and evaluate a frozen independent query set.
- True local semantic embeddings/hybrid search: no appropriate installed embedding runtime or model was found on the Mac. Existing speech models are unrelated. No large model or extra dependency was installed. Evaluate a small multilingual model separately only if it demonstrably improves relevance and resource use.
- Historical private metadata remains unverified; not included in this public pilot.
- Real Actions execution after publication, cross-platform checks, security review, Agent activation and release remain separate gates.

Validation: 148 passing tests plus 6 subtests; git diff --check passed (existing CSV line-ending normalization warnings).
