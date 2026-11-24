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

Python 3.10+ is required; Git is needed for a checkout and Git-based maintenance, not for running the standalone private package. The Bash examples below are for macOS/Linux.

~~~bash
git clone https://github.com/Mahdi-Soleimani/global-ai-skills-library.git && cd global-ai-skills-library && ./install.sh
~~~

~~~bash
./gasl mcp
~~~

The first command creates a local .venv and installs only the optional pinned MCP SDK and its dependencies. The second starts the MCP server over STDIO. Setup and launch use isolated Python mode, exclude system site-packages, and do not modify Agent settings. Existing invalid or redirected environments are refused rather than deleted.

**Windows (PowerShell)** — no Bash required:

~~~powershell
git clone https://github.com/Mahdi-Soleimani/global-ai-skills-library.git
cd global-ai-skills-library
python -I -B -X utf8 tools/runtime_setup.py
python -I -B -X utf8 tools/runtime_launch.py mcp
~~~

Use the same Python scripts on macOS/Linux (with python3) if preferred. Check an existing local runtime without installing using `python -I tools/runtime_setup.py --check` (or `./install.sh --check`). For an MCP client, configure the absolute local launcher path on POSIX; on Windows use the absolute path to `.venv/Scripts/python.exe` as command and arguments `["-I", "-B", "-X", "utf8", "C:/ABSOLUTE/PATH/tools/gasl.py", "mcp"]`, replacing the script path with your own. See [MCP_CONFIG.example.json](MCP_CONFIG.example.json). No Agent configuration is written automatically. Setup requires access to Python package distribution infrastructure; normal offline search does not.

### Use without MCP

The search CLI and local Explorer do not require the MCP dependency. On Windows replace `./gasl` with `python -I -B -X utf8 tools/runtime_launch.py`:

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

The first download command plans the complete package; the second retrieves verified regular files and applicable upstream notices to the ignored local catalog. It does not install or execute anything. The full-package collector uses portable local locking and Python standard-library pinned HTTPS retrieval, without a curl dependency. The portable retrieval path passed the six OS/Python CI combinations on Windows, macOS and Linux in Phase 63. Ordinary collection now also reconstructs every recursive Git tree object against the recorded tree pin before planning; incomplete or mismatched tree metadata is refused. This is tree-object evidence, not independent commit reconstruction or proof of runtime dependencies. Root-level Skills and unsafe or oversized package layouts require separate handling. To inspect a repository-root `SKILL.md` without downloading any file content, use:

~~~bash
./gasl root-skill-review --id YOUR_SOURCE_RECORD_ID
~~~

This explicitly online metadata-only review reconstructs all Git tree hashes, reports candidate paths, nested Skill exclusions and unsafe/oversized entries, and binds the proposed inventory to a review SHA-256. It does not establish package completeness or approve download, installation, execution, or redistribution. The ordinary complete-package downloader still refuses repository-root Skills. For an explicit private review of selected files, preview the exact scope first:

~~~bash
./gasl root-skill-scope --id YOUR_SOURCE_RECORD_ID --file SKILL.md --file scripts/example.py
~~~

Replace the example script path with a real candidate from the review. Repeat `--file` for every requested path, including SKILL.md. Relevant ordinary root/ancestor license-notice candidates are included in the preview. To collect only the reviewed scope, repeat the same command with `--execute --acknowledge-plan-sha256 PLAN_SHA256`. The plan is rebuilt against pinned upstream metadata before retrieval; mismatched acknowledgement, unsafe paths and changed file hashes fail closed. The collected selection is isolated under ignored `private/root-skill-scopes/`, not the installable catalog, and is explicitly incomplete. Re-audit stored bytes and static findings offline:

~~~bash
./gasl root-skill-scope --id YOUR_SOURCE_RECORD_ID --audit-plan-sha256 PLAN_SHA256
~~~

This never approves installation or redistribution, runs a Skill or resolves external dependencies. A large repository can be inspected and a smaller explicit subset reviewed without treating the whole repository as a single package.

To explicitly preview all candidates in an unblocked bounded root inventory:

~~~bash
./gasl root-skill-scope --id YOUR_SOURCE_RECORD_ID --all-candidates
~~~

Repeat with the exact plan digest and `--execute --acknowledge-plan-sha256 PLAN_SHA256` to collect that scope. Preview and collection report selected and missing candidate paths/counts, excluded and blocked entry counts, and whether all eligible candidates are selected. A stored scope can be checked against fresh pinned upstream inventory without re-downloading file content:

~~~bash
./gasl root-skill-scope --id YOUR_SOURCE_RECORD_ID --verify-coverage-plan-sha256 PLAN_SHA256
~~~

Explorer also exposes an explicit online root review button on pinned repository-root Skill details. Filter and select exact paths, then preview the digest-bound plan (including license candidates) and copy its JSON. The REST endpoints `POST /v1/root-skill-review` (id) and `POST /v1/root-skill-plan` (id, review_sha256, files) perform metadata-only review and planning; they do not accept execution or collection options. Content retrieval remains an explicit CLI operation with the matching acknowledgement digest.

This is an explicitly online metadata check, unlike the offline audit. Full candidate coverage is not proof of semantic package completeness or runtime dependency coverage and does not promote a private scope into the ordinary installable catalog. The all-candidates option refuses blocked or oversized inventories; explicit smaller scopes remain supported under the existing policy.

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

**Inert container isolation CI (Phase 19):** The separate [GASL sandbox canary workflow](.github/workflows/gasl-sandbox-canary.yml) builds a tiny self-authored static Go program in a `FROM scratch` Docker image **locally**, without downloading dependencies or executing downloaded Skill code. It uses a source-hash-labelled, immutable local Docker image ID and a restricted ephemeral Linux container to test network isolation, read-only mounts, an unprivileged identity, dropped capabilities, seccomp, memory/CPU/process limits, scratch-space limits, absent host secrets and symlink escapes. The Docker run uses `--network none`, `--read-only`, a read-only synthetic fixture and `--pull never`. The updated Phase 64 command is `./gasl sandbox --verify-canary` on Linux with local Go and Docker. It builds from GASL’s own tracked source and rejects externally supplied image IDs, uses a unique build tag, and verifies tag removal. No third-party Skill code or arbitrary command is accepted. The ephemeral Linux [canary run 45046458532](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45046458532) passed all **18** actual isolation checks. A passing canary is **not** certification of arbitrary-code safety, and no real Skill installation/execution path is enabled. The regular `./gasl sandbox` status command remains non-executing. See [Phase 19](docs/reports/PHASE-19-EPHEMERAL-INERT-SANDBOX-CANARY-2026-11-22.md).

### Phase 20: Preview a pinned Skill installation and simulate rollback (no actual install)

Plan a specific already indexed Skill against an explicit **logical** Agent and scope, fully offline:

~~~bash
./gasl install-plan --id GASL-SRC-ce593c8b9b3fd34f44d6 --agent codex --scope project
~~~

The output includes a deterministic SHA-256 `plan_id`, exact source commit and `SKILL.md` Git Blob, license caveats, locally rechecked source/package integrity (when downloaded), static-security warnings, unverified host compatibility, conceptual backup/rollback requirements and the state `actual_install_enabled: false`. This command does not contact the network, run a Skill, create a simulation ledger or modify Agent configuration. Supported **preview labels** are `codex`, `cursor`, `claude-code`, `claude-desktop`, `generic-mcp`; this particular plan command does not install or verify Host compatibility. Separate POSIX project-only transactional installers now exist for Codex, Cursor and Claude Code, but other preview targets remain preview-only.

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

### Phase 29: Real Codex discovers a transaction-installed inert Skill, then observes its removal

GASL now has an end-to-end test that connects the **actual Phase-28 fixture transaction** to the **real Codex App Server**. It builds a ZIP containing only GASL-authored, inert `gasl-discovery-probe/SKILL.md`, creates an isolated temporary project and empty Home/`CODEX_HOME`, and checks three independent real Host observations: the Skill is missing **before installation**, present and enabled **after the fixture-only transaction**, and missing again **after rollback**.

~~~bash
# Only for a trusted local Codex CLI. The script manages a disposable test profile.
./gasl codex-transaction-e2e --codex-bin /ABSOLUTE/PATH/TO/CODEX/CLI
~~~

Only App Server `initialize` and `skills/list` are used; there is **no login, prompt, model turn, untrusted downloaded Skill or real Agent directory access**. The test fails closed on wrong Skill path/disabled state, malformed protocol replies, failed ZIP installation, or unexpected discovery after rollback. The [dedicated Linux workflow](.github/workflows/gasl-codex-transaction-e2e.yml) installs exact Codex CLI `0.162.1` in runner temporary storage with npm lifecycle scripts disabled and validates this real-host lifecycle; synthetic fake-Host tests remain separate evidence. The real-user production installer is still disabled. See [Phase 29](docs/reports/PHASE-29-REAL-CODEX-TRANSACTION-DISCOVERY-2026-11-22.md).

### Phase 54: Windows current-user Profile SID and ACL security (native CI pending)

The current-user Profile transaction engine is being extended to Windows without changing the existing POSIX UID/passwd checks. A new standard-library Win32 adapter reads the current process token SID and GetUserProfileDirectoryW, matches it against USERPROFILE and Path.home(), rejects elevated, restricted, AppContainer, service and impersonated-thread contexts, and verifies actual NTFS owner/DACL ACEs. Ownership may be the current SID or a trusted OS principal only when the current SID has explicit modify/delete access. It rejects non-fixed/network/removable drives, reparse points in all path components, untrusted write ACEs, hard-link aliases, unknown ACL entry types and unstable profile identity.

Windows User Profile uses the same staged transaction, backup, restore, archived uninstall/reinstall and crash-recovery logic with the cross-platform msvcrt file lock. ACLs are checked recursively for the state records, active Skills, staging and retained backups. Windows directory fsync/power-loss durability is not claimed.

**The production Windows User Profile path remains disabled until native Windows CI passes.** Only the dedicated disposable Windows workflow sets GASL_ENABLE_WINDOWS_USER_PROFILE_CI=1 to exercise fake temporary HOME roots and read-only current-profile inspection. The workflow now tests native token/SID, ACL, Everyone-write refusal, NTFS Junctions, hard-link aliases, impersonation refusal and the full fake-profile transaction lifecycle. No real Agent profile is written. See [Phase 54 report](docs/reports/PHASE-54-WINDOWS-USER-PROFILE-SID-ACL-2026-11-23.md).

### Phase 60: Canonical Skill evidence (read-only)

    python tools/gasl.py canonical-index --summary
    python tools/gasl.py canonical-index --id EXACT_SOURCE_ID
    python tools/gasl.py canonical-index --compare ID_A ID_B
    python tools/gasl.py canonical-index --compare ID_A ID_B --verify-online
    python tools/gasl.py canonical-index --lineage ID_A ID_B
    python tools/gasl.py canonical-index --package-compare ID_A ID_B

The summary, ID lookup and default pair comparison are offline. Explicit online operations inspect only pinned candidate pairs. File comparison verifies retrieved SKILL.md bytes; lineage reports public GitHub metadata; package comparison reconstructs Git tree object hashes and compares the entire containing directory, including nested Skills, without fetching blob contents. It also reports filename-based license/notice and dependency manifest candidates from ancestor directories and the Skill directory. Matching tree hashes do not establish license applicability, runtime dependency equivalence, full install bundle equivalence or security approval. Missing evidence remains unknown. No records are merged or removed. See [Phase 60 report](docs/reports/PHASE-60-CANONICAL-EVIDENCE-INDEX-2026-11-24.md).

### Phase 58: Read-only Codex ownership migration audit

Existing legacy Codex project records and the host-scoped Windows records are deliberately separate. Check compatibility of a **single explicitly selected** legacy active Skill before considering migration:

    python tools/gasl.py codex-migration-audit --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL

The command is read-only on Windows, macOS and Linux. It checks complete recorded fresh-install, replacement and pinned-restore backup chains, exact restored source Plan and content hashes, conflicting state, hardlinks and portable Windows filenames; it computes a candidate metadata digest in memory. It emits no converted receipt, lock, journal or path contents. Exit 0 means compatible candidate metadata only, not installation or migration approval; exit 2 means blocked. Project-bound uninstall markers and retained reinstall evidence can be checked, but their conversion remains blocked: the native schema does not preserve identical path-binding and historical-marker semantics. Pending transactions, unowned backups, unmanaged restore and unsupported reconciliation remain blocked. The audit is not a locked snapshot, independent upstream provenance check or rollback certification. Reversible migration is rehearsed only on generated inert disposable fixtures. No production write-capable migration is enabled.

### Native Windows Codex backup and provenance review (Phase 58)

The existing read-only `backup-review` and `provenance-compare` commands route to the native host-scoped Codex ownership store on Windows; POSIX retains its legacy review behavior.

    python tools/gasl.py backup-review --selected-root "$env:GASL_SELECTED_PROJECT" --skill-name SKILL
    python tools/gasl.py provenance-compare --selected-root "$env:GASL_SELECTED_PROJECT" --skill-name SKILL --left active --right EXACT_BACKUP_ID

Both validate recorded backup lineage and file hashes without changing project files. A selected eligible backup can provide a binding from the existing native restore/reinstall preview; any subsequent write still requires exact interactive local approval. Legacy state, pending migrations and rehearsal-only archive evidence are not adopted. Native archive markers are not equivalent to the legacy project-bound ownership marker; local Plan references are not independently verified upstream provenance. No production migration is enabled.

On Windows, the compatibility commands `codex-project-install` and `codex-install-wizard` now route to the native host-scoped installer and wizard. Restore/reinstall aliases use native preview bindings, and Windows uninstall requires a `preview-uninstall` binding. `audit-legacy-backups` supports read-only orphan history inspection; `preview-legacy-reinstall` and `reinstall-legacy-backup` remain refused on Windows. No legacy state is adopted, no old authorization is translated, and no production migration is enabled. The original POSIX command behavior is unchanged except that the Windows-specific `preview-uninstall` action is explicitly rejected on POSIX.

### Phase 53: Native Windows project-scope Skill transactions

GASL now supports **Windows-native, write-capable project-scope Skill transactions** for Codex, Cursor and Claude Code in explicitly selected existing Git project roots. The engine uses the same verified pinned private ZIP and host-target preflight as the POSIX installers, with a Windows file-range lock based on Python msvcrt. Staging, ownership receipts, journals, complete backup, restore, archived uninstall/reinstall and fail-closed recovery are retained.

From a Windows PowerShell terminal in the GASL repository:

    $env:GASL_SELECTED_PROJECT = "C:\path\to\an\existing\git-project"
    python tools/gasl.py host-project-wizard --host codex --id GASL-SRC-EXACT_ID --selected-root "$env:GASL_SELECTED_PROJECT" --action preview
    python tools/gasl.py host-project-wizard --host codex --id GASL-SRC-EXACT_ID --selected-root "$env:GASL_SELECTED_PROJECT" --action install --download-if-missing

Change --host codex to --host cursor or --host claude-code as needed. **PowerShell** is used on Windows because the repository root ./gasl launcher is a Unix Bash script. The installer still requires exact interactive TTY approval and a fresh Plan/target binding. Browser selection only copies commands; no HTTP endpoint gains installation access.

Windows paths use .agents/skills/SLUG, .cursor/skills/SLUG and .claude/skills/SLUG. Windows Codex uses an **independent host-scoped** ownership store at .gasl-managed/hosts/codex/; it does not silently adopt or migrate existing POSIX Codex receipts under .gasl-managed/. Existing unmanaged Skills are always refused, not overwritten. Windows NTFS Junctions, Symlinks and unsafe ZIP device or ADS filenames are blocked.

The cross-platform file lock uses POSIX flock on macOS/Linux and msvcrt.locking on Windows. It coordinates cooperating GASL transactions, not arbitrary external editors or privileged actors. The journal and byte inventory protect interrupted **process** operations, but Windows directory fsync durability is not claimed. Cloud sync, network shares, third-party concurrent writers, power-loss durability and live Agent discovery are **not certified**.

**Native verification:** [Windows GitHub Actions Run 45254049109](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45254049109) passed **15 Windows-native transaction tests plus 57 existing safety/adapter tests**. Two earlier failed runs exposed and prompted fixes for portable source metadata and canonical file ordering; no integrity checks were bypassed.

**Scope boundary:** Windows currently supports *project installation only*. The Windows User Profile SID/ACL implementation is tracked separately in Phase 54 and remains gated until its native Windows CI passes. Windows GitHub Actions tests use only inert packages and disposable roots, never real Agent installations or third-party Skill execution. See [Phase 53 report](docs/reports/PHASE-53-WINDOWS-PROJECT-SKILL-TRANSACTIONS-2026-11-23.md).

### Phase 52: Current-user Profile installation, backup and recovery (POSIX; Windows extension pending Phase 54 CI)

GASL now supports explicit, local TTY-only **user-wide Skill installation** for Codex, Cursor and Claude Code. These operations affect all local projects under the *current OS account's actual HOME*: Codex uses ~/.agents/skills/, Cursor ~/.cursor/skills/, and Claude Code ~/.claude/skills/. Ownership receipts, backup manifests, pending transaction journals and uninstall markers live separately under ~/.gasl-managed/user/hosts/HOST/.

Run from this GASL repository:

    # Read-only preview, never installs or prepares a ZIP
    ./gasl user-profile-wizard --host codex --id GASL-SRC-EXACT_ID --selected-home "$HOME" --action preview

    # Real user-wide filesystem install with independent, exact local TTY approvals
    ./gasl user-profile-wizard --host codex --id GASL-SRC-EXACT_ID --selected-home "$HOME" --action install --download-if-missing

Use --host cursor or --host claude-code for the other supported Agents. The Explorer selection panel offers both project-only and user-wide copyable commands; **the browser cannot install, execute, approve, or download Skills**.

The selected HOME is checked against the current operating-system passwd record, real/effective UID, the current Python HOME and filesystem owner. Sudo/root, selecting another account's HOME, a fake HOME variable, symlinks, unsafe ownership and world-writable state or Agent directories are refused. Receipts, journal entries, backup manifests, markers and approval bindings carry or verify an immutable SHA-256 account identity including current UID, canonical HOME and filesystem inode; copied state from another HOME is not adopted.

Every normal lifecycle write (install, replace, restore, uninstall or reinstall) uses an explicit **USER PROFILE ALL PROJECTS** approval phrase. The separately requested **recover** command is the exception: it only finalizes or rolls back an already recorded, validated transaction and does not require another TTY challenge. Cursor's exact phrase additionally includes **CURSOR-SYNC-RISK**: if Cursor Sync Skills is enabled, a user-scope Skill might be synchronized to Cloud Agents. Cursor may also discover Skills stored in the Codex or Claude user directories. GASL does not control Cursor settings, and installing is not a safety certification.

The user-wide transaction engine provides fresh installation, replacement of unmodified GASL-owned Skills with full-byte backup, backup listing, restore while archiving the replaced version, uninstall with retained archive, reinstatement of a chosen owned backup, and interrupted-transaction recovery. It refuses unexpected user edits, ambiguous ownership or altered ZIP/manifest evidence. The low-level command is:

    ./gasl user-profile-install --help

**Verification boundary:** these write-capable paths are tested only with inert Skill packages and synthetic disposable HOME roots. No actual user profile was modified, no third-party Skill was executed, and no new live Cursor/Claude Host discovery claim is made. Windows User Profile security is being implemented separately in Phase 54 and remains gated until native CI acceptance. Runtime sandbox, independent publisher identity verification and a user-selected GASL project License remain separate. See [Phase 52 report](docs/reports/PHASE-52-USER-PROFILE-TRANSACTIONAL-AGENT-SKILLS-2026-11-23.md).

### Phase 51: Real Cursor and Claude Code project Skill transactions (POSIX only)

GASL now has a **separate host-scoped transactional filesystem installer** for **Cursor** and **Claude Code** at an explicitly selected existing Git **project root**. The current official paths are `.cursor/skills/<slug>/SKILL.md` and `.claude/skills/<slug>/SKILL.md` respectively. The implementation reuses the previously verified pinned ZIP, static Skill format review, full-file hashing and exact target binding, but stores independent ownership receipts, journals, backup versions, and uninstall markers under `.gasl-managed/hosts/cursor/` and `.gasl-managed/hosts/claude-code/`.

From the GASL repository:

    export GASL_SELECTED_PROJECT="/absolute/path/to/your/existing/git/project"
    ./gasl host-project-wizard --host cursor --id GASL-SRC-EXACT_ID --selected-root "$GASL_SELECTED_PROJECT" --action preview
    ./gasl host-project-wizard --host cursor --id GASL-SRC-EXACT_ID --selected-root "$GASL_SELECTED_PROJECT" --action install --download-if-missing

For Claude Code change `--host cursor` to `--host claude-code`. The read-only preview creates no project or ZIP files. Real actions require a **local TTY** and distinct, exact approvals for optional pinned download, private ZIP creation and final installation. The browser only supplies copyable terminal commands; **there is no HTTP write endpoint**. For replacing a GASL-managed Skill, use `--action replace` explicitly. Existing unmanaged files are never silently overwritten or adopted.

The explicit low-level transaction CLI handles **fresh install, replace, list-backups, restore, uninstall/archive, reinstall from an owned archive, and interrupted-transaction recovery**:

    ./gasl host-project-install --host cursor --selected-root "$GASL_SELECTED_PROJECT" --action list-backups --skill-name exact-slug
    ./gasl host-project-install --host cursor --selected-root "$GASL_SELECTED_PROJECT" --action preview-uninstall --skill-name exact-slug
    ./gasl host-project-install --host cursor --selected-root "$GASL_SELECTED_PROJECT" --action preview-restore --skill-name exact-slug --backup-id EXACT_BACKUP_ID
    # Copy the fresh state_binding_id printed by the chosen preview.
    ./gasl host-project-install --host cursor --selected-root "$GASL_SELECTED_PROJECT" --action restore --skill-name exact-slug --backup-id EXACT_BACKUP_ID --state-binding-id EXACT_BINDING
    ./gasl host-project-install --host cursor --selected-root "$GASL_SELECTED_PROJECT" --action recover --skill-name exact-slug

The engine uses a host-local POSIX lock, a durable write-ahead journal, verified staging, atomic same-filesystem rename, full-file Backup, SHA-256 inventory and ownership checks. It **refuses changed user files, path symlinks, unknown archive lineages and stale preflight bindings**. Restoration retains the version it replaces as another Backup; uninstall retains a restorable archive and owner marker. Recovery can roll back or finalize a recorded transaction only if its exact byte inventories are still intact; it refuses any uncertain state instead of deleting user changes.

**Scope boundary:** this is **real filesystem installation code**, tested with entirely inert synthetic Skill packages and disposable Git roots; **the real Cursor/Claude Code applications have NOT been launched for discovery** and no user project/Agent profile has been modified. Therefore no claim of verified runtime Host behavior is made. Cursor may also discover Skills placed in Claude directories: the engine isolates ownership state, not all Host-level discovery or precedence effects. User HOME scope, Windows writes, third-party code execution, sandbox, and an open-source/public release remain separate roadmap tasks. See [Phase 51 report](docs/reports/PHASE-51-CURSOR-CLAUDE-PROJECT-INSTALL-2026-11-23.md).

### Phase 50: Deterministic private MVP release draft and publication gate

GASL now supports a **private, offline, reproducible ZIP draft** of the core CLI/Explorer distribution. The build uses only a strict allowlist of **Git-tracked** runtime files, local source-catalog metadata, project attribution/notices and required configuration. It **excludes** untracked/private Skill packages, personal files, test fixtures, credentials and the user's Agent profiles.

    # Read-only release readiness report (no ZIP created)
    ./gasl release-draft --action inspect

    # Only after committing intended changes: create a private local draft ZIP
    ./gasl release-draft --action build

    # Read-only verification of the existing draft; never extracts the ZIP
    ./gasl release-draft --action verify

The private ZIP is placed under the ignored `private/release-drafts/` directory, with a SHA-256 sidecar and a manifest of every included file's name, length and hash. Both construction and verification bind the exact inventory and bytes to the committed Git tree, not merely the worktree or the ZIP's own manifest. Phase 59 uses stored ZIP entries with fixed ordering, timestamps and permissions to avoid compression-library differences; a fixed-commit golden SHA-256 test is run on the three CI platforms. Verification distinguishes canonical archive bytes from older compressed drafts with verified content. Overwriting existing drafts, redirected paths, uncommitted tracked changes, missing required runtime files and unexpected large inputs are refused. Windows PowerShell can invoke the same commands with `python tools/gasl.py` in place of `./gasl`.

The draft is a standalone metadata-only runtime snapshot, not a complete Git clone. It contains the install script, pinned optional MCP requirements and example MCP configuration files, but does not contain downloaded Skill packages or the public mirror's third-party payloads. Use the extracted `python tools/gasl.py search`, `route`, `serve` or `mcp` commands; Git-based release construction and repository-maintenance commands require the original checkout. Offline Skill content retrieval correctly reports a cache miss in a fresh draft. The standalone smoke test runs the actual CLI, local REST Explorer and optional MCP STDIO from a verified draft in an isolated temporary directory.

**This is deliberately NOT a public release.** The code project still lacks a project `LICENSE` chosen by its owner; licensing collected third-party Skills would require separate terms/attribution review. Even if a project license is later added, the current tool keeps `public_release_allowed=false` until other release blockers are resolved. It does **not** upload files to GitHub, grant a software license, declare Windows or other Host compatibility, or run third-party code. See [Phase 50 report](docs/reports/PHASE-50-PRIVATE-MVP-RELEASE-DRAFT-2026-11-23.md).

### Phase 49: Explicit Codex project installation handoff from Explorer

GASL Explorer's selected Skill view now shows a **copyable terminal command** that completes the Codex project-scope installation workflow without turning the local web API into a write-capable service. The browser **does not** install, execute, download or approve any Skill. It never receives permission to write inside an Agent project.

From the GASL repository, explicitly choose an **existing absolute Git project root** and one selected pinned source record:

    export GASL_SELECTED_PROJECT="/absolute/path/to/your/existing/git/project"
    ./gasl codex-install-wizard --id GASL-SRC-EXACT_SOURCE_ID --selected-root "$GASL_SELECTED_PROJECT" --action preview

The preview checks pinned source identity, local downloaded-package integrity, known static scan findings, recorded compatibility/license warnings and project-root eligibility. It creates no ZIP or Agent files and does not require a TTY.

When the chosen source and project are correct, the user **separately opts into** installation:

    ./gasl codex-install-wizard --id GASL-SRC-EXACT_SOURCE_ID --selected-root "$GASL_SELECTED_PROJECT" --action install --download-if-missing

The interactive wizard enforces these gates, each with its own real **local TTY exact phrase** when necessary:

1. **Optional pinned download** — only if missing and the user explicitly passed `--download-if-missing`. The existing on-demand downloader rechecks the exact commit/blob and performs static scanning. No downloaded script runs.
2. **Private ZIP** — if absent, the wizard displays the exact Plan and requires approval before producing the locally ignored private bundle. A pre-existing ZIP must pass independent integrity verification; altered ZIPs are refused, not overwritten.
3. **Project target preflight** — invokes the existing Codex project install/replace preview with its target/ZIP hash binding. Missing destination is required for `install`; it never silently overwrites an existing directory.
4. **Real installation** — the existing project-only transactional installer requires a **separate, exact TTY phrase**. It rechecks the binding under a local lock, writes an ownership receipt, and preserves crash-recovery semantics. It never executes Skill content.
5. **Replace** — permitted **only** with the separately requested `--action replace`. The existing installer retains and verifies the entire prior Skill in a restorable Backup; no automatic replacement happens on name collision.

A missing, tampered, ambiguous, or statically flagged source remains blocked. Real user `HOME` scope is not supported. The required project root is not inferred from the browser, and the workflow never starts or uses Codex itself. This was the Phase-49 state; Phase 51 has since added separate POSIX project-only Cursor and Claude Code transactional installers. Real Host discovery remains unverified.

**Important:** Running this CLI with an exact TTY phrase is a real action on the explicitly chosen project. The Phase-49 synthetic tests use only disposable Git roots; **no real user project install or real-host/manual test has been performed**. Other hosts, Windows, security sandbox execution and public release readiness remain separate roadmap work. See [Phase 49](docs/reports/PHASE-49-CODEX-EXPLORER-INSTALL-HANDOFF-2026-11-23.md).

### Phase 48: Reproducible, *provisional* search-quality evaluation

GASL's historical **26-query, 148-judgment** bilingual development set could no longer run directly against the refreshed Source Catalog: 24 of its 72 judged source IDs had changed when upstream repositories advanced to new pinned Commits. The original dataset is **not independently adjudicated Gold**; silently assigning old labels to new IDs would be misleading.

The Phase 48 local evaluator preserves the original labels, reconstructs a pinned historical crosswalk from a **specific old Git revision**, and transfers each label only when **repository, source path and exact Git Blob SHA are the same**. Changed/missing blobs, ambiguous duplicates and reused IDs fail closed.

    # Reproduce the old-ID to new-ID crosswalk from Git history (local only):
    python3 tools/benchmark_reconcile.py --historical-revision 7e616c0f5a8b6ba906bea59a0ade3fc163d9e418 --write-map benchmarks/search-gold-v1-crosswalk.json --report /tmp/gasl-provisional-baseline.json

    # Replay without requiring the older Git commit to be present locally:
    python3 tools/benchmark_reconcile.py --map benchmarks/search-gold-v1-crosswalk.json --report /tmp/gasl-provisional-baseline.json

    # Compare four experimental sorts on the same retrieved candidates:
    python3 tools/search_ranking_lab.py --output /tmp/gasl-provisional-ablation.json

The measured **development-only** baseline at the Phase-48 source snapshot is P@5 **0.4385**, Recall@5 **0.5818**, MRR@10 **0.8987** and NDCG@5 **0.6577**. The experiment score-first yielded NDCG@5 **0.6770** on the same small internal labels, but **only 50% of top-five results were judged**. It improved seven queries and regressed three; that is **not evidence of independently verified real-world quality gains**. No experimental ranker was promoted to default, no quality score was fabricated, and no Skill was installed or executed.

**Fresh checkout comparison:** The development Mac also has optional private metadata and a Git-untracked local Skill manifest, which are absent in GitHub CI. Replaying the exact **tracked-only** inputs in isolation yields production NDCG@5 **0.6456**, and the same score-first experiment falls to **0.6326**. This reversal reinforces why no unadjudicated variant is released. Both input scopes and their SHA-256 fingerprints are documented in the Phase 48 report.

**Phase 57: source-version drift audit.** Inspect every historical judgment before attempting ranking evaluation:

    python3 tools/benchmark_reconcile.py --map benchmarks/search-gold-v1-crosswalk.json --audit-report /tmp/gasl-benchmark-drift.json

The JSON report records source/commit/blob identities, same-blob eligibility, blocked identities, affected query IDs, counts and input digests, without producing ranking metrics or creating new judgments. `ready_provisional` permits the existing strict evaluator; `rejudgment_required` records changed/missing content and blocks all aggregate ranking metrics; `integrity_blocked` additionally exits nonzero for identity collisions, ambiguous matches or invalid pins. The quality workflow reports ordinary drift explicitly and skips both metric steps; the daily refresh audits its newly generated catalog before metadata publication. A successful audit is **not** a successful ranking evaluation. The original strict `--report` and ablation commands still fail closed on any unresolved judgment.

Dedicated lightweight quality CI checks the crosswalk, original-label immutability, absence of fabricated Gold and reproducibility. Actual search-quality promotion requires **two independent human reviewers, adjudication, out-of-pool negatives, a frozen holdout and validated answerability**. See [Phase 48 report](docs/reports/PHASE-48-PROVISIONAL-SEARCH-QUALITY-2026-11-23.md) and [Phase 57 report](docs/reports/PHASE-57-BENCHMARK-VERSION-DRIFT-2026-11-23.md).

### Phase 47: From a task to a shortlist, comparison, and Skill choice

GASL Explorer now implements a simple **three-step local workflow** on top of the existing source catalog, search and experimental router. Start the same localhost Explorer as before:

    ./gasl serve

1. **Describe a task:** use *پیشنهاد برای نیاز* to retrieve up to 20 provisional recommendations using the existing task router. Choose the intended Agent and optional domain/content/public filters. When answerability is \`abstain\` or \`undetermined\`, the UI explicitly says that its evidence is insufficient; it does not pretend that an answer or a catalog-wide absence has been proven. The separate *جست‌وجوی گسترده* action still uses the existing lexical search and offers up to 50 results.
2. **Compare 2–3 options:** tick choices and compare locally recorded source records in an accessible, scrollable table. View description, repository, license/assessment, static security status, declared compatibility, content availability and pinned commit; differences are marked without inventing an overall quality score. The new authenticated \`POST /v1/compare\` takes \`{"ids": ["GASL-SRC-...", "GASL-SRC-..."]}\`, checks exactly two or three distinct, existing source IDs, and never fetches remote code or runs Skills. It returns neither a winning option nor installation/security approval.
3. **Choose for further review:** directly select any individual result, or compare multiple options and then click *بررسی این گزینه*, to see the source and the optional \`./gasl install-plan --id ... --agent ... --scope project\` command, which is a **read-only installation preview**. No Skill is installed, activated, executed, or implicitly approved. Real installation remains in the separately approved Codex project-only transaction flow.

This is intentionally a small enhancement to the existing **local-only** web UI, with no JavaScript framework, paid API, AI model or new Python dependency. The workflow clears stale comparisons when the user starts another search and uses safe DOM text nodes instead of injecting source text as HTML. It excludes unexpected external source link protocols. Existing REST bearer-token authentication applies to the new compare endpoint.

The ranking is **lexical and experimental**, not a calibrated quality/security assessment. License metadata is not legal clearance; a static scan status does not guarantee a safe Skill; declared Agent compatibility is not verified runtime compatibility. Source record comparisons are advisory. See [Phase 47](docs/reports/PHASE-47-EXPLORER-NEED-COMPARE-SELECT-2026-11-23.md).

### Phase 46: Offline provenance comparison and evidence boundaries

The read-only provenance comparison distinguishes **verified local bytes**, **claims recorded in local receipts and archive manifests**, and **unverified upstream provenance**. This does **not** connect to the Internet, independently confirm repository ownership, certify Git commit/blob provenance, inspect licenses or attest that Skill instructions/dependencies are safe.

    # Review the provenance evidence of active and archived versions, without writing:
    ./gasl provenance-compare --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL

    # Compare two exact archived versions or active vs one archived version:
    ./gasl provenance-compare --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL --left active --right EXACT_32_HEX_BACKUP_ID

    # Machine-readable structured output:
    ./gasl provenance-compare --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL --format json

For each version, the report includes its role, count of files, a SHA-256 digest of the verified local inventory, locally recorded source kind and Plan ID if available, an ownership-evidence classification, and an **explicit NOT CHECKED** status for upstream owner, Git commit/blob, license and code safety. Comparing two versions shows equality of complete local inventories, counts of added/removed/changed files, and whether their *recorded* Plan references match. None of these imply that two copies came from an authentic upstream publisher.

Historical version ancestry may reveal a prior **manual ownership attestation** even after successive GASL restores and reinstalls. The comparison preserves this warning and never upgrades a manual claim into cryptographic proof. Phase-43 project-bound local markers are evidence of local continuity, not independent proof of who owned the original source or its safety. Legacy archives remain historically unverified.

This feature has **no write action**, no implicit HOME/project discovery, no remote verification, no consent grant and no Skill execution. Backup hashes are observed at review time; unrelated processes with filesystem write access are beyond the protection of a read-only report. For interactive recovery use the **separate**, previously established Phase 40–45 flow. See [Phase 46](docs/reports/PHASE-46-OFFLINE-CODEX-PROVENANCE-COMPARISON-2026-11-23.md).

### Phase 45: Unified, readable and provenance-aware Codex Backup review

There is now **one read-only entrypoint** for the three existing verified project-scope Codex recovery flows. You no longer need to guess whether a Skill is installed, was uninstalled with a GASL ownership marker, or has orphaned historical backups:

    # From the GASL repository, explicitly choose an existing Git project root:
    ./gasl backup-review --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL

    # Select an exact Backup ID from that list to preview the correct existing operation:
    ./gasl backup-review --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL --backup-id EXACT_32_HEX_ID

    # Structured output for reporting — STILL READ-ONLY:
    ./gasl backup-review --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL --format json

The default text review shows the state, Backup IDs, file counts, *locally recorded* source-plan references, ownership evidence, safeguards, available recovery effect and next command with the binding supplied by the relevant existing read-only preview. The output uses $GASL_SELECTED_PROJECT instead of disclosing the actual selected absolute project path. Before using a suggested command, explicitly set the variable to the **same** Git project root. Neither the review, a preview ID nor a suggested command is an installation authorization: the existing write command still requires a **separate exact approval phrase entered in a local interactive TTY** and rechecks target/Backup state under lock.

- **Installed managed Skill:** lists verified retained Backups; restoring one saves the currently active version as another Backup. Byte-identical/no-op versions are not selectable.
- **Uninstalled with marker:** lists verified project-bound archives and offers the existing reinstall-backup path, without consuming the archives.
- **Legacy/orphan archives:** verifies the full history and explicitly states that original project ownership is **not proven**, even if a historical manifest records an upstream Plan ID. Only the manually attested reinstall-legacy-backup path is offered.
- **Pending transaction, unknown owner, occupied/unsafe target or missing receipt:** reports the blocker without guessing ownership, bypassing approval or overwriting user files.

No real user HOME or other projects are scanned. All verified file inventories and the actual restore/write/rollback safety logic remain with the existing Phase 40–44 components; this phase adds **no new write path**. The reviewer never executes a Skill, a dependency, a Codex prompt or a model request. See [Phase 45](docs/reports/PHASE-45-UNIFIED-CODEX-BACKUP-REVIEW-UX-2026-11-23.md).

### Phase 44: Manual reconciliation of legacy orphaned Codex Skill backups

Pre-Phase-43 uninstall operations retained some historical Backup folders but removed their ownership receipt and did not create the project-bound Uninstall Marker added later. Phase 44 provides a **separate, explicit and manually attested** route to reinstallation without falsely claiming historical ownership.

The following commands apply only to an explicitly chosen, existing Git project and a **currently empty** Codex project Skill target:

    # Examine the complete legacy archive chain; READ-ONLY
    ./gasl codex-project-install --action audit-legacy-backups --selected-root /ABSOLUTE/GIT/PROJECT --skill-name SKILL

    # Inspect one selected historical Backup; READ-ONLY
    ./gasl codex-project-install --action preview-legacy-reinstall --selected-root /ABSOLUTE/GIT/PROJECT --skill-name SKILL --backup-id EXACT_32_HEX_ID

    # Explicitly attest the backups belong to this project and reinstall
    ./gasl codex-project-install --action reinstall-legacy-backup --selected-root /ABSOLUTE/GIT/PROJECT --skill-name SKILL --backup-id EXACT_32_HEX_ID --state-binding-id EXACT_PREVIEW_BINDING

    # If a journaled legacy reinstatement was interrupted:
    ./gasl codex-project-install --action recover --selected-root /ABSOLUTE/GIT/PROJECT --skill-name SKILL

GASL checks every archive directory and manifest against the SHA-256 inventories, enforces a complete/unambiguous historical ancestry, checks the static SKILL.md name matches the selected Skill, rejects symlinks and unknown entries, and binds the preview to the target path and all backup manifests. **These checks cannot cryptographically prove which project originally owned a pre-Phase-43 backup.** The user must acknowledge that uncertainty and enter a separate, exact local TTY attestation phrase. No prompt or default provides implicit ownership approval.

The selected Backup is copied into private staging and the original backup chain remains unchanged. The resulting managed receipt uses **source_kind=unmanaged**, a synthetic local identity, and records manual_ownership_attested=true and historical_project_ownership_verified=false even when a historical manifest mentions an upstream Plan ID. Subsequent opt-in Uninstall produces the Phase 43 ownership marker, preserving the complete chain.

An unresolved legacy backup directory also **blocks ordinary fresh installation and unmanaged replacement** so it cannot silently fall outside new GASL backup history. No third-party Skill code or dependency is executed; the real user HOME remains untouched. Historical ownership still requires the user's independent judgement, not this tool's certification. See [Phase 44](docs/reports/PHASE-44-ATTESTED-LEGACY-CODEX-BACKUP-RECOVERY-2026-11-23.md).

### Phase 43: Recover a Codex project Skill after a completed uninstall

Uninstall now **archives the currently active Skill** outside the Codex discovery directory, keeps all earlier backup versions, and records a project-bound **Uninstall Ownership Marker** in the project-local .gasl-managed/uninstalled/ directory. An explicitly selected and verified Backup can subsequently be reinstalled into the **same empty project Skill target**, with a fresh receipt preserving the full historical backup chain.

New commands:

    ./gasl codex-project-install --action list-uninstalled-backups --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL

    ./gasl codex-project-install --action preview-reinstall --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL --backup-id EXACT_BACKUP_ID

    ./gasl codex-project-install --action reinstall-backup --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL --backup-id EXACT_BACKUP_ID --state-binding-id EXACT_PREVIEW_BINDING

    # If a journaled uninstall or reinstall was interrupted:
    ./gasl codex-project-install --action recover --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --skill-name SKILL

The read-only list and preview verify the ownership marker, selected project target hash, last GASL receipt, each backup manifest and all file SHA-256 inventories. They do not execute Skill code or expose local absolute paths. Reinstallation requires a live local interactive TTY with an exact challenge binding the selected Backup ID, previous uninstall event and preview state. It refuses an occupied destination, foreign/unowned backups, symlinks, modified archives, stale binding or a pending transaction.

Uninstall is still complete **from Codex's viewpoint** (the Skill directory disappears); retaining its exact bytes in a project-local backup makes recovery possible without downloading or re-running it. The current version is newly archived even when no older backups exist. Interrupted uninstalls can restore the prior active version, and interrupted reinstalls are rolled back or finalized only after checking the complete journal and file inventories. A second uninstall updates ownership without dropping the prior version chain.

**Compatibility limit:** Backup folders left behind by **pre-Phase-43 uninstallations do not contain this ownership marker**, so GASL will not automatically claim them for restoration. They require a separate future, explicitly reviewed reconciliation feature. This remains **project-scope Codex only**; real user HOME, other Agent profiles, and unattended installation remain excluded. See [Phase 43](docs/reports/PHASE-43-CODEX-UNINSTALLED-SKILL-REINSTALL-2026-11-23.md).

### Phase 42: Restore a previously committed Codex Skill backup

Previously, the recover action could undo an **interrupted** upgrade, but could not revert a **successfully committed** upgrade. The new restore workflow lets you choose a retained, hash-verified backup and restore its exact files. It preserves the currently active version as a **new backup**, and the selected historical backup is never consumed or overwritten.

Use an explicit existing Git project root, never the user HOME:

    # 1. List all retained backups without modifying anything
    ./gasl codex-project-install --action list-backups --selected-root /ABSOLUTE/GIT/PROJECT --skill-name SKILL

    # 2. Preview the chosen backup; copy its state_binding_id
    ./gasl codex-project-install --action preview-restore --selected-root /ABSOLUTE/GIT/PROJECT --skill-name SKILL --backup-id EXACT_32_CHAR_BACKUP_ID

    # 3. Restore only after entering the exact, backup-bound local TTY approval phrase
    ./gasl codex-project-install --action restore-backup --selected-root /ABSOLUTE/GIT/PROJECT --skill-name SKILL --backup-id EXACT_32_CHAR_BACKUP_ID --state-binding-id EXACT_PREVIEW_BINDING

    # If an interrupted restore has left a transaction journal:
    ./gasl codex-project-install --action recover --selected-root /ABSOLUTE/GIT/PROJECT --skill-name SKILL

The read-only preview binds the exact project target path, installed receipt, installed file hashes, selected backup, and all other backup manifests. After explicit confirmation, GASL copies the selected local backup to private staging, atomically moves the active version to a new versioned backup, checks both inventories and commits a new receipt. Interrupted restores return to the previous installed version; crashes after receipt commit safely finalize the new version. Modified files, symlinks, missing manifests, tampering, stale bindings and ambiguous recovery states fail closed without deleting unknown data.

Restoring a backup whose previous version was **unmanaged** is supported: GASL identifies the restored version as unmanaged provenance and uses a clearly marked **synthetic local identity** instead of falsely claiming a pinned upstream package. After restoration, that version is managed by GASL for future updates and opt-in removal. The list-backups action exposes version IDs and provenance without leaking full local paths or user files.

This operation is Codex **project-scope only**, supports local POSIX Hosts (macOS/Linux), and never executes any Skill, its instructions, dependencies or model turns. No actual personal Agent profile was used in tests. See [Phase 42](docs/reports/PHASE-42-CODEX-COMMITTED-BACKUP-RESTORE-2026-11-23.md).

### Phase 41: Explicit Codex project Skill replacement, retained backup and crash recovery

GASL can now replace an **existing** project-scope Codex Skill after a separate read-only preview and an exact local TTY confirmation.

Commands:

    ./gasl codex-project-install --action preview-replace --plan-id EXACT_NEW_PLAN_ID --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT
    ./gasl codex-project-install --action replace --plan-id EXACT_NEW_PLAN_ID --selected-root /ABSOLUTE/EXISTING/GIT/PROJECT --state-binding-id EXACT_PREVIEW_BINDING

Before activation, the complete previous Skill directory (including unlisted user notes/files) is atomically moved into .gasl-managed/backups/SKILL_NAME/BACKUP_ID; a hash inventory and the previous GASL receipt, if any, are retained in a separate manifest. A durable transaction journal allows the recover action to restore the exact previous directory if the process is interrupted before the new receipt is committed. Once committed, the old backup remains and is checked before subsequent upgrades and uninstall. Uninstall removes only the current unchanged managed Skill and deliberately retains verified backups.

The replace flow refuses changed managed files, symlinks, incomplete/modified backup history, stale preview bindings and ambiguous recovery states. It never overwrites a backup. A successful replace returns its backup ID and relative backup path. This is **project scope only**; no real user HOME, other projects, unattended operation, or Skill instruction/dependency execution is enabled. Phase 42 adds a distinct interactive restore-from-a-successfully-committed-backup command; recovery still handles interrupted transactions. See [Phase 41](docs/reports/PHASE-41-CODEX-PROJECT-REPLACEMENT-BACKUP-RECOVERY-2026-11-23.md).

### Phase 40: Explicit opt-in Codex project Skill installation (fresh only)

GASL now offers a **real, explicitly approved project-scope installer** for Codex: `./gasl codex-project-install --action preview --plan-id EXACT_PROJECT_PLAN_ID --selected-root /ABSOLUTE/GIT/PROJECT` followed by a separate `--action install` with the exact `--state-binding-id` from preview. The CLI requires a live interactive terminal and a source/target-bound confirmation phrase; it refuses existing Skill collisions and the real user HOME. It can `--action uninstall --skill-name EXACT_NAME` with verified ownership/unchanged file inventory, or `--action recover` an interrupted journal. Files are staged outside Codex's discovery directory and no Skill instructions/dependencies are executed. **Existing-Skill replacement was added in Phase 41; production user-scope installation and automatic activation remain unavailable.** See [Phase 40](docs/reports/PHASE-40-OPT-IN-CODEX-PROJECT-INSTALL-2026-11-23.md).

### Phase 39: Verified pinned full ZIP lifecycle in disposable real Codex HOME

The new `./gasl codex-pinned-bundle-e2e --codex-bin /ABSOLUTE/PATH/TO/CODEX/CLI --plan-id EXACT_PLAN_ID --acknowledge-fixture-only GASL_DISPOSABLE_CODEX_BUNDLE_ONLY` combines current Source/ZIP/format verification, a read-only state-bound target preflight, locked full-ZIP staging and activation, real Codex `skills/list` observations before/after, and checked rollback **inside a new disposable user HOME only**. Real macOS Codex `0.167.0` verified the exact three-file pinned `python-mcp-server-generator` bundle and removal; no model turn, Skill command, dependency or user profile was accessed. Production installations remain disabled. See [Phase 39](docs/reports/PHASE-39-PINNED-FULL-BUNDLE-CODEX-E2E-2026-11-23.md).

### Phase 38: Offline cross-Host Skill format review (no installation)

`./gasl host-format-review --plan-id YOUR_EXACT_PLAN_ID --host cursor --scope user` now checks a previously verified, private pinned Skill ZIP entirely offline for Codex, Cursor, or Claude Code. It re-verifies source and ZIP hashes, inspects a bounded **simple frontmatter subset** without executing or extracting third-party files, and reports the documented Host Skill directory. It explicitly does **not** claim real Host discovery, full YAML portability, behavioral safety, account compatibility, or permission to install. Local regression tests and the dedicated ZIP safety workflow cover this operation. See [Phase 38](docs/reports/PHASE-38-CROSS-HOST-STATIC-FORMAT-REVIEW-2026-11-23.md).

### Phase 37: Real third-party Codex discovery verified on macOS and Linux

The exact pinned `python-mcp-server-generator/SKILL.md` was discovered as enabled by a **real Codex App Server**, then removed and confirmed absent, inside a disposable user HOME on both macOS (Codex CLI `0.167.0`) and Ubuntu GitHub Actions (Codex CLI `0.162.1`). Private ZIP integrity and the pinned Git Blob passed. The [manual workflow run `45166176466`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45166176466) completed **SUCCESS**. No model turn, downloaded Skill command, dependency installation, login, or real user-profile modification occurred. **Production installation and execution remain disabled.** See [Phase 37](docs/reports/PHASE-37-REAL-THIRD-PARTY-CODEX-DISCOVERY-2026-11-23.md).

### Phase 36: Approval-gated third-party Codex discovery only

Added `tools/codex_third_party_discovery.py` and a **manual-only** GitHub Actions workflow. After explicit approval, it fetches the exact pinned `python-mcp-server-generator/SKILL.md`, verifies its Git Blob, copies only that file into a disposable Codex user `HOME`, and asks the real App Server only `initialize` + `skills/list` before and after installation/rollback. It requires the exact source-bound approval phrase, verifies the Skill is enabled at the exact path, removes it, confirms it is absent, and deletes the temporary profile. No model turn, Skill instruction/command, dependency, MCP server, real user profile, or credential is accessed. The workflow has no automatic push/PR/schedule trigger and was **not yet dispatched when Phase 36 was written**; Phase 37 records the later successful manual run. See [Phase 36](docs/reports/PHASE-36-THIRD-PARTY-CODEX-DISCOVERY-ONLY-2026-11-22.md).

### Phase 35: Detect unpinned package runners and review a Python MCP generator

The static scanner now reviews remote package-runner commands inside Skill Markdown as well as code. It flags unpinned `npx`, `pnpm dlx`, `bunx`, `yarn dlx`, `npm exec`, and `npm create` commands; exact SemVer pins and local paths are excluded. This exposed three review signals in `typescript-mcp-server-generator` (`npx ...@latest`, unpinned `npx tsx`, and unpinned MCP Inspector). Its pre-rule private ZIP was deleted; the candidate remains `manual_review_required`. A better-fit `python-mcp-server-generator` from `github/awesome-copilot@f10fdb8b2660ce85c98f220b2f1ca24653768a5c` was downloaded, hash/Blob-verified, manually reviewed, and statically scanned with zero findings. Its MIT license and HTTP reference are included in a three-file private ZIP (SHA-256 `8870d46717fe6a44589020556432f3c79c10cbb07364c4de48d0fe21c1f05367`). It is **not installed or executed**. Local prerequisites `uv 0.9.15`, Python 3.13.9 and Node 24.13.0 are present. The next Codex `skills/list` test requires explicit approval and will use only a disposable HOME, no model turn, and rollback. See [Phase 35](docs/reports/PHASE-35-UNPINNED-PACKAGE-EXECUTION-AND-PYTHON-MCP-CANDIDATE-2026-11-22.md).

### Phase 34: Detect code-generation injection and exposed development server templates

A manual review caught missed risks in two pinned downloaded Skill packages. The updated static scanner now flags unescaped OpenAPI description interpolation in generated source, wildcard CORS origins, and Node HTTP server `.listen(port)` without an explicit loopback host. It scans JavaScript and TypeScript (`.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`, `.tsx`) and does **not** execute third-party code. Fresh read-only scans report **2 findings** in `mcp-server-builder` and **3** in `chatgpt-apps`; both are `manual_review_required` and fail the new-install-bundle safety gate. The previously created private `mcp-server-builder` ZIP remains integrity-verifiable but **is not security-approved and must not be installed**. See [Phase 34](docs/reports/PHASE-34-STATIC-CODEGEN-CORS-NETWORK-BIND-2026-11-22.md).

### Phase 33: Select and prepare the first practical MCP Skill

The first practical candidate is `mcp-server-builder` from `alirezarezvani/claude-skills`, pinned to commit `5909a72e62b5fbb809935fb6a55b58bdbe175074`. Its MIT license is included and all 10 source file blobs are verified. GASL's static audit reports zero findings. Its two Python scripts only generate MCP scaffolds in a caller-selected output directory and validate local manifests; neither makes network calls or launches subprocesses. A private ZIP was created and verified under the previous scanner, but **not installed**. **Phase 34 supersedes its prior zero-finding result: two high-severity source-generation signals now block installation or new bundle creation.** Codex adapter/transaction/preparation workflows passed on commit `1189202` ([Codex](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45074583955), [ZIP safety](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45074583807)). The first test of this third-party Skill will be discovery-only, with no script execution or model turn, after explicit approval. See [Phase 33](docs/reports/PHASE-33-MCP-SERVER-BUILDER-CANDIDATE-REVIEW-2026-11-22.md).

### Phase 32: First real Skill license and security review

The prepared private `academy-guide` bundle was reviewed against its exact upstream commit. Its per-skill `LICENSE.txt` identifies Apache-2.0 and carries Anthropic's copyright notice; both files' Git blob IDs and the ZIP SHA-256 were verified. GASL's offline audit reports zero static findings and confirms the main pinned blob. The Skill contains instructions only (no scripts or binaries) and requests one read-only fetch from the official Claude Academy catalog when relevant. Codex compatibility is not declared upstream, and this third-party Skill has not yet been tested by the real Host. The review is **not installation approval**; a separate user decision is required before it enters even an isolated Codex profile. See [Phase 32](docs/reports/PHASE-32-ACADEMY-GUIDE-LICENSE-SECURITY-REVIEW-2026-11-22.md).

### Phase 31: Real Codex user-scope discovery in a disposable HOME

The real Codex App Server test now covers both project scope (`.agents/skills/`) and user scope (`$HOME/.agents/skills/`) using a freshly created, empty `HOME` and `CODEX_HOME`. It asks the pinned Codex CLI to perform only `initialize` and `skills/list` before install, after the inert fixture transaction, and after rollback. The user-scope test also consumes the Phase-30 one-time receipt. It never reads or writes the developer's existing home, `.codex`, or `.agents/skills`, and never starts a model turn or executes a third-party Skill. The official Codex CLI installation guide lists `.agents/skills/` as the project path and `~/.agents/skills/` as the user-wide path: [OpenAI CLI Skill installation](https://developers.openai.com/api/reference/cli). Real-user installation remains disabled.

Run locally against a trusted Codex CLI binary (the command creates and destroys its own isolated HOME):

~~~bash
./gasl codex-transaction-e2e --codex-bin /absolute/path/to/codex --scope user --test-one-time-receipt
~~~

CI pins Codex CLI `0.162.1` and runs both project and user scopes against the real App Server; the user-scope lifecycle and one-time receipt passed in [run `45073141936`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45073141936). The typed phrase is simulated in CI and must not be represented as human consent. See [Phase 31](docs/reports/PHASE-31-CODEX-ISOLATED-USER-SCOPE-2026-11-22.md).

### Phase 30: One-time, expiring confirmation for a strictly disposable Skill installation

GASL now supports a **separate, explicit confirmation step** before a test-only Skill transaction. Each request binds the immutable ZIP SHA-256, plan ID, exact temporary destination fingerprint, Host, scope and `install`/`replace` action. It expires within 30–300 seconds and can be **consumed only once under the same POSIX transaction lock**. A private HMAC-protected receipt and local secret are created solely in the disposable GASL fixture; both disappear after the test. Tampered, expired, reused or stale approvals fail closed, including if staging fails after the receipt was consumed.

For a human-operated, *temporary-profile-only* review of an already privately downloaded bundle:

~~~bash
./gasl consent-fixture-interactive --plan-id YOUR_EXACT_PLAN_ID \
  --agent codex --scope project --action install \
  --acknowledge-fixture-only GASL_DISPOSABLE_FIXTURE_ONLY
~~~

The CLI requires a **real interactive terminal**, prints the selected plan, version digest, Host, scope, operation and a distinct confirmation phrase, and refuses to proceed unless the operator types that phrase exactly. It then installs and rolls back **inside its own disposable fixture**, never inside a real Host account. The phrase and signed local receipt do not prove a person's identity and **cannot authorize production installation**. A failed or canceled confirmation does not install anything.

The [Codex integration workflow](.github/workflows/gasl-codex-transaction-e2e.yml) separately **simulates** the confirmation gesture on synthetic first-party test data and asks the *real Codex App Server* to verify absent → discovered → absent. CI explicitly reports `human_confirmation_verified=false` so automated tests are not misrepresented as genuine human consent. No original downloaded Skill is imported into Codex or uploaded to CI. Real-user Agent installation, login, model invocation and third-party Skill execution remain disabled. See [Phase 30](docs/reports/PHASE-30-ONE-TIME-FIXTURE-CONSENT-2026-11-22.md).

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
