> **Superseded scope notice — 2026-11-22:** The first V2 reviewer packet incorrectly replaced the Android device-SMS task with a Twilio webhook task. That substitution was an error. Do not distribute the Twilio-scope packets archived with `PRE-ANDROID-RESTORE-2026-11-22`. The active packet restores Android/Kotlin `BroadcastReceiver` banking-SMS reception and adds a separate answerability review. See `docs/reports/PHASE-11B-ANDROID-SMS-COVERAGE-CORRECTION-2026-11-22.md` for the authoritative corrected scope and validation.

---

> **Reviewer intake revision notice — 2026-11-22:** The original reviewer sheets, answerability forms and ZIPs described below are historical. The current distribution artifacts are the `INTAKE-V2` files under `private/benchmark-review/`, with explicit out-of-pool evidence fields and independent-human attestations. Distribute only `SEARCH-GOLD-V2-REVIEWER-A-PACKET-INTAKE-V2.zip` to Reviewer A and the corresponding B packet to Reviewer B. See [Phase 14](PHASE-14-HUMAN-REVIEW-INTAKE-2026-11-22.md). Hashes in this report describe the original preparation snapshot, not the current intake-v2 files.

# Phase 11 — Independent Bilingual Search Benchmark Preparation

**Date:** 2026-11-22  
**Status:** Review packet prepared; awaiting two independent human judgments  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Branch / base HEAD:** `main` / `7e616c0f5a8b6ba906bea59a0ade3fc163d9e418`

## 1. Goal

Prepare a new blind, bilingual relevance-review set that can later become an independent Search Gold Dataset. This phase prepares query tasks, candidate pools, reviewer separation, provenance, and adjudication scaffolding. It does **not** produce relevance labels or benchmark metrics.

## 2. Baseline and constraints

- Commit-pinned eligible Source Catalog: **4,405** records.
- Verified Search Feature records: **4,404 / 4,405** (99.9773%); one oversized Skill remains a permanent, policy-based exclusion.
- Existing benchmark: 26 queries / 148 judgments, status `provisional`. It is a development regression set, not independent Gold data. The Source Catalog and ranking-code fingerprints differ from the earlier snapshot; no direct before/after attribution is valid.
- A scan of the checked-in `private/` project tree found no real user search-query log. The new queries are therefore **curated task prompts**, not claimed to be real production searches.
- No Source Catalog, original research dataset, Skill package, taxonomy term, ranking weight, or search implementation was changed in this phase.

## 3. Query-set design

- **26** queries in **13** bilingual task pairs.
- **13 English + 13 Persian** formulations.
- **10** taxonomy domains represented.
- One relevance judgment is recorded per task-pair / Source ID. The English and Persian prompts in a pair are intended semantic translations of the same task, so the adjudicated qrels will be shared across both query IDs. This halves duplicate annotation while still allowing English and Persian retrieval results to be compared against the same relevance set.
- Reviewers can flag a language-specific exception if a pair is not semantically equivalent or a Skill only fits one formulation.

The initial Android banking-SMS task was replaced before reviewer distribution. The current catalog did not surface direct Android SMS parsing Skills; results were mostly generic messaging or Twilio content. The replacement is a corpus-supported task:

- English: secure Python FastAPI webhook for inbound Twilio SMS, signature validation, retry-safe processing.
- Persian: equivalent secure FastAPI webhook task for inbound Twilio SMS.

The replacement pool contains direct source candidates including `twilio-messaging-webhooks`, `twilio-webhook-architecture`, `twilio-sendgrid-inbound-parse`, `twilio-security-hardening`, and `fastapi-router-py`. This improves task-to-corpus construct validity; it does not assert that those candidates are relevant before human review.

## 4. Candidate-pool construction

For each bilingual pair, the candidate pool is the deduplicated union of:

1. Top 8 results from the current GASL search for each language variant.
2. Top 5 candidates from metadata-token overlap for each language variant.
3. Top 5 results from a domain-level retrieval query.
4. Two deterministic random controls from the eligible pinned corpus.

Results:

- **373** unique task-pair / Source ID candidate rows.
- Pool size per pair: **17–46** candidates.
- **26** random controls in total (two per pair).
- Equivalent query-specific qrels after adjudication: up to **746** rows (373 candidates × two language query IDs).
- Each candidate carries its Source ID, repository, path, exact commit SHA, and Git Blob SHA.
- The private manifest records each candidate's pool origin and pinned provenance. Pool origin, rank, and retrieval scores are deliberately absent from reviewer files.

This is a pooled set, not an exhaustive scan of all 4,405 Skills. Reviewers are instructed to append relevant Source IDs found outside the pool.

## 5. Blind-review protocol

Two independent reviewer files were created:

- Reviewer A: **373** rows, independently randomized order.
- Reviewer B: **373** rows, independently randomized order.
- Adjudication template: **373** rows with separate A/B grades and final adjudication fields.

Relevance scale:

- `0`: Not relevant.
- `1`: Related, but insufficient for the task.
- `2`: Useful and actionable for a meaningful part of the task.
- `3`: Direct match / primary useful Skill.

Relevant threshold: **2**.

Reviewers must not see each other's files, the private provenance manifest, or retrieval scores/ranks. If metadata is insufficient, they may inspect the exact pinned Skill using `./gasl get --id SOURCE_ID`; no Skill or supporting script may be installed or executed. Grades remain blank until human review.

## 6. Local artifacts

All review artifacts are under the Git-ignored `private/benchmark-review/` directory:

| File | Purpose | Sharing rule |
|---|---|---|
| `SEARCH-GOLD-V2-REVIEWER-A-PACKET.zip` | A's CSV + A-specific instructions | Give only to Reviewer A |
| `SEARCH-GOLD-V2-REVIEWER-B-PACKET.zip` | B's CSV + B-specific instructions | Give only to Reviewer B |
| `SEARCH-GOLD-V2-REVIEWER-A.csv` | A's 373-row review sheet | Reviewer A only |
| `SEARCH-GOLD-V2-REVIEWER-B.csv` | B's 373-row review sheet | Reviewer B only |
| `SEARCH-GOLD-V2-ADJUDICATION-TEMPLATE.csv` | Merge and adjudication template | Keep until both reviews return |
| `SEARCH-GOLD-V2-QUERY-MANIFEST.json` | Queries, source pins, and hidden pool provenance | **Do not share with reviewers** |
| `SEARCH-GOLD-V2-REVIEW-INSTRUCTIONS.md` | Common protocol | Internal reference |
| `SEARCH-GOLD-V2-REVIEWER-A-INSTRUCTIONS.md` | A-specific instructions | Reviewer A only |
| `SEARCH-GOLD-V2-REVIEWER-B-INSTRUCTIONS.md` | B-specific instructions | Reviewer B only |

The earlier ungraded drafts and pre-Twilio manifest were preserved with `PRE-TWILIO-SCOPE-2026-11-22` suffixes; the earlier query-level CSV draft was also retained as `SEARCH-GOLD-V2-QUERY-LEVEL-SUPERSEDED-2026-11-22.csv`.

The reviewer ZIPs were opened and integrity-tested. Neither ZIP contains the private manifest, adjudication template, or the other reviewer's CSV. Git ignore verification confirmed `private/` is excluded from Git.

## 7. Reproducibility fingerprints

- Source Catalog SHA-256: `af0617d13790d4bf13ba30c723b2107483898227e60cec99667db24cf39633d2`.
- Taxonomy SHA-256: `3c16e787ccc6ad0f481f69e3683330801d9ba745578ca9476d26c6f37116174f`.
- Private manifest SHA-256: `085d79ef1febf0845a59aaae555958414f0bcb09ae05dd1cd5211adfe38dda00`.
- Reviewer A CSV SHA-256: `a30882440c57f5e2ac3f1c66db741c40580beb22858af9492fd6fe09eb818e94`.
- Reviewer B CSV SHA-256: `7cdd3d692cca9cf0a62da07c943c1f3a1d42f59bdb6d175626aa8c5b2e59cacc`.
- Adjudication template SHA-256: `3e539e9b671de40034f7829f5c1db9fce47a5e2139038558dc457dd17d3f0671`.
- Reviewer A ZIP SHA-256: `c669c687f5eb57241e883d7592c3ee2b0958ccb6176e482c2a29eb37e783dc07`.
- Reviewer B ZIP SHA-256: `28e26e51c9c88c96a9bbd2980d5c76bcbbfc134ac1bf90482c3db2dff80025ef`.

## 8. Validation

- Exactly 26 unique query IDs and 13 complete English/Persian pairs.
- All 13 pairs have the same candidate Source ID set across language variants.
- All 373 candidate rows resolve to the current Source Catalog.
- Candidate commit and Git Blob SHAs match the Source Catalog exactly.
- Hidden provenance exists for every candidate; all pools contain exactly two random controls.
- Reviewer A and B candidate sets match, but row ordering differs.
- No retrieval score, rank, or pool-origin columns appear in reviewer CSVs.
- All grade, rationale, and adjudication cells are blank.
- ZIP integrity passes; reviewer packages do not leak the manifest or the other reviewer's file.
- `git check-ignore` confirms the review workspace is excluded from Git.
- `git diff --check` passes with only the previously observed CRLF-to-LF warnings on three existing CSVs.

## 9. Changes and non-actions

- Added this report under `docs/reports/`.
- Updated `docs/ROADMAP.md` to record the prepared review packet and pending human gate.
- Created / updated only local, Git-ignored review artifacts under `private/benchmark-review/`.
- No production code, search ranking, taxonomy, Source Catalog, Skill content, or original research data changed.
- No Commit, Push, staging, or destructive Git operation was performed.
- No relevance grade was generated by the model or inferred from retrieval rank.
- No benchmark metric was calculated from this candidate set.

## 10. Acceptance and next gate

**Preparation accepted:** The blind review packet is reproducible, source-pinned, reviewer-separated, and ready for independent annotation.

**Still blocked on human review:**

1. Give Reviewer A only `SEARCH-GOLD-V2-REVIEWER-A-PACKET.zip`.
2. Give Reviewer B only `SEARCH-GOLD-V2-REVIEWER-B-PACKET.zip`.
3. Receive both completed CSVs without merging them prematurely.
4. Validate grade values, source pins, additions, and missing rows.
5. Merge into the adjudication template and resolve disagreements.
6. Freeze a versioned qrels dataset and only then run the independent benchmark with Precision@5, Recall@5, MRR@10, and NDCG@5.
7. Preserve the existing 26-query / 148-judgment development benchmark separately.

Until steps 1–6 are complete, Search quality remains **unrated by an independent benchmark**. The existing provisional metrics must not be relabeled as independent results.
