# Global AI Skills Library (GASL)

**A public, local-first discovery and routing engine for AI Agent Skills, designed for community development.**

GASL indexes attributed Skill sources, searches them locally, ranks candidates for a task, and exposes the same core through an MCP server. It is designed to run on the user's own computer—not as a hosted SaaS.

- No GASL server to buy, rent, or maintain.
- No paid LLM API or API key required.
- No Docker or cloud account required for normal use.
- MCP uses local **STDIO**, so an Agent launches GASL directly.
- Search and indexing run locally with Python's standard library and SQLite FTS5.
- Full Skill instructions are retrieved on demand from the exact pinned upstream commit or the attributed public catalog. No separate private repository or hosted archive is required. Optional metadata enrichment fetches only pinned SKILL.md files into an ignored local cache.
- Third-party Skill instructions are treated as untrusted data. GASL does not install or execute them.

## Quick start — two commands

Python 3.10+ and Git are required.

~~~bash
git clone https://github.com/Mahdi-Soleimani/global-ai-skills-library.git && cd global-ai-skills-library && ./install.sh
~~~

~~~bash
./gasl mcp
~~~

The first command creates a local .venv and installs only the optional MCP SDK. The second starts the MCP server over STDIO. In an MCP client, configure the absolute path to the repository's gasl launcher; see [MCP_CONFIG.example.json](MCP_CONFIG.example.json).

### Use without MCP

The search CLI and local Explorer do not require the MCP dependency:

~~~bash
./gasl search --query "review a Python API for security issues"
./gasl route --task "audit a cloud configuration" --top-k 5
./gasl serve
~~~

The serve command opens the optional Explorer at http://127.0.0.1:8787. This is a process on your own computer, not a hosted service. It binds to localhost by default.

**Router answerability status:** `gasl route` and `gasl_route_task` now return `routing_decision: recommend | abstain | undetermined` using a transparent **experimental, uncalibrated lexical heuristic**. A `recommend` means *candidate worth inspecting*, never a quality/security/install approval. `abstain` means *insufficient matching evidence among retrieved candidates*, never proof of a corpus-wide absence. Candidate-level security and installation checks remain separate. See [Phase 15](docs/reports/PHASE-15-AUTONOMOUS-PROXY-EVALUATION-2026-11-22.md).

### Retrieve a selected Skill

Use the source record ID returned by search:

~~~bash
./gasl search --query "security audit" --json
./gasl get --id YOUR_SOURCE_RECORD_ID
./gasl download --id YOUR_SOURCE_RECORD_ID
./gasl download --id YOUR_SOURCE_RECORD_ID --execute
~~~

The first download command plans the complete package; the second retrieves verified regular files and applicable upstream notices to the ignored local catalog. It does not install or execute anything. Full-package download currently uses the macOS/Linux collector; Windows support remains to be tested. Root-level Skills and unsafe or oversized package layouts require separate handling.

For a previously downloaded, pinned Skill, repeat the **offline** integrity and static security scan without contacting upstream:

~~~bash
./gasl audit --id YOUR_SOURCE_RECORD_ID
~~~

`download --execute` now performs this local scan automatically after the verified package download. The audit checks that all files stay inside the selected package, rejects symlinks and unlisted files, verifies file size/SHA-256 and the original pinned `SKILL.md` Git Blob, and reports suspicious code patterns. Detailed evidence is written to the ignored `reports/security/on-demand/` directory. Even a scan with no visible flags remains **`no_obvious_static_flags_not_approved`**; installation/execution stay disabled. The audit never runs downloaded instructions, scripts, tests or dependencies. A real enforced sandbox and installation approval workflow are still separate pending tasks. See [Phase 17](docs/reports/PHASE-17-SELECTED-SKILL-OFFLINE-SECURITY-GATE-2026-11-22.md).

To inspect **sandbox readiness without running or pulling any container or Skill**, use:

~~~bash
./gasl sandbox
~~~

This command checks only Docker CLI/daemon availability and prints the required isolation controls. A working Docker daemon is **not** considered proof of an enforced isolation boundary: actual canary tests and explicit consent remain prerequisites for any future dynamic validation. On the development Mac, Docker CLI exists but the daemon was unreachable, so the gate correctly reports `blocked`. The static scanner now preserves informational test-harness findings without treating them as actionable security warnings; all packages still remain unapproved. See [Phase 18](docs/reports/PHASE-18-SECURITY-TRIAGE-AND-SANDBOX-READINESS-2026-11-22.md).

**Inert container isolation CI (Phase 19):** The separate [GASL sandbox canary workflow](.github/workflows/gasl-sandbox-canary.yml) builds a tiny self-authored static Go program in a `FROM scratch` Docker image **locally**, without downloading dependencies or executing downloaded Skill code. It uses a source-hash-labelled, immutable local Docker image ID and a restricted ephemeral Linux container to test network isolation, read-only mounts, an unprivileged identity, dropped capabilities, seccomp, memory/CPU/process limits, scratch-space limits, absent host secrets and symlink escapes. The Docker run uses `--network none`, `--read-only`, a read-only synthetic fixture and `--pull never`. Only this benign canary can be tested via `./gasl sandbox --verify-canary --image-id sha256:...` on Linux. A passing canary is **not** certification of arbitrary-code safety, and no real Skill installation/execution path is enabled. The regular `./gasl sandbox` status command remains non-executing. See [Phase 19](docs/reports/PHASE-19-EPHEMERAL-INERT-SANDBOX-CANARY-2026-11-22.md).

### Connect an MCP client

Example configuration (replace the path with the actual clone location):

~~~json
{
  "mcpServers": {
    "gasl": {
      "command": "/absolute/path/to/global-ai-skills-library/gasl",
      "args": ["mcp"]
    }
  }
}
~~~

The launcher automatically uses .venv after install.sh; no separate server process or remote endpoint is needed. See [the compatibility and installation report](docs/reports/HOST-COMPATIBILITY-AND-INTEGRITY-2026-11-20.md) for actual tested environments and unverified hosts.

- Claude Desktop, Cursor, and other clients with JSON MCP configuration: use [MCP_CONFIG.example.json](MCP_CONFIG.example.json).
- Codex: copy the section from [MCP_CONFIG.codex.example.toml](MCP_CONFIG.codex.example.toml) into ~/.codex/config.toml.

GASL is not an LLM and does not call a model API. Your existing Agent/LLM host remains responsible for reasoning; GASL provides local Skill discovery, provenance, and routing.

The MCP adapter currently exposes:

| Tool | Purpose |
|---|---|
| gasl_search_skills | Search by task, domain, license, and security status |
| gasl_get_skill_details | Inspect source, pinned commit, license, and evidence |
| gasl_get_skill_content | Fetch one SKILL.md on demand |
| gasl_route_task | Rank candidates for a task and Agent constraints |
| gasl_list_domains | List the domain taxonomy |
| gasl_health | Report catalog and capability status |

MCP is the primary Agent integration. The local REST API and Explorer are optional interfaces over the same core.

## Current catalog status — 2026-11-20

- Four independent research sources are maintained separately: EN-675, FA-234, AUX-FA-750PLUS, and AUX-FA-438.
- The original row-level CSV/JSON/XLSX databases for the primary EN-675 and FA-234 datasets remain unavailable. No missing records have been reconstructed.
- The live source universe contains 57 repositories, 4,478 observed SKILL.md paths, and 4,405 commit-pinned source records. These are repository/path records, not globally unique Skill totals.
- The public GitHub catalog contains nine version-pinned packages (119 files; 664,466 bytes). The separate 63-package local pilot is not copied wholesale into the public repository.
- The local SQLite FTS5 index covers all 4,405 attributed source records. It is generated on the user's computer and ignored by Git.
- Optional local metadata enrichment is incremental, defaults to 100 records per run, and is stored under ignored private/; it is never added to the public catalog automatically.
- Metadata completeness and provenance are separate evidence fields. Behavioral quality remains unrated until reproducible benchmarks exist.
- The router ranks by task relevance and reports query-term coverage plus matched/unmatched concept groups, so generic title matches do not silently outrank candidates matching the full request. Evidence and compatibility are shown separately; metadata completeness is not treated as Skill quality.
- No third-party Skill has been installed or executed by GASL.

The successful public catalog refresh is recorded in [GitHub Actions](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/44747234619), with resulting commit [83c1031](https://github.com/Mahdi-Soleimani/global-ai-skills-library/commit/83c103114540687c5ebb76d90318d623b12b65c2).

## Development and tests

~~~bash
./install.sh
./.venv/bin/python -m pip install -r requirements-dev.txt
./.venv/bin/python -m pytest -q
~~~

The core search, router, and local REST API use the Python standard library. MCP is an optional dependency. GitHub Actions uses temporary runners to refresh source metadata only; this is not a runtime dependency for users and does not require a separately purchased server.

### Search quality regression benchmark

Run the provisional Persian/English relevance set locally:

~~~bash
./gasl benchmark --k 5 --mrr-k 10
~~~

The benchmark reports Precision@5, Recall@5, MRR@10, and NDCG@5 overall and by language. A fresh install has less search evidence than an enriched local workspace; see [the comparison](docs/reports/SEARCH-BENCHMARK-2026-11-20.md). Its graded judgments are provisional; they must be independently reviewed before any public search-quality claim. Unjudged results count as non-relevant.

The answerability-aware benchmark schema `1.1.0` distinguishes `answerable`, `unanswerable`, and `uncertain` queries and supports no-answer precision/recall, false-abstention rate, and coverage. **Independently validated Gold metrics remain unavailable.** An additional automated proxy-review workflow (below) evaluates the curated V2 candidate set with deterministic source-text rubrics and reports proxy ranking metrics. These **weak labels are not human Gold data and must not be called independent accuracy estimates**. Router decisions use a separate heuristic, not a threshold fitted on the proxy data. See [the benchmark implementation](docs/reports/PHASE-12-REVIEWER-STRESS-2026-11-22/ANSWERABILITY-SCHEMA-1.1-IMPLEMENTATION.md), [Phase 13](docs/reports/PHASE-13-ROUTER-ANSWERABILITY-GATE-2026-11-22.md), and [Phase 15](docs/reports/PHASE-15-AUTONOMOUS-PROXY-EVALUATION-2026-11-22.md).

The local SQLite read paths explicitly close their connections. A regression test runs the search/index-reuse path with `ResourceWarning` treated as an error.

### Autonomous internal V2 evaluation (local/private)

On the enriched development workspace (requires the ignored `private/skill-metadata-cache.json` and V2 candidate manifest):

~~~bash
./gasl auto-review
./gasl route --task "Native Android Kotlin BroadcastReceiver bank SMS parser" --json
~~~

The first command evaluates all 385 pinned candidates using two conservative deterministic rubric variants, records discrepancies, and assesses 26 bilingual searches. It writes `private/benchmark-review/AUTOMATED-PROXY-EVALUATION-V1.json`, which is intentionally **Git-ignored**, not a published Gold Dataset. No LLM API, extra server, independent reviewer or Skill execution is required. On clean installs without the private review data, normal search/routing continues to work; the `auto-review` command is an optional development evaluation only. The router's provisional decisions operate without that private file.

### Independent V2 reviewer intake (local/private)

The 26-query / 385-candidate V2 human-review packet is kept under the Git-ignored `private/benchmark-review/` workspace. Distribute only `SEARCH-GOLD-V2-REVIEWER-A-PACKET-INTAKE-V2.zip` to Reviewer A and the corresponding B packet to Reviewer B. Never share the private query manifest, coverage audit, or adjudication templates with reviewers.

Validate the local packet before distribution:

~~~bash
python3 tools/benchmark_review.py audit
~~~

After both reviewers return their completed candidate, answerability, and independent-human attestation CSVs, validate the intake:

~~~bash
python3 tools/benchmark_review.py validate
~~~

If reviewers independently add out-of-pool candidates, create blinded grade-free addenda for the other reviewer with:

~~~bash
python3 tools/benchmark_review.py validate --create-addenda
~~~

The validator checks source pins, required grades/rationales, answerability evidence, distinct reviewer IDs, reviewer blindness, and candidate-set parity. Exit code `2` means the review is incomplete; exit code `1` means validation failed. It does not generate human judgments or freeze a Gold Dataset.

### Lightweight public search vocabulary

The public search index can use standardized technology/task terms extracted from the exact verified upstream frontmatter. The generated registry/search-features.json stores only vocabulary terms from the GASL taxonomy, source identity, and Git blob evidence, not the upstream description or instructions.

Daily GitHub Actions refreshes up to 200 missing entries; a changed commit does not cause re-download if the same repository/path still has the exact verified blob SHA. On a local installation, update the vocabulary index explicitly with:

~~~bash
./gasl features --limit 200 --workers 4
~~~

Normal search remains offline and requires no new Python dependency, model download, or paid API. This is concept-expanded lexical retrieval, not vector embeddings or semantic similarity. The current verified index covers 1,282 of 4,405 public records. Refresh saves intermediate progress every 25 completed requests and defers previously failed records behind unattempted source pins so a temporary failure cannot block catalog coverage. The incomplete development benchmark and mixed metrics are documented in [the pilot report](docs/reports/PHASE-8-SEARCH-FEATURES-2026-11-20.md).

### Optional semantic research prototype

A separate offline research script, tools/semantic_experiment.py, evaluates E5-small semantic candidate reranking and weighted reciprocal rank fusion against lexical retrieval. This is not enabled in the CLI/MCP search engine and does not install dependencies or download models. The exact pinned artifacts and checksum requirements are declared in the script. The benchmark showed a small hybrid improvement and approximately 741 MiB peak process RSS; see [the experiment report](docs/reports/PHASE-8-SEARCH-FEATURES-BATCH-02-03-2026-11-20.md). Full-catalog dense retrieval remains an open research item.

### Optional metadata enrichment

Metadata enrichment is not part of installation or normal search startup. It fetches the exact pinned SKILL.md files to improve local search metadata and stores only a compact metadata cache under the ignored private/ directory:

~~~bash
./gasl enrich                 # 100 records per run by default
./gasl enrich --limit 500     # choose a bounded batch
./gasl enrich --all           # explicitly process every remaining source record
~~~

The source catalog remains unchanged. New metadata reads and on-demand content are checked against the recorded Git blob SHA before use. Existing metadata caches created before this integrity gate are historical evidence, not retroactively blob-verified. No Skill code is executed, and the cache is never published automatically.

## Data and security rules

- Keep EN-675, FA-234, AUX-FA-750PLUS, and AUX-FA-438 independent. Repository overlap is a cross-reference, never a merge of source Skill records.
- Preserve original source records, upstream links, publisher identity, immutable commit pins, and available license evidence.
- All discovered Skill source records are indexed regardless of license. Selected pinned upstream content can be retrieved locally without a license-class filter, subject to access, integrity and technical safety checks and applicable terms. No bulk private archive is required.
- Public mirroring is a separate review operation, not part of daily refresh. The existing public packages are preserved; other Skills are available as attributed upstream references and on-demand retrieval.
- A public repository or attribution line alone does not grant redistribution rights.
- Download, static scan, manual review, install approval, installation, and execution are separate lifecycle states.
- Downloaded Skill content is untrusted. Never execute it on the host. Dynamic checks require a separately enforced sandbox.
- No Skill installation or execution is exposed by the current MCP tools.
- All implementation progress and phase evidence belong under docs/reports/.

## Repository layout

- config/: source, safety policy, and taxonomy metadata.
- datasets/: independent dataset status and recovery rules.
- research/: source manifests.
- reconciliation/: repository crosswalk and duplicate candidates.
- registry/source-catalog.json/.csv: attributed source index, including entries whose license does not permit public mirroring.
- registry/search-features.json: verified, attributed standardized search terms; no Skill instructions.
- registry/skill-evaluations.json: derived metadata/provenance/security evidence; behavioral quality remains unrated until benchmarks exist.
- public-catalog/: tracked copies of eligible packages with upstream attribution and license evidence.
- tools/: source collection, validation, evidence evaluation, search, routing, local API, and MCP adapters.
- web/: local Explorer UI.
- private/, catalog/, quarantine/, storage/, and root reports/: local-only data excluded from public Git.
- registry/gasl-search.sqlite3: generated local index, ignored by Git.
- docs/ROADMAP.md and docs/reports/: roadmap and phase acceptance evidence.

## Third-party content and licensing

GASL does not claim authorship or exclusive ownership of collected Skills. Every source record links to its upstream repository/path and preserves available license metadata. Public copies are restricted by the configured license/evidence policy and carry attribution and upstream notices. See [ATTRIBUTION.md](ATTRIBUTION.md), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and [the redistribution policy](docs/ATTRIBUTION-AND-REDISTRIBUTION-POLICY.md).

**Project license:** not selected yet. Until a project license is chosen and added, this repository's own code is publicly visible but is not granted an open-source license. Third-party package licenses remain independent.
