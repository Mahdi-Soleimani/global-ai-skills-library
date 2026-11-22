#!/usr/bin/env python3
"""Non-executing sandbox readiness check; it NEVER runs untrusted code.

A Docker CLI/daemon is not proof of isolation. GASL must remain fail-closed
until resource, filesystem, network and no-secret guards pass real canaries.
"""
import shutil
import subprocess

REQUIRED_ENFORCEMENTS = (
    "immutable_local_image_digest_no_implicit_pull",
    "network_isolation_enforced_and_canary_tested",
    "empty_secret_environment_and_no_host_credentials",
    "no_docker_socket_or_host_home_mount",
    "read_only_root_and_read_only_pinned_skill_input",
    "unprivileged_user_all_capabilities_dropped_no_new_privileges",
    "bounded_cpu_memory_process_count_scratch_space_and_wall_time",
    "filesystem_escape_and_symlink_canary_tested",
    "explicit_per_skill_user_approval_and_auditable_cleanup",
)


def sandbox_status(docker_path=None, runner=None):
    """Inspect Docker availability only: no pull, container, script, or Skill run."""
    if docker_path is None:
        docker_path = shutil.which("docker")
    if runner is None:
        runner = subprocess.run
    result = {
        "status": "blocked",
        "backend": "docker_isolated_container_candidate",
        "docker_cli_available": bool(docker_path),
        "docker_daemon_available": False,
        "isolation_canary_verified": False,
        "sandbox_execution_enabled": False,
        "third_party_code_executed": False,
        "installation_allowed": False,
        "requirements": list(REQUIRED_ENFORCEMENTS),
        "host_sandbox_exec_accepted_as_verified_boundary": False,
        "reason_code": "docker_client_unavailable",
    }
    if not docker_path:
        return result
    try:
        call = runner([docker_path, "version", "--format", "{{.Server.Version}}"],
                      capture_output=True, text=True, timeout=6, check=False)
    except (OSError, subprocess.TimeoutExpired):
        result["reason_code"] = "docker_daemon_unreachable"
        return result
    if call.returncode != 0 or not str(call.stdout).strip():
        result["reason_code"] = "docker_daemon_unreachable"
        return result
    result["docker_daemon_available"] = True
    result["reason_code"] = "isolation_canary_and_policy_not_verified"
    return result
