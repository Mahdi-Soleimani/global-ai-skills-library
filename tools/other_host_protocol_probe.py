#!/usr/bin/env python3
"""Actual Host *readiness* probes in disposable, credential-free profiles.

Neither probe requests authentication, starts an Agent/model turn, uploads a
Skill, installs GASL packages, or modifies the developer's Host profiles.
Cursor ACP initialize is NOT proof of Skill discovery. Claude --version is
NOT proof of Skill discovery. Both are clearly marked as such in the output.
"""
import argparse
import json
import os
import re
import selectors
import subprocess
import tempfile
import time
from pathlib import Path

from codex_discovery_probe import _read_protocol_message

HOSTS = ('cursor', 'claude-code')
MAX_TIMEOUT = 18


def _blocked(host, reason):
    return {
        'schema_version': 'gasl-other-host-readiness-v1',
        'host': host,
        'status': 'blocked',
        'reason_code': reason,
        'real_host_protocol_verified': False,
        'skill_discovery_verified': False,
        'authentication_performed': False,
        'model_turn_started': False,
        'third_party_skill_executed': False,
        'real_host_files_modified': False,
        'production_installation_enabled': False,
    }


def _runtime(root, base=None):
    if base is None:
        base = os.environ
    return {
        'PATH': base.get('PATH', '/usr/local/bin:/usr/bin:/bin'),
        'HOME': str(root / 'home'),
        'XDG_CONFIG_HOME': str(root / 'xdg-config'),
        'XDG_CACHE_HOME': str(root / 'xdg-cache'),
        'TMPDIR': str(root / 'tmp'),
        'CI': '1',
        'NO_COLOR': '1',
        'DISABLE_AUTOUPDATER': '1',
        'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1',
    }


def verify_host_readiness(host, binary, *, timeout=12, popen=subprocess.Popen):
    if host not in HOSTS:
        raise ValueError('Unsupported Host')
    result = _blocked(host, 'not_executed')
    path = Path(binary)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        result['reason_code'] = 'absolute_local_executable_required'
        return result
    with tempfile.TemporaryDirectory(prefix='gasl-host-readiness-') as tmp:
        root = Path(tmp)
        for dirname in ('project', 'home', 'xdg-config', 'xdg-cache', 'tmp'):
            (root / dirname).mkdir()
        env = _runtime(root)
        proc = None
        try:
            args = [str(path), 'acp'] if host == 'cursor' else [str(path), '--version']
            proc = popen(args, cwd=str(root / 'project'), env=env,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=False, bufsize=0)
            deadline = time.monotonic() + min(max(float(timeout), 1), MAX_TIMEOUT)
            with selectors.DefaultSelector() as sel:
                sel.register(proc.stdout, selectors.EVENT_READ)
                buffer = [b'']
                if host == 'cursor':
                    request = {
                        'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                        'params': {
                            'protocolVersion': 1,
                            'clientCapabilities': {'fs': {'readTextFile': False,
                                                          'writeTextFile': False},
                                                   'terminal': False},
                            'clientInfo': {'name': 'gasl-inert-protocol-check', 'version': '0.1.0'},
                        },
                    }
                    proc.stdin.write(json.dumps(request, separators=(',', ':')).encode() + b'\n')
                    proc.stdin.flush()
                    while True:
                        message = _read_protocol_message(proc, sel, buffer, deadline)
                        if message.get('id') != 1:
                            continue
                        info = message.get('result')
                        if (message.get('error') is not None or not isinstance(info, dict)
                                or info.get('protocolVersion') != 1
                                or not isinstance(info.get('agentCapabilities'), dict)):
                            result['reason_code'] = 'cursor_acp_initialize_response_invalid'
                            return result
                        result['status'] = 'real_host_readiness_verified'
                        result['reason_code'] = 'cursor_acp_initialized_without_authentication'
                        result['real_host_protocol_verified'] = True
                        result['protocol'] = 'ACP initialize only; session creation not attempted'
                        return result
                else:
                    chunks = []
                    total = 0
                    while time.monotonic() < deadline:
                        events = sel.select(min(0.25, max(0, deadline - time.monotonic())))
                        if events:
                            chunk = os.read(proc.stdout.fileno(), 2048)
                            if chunk:
                                chunks.append(chunk)
                                total += len(chunk)
                                if total > 8192:
                                    raise ValueError('Claude CLI version output exceeded limit')
                            elif proc.poll() is not None:
                                break
                        elif proc.poll() is not None:
                            break
                    try:
                        remaining = proc.wait(timeout=max(0.1, deadline - time.monotonic()))
                    except subprocess.TimeoutExpired:
                        raise TimeoutError('Claude CLI version check exceeded deadline')
                    output = b''.join(chunks).decode('utf-8', 'replace').strip()
                    match = re.search(r'\b(\d+\.\d+\.\d+)\b', output)
                    if remaining != 0 or not match:
                        result['reason_code'] = 'claude_cli_version_unavailable'
                        return result
                    result['status'] = 'real_host_readiness_verified'
                    result['reason_code'] = 'claude_cli_version_verified_without_authentication'
                    result['real_host_protocol_verified'] = True
                    result['host_version'] = match.group(1)
                    result['protocol'] = 'CLI --version only; no Skill discovery attempted'
                    return result
        except (OSError, ValueError, TimeoutError, BrokenPipeError):
            result['reason_code'] = 'host_protocol_unavailable_or_timed_out'
            return result
        finally:
            if proc is not None:
                if proc.stdin and not proc.stdin.closed:
                    proc.stdin.close()
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=2)
                if proc.stdout:
                    proc.stdout.close()


def main():
    parser = argparse.ArgumentParser(description='Readiness check of real Host CLI; never invoke a model')
    parser.add_argument('--host', required=True, choices=HOSTS)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify_host_readiness(args.host, args.binary)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    print(payload, end='')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding='utf-8')
    return 0 if result['real_host_protocol_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
