#!/usr/bin/env python3
"""Read-only legacy Codex -> host-scoped receipt compatibility rehearsal.

Only a strictly understood active fresh/replace chain is mapped in memory.
No migration, authorization, ownership attestation, source fetch or write is
performed. Other histories retain their original semantics and are blocked.
"""
import hashlib
import json
import os
import stat

import codex_project_install as legacy
import host_project_install as native
from fixture_bundle_install import _inventory
from host_target_preflight import _target_path
from transaction_file_lock import is_redirected, require_windows_filename_safety

SCHEMA = 'gasl-codex-migration-audit-v1'
_BASE_RECEIPT = {'schema', 'action', 'slug', 'transaction', 'plan_id', 'binding', 'files'}
_MANIFEST_FIELDS = {'schema', 'kind', 'slug', 'backup_id', 'transaction', 'previous_receipt', 'files'}


class AuditBlocked(ValueError):
    pass


def _digest(value):
    return hashlib.sha256(legacy._serialized(value)).hexdigest()


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise AuditBlocked('duplicate_json_key')
        value[key] = item
    return value


def _record(path):
    if is_redirected(path):
        raise AuditBlocked('unsafe_record')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 100_000:
        raise AuditBlocked('unsafe_record')
    with path.open('rb') as stream:
        raw = stream.read(100_001)
    if len(raw) > 100_000:
        raise AuditBlocked('unsafe_record')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object), hashlib.sha256(raw).hexdigest()


def _directory(path):
    if is_redirected(path) or (path.exists() and not path.is_dir()):
        raise AuditBlocked('unsafe_state_directory')
    if os.name == 'nt':
        from windows_user_profile import assert_no_reparse_components
        assert_no_reparse_components(path)


def _present(path):
    return path.exists() or is_redirected(path)


def _nonempty(path):
    return path.is_dir() and next(path.iterdir(), None) is not None


def _inventory_checked(folder):
    _directory(folder)
    entries = _inventory(folder)
    if not any(row['path'] == 'SKILL.md' for row in entries):
        raise AuditBlocked('missing_root_skill')
    for row in entries:
        require_windows_filename_safety(row['path'], portable=True)
        item = folder / row['path']
        if item.stat().st_nlink != 1:
            raise AuditBlocked('hardlinked_inventory')
    return entries


def _candidate_receipt(value, slug, prefix):
    legacy._checked_receipt(value, slug)
    if any(not isinstance(value[key], str) for key in ('plan_id', 'binding', 'transaction')):
        raise AuditBlocked('invalid_record_identity_type')
    if value['action'] not in ('fresh_install', 'replace_install'):
        raise AuditBlocked('historical_action_requires_explicit_semantics')
    if set(value) not in (_BASE_RECEIPT, _BASE_RECEIPT | {'backup_ids'}):
        raise AuditBlocked('historical_fields_require_explicit_semantics')
    if value.get('backup_ids', []) != prefix:
        raise AuditBlocked('backup_lineage_mismatch')
    if value['action'] == 'fresh_install':
        if prefix:
            raise AuditBlocked('backup_lineage_mismatch')
        action = 'install'
    else:
        if not prefix or value['transaction'] != prefix[-1]:
            raise AuditBlocked('backup_lineage_mismatch')
        action = 'replace'
    candidate = {
        'schema': native.SCHEMA, 'host': 'codex', 'scope': 'project',
        'slug': slug, 'action': action, 'transaction': value['transaction'],
        'plan_id': value['plan_id'], 'binding': value['binding'],
        'files': value['files'], 'backup_ids': list(prefix),
    }
    return native._receipt_valid(candidate, 'codex', slug)


def _snapshot(root, slug):
    base = root / legacy.STATE
    destination = base / 'hosts' / 'codex'
    for path in (base, base / 'hosts', destination):
        _directory(path)
    for store in (base, destination):
        for name in ('receipts', 'journals', 'backups', 'stage', 'uninstalled'):
            _directory(store / name)
        _directory(store / 'backups' / slug)
    target, _ = _target_path(root, 'codex', 'project', slug)
    _directory(target)
    if (any(_present(destination / name / (slug + '.json'))
            for name in ('receipts', 'journals', 'uninstalled'))
            or _nonempty(destination / 'backups' / slug)
            or _nonempty(destination / 'stage')):
        raise AuditBlocked('destination_ownership_or_pending_state')
    if _present(legacy._journal(base, slug)) or _nonempty(base / 'stage'):
        raise AuditBlocked('legacy_recovery_required')
    if _present(base / 'uninstalled' / (slug + '.json')):
        # Do not erase project-bound historical marker semantics, including
        # an older marker retained after a reinstall.
        raise AuditBlocked('uninstall_marker_requires_explicit_semantics')
    receipt_path = legacy._receipt(base, slug)
    if not _present(receipt_path):
        if _nonempty(base / 'backups' / slug):
            raise AuditBlocked('unowned_history_requires_manual_review')
        raise AuditBlocked('no_legacy_active_receipt')
    active, active_sha = _record(receipt_path)
    legacy._checked_receipt(active, slug)
    ids = active.get('backup_ids', [])
    candidate = _candidate_receipt(active, slug, ids)
    if not target.is_dir() or _inventory_checked(target) != active['files']:
        raise AuditBlocked('active_inventory_mismatch')
    parent = base / 'backups' / slug
    expected = set(ids) | {ident + '.json' for ident in ids}
    actual = {p.name for p in parent.iterdir()} if parent.is_dir() else set()
    if actual != expected:
        raise AuditBlocked('unknown_or_missing_backup_entries')
    source_digests, mapped = [], []
    for index, ident in enumerate(ids):
        path = legacy._backup_manifest(base, slug, ident)
        manifest, raw_sha = _record(path)
        legacy._checked_backup(manifest, slug, ident)
        if set(manifest) != _MANIFEST_FIELDS:
            raise AuditBlocked('historical_fields_require_explicit_semantics')
        previous = manifest['previous_receipt']
        if previous is None:
            raise AuditBlocked('unmanaged_backup_requires_manual_review')
        converted = _candidate_receipt(previous, slug, ids[:index])
        if _inventory_checked(legacy._backup_dir(base, slug, ident)) != manifest['files']:
            raise AuditBlocked('backup_inventory_mismatch')
        item = {'schema': native.SCHEMA, 'host': 'codex', 'scope': 'project',
                'slug': slug, 'backup_id': ident, 'previous_receipt': converted,
                'files': manifest['files']}
        native._manifest_valid(item, 'codex', slug, ident)
        mapped.append(item)
        source_digests.append({'backup_id': ident, 'manifest_sha256': raw_sha,
                               'inventory_sha256': _digest(manifest['files'])})
    # No converted records are emitted to stdout or persisted. The original
    # binding is retained as historical evidence, never as a new approval.
    return {
        'source_snapshot_sha256': _digest({
            'root_binding': hashlib.sha256(os.fsencode(str(root))).hexdigest(),
            'slug': slug, 'receipt_sha256': active_sha,
            'active_inventory_sha256': _digest(active['files']),
            'backups': source_digests,
        }),
        'candidate_metadata_sha256': _digest({'receipt': candidate, 'manifests': mapped}),
        'backup_count': len(ids),
        'active_file_count': len(active['files']),
        'candidate_record_count': 1 + len(mapped),
    }


def audit_legacy_migration(slug, selected_root):
    """Return a bounded compatibility report, never a write-capable plan."""
    if not isinstance(slug, str) or not legacy.SLUG.fullmatch(slug):
        raise ValueError('Exact safe Skill slug required')
    report = {
        'schema': SCHEMA, 'host': 'codex', 'scope': 'project', 'slug': slug,
        'status': 'blocked', 'reason_code': 'not_checked',
        'source_schema': legacy.SCHEMA, 'candidate_schema': native.SCHEMA,
        'source_snapshot_sha256': None, 'candidate_metadata_sha256': None,
        'backup_count': 0, 'active_file_count': 0, 'candidate_record_count': 0,
        'read_only': True, 'migration_performed': False,
        'migration_write_allowed': False, 'local_tty_approval_collected': False,
        'upstream_provenance_revalidated': False,
        'historical_ownership_independently_verified': False,
        'real_host_files_modified': False, 'third_party_skill_executed': False,
        'rollback_implementation_verified': False,
        'cooperative_lock_acquired': False,
    }
    try:
        require_windows_filename_safety(slug, portable=True)
        if os.name == 'nt':
            from windows_user_profile import assert_no_reparse_components
            assert_no_reparse_components(selected_root)
        root = legacy._root(selected_root)
        first = _snapshot(root, slug)
        # Detect observable changes during audit without creating any lock,
        # journal, directory or other filesystem record. Not an atomic view.
        if first != _snapshot(root, slug):
            raise AuditBlocked('state_changed_during_audit')
        report.update(first)
        report.update(status='candidate_metadata_verified_read_only',
                      reason_code='simple_locally_recorded_chain_compatible')
    except AuditBlocked as exc:
        report['reason_code'] = str(exc)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        report['reason_code'] = 'invalid_or_unsafe_local_evidence'
    return report
