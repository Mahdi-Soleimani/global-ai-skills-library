# Global AI Skills Library (GASL)

A local-first, provenance-aware library for discovering, collecting, validating, indexing, evaluating, and selectively installing AI Agent Skills.

## Verified status — 2026-11-20

- Four independent research sources are maintained separately: `EN-675`, `FA-234`, `AUX-FA-750PLUS`, and `AUX-FA-438`. Their original report texts are archived locally and SHA-256 verified.
- The original row-level CSV/JSON/XLSX databases for the primary EN-675 and FA-234 datasets remain unavailable. No missing records have been reconstructed.
- The four source manifests contain 87 repository mentions and 56 historical repository references. The live source universe now has 57 repositories, 4,478 observed SKILL.md paths, and 4,405 valid Skill-path records.
- Local-only collection pilot: 63 packages, 640 files, 13,583,889 bytes across seven repositories (59 Skill candidates and four evaluation fixtures). Separately, the public GitHub catalog now contains nine version-pinned packages (119 files; 664,466 bytes).
- Security status: the local-only 63-package pilot has 10 packages requiring manual review and two high-confidence static signals. The nine public-mirror packages have one manual-review flag and zero high-confidence signals; none has been installed or executed.
- No downloaded third-party code has been executed. No Skill is approved or installed.
- The live attributed source index contains 4,405 records across 57 repositories; all 4,405 records are commit-pinned. These are repository/path records, not globally unique skills.
- Project tests: python3 -m pytest -q — 57 passed.

Counts from research reports are reported claims, not verified global-unique Skill totals. Repository `SKILL.md` path counts are not unique-skill counts.

GitHub Actions has verified all 57 repositories with zero errors, refreshed the complete source index, and committed it. The successful run mirrored nine eligible packages with upstream license evidence and attribution. [View successful run](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/44747234619); resulting commit: [83c1031](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/83c103114540687c5ebb76d90318d623b12b65c2).

The pinned download manifest now contains 71 package records (757 files; 14,229,883 bytes). Nine packages are mirrored publicly; the earlier 63-package local pilot is not copied wholesale into the public repository.

Attribution and automation are live: every discovered source path is indexed regardless of license; public package content is mirrored only when the configured SPDX/evidence gate passes. Every mirrored package has ATTRIBUTION.md and ATTRIBUTION.json. See ATTRIBUTION.md and docs/ATTRIBUTION-AND-REDISTRIBUTION-POLICY.md.

## Non-negotiable data and security rules

- Keep EN-675, FA-234, AUX-FA-750PLUS, and AUX-FA-438 independent. Repository overlap is a cross-reference, never a join or merge of source Skill records.
- Never delete, translate, normalize, or rewrite original source records. Preserve original report files byte-for-byte and verify their hashes.
- Never infer missing CSV/JSON/XLSX rows from a research report or an embedded sample.
- Download, static scan, manual review, install approval, installation, and execution are separate lifecycle states.
- Preserve third-party ownership, source links, publisher identity, license metadata, and immutable source pins. Unknown or non-allowlisted licenses remain in the source index; their content is not automatically mirrored publicly.
- Downloaded Skill content is untrusted. Never execute it on the host. Dynamic checks require a separately enforced sandbox; otherwise record the blocker.
- All implementation progress and phase evidence belong under `docs/reports/`.

## Quick start

```bash
python3 -m pytest -q
python3 tools/gasl.py summary
python3 tools/gasl.py verify --limit 3 --trees
python3 tools/collector.py download --repo openai/codex-security  # dry-run by default
python3 tools.gasl.py reconcile  # requires local verification and skill registry snapshots
python3 tools.discover.py --limit 100 --refresh --retry-errors
python3 tools.queue_ingest.py --repo microsoft/skills --per-repo 1 --public-redistributable-only --execute
python3 tools.static_scan.py
python3 tools/build_registry.py
python3 tools/build_public_catalog.py
python3 tools/build_source_catalog.py
```

Python 3.9+; standard library only. Docker is not required. Collection needs network access to the GitHub API and raw file endpoints. The downloader is dry-run by default; `--execute` is required to download. Evaluation fixtures under `evals/.../fixtures/` are excluded unless `--include-test-fixtures` is supplied.

## Repository layout

- `config/`: source and safety policy metadata. Account-scoped file IDs are kept only in the local ignored `private/` directory.
- `datasets/`: independent dataset status and recovery rules.
- `research/`: four independent source manifests.
- `reconciliation/`: repository crosswalk and historical path/registry reconciliation; no source-record merge. Detailed third-party path and duplicate evidence is local-only.
- `registry/source-catalog.json/.csv`: complete attributed source index for every discovered skill path, including unknown/restricted license entries.
- `registry/download-manifest.json`: pinned local collection provenance.
- `public-catalog/`: tracked public copies of eligible packages, each with upstream attribution and license evidence.
- `tools/`: source verifier, collector, static scanner, registry builder, and CLI.
- `tests/`: project regression tests.
- `docs/ROADMAP.md`: current authoritative roadmap.
- `docs/reports/`: phase reports and acceptance evidence.
- `private/`, `catalog/`, `quarantine/`, `storage/`, and root `reports/`: local-only content excluded from public Git.

## Third-party content and licensing

GASL does not claim authorship or exclusive ownership of collected skills. Every source record links to its upstream repository/path and preserves available license metadata. A repository public visibility or an attribution line alone does not grant redistribution rights. Unknown, proprietary, or non-allowlisted sources remain fully represented in the source index, while their content is not automatically copied into the public repository. Every mirrored package carries its own attribution and upstream license/notice evidence. See `ATTRIBUTION.md`.

**Project license:** not selected yet. No open-source license is granted by this repository at this time.
