# GASL Search Benchmark — 2026-11-20

**Status:** Provisional internal regression benchmark  
**Catalog snapshot:** 4,405 source records  
**Dataset:** benchmarks/search-gold-v1.json  
**Machine-readable output:** docs/reports/SEARCH-BENCHMARK-2026-11-20.json

## Scope

- 26 queries: 13 English and 13 Persian.
- 148 graded relevance judgments.
- Relevance scale: 0 = not relevant/unjudged, 1 = adjacent, 2 = relevant, 3 = highly relevant.
- Top-K: 5; MRR cutoff: 10.
- Metrics are macro-averaged per query.

## Results

| Metric | Overall | English | Persian |
|---|---:|---:|---:|
| Precision@5 | 0.5308 | 0.5231 | 0.5385 |
| Recall@5 | 0.6651 | 0.6786 | 0.6516 |
| MRR@10 | 1.0000 | 1.0000 | 1.0000 |
| NDCG@5 | 0.7762 | 0.7876 | 0.7648 |

## Fresh-install comparison

The same 26 queries, 148 judgments, source catalog, taxonomy and ranking code were evaluated in an isolated copy without the private metadata cache or private package registry.

| Metric | Fresh install (public-only inputs) | Enriched local workspace |
|---|---:|---:|
| Precision@5 | 0.2462 | 0.5308 |
| Recall@5 | 0.2934 | 0.6651 |
| MRR@10 | 0.6609 | 1.0000 |
| NDCG@5 | 0.3923 | 0.7762 |

The enriched results are not representative of a fresh user's installation. The difference reflects the combined local inputs, not an ablation isolating the metadata cache alone. See SEARCH-BENCHMARK-CLEAN-2026-11-20.json for the public-input run.

## Search changes evaluated

1. Persian-to-English domain phrase expansion for WordPress, Next.js, TypeScript, Excel/XLSX, SEO, GitHub Actions, Cloudflare Workers, FastAPI, Redis, Telegram, authentication, and related terms.
2. Phrase-level alternatives: all tokens in a translated concept are required for full coverage; partial coverage is possible. Tokens need not be contiguous. A generic match such as plugin no longer satisfies the complete concept WordPress plugin.
3. Weighted concept groups: named technologies and specific phrases can carry more weight than generic action words.
4. Lower evidence weight for incidental mentions in the full Skill body; Skill name and frontmatter description remain stronger signals.
5. Search result duplicate grouping remains display-only and preserves source IDs and paths.

## Interpretation and limitations

- In the enriched run, the first judged-relevant result is ranked first for every query in this provisional set (MRR@10 = 1.0). It does **not** mean every top-5 result is relevant.
- Precision@5 is affected by the intentionally incomplete judgments. Unjudged results count as non-relevant; metrics are relative to these incomplete judgments, not exhaustive ground truth.
- Several queries have only one or two known relevant Skills, so a low Precision@5 can coexist with Recall@5 = 1.0.
- The queries and labels were iteratively revised during ranking development based on catalog descriptions and observed search results. This is a development set, not a held-out evaluation; independent review and a frozen unseen test set are required. They are not an independent or public quality certification.
- This measures search relevance only. It does not measure whether a Skill improves an Agent's task success, nor does it approve a Skill's license, security, or execution safety.
- No Skill was installed or executed during this benchmark.

## Reproduction

~~~bash
./gasl benchmark --k 5 --mrr-k 10
~~~

The JSON reports record catalog, taxonomy, dataset and ranking-code SHA-256 fingerprints and a combined search-input fingerprint, plus private-cache presence. Original private metadata is not published. Source IDs are commit-specific: a changed catalog may need a new independently reviewed benchmark version.
