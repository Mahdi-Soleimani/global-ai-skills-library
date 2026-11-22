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
    _make_run_command, run_benign_canary,
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
    def test_does_not_run_anything_on_macos(self):
        runner = Mock(side_effect=AssertionError('no Docker subprocess allowed'))
        result = run_benign_canary(IMAGE_ID, docker_bin='/usr/bin/docker', system='Darwin', runner=runner)
        self.assertEqual(result['reason_code'], 'requires_ephemeral_linux_runner_not_local_mac')
        self.assertFalse(result['benign_canary_verified'])
        runner.assert_not_called()

    def test_unpinned_image_rejected_before_process_launch(self):
        runner = Mock(side_effect=AssertionError('no Docker subprocess allowed'))
        result = run_benign_canary('inert-canary:latest', docker_bin='/usr/bin/docker', system='Linux', runner=runner)
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
                     '--user 65532:65532', '--ipc private', '--pid private',
                     '--cgroupns private', '--entrypoint /canary',
                     '--tmpfs /tmp:rw,nosuid,nodev,noexec,size=8m,mode=1777',
                     '--mount type=bind,src=/tmp/fixture,dst=/skill,readonly'):
            self.assertIn(term, arguments)
        self.assertEqual(argv[-1], IMAGE_ID)
        self.assertNotIn('--privileged', argv)
        self.assertNotIn('/var/run/docker.sock', arguments)
        self.assertNotIn('bash', argv)

    def test_connected_daemon_and_verified_inert_canary_success(self):
        calls = []
        def runner(argv, **kwargs):
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
        result = run_benign_canary(IMAGE_ID, docker_bin='/usr/bin/docker', system='Linux', runner=runner)
        self.assertEqual(result['status'], 'benign_canary_verified')
        self.assertTrue(result['benign_canary_verified'])
        self.assertEqual(set(result['checks']), EXPECTED_CHECKS)
        self.assertEqual([args[0][1] for args in calls], ['version', 'image', 'run'])
        self.assertFalse(result['sandbox_execution_enabled'])
        self.assertFalse(result['skill_installation_allowed'])
        self.assertFalse(result['host_runtime_isolation_proven'])

    def test_failed_check_never_enables_sandbox(self):
        def runner(argv, **kwargs):
            if argv[1] == 'version':
                return subprocess.CompletedProcess(argv, 0, '29.0.1\n', '')
            if argv[1] == 'image':
                return subprocess.CompletedProcess(argv, 0, json.dumps(image_details()), '')
            return subprocess.CompletedProcess(argv, 0,
                json.dumps({'schema_version': 'gasl-inert-canary-1', 'passed': True,
                            'checks': {**{x: True for x in EXPECTED_CHECKS}, 'network_access_denied': False},
                            'third_party_code_executed': False, 'skills_installed': False}), '')
        result = run_benign_canary(IMAGE_ID, docker_bin='/usr/bin/docker', system='Linux', runner=runner)
        self.assertEqual(result['reason_code'], 'canary_report_contains_failures_or_missing_checks')
        self.assertFalse(result['benign_canary_verified'])

    def test_daemon_unreachable_blocks(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 1, '', 'daemon down'))
        result = run_benign_canary(IMAGE_ID, docker_bin='/usr/bin/docker', system='Linux', runner=runner)
        self.assertEqual(result['reason_code'], 'docker_daemon_unreachable')
        self.assertEqual(runner.call_count, 1)

    def test_timeout_attempts_force_cleanup(self):
        commands = []
        def runner(argv, **kwargs):
            commands.append(argv)
            if argv[1] == 'version':
                return subprocess.CompletedProcess(argv, 0, '29.0.1\n', '')
            if argv[1] == 'image':
                return subprocess.CompletedProcess(argv, 0, json.dumps(image_details()), '')
            if argv[1] == 'run':
                raise subprocess.TimeoutExpired(argv, 25)
            if argv[1] == 'rm':
                return subprocess.CompletedProcess(argv, 0, '', '')
            self.fail('unexpected Docker subcommand')
        result = run_benign_canary(IMAGE_ID, docker_bin='/usr/bin/docker', system='Linux', runner=runner)
        self.assertEqual(result['reason_code'], 'canary_timeout_container_cleanup_attempted')
        self.assertIn('rm', commands[-1])
        self.assertIn('--force', commands[-1])

    def test_invalid_runtime_json_blocks(self):
        def runner(argv, **kwargs):
            if argv[1] == 'version':return subprocess.CompletedProcess(argv, 0, '29.0.1\n', '')
            if argv[1] == 'image':return subprocess.CompletedProcess(argv, 0, json.dumps(image_details()), '')
            return subprocess.CompletedProcess(argv, 0, 'invalid JSON', '')
        result = run_benign_canary(IMAGE_ID, docker_bin='/usr/bin/docker', system='Linux', runner=runner)
        self.assertEqual(result['reason_code'], 'invalid_canary_result')


if __name__ == '__main__':
    unittest.main()
