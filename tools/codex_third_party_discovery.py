#!/usr/bin/env python3
"""Discovery-only check for one pinned third-party Skill in a disposable Codex HOME.

The test copies only the exact, Git-Blob-verified SKILL.md into a temporary
HOME/.agents/skills directory. It asks Codex app-server only initialize and
skills/list before/after/rollback. It never starts a model turn or executes
Skill instructions, scripts, package managers, servers, or dependencies.
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

from codex_discovery_probe import (
    _minimal_environment, _read_protocol_message, _request, _protocol_selector,
)
from queue_ingest import git_blob

SCHEMA = 'gasl-codex-third-party-discovery-only-v1'
SOURCE_ID_RE = re.compile(r'^GASL-SRC-[0-9a-f]{20}$')
SHA_RE = re.compile(r'^[0-9a-f]{40}$')
SKILL_NAME_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,63}$')
MAX_SKILL_BYTES = 256 * 1024


def approval_phrase(source_record_id, skill_name, expected_git_blob):
    if (not SOURCE_ID_RE.fullmatch(str(source_record_id))
            or not SKILL_NAME_RE.fullmatch(str(skill_name))
            or not SHA_RE.fullmatch(str(expected_git_blob))):
        raise ValueError('Invalid source identity for approval phrase')
    return ('INSTALL ' + skill_name.upper() + ' IN DISPOSABLE CODEX USER HOME '
            + 'FOR DISCOVERY ONLY ' + source_record_id.upper() + ' '
            + expected_git_blob[:12].upper())


def _frontmatter_name(data):
    try:
        content = data.decode('utf-8')
    except UnicodeError as exc:
        raise ValueError('SKILL.md must be UTF-8') from exc
    match = re.match(r'\A---\s*\n(.*?)\n---(?:\n|$)', content, re.S)
    if not match:
        raise ValueError('SKILL.md lacks valid YAML frontmatter')
    name = re.search(r'(?m)^name:\s*([a-z0-9][a-z0-9-]{0,63})\s*$', match.group(1))
    if not name:
        raise ValueError('SKILL.md frontmatter has no valid name')
    return name.group(1)


def _skill_matches(response, project, skill_name):
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
        skills = group.get('skills')
        if not isinstance(skills, list):
            raise ValueError('Codex skills/list group has invalid skills array')
        for skill in skills:
            if isinstance(skill, dict) and skill.get('name') == skill_name:
                matches.append(skill)
    return matches


def _query_codex(binary, root, project, skill_name, skill_file, *, timeout=25,
                 popen=subprocess.Popen):
    if os.name == "nt" and popen is subprocess.Popen:
        raise ValueError("Windows live Host probe not yet verified")
    process = None
    try:
        environment = _minimal_environment(root)
        environment['GASL_TEST_SKILL_NAME'] = skill_name
        environment['GASL_TEST_SKILL_PATH'] = str(skill_file)
        process = popen([str(binary), 'app-server'], cwd=str(project), env=environment,
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL, text=False, bufsize=0)
        with _protocol_selector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            buffered = [b'']
            deadline = time.monotonic() + min(max(float(timeout), 1), 45)

            def send(payload):
                process.stdin.write(json.dumps(payload, separators=(',', ':')).encode('utf-8') + b'\n')
                process.stdin.flush()

            def receive(expected_id):
                while True:
                    message = _read_protocol_message(process, selector, buffered, deadline)
                    if message.get('id') == expected_id:
                        return message

            send(_request(0, 'initialize', {'clientInfo': {
                'name': 'gasl-third-party-discovery-only',
                'title': 'GASL Third-party Skill Discovery Only', 'version': '0.1.0'}}))
            initialized = receive(0)
            if initialized.get('error') is not None or not isinstance(initialized.get('result'), dict):
                raise ValueError('Codex app-server initialization failed')
            send({'method': 'initialized', 'params': {}})
            send(_request(1, 'skills/list', {'cwds': [str(project)], 'forceReload': True}))
            return _skill_matches(receive(1), project, skill_name)
    finally:
        if process is not None:
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            if process.stdout is not None:
                process.stdout.close()


def verify_third_party_codex_discovery(binary, skill_file, *, source_record_id,
                                      skill_name, expected_git_blob, timeout=25,
                                      query=_query_codex, popen=subprocess.Popen):
    """Copy one verified SKILL.md into disposable user scope and verify rollback."""
    result = {
        'schema_version': SCHEMA,
        'source_record_id': source_record_id,
        'skill_name': skill_name,
        'host': 'codex',
        'scope': 'user',
        'status': 'blocked',
        'reason_code': 'not_executed',
        'source_git_blob_verified': False,
        'absent_before_install': False,
        'third_party_skill_temporarily_installed': False,
        'exact_skill_discovered_and_enabled': False,
        'absent_after_rollback': False,
        'temporary_profile_deleted': False,
        'model_turn_started': False,
        'authentication_performed': False,
        'third_party_skill_executed': False,
        'skill_commands_or_dependencies_executed': False,
        'real_home_or_codex_profile_accessed': False,
        'real_host_files_modified': False,
        'production_installation_enabled': False,
        'injected_test_transport': query is not _query_codex or popen is not subprocess.Popen,
    }
    binary = Path(binary)
    source = Path(skill_file)
    if not binary.is_absolute() or binary.is_symlink() or not binary.is_file():
        result['reason_code'] = 'absolute_regular_codex_executable_required'
        return result
    if os.name == 'nt' and query is _query_codex and popen is subprocess.Popen:
        result['reason_code'] = 'windows_live_host_probe_not_yet_verified'
        return result
    if (not SOURCE_ID_RE.fullmatch(str(source_record_id))
            or not SKILL_NAME_RE.fullmatch(str(skill_name))
            or not SHA_RE.fullmatch(str(expected_git_blob))):
        result['reason_code'] = 'invalid_pinned_skill_identity'
        return result
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_SKILL_BYTES:
        result['reason_code'] = 'skill_file_missing_unsafe_or_oversized'
        return result
    data = source.read_bytes()
    if git_blob(data) != expected_git_blob:
        result['reason_code'] = 'pinned_skill_git_blob_mismatch'
        return result
    if _frontmatter_name(data) != skill_name:
        result['reason_code'] = 'skill_frontmatter_name_mismatch'
        return result
    result['source_git_blob_verified'] = True

    root = None
    with tempfile.TemporaryDirectory(prefix='gasl-codex-third-party-discovery-') as temporary:
        root = Path(temporary)
        for dirname in ('workspace', 'home', 'codex-home', 'cache', 'xdg-config', 'tmp'):
            (root / dirname).mkdir()
        project = root / 'workspace'
        home = root / 'home'
        skill_dir = home / '.agents' / 'skills' / skill_name
        skill_path = skill_dir / 'SKILL.md'
        try:
            before = query(binary, root, project, skill_name, skill_path,
                           timeout=timeout, popen=popen)
            if before:
                result['reason_code'] = 'same_name_skill_preexists_in_disposable_profile'
            else:
                result['absent_before_install'] = True
                skill_dir.mkdir(parents=True, exist_ok=False)
                with skill_path.open('xb') as output:
                    output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
                if skill_path.is_symlink() or skill_path.read_bytes() != data:
                    result['reason_code'] = 'temporary_skill_copy_verification_failed'
                else:
                    result['third_party_skill_temporarily_installed'] = True
                    matches = query(binary, root, project, skill_name, skill_path,
                                    timeout=timeout, popen=popen)
                    exact = (len(matches) == 1 and isinstance(matches[0].get('path'), str)
                             and Path(matches[0]['path']).resolve() == skill_path.resolve()
                             and matches[0].get('enabled') is True)
                    if not exact:
                        result['reason_code'] = 'codex_did_not_discover_exact_enabled_skill'
                    else:
                        result['exact_skill_discovered_and_enabled'] = True
                        # Remove only the exact file whose bytes were copied by this run.
                        if (skill_path.is_symlink() or not skill_path.is_file()
                                or skill_path.read_bytes() != data
                                or {p.name for p in skill_dir.iterdir()} != {'SKILL.md'}):
                            result['reason_code'] = 'temporary_skill_changed_refuse_rollback'
                        else:
                            skill_path.unlink()
                            skill_dir.rmdir()
                            skills_root = home / '.agents' / 'skills'
                            if skills_root.is_dir() and not any(skills_root.iterdir()):
                                skills_root.rmdir()
                            agents_root = home / '.agents'
                            if agents_root.is_dir() and not any(agents_root.iterdir()):
                                agents_root.rmdir()
                            after = query(binary, root, project, skill_name, skill_path,
                                          timeout=timeout, popen=popen)
                            result['absent_after_rollback'] = not after and not skill_dir.exists()
                            if result['absent_after_rollback']:
                                result['status'] = 'verified_temporary_third_party_codex_discovery_and_rollback'
                                result['reason_code'] = 'exact_skill_discovered_then_removed_from_disposable_home'
                            else:
                                result['reason_code'] = 'codex_still_discovers_skill_after_rollback'
        except (OSError, ValueError, TimeoutError, BrokenPipeError):
            result['reason_code'] = 'codex_protocol_or_temporary_profile_error'
    result['temporary_profile_deleted'] = root is not None and not root.exists()
    if result['status'] == 'verified_temporary_third_party_codex_discovery_and_rollback' and not result['temporary_profile_deleted']:
        result['status'] = 'blocked'
        result['reason_code'] = 'temporary_profile_cleanup_failed'

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Install one pinned SKILL.md into disposable Codex HOME for skills/list only; never a real profile')
    parser.add_argument('--codex-bin', type=Path, required=True)
    parser.add_argument('--skill-file', type=Path, required=True)
    parser.add_argument('--source-record-id', required=True)
    parser.add_argument('--skill-name', required=True)
    parser.add_argument('--expected-git-blob', required=True)
    parser.add_argument('--acknowledge', required=True,
                        help='Exact phrase shown by the manual review report; approval for this one disposable discovery test only')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    expected = approval_phrase(args.source_record_id, args.skill_name, args.expected_git_blob)
    if args.acknowledge != expected:
        raise SystemExit('Exact approval phrase does not match this source, Skill, and discovery-only scope')
    report = verify_third_party_codex_discovery(
        args.codex_bin, args.skill_file, source_record_id=args.source_record_id,
        skill_name=args.skill_name, expected_git_blob=args.expected_git_blob)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    print(payload, end='')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding='utf-8')
    return 0 if report['status'] == 'verified_temporary_third_party_codex_discovery_and_rollback' else 1


if __name__ == '__main__':
    raise SystemExit(main())
