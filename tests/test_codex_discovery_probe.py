"""Phase 23: Codex JSON-RPC discovery with generated inert fake Host binaries."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from codex_discovery_probe import (
    _extract_exact_skill, _minimal_environment, SKILL_BODY, SKILL_NAME,
    verify_codex_discovery as _verify_codex_discovery,
)


def _fixture_popen(args, **kwargs):
    # Execute the authored fixture with the current Python on Windows, where
    # CreateProcess cannot launch a plain script with a POSIX shebang.
    if os.name == 'nt':
        args = [sys.executable, '-I', '-B', *args]
    return subprocess.Popen(args, **kwargs)


def verify_codex_discovery(binary, **kwargs):
    return _verify_codex_discovery(binary, popen=_fixture_popen, **kwargs)


class CodexDiscoveryProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='gasl-fake-codex-host-')
        self.addCleanup(self.tmp.cleanup)
        self.bin = Path(self.tmp.name) / 'codex-fake'

    def _fake_codex(self, *, mode='expected', capture=None):
        script = textwrap.dedent('''\
            #!/usr/bin/env python3
            import json, os, sys
            if sys.argv[1:] != ['app-server']:
                sys.exit(33)
            first = json.loads(sys.stdin.readline())
            if first['method'] != 'initialize':
                sys.exit(34)
            print(json.dumps({'id':0,'result':{'userAgent':'fake-host-test'}}), flush=True)
            notification = json.loads(sys.stdin.readline())
            assert notification['method'] == 'initialized'
            listed = json.loads(sys.stdin.readline())
            assert listed['method'] == 'skills/list'
            assert listed['params']['forceReload'] is True
            cwd = listed['params']['cwds'][0]
            path = os.path.join(cwd, '.agents', 'skills', 'gasl-discovery-probe', 'SKILL.md')
            assert os.path.exists(path)
            with open(path, 'rb') as f:
                assert f.read() == %r
            if %r:
                with open(%r, 'w', encoding='utf-8') as f:
                    json.dump({'env_keys':sorted(os.environ.keys()),'cwd_matches':os.path.realpath(os.getcwd())==os.path.realpath(cwd),
                               'no_user_codex_home':os.path.realpath(os.environ['CODEX_HOME']).startswith(os.path.realpath(os.path.dirname(cwd)) + os.sep),
                               'no_user_home':os.path.realpath(os.environ['HOME']).startswith(os.path.realpath(os.path.dirname(cwd)) + os.sep)}, f)
            skill = {'name':'gasl-discovery-probe','path':path,'enabled':True}
            mode = %r
            if mode == 'wrong_path':
                skill['path'] = '/not/our/skill/SKILL.md'
            if mode == 'disabled':
                skill['enabled'] = False
            if mode == 'duplicate':
                skills = [skill, skill]
            elif mode == 'missing':
                skills = []
            else:
                skills = [skill]
            if mode == 'error':
                output = {'id':1,'error':{'message':'blocked'}}
            elif mode == 'broken_json':
                sys.stdout.write('not-json\\n');sys.stdout.flush();sys.exit(0)
            else:
                output = {'id':1,'result':{'data':[{'cwd':cwd,'skills':skills,'errors':[]}]}}
            print(json.dumps(output), flush=True)
            sys.stdin.read()
        ''' % (SKILL_BODY, bool(capture), str(capture), mode))
        self.bin.write_text(script, encoding='utf-8')
        self.bin.chmod(self.bin.stat().st_mode | stat.S_IXUSR)
        return self.bin

    def test_valid_discovery_with_real_json_rpc_process_and_sanitized_result(self):
        evidence = Path(self.tmp.name) / 'fake-host-environment.json'
        binary = self._fake_codex(capture=evidence)
        report = verify_codex_discovery(binary)
        self.assertEqual(report['status'], 'verified_isolated_codex_discovery')
        self.assertTrue(report['isolated_skill_discovery_verified'])
        self.assertEqual(report['reason_code'], 'exact_inert_skill_discovered')
        self.assertFalse(report['model_turn_started'])
        self.assertFalse(report['third_party_skill_executed'])
        self.assertFalse(report['real_host_files_modified'])
        self.assertFalse(report['production_installation_enabled'])
        self.assertNotIn(str(self.tmp.name), json.dumps(report))
        evidence_data = json.loads(evidence.read_text())
        self.assertTrue(evidence_data['cwd_matches'])
        self.assertTrue(evidence_data['no_user_codex_home'])
        self.assertTrue(evidence_data['no_user_home'])
        self.assertNotIn('OPENAI_API_KEY', evidence_data['env_keys'])
        self.assertNotIn('GITHUB_TOKEN', evidence_data['env_keys'])

    def test_missing_skill_never_counts_as_verified(self):
        report = verify_codex_discovery(self._fake_codex(mode='missing'))
        self.assertFalse(report['isolated_skill_discovery_verified'])
        self.assertEqual(report['reason_code'], 'expected_inert_skill_not_found')

    def test_unexpected_skill_path_is_not_accepted(self):
        report = verify_codex_discovery(self._fake_codex(mode='wrong_path'))
        self.assertFalse(report['isolated_skill_discovery_verified'])

    def test_disabled_skill_not_counted(self):
        report = verify_codex_discovery(self._fake_codex(mode='disabled'))
        self.assertFalse(report['isolated_skill_discovery_verified'])

    def test_duplicate_named_skill_not_counted(self):
        report = verify_codex_discovery(self._fake_codex(mode='duplicate'))
        self.assertFalse(report['isolated_skill_discovery_verified'])

    def test_host_rpc_error_fails_closed(self):
        report = verify_codex_discovery(self._fake_codex(mode='error'))
        self.assertEqual(report['reason_code'], 'codex_skills_list_error')

    def test_malformed_rpc_is_not_discovery(self):
        report = verify_codex_discovery(self._fake_codex(mode='broken_json'))
        self.assertEqual(report['reason_code'], 'codex_protocol_unavailable_or_invalid')

    def test_partial_protocol_line_cannot_hang_probe(self):
        self.bin.write_text(
            '#!/usr/bin/env python3\nimport sys,time\nsys.stdin.readline()\n'
            'sys.stdout.write("{");sys.stdout.flush()\ntime.sleep(30)\n',
            encoding='utf-8')
        self.bin.chmod(self.bin.stat().st_mode | stat.S_IXUSR)
        start = time.monotonic()
        report = verify_codex_discovery(self.bin, timeout=1)
        self.assertFalse(report['isolated_skill_discovery_verified'])
        self.assertEqual(report['reason_code'], 'codex_protocol_unavailable_or_invalid')
        self.assertLess(time.monotonic() - start, 8)

    def test_oversized_protocol_output_fails_closed(self):
        self.bin.write_text(
            '#!/usr/bin/env python3\nimport sys\nsys.stdin.readline()\n'
            'print("X" * (3 * 1024 * 1024),flush=True)\n',
            encoding='utf-8')
        self.bin.chmod(self.bin.stat().st_mode | stat.S_IXUSR)
        report = verify_codex_discovery(self.bin, timeout=10)
        self.assertFalse(report['isolated_skill_discovery_verified'])
        self.assertEqual(report['reason_code'], 'codex_protocol_unavailable_or_invalid')

    def test_missing_or_relative_or_symlink_executable_is_blocked(self):
        for invalid in ('codex', Path(self.tmp.name)/'nonexistent'):
            with self.subTest(path=invalid):
                self.assertEqual(verify_codex_discovery(invalid)['reason_code'],
                                 'absolute_local_codex_executable_required')
        binary = self._fake_codex()
        link = Path(self.tmp.name) / 'alias'
        try:
            link.symlink_to(binary)
        except OSError as exc:
            if os.name == 'nt' and getattr(exc, 'winerror', None) == 1314:
                self.skipTest('Windows runner cannot create a disposable symbolic link')
            raise
        self.assertEqual(verify_codex_discovery(link)['reason_code'],
                         'absolute_local_codex_executable_required')

    @unittest.skipUnless(os.name == 'nt', 'Windows live Host gate')
    def test_native_windows_vendor_launch_remains_gated(self):
        report = _verify_codex_discovery(self._fake_codex())
        self.assertEqual(report['reason_code'], 'windows_live_host_probe_not_yet_verified')
        self.assertFalse(report['isolated_skill_discovery_verified'])

    def test_protocol_parser_rejects_unstructured_response(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'project'
            skill = project / 'file'
            for payload in ({'result': None}, {'result': {'data': 'not-list'}}, {'result': {'data': []}},
                            {'error': {'message': 'fail'}}):
                with self.subTest(payload=payload):
                    if isinstance(payload.get('result'), dict) and payload['result'].get('data') == []:
                        self.assertFalse(_extract_exact_skill(payload,project,skill))
                    else:
                        with self.assertRaises(ValueError):
                            _extract_exact_skill(payload,project,skill)

    def test_secretless_environment_exact_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = _minimal_environment(root, {'PATH':'/usr/bin','OPENAI_API_KEY':'SENSITIVE',
                                               'GITHUB_TOKEN':'SENSITIVE','HOME':'/real/user'})
            self.assertEqual(env['PATH'], '/usr/bin')
            keys = {'PATH','HOME','CODEX_HOME','XDG_CONFIG_HOME',
                    'XDG_CACHE_HOME','TMPDIR','CI','NO_COLOR'}
            if os.name == 'nt':
                keys.update({'USERPROFILE','HOMEDRIVE','HOMEPATH','APPDATA',
                             'LOCALAPPDATA','TEMP','TMP'})
                self.assertEqual(env['USERPROFILE'], env['HOME'])
                self.assertEqual(env['TEMP'], env['TMPDIR'])
                self.assertEqual(env['APPDATA'], env['XDG_CONFIG_HOME'])
            self.assertEqual(set(env), keys)
            self.assertNotIn('SENSITIVE',str(env))
            self.assertTrue(env['HOME'].startswith(directory))


if __name__ == '__main__':
    unittest.main()
