#!/usr/bin/env python3
"""Version-pinned Skill installation PREVIEW and rollback-able *simulation* only.

No downloaded Skill is installed or run. No Agent configuration, extension,
project or user home path is written. Real approval/installation remain disabled.
"""
import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from queue_ingest import git_blob, no_symlink, package_location
from skill_search import ROOT, get_skill_by_id, normalize_text
from static_scan import scan_package
from security_gate import _legacy_source_path
from host_adapters import HOST_LAYOUTS

AGENTS = tuple(HOST_LAYOUTS)
SCOPES = ('user', 'project')
SCHEMA = 'gasl-install-plan-v1'
EVENT_SCHEMA = 'gasl-install-simulation-v1'
ID_PATTERN = re.compile(r'^[0-9a-f]{64}$')


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def _validate_agent_scope(agent, scope):
    if agent not in AGENTS:
        raise ValueError('Unknown agent; supported preview targets: ' + ', '.join(AGENTS))
    if scope not in SCOPES:
        raise ValueError('Scope must be user or project')


def _get_local_package_status(root, record):
    """Fresh, non-mutating inventory inspection. Never rely on stale scan labels."""
    folder = no_symlink(root, package_location(root, {**record, 'skill_path': record['source_path']}))
    source = no_symlink(root, folder / 'source.json')
    if not source.is_file():
        source = _legacy_source_path(root, source, record)
        if source is None:
            return {'status': 'not_downloaded', 'integrity_ok': False,
                    'pinned_skill_blob_ok': False, 'security_status': 'not_scanned',
                    'actionable_findings': None, 'inventory_file_count': 0}
        folder = source.parent
    # Older pinned folder format may be used only with exact identity evidence.
    try:
        no_symlink(root, source)
        meta = json.loads(source.read_text(encoding='utf-8'))
        identity_ok = (str(meta.get('repository', '')).casefold() == str(record['repository']).casefold()
                       and meta.get('commit_sha') == record['commit_sha']
                       and meta.get('source_skill_path') == record['source_path']
                       and meta.get('package_complete') is True
                       and meta.get('skill_md_blob_sha') in (None, record['skill_md_blob_sha']))
        main = no_symlink(root, folder / 'SKILL.md')
        expected_blob = record.get('skill_md_blob_sha')
        blob_ok = (isinstance(expected_blob, str) and len(expected_blob) == 40
                   and main.is_file() and git_blob(main.read_bytes()) == expected_blob)
        if not identity_ok or not blob_ok:
            return {'status': 'integrity_failed', 'integrity_ok': False,
                    'pinned_skill_blob_ok': bool(blob_ok),
                    'security_status': 'integrity_failed',
                    'actionable_findings': None, 'inventory_file_count': 0}
        inspection = scan_package(source, root=root, persist=False)
        valid = bool(inspection['integrity_ok'])
        return {
            'status': 'downloaded_verified' if valid else 'integrity_failed',
            'integrity_ok': valid, 'pinned_skill_blob_ok': True,
            'security_status': inspection['security_status'],
            'actionable_findings': inspection['actionable_finding_count'],
            'inventory_file_count': len(meta.get('files', [])),
        }
    except (OSError, ValueError, TypeError, KeyError):
        return {'status': 'integrity_failed', 'integrity_ok': False,
                'pinned_skill_blob_ok': False, 'security_status': 'integrity_failed',
                'actionable_findings': None, 'inventory_file_count': 0}


def _compatibility(agent, value):
    """Upstream compatibility claims are unverified, and never become host approval."""
    if not isinstance(value, str) or not value.strip():
        return {'status': 'not_declared', 'claim': None,
                'host_integration_verified': False}
    label = {'codex': 'codex', 'cursor': 'cursor', 'claude-code': 'claude code',
             'claude-desktop': 'claude desktop', 'generic-mcp': 'mcp'}[agent]
    normalized = normalize_text(value)
    return {'status': 'declared_match_unverified' if label in normalized else 'declared_nonmatching_unverified',
            'claim': value[:240], 'host_integration_verified': False}


def plan_install(source_record_id, agent, scope='user', *, root=ROOT, lookup=None):
    """Generate deterministic read-only install plan, not an authorization token."""
    _validate_agent_scope(agent, scope)
    root = Path(root).resolve()
    record = lookup(source_record_id, root=root) if lookup is not None else get_skill_by_id(source_record_id, root=root)
    if not record:
        raise KeyError('Unknown Skill source record ID: ' + source_record_id)
    if (record.get('snapshot_status') != 'verified_commit_pinned'
            or not re.fullmatch(r'[0-9a-f]{40}', str(record.get('commit_sha') or ''))
            or not re.fullmatch(r'[0-9a-f]{40}', str(record.get('skill_md_blob_sha') or ''))):
        raise ValueError('Exact commit and pinned SKILL.md Git blob are required')

    identity = {
        'schema_version': SCHEMA, 'source_record_id': source_record_id,
        'repository': record['repository'], 'source_path': record['source_path'],
        'commit_sha': record['commit_sha'],
        'skill_md_blob_sha': record['skill_md_blob_sha'],
        'agent': agent, 'scope': scope,
    }
    plan_id = hashlib.sha256(_json_bytes(identity)).hexdigest()
    package = _get_local_package_status(root, record)
    compatibility = _compatibility(agent, record.get('compatibility'))
    license_spdx = record.get('license_spdx')
    warnings = []
    if license_spdx in (None, '', 'NOASSERTION', 'UNKNOWN'):
        warnings.append('license_terms_require_review')
    if compatibility['status'] == 'not_declared':
        warnings.append('host_compatibility_not_declared')
    else:
        warnings.append('host_compatibility_claim_not_tested')
    if package['status'] == 'not_downloaded':
        warnings.append('download_pinned_package_before_any_actual_install')
    elif not package['integrity_ok']:
        warnings.append('downloaded_package_integrity_failed')
    elif package['actionable_findings']:
        warnings.append('static_security_review_required')
    warnings.append('dynamic_skill_execution_not_approved')
    if HOST_LAYOUTS[agent].get('verified_with_real_host'):
        warnings.append('host_discovery_verified_in_disposable_profile_only')
    else:
        warnings.append('host_adapter_not_verified_with_real_host')
    warnings.append('real_user_profile_installation_not_enabled')
    warnings.append('no_user_install_approval_collected')
    can_simulate_apply = (package['status'] == 'downloaded_verified'
                          and package['actionable_findings'] == 0)
    return {
        'schema_version': SCHEMA, 'plan_id': plan_id,
        'source_record_id': source_record_id,
        'skill_name': record.get('skill_name'),
        'repository': record['repository'], 'source_url': record.get('source_url'),
        'source_path': record['source_path'],
        'pinned_version': {'commit_sha': record['commit_sha'],
                           'skill_md_blob_sha': record['skill_md_blob_sha']},
        'license_spdx': license_spdx,
        'agent': agent, 'scope': scope,
        'logical_destination': 'preview:{}:{}'.format(agent, scope),
        'filesystem_target_resolved': False,
        'compatibility': compatibility,
        'host_adapter': {
            'kind': HOST_LAYOUTS[agent]['kind'],
            'documented_relative_skill_directory': HOST_LAYOUTS[agent][scope],
            'source_documentation': HOST_LAYOUTS[agent]['docs'],
            'verified_with_real_host': HOST_LAYOUTS[agent]['verified_with_real_host'],
            'verified_capabilities': HOST_LAYOUTS[agent].get('verified_capabilities', []),
            'verification_scope': HOST_LAYOUTS[agent].get('verification_scope'),
            'verification_report': HOST_LAYOUTS[agent].get('verification_report'),
            'fixture_rehearsal_available': HOST_LAYOUTS[agent]['kind'] == 'filesystem_skill_directory',
            'actual_install_enabled': False,
        },
        'local_package': package,
        'warnings': sorted(set(warnings)),
        'plan_steps': [
            'verify_exact_pinned_version', 'review_license_and_security',
            'validate_actual_agent_adapter_and_target', 'obtain_explicit_user_approval',
            'prepare_versioned_backup_and_rollback', 'install_only_after_future_security_gates',
        ],
        'rollback_steps': ['verify_recorded_install_identity',
                           'restore_previous_version_from_verified_backup',
                           'remove_only_resources_owned_by_the_install'],
        'simulation_apply_eligible': can_simulate_apply,
        'simulation_requires_exact_plan_acknowledgement': True,
        'actual_install_enabled': False, 'installation_allowed': False,
        'installed': False, 'executed': False,
        'destination_modified': False,
    }


def _ledger_path(root):
    root = Path(root).resolve()
    return no_symlink(root, root / 'private' / 'install-simulation' / 'events.sqlite3')


def _events(connection):
    return connection.execute('SELECT sequence, payload, previous_hash, event_hash FROM events ORDER BY sequence').fetchall()


def _validate_history(connection):
    previous = '0' * 64
    status = {}
    last_sequence = 0
    for sequence, raw, prev_hash, event_hash in _events(connection):
        if sequence != last_sequence + 1 or prev_hash != previous:
            raise ValueError('Simulated install ledger sequence or hash-chain conflict')
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            raise ValueError('Invalid simulated-install event')
        if (not isinstance(payload, dict)
                or payload.get('schema_version') != EVENT_SCHEMA
                or payload.get('simulation_only') is not True
                or payload.get('real_installation_performed') is not False
                or payload.get('real_execution_performed') is not False):
            raise ValueError('Simulated install ledger tampering detected: invalid event metadata')
        computed = hashlib.sha256((previous + '\n').encode() + _json_bytes(payload)).hexdigest()
        if computed != event_hash or not ID_PATTERN.fullmatch(str(payload.get('plan_id'))):
            raise ValueError('Simulated install ledger tampering detected')
        plan_id = payload['plan_id']
        action = payload.get('action')
        if action == 'simulate_apply':
            if status.get(plan_id) == 'simulated_active':
                raise ValueError('Invalid repeated active install event')
            status[plan_id] = 'simulated_active'
        elif action == 'simulate_rollback':
            if status.get(plan_id) != 'simulated_active':
                raise ValueError('Invalid rollback event without active simulated install')
            status[plan_id] = 'simulated_rolled_back'
        else:
            raise ValueError('Unexpected simulated-install event type')
        previous = event_hash
        last_sequence = sequence
    return status, previous, last_sequence


def _open_ledger(root, create=False):
    path = _ledger_path(root)
    if not create and not path.exists():
        return None
    if create:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name == 'posix':
            path.parent.chmod(0o700)
    no_symlink(Path(root).resolve(), path)
    # SQLite's transactional write locking works on both macOS and Windows.
    connection = (sqlite3.connect(str(path), timeout=10.0) if create
                  else sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=10.0))
    if create:
        if os.name == 'posix':
            path.chmod(0o600)
        connection.execute('''CREATE TABLE IF NOT EXISTS events (
            sequence INTEGER PRIMARY KEY, payload TEXT NOT NULL,
            previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL UNIQUE
        )''')
    return connection


def simulation_status(plan_id, *, root=ROOT):
    if not ID_PATTERN.fullmatch(str(plan_id)):
        raise ValueError('A valid SHA-256 plan ID is required')
    connection = _open_ledger(root, create=False)
    if connection is None:
        return {'plan_id': plan_id, 'status': 'never_simulated',
                'event_count': 0, 'real_installation_performed': False}
    try:
        states, _, count = _validate_history(connection)
        return {'plan_id': plan_id, 'status': states.get(plan_id, 'never_simulated'),
                'event_count': count, 'real_installation_performed': False}
    finally:
        connection.close()


def simulate(action, plan_id, *, acknowledgement, root=ROOT, plan=None):
    if action not in ('apply', 'rollback'):
        raise ValueError('Simulation action must be apply or rollback')
    if not ID_PATTERN.fullmatch(str(plan_id)) or acknowledgement != plan_id:
        raise ValueError('Explicit acknowledgement of the exact plan ID is required')
    if action == 'apply':
        if not isinstance(plan, dict) or plan.get('plan_id') != plan_id:
            raise ValueError('Regenerate and verify the exact current plan before simulation')
        if not plan.get('simulation_apply_eligible'):
            raise ValueError('Simulated apply requires a verified, non-flagged local package')
    root = Path(root).resolve()
    if action == 'rollback' and not _ledger_path(root).is_file():
        raise ValueError('No active simulated installation ledger exists for rollback')
    connection = _open_ledger(root, create=True)
    try:
        connection.execute('BEGIN IMMEDIATE')
        states, previous_hash, count = _validate_history(connection)
        existing = states.get(plan_id)
        if action == 'apply' and existing == 'simulated_active':
            raise ValueError('This plan is already simulated as active')
        if action == 'rollback' and existing != 'simulated_active':
            raise ValueError('Only a simulated active plan may be rolled back')
        payload = {
            'schema_version': EVENT_SCHEMA,
            'plan_id': plan_id,
            'action': 'simulate_apply' if action == 'apply' else 'simulate_rollback',
            'timestamp_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            'simulation_only': True,
            'real_installation_performed': False,
            'real_execution_performed': False,
        }
        if action == 'apply':
            payload['source_record_id'] = plan['source_record_id']
            payload['commit_sha'] = plan['pinned_version']['commit_sha']
            payload['agent'] = plan['agent']
            payload['scope'] = plan['scope']
        event_hash = hashlib.sha256((previous_hash + '\n').encode() + _json_bytes(payload)).hexdigest()
        connection.execute('INSERT INTO events(sequence, payload, previous_hash, event_hash) VALUES (?, ?, ?, ?)',
                           (count + 1, json.dumps(payload, ensure_ascii=False), previous_hash, event_hash))
        connection.commit()
        return {
            'plan_id': plan_id,
            'status': 'simulated_active' if action == 'apply' else 'simulated_rolled_back',
            'event_sequence': count + 1,
            'event_sha256': event_hash,
            'ledger_location': 'private/install-simulation/events.sqlite3',
            'simulation_only': True,
            'real_installation_performed': False,
            'real_execution_performed': False,
            'agent_files_modified': False,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
