#!/usr/bin/env python3
"""Ephemeral, auth-free Codex app-server Skill discovery integration check.

Only a generated, inert GASL-authored SKILL.md is presented to the Host.
Never launches a model turn, runs a Skill, accesses the user's real home,
reads account credentials, or modifies the Host's real configuration.
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

SKILL_NAME = 'gasl-discovery-probe'
SKILL_BODY = (b'---\nname: gasl-discovery-probe\n'
              b'description: Inert test of Host Skill discovery in isolated CI\n'
              b'---\n# GASL discovery fixture\nNo tools, commands, or external dependencies.\n')
EXPECTED_SCHEMA = 'gasl-codex-live-discovery-v1'
MAX_PROTOCOL_BYTES = 2 * 1024 * 1024


def _request(request_id, method, params):
    return {'id': request_id, 'method': method, 'params': params}


def _setup_fixture(root):
    project = root / 'project'
    skill_dir = project / '.agents' / 'skills' / SKILL_NAME
    skill_dir.mkdir(parents=True)
    expected = skill_dir / 'SKILL.md'
    expected.write_bytes(SKILL_BODY)
    for directory in ('home', 'codex-home', 'cache', 'xdg-config', 'tmp'):
        (root / directory).mkdir()
    return project, expected


def _windows_runtime_environment(root, base, config, cache):
    """Explicit Windows profile/temp variables, never inherit user credentials."""
    if os.name != 'nt':
        return {}
    home = root / 'home'
    drive, tail = os.path.splitdrive(str(home))
    env = {
        'USERPROFILE': str(home), 'HOMEDRIVE': drive, 'HOMEPATH': tail,
        'APPDATA': str(root / config), 'LOCALAPPDATA': str(root / cache),
        'TEMP': str(root / 'tmp'), 'TMP': str(root / 'tmp'),
    }
    # Windows needs SystemRoot for side-by-side assemblies and system DLLs.
    # Do not copy arbitrary inherited environment variables.
    for key in ('SystemRoot', 'WINDIR'):
        if base.get(key):
            env[key] = base[key]
    return env


class _WindowsPipeSelector:
    """Single-reader anonymous-pipe readiness using native PeekNamedPipe.

    Windows select() only accepts sockets. Peek without consuming, then the
    existing reader may read available bytes or observe EOF. No reader thread,
    busy spin, or unbounded read is required.
    """
    def __init__(self):
        import ctypes
        import msvcrt
        from ctypes import wintypes
        self.ctypes = ctypes
        self.wintypes = wintypes
        self.msvcrt = msvcrt
        self.peek = ctypes.WinDLL('kernel32', use_last_error=True).PeekNamedPipe
        self.peek.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                              wintypes.LPDWORD, wintypes.LPDWORD, wintypes.LPDWORD]
        self.peek.restype = wintypes.BOOL
        self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.handle = None

    def register(self, stream, events):
        if self.handle is not None or events != selectors.EVENT_READ:
            raise ValueError('Only one protocol output reader is supported')
        self.handle = self.msvcrt.get_osfhandle(stream.fileno())

    def select(self, timeout):
        if self.handle is None:
            raise ValueError('Protocol pipe is not registered')
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            available = self.wintypes.DWORD()
            if not self.peek(self.handle, None, 0, None,
                             self.ctypes.byref(available), None):
                code = self.ctypes.get_last_error()
                if code in (109, 232, 233):  # broken/closing/disconnected pipe
                    return [True]
                raise self.ctypes.WinError(code)
            if available.value:
                return [True]
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return []
            time.sleep(min(0.01, remaining))


def _protocol_selector():
    return _WindowsPipeSelector() if os.name == 'nt' else selectors.DefaultSelector()


def _minimal_environment(root, base_env=None):
    """No user credentials/tokens, no real home, no real Codex configuration."""
    if base_env is None:
        base_env = os.environ
    return {
        'PATH': base_env.get('PATH', '/usr/local/bin:/usr/bin:/bin'),
        'HOME': str(root / 'home'),
        'CODEX_HOME': str(root / 'codex-home'),
        'XDG_CONFIG_HOME': str(root / 'xdg-config'),
        'XDG_CACHE_HOME': str(root / 'cache'),
        'TMPDIR': str(root / 'tmp'),
        'CI': '1',
        'NO_COLOR': '1',
        **_windows_runtime_environment(root, base_env, 'xdg-config', 'cache'),
    }


def _read_protocol_message(proc, selector, buffered, deadline):
    """Read complete newline-delimited JSON without waiting forever on a partial line."""
    while time.monotonic() < deadline:
        if b'\n' in buffered[0]:
            raw, buffered[0] = buffered[0].split(b'\n', 1)
            if len(raw) > MAX_PROTOCOL_BYTES:
                raise ValueError('Codex app-server protocol message exceeded bounded size')
            try:
                value = json.loads(raw)
            except (ValueError, UnicodeError):
                raise ValueError('Codex app-server returned malformed JSONL')
            if not isinstance(value, dict):
                raise ValueError('Codex app-server JSONL message is not an object')
            return value
        if len(buffered[0]) > MAX_PROTOCOL_BYTES:
            raise ValueError('Codex app-server protocol message exceeded bounded size')
        if proc.poll() is not None:
            # Poll one more time to drain any bytes buffered on the closed pipe.
            wait = 0
        else:
            wait = min(0.4, max(0.0, deadline - time.monotonic()))
        events = selector.select(wait)
        if not events:
            if proc.poll() is not None:
                raise ValueError('Codex app-server exited before the requested response')
            continue
        chunk = os.read(proc.stdout.fileno(), 4096)
        if not chunk:
            raise ValueError('Codex app-server closed its protocol output prematurely')
        buffered[0] += chunk
    raise TimeoutError('Codex app-server did not respond within bounded deadline')


def _extract_exact_skill(response, project, skill_file):
    """Only accept the expected exact fixture path returned by the real Host."""
    if not isinstance(response, dict) or response.get('error') is not None:
        raise ValueError('Codex skills/list returned a protocol error')
    result = response.get('result')
    data = result.get('data') if isinstance(result, dict) else None
    if not isinstance(data, list):
        raise ValueError('Codex skills/list response lacks data array')
    matches = []
    for group in data:
        if not isinstance(group, dict) or group.get('cwd') != str(project):
            continue
        for skill in group.get('skills', []):
            if isinstance(skill, dict) and skill.get('name') == SKILL_NAME:
                matches.append(skill)
    # Avoid treating another bundled Skill with the same name as our test.
    return (len(matches) == 1 and isinstance(matches[0].get('path'), str)
            and Path(matches[0]['path']).resolve() == skill_file.resolve()
            and matches[0].get('enabled') is True)


def verify_codex_discovery(binary, *, timeout=25, popen=subprocess.Popen):
    """No model turn. Single `initialize` and `skills/list` against disposable profile."""
    result = {
        'schema_version': EXPECTED_SCHEMA,
        'host': 'codex',
        'protocol': 'app-server stdio initialize + skills/list',
        'status': 'blocked',
        'reason_code': 'not_executed',
        'isolated_skill_discovery_verified': False,
        'authenticated_user_profile_accessed': False,
        'model_turn_started': False,
        'third_party_skill_executed': False,
        'real_host_files_modified': False,
        'production_installation_enabled': False,
    }
    path = Path(binary)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        result['reason_code'] = 'absolute_local_codex_executable_required'
        return result
    if os.name == 'nt' and popen is subprocess.Popen:
        result['reason_code'] = 'windows_live_host_probe_not_yet_verified'
        return result
    with tempfile.TemporaryDirectory(prefix='gasl-codex-discovery-') as temporary:
        root = Path(temporary)
        project, skill_file = _setup_fixture(root)
        env = _minimal_environment(root)
        proc = None
        try:
            proc = popen([str(path), 'app-server'], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         text=False, cwd=str(project), env=env, bufsize=0)
            with _protocol_selector() as selector:
                selector.register(proc.stdout, selectors.EVENT_READ)
                buffer = [b'']
                deadline = time.monotonic() + min(max(float(timeout), 1), 45)

                def send(message):
                    proc.stdin.write(json.dumps(message, separators=(',', ':')).encode('utf-8') + b'\n')
                    proc.stdin.flush()

                def reply(request_id):
                    while True:
                        obj = _read_protocol_message(proc, selector, buffer, deadline)
                        if obj.get('id') == request_id:
                            return obj

                send(_request(0, 'initialize', {'clientInfo': {
                    'name': 'gasl_isolated_discovery', 'title': 'GASL Isolated Discovery', 'version': '0.1.0'}}))
                initialized = reply(0)
                if initialized.get('error') is not None or not isinstance(initialized.get('result'), dict):
                    result['reason_code'] = 'codex_app_server_initialization_failed'
                    return result
                send({'method': 'initialized', 'params': {}})
                send(_request(1, 'skills/list', {'cwds': [str(project)], 'forceReload': True}))
                listed = reply(1)
                if listed.get('error') is not None:
                    result['reason_code'] = 'codex_skills_list_error'
                    return result
                verified = _extract_exact_skill(listed, project, skill_file)
                result['isolated_skill_discovery_verified'] = verified
                result['status'] = 'verified_isolated_codex_discovery' if verified else 'blocked'
                result['reason_code'] = 'exact_inert_skill_discovered' if verified else 'expected_inert_skill_not_found'
                return result
        except (OSError, ValueError, TimeoutError, BrokenPipeError):
            result['reason_code'] = 'codex_protocol_unavailable_or_invalid'
            return result
        finally:
            if proc is not None:
                if proc.stdin:
                    proc.stdin.close()
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=3)
                if proc.stdout:
                    proc.stdout.close()


def main():
    parser = argparse.ArgumentParser(description='Isolated real Codex skill discovery only; no model calls')
    parser.add_argument('--codex-bin', required=True, type=Path,
                        help='absolute path to a locally installed Codex CLI executable')
    parser.add_argument('--output', type=Path,
                        help='optional JSON status file; never contains paths or credentials')
    args = parser.parse_args()
    report = verify_codex_discovery(args.codex_bin)
    content = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    print(content, end='')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding='utf-8')
    return 0 if report['isolated_skill_discovery_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
