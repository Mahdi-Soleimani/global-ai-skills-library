# Contributing

GASL is developed as a local-first project. Normal use must not depend on a maintainer-hosted server, paid API, Docker, or cloud account.

## Local setup

Python 3.10+ and Git are required.

~~~bash
git clone https://github.com/Mahdi-Soleimani/global-ai-skills-library.git
cd global-ai-skills-library
./install.sh
~~~

Run the MCP server locally:

~~~bash
./gasl mcp
~~~

Run tests:

~~~bash
./install.sh
./.venv/bin/python -m pip install -r requirements-dev.txt
./.venv/bin/python -m pytest -q
~~~

## Data and safety rules

1. Preserve all four source datasets independently: EN-675, FA-234, AUX-FA-750PLUS, and AUX-FA-438.
2. Do not delete, merge, translate, or rewrite original source records. Use cross-reference records for overlap.
3. Do not add downloaded third-party Skill content without verified redistribution rights and required attribution.
4. Do not execute downloaded Skill code on the host.
5. Never commit private research originals, local-only Skill packages, caches, secrets, tokens, model weights, or security evidence.
6. Keep source repository, source path, immutable commit, publisher, license evidence, and content hash attached to every source record.
7. Run the full test suite before submitting a pull request.
8. Record implementation details, tests, limitations, and acceptance evidence under docs/reports/.

## Pull requests

- Keep changes focused and explain the user-visible or architectural effect.
- Add regression tests for changed behavior.
- Do not represent static scan results as security approval or metadata completeness as Skill quality.
- Do not change the public redistribution allowlist without license evidence and review.
- The pull request CI workflow must pass.
