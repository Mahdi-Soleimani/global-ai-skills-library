#!/usr/bin/env python3
"""Actual Codex Skill discovery after a fixture-only install AND rollback.

Uses only GASL-authored inert SKILL.md and disposable project/home directories.
Never imports downloaded third-party Skills into Codex, starts a model turn,
uses real user Agent profiles or grants a production installation approval.
"""
import argparse
import hashlib
import json
import os
import selectors
import subprocess
import time
import zipfile
from pathlib import Path

from codex_discovery_probe import (
    SKILL_BODY, SKILL_NAME, _extract_exact_skill, _minimal_environment,
    _read_protocol_message, _request,
)
from fixture_transaction_v2 import (
    enact_fixture_transaction, preview_fixture_consent, recover_fixture_transaction,
)
from host_transaction_fixture import _new_root
from install_bundle import SCHEMA as BUNDLE_SCHEMA
from queue_ingest import git_blob

SCHEMA = 'gasl-real-codex-transaction-discovery-v1'


def _synthetic_inert_bundle(root, scope='project'):
    """Write a one-Skill ZIP and sidecar only inside an already marked fixture."""
    if scope not in ('project', 'user'):
        raise ValueError('Unsupported isolated Codex scope')
    name = SKILL_NAME + '/SKILL.md'
    plan_id = hashlib.sha256(
        ('GASL self-authored fixture, codex/' + scope + ', v1\n').encode() + SKILL_BODY
    ).hexdigest()
    folder = root / 'private' / 'install-bundles'
    folder.mkdir(parents=True)
    path = folder / (plan_id + '.zip')
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, SKILL_BODY)
    manifest = {
        'schema_version': BUNDLE_SCHEMA,
        'plan_id': plan_id,
        'agent': 'codex',
        'scope': scope,
        'archive_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'pinned_skill_md_blob_sha': git_blob(SKILL_BODY),
        'entries': [{'archive_path': name,
                     'sha256': hashlib.sha256(SKILL_BODY).hexdigest()}],
        'manual_review_required': True,
        'host_installation_approved': False,
        'production_installation_enabled': False,
    }
    (folder / (plan_id + '.json')).write_text(json.dumps(manifest), encoding='utf-8')
    return plan_id


def _host_skills_list(binary, root, scope='project', *, timeout=25, popen=subprocess.Popen):
    """Ask real Codex app-server only `initialize` and `skills/list` in isolated HOME."""
    if scope not in ('project', 'user'):
        raise ValueError('Unsupported isolated Codex scope')
    project = root / 'workspace'
    expected = (project / '.agents' / 'skills' if scope == 'project'
                else root / 'home' / '.agents' / 'skills') / SKILL_NAME / 'SKILL.md'
    process = None
    try:
        environment = _minimal_environment(root)
        environment['GASL_TEST_SCOPE'] = scope
        process = popen([str(binary), 'app-server'], cwd=str(project),
                        env=environment, stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                        text=False, bufsize=0)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            buffered = [b'']
            deadline = time.monotonic() + min(max(float(timeout), 1), 45)

            def send(payload):
                process.stdin.write(json.dumps(payload, separators=(',', ':')).encode() + b'\n')
                process.stdin.flush()

            def receive(expected_id):
                while True:
                    message = _read_protocol_message(process, selector, buffered, deadline)
                    if message.get('id') == expected_id:
                        return message

            send(_request(0, 'initialize', {'clientInfo': {
                'name': 'gasl_installer_e2e_test',
                'title': 'GASL Inert Fixture Transaction', 'version': '0.1.0'}}))
            initialized = receive(0)
            if initialized.get('error') is not None or not isinstance(initialized.get('result'), dict):
                raise ValueError('Codex did not initialize successfully')
            send({'method': 'initialized', 'params': {}})
            send(_request(1, 'skills/list', {'cwds': [str(project)], 'forceReload': True}))
            response = receive(1)
            return _extract_exact_skill(response, project, expected)
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


def verify_full_codex_lifecycle(binary, *, query=_host_skills_list, scope='project',
                                require_one_time_fixture_receipt=False):
    """A meaningful real Host result is only possible after all 3 observations."""
    result = {
        'schema_version': SCHEMA,
        'host': 'codex',
        'scope': scope,
        'isolated_home_profile_used': False,
        'real_home_or_codex_profile_accessed': False,
        'status': 'blocked',
        'reason_code': 'not_tested',
        'absent_before_install': False,
        'inert_skill_discovered_after_install': False,
        'absent_after_rollback': False,
        'fixture_rollback_verified': False,
        'model_turn_started': False,
        'authentication_performed': False,
        'third_party_skill_installed_or_executed': False,
        'real_host_files_modified': False,
        'production_installation_enabled': False,
        'one_time_fixture_receipt_consumed': False,
        'human_confirmation_verified': False,
    }
    if scope not in ('project', 'user'):
        result['reason_code'] = 'unsupported_codex_scope'
        return result
    binary = Path(binary)
    if not binary.is_absolute() or binary.is_symlink() or not binary.is_file():
        result['reason_code'] = 'absolute_regular_codex_executable_required'
        return result
    with _new_root()[0] as fixture_string:
        root = Path(fixture_string)
        # _new_root creates the marker. This root is always a disposable fixture.
        for dirname in ('workspace', 'home', 'codex-home', 'cache', 'xdg-config', 'tmp'):
            (root / dirname).mkdir()
        plan_id = _synthetic_inert_bundle(root, scope)
        try:
            initial = query(binary, root, scope)
            if initial:
                result['reason_code'] = 'inert_skill_unexpectedly_preexisting'
                return result
            result['absent_before_install'] = True
            preview = preview_fixture_consent(root, root, plan_id, 'codex', scope, 'install')
            receipt_id = None
            if require_one_time_fixture_receipt:
                # CI confirmation is deliberately synthetic, NOT human consent.
                from fixture_explicit_consent import request_fixture_consent, confirm_fixture_consent
                pending = request_fixture_consent(root, root, plan_id, 'codex', scope, 'install')
                confirm_fixture_consent(root, root, pending['request_id'],
                                        pending['confirmation_phrase'])
                receipt_id = pending['request_id']
            installed = enact_fixture_transaction(root, root, plan_id, 'codex', scope,
                                        'install', preview['approval_challenge'],
                                        consent_request_id=receipt_id)
            result['one_time_fixture_receipt_consumed'] = installed['one_time_fixture_receipt_consumed']
            target_root = (root / 'workspace' if scope == 'project' else root / 'home')
            installed_file = target_root / '.agents' / 'skills' / SKILL_NAME / 'SKILL.md'
            if not installed_file.is_file() or installed_file.read_bytes() != SKILL_BODY:
                result['reason_code'] = 'fixture_bytes_not_materialized'
                return result
            observed = query(binary, root, scope)
            if not observed:
                result['reason_code'] = 'codex_failed_to_discover_installed_inert_skill'
                return result
            result['inert_skill_discovered_after_install'] = True
            rollback = recover_fixture_transaction(root)
            result['fixture_rollback_verified'] = bool(rollback['previous_files_restored']) and not installed_file.exists()
            if not result['fixture_rollback_verified']:
                result['reason_code'] = 'fixture_rollback_validation_failed'
                return result
            still_present = query(binary, root, scope)
            result['absent_after_rollback'] = not still_present
            if still_present:
                result['reason_code'] = 'codex_still_discovers_removed_skill'
                return result
            result['status'] = 'real_codex_inert_install_discovery_rollback_verified'
            result['isolated_home_profile_used'] = True
            result['reason_code'] = 'three_real_host_observations_and_fixture_rollback_passed'
            return result
        except (OSError, ValueError, TimeoutError, BrokenPipeError):
            result['reason_code'] = 'codex_e2e_protocol_or_fixture_error'
            return result


def main():
    parser = argparse.ArgumentParser(description='Real Codex discovery, only inert installed fixture, never a user profile')
    parser.add_argument('--codex-bin', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--scope', choices=('project', 'user'), default='project',
        help='Project .agents/skills or user ~/.agents/skills inside the disposable HOME')
    parser.add_argument('--test-one-time-receipt', action='store_true',
        help='Test only: CI simulates consent in disposable fixture; not human approval')
    args = parser.parse_args()
    result = verify_full_codex_lifecycle(args.codex_bin, scope=args.scope,
              require_one_time_fixture_receipt=args.test_one_time_receipt)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    print(payload, end='')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding='utf-8')
    return 0 if result['status'] == 'real_codex_inert_install_discovery_rollback_verified' else 1


if __name__ == '__main__':
    raise SystemExit(main())
