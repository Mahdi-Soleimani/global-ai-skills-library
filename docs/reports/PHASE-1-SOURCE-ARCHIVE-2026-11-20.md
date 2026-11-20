# Phase 1 — Source archive and provenance lock

- Date: 2026-11-20
- Scope: EN-675, FA-234, AUX-FA-750PLUS, AUX-FA-438
- Mode: source-preserving archive and metadata validation; no record-level merge

## Result

All four original report texts are now present in the local private archive. Each file was verified against the SHA-256 and byte-size values in the source manifest. The archive files remain separate and byte-for-byte unchanged.

| Source ID | Local archive | Bytes | SHA-256 | Result |
|---|---|---:|---|---|
| EN-675 | `private/research-originals/EN-675/deep-research-report.md` | 19,370 | `9b82cd727af15ce14421894db8479424a31f6c1709928343c5b5b067e5f3fa6d` | PASS |
| FA-234 | `private/research-originals/FA-234/deep-research-report.md` | 12,820 | `d25087595baa6c51f20fc202cbea3baca5ae10535a8d8231b6d6022ab4e5d79d` | PASS |
| AUX-FA-750PLUS | `private/research-originals/AUX-FA-750PLUS/deep-research-report.md` | 187,648 | `9f96e22bd75987580a75949226b7634ba9b1ae8ae7ff076071eb2b782652982a` | PASS |
| AUX-FA-438 | `private/research-originals/AUX-FA-438/deep-research-report.md` | 151,329 | `74110309cc4cccbda2706759b702366e34cb5a677b5d1c43107d1d049309e134` | PASS |

## Metadata and privacy changes

- Added `local_archive_status=sha256_verified` and verification timestamp to the four source manifests and source registry metadata.
- Preserved the original pre-sanitization config and source manifests under the ignored local-only `private/provenance-originals/` directory.
- Moved account-scoped Library file identifiers into `private/source-library-references.json`; removed those identifiers from the public config and four public source manifests.
- Removed future generation of `source_library_file_id` from `tools/gasl.py` bootstrap output.
- No source report content, embedded sample rows, or dataset record was edited.

## Verified inventory

`python3 tools/gasl.py summary` reports 87 repository mentions, 56 distinct repository references, 25 cross-referenced references, 56 live-verified references, and 55 canonical repositories. These are repository-level relationships only.

The primary row-level CSV/JSON/XLSX databases for EN-675 and FA-234 remain unavailable. The claimed 675 and 234 counts have not been reconstructed. The 45- and 40-row supplemental examples remain supplemental and independent.

## Tests

- `python3 -m pytest -q`: 14 tests expected after the source-privacy regression tests are included.
- `python3 tools/gasl.py summary`: PASS.
- Four source archive SHA-256 and byte-size checks: PASS.
- Public metadata scan for account-scoped file IDs and machine-specific absolute paths: PASS.

## Acceptance

- Four independent source report archives: PASS.
- Four hashes and sizes match source manifests: PASS.
- Public source manifests no longer expose account-scoped Library IDs: PASS.
- Primary row-level databases recovered: NOT DONE; original files remain missing.
- Source datasets merged or rewritten: NO.

## Remaining work

Proceed to repository crosswalk and duplicate-candidate analysis. Do not merge or delete any record; use evidence-backed relationships only.
