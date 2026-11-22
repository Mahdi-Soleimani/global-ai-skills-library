# Phase 25 — Private, version-pinned Skill ZIP preparation and audit

**Date:** 2026-11-22  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Scope:** Prepare a usable **offline review artifact**, without real installation, execution, account login, host directory changes or publication of downloaded third-party Skill contents.

## 1. User-facing goal

The GASL catalog could already discover, download, hash, statically inspect, preview and simulate installation decisions. However, the application did not yet produce a portable, verifiable file for reviewing one pinned Skill prior to installation. Phase 25 bridges this gap with a **locally private ZIP** containing the original downloaded Skill files plus a separate, local JSON audit manifest.

### CLI

```bash
# Read-only: obtain a deterministic source + destination plan ID
./gasl install-plan --id GASL-SRC-ce593c8b9b3fd34f44d6 --agent codex --scope project

# Explicit local bundle preparation ONLY (not install authorization)
./gasl install-bundle --id GASL-SRC-ce593c8b9b3fd34f44d6 \
  --agent codex --scope project --acknowledge-plan-id YOUR_EXACT_PLAN_ID

# Verify ZIP and sidecar hashes again, without extraction
./gasl install-bundle --verify-plan-id YOUR_EXACT_PLAN_ID
```

Supported manual review labels: `codex`, `cursor`, `claude-code`, `claude-desktop`. Generic MCP is intentionally excluded since it has no universal filesystem Skill installation format. The command does **not** place the bundle in any live Agent profile and does **not** upload it to Claude Desktop.

## 2. Technical implementation

- Added `tools/install_bundle.py`: reconstructs the install plan from the current pinned source ID; requires **exact `plan_id` acknowledgement** before writing anything. A missing, damaged or actionable-statically-flagged local package is rejected.
- Revalidates original source metadata (`repository`, `source_skill_path`, full commit SHA, main `SKILL.md` Git Blob) and compares every local file's **size and recorded SHA-256**. Where Git Blob SHA is present in the package manifest, that is checked too. The original main SKILL.md always has to match the immutable Git Blob SHA in the source catalog. Paths must be normalized, safe, unique and within the package. Extra files, path traversal, symlinks, file/directory collisions and oversized archives are disallowed. No Skill text or scripts are executed.
- Supports **historical downloaded manifests** lacking `package_relative_path` or per-file `git_blob_sha`: derives the relative path from an explicitly validated package-local `local_path`, keeps SHA-256 and main Git Blob checks, and **records the missing Git Blob evidence count** in both return JSON and the sidecar. This does not claim that every historical non-main file was proven against upstream Git history.
- ZIP contains **only original, unchanged Skill content**, under a sanitized folder name, e.g. `academy-guide/SKILL.md` plus any applicable `LICENSE.txt`, `NOTICE`, or other captured files. No `source.json`, application credentials, private audit ledger or artificial code is included. ZIP entries have fixed timestamps, fixed regular-file mode and deterministic compression settings for repeatability.
- ZIP and a separate JSON evidence file are written under the local Git-ignored `private/install-bundles/` directory, with restricted parent permissions on POSIX. The evidence JSON includes the pinned source identity, original license status, warnings, individual file hashes, whole-archive SHA-256 and explicit `manual_review_required=true`, `host_installation_approved=false`, `production_installation_enabled=false`.
- Creation uses a temporary file plus an exclusive, same-filesystem hard link to ensure that an unexpected existing ZIP is **not overwritten**. Existing bundle paths and sidecars block a second creation until reviewed; the verification command reads but never extracts the ZIP. This is local integrity checking, **not a signed or tamper-proof external provenance attestation**.
- Added `./gasl install-bundle` CLI; existing discovery/search/API/MCP and real installation restrictions remain unchanged.

## 3. Actual Mac end-to-end check with a pinned downloaded package

Used local `GASL-SRC-ce593c8b9b3fd34f44d6` (`academy-guide`), already present in the ignored local catalog. No package was downloaded anew, and its third-party content was **not** copied into public Git.

| Observation | Actual result |
|---|---|
| `install-plan` | Existing downloaded package `downloaded_verified`, zero actionable static flags |
| Exact Plan ID | `f52f11b345714191c780bd63b6e18e1d05a9f2ed3257c3b791a9e2fa00e45fcb` |
| ZIP creation | `private_review_bundle_created` |
| Actual ZIP files | `academy-guide/SKILL.md`, `academy-guide/LICENSE.txt` |
| ZIP bytes | 7,497 |
| Zip integrity check | `private_bundle_integrity_verified` |
| License | Source catalog SPDX was unknown (`null`); review warning preserved |
| Historical Git Blob evidence | 2 legacy manifest entries lack per-file Blob SHA; accurately recorded as unverified against upstream Blob evidence |
| User/Agent files touched | **0** |
| Third-party Skill executed | **0** |
| Production installer enabled / auto upload | **false / false** |
| Git status of generated ZIP and audit JSON | **ignored/private; not staged for GitHub** |

A previous initial live-package attempt correctly failed rather than bypassing missing fields in a legacy metadata manifest. The compatibility path was implemented with additional unit coverage, without removing existing file hash or pin requirements.

## 4. Regression tests and dedicated CI

- Added `tests/test_install_bundle.py` with **19** independent test methods covering ZIP correctness, deterministic bytes, mandatory exact acknowledgement, missing/changed/unlisted files, symlinks, unknown license, legacy manifest evidence, ZIP tampering, sidecar changes, repeated output collision, non-ASCII names, blocked generic MCP and flagged content.
- Full project suite: **326 tests and 91 subtests PASS**, `compileall` and `git diff --check` PASS.
- Added `.github/workflows/gasl-private-install-bundle.yml`: disposable Linux CI, no persisted Git credentials, **synthetic test packages only**, asserts no real user catalog or private bundle output is written into the repository checkout.
- No private ZIP, original Skill file, local download Manifest, account token or session metadata may be committed or uploaded as a CI artifact. Verify the live CI run after publishing this phase before claiming remote CI success.

## 5. Known limitations and next steps

1. **Not approved for installation:** ZIP creation or a static-scan PASS does not prove behavioral safety, license permissions, reliability, or Agent compatibility. The downloaded Skill remains untrusted code/instructions. A consumer must manually review the license and contents before any import. A successful Codex inert discovery test is not automatic approval of arbitrary GASL Skills.
2. **Host integration:** no file was installed into Codex, Cursor or Claude Code; Claude Desktop ZIP upload is a separate manual account action. Real Agent install/uninstall remains disabled. The app must later implement an explicit user-consent transaction with version/target binding, backups and rollback on real disposable Host profiles.
3. **Legacy package provenance:** for old manifests missing Git Blob SHA on non-main files, the archive verifies the previously recorded SHA-256, not a newly fetched upstream Git Blob. Missing evidence is surfaced rather than guessed.
4. **Artifact security:** ZIP + JSON is not cryptographically signed; local users with filesystem write access can rewrite both. Do not treat it as an externally verified trusted release.
5. **Copyright/redistribution:** the ZIP is locally private and contains the original upstream license evidence where available. This phase does not publish, mirror or redistribute third-party Skill source code on GitHub.

**Acceptance: successful private pinned ZIP creation and verification on a real local package, with explicit limitations and no actual Host/Agent modifications.**

## 6. Observed GitHub Actions acceptance and public source verification

- Source implementation commit [`124bbe4`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/124bbe44fd324427f1ab50afa082830fbfb85cf6) was pushed normally (non-force) to `main`; staged content review covered **exactly 7 public code/test/workflow/documentation paths**, with **zero secret, private path, personal email or telephone matches**.
- Clean archive/export of the commit without `.git`, `private/`, `catalog/`, `storage/`, or `reports/` passed the complete **326-test and 91-subtest** suite, Python byte-compilation, CLI option smoke and search-index checks. The clean checkout contained **no third-party bundle contents**.
- Dedicated [GitHub Actions run `45058488535`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45058488535) completed **SUCCESS** on ephemeral Ubuntu: checkout without preserved credentials, code compilation, synthetic pinned ZIP checks and an explicit assertion that no repository-local private bundle or catalog was created.
- The downloaded real `academy-guide` bundle remains **only on the development Mac** inside Git-ignored `private/install-bundles/`, with its accompanying evidence JSON. No binary ZIP, external Skill instructions or original license text was committed to public GitHub.
- The separate standard source-catalog refresh job may advance remote `main` independently of this feature; any subsequent synchronization must use a normal fast-forward or non-destructive merge, not a forced update.

**Acceptance after live CI: PASS for archive preparation and integrity checks; NOT a Host-side installation approval or third-party safety certification.**
