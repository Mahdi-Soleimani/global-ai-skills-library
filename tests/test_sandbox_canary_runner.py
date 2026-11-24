import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from sandbox_canary_runner import (
    EXPECTED_CHECKS, SOURCE, _image_is_verified_local_canary,
    _make_run_command, _run_locally_built_canary, run_benign_canary,
)

IMAGE_ID = 'sha256:' + 'a' * 64
SOURCE_HASH = hashlib.sha256(SOURCE.read_bytes()).hexdigest()


def image_details(source_hash=SOURCE_HASH):
    return {
        'Id': IMAGE_ID,
        'Config': {
            'User': '65532:65532',
            'Entrypoint': ['/canary'],
            'Labels': {
                'org.gasl.inert-canary': 'v1',
                'org.gasl.canary-source-sha256': source_hash,
            },
        },
        'RootFS': {'Type': 'layers', 'Layers': ['sha256:' + 'b' * 64]},
    }


def inert_canary_output(changes=None):
    checks = {name: True for name in EXPECTED_CHECKS}
    checks.update(changes or {})
    return json.dumps({'schema_version': 'gasl-inert-canary-1',
                       'passed': all(checks.values()),
                       'checks': checks,
                       'third_party_code_executed': False, 'skills_installed': False})


class SandboxCanaryRunnerTests(unittest.TestCase):
    def test_public_entrypoint_rejects_even_pinned_external_image(self):
        runner=Mock(side_effect=AssertionError("No external image execution"))
        compiler=Mock(side_effect=AssertionError("No compilation"))
        report=run_benign_canary(IMAGE_ID,system="Linux",runner=runner,compiler=compiler)
        self.assertEqual(report["reason_code"],"external_canary_image_not_accepted_build_locally")
        runner.assert_not_called()
        compiler.assert_not_called()

    def test_local_build_only_and_cleanup(self):
        calls=[]
        def compiler(argv,**kw):
            self.assertEqual(kw["env"]["GOPROXY"],"off")
            self.assertEqual(kw["env"]["CGO_ENABLED"],"0")
            self.assertEqual(Path(argv[-1]).read_bytes(),SOURCE.read_bytes())
            Path(argv[argv.index("-o")+1]).write_bytes(b"INERT FIXTURE BINARY")
            return subprocess.CompletedProcess(argv,0,"","")
        def runner(argv,**kw):
            calls.append(argv)
            if argv[1:3]==["container","ls"]:
                return subprocess.CompletedProcess(argv,0,"","")
            if argv[1]=="build":
                self.assertIn("--network=none",argv)
                self.assertIn("--pull=false",argv)
                self.assertEqual(set(x.name for x in Path(argv[-1]).iterdir()),{"Dockerfile","canary"})
                Path(argv[argv.index("--iidfile")+1]).write_text(IMAGE_ID)
                return subprocess.CompletedProcess(argv,0,"","")
            if argv[1]=="version":
                return subprocess.CompletedProcess(argv,0,"29.0.1","")
            if argv[1:3]==["image","inspect"]:
                return subprocess.CompletedProcess(argv,0,json.dumps(image_details()),"")
            if argv[1]=="run":
                self.assertEqual(argv[-1],IMAGE_ID)
                return subprocess.CompletedProcess(argv,0,inert_canary_output(),"")
            if argv[1:3]==["image","ls"]:
                tag=calls[0][calls[0].index("-t")+1]
                removed=any(c[1:3]==["image","rm"] for c in calls)
                return subprocess.CompletedProcess(argv,0,"" if removed else tag+"\n","")
            if argv[1:3]==["image","rm"]:
                self.assertEqual(argv[-1],calls[0][calls[0].index("-t")+1])
                return subprocess.CompletedProcess(argv,0,"","")
            self.fail("Unexpected subcommand")
        result=run_benign_canary(system="Linux",docker_bin="/usr/bin/docker",go_bin="/usr/bin/go",
                                 runner=runner,compiler=compiler)
        self.assertTrue(result["benign_canary_verified"])
        self.assertTrue(result["local_source_build_performed"])
        self.assertTrue(result["local_build_tag_removed"])
        self.assertFalse(result["external_image_accepted"])
        self.assertFalse(result["sandbox_execution_enabled"])

    def test_every_required_check_is_registered_in_actual_go_entrypoint(self):
        source = SOURCE.read_text(encoding='utf-8')
        for name in sorted(EXPECTED_CHECKS):
            self.assertIn('checks["{}"]'.format(name), source)

    def test_does_not_run_anything_on_macos(self):
        runner = Mock(side_effect=AssertionError('no Docker subprocess allowed'))
        result = _run_locally_built_canary(IMAGE_ID, docker_bin='/usr/bin/docker', system='Darwin', runner=runner)
        self.assertEqual(result['reason_code'], 'requires_ephemeral_linux_runner_not_local_mac')
        self.assertFalse(result['benign_canary_verified'])
        runner.assert_not_called()

    def test_unpinned_image_rejected_before_process_launch(self):
        runner = Mock(side_effect=AssertionError('no Docker subprocess allowed'))
        result = _run_locally_built_canary('inert-canary:latest', docker_bin='/usr/bin/docker', system='Linux', runner=runner)
        self.assertEqual(result['reason_code'], 'immutable_local_image_id_required')
        runner.assert_not_called()

    def test_wrong_source_hash_rejected(self):
        self.assertFalse(_image_is_verified_local_canary(image_details('0' * 64), IMAGE_ID, SOURCE_HASH))
        self.assertFalse(_image_is_verified_local_canary({**image_details(), 'Id': 'sha256:' + 'c' * 64}, IMAGE_ID, SOURCE_HASH))

    def test_canary_command_has_strict_resource_isolation(self):
        argv = _make_run_command('/usr/bin/docker', IMAGE_ID, '/tmp/fixture', 'gasl-safe-fixture')
        arguments = ' '.join(argv)
        for term in ('--pull never', '--network none', '--read-only', '--cap-drop ALL',
                     '--security-opt no-new-privileges:true', '--memory 128m',
                     '--memory-swap 128m', '--cpus 0.5', '--pids-limit 64',
                     '--user 65532:65532', '--ipc private',
                     '--cgroupns private', '--entrypoint /canary',
                     '--tmpfs /tmp:rw,nosuid,nodev,noexec,size=8m,mode=1777',
                     '--env HOME=/nonexistent',
                     '--mount type=bind,src=/tmp/fixture,dst=/skill,readonly'):
            self.assertIn(term, arguments)
        self.assertEqual(argv[-1], IMAGE_ID)
        self.assertNotIn('--privileged', argv)
        self.assertNotIn('--pid', argv)  # Docker defaults to private; Go canary checks PID 1.
        self.assertNotIn('/var/run/docker.sock', arguments)
        self.assertNotIn('bash', argv)

    def test_connected_daemon_and_verified_inert_canary_success(self):
        calls = []
        def runner(argv, **kwargs):
            if argv[1:3] == ["container","ls"]:
                return subprocess.CompletedProcess(argv,0,"","")
            calls.append((argv, kwargs))
            self.assertEqual(kwargs['env']['HOME'], '/nonexistent')
            if argv[1] == 'version':
                return subprocess.CompletedProcess(argv, 0, '29.0.1\n', '')
            if argv[1:3] == ['image', 'inspect']:
                return subprocess.CompletedProcess(argv, 0, json.dumps(image_details()), '')
            if argv[1] == 'run':
                self.assertTrue(kwargs['timeout'] <= 25)
                fixture = next(item for item in argv if item.startswith('type=bind,src='))
                source = Path(fixture.split('src=', 1)[1].split(',dst=', 1)[0])
                self.assertEqual((source / 'pinned.txt').read_text(), 'GASL_INERT_TEST_FIXTURE_V1\n')
                self.assertTrue((source / 'escape-to-host').is_symlink())
                return subprocess.CompletedProcess(argv, 0, inert_canary_output(), '')
            self.fail('unexpected Docker subcommand: {}'.format(argv))
        result = _run_locally_built_canary(IMAGE_ID, docker_bin='/usr/bin/docker', system='Linux', runner=runner)
        self.assertEqual(result['status'], 'benign_canary_verified')
        self.assertTrue(result['benign_canary_verified'])
        self.assertEqual(set(result['checks']), EXPECTED_CHECKS)
        self.assertEqual([args[0][1] for args in calls], ['version', 'image', 'run'])
        self.assertFalse(result['sandbox_execution_enabled'])
        self.assertFalse(result['skill_installation_allowed'])
        self.assertFalse(result['host_runtime_isolation_proven'])

    def test_nonzero_canary_exposes_only_failed_predicate_names(self):
        def runner(argv, **kwargs):
            if argv[1:3] == ["container","ls"]:
                return subprocess.CompletedProcess(argv,0,"","")
            if argv[1] == 'version':
                return subprocess.CompletedProcess(argv, 0, '29.0.1\n', '')
            if argv[1] == 'image':
                return subprocess.CompletedProcess(argv, 0, json.dumps(image_details()), '')
            return subprocess.CompletedProcess(argv, 1,
                inert_canary_output({'scratch_tmpfs_restricted_mount': False}), '')
        result = _run_locally_built_canary(IMAGE_ID, docker_bin='/usr/bin/docker', system='Linux', runner=runner)
        self.assertEqual(result['reason_code'], 'benign_isolation_checks_failed')
        self.assertEqual(result['failed_checks'], ['scratch_tmpfs_restricted_mount'])
        self.assertFalse(result['benign_canary_verified'])
        self.assertFalse(result['sandbox_execution_enabled'])

    def test_failed_check_never_enables_sandbox(self):
        def runner(argv, **kwargs):
            if argv[1:3] == ["container","ls"]:
                return subprocess.CompletedProcess(argv,0,"","")
            if argv[1] == 'version':
                return subprocess.CompletedProcess(argv, 0, '29.0.1\n', '')
            if argv[1] == 'image':
                return subprocess.CompletedProcess(argv, 0, json.dumps(image_details()), '')
            return subprocess.CompletedProcess(argv, 0,
                json.dumps({'schema_version': 'gasl-inert-canary-1', 'passed': True,
                            'checks': {**{x: True for x in EXPECTED_CHECKS}, 'network_access_denied': False},
                            'third_party_code_executed': False, 'skills_installed': False}), '')
        result = _run_locally_built_canary(IMAGE_ID, docker_bin='/usr/bin/docker', system='Linux', runner=runner)
        self.assertEqual(result['reason_code'], 'canary_report_contains_failures_or_missing_checks')
        self.assertFalse(result['benign_canary_verified'])

    def test_daemon_unreachable_blocks(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 1, '', 'daemon down'))
        result = _run_locally_built_canary(IMAGE_ID, docker_bin='/usr/bin/docker', system='Linux', runner=runner)
        self.assertEqual(result['reason_code'], 'docker_daemon_unreachable')
        self.assertEqual(runner.call_count, 1)

    def test_timeout_attempts_force_cleanup(self):
        commands = []
        def runner(argv, **kwargs):
            commands.append(argv)
            if argv[1:3] == ["container","ls"]:
                run=next(c for c in commands if c[1]=="run")
                name=run[run.index("--name")+1]
                removed=any(c[1]=="rm" for c in commands)
                return subprocess.CompletedProcess(argv,0,"" if removed else name+"\n","")
            if argv[1] == 'version':
                return subprocess.CompletedProcess(argv, 0, '29.0.1\n', '')
            if argv[1] == 'image':
                return subprocess.CompletedProcess(argv, 0, json.dumps(image_details()), '')
            if argv[1] == 'run':
                raise subprocess.TimeoutExpired(argv, 25)
            if argv[1] == 'rm':
                return subprocess.CompletedProcess(argv, 0, '', '')
            self.fail('unexpected Docker subcommand')
        result = _run_locally_built_canary(IMAGE_ID, docker_bin='/usr/bin/docker', system='Linux', runner=runner)
        self.assertEqual(result['reason_code'], 'canary_timeout_container_cleanup_verified')
        self.assertTrue(result['container_cleanup_verified'])
        self.assertIn('--force', next(c for c in commands if c[1]=='rm'))
        self.assertEqual(commands[-1][1:3],['container','ls'])

    def test_cleanup_failure_blocks_even_passing_canary(self):
        def runner(argv,**kwargs):
            if argv[1]=="version":
                return subprocess.CompletedProcess(argv,0,"29.0.1","")
            if argv[1:3]==["image","inspect"]:
                return subprocess.CompletedProcess(argv,0,json.dumps(image_details()),"")
            if argv[1]=="run":
                return subprocess.CompletedProcess(argv,0,inert_canary_output(),"")
            if argv[1:3]==["container","ls"]:
                return subprocess.CompletedProcess(argv,1,"","unreachable")
            self.fail("Unexpected subcommand")
        result=_run_locally_built_canary(IMAGE_ID,system="Linux",docker_bin="/usr/bin/docker",runner=runner)
        self.assertEqual(result["reason_code"],"canary_container_cleanup_unverified")
        self.assertFalse(result["benign_canary_verified"])
        self.assertFalse(result["sandbox_execution_enabled"])

    def test_container_start_error_redacts_paths_and_tokens(self):
        def runner(argv, **kwargs):
            if argv[1:3] == ["container","ls"]:
                return subprocess.CompletedProcess(argv,0,"","")
            if argv[1] == 'version':
                return subprocess.CompletedProcess(argv, 0, '29.0.1\n', '')
            if argv[1] == 'image':
                return subprocess.CompletedProcess(argv, 0, json.dumps(image_details()), '')
            return subprocess.CompletedProcess(argv, 125, '',
                'docker: failed to mount /home/runner/work/project token=VERY_PRIVATE_SECRET\n')
        result = _run_locally_built_canary(IMAGE_ID, docker_bin='/usr/bin/docker', system='Linux', runner=runner)
        self.assertEqual(result['reason_code'], 'docker_container_start_or_runtime_failed')
        self.assertIn('failed to mount', result['sanitized_docker_error'])
        self.assertNotIn('/home/runner/work', result['sanitized_docker_error'])
        self.assertNotIn('VERY_PRIVATE_SECRET', result['sanitized_docker_error'])
        self.assertFalse(result['sandbox_execution_enabled'])

    def test_invalid_runtime_json_blocks(self):
        def runner(argv, **kwargs):
            if argv[1:3] == ["container","ls"]:
                return subprocess.CompletedProcess(argv,0,"","")
            if argv[1] == 'version':return subprocess.CompletedProcess(argv, 0, '29.0.1\n', '')
            if argv[1] == 'image':return subprocess.CompletedProcess(argv, 0, json.dumps(image_details()), '')
            return subprocess.CompletedProcess(argv, 0, 'invalid JSON', '')
        result = _run_locally_built_canary(IMAGE_ID, docker_bin='/usr/bin/docker', system='Linux', runner=runner)
        self.assertEqual(result['reason_code'], 'invalid_canary_result')


if __name__ == '__main__':
    unittest.main()
