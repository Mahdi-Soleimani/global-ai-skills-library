# Phase 70 — Repository presentation, discovery and community documentation

## Scope
Owner requested a professional, searchable public repository with concise English, Persian and Simplified Chinese presentation, usage instructions, images and GitHub conventions. The previous development-oriented README is preserved in immutable revision 9e49dd49afe18e6299f858fe9103419d294564ab, linked as historical reference; technical reports, datasets, source attribution, security evidence and project history are not deleted. No false authorship, quality ratings, popularity claims or compatibility claims added.

## Implementation
- Root README reduced from 841+ lines to approximately 100 lines; equivalent README.fa.md and README.zh-CN.md with language switch links, snapshot date/count, features, Windows/POSIX quickstart, MCP configuration, retrieval, safety and documentation.
- docs/assets/social-preview.png: original 1280x640 project cover, 40,172 bytes; docs/assets/architecture.svg: original accessible diagram; docs/assets/explorer.png: actual 1440x1100 local Explorer screenshot, 193,979 bytes. A temporary headless Chrome profile opened the actual loopback UI and submitted Python API security audit; displayed ten results. No real user browser profile was used, no Skill executed. Chrome temporary directory cleanup reported a transient nonempty-directory error after capture; PNG independently verified.
- Added CODE_OF_CONDUCT.md, CITATION.cff, bug and feature issue templates, pull request template. Existing LICENSE, CONTRIBUTING and SECURITY policies retained.
- Root roadmap records owner decision: behavioral quality evaluation optional, not a catalog or MVP acceptance requirement.
- Added exact presentation-file allowlist to private draft packager, CI path triggers and targeted regression to ensure the three languages and images travel with the package while arbitrary docs/assets are excluded. Private-only/public-release gates remain unchanged.
- GitHub REST API verified description and 19 relevant topics. Repository visibility unchanged. Social preview image exists in repository; GitHub Settings social preview requires a separate UI upload and is not implied by committing the file.

## Verification
Three language files checked for local destinations; both PNG images decoded and dimensions verified, SVG XML parsed. Local CI-style unit suite passed 34 tests, canonical golden digest unchanged. No dependency installation or runtime feature change. Public source repository remains MIT for GASL-owned code; public standalone ZIP still gated. Search-engine ranking and indexing not measured or guaranteed.
