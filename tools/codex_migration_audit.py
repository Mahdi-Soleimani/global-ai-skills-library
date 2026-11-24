#!/usr/bin/env python3
"""Read-only legacy Codex -> host-scoped receipt compatibility rehearsal.

Only strictly understood active pinned histories are mapped in memory.
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
    if os.name == 'nt':
        from windows_user_profile import assert_no_reparse_components
        assert_no_reparse_components(path)
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
    # Reject redirected/hardlinked entries before hashing or descending.
    # This is a bounded cooperative audit, not a hostile-filesystem lock.
    from install_bundle import MAX_FILES, MAX_BYTES, MAX_ONE_FILE
    pending, count, total = [folder], 0, 0
    while pending:
        current = pending.pop()
        for item in current.iterdir():
            count += 1
            if count > MAX_FILES * 32:
                raise AuditBlocked('excessive_inventory_entries')
            if is_redirected(item):
                raise AuditBlocked('unsafe_inventory_entry')
            if os.name == 'nt':
                from windows_user_profile import assert_no_reparse_components
                assert_no_reparse_components(item)
            require_windows_filename_safety(item.relative_to(folder).as_posix(), portable=True)
            info = item.stat()
            if stat.S_ISDIR(info.st_mode):
                pending.append(item)
            elif not stat.S_ISREG(info.st_mode):
                raise AuditBlocked('unsafe_inventory_entry')
            else:
                if info.st_nlink != 1:
                    raise AuditBlocked('hardlinked_inventory')
                total += info.st_size
                if info.st_size > MAX_ONE_FILE or total > MAX_BYTES:
                    raise AuditBlocked('excessive_inventory_bytes')
    entries = _inventory(folder)
    if not any(row['path'] == 'SKILL.md' for row in entries):
        raise AuditBlocked('missing_root_skill')
    return entries


def _candidate_receipt(value, slug, prefix, *, prior_manifests=None):
    legacy._checked_receipt(value, slug)
    if any(not isinstance(value[key], str) for key in ('plan_id', 'binding', 'transaction')):
        raise AuditBlocked('invalid_record_identity_type')
    historical_action = value['action']
    if historical_action not in ('fresh_install', 'replace_install', 'restore_backup'):
        raise AuditBlocked('historical_action_requires_explicit_semantics')
    if historical_action == 'restore_backup':
        if value.get('source_kind') != 'pinned':
            raise AuditBlocked('unmanaged_restore_requires_manual_review')
        if set(value) != _BASE_RECEIPT | {'backup_ids', 'restored_backup_id', 'source_kind'}:
            raise AuditBlocked('historical_fields_require_explicit_semantics')
    elif set(value) not in (_BASE_RECEIPT, _BASE_RECEIPT | {'backup_ids'}):
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
        action = 'replace' if historical_action == 'replace_install' else 'restore'
    candidate = {
        'schema': native.SCHEMA, 'host': 'codex', 'scope': 'project',
        'slug': slug, 'action': action, 'transaction': value['transaction'],
        'plan_id': value['plan_id'], 'binding': value['binding'],
        'files': value['files'], 'backup_ids': list(prefix),
    }
    if action == 'restore':
        selected_id = value['restored_backup_id']
        # The selected backup must predate the archive created by the
        # restore itself. Match its exact recorded bytes and Plan identity.
        if selected_id not in prefix[:-1] or prior_manifests is None:
            raise AuditBlocked('restore_source_lineage_mismatch')
        selected = prior_manifests.get(selected_id)
        if (selected is None or selected['files'] != value['files']
                or selected['previous_receipt']['plan_id'] != value['plan_id']):
            raise AuditBlocked('restore_source_evidence_mismatch')
        candidate['restored_backup_id'] = selected_id
    return native._receipt_valid(candidate, 'codex', slug)


ARCHIVE_EVIDENCE_SCHEMA = 'gasl-codex-legacy-archive-evidence-v1'


def _archive_candidate(marker, marker_sha, active, mapped, *, target_sha):
    """Map only verified locally recorded evidence, never authorize a write.

    Keep the complete path-bound original marker in a separate evidence
    record. This is a rehearsal model, not an accepted production schema.
    """
    slug = marker['slug']
    ids = marker['backup_ids']
    by_id = {item['backup_id']: item for item in mapped}
    last = by_id[marker['uninstall_event_id']]['previous_receipt']
    if marker['target_sha256'] != target_sha:
        raise AuditBlocked('invalid_project_bound_uninstall_marker')
    evidence = {
        'schema': ARCHIVE_EVIDENCE_SCHEMA, 'host': 'codex', 'scope': 'project',
        'slug': slug, 'target_sha256': target_sha,
        'legacy_marker_sha256': marker_sha,
        'legacy_marker': marker,
        'historical_ownership_independently_verified': False,
        'production_migration_enabled': False,
    }
    if active is None:
        candidate = None
        native_marker = {
            'schema': native.SCHEMA, 'host': 'codex', 'scope': 'project',
            'slug': slug, 'status': 'uninstalled_archive',
            'archive_id': marker['uninstall_event_id'],
            'last_receipt': last, 'backup_ids': ids,
        }
    else:
        native_marker = None
        if active['action'] == 'reinstall_backup':
            if set(active) != _BASE_RECEIPT | {
                    'backup_ids', 'restored_backup_id', 'uninstall_event_id', 'source_kind'}:
                raise AuditBlocked('historical_fields_require_explicit_semantics')
            if any(not isinstance(active[key], str) for key in ('plan_id', 'binding', 'transaction')):
                raise AuditBlocked('invalid_record_identity_type')
            candidate = native._receipt_valid({
                'schema': native.SCHEMA, 'host': 'codex', 'scope': 'project',
                'slug': slug, 'action': 'reinstall', 'transaction': active['transaction'],
                'plan_id': active['plan_id'], 'binding': active['binding'],
                'files': active['files'], 'backup_ids': active['backup_ids'],
                'reinstalled_backup_id': active['restored_backup_id'],
            }, 'codex', slug)
        else:
            candidate = _candidate_receipt(active, slug, active['backup_ids'], prior_manifests=by_id)
    return {'receipt': candidate, 'marker': native_marker, 'manifests': mapped,
            'historical_evidence': evidence}


def _snapshot(root, slug):
    if _present(root / '.gasl-codex-migration-pending'):
        raise AuditBlocked('migration_recovery_required')
    base = root / legacy.STATE
    destination = base / 'hosts' / 'codex'
    for path in (base, base / 'hosts', destination):
        _directory(path)
    for store in (base, destination):
        for name in ('receipts', 'journals', 'backups', 'stage', 'uninstalled'):
            _directory(store / name)
        _directory(store / 'backups' / slug)
    evidence_dir = destination / 'historical-evidence'
    _directory(evidence_dir)
    if any(_present(evidence_dir / (slug + suffix)) for suffix in ('.json', '.legacy-marker')):
        raise AuditBlocked('destination_ownership_or_pending_state')
    target, _ = _target_path(root, 'codex', 'project', slug)
    _directory(target)
    if (any(_present(destination / name / (slug + '.json'))
            for name in ('receipts', 'journals', 'uninstalled'))
            or _nonempty(destination / 'backups' / slug)
            or _nonempty(destination / 'stage')):
        raise AuditBlocked('destination_ownership_or_pending_state')
    if _present(legacy._journal(base, slug)) or _nonempty(base / 'stage'):
        raise AuditBlocked('legacy_recovery_required')
    marker_path = base / 'uninstalled' / (slug + '.json')
    receipt_path = legacy._receipt(base, slug)
    marker = None
    marker_sha = None
    if _present(marker_path):
        # Native active receipts cannot coexist with a retained uninstall
        # marker, and native archive markers do not enforce the old path
        # binding. Inspect evidence, but never silently convert this state.
        marker, marker_sha = _record(marker_path)
        from codex_uninstalled_restore import MARKER_SCHEMA
        expected_fields = {'schema', 'kind', 'slug', 'target_sha256',
                           'uninstall_event_id', 'archived_current_backup_id',
                           'last_receipt', 'backup_ids'}
        if (not isinstance(marker, dict) or set(marker) != expected_fields
                or marker['schema'] != MARKER_SCHEMA
                or marker['kind'] != 'uninstalled_codex_project_skill'
                or marker['slug'] != slug
                or marker['target_sha256'] != hashlib.sha256(os.fsencode(str(target))).hexdigest()
                or marker['uninstall_event_id'] != marker['archived_current_backup_id']
                or not isinstance(marker['uninstall_event_id'], str)
                or not native.TXID.fullmatch(marker['uninstall_event_id'])):
            raise AuditBlocked('invalid_project_bound_uninstall_marker')
        last = legacy._checked_receipt(marker['last_receipt'], slug)
        expected_ids = last.get('backup_ids', []) + [marker['uninstall_event_id']]
        if (marker['backup_ids'] != expected_ids or len(expected_ids) > 1000
                or len(set(expected_ids)) != len(expected_ids)):
            raise AuditBlocked('uninstall_marker_lineage_mismatch')
    if _present(receipt_path):
        active, active_sha = _record(receipt_path)
        legacy._checked_receipt(active, slug)
        ids = active.get('backup_ids', [])
        if not target.is_dir() or _inventory_checked(target) != active['files']:
            raise AuditBlocked('active_inventory_mismatch')
        if marker is not None and ids[:len(marker['backup_ids'])] != marker['backup_ids']:
            raise AuditBlocked('uninstall_marker_lineage_mismatch')
    elif marker is not None:
        if _present(target):
            raise AuditBlocked('archived_target_occupied')
        active, active_sha = None, None
        ids = marker['backup_ids']
    else:
        if _nonempty(base / 'backups' / slug):
            raise AuditBlocked('unowned_history_requires_manual_review')
        raise AuditBlocked('no_legacy_active_receipt')
    parent = base / 'backups' / slug
    expected = set(ids) | {ident + '.json' for ident in ids}
    actual = {p.name for p in parent.iterdir()} if parent.is_dir() else set()
    if actual != expected:
        raise AuditBlocked('unknown_or_missing_backup_entries')
    source_digests, mapped, mapped_by_id, originals = [], [], {}, {}
    for index, ident in enumerate(ids):
        path = legacy._backup_manifest(base, slug, ident)
        manifest, raw_sha = _record(path)
        legacy._checked_backup(manifest, slug, ident)
        if set(manifest) != _MANIFEST_FIELDS:
            raise AuditBlocked('historical_fields_require_explicit_semantics')
        previous = manifest['previous_receipt']
        if previous is None:
            raise AuditBlocked('unmanaged_backup_requires_manual_review')
        converted = _candidate_receipt(previous, slug, ids[:index], prior_manifests=mapped_by_id)
        if _inventory_checked(legacy._backup_dir(base, slug, ident)) != manifest['files']:
            raise AuditBlocked('backup_inventory_mismatch')
        item = {'schema': native.SCHEMA, 'host': 'codex', 'scope': 'project',
                'slug': slug, 'backup_id': ident, 'previous_receipt': converted,
                'files': manifest['files']}
        native._manifest_valid(item, 'codex', slug, ident)
        mapped.append(item)
        mapped_by_id[ident] = item
        originals[ident] = manifest
        source_digests.append({'backup_id': ident, 'manifest_sha256': raw_sha,
                               'inventory_sha256': _digest(manifest['files'])})
    if marker is not None:
        last_manifest = originals[marker['uninstall_event_id']]
        if last_manifest['previous_receipt'] != marker['last_receipt']:
            raise AuditBlocked('uninstall_marker_archive_mismatch')
        if active is not None:
            # A retained marker is itself historical ownership evidence.
            # Validate current reinstatement evidence, but do not discard it
            # to satisfy the native schema's active/archived exclusivity.
            if active['action'] == 'reinstall_backup':
                if active.get('source_kind') != 'pinned':
                    raise AuditBlocked('unmanaged_restore_requires_manual_review')
                selected = mapped_by_id.get(active['restored_backup_id'])
                if (active['uninstall_event_id'] != marker['uninstall_event_id']
                        or active['restored_backup_id'] not in marker['backup_ids']
                        or ids != marker['backup_ids']
                        or selected is None or selected['files'] != active['files']
                        or selected['previous_receipt']['plan_id'] != active['plan_id']):
                    raise AuditBlocked('reinstall_source_evidence_mismatch')
            else:
                _candidate_receipt(active, slug, ids, prior_manifests=mapped_by_id)
        archive_candidate = _archive_candidate(marker, marker_sha, active, mapped,
                                                target_sha=hashlib.sha256(os.fsencode(str(target))).hexdigest())
        return {
            'archive_rehearsal_metadata_sha256': _digest(archive_candidate),
            'source_snapshot_sha256': _digest({
                'root_binding': hashlib.sha256(os.fsencode(str(root))).hexdigest(),
                'slug': slug, 'receipt_sha256': active_sha,
                'marker_sha256': marker_sha, 'backups': source_digests,
            }),
            'backup_count': len(ids),
            'active_file_count': len(active['files']) if active else 0,
            'historical_lifecycle': 'active_with_retained_uninstall_marker' if active else 'uninstalled_owned',
            'project_bound_archive_evidence_checked': True,
            'candidate_metadata_sha256': None,
            'candidate_record_count': 0,
        }
    candidate = _candidate_receipt(active, slug, ids, prior_manifests=mapped_by_id)
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
        'historical_lifecycle': None, 'project_bound_archive_evidence_checked': False,
        'archive_rehearsal_metadata_sha256': None,
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
        if first['candidate_metadata_sha256'] is None:
            report.update(status='blocked',
                          reason_code='uninstall_marker_requires_explicit_semantics')
        else:
            report.update(status='candidate_metadata_verified_read_only',
                          reason_code='simple_locally_recorded_chain_compatible')
    except AuditBlocked as exc:
        report['reason_code'] = str(exc)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        report['reason_code'] = 'invalid_or_unsafe_local_evidence'
    return report
