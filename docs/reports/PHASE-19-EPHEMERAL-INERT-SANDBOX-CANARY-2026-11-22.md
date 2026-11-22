# Phase 19 — Ephemeral inert sandbox isolation canary

**Date:** 2026-11-22  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Objective:** Validate actual isolation controls in a Linux container without running a downloaded Skill, external script, package manager, real credential or production target.  
**Execution category:** Only **self-authored benign Go canary**; **third-party Skill execution stays disabled**.

## 1. Starting point and environment

- Phase 18's `./gasl sandbox` correctly reported `blocked`: Docker CLI was available on the macOS development machine, but its daemon was unavailable. Starting a resource-hungry local Docker Desktop VM on the user's 8 GiB Mac is **not required** for normal GASL.
- Phase 18 re-audited 38 pinned packages: 31 had no actionable static heuristic signals (none were approved), seven required review. No package was dynamically executed.
- Docker's mere presence, an arbitrary container start, and the legacy `sandbox-exec` binary are not treated as proof of containment.

## 2. New, deliberately narrow implementation

- `tools/sandbox_canary/main.go`: standalone Go program using **only the standard library**. It reads a synthetic fixture, probes restrictions, and returns a machine-readable result. It contains no third-party Skill data and cannot install a Skill.
- `tools/sandbox_canary/Dockerfile`: `FROM scratch`; the only copied file is the self-compiled static Go binary. Unprivileged UID/GID `65532:65532`; fixed `/canary` entrypoint. Source SHA-256 label ties the image inspection to the checked-out Go source.
- `tools/sandbox_canary_runner.py`: guards Linux-only execution, requires an exact immutable local `sha256:<64 hex>` image ID, validates image metadata, scrubs Docker-client environment, creates only synthetic read-only fixture files, runs with stringent Docker constraints, checks each canary result, and attempts forced container removal after a timeout. It **does not** accept an arbitrary container command or any Skill path.
- `./gasl sandbox`: unchanged non-executing readiness by default. Explicit `--verify-canary --image-id sha256:...` is available only for the inert Linux canary and never changes the Skill installation flag.
- `.github/workflows/gasl-sandbox-canary.yml`: independent workflow triggered by relevant source changes, or manually; `contents: read` only, `ubuntu-24.04`, locally compiles a static Go binary with `GOPROXY=off`, builds an image with `--pull=false --network=none` and `FROM scratch`, then tests the immutable local image ID. **No Skill packages are downloaded or run**. CI emits a per-check summary and fails closed if any check fails.

## 3. Isolation constraints and benign checks

The restricted container uses:

- `--pull never`, immutable local image ID and `/canary` entrypoint;
- `--network none`, a canary for failed outbound TCP plus an interface check that only loopback exists;
- `--read-only`, a read-only synthetic fixture mount, and actual `/proc/self/mountinfo` checks for read-only flags;
- `--tmpfs /tmp:rw,nosuid,nodev,noexec,size=8m,mode=1777`, bounded/writable scratch probes;
- `--user 65532:65532`, `--cap-drop ALL`, `--security-opt no-new-privileges:true`, and checks of `CapEff`, `NoNewPrivs` and active seccomp filter in `/proc/self/status`;
- `--memory 128m`, `--memory-swap 128m`, `--cpus 0.5`, `--pids-limit 64`, restrictive ulimits and `/sys/fs/cgroup` quota checks;
- private IPC/cgroup namespaces and Docker's default private PID namespace (verified by PID 1 inside the canary), no Docker socket or home directory mounted, minimal explicit environment, and a synthetic symlink escape canary;
- `--rm`, a fixed run timeout and forced container cleanup attempt after timeouts.

The test checks exactly **18 explicitly enumerated predicates** in the current schema. Each failed predicate fails the entire check. No falling back to host execution is possible through this CLI path.

## 4. Guarantees deliberately not claimed

- **Passing a self-test does not prove an arbitrary malicious Skill cannot escape** the container; Docker, the kernel and the trusted CI runner are part of the attack surface.
- No external container image, third-party script, real API credential or live target is tested.
- This phase **does not implement the generalized Skill runner, user approval lifecycle, execution authorization, install/uninstall, package manager or compatibility adapter**. The Boolean `sandbox_execution_enabled` remains `false` even when the benign canary passes.
- Results are valid only on the **specific ephemeral Linux Runner** on which they are observed. They do not demonstrate that Docker on the user's Mac is configured or ready.
- No dynamic Skill validation is claimed. Previously reviewed packages remain unapproved.

## 5. Verification and audit trail

- Local macOS build of the Go program with `CGO_ENABLED=0`, `GOOS=linux`, `GOARCH=amd64`, `GOPROXY=off`, `GOSUMDB=off`: **PASS** (static Linux ELF file in `/tmp`, not staged).
- Python regression suite after integration: **235 tests and 6 subtests passed** (after the final full-canary registration guard).
- `tests/test_sandbox_canary_runner.py`: **12 tests**, including invalid/non-pinned image rejection, immutable source label checks, Docker flag verification, no Mac execution, fail-closed results, timeout cleanup and benign mock success.
- Python compilation and whitespace checks: PASS.
- The newly added GitHub workflow provides the actual **Linux Docker containment verification**. Its live URL, result and number of observed checks must be recorded after its first completion; **do not report Linux canary success from mock-only tests**.

## 6. Next engineering gates

1. Confirm the independent ephemeral GitHub Actions canary run passes every check; if not, investigate and fix a specific fault rather than downgrading or removing a failing check.
2. Keep the local macOS readiness gate `blocked` until a genuine Docker daemon and the same host-specific canaries can run locally; there is no need to allocate laptop RAM just to pass this phase.
3. Design a separate, **opt-in** installation proposal, with immutable hashes, license/security evidence, compatibility constraints and manual consent; never expose generalized untrusted execution until dedicated integration, rollback, log/audit and sandbox escape tests are complete.
4. Continue to record each phase under `docs/reports/`. Never put private reports, Skill code or secrets into Actions artifacts or public Git.

**Live CI outcome:** `benign_canary_verified` on the ephemeral Linux runner; 18/18 real benign isolation checks passed. `sandbox_execution_enabled=false` and `skill_installation_allowed=false` still apply. See live verification below. This is *not* approval of arbitrary code or dynamic Skill execution.

## 7. Live CI iteration 1 — diagnostic follow-up

- Workflow run [`45045856726`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45045856726), triggered by source commit `ba4b934`, **FAILED** in the inert container verification step. Python unit tests, the static Go build and the offline `FROM scratch` image build all passed. The production security/Skill-execution gate stayed disabled.
- The initial Python wrapper discarded the child process output on a nonzero exit; its `reason_code` only reported `canary_nonzero_exit_or_isolation_failure`, so the failed predicate(s) were not observable. No evidence of an isolation PASS was claimed.
- The wrapper was corrected to parse **only the self-authored canary JSON**, retain sanitized boolean check outcomes and failed predicate names, and continue to block. Raw Docker stdout/stderr and secrets are not exposed. A new unit test covers this fail-closed diagnostic path.
- A second CI run must identify the concrete failure(s), which must then be fixed without removing or downgrading an isolation check.

### Live CI iteration 2 — startup failure remains blocked

- Run [`45045980285`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45045980285), commit `94ce8e6`, **FAILED** after the unit, Go compilation and offline image-build steps passed.
- The updated diagnostic parser confirmed the child did **not** return a valid canary JSON result, hence `docker_container_start_or_runtime_failed`; no isolation predicate could yet be assessed.
- The fail-closed host wrapper was updated again to print only one bounded, sanitized Docker startup error line, with local paths and credential-assignment values redacted. A new test verifies this behavior.
- The metadata refresh trigger now explicitly excludes stand-alone sandbox canary source/runner changes, to avoid redundant full-library refreshes while iterating on the containment test. That change to the refresh workflow itself still triggers one regular refresh.

### Live CI iteration 3 — Docker startup incompatibility identified

- Run [`45046187857`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45046187857) **FAILED** with a Docker daemon validation error: `docker: --pid: invalid PID mode`. The canary had not launched; no isolation claim could be made.
- The Docker CLI does not accept `--pid private`; a private PID namespace is its default. The explicit unsupported flag was removed, while the benign Go canary was strengthened with `private_pid_namespace_verified = (os.Getpid() == 1)` to check real runtime isolation. No security check was waived.
- Full local regression suite after this fix: **234 tests and 6 subtests passed**; the static Linux Go canary also rebuilt successfully. The next live CI run will decide whether remaining isolation checks actually hold on Ubuntu.

### Live CI iteration 4 — three predicates identified, no false PASS

- Run [`45046313367`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45046313367) **FAILED** after successfully starting the benign Docker container. Its checks confirmed read-only root/fixture, denied external network sockets, dropped capabilities, Seccomp, no-new-privileges, unprivileged UID/GID, PID namespace isolation, scratch-space quota, and CPU/RAM/PID cgroup limits.
- Three predicates did not pass: `network_namespace_has_only_loopback` and `scratch_tmpfs_restricted_mount` were **absent from the Go entrypoint's checks map** (helpers existed but were not wired); `no_unexpected_environment` was false because an implicit/expected container environment was not accounted for.
- Wired the first two checks to their actual runtime filesystem/network probes. Strengthened root/fixture Read-only checks to require `/proc/self/mountinfo` mount flags, not just failed writes.
- Set `HOME=/nonexistent` explicitly in the container environment and required exactly that safe value. Other unexpected environment variables remain disallowed. Added a source-to-wrapper test asserting that every required check name is registered in the Go entrypoint to prevent silent omissions.
- Previous runner results remain **failed** and must not be recast as successful. A fresh Linux CI run is required before making a verified isolation claim.

### Live CI iteration 5 — all 18 runtime checks verified

- Live workflow [run `45046458532`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45046458532), source commit `2c98a58`, **completed / SUCCESS** on ephemeral `ubuntu-24.04`.
- Self-authored Go canary compiled locally and packaged in a `FROM scratch` image **without image pulls or build network**.
- Docker started the benign canary with an immutable local image ID `sha256:1f764569680d441eebed1eb1d1abdf4d78844b6ce11a1a538e962e177ad58fc6` and a matching source SHA-256 `634b1ec36a455fb369e394e017d6c4313cc5eb48ecfead4bfdbf4c701b67eeb0`.
- All **18** checks reported `true`: `capabilities_dropped`, `cpu_cgroup_bounded`, `fixture_symlink_cannot_escape_to_host`, `memory_cgroup_bounded`, `network_access_denied`, `network_namespace_has_only_loopback`, `no_docker_socket_or_host_home`, `no_new_privileges`, `no_unexpected_environment`, `pids_cgroup_bounded`, `pinned_read_only_input`, `private_pid_namespace_verified`, `root_filesystem_read_only`, `scratch_size_bounded`, `scratch_tmpfs_restricted_mount`, `scratch_writable`, `seccomp_filter_active`, and `unprivileged_uid_gid`.
- `third_party_code_executed=false`, `sandbox_execution_enabled=false`, `skill_installation_allowed=false`, `host_runtime_isolation_proven=false`. The latter remains false because a finite set of canary tests is not an adversarial escape-proof guarantee.
- The earlier CI failures are preserved above to make the correction and final verification traceable. No failing security predicate was removed or bypassed.

## 8. Separate Metadata CI race observed

The distinct scheduled/source-catalog workflow [run `45046187882`](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45046187882) passed its discovery/index/tests but failed at metadata publication because the user's `main` branch advanced concurrently. GitHub rejected the non-fast-forward push as intended. The workflow was updated to keep **non-forced** publication and, if the branch advances, explicitly warn/skip stale metadata with a GitHub summary; it must still error if remote history is unexpectedly rewritten. This does not change the independent Sandbox canary outcome.
