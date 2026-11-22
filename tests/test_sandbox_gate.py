import sys
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from sandbox_gate import REQUIRED_ENFORCEMENTS, sandbox_status


class SandboxGateTests(unittest.TestCase):
    def test_no_client_is_blocked_without_any_commands(self):
        runner = Mock(side_effect=AssertionError('must never run'))
        result = sandbox_status(docker_path='',runner=runner)
        self.assertEqual(result['reason_code'],'docker_client_unavailable')
        self.assertFalse(result['sandbox_execution_enabled'])
        runner.assert_not_called()

    def test_unreachable_daemon_blocks_without_container_execution(self):
        runner = Mock(return_value=subprocess.CompletedProcess([],1,'','not connected'))
        result = sandbox_status(docker_path='/usr/local/bin/docker',runner=runner)
        self.assertEqual(result['reason_code'],'docker_daemon_unreachable')
        self.assertFalse(result['docker_daemon_available'])
        self.assertFalse(result['sandbox_execution_enabled'])
        args=runner.call_args.args[0]
        self.assertEqual(args,['/usr/local/bin/docker','version','--format','{{.Server.Version}}'])
        self.assertNotIn('run',args)

    def test_connected_daemon_is_not_sandbox_verification(self):
        runner = Mock(return_value=subprocess.CompletedProcess([],0,'29.0.1\n',''))
        result = sandbox_status(docker_path='/usr/local/bin/docker',runner=runner)
        self.assertTrue(result['docker_daemon_available'])
        self.assertEqual(result['reason_code'],'isolation_canary_and_policy_not_verified')
        self.assertFalse(result['sandbox_execution_enabled'])
        self.assertFalse(result['isolation_canary_verified'])
        self.assertFalse(result['installation_allowed'])

    def test_timeout_is_fail_closed(self):
        runner = Mock(side_effect=subprocess.TimeoutExpired(['docker','version'],6))
        result = sandbox_status(docker_path='/usr/local/bin/docker',runner=runner)
        self.assertEqual(result['reason_code'],'docker_daemon_unreachable')
        self.assertFalse(result['third_party_code_executed'])

    def test_hardening_contract_contains_key_restrictions(self):
        requirements=' '.join(REQUIRED_ENFORCEMENTS)
        for term in ('network','secret','read_only','capabilities','cpu','memory','symlink','approval'):
            self.assertIn(term,requirements)

if __name__=='__main__':
    unittest.main()
