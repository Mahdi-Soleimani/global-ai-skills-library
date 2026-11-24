# Phase 67 — Standalone documentation link integrity

## Baseline and defect
Read-only audit of private archive for 8b0b2048ceb21f96f5623f2c81368b3a8ef5322c found 53 distinct absent local link destinations in README and one in docs/ROADMAP.md. Other shipped Markdown files had no missing relative destinations. All 54 occurrences at distinct document/destination scope referred to reports or workflow definitions present in the committed public source tree but not included in the intentionally narrow runtime ZIP. This is a documentation defect, not an executable runtime failure.

## Correction
README.md and docs/ROADMAP.md: replace only absent relative targets with GitHub blob URLs pinned to the verified prior commit. Every target checked against that exact commit with git cat-file. Preserve links to included files, historical text and package allowlist. Add explicit standalone-vs-source-checkout instructions and note that historical links require network access. No external URL fetched, no report/private data added to ZIP. tests/release_package_smoke.py: check simple inline relative Markdown targets within the verified extracted package before runtime checks; reject missing or escaping destinations, report count; same-page anchors and external URLs intentionally not checked. tests/test_release_draft.py: positive local link, external/anchor skip, missing and escaping destination regression. .github/workflows/gasl-release-draft.yml: trigger on the shipped Markdown paths on push and PR as well as existing test/runtime changes. No production code or security controls changed.

## Acceptance
New regression passed via exact CI-style unittest invocation; complete focused suite and standalone package smoke to be recorded after execution. No claim of general Markdown parser, external reachability, arbitrary-code execution safety, new real Host compatibility, or public release permission.
