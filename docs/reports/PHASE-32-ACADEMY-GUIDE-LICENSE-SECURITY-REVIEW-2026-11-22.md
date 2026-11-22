# Phase 32 — First real Skill: license and static security review

**Date:** 2026-11-22  
**Candidate:** `academy-guide`  
**Source:** [`anthropics/skills`](https://github.com/anthropics/skills), pinned commit `e4bb5d960d87126ff3b3a8af1a104b7db67560ba`, path `skills/academy-guide/`  
**Target under consideration:** Codex user scope inside a separately isolated HOME only. No existing user profile is eligible for this review.

## 1. Immutable source and bundle integrity

| Item | Evidence |
|---|---|
| GASL Source Record | `GASL-SRC-ce593c8b9b3fd34f44d6` |
| Private Plan ID | `f52f11b345714191c780bd63b6e18e1d05a9f2ed3257c3b791a9e2fa00e45fcb` |
| Upstream commit | `e4bb5d960d87126ff3b3a8af1a104b7db67560ba` |
| `SKILL.md` Git blob | `cefeaeb20cc29a803af0335d7c7155b066d8770f` |
| `SKILL.md` SHA-256 | `f27992510c051355dfe68c92394d509af730da5298094ec86834ee40bbd31376` |
| `LICENSE.txt` Git blob | `4f881c52d1f72f4cfb720e339e2d35c3058d01a9` |
| `LICENSE.txt` SHA-256 | `bc6b3af2f331cbc7fb0da1344efb2cbe5877a31498b4d70dbc7000f3405a1362` |
| Private ZIP SHA-256 | `b3d75ac2bbe5d73dd32274806a6b41ee721a991106bc486e6209b4557a99701e` |
| ZIP contents | Exactly `academy-guide/SKILL.md` and `academy-guide/LICENSE.txt`; 7,497 compressed bytes, 19,100 uncompressed bytes |

Both upstream Git blob IDs were fetched at the exact pinned commit and independently matched against the local downloaded file bytes. The private ZIP's SHA-256 and entry hashes match its sidecar. No source content was executed.

Upstream file references: [SKILL.md at pinned commit](https://github.com/anthropics/skills/blob/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/skills/academy-guide/SKILL.md), [LICENSE.txt at pinned commit](https://github.com/anthropics/skills/blob/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/skills/academy-guide/LICENSE.txt), [repository README at pinned commit](https://github.com/anthropics/skills/blob/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/README.md).

## 2. License review

**Per-skill license evidence identifies Apache License 2.0 (`Apache-2.0`).** `LICENSE.txt` includes the complete Apache 2.0 terms and the notice `Copyright 2026 Anthropic, PBC.` The upstream repository README describes many of its skills as Apache 2.0, and this individual skill folder includes its own complete license file. The repository-level metadata had `license_spdx=null`; that missing metadata was a discovery limitation, not evidence that the individual skill is unlicensed. This review records the per-skill file as stronger, path-specific evidence; it does not rewrite the public source catalog automatically.

Practical redistribution conditions to preserve:

- Include a copy of the Apache 2.0 license with redistributed copies.
- Retain applicable copyright, patent, trademark and attribution notices.
- Mark modified files prominently as changed.
- Do not imply that the license grants rights to use Anthropic trademarks.
- Preserve any applicable upstream NOTICE/attribution material.

The repository also has a root [`THIRD_PARTY_NOTICES.md`](https://github.com/anthropics/skills/blob/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/THIRD_PARTY_NOTICES.md). It lists imageio, imageio-ffmpeg, FFmpeg, Pillow and font components; it does not name `academy-guide`, and the selected Skill package contains no code, images, fonts or those dependencies. The file is outside the selected Skill folder. This is recorded as a repository-level notice to preserve/consider if redistributing a wider repository snapshot; it is not silently treated as a dependency of this two-file Skill.

This is a technical license identification and obligation summary, not legal advice.

## 3. Security and behavior review

The exact pinned package was audited using `gasl audit --id GASL-SRC-ce593c8b9b3fd34f44d6`:

- `integrity_ok=true`; pinned main Git blob verified.
- `security_status=no_obvious_static_flags_not_approved`.
- **0 total findings, 0 actionable findings, 0 high-confidence signals**.
- No scripts, executable files, shell commands, subprocess calls, package dependencies, MCP server configuration or bundled binaries are present. The package contains only Markdown instructions and the license text.
- No prompt-injection pattern was detected by the scanner. Manual inspection found no instruction to reveal secrets, override system instructions, access local credentials or modify files.
- The Skill is narrowly about questions on Claude/Claude products and learning how to use AI. It tells the Agent to answer first, recommend Academy material only on a strong learning-intent match, and avoid invented links or course titles.
- It asks the Agent to fetch one public JSON catalog at `https://academy.claude.com/assets/data/catalog.json` when a strong recommendation is warranted. This is the only material network behavior identified; it is a bounded read of the named Academy domain, not a shell or arbitrary code action.
- It is an Anthropic/Claude-oriented Skill. Codex format discovery is technically supported, but upstream does not declare Codex compatibility. The Phase-31 Codex user-scope test used a GASL-authored inert Skill, **not this third-party candidate**.

A zero-finding static scan is not a security approval and does not prove the behavior of a future model invocation.

## 4. Decision and remaining approval

<status>REVIEWED — CANDIDATE FOR ISOLATED TEST ONLY</status>

- License: identified as Apache-2.0 from the exact per-skill license file.
- Integrity: verified against the pinned commit and private ZIP.
- Static scan: zero findings; no code payload.
- Behavioral/network review: one documented read-only Academy catalog fetch; scope is Claude-learning recommendations.
- Codex compatibility: not declared upstream; must be confirmed by the real Codex user-scope test using this exact package.
- **User approval to install this exact third-party Skill has not been collected.**
- Installation, model invocation and Skill execution remain disabled. No file in the actual Codex home or `~/.agents/skills` has been modified.

Next controlled operation, only after explicit approval: install this exact Plan ID into a dedicated, separately marked Codex HOME profile, verify `skills/list` sees the exact pinned `academy-guide` path, then remove the isolated profile or preserve it only if separately requested. Do not write to the user's normal Codex home. Do not start a model turn or execute the Skill during the initial compatibility check.
