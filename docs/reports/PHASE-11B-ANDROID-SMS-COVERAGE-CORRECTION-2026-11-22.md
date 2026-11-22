# Phase 11B — Android Banking SMS Coverage-Gap Correction

> **Intake revision notice — 2026-11-22:** The original reviewer sheets and ZIPs described in this report are historical preparation artifacts. They are superseded for distribution by the `INTAKE-V2` sheets and `*-PACKET-INTAKE-V2.zip` files created in [Phase 14](PHASE-14-HUMAN-REVIEW-INTAKE-2026-11-22.md). The new intake adds explicit out-of-pool evidence fields and independent-human attestations. Do not distribute the older ZIPs. The hashes below document the original Phase 11B packet version; current artifact hashes are recorded in the Phase 14 checksum manifest.

**Date:** 2026-11-22  
**Status:** Corrected V2 reviewer packets prepared; awaiting independent human relevance and answerability review  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Branch:** `main` (no commit or push performed)

## 1. Why this correction was required

The first V2 preparation incorrectly replaced the Android device-side banking-SMS task with a Twilio inbound-webhook task because Twilio Skills appeared in the search results. This changed the user's intended task to fit the corpus and invalidated the benchmark scenario. That was an evaluation-design error.

The active benchmark has now restored the Android task. The previous Twilio-based manifest, reviewer sheets, instructions, and ZIPs were preserved with the suffix `PRE-ANDROID-RESTORE-2026-11-22`; they are historical only and must not be distributed to reviewers.

## 2. Restored task

**English:** Build a native Android Kotlin feature that receives incoming banking SMS messages with BroadcastReceiver and extracts transaction details from sender and message body

**Persian:** پیاده‌سازی گیرنده پیامک بانکی در اندروید با Kotlin و BroadcastReceiver؛ دریافت سرشماره و متن کامل پیامک و استخراج اطلاعات تراکنش بدون parser اختصاصی برای هر بانک

This task is specifically about receiving SMS on the Android device using Kotlin / `BroadcastReceiver`, capturing the sender and message body, and extracting transaction details. It is not about sending SMS through a provider or receiving a provider webhook.

## 3. Corpus coverage audit

The audit examined the current local index and pinned source records:

| Scope | Count |
|---|---:|
| Source Catalog records | 4,429 |
| Commit-pinned eligible records | 4,405 |
| Search Feature records | 4,404 |
| Android/SMS-related metadata matches | 12 |
| Pinned Skill bodies fetched and Git-Blob verified | 12 / 12 |
| Bodies containing direct Android SMS receiver implementation terms | 0 |

### 3.1 All Android/SMS-related metadata matches

| Source ID | Skill | Repository | Source path |
|---|---|---|---|
| `GASL-SRC-2ae7a298ae49f2e66d66` | google-mobile-ads-android-migrate-to-next-gen | google/skills | `skills/ads/google-mobile-ads-android-migrate-to-next-gen/SKILL.md` |
| `GASL-SRC-32eecc208e009ab3cdb0` | twilio-sms-send-message | openai/plugins | `plugins/twilio-developer-kit/skills/twilio-sms-send-message/SKILL.md` |
| `GASL-SRC-3f47ea3f9e9d80d79de9` | android-emulator-qa | openai/plugins | `plugins/test-android-apps/skills/android-emulator-qa/SKILL.md` |
| `GASL-SRC-73d54300483e40990e51` | azure-communication-sms-java | microsoft/skills | `.github/plugins/azure-sdk-java/skills/azure-communication-sms-java/SKILL.md` |
| `GASL-SRC-7b5b80d80031f1edb82d` | android | openai/plugins | `plugins/zoom/skills/meeting-sdk/android/SKILL.md` |
| `GASL-SRC-9768b792a5b5f96921aa` | android | openai/plugins | `plugins/zoom/skills/virtual-agent/android/SKILL.md` |
| `GASL-SRC-98d2de0a37ebae330d18` | android | openai/plugins | `plugins/zoom/skills/contact-center/android/SKILL.md` |
| `GASL-SRC-b3fa1ac686a3c898f7eb` | android-performance | openai/plugins | `plugins/test-android-apps/skills/android-performance/SKILL.md` |
| `GASL-SRC-b8db6c7cd3cdb8b1ccc1` | isms-audit-expert | alirezarezvani/claude-skills | `ra-qm-team/skills/isms-audit-expert/SKILL.md` |
| `GASL-SRC-ca7f0a8fed5e6615e996` | android | openai/plugins | `plugins/zoom/skills/video-sdk/android/SKILL.md` |
| `GASL-SRC-cae694fd17a8e179e8f7` | twilio-sms-isv-setup | openai/plugins | `plugins/twilio-developer-kit/skills/twilio-sms-isv-setup/SKILL.md` |
| `GASL-SRC-d800504cd191e3e122dd` | sms | coreyhaines31/marketingskills | `skills/sms/SKILL.md` |

All 12 eligible Skill bodies in this metadata-matched set were retrieved from their exact pinned commits and their Git Blob hashes verified. None contained direct implementation terms such as `BroadcastReceiver`, `SMS_RECEIVED`, `SmsRetriever`, `Telephony`, `READ_SMS`, or `RECEIVE_SMS`. One Twilio send-message Skill mentions inbound SMS only by pointing to a separate Twilio webhook Skill; that is provider-side messaging, not Android device reception.

The extracted Search Feature vocabulary was also checked for `android`, `broadcast`, `receiver`, `telephony`, `sms`, `inbox`, `banking`, `message`, `kotlin`, `phone`, and `notification`. The exact indexed-term count for each of these terms was zero. This reflects the current extracted feature vocabulary; it is not a claim that every Skill body was downloaded.

### 3.2 Leading search results expose a ranking failure signal

For the restored English query, the current GASL search returned:

| Rank | Skill | Repository | Relevance score | Query coverage |
|---:|---|---|---:|---:|
| 1 | twilio-messaging-webhooks | openai/plugins | 15.43 | 0.353 |
| 2 | incoming-request-advisor | deanpeters/Product-Manager-Skills | 11.67 | 0.353 |
| 3 | incoming-request-advisor | deanpeters/Product-Manager-Skills | 11.67 | 0.353 |
| 4 | twilio-sms-send-message | openai/plugins | 15.45 | 0.294 |
| 5 | twilio-whatsapp-send-message | openai/plugins | 12.44 | 0.294 |
| 6 | expo-brownfield | expo/skills | 11.64 | 0.294 |
| 7 | twilio-marketing-promotions-advisor | openai/plugins | 9.43 | 0.294 |
| 8 | azure-servicebus-ts | microsoft/skills | 9.43 | 0.294 |
| 9 | conventional-commit | github/awesome-copilot | 7.22 | 0.294 |
| 10 | commit | getsentry/skills | 7.22 | 0.294 |

The top-ranked result, `twilio-messaging-webhooks`, was separately fetched from its pinned commit and inspected. Its body describes a server-side Twilio POST webhook and TwiML responses. It does not implement Android `BroadcastReceiver` or local SMS reception. The leading Expo brownfield candidate is about embedding React Native into a native app; `mobile-release` concerns release readiness and permission declarations. These are adjacent or false-positive candidates, not direct matches.

**Interpretation:** There is strong evidence of an Android device-side SMS coverage gap in the current indexed corpus and a clear retrieval false-positive signal. This is not yet a final gold `no_relevant_skill_found` label: the full body of every one of the 4,404 feature-bearing Skills was not downloaded and exhaustively searched. Independent reviewers must search outside the pooled candidates and confirm answerability.

## 4. Corrected benchmark candidate set

- **26** queries: 13 English and 13 Persian.
- **13** bilingual task pairs across **10** domains.
- **385** pair-level Source ID candidates; each reviewer receives 385 rows.
- The Android banking-SMS pair has **38** candidates and explicitly includes all 12 Android/SMS-related metadata matches, in addition to normal retrieval candidates and random controls.
- The two language variants share relevance labels only after reviewers confirm that they are semantically equivalent.
- Every candidate is pinned to a Source Catalog record and includes the exact commit SHA and Git Blob SHA.
- The candidate pool is not exhaustive; reviewers may append missing relevant Source IDs.

## 5. Separate answerability assessment

Each reviewer also receives a separate **13-row answerability sheet**. For each task pair, the reviewer must choose one of:

- `direct_match_found`
- `partial_match_only`
- `no_relevant_skill_found`
- `uncertain`

A `no_relevant_skill_found` label is allowed only when the reviewer documents a full-catalog review, uses multiple query formulations/synonym groups, records the search method, and explains why no relevant Source ID exists. Absence from the pooled candidate list alone is insufficient.

The Android case is recorded internally as `strong_coverage_gap_signal_pending_independent_human_confirmation`. That hypothesis is intentionally not shown in the reviewer packets.

## 6. Blind-review packet separation

Active packets:

- `SEARCH-GOLD-V2-REVIEWER-A-PACKET.zip`
- `SEARCH-GOLD-V2-REVIEWER-B-PACKET.zip`

Each ZIP contains only that reviewer's candidate CSV, answerability CSV, and reviewer-specific instructions. It excludes the private manifest, coverage audit, adjudication template, and the other reviewer's files. The two candidate orders and answerability row orders are independently randomized.

The adjudication template contains **385** rows and blank fields for both reviewers plus the final adjudicated grade. No grade or answerability value has been generated or prefilled.

## 7. Important benchmark-runner limitation

The current `tools/search_benchmark.py` is designed for the existing provisional positive-qrels regression set. Its loader requires every query to have a non-empty `relevant` dictionary. It does not model expected answerability or an explicit abstain decision. Therefore an unanswerable query cannot yet be evaluated correctly: a zero-relevant qrels set is rejected, and simply treating every result as irrelevant would conflate correct abstention with retrieval failure.

After human review and adjudication, add a separately tested answerability/abstention layer:

1. Support an explicit query-level expected answerability label.
2. Allow empty qrels only when adjudicated as no relevant Skill found.
3. Obtain an explicit system prediction (`abstain` versus `recommend`) from the router; do not infer it from a threshold selected for this one query.
4. Report no-answer precision/recall, false-abstention rate, and answerable-query coverage separately from Precision@K / Recall@K / MRR / NDCG.
5. Calibrate any abstention threshold only on a sufficiently large reviewed set, not on this single gap case.

No search ranking or abstention threshold was changed in this correction.

## 8. Validation results

- 26 unique query IDs, 13 complete English/Persian pairs, 10 domains.
- Active manifest contains `android-banking-sms`; it does not contain `twilio-inbound-sms`.
- Android pool contains 38 candidates and all 12 metadata-audit records.
- All 12 metadata-matched Skill bodies were retrieved from pinned commits and Git-Blob verified; zero had direct Android SMS receiver implementation terms.
- The leading Twilio webhook, Expo brownfield, and mobile-release result bodies were also retrieved from pinned commits and verified.
- 385 candidate rows in each reviewer sheet; candidate sets match, row order differs.
- 13 answerability rows in each reviewer sheet; all fields remain blank.
- 385 adjudication rows; all reviewer and adjudication grade fields remain blank.
- All candidate Source IDs resolve to the current Source Catalog; commit SHA and Git Blob SHA match exactly.
- Exactly two deterministic random controls per pair are recorded in the private provenance manifest.
- ZIP integrity passes; neither packet leaks the other reviewer, private manifest, coverage audit, or adjudication template.
- Git ignore verification confirms the review workspace remains local/private.
- No commit, push, staging, or production ranking change was performed.

## 9. Reproducibility fingerprints

- Source Catalog SHA-256: `af0617d13790d4bf13ba30c723b2107483898227e60cec99667db24cf39633d2`
- Taxonomy SHA-256: `3c16e787ccc6ad0f481f69e3683330801d9ba745578ca9476d26c6f37116174f`

| Artifact | SHA-256 |
|---|---|
| `SEARCH-GOLD-V2-QUERY-MANIFEST.json` | `324ec246e644f54d0551c079c5db1bb94b88a857553a2ad06345933fb3453121` |
| `SEARCH-GOLD-V2-ANDROID-SMS-COVERAGE-AUDIT.json` | `4721de1546c235ff5cca6cdf861b7a6458c5e30659361e3a93708d9e3160b8d5` |
| `SEARCH-GOLD-V2-REVIEWER-A.csv` | `ad3436d30d03f328cf5de1bcb864ec6f7f02b06df6be437b4eb8e06e56ec0618` |
| `SEARCH-GOLD-V2-REVIEWER-B.csv` | `c776a8b53587e6c99d620bd0489dd027c793615b453335e11d537335f35cda8e` |
| `SEARCH-GOLD-V2-ANSWERABILITY-REVIEWER-A.csv` | `4033b5ce67b024c78a376fb796c7c4cc0fa8f80c0268929e3d0b28b69a37a07a` |
| `SEARCH-GOLD-V2-ANSWERABILITY-REVIEWER-B.csv` | `41e86e194f929528ae8fa536021c7fa6ac6e59e4f7f0b7bd5fec04dec6c39ab3` |
| `SEARCH-GOLD-V2-ADJUDICATION-TEMPLATE.csv` | `7ed697ef5bbe49b396d9eedbcb02ae97b8140f2235b0b38e048b031c40eb6e27` |
| `SEARCH-GOLD-V2-REVIEWER-A-PACKET.zip` | `b86b678459a021e8b13f53b4e849354dddb488ae7e041be616e5eec4bfbd0607` |
| `SEARCH-GOLD-V2-REVIEWER-B-PACKET.zip` | `98a6c2d43b3b5b30f9cd0c664399cfed1c3ca8099a9b294ab903ef627d4ebc3b` |

## 10. Next gate

1. Give Reviewer A only `SEARCH-GOLD-V2-REVIEWER-A-PACKET.zip`.
2. Give Reviewer B only `SEARCH-GOLD-V2-REVIEWER-B-PACKET.zip`.
3. Receive both independent candidate grades and answerability sheets.
4. Validate source pins, language equivalence, out-of-pool additions, and catalog-search evidence.
5. Adjudicate disagreements and freeze versioned qrels plus query answerability labels.
6. Extend and test the benchmark runner for empty qrels and abstention metrics.
7. Only then run the independent benchmark and compare retrieval quality and coverage-gap detection.

Until then, the Android task is a **coverage-gap hypothesis**, not a final gold no-answer label, and the independent benchmark remains pending human review.
