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

**Inert container isolation CI (Phase 19):** The separate [GASL sandbox canary workflow](.github/workflows/gasl-sandbox-canary.yml) builds a tiny self-authored static Go program in a `FROM scratch` Docker image **locally**, without downloading dependencies or executing downloaded Skill code. It uses a source-hash-labelled, immutable local Docker image ID and a restricted ephemeral Linux container to test network isolation, read-only mounts, an unprivileged identity, dropped capabilities, seccomp, memory/CPU/process limits, scratch-space limits, absent host secrets and symlink escapes. The Docker run uses `--network none`, `--read-only`, a read-only synthetic fixture and `--pull never`. Only this benign canary can be tested via `./gasl sandbox --verify-canary --image-id sha256:...` on Linux. The ephemeral Linux [canary run 45046458532](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45046458532) passed all **18** actual isolation checks. A passing canary is **not** certification of arbitrary-code safety, and no real Skill installation/execution path is enabled. The regular `./gasl sandbox` status command remains non-executing. See [Phase 19](docs/reports/PHASE-19-EPHEMERAL-INERT-SANDBOX-CANARY-2026-11-22.md).

### Phase 20: Preview a pinned Skill installation and simulate rollback (no actual install)

Plan a specific already indexed Skill against an explicit **logical** Agent and scope, fully offline:

~~~bash
./gasl install-plan --id GASL-SRC-ce593c8b9b3fd34f44d6 --agent codex --scope project
~~~

The output includes a deterministic SHA-256 `plan_id`, exact source commit and `SKILL.md` Git Blob, license caveats, locally rechecked source/package integrity (when downloaded), static-security warnings, unverified host compatibility, conceptual backup/rollback requirements and the state `actual_install_enabled: false`. This command does not contact the network, run a Skill, create a simulation ledger or modify Agent configuration. Supported **preview labels** are `codex`, `cursor`, `claude-code`, `claude-desktop`, `generic-mcp`; these are *not working installer adapters or verified host compatibility claims*.

To test only the simulated approval/state transitions, use the `plan_id` returned by the previous command (and an already downloaded, integrity-clean, no-actionable-flags package):

~~~bash
./gasl install-simulate --action apply --id GASL-SRC-ce593c8b9b3fd34f44d6 \
  --agent codex --scope project --plan-id PLAN_SHA256 --acknowledge-plan-id PLAN_SHA256
./gasl install-status --plan-id PLAN_SHA256
./gasl install-simulate --action rollback --plan-id PLAN_SHA256 \
  --acknowledge-plan-id PLAN_SHA256
~~~

`apply` and `rollback` here **only append local simulation events**, not copy, link, install, uninstall or execute any Skill. The exact plan-ID acknowledgement is for **simulation only** and does not constitute permission for real installation. All events are stored in a private, Git-ignored transactional SQLite ledger with a SHA-256 integrity chain at `private/install-simulation/events.sqlite3`; they can be read with `install-status`. The simulated rollback does **not** restore any actual Agent files because none were changed. An unknown license or unconfirmed Agent remains explicitly warned about, and no actual installation is permitted. See [Phase 20](docs/reports/PHASE-20-INSTALL-LIFECYCLE-SIMULATION-2026-11-22.md).


### Phase 21: Verified documentation, isolated Host Adapter rehearsals (no real installation)

The Host Adapter matrix distinguishes **Codex**, **Cursor**, **Claude Code**, **Claude Desktop**, and **generic MCP** instead of inventing one universal Skill installation path:

~~~bash
./gasl host-adapters
./gasl host-rehearsal --agent codex --scope project --scenario upgrade
./gasl host-rehearsal --agent cursor --scope user --scenario conflict
./gasl host-rehearsal --agent claude-code --scope project --scenario symlink
./gasl host-rehearsal --agent claude-desktop --scope user
~~~

Documented local directory conventions: Codex `.agents/skills/`, Cursor `.cursor/skills/`, Claude Code `.claude/skills/` (each with project/user scopes). **Claude Desktop (Chat account) instead uploads a Skill ZIP through Customize > Skills**, not by writing `.claude/skills/`; generic MCP has no universal file-based Skill install destination. These layouts are derived from the vendors' current documentation, **not** an actual live Host integration test.

The rehearsal creates its own short-lived, clearly marked `gasl-host-fixture-*` directory in the OS temporary folder and writes **only GASL-authored inert fixture bytes**. It tests a fresh Skill, a backed-up fixture upgrade and restoration, existing-file conflict protection, and symlink refusal, then deletes the temporary fixture. No user Home, project files, Agent configuration, real Skill code, network endpoint or account is touched. The output is a **fixture-only validation**, not permission to install, enable or execute any real downloaded Skill. See [Phase 21](docs/reports/PHASE-21-HOST-ADAPTER-FIXTURE-REHEARSAL-2026-11-22.md).

### Phase 22: Host capability check and interrupted transaction recovery (fixture only)

Discover which Host CLI programs are visible, **without launching them, reading their user profiles or exposing executable paths**:

~~~bash
./gasl host-probe
~~~

An available binary is **not** evidence that it recognizes a Skill. On the development Mac, none of `codex`, `cursor` or `claude` was visible on `PATH` during this phase; real Host discovery remains unverified. For Claude Desktop and generic MCP there is no universal CLI-based local Skill install probe.

Safely rehearse an interrupted *fixture-only* Skill upgrade, with an independent backup, an inert file, recovery and verification:

~~~bash
./gasl host-transaction-rehearsal --agent cursor --scope project \
  --kind upgrade --interrupt-after new_activated
~~~

Accepted agents: `codex`, `cursor`, `claude-code`; scopes: `project`, `user`; `--kind`: `fresh` or `upgrade`; interruption checkpoints: `prepared`, `old_backed_up`, `new_activated`. The tool uses **only its own temporary GASL-owned inert directories**, never reads or modifies the user's actual Agent configuration or downloads/executes a Skill. It refuses to overwrite a modified post-upgrade file or damaged backup. Tests emulate interruption boundaries; they are **not** a power-failure guarantee. A dedicated lightweight GitHub Actions workflow verifies the same behavior on an ephemeral Linux runner. See [Phase 22](docs/reports/PHASE-22-HOST-PROBE-AND-INERT-TRANSACTION-RECOVERY-2026-11-22.md).

### Phase 23: Real Codex discovery through an isolated App Server

Codex [officially supports the `skills/list` App Server JSON-RPC method](https://learn.chatgpt.com/docs/app-server) to list discovered Skills. GASL now tests that capability against a **real, version-pinned Codex CLI**, installed **only in the temporary directory of an ephemeral Ubuntu GitHub Actions runner**. The test starts Codex App Server with a freshly created, empty `HOME`, `CODEX_HOME` and XDG configuration directory, sends only `initialize` and `skills/list`, and requires the exact path and enabled state of one inert `gasl-discovery-probe/SKILL.md`. It does not start a thread, send a prompt, require authentication, run any Skill code, or install anything in the developer's actual Host profile.

~~~bash
# For disposable CI/test profiles only, never your normal user-agent profile:
python3 tools/codex_discovery_probe.py --codex-bin /ABSOLUTE/PATH/TO/CODEX/CLI
~~~

The isolated [live Codex CI run 45055665888](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45055665888) **passed**, confirming the real `@openai/codex@0.162.1` CLI discovered the exact inert fixture via `skills/list`. The script rejects unknown or ambiguous Skill paths and incomplete protocol responses, removes temporary files, and prints a **sanitized JSON result** with no executable locations, user directories or tokens. Real Codex discovery applies **only to the tested inert fixture in that runner**; it is not blanket Agent compatibility or authorization to install GASL packages. Cursor and Claude Code remain documented fixture adapters, with real Host discovery still unverified. See [Phase 23](docs/reports/PHASE-23-REAL-CODEX-DISCOVERY-2026-11-22.md).

### Phase 24: Cursor ACP and Claude Code readiness without authentication

Cursor Agent CLI [supports ACP](https://cursor.com/docs/cli/acp), which can be initialized without requesting an authenticated Session. Claude Code CLI supports an ordinary `--version` check without starting a model. GASL tests these independent, narrow capabilities with the vendors' **actual CLI binaries in disposable Linux CI environments**:

~~~bash
# Only in a disposable test profile with a trusted, local executable:
python3 tools/other_host_protocol_probe.py --host cursor --binary /ABSOLUTE/PATH/TO/agent
python3 tools/other_host_protocol_probe.py --host claude-code --binary /ABSOLUTE/PATH/TO/claude
~~~

The probe creates an empty temporary `HOME` and XDG directories, strips inherited API keys and identity-related environment variables, and never opens a Session, sends a Prompt, logs in, writes to real Agent directories, or runs any Skill. **Cursor ACP initialize and Claude Code `--version` are readiness checks, not real Skill discovery.** Both real Host readiness jobs [passed in GitHub Actions run 45057489934](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45057489934), while both explicitly retained `skill_discovery_verified=false`. The [dedicated GitHub Actions workflow](.github/workflows/gasl-other-host-readiness.yml) retrieves official CLI distributions only inside ephemeral Ubuntu runners and validates the isolated responses. Neither an available binary nor a ready protocol unlocks GASL production installation. See [Phase 24](docs/reports/PHASE-24-OTHER-HOST-READINESS-2026-11-22.md).

### Phase 25: Prepare a verified, private Skill ZIP for review (never install)

For an already downloaded, exact-pinned Skill, GASL can create a **private ZIP** containing only its verified package inventory (including the original LICENSE/NOTICE files where available). First inspect the read-only plan, then explicitly acknowledge its SHA-256 ID to prepare a local bundle:

~~~bash
./gasl install-plan --id GASL-SRC-ce593c8b9b3fd34f44d6 --agent codex --scope project
./gasl install-bundle --id GASL-SRC-ce593c8b9b3fd34f44d6 --agent codex \
  --scope project --acknowledge-plan-id YOUR_EXACT_PLAN_ID
./gasl install-bundle --verify-plan-id YOUR_EXACT_PLAN_ID
~~~

The ZIP and a separate audit JSON live **only** in ignored `private/install-bundles/`. GASL rechecks the downloaded file manifest, `SKILL.md` Git Blob, individual SHA-256 values and static-scan status, then verifies the ZIP itself. The output records missing historical non-main Git Blob evidence and unknown licenses rather than claiming that all upstream files have been fully verified. Unsafe, flagged, missing, symlinked, additional or changed files stop packaging. Existing bundles are not silently overwritten. Only the code and synthetic tests are published; **the actual ZIP and third-party source files are not pushed to GitHub**. **Bundle creation is not permission to install or execute anything**, and neither Codex/Cursor/Claude Code configuration nor Claude Desktop account is accessed. For manual inspection only, not automatic importing. See [Phase 25](docs/reports/PHASE-25-PRIVATE-SKILL-BUNDLE-PREPARATION-2026-11-22.md).

### Phase 26: Install and rollback a private ZIP in a disposable test profile

GASL now goes beyond event-only simulation: it can **physically extract** the Phase-25 verified ZIP into a newly created, temporary Codex, Cursor or Claude Code **fixture profile**, checkpoint a replace/upgrade, then restore the exact prior version. No actual Agent application is started, and the real user/project Skill directories are never accessed. Use the precise `plan_id` from the previously created private ZIP:

~~~bash
./gasl bundle-fixture --plan-id YOUR_EXACT_PLAN_ID \
  --acknowledge-plan-id YOUR_EXACT_PLAN_ID --agent codex --scope project \
  --scenario upgrade --stop-after activated
~~~

`--scenario` supports `fresh`, `upgrade` and `conflict`; `--stop-after` supports `staged`, `backed_up` and `activated`. The trial uses the actual private ZIP bytes, but creates a unique `gasl-host-fixture-*` profile, validates every ZIP file, stages it under that profile, atomically renames a prior **fixture-only** version into a backup, and verifies rollback. A modification to either the active files, backup or even a newly added empty directory blocks automatic removal. CLI exit artifacts contain no third-party Skill text. The private ZIP, detailed local cache and user Agent directories remain untouched.

**This is not a real user-profile installer.** It neither runs a Skill nor enables automatic import or execution. The verified Codex discovery test and Cursor/Claude CLI readiness do not lift any of these restrictions. See [Phase 26](docs/reports/PHASE-26-PRIVATE-BUNDLE-FIXTURE-INSTALL-ROLLBACK-2026-11-22.md).

### Phase 27: Read-only, exact Host destination preflight (not installation authorization)

GASL can now inspect a **caller-selected, existing root** before any future real Skill installation. It resolves only the Host's documented relative Skill directory, refuses symlink/file-based escapes and case-only folder collisions, checks the exact pinned private ZIP, and distinguishes a missing Skill from an existing Skill with a full SHA-256 inventory. It does **not** install, authorize, execute, create a backup, launch an Agent or write to that directory.

~~~bash
# Only after explicitly choosing a project root (never auto-discovered):
./gasl target-preflight --plan-id YOUR_EXACT_PLAN_ID --agent codex \
  --scope project --selected-root /ABSOLUTE/SELECTED/PROJECT

# Optional second read: refuse if the ZIP or selected Skill's files changed:
./gasl target-preflight --plan-id YOUR_EXACT_PLAN_ID --agent codex \
  --scope project --selected-root /ABSOLUTE/SELECTED/PROJECT \
  --expect-state-binding-id PRIOR_STATE_BINDING_ID
~~~

The output includes `relative_target`, `prior_target_state`, source ZIP SHA-256 and a deterministic `state_binding_id` that binds the **selected exact target path and existing content inventory** to the pinned Host/Scope/ZIP identity. It does not display the actual root path, existing filenames or Skill contents. For an already existing target, its bytes are **read locally for hashing only**, never copied into reports, uploads or public Git. This state binding is **not** an installation permission, a user consent receipt or a trusted signature; it must be recomputed at any future install boundary. Missing license or Host compatibility evidence remains explicitly warned about. Claude Desktop and generic MCP have no filesystem preflight adapter.

The dedicated [target-preflight CI](.github/workflows/gasl-target-preflight.yml) uses only synthetic ZIPs and disposable roots, **not the developer's real Agent profiles**. See [Phase 27](docs/reports/PHASE-27-READ-ONLY-TARGET-PREFLIGHT-2026-11-22.md).

### Phase 28: Exact fixture-only approval, process locking and interrupted ZIP rollback

GASL can rehearse a **state-bound approval challenge**, POSIX `flock`-protected transaction, fsynced staging, and independently resumed recovery on a **freshly generated disposable Host test profile**. It uses the real Phase-25 *private* ZIP bytes, but **never writes to any real Agent profile**, installs a production Skill, invokes a model, or executes Skill code.

~~~bash
./gasl locked-bundle-fixture --plan-id YOUR_EXACT_PLAN_ID \
  --acknowledge-plan-id YOUR_EXACT_PLAN_ID --agent codex --scope project \
  --action replace --checkpoint backed_up \
  --acknowledge-fixture-only GASL_DISPOSABLE_FIXTURE_ONLY
~~~

`--action` is `install` (absent target) or `replace` (existing **inert fixture**); checkpoints are `staged`, `backed_up` and `activated`. The challenge binds the private ZIP SHA-256, exact Plan ID, Host, Scope, **temporary target identity**, existing-target fingerprint, and requested action. A changed target or ZIP causes rejection. A persistent lock inode and nonblocking POSIX advisory `flock` serialize cooperating fixture transactions; file and directory `fsync` barriers accompany the staged content and renames. Recovering in a **new process** after an intentional interruption rechecks both current files and versioned backup before restoring them; any conflicting edits are preserved instead of overwritten. On platforms without POSIX locking, the transaction fails closed. The only allowed writes are inside a GASL-marked temporary directory that is removed afterward.

**This is a test-only workflow:** the preview's digest and the `GASL_DISPOSABLE_FIXTURE_ONLY` acknowledgment are **not real user-install permission or an authentication mechanism**, nor do they enable real Host installation. Advisory file locking does not block non-cooperating software; deliberate checkpoint tests do not prove sudden power-loss durability. See [Phase 28](docs/reports/PHASE-28-LOCKED-FIXTURE-CONSENT-AND-RECOVERY-2026-11-22.md).

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
