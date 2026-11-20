# Global AI Skills Library (GASL)

A local-first, provenance-aware library for discovering, collecting, validating, indexing, evaluating, and selectively installing AI Agent Skills.

## Verified status — 2026-11-20

- Four independent research sources are maintained separately: `EN-675`, `FA-234`, `AUX-FA-750PLUS`, and `AUX-FA-438`. Their original report texts are archived locally and SHA-256 verified.
- The original row-level CSV/JSON/XLSX databases for the primary EN-675 and FA-234 datasets remain unavailable. No missing records have been reconstructed.
- The four source manifests contain 87 repository mentions and 56 distinct references; the current verification snapshot records 55 canonical GitHub repositories and 4,214 observed `SKILL.md` paths (not deduplicated).
- Local collection pilot: 60 packages, 623 files, 13,518,797 bytes across four repositories. The registry classifies these as 56 Skill candidates and four evaluation fixtures.
- Security status: 10 packages require manual review (nine Skill candidates and one fixture); two high-confidence static signals remain in the review ledger.
- No downloaded third-party code has been executed. No Skill is approved or installed.
- Project tests: `python3 -m pytest -q` — 14 passed.

Counts from research reports are reported claims, not verified global-unique Skill totals. Repository `SKILL.md` path counts are not unique-skill counts.

## Non-negotiable data and security rules

- Keep EN-675, FA-234, AUX-FA-750PLUS, and AUX-FA-438 independent. Repository overlap is a cross-reference, never a join or merge of source Skill records.
- Never delete, translate, normalize, or rewrite original source records. Preserve original report files byte-for-byte and verify their hashes.
- Never infer missing CSV/JSON/XLSX rows from a research report or an embedded sample.
- Download, static scan, manual review, install approval, installation, and execution are separate lifecycle states.
- Pin source commits and verify SHA-256. Unknown license means local review only; no public redistribution.
- Downloaded Skill content is untrusted. Never execute it on the host. Dynamic checks require a separately enforced sandbox; otherwise record the blocker.
- All implementation progress and phase evidence belong under `docs/reports/`.

## Quick start

```bash
python3 -m pytest -q
python3 tools/gasl.py summary
python3 tools/gasl.py verify --limit 3 --trees
python3 tools/collector.py download --repo openai/codex-security  # dry-run by default
python3 tools/static_scan.py
python3 tools/build_registry.py
```

Python 3.9+; standard library only. Docker is not required. Collection needs network access to the GitHub API and raw file endpoints. The downloader is dry-run by default; `--execute` is required to download. Evaluation fixtures under `evals/.../fixtures/` are excluded unless `--include-test-fixtures` is supplied.

## Repository layout

- `config/`: source and safety policy metadata. Account-scoped file IDs are kept only in the local ignored `private/` directory.
- `datasets/`: independent dataset status and recovery rules.
- `research/`: four independent source manifests.
- `reconciliation/`: repository cross-reference only; no source-record merge.
- `registry/download-manifest.json`: pinned local collection provenance; no third-party Skill contents.
- `tools/`: source verifier, collector, static scanner, registry builder, and CLI.
- `tests/`: project regression tests.
- `docs/ROADMAP.md`: current authoritative roadmap.
- `docs/reports/`: phase reports and acceptance evidence.
- `private/`, `catalog/`, `quarantine/`, `storage/`, and root `reports/`: local-only content excluded from public Git.

## Third-party content and licensing

The public repository does not include downloaded third-party Skill packages or original Deep Research source reports. Those remain local-only until their redistribution rights are independently verified. Repository metadata and source links do not imply permission to republish Skill content.

**Project license:** not selected yet. No open-source license is granted by this repository at this time.
