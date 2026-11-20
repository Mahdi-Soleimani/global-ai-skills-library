# GASL — Attribution, source catalog, and public mirroring policy

## Product intent

GASL is a comprehensive index of discovered AI agent skills. A source is not excluded from the catalog merely because its license is unknown, restrictive, or missing. The catalog is an attributed directory of third-party works, not a claim that GASL authored or owns them.

## Source record requirements

Each source record should preserve, where available:

- Skill name/path and original repository URL.
- Direct source URL, pinned to a commit when live verification is available.
- Repository owner/publisher. This field must not be described as the individual author unless independently supported.
- Repository-level SPDX identifier/name and link to applicable license evidence.
- Commit SHA, tree SHA, and SKILL.md blob SHA.
- Discovery timestamp, research lead, package/content status, and security status.
- ownership=third_party, original_author=null unless evidenced, and gasl_claims_exclusive_ownership=false.

Legacy path snapshots without a commit remain visible but are explicitly marked unpinned until refreshed.

## License and redistribution handling

The source index contains every discovered path irrespective of license. Repository-level GitHub license metadata is a signal, not a per-file legal determination.

Public content mirroring is a separate operation. The current automation requires:

1. A recognized SPDX identifier from config/policy.json.
2. The applicable LICENSE/COPYING/NOTICE evidence from the source repository, pinned to the same commit, bundled with the package.
3. A complete package inventory and successful Git blob/SHA-256 integrity verification.
4. The original files and notices to remain unchanged.
5. A generated ATTRIBUTION.md and ATTRIBUTION.json with source repository, original path, exact commit, license, and ownership disclaimer.

Missing, NOASSERTION, proprietary, custom, or non-allowlisted licenses remain in registry/source-catalog.json with their original links. Their contents are not automatically mirrored into the public GitHub repository. Attribution alone is not treated as permission to redistribute.

The allowlist is an automation gate, not a legal opinion. Repository-level license metadata may not capture per-file exceptions, additional third-party assets, or all downstream obligations. Every public package records this limitation. License expressions or terms that do not exactly match the allowlist remain reference-only pending review.

## GitHub Actions automation

.github/workflows/gasl-refresh.yml runs daily and on manual dispatch:

1. Runs the regression suite.
2. Refreshes all configured source repositories through the GitHub API.
3. Pins each successful snapshot to commit/tree/blob identifiers.
4. Builds the complete metadata-only source catalog and CSV.
5. Downloads a bounded batch only when the public-mirror license/evidence gate passes.
6. Runs static integrity/security heuristics without executing any downloaded content.
7. Preserves historical registry metadata on ephemeral runners.
8. Builds the public catalog and attribution files.
9. Commits and pushes changed metadata and eligible packages to main.

The workflow uses GITHUB_TOKEN with contents: write. It does not require the user's Mac to remain online. GitHub Actions runners are ephemeral; therefore only the tracked metadata and public-catalog/ survive between runs. Private persistent storage is outside the scope of this workflow; only eligible public packages and source metadata are persisted by this pipeline.

## Explicit non-goals

- No claim of exclusive ownership or authorship over upstream skills.
- No inference that a repository owner wrote every skill in the repository.
- No merging or rewriting of the four independent Deep Research datasets.
- No automatic installation or execution.
- No public content mirror solely because a repository is public or because an attribution link is present.
