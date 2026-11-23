"""Fake real-subprocess protocol tests; never imply actual Host Skill discovery."""
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from other_host_protocol_probe import verify_host_readiness as _verify_host_readiness, _runtime
from tests.test_codex_discovery_probe import _fixture_popen


def verify_host_readiness(host, binary, **kwargs):
    return _verify_host_readiness(host, binary, popen=_fixture_popen, **kwargs)


class OtherHostProtocolProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gasl-probe-fake-')
        self.addCleanup(self.temp.cleanup)
        self.binary = Path(self.temp.name) / 'host-fake'

    def _write(self, source):
        self.binary.write_text('#!/usr/bin/env python3\n' + source, encoding='utf-8')
        self.binary.chmod(self.binary.stat().st_mode | stat.S_IXUSR)
        return self.binary

    def test_cursor_acp_initialize_without_authentication_is_not_discovery(self):
        source = '''import json,sys,os
assert sys.argv[1:] == ['acp']
obj=json.loads(sys.stdin.readline())
assert obj['method'] == 'initialize'
assert obj['params']['clientCapabilities']['terminal'] is False
assert obj['params']['clientCapabilities']['fs']['writeTextFile'] is False
assert 'CURSOR_API_KEY' not in os.environ and 'OPENAI_API_KEY' not in os.environ
print(json.dumps({'jsonrpc':'2.0','id':1,'result':{'protocolVersion':1,'agentCapabilities':{},'authMethods':[{'id':'cursor_login'}]}}),flush=True)
'''
        result = verify_host_readiness('cursor', self._write(source))
        self.assertEqual(result['status'], 'real_host_readiness_verified')
        self.assertTrue(result['real_host_protocol_verified'])
        self.assertFalse(result['skill_discovery_verified'])
        self.assertFalse(result['authentication_performed'])
        self.assertFalse(result['model_turn_started'])
        self.assertFalse(result['real_host_files_modified'])

    def test_cursor_failure_to_initialize_is_not_discovery(self):
        for body in ("print('{}',flush=True)",
                     "print('{\"jsonrpc\":\"2.0\",\"id\":1,\"error\":{\"message\":\"authentication required\"}}',flush=True)"):
            with self.subTest(body=body):
                result = verify_host_readiness('cursor', self._write('import sys\nsys.stdin.readline()\n' + body))
                self.assertFalse(result['real_host_protocol_verified'])
                self.assertFalse(result['skill_discovery_verified'])

    def test_claude_version_only_is_not_discovery(self):
        source = '''import os,sys
assert sys.argv[1:] == ['--version']
assert 'ANTHROPIC_API_KEY' not in os.environ
assert 'HOME' in os.environ and os.path.basename(os.path.dirname(os.environ['HOME'])).startswith('gasl-host-readiness-')
print('2.1.330 (Claude Code)',flush=True)
'''
        result = verify_host_readiness('claude-code', self._write(source))
        self.assertEqual(result['host_version'], '2.1.330')
        self.assertTrue(result['real_host_protocol_verified'])
        self.assertFalse(result['skill_discovery_verified'])
        self.assertFalse(result['authentication_performed'])
        self.assertFalse(result['production_installation_enabled'])

    def test_claude_non_version_output_does_not_pass(self):
        result = verify_host_readiness('claude-code', self._write("print('not a version')"))
        self.assertEqual(result['reason_code'], 'claude_cli_version_unavailable')

    def test_claude_version_with_oversized_output_fails_closed(self):
        result = verify_host_readiness(
            'claude-code', self._write("print('2.1.330 ' + 'x' * 10000,flush=True)"))
        self.assertFalse(result['real_host_protocol_verified'])
        self.assertEqual(result['reason_code'], 'host_protocol_unavailable_or_timed_out')

    def test_invalid_binary_path_never_launches_process(self):
        for host in ('cursor', 'claude-code'):
            for path in ('./host-fake', '/never/a/real/path'):
                with self.subTest(host=host, path=path):
                    result = verify_host_readiness(host, path)
                    self.assertEqual(result['reason_code'], 'absolute_local_executable_required')
                    self.assertFalse(result['skill_discovery_verified'])

    def test_symlink_binary_rejected(self):
        binary = self._write("print('2.1.330')")
        link = binary.parent / 'other'
        try:
            link.symlink_to(binary)
        except OSError as exc:
            if os.name == 'nt' and getattr(exc, 'winerror', None) == 1314:
                self.skipTest('Windows runner cannot create a disposable symbolic link')
            raise
        result = verify_host_readiness('claude-code', link)
        self.assertEqual(result['reason_code'], 'absolute_local_executable_required')

    def test_environment_drops_credentials_and_home(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            env = _runtime(root, {'PATH':'/usr/bin','HOME':'/real/home',
                                  'CURSOR_API_KEY':'FAKE_SECRET','ANTHROPIC_API_KEY':'FAKE_SECRET'})
            self.assertNotIn('FAKE_SECRET',repr(env))
            self.assertEqual(env['HOME'], str(root/'home'))
            self.assertEqual(env['PATH'], '/usr/bin')
            self.assertNotIn('CURSOR_API_KEY',env)
            self.assertNotIn('ANTHROPIC_API_KEY',env)
            if os.name == 'nt':
                self.assertEqual(env['USERPROFILE'], str(root/'home'))
                self.assertEqual(env['APPDATA'], str(root/'xdg-config'))
                self.assertEqual(env['LOCALAPPDATA'], str(root/'xdg-cache'))
                self.assertEqual(env['TEMP'], str(root/'tmp'))

    @unittest.skipUnless(os.name == 'nt', 'Windows live Host gate')
    def test_native_windows_vendor_launch_remains_gated(self):
        report = _verify_host_readiness('claude-code', self._write("print('2.1.330')"))
        self.assertEqual(report['reason_code'], 'windows_live_host_probe_not_yet_verified')
        self.assertFalse(report['real_host_protocol_verified'])

    def test_host_name_validation_is_strict(self):
        with self.assertRaisesRegex(ValueError,'Unsupported Host'):
            verify_host_readiness('../cursor',self.binary)


if __name__=='__main__':
    unittest.main()
