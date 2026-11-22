# GASL — Search features batches 02 and 03

Date: 2026-11-20. Local working tree; no commit or push.

## Coverage and evidence

The fixed 4,405-source public catalog was rebuilt separately from local registry/package metadata. All license classes remain eligible; no full Skill contents, private descriptions or model weights are published.

| Batch | Attempts | New verified | Failures | Cumulative verified |
|---|---:|---:|---:|---:|
| Initial pilot | 316 | 291 | 25 | 291 |
| 02 | 500 | 496 | 4 | 787 |
| 03 | 500 | 495 | 5 | 1,282 |

All 25 initial failures were recovered in batch 02. Nine failures remain in the exact-pin failure ledger; 3,123 source records remain without verified features. Coverage is 29.1%. Features span all 57 public repositories. All existing 291 and then 787 entries were compared for exact equality before promoting the expanded index. The resulting feature file is 631,071 bytes and contains only curated vocabulary terms and source pin/verification evidence, plus error-class counts and exact-pin references for failed attempts.

## Resumability

- Persist failure attempts keyed by source record, commit and blob.
- Prioritize unattempted records over retries while maintaining repository round-robin within a tier.
- Checkpoint every 25 processed requests and at batch completion, using atomic file replacement.
- Successful retries clear their failure entries; changed source pins invalidate prior failure evidence.
- New tests verify that an unsuccessful record cannot starve untouched records and can subsequently be retried successfully.

## Frozen development benchmark

Same public-only snapshot, same lexical ranking code, same 26-query/148-judgment set.

| Metric | Original clean install | 291 features | 787 features | 1,282 features |
|---|---:|---:|---:|---:|
| Precision@5 | 0.2462 | 0.3385 | 0.3231 | 0.2923 |
| Recall@5 | 0.2934 | 0.3871 | 0.3714 | 0.3346 |
| MRR@10 | 0.6609 | 0.5882 | 0.6359 | 0.6424 |
| NDCG@5 | 0.3923 | 0.4391 | 0.4279 | 0.4165 |

Partial enrichment has uneven ranking behavior. Do not extrapolate these results to full coverage. No ranking weights or judgments were tuned this stage. The original clean baseline predates the domain-evidence correction; direct batch comparisons use the same corrected ranking code. The set is provisional and not independent. Detailed results are SEARCH-FEATURES-BATCH-02-2026-11-20.json and SEARCH-FEATURES-BATCH-03-2026-11-20.json.

## Semantic experiment

Added tools/semantic_experiment.py and tests/test_semantic_experiment.py. This is a bounded offline experiment that reranks lexical candidates with E5 embeddings and fixed weighted reciprocal rank fusion (semantic weight 0.35). It requires explicit pinned ONNX and tokenizer artifacts and verifies both against published hashes before loading. No network access or model download is performed by the experiment itself; no model files or new dependencies are added to the default installation. The prototype is not full-corpus vector retrieval.

Model: https://huggingface.co/Xenova/multilingual-e5-small/tree/761b726dd34fb83930e26aab4e9ac3899aa1fa78
Original model documentation: https://huggingface.co/intfloat/multilingual-e5-small

### Actual E5 execution

Both artifacts were downloaded into an isolated temporary environment and verified against the upstream SHA-256 and file sizes before ONNX execution. Earlier HTTP transfer timeouts were recovered by resuming the incomplete file. Weights: 118,054,593 bytes; tokenizer: 17,082,730 bytes. Python 3.13 ARM64, NumPy 2.5.5, ONNX Runtime 1.32.0, tokenizers 0.23.3. No changes to default dependency files.

| Metric | Lexical (same 30 candidates) | E5 rerank | Hybrid RRF |
|---|---:|---:|---:|
| Precision@5 | 0.3000 | 0.2538 | 0.3154 |
| Recall@5 | 0.3442 | 0.3053 | 0.3634 |
| MRR@10 | 0.6616 | 0.5972 | 0.6538 |
| NDCG@5 | 0.4261 | 0.3680 | 0.4405 |

The actual candidate-pool benchmark covers 26 queries and 417 distinct candidates. Two CPU threads; model load including artifacts verification 5.20 seconds, batch candidate encoding 3.35 seconds, median warm query encoding plus reranking 2.53 ms (candidate vectors already computed; excludes lexical retrieval and model load). Peak whole-process RSS 740.91 MiB on this Mac, not a model-only or incremental-memory measurement. The temporary virtual environment occupies approximately 170 MiB; no model weights or Python packages are committed.

Hybrid improves P@5 by 1.54 pp and NDCG@5 by 1.44 pp over the same candidate-pool lexical baseline, with a 0.78 pp MRR decline. Semantic-only reranking is worse overall. Given the memory/setup overhead and small, non-independent benchmark, do not enable semantic reranking in default search. Retain the explicit opt-in research prototype. Full-corpus vector retrieval, a frozen independent benchmark, and optional production integration remain open. Report: SEMANTIC-EXPERIMENT-2026-11-20.json.

## Validation

152 tests and 6 subtests passed. Git diff --check passed (existing line-ending normalization warnings). No Skill was installed or executed. No Git push or revised remote Actions execution was performed.
