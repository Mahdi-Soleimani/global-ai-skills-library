#!/usr/bin/env python3
"""CI-only, inert Docker isolation canary. No third-party Skill code is run.

The image must be built locally from tools/sandbox_canary/Dockerfile (FROM scratch)
and its self-authored static Go source. This tool does NOT install, validate,
or run a Skill. It does NOT enable GASL's production Skill execution.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tools' / 'sandbox_canary' / 'main.go'
IMAGE_RE = re.compile(r'^sha256:[0-9a-f]{64}$')
EXPECTED_CHECKS = frozenset((
    'pinned_read_only_input', 'root_filesystem_read_only', 'network_access_denied',
    'network_namespace_has_only_loopback', 'scratch_tmpfs_restricted_mount',
    'unprivileged_uid_gid', 'capabilities_dropped', 'no_new_privileges',
    'seccomp_filter_active', 'no_unexpected_environment',
    'no_docker_socket_or_host_home', 'fixture_symlink_cannot_escape_to_host',
    'scratch_writable', 'scratch_size_bounded', 'memory_cgroup_bounded',
    'pids_cgroup_bounded', 'cpu_cgroup_bounded',
))


def _empty_result(reason):
    return {
        'schema_version': 'gasl-inert-sandbox-validation-v1',
        'status': 'blocked',
        'reason_code': reason,
        'benign_canary_verified': False,
        'sandbox_execution_enabled': False,  # Actual third-party Skill execution stays disabled.
        'third_party_code_executed': False,
        'skill_installation_allowed': False,
        'host_runtime_isolation_proven': False,
        'checks': {},
    }


def _client_environment():
    # Avoid leaking host API keys or Docker credentials to subprocesses.
    # Runner supports only the local default Docker UNIX socket on Linux.
    return {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/nonexistent',
            'DOCKER_CONFIG': '/nonexistent/docker-config'}


def _run(argv, *, runner=subprocess.run, timeout=12):
    return runner(argv, capture_output=True, text=True, timeout=timeout,
                  check=False, env=_client_environment())


def _image_is_verified_local_canary(details, image_id, source_digest):
    if not isinstance(details, dict) or details.get('Id') != image_id:
        return False
    config = details.get('Config') or {}
    labels = config.get('Labels') or {}
    rootfs = details.get('RootFS') or {}
    return (labels.get('org.gasl.inert-canary') == 'v1'
            and labels.get('org.gasl.canary-source-sha256') == source_digest
            and config.get('Entrypoint') == ['/canary']
            and config.get('User') == '65532:65532'
            and rootfs.get('Type') == 'layers'
            and len(rootfs.get('Layers') or []) == 1)


def _make_run_command(docker_bin, image_id, fixture_dir, container_name):
    # This function only configures Docker; it never accepts a third-party command.
    return [
        docker_bin, 'run', '--rm', '--pull', 'never',
        '--name', container_name, '--hostname', 'gasl-inert-canary',
        '--network', 'none', '--read-only',
        '--mount', 'type=bind,src={},dst=/skill,readonly'.format(fixture_dir),
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=8m,mode=1777',
        '--user', '65532:65532', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges:true',
        '--memory', '128m', '--memory-swap', '128m',
        '--cpus', '0.5', '--pids-limit', '64',
        '--ulimit', 'nofile=256:256', '--ulimit', 'core=0:0',
        '--ipc', 'private', '--pid', 'private', '--cgroupns', 'private',
        '--workdir', '/', '--env', 'GASL_CANARY=INERT_ONLY',
        '--entrypoint', '/canary', image_id,
    ]


def run_benign_canary(image_id, *, docker_bin=None, system=None, runner=subprocess.run):
    """Run only the local GASL Go canary, never a downloaded Skill or arbitrary command.

    Uses a self-contained temp input, an immutable local image ID and a strict
    Docker profile. Even a PASS does not turn on application Skill execution.
    """
    if system is None:
        system = platform.system()
    if system != 'Linux':
        return _empty_result('requires_ephemeral_linux_runner_not_local_mac')
    if not isinstance(image_id, str) or not IMAGE_RE.fullmatch(image_id):
        return _empty_result('immutable_local_image_id_required')
    if docker_bin is None:
        docker_bin = shutil.which('docker')
    if not docker_bin:
        return _empty_result('docker_client_unavailable')
    source_digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    try:
        available = _run([docker_bin, 'version', '--format', '{{.Server.Version}}'],
                         runner=runner)
        if available.returncode != 0 or not (available.stdout or '').strip():
            return _empty_result('docker_daemon_unreachable')
        inspection = _run([docker_bin, 'image', 'inspect', image_id,
                           '--format', '{{json .}}'], runner=runner)
        if inspection.returncode != 0:
            return _empty_result('local_canary_image_not_available')
        try:
            image_data = json.loads(inspection.stdout)
        except (TypeError, json.JSONDecodeError):
            return _empty_result('invalid_image_inspection')
        if not _image_is_verified_local_canary(image_data, image_id, source_digest):
            return _empty_result('untrusted_or_mismatched_canary_image')
        with tempfile.TemporaryDirectory(prefix='gasl-inert-canary-') as scratch:
            fixture_dir = Path(scratch)
            fixture_dir.chmod(0o755)  # UID 65532 in the container may read it.
            (fixture_dir / 'pinned.txt').write_text('GASL_INERT_TEST_FIXTURE_V1\n', encoding='utf-8')
            (fixture_dir / 'pinned.txt').chmod(0o444)
            (fixture_dir / 'escape-to-host').symlink_to('/host-only-canary-secret')
            container_name = 'gasl-inert-canary-{}'.format(os.getpid())
            argv = _make_run_command(docker_bin, image_id, str(fixture_dir), container_name)
            try:
                executed = _run(argv, runner=runner, timeout=25)
            except subprocess.TimeoutExpired:
                # Timeout is not merely a reporting failure: clean up the container.
                _run([docker_bin, 'rm', '--force', container_name], runner=runner, timeout=8)
                return _empty_result('canary_timeout_container_cleanup_attempted')
            if executed.returncode != 0:
                # A failing benign canary reports only booleans, not host secrets.
                # Preserve failing check names for actionable, non-sensitive CI diagnosis.
                try:
                    failure = json.loads(executed.stdout)
                except (TypeError, json.JSONDecodeError):
                    failure = None
                if isinstance(failure, dict) and failure.get('schema_version') == 'gasl-inert-canary-1':
                    checks = failure.get('checks')
                    if isinstance(checks, dict):
                        result = _empty_result('benign_isolation_checks_failed')
                        result['checks'] = {key: value for key, value in checks.items()
                                            if key in EXPECTED_CHECKS and isinstance(value, bool)}
                        result['failed_checks'] = sorted(key for key in EXPECTED_CHECKS
                                                         if checks.get(key) is not True)
                        return result
                result = _empty_result('docker_container_start_or_runtime_failed')
                # Only a bounded, redacted Docker *error* line from the trusted CI
                # runner; never include stdout, environment, image contents or Skills.
                stderr = str(executed.stderr or '').splitlines()
                if stderr:
                    detail = stderr[0][:500]
                    detail = re.sub(r'/(?:home|tmp|Users|private)/[^\s"\']+', '<local-path>', detail)
                    detail = re.sub(r'(?i)(token|password|secret|key)=\S+', r'\1=[REDACTED]', detail)
                    result['sanitized_docker_error'] = detail[:320]
                return result
            try:
                payload = json.loads(executed.stdout)
            except (TypeError, json.JSONDecodeError):
                return _empty_result('invalid_canary_result')
            if not isinstance(payload, dict):
                return _empty_result('invalid_canary_result')
            checks = payload.get('checks')
            if (payload.get('schema_version') != 'gasl-inert-canary-1'
                    or payload.get('passed') is not True
                    or payload.get('third_party_code_executed') is not False
                    or payload.get('skills_installed') is not False
                    or not isinstance(checks, dict)
                    or set(checks) != EXPECTED_CHECKS
                    or any(value is not True for value in checks.values())):
                return _empty_result('canary_report_contains_failures_or_missing_checks')
            result = _empty_result('benign_canary_passed_on_this_ephemeral_runner')
            result.update({
                'status': 'benign_canary_verified',
                'benign_canary_verified': True,
                'checks': checks,
                'verified_local_image_id': image_id,
                'canary_source_sha256': source_digest,
                'runtime': 'linux_docker_ephemeral_ci',
            })
            return result
    except (OSError, subprocess.TimeoutExpired):
        return _empty_result('docker_probe_failed_or_timed_out')


def main():
    parser = argparse.ArgumentParser(description='GASL inert Docker sandbox canary (NOT a Skill runner)')
    parser.add_argument('--image-id', required=True, help='exact local immutable sha256 Docker image ID')
    parser.add_argument('--output', type=Path, help='optional JSON result file')
    args = parser.parse_args()
    result = run_benign_canary(args.image_id)
    data = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    print(data, end='')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding='utf-8')
    return 0 if result['benign_canary_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
