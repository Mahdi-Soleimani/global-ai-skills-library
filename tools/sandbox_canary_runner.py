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
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tools' / 'sandbox_canary' / 'main.go'
IMAGE_RE = re.compile(r'^sha256:[0-9a-f]{64}$')
EXPECTED_CHECKS = frozenset((
    'pinned_read_only_input', 'root_filesystem_read_only', 'network_access_denied',
    'network_namespace_has_only_loopback', 'scratch_tmpfs_restricted_mount',
    'private_pid_namespace_verified',
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
        docker_bin, 'run', '--rm', '--pull', 'never', '--no-healthcheck',
        '--name', container_name, '--hostname', 'gasl-inert-canary',
        '--network', 'none', '--read-only',
        '--mount', 'type=bind,src={},dst=/skill,readonly'.format(fixture_dir),
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=8m,mode=1777',
        '--user', '65532:65532', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges:true',
        '--memory', '128m', '--memory-swap', '128m',
        '--cpus', '0.5', '--pids-limit', '64',
        '--ulimit', 'nofile=256:256', '--ulimit', 'core=0:0',
        '--ipc', 'private', '--cgroupns', 'private',
        '--workdir', '/', '--env', 'GASL_CANARY=INERT_ONLY',
        '--env', 'HOME=/nonexistent',
        '--entrypoint', '/canary', image_id,
    ]


def _cleanup_container(docker_bin, name, runner):
    """Verify absence; remove only this invocation's random container name."""
    def listed():
        return _run([docker_bin,"container","ls","-a","--filter","name=^/"+name+"$",
                     "--format","{{.Names}}"],runner=runner,timeout=8)
    try:
        before=listed()
        names=(before.stdout or "").splitlines()
        if before.returncode!=0:
            return False
        if not names:
            return True
        if names!=[name]:
            return False
        _run([docker_bin,"rm","--force",name],runner=runner,timeout=8)
        after=listed()
        return after.returncode==0 and not (after.stdout or "").strip()
    except (OSError,subprocess.TimeoutExpired):
        return False


def _run_locally_built_canary(image_id, *, docker_bin=None, system=None, runner=subprocess.run):
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
            container_name = 'gasl-inert-canary-'+uuid.uuid4().hex
            argv = _make_run_command(docker_bin, image_id, str(fixture_dir), container_name)
            failed = None
            try:
                executed = _run(argv, runner=runner, timeout=25)
            except subprocess.TimeoutExpired:
                failed = 'canary_timeout_container_cleanup_verified'
            except OSError:
                failed = 'canary_launch_failed'
            finally:
                cleaned = _cleanup_container(docker_bin,container_name,runner)
            if not cleaned:
                return _empty_result('canary_container_cleanup_unverified')
            if failed:
                return {**_empty_result(failed),'container_cleanup_verified':True}
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
                'container_cleanup_verified': True,
            })
            return result
    except (OSError, subprocess.TimeoutExpired):
        return _empty_result('docker_probe_failed_or_timed_out')


def run_benign_canary(image_id=None, *, docker_bin=None, system=None, runner=subprocess.run,
                      go_bin=None, compiler=subprocess.run):
    """Build from this checkout and run only the resulting local inert image.

    An external image ID and self-asserted labels are not trusted provenance.
    The local OS, compiler, Docker daemon and checked-out GASL code remain trusted
    components of this explicitly requested Linux-only diagnostic.
    """
    if system is None:
        system = platform.system()
    if system != "Linux":
        return _empty_result("requires_ephemeral_linux_runner_not_local_mac")
    if image_id is not None:
        return _empty_result("external_canary_image_not_accepted_build_locally")
    docker_bin = docker_bin or shutil.which("docker")
    go_bin = go_bin or shutil.which("go")
    if not docker_bin:
        return _empty_result("docker_client_unavailable")
    if not go_bin:
        return _empty_result("local_go_compiler_unavailable")
    try:
        source = SOURCE.read_bytes()
        dockerfile = SOURCE.with_name("Dockerfile").read_bytes()
    except OSError:
        return _empty_result("trusted_canary_source_missing")
    source_digest = hashlib.sha256(source).hexdigest()
    # Never use a caller-supplied build context or Dockerfile. The trusted
    # checkout contains the self-authored program and FROM scratch Dockerfile.
    tag = "gasl-inert-canary:local-"+uuid.uuid4().hex
    build_attempted = False
    result = _empty_result("local_canary_build_failed")
    try:
        with tempfile.TemporaryDirectory(prefix="gasl-canary-build-") as temporary:
            folder = Path(temporary)
            (folder/"main.go").write_bytes(source)
            (folder/"Dockerfile").write_bytes(dockerfile)
            binary = folder/"canary"
            env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME":str(folder),
                   "GOCACHE":str(folder/"go-cache"), "GOPATH":str(folder/"go-path"),
                   "GOENV":"off","GOWORK":"off","GOFLAGS":"","GO111MODULE":"off",
                   "GOTOOLCHAIN":"local","GOPROXY":"off","GOSUMDB":"off",
                   "CGO_ENABLED":"0","GOOS":"linux"}
            compiled = compiler([go_bin,"build","-trimpath","-buildvcs=false","-ldflags=-s -w",
                                 "-o",str(binary),str(folder/"main.go")],
                                cwd=folder,env=env,capture_output=True,text=True,timeout=180,check=False)
            if compiled.returncode or not binary.is_file() or binary.stat().st_size>16*1024*1024:
                return _empty_result("local_canary_compile_failed")
            binary_hash=hashlib.sha256(binary.read_bytes()).hexdigest()
            context=folder/"context"
            context.mkdir()
            binary.rename(context/"canary")
            (folder/"Dockerfile").rename(context/"Dockerfile")
            iid=folder/"image-id"
            # Unique tag and immutable ID from the same build; only our two
            # trusted files are in the context. No dependency download or pull.
            build_attempted=True
            build=_run([docker_bin,"build","--pull=false","--network=none","--no-cache",
                        "--iidfile",str(iid),"--build-arg","CANARY_SOURCE_SHA="+source_digest,
                        "-t",tag,str(context)],runner=runner,timeout=120)
            if build.returncode:
                result=_empty_result("local_canary_image_build_failed")
            elif not iid.is_file() or iid.stat().st_size>128:
                result=_empty_result("local_canary_image_id_missing")
            else:
                local_id=iid.read_text(encoding="ascii").strip()
                if (not IMAGE_RE.fullmatch(local_id) or SOURCE.read_bytes()!=source
                        or SOURCE.with_name("Dockerfile").read_bytes()!=dockerfile):
                    result=_empty_result("local_canary_image_id_or_source_changed")
                else:
                    result=_run_locally_built_canary(local_id,docker_bin=docker_bin,
                        system=system,runner=runner)
                    result.update({"local_source_build_performed":True,
                                   "canary_binary_sha256":binary_hash,
                                   "external_image_accepted":False})
    except (OSError,ValueError,subprocess.TimeoutExpired):
        result=_empty_result("local_canary_build_or_probe_failed")
    finally:
        if build_attempted:
            try:
                def listed():
                    return _run([docker_bin,"image","ls","--filter","reference="+tag,
                                 "--format","{{.Repository}}:{{.Tag}}"],runner=runner,timeout=12)
                listing=listed()
                names=(listing.stdout or "").splitlines()
                cleaned=listing.returncode==0 and not names
                if listing.returncode==0 and names==[tag]:
                    cleanup=_run([docker_bin,"image","rm",tag],runner=runner,timeout=12)
                    after=listed()
                    cleaned=cleanup.returncode==0 and after.returncode==0 and not (after.stdout or "").strip()
            except (OSError,subprocess.TimeoutExpired):
                cleaned=False
            result["local_build_tag_removed"]=cleaned
            if not cleaned:
                result.update(status="blocked",reason_code="local_build_tag_cleanup_failed",
                              benign_canary_verified=False)
    return result


def main():
    parser = argparse.ArgumentParser(description='GASL inert Docker sandbox canary (NOT a Skill runner)')
    parser.add_argument('--image-id', help='Deprecated: external images are refused; omit to build locally')
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
