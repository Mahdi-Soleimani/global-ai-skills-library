"""Read-only review of native host-scoped Codex project records.

No legacy state adoption, migration, write approval or upstream verification.
The existing native installer remains the sole writer.
"""
import hashlib
import os

import codex_project_install as legacy
import host_project_install as native
from codex_migration_audit import _record, _directory, _inventory_checked, _present, _nonempty
from transaction_file_lock import require_windows_filename_safety

_BASE = {'schema', 'host', 'scope', 'slug', 'action', 'transaction',
         'plan_id', 'binding', 'files', 'backup_ids'}


def _receipt_checked(data, slug, prefix, prior):
    native._receipt_valid(data, 'codex', slug)
    action = data['action']
    extra = {'restore': 'restored_backup_id', 'reinstall': 'reinstalled_backup_id'}.get(action)
    if set(data) != (_BASE | ({extra} if extra else set())):
        raise ValueError('Unknown native receipt fields; preserve provenance evidence')
    if any(not isinstance(data[k], str) for k in ('plan_id', 'binding', 'transaction')):
        raise ValueError('Invalid native receipt identity type')
    if data['backup_ids'] != prefix:
        raise ValueError('Native backup lineage mismatch')
    if action == 'install' and prefix:
        raise ValueError('Fresh native receipt contains backup history')
    if action in ('replace', 'restore') and (not prefix or data['transaction'] != prefix[-1]):
        raise ValueError('Native transaction does not extend history')
    if extra:
        selected = data[extra]
        if selected not in (prefix[:-1] if action == 'restore' else prefix):
            raise ValueError('Native restore/reinstall source is outside prior history')
        origin = prior.get(selected)
        if (origin is None or origin['files'] != data['files']
                or origin['previous_receipt']['plan_id'] != data['plan_id']):
            raise ValueError('Native restore/reinstall source evidence mismatch')
    return data


def _snapshot(slug, selected_root):
    if not isinstance(slug, str) or not native.SLUG.fullmatch(slug):
        raise ValueError('Exact safe Skill slug required')
    require_windows_filename_safety(slug, portable=True)
    if os.name == 'nt':
        from windows_user_profile import assert_no_reparse_components
        assert_no_reparse_components(selected_root)
    root = legacy._root(selected_root)
    target, relative, state = native._paths(root, 'codex', slug)
    for path in (target, state, state/'receipts', state/'journals', state/'stage',
                 state/'uninstalled', state/'backups', state/'backups'/slug):
        _directory(path)
    journal = native._journal(state, slug)
    receipt_path, marker_path = native._receipt(state, slug), native._marker(state, slug)
    base = {'relative_target': relative, 'receipt': None, 'marker': None,
            'manifests': [], 'record_digests': []}
    if _present(journal) or _nonempty(state/'stage'):
        return dict(base, lifecycle='pending_transaction')
    active, marker = None, None
    if _present(receipt_path):
        active, digest = _record(receipt_path)
        base['record_digests'].append(digest)
        native._receipt_valid(active, 'codex', slug)
    if _present(marker_path):
        marker, digest = _record(marker_path)
        if not isinstance(marker, dict):
            raise ValueError('Invalid native archive marker')
        base['record_digests'].append(digest)
    if active is not None and marker is not None:
        raise ValueError('Conflicting native ownership receipts')
    if active is None and marker is None:
        if _nonempty(state/'backups'/slug):
            raise ValueError('Unowned native backup history requires separate review')
        return dict(base, lifecycle='unmanaged_target' if _present(target) else 'no_backups')
    if active is not None:
        if not target.is_dir() or _inventory_checked(target) != active['files']:
            raise ValueError('Native active Skill contents changed')
        ids = active['backup_ids']
    else:
        if _present(target):
            raise ValueError('Archived native target is occupied')
        if (not isinstance(marker, dict) or set(marker) != {
                'schema', 'host', 'scope', 'slug', 'status', 'archive_id',
                'last_receipt', 'backup_ids'}
                or marker['schema'] != native.SCHEMA or marker['host'] != 'codex'
                or marker['scope'] != 'project' or marker['slug'] != slug
                or marker['status'] != 'uninstalled_archive'):
            raise ValueError('Invalid native archive marker')
        last = native._receipt_valid(marker['last_receipt'], 'codex', slug)
        archive_id = marker['archive_id']
        ids = marker['backup_ids']
        if (not isinstance(archive_id, str) or not native.TXID.fullmatch(archive_id)
                or ids != last['backup_ids'] + [archive_id]):
            raise ValueError('Native archive lineage mismatch')
    if (not isinstance(ids, list) or len(ids) > 1000
            or any(not isinstance(x, str) or not native.TXID.fullmatch(x) for x in ids)
            or len(ids) != len(set(ids))):
        raise ValueError('Invalid native backup IDs')
    parent = state/'backups'/slug
    actual = {p.name for p in parent.iterdir()} if parent.is_dir() else set()
    if actual != set(ids) | {x+'.json' for x in ids}:
        raise ValueError('Unknown or missing native backup entries')
    prior = {}
    for index, ident in enumerate(ids):
        manifest, digest = _record(native._manifest(state, slug, ident))
        if set(manifest) != {'schema', 'host', 'scope', 'slug', 'backup_id',
                             'files', 'previous_receipt'}:
            raise ValueError('Unknown native backup metadata fields')
        native._manifest_valid(manifest, 'codex', slug, ident)
        _receipt_checked(manifest['previous_receipt'], slug, ids[:index], prior)
        if _inventory_checked(native._backup(state, slug, ident)) != manifest['files']:
            raise ValueError('Native backup contents changed')
        prior[ident] = manifest
        base['manifests'].append(manifest)
        base['record_digests'].append(digest)
    if active is not None:
        _receipt_checked(active, slug, ids, prior)
    elif prior[marker['archive_id']]['previous_receipt'] != marker['last_receipt']:
        raise ValueError('Native archive marker disagrees with archived receipt')
    return dict(base, receipt=active, marker=marker,
                lifecycle='installed' if active else 'uninstalled_owned')


def snapshot(slug, selected_root):
    first = _snapshot(slug, selected_root)
    if first != _snapshot(slug, selected_root):
        raise ValueError('Native review state changed during inspection')
    return first


def review(slug, selected_root, *, backup_id=None):
    data = snapshot(slug, selected_root)
    lifecycle, active, marker = data['lifecycle'], data['receipt'], data['marker']
    rows = []
    for manifest in data['manifests']:
        ident = manifest['backup_id']
        rows.append({'backup_id': ident, 'file_count': len(manifest['files']),
                     'file_integrity_verified': True,
                     'provenance': 'native_local_plan_reference',
                     'historical_plan_reference': manifest['previous_receipt']['plan_id'],
                     'ownership_evidence': 'native_host_scoped_local_receipt',
                     'eligible_for_recovery': active is None or manifest['files'] != active['files'],
                     'last_active_before_uninstall': bool(marker and ident == marker['archive_id'])})
    report = {
        'schema': 'gasl-codex-backup-review-v1', 'status': 'codex_backup_review_read_only',
        'host': 'codex', 'scope': 'project', 'slug': slug,
        'relative_target': data['relative_target'], 'lifecycle': lifecycle,
        'ownership_store': 'native_host_scoped', 'backup_count': len(rows), 'backups': rows,
        'title': {'installed': 'Native Codex managed Skill',
                  'uninstalled_owned': 'Native Codex archived Skill',
                  'pending_transaction': 'Pending native transaction; recover before review',
                  'unmanaged_target': 'Unmanaged target; no ownership claim',
                  'no_backups': 'No native managed history'}[lifecycle],
        'ownership_evidence': ('native_host_scoped_local_receipt' if active else
                               'native_local_archive_marker_not_project_bound' if marker else 'not_established'),
        'historical_project_ownership_verified': False,
        'manual_ownership_attestation_required': False,
        'project_path_disclosed': False, 'real_host_files_modified': False,
        'third_party_skill_executed': False, 'approval_granted': False,
        'upstream_provenance_revalidated': False,
        'available_recovery': any(x['eligible_for_recovery'] for x in rows),
        'safety_notice': 'Native local Plan references and archive markers do not prove upstream authenticity or historical project ownership.',
        'review_command_template': 'python tools/gasl.py backup-review --selected-root "$env:GASL_SELECTED_PROJECT" --skill-name '+slug+' --backup-id BACKUP_ID',
    }
    if active:
        report['current_version'] = {'local_plan_id': active['plan_id'],
                                     'source_kind': 'native_local_plan_reference',
                                     'historical_project_ownership_verified': None,
                                     'manual_ownership_attested': False}
    if backup_id is not None:
        selected = next((x for x in rows if x['backup_id'] == backup_id), None)
        if selected is None or not selected['eligible_for_recovery']:
            raise ValueError('No eligible native backup selection')
        action = 'restore' if active else 'reinstall'
        preview = (native.preview_restore if active else native.preview_reinstall)(
            'codex', selected_root, slug, backup_id)
        if data != snapshot(slug, selected_root):
            raise ValueError('Native review changed during preview')
        binding = preview['state_binding_id']
        report['selected'] = {
            **selected, 'state_binding_id': binding, 'preview_completed_read_only': True,
            'requires_real_local_tty_confirmation': True,
            'manual_ownership_attestation_required': False,
            'recovery_command': ('python tools/gasl.py host-project-install --host codex --action '
                +action+' --selected-root "$env:GASL_SELECTED_PROJECT" --skill-name '+slug
                +' --backup-id '+backup_id+' --state-binding-id '+binding),
        }
    return report


def compare(slug, selected_root, *, left_id=None, right_id=None):
    from codex_provenance_compare import SCHEMA, UPSTREAM_NOT_CHECKED, _compare
    if (left_id is None) != (right_id is None) or (left_id is not None and left_id == right_id):
        raise ValueError('Select two distinct version IDs')
    data = snapshot(slug, selected_root)
    active = data['receipt']
    versions = ([('active', active)] if active else []) + [
        (m['backup_id'], m['previous_receipt']) for m in data['manifests']]
    indexed = {}
    for ident, receipt in versions:
        files = receipt['files']
        indexed[ident] = {
            'version_id': ident, 'role': 'active' if ident == 'active' else 'backup',
            'file_count': len(files),
            'content_manifest_sha256': hashlib.sha256(legacy._serialized(files)).hexdigest(),
            'local_file_integrity_verified': True, 'recorded_source_kind': 'native_local_plan_reference',
            'recorded_plan_id': receipt['plan_id'], 'historical_upstream_reference_only': True,
            'evidence': {'local_file_sha256_inventory': 'verified_at_review_time',
                         'local_ownership_evidence': 'native_local_management_receipt_only',
                         'local_owner_proof_type': 'locally_recorded_receipt',
                         'source_plan_reference_evidence': 'GASL_local_receipt_claim_only',
                         'source_plan_reference': receipt['plan_id'],
                         'upstream_checks': dict(UPSTREAM_NOT_CHECKED),
                         'upstream_authenticity_verified': False,
                         'historical_project_ownership_proven': False},
            '_files': files,
        }
    comparison = None
    if left_id is not None:
        if left_id not in indexed or right_id not in indexed:
            raise ValueError('Both selected versions must exist in verified native history')
        comparison = _compare(indexed[left_id], indexed[right_id])
    return {
        'schema': SCHEMA, 'status': 'codex_provenance_comparison_read_only',
        'host': 'codex', 'scope': 'project', 'slug': slug, 'relative_target': data['relative_target'],
        'lifecycle': data['lifecycle'], 'ownership_store': 'native_host_scoped',
        'ownership_evidence': 'native_local_records_only' if indexed else 'not_established',
        'historical_project_ownership_verified': False, 'upstream_verification_performed': False,
        'network_requests_performed': False, 'installation_or_recovery_performed': False,
        'third_party_skill_executed': False, 'real_host_files_modified': False, 'approval_granted': False,
        'versions': [{k:v for k,v in x.items() if k != '_files'} for x in indexed.values()],
        'comparison': comparison,
        'next_verification_steps': ['Verify upstream repository, commit, blob, license and runtime safety independently.'],
        **({'blocked_reason': 'No verified native versions in this lifecycle'} if not indexed else {}),
    }
