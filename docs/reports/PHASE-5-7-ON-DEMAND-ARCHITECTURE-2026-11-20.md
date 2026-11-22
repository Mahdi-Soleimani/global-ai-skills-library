# GASL — On-demand architecture (phases 5 and 7)

Date: 2026-11-20. Local main working tree; no commit or push.

## User decision and scope

No separate private repository, R2, or durable central archive. All license classes remain indexed and selectable, with upstream provenance and applicable access and license terms. Daily GitHub Actions refreshes metadata only; consumers retrieve exact pinned content on demand. Existing nine public mirrors and local research originals remain intact. No third-party package is run or installed.

## Implementation

- .github/workflows/gasl-refresh.yml: remove private-archive readiness condition, bulk package download and automatic republishing. Explicit staging of six generated metadata files only (queue, discovery state, source catalog JSON/CSV/summary, evidence evaluation) plus discovery summary.
- tools/build_source_catalog.py: --public-only excludes local package registry and local historical snapshot, retaining tracked discovery state and existing public index.
- tools/on_demand.py and tools/gasl.py: selected ID-based get (verified SKILL.md) and download (plan by default, explicit --execute for selected complete package). Reuse existing tree/blob verification, size bounds and atomic ingestion. No license allowlist at download time.
- tools/queue_ingest.py: optional local download manifest path; user-triggered downloads record inventory in ignored private/on-demand-manifest.json rather than modifying the tracked download manifest.
- config/policy.json: version 0.3.0, private_archive_required=false, source_metadata_only refresh.
- Updated README, roadmap, attribution policy and corrected the prior archive requirement.

## Evidence

- 143 passed, 6 subtests passed.
- YAML parsed, no private archive variable or queue ingestion in scheduled workflow.
- Temporary public-input build: 4,405 source records, 9 mirrored packages, 0 private package records; index build and live local search successful.
- Local source catalog currently contains 4,429 records, including additional local revisions; no private records were published by this test.
- Mocked unknown-license package: plan without writing contents, download both regular files with correct blob hashes, preserve source and license metadata, resume without repeated content fetch, no tracked manifest change, no installation/execution.
- Unpinned source rejected before network. Public-only builder excludes private metadata and local historical observations.
- Actual pinned upstream SKILL.md fetch for GASL-SRC-7da38ea6a24d9e9fa3e7 failed with TLS handshake timeout; complete-package live run not reached. No TLS bypass or network setting change.
- Previous successful live refresh and package pilot are not evidence that the revised workflow ran on GitHub.
- Git diff --check passes (existing CRLF normalization warnings).

## Remaining acceptance

Run revised Actions after reviewed publication; retest live upstream access; add Windows-compatible collector, root-level/exception-package handling and package-level Agent adapter. Improve fresh-install search evidence and complete security/behavioral evaluation and host compatibility in subsequent phases. No claims of global completeness or redistribution permission from attribution alone.
