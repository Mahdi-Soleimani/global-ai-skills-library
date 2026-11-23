#!/usr/bin/env python3
"""Phase 46: offline, read-only evidence comparison for Codex Skill versions.

Local checksum, provenance claims and upstream authenticity are separate facts.
No network, installer, subprocess, Skill execution or user-profile writes.
"""
import os
import hashlib
import json
import re

from codex_backup_review import review_codex_backups
from codex_project_install import (
    _root, _paths, _receipt, _load, _checked_receipt, _checked_backup,
    _backup_manifest, _backup_dir, _inventory, _serialized,
)

SCHEMA = 'gasl-codex-version-provenance-v1'
BACKUP_ID = re.compile(r'^[a-f0-9]{32}$')

UPSTREAM_NOT_CHECKED = {
    'repository_and_publisher_identity': 'not_checked',
    'source_commit_and_git_blob': 'not_checked',
    'license_and_notices': 'not_checked',
    'instructions_dependencies_and_runtime_safety': 'not_checked',
}


def _fingerprint(files):
    return hashlib.sha256(_serialized(files)).hexdigest()


def _files_checked(root, slug, ident, review):
    target, _, state = _paths(root, slug)
    if ident == 'active':
        if review['lifecycle'] != 'installed':
            raise ValueError('Active Skill is unavailable when not installed')
        receipt = _checked_receipt(_load(_receipt(state, slug)), slug)
        expected = receipt['files']
        actual = _inventory(target)
        if actual != expected:
            raise ValueError('Active Skill was changed during provenance review')
        return actual, receipt
    if not BACKUP_ID.fullmatch(str(ident)):
        raise ValueError('Invalid exact Backup ID')
    manifest = _checked_backup(_load(_backup_manifest(state, slug, ident)), slug, ident)
    expected = manifest['files']
    actual = _inventory(_backup_dir(state, slug, ident))
    if actual != expected:
        raise ValueError('Backup bytes changed during provenance review')
    return actual, manifest['previous_receipt']


def _manual_attestation_in_ancestry(root, slug, record):
    """Read-only: follow recorded restore/reinstall ancestry without upgrading trust.

    Older receipts can omit the original manual-attestation warning after
    subsequent reinstallation. Follow only exact, verified local archives;
    never infer a verified historical owner from a new managed receipt.
    """
    if record is None:
        return False
    _, _, state = _paths(root, slug)
    visited = set()
    for _ in range(1001):
        if record.get('historical_project_ownership_verified') is False:
            return True
        if record.get('action') not in ('reinstall_backup', 'restore_backup'):
            return False
        selected = record.get('restored_backup_id')
        if not BACKUP_ID.fullmatch(str(selected)) or selected in visited:
            raise ValueError('Invalid circular restore ancestry')
        visited.add(selected)
        manifest = _checked_backup(
            _load(_backup_manifest(state, slug, selected)), slug, selected)
        if _inventory(_backup_dir(state, slug, selected)) != manifest['files']:
            raise ValueError('Restore ancestry backup was changed')
        record = manifest['previous_receipt']
        if record is None:
            return False
    raise ValueError('Restore ancestry exceeds maximum verified depth')


def _evidence_for_row(item, review, receipt):
    lifecycle = review['lifecycle']
    active = item['version_id'] == 'active'
    recorded_plan = item.get('recorded_plan_id')
    manual = active and receipt.get('historical_project_ownership_verified') is False
    if lifecycle == 'uninstalled_legacy':
        owner = 'historical_project_ownership_unproven'
        proof = 'none'
    elif manual or (receipt is not None
                    and receipt.get('historical_project_ownership_verified') is False):
        owner = 'manual_attestation_does_not_verify_historical_ownership'
        proof = 'local_management_receipt_only'
    elif not active and receipt is None:
        owner = 'historical_version_precedes_GASL_management'
        proof = 'local_backup_inventory_only'
    elif lifecycle == 'uninstalled_owned':
        owner = 'project_bound_local_uninstall_marker_present'
        proof = 'local_project_marker_and_archived_receipts'
    else:
        owner = 'local_management_receipt_present'
        proof = 'locally_recorded_receipt'
    # A managed backup can have previous_receipt=None (a pre-managed Skill).
    if not active and receipt is None:
        plan_evidence = 'no_previous_GASL_receipt'
    elif lifecycle == 'uninstalled_legacy':
        plan_evidence = 'historical_receipt_reference_only' if recorded_plan else 'no_source_reference'
    elif recorded_plan:
        plan_evidence = 'GASL_local_receipt_claim_only'
    else:
        plan_evidence = 'no_source_reference'
    return {
        'local_file_sha256_inventory': 'verified_at_review_time',
        'local_ownership_evidence': owner,
        'local_owner_proof_type': proof,
        'source_plan_reference_evidence': plan_evidence,
        'source_plan_reference': recorded_plan,
        'upstream_checks': dict(UPSTREAM_NOT_CHECKED),
        'upstream_authenticity_verified': False,
        'historical_project_ownership_proven': False,
    }


def _version(root, slug, review, item):
    ident = item['version_id']
    files, receipt = _files_checked(root, slug, ident, review)
    recorded = item.get('recorded_plan_id')
    evidence = _evidence_for_row(item, review, receipt)
    if (review['lifecycle'] != 'uninstalled_legacy'
            and _manual_attestation_in_ancestry(root, slug, receipt)):
        evidence['local_ownership_evidence'] = (
            'manual_attestation_does_not_verify_historical_ownership')
        evidence['local_owner_proof_type'] = 'local_management_receipt_only'
    return {
        'version_id': ident,
        'role': 'active' if ident == 'active' else 'backup',
        'file_count': len(files),
        'content_manifest_sha256': _fingerprint(files),
        'local_file_integrity_verified': True,
        'recorded_source_kind': item['recorded_source_kind'],
        'recorded_plan_id': recorded,
        'historical_upstream_reference_only': item.get('historical_upstream_reference_only', False),
        'evidence': evidence,
        '_files': files,
    }


def _version_inputs(review):
    versions = []
    if review['lifecycle'] == 'installed':
        active = review['current_version']
        versions.append({
            'version_id': 'active',
            'recorded_source_kind': active['source_kind'],
            'recorded_plan_id': active['local_plan_id'],
        })
    for backup in review['backups']:
        category = backup['provenance']
        historical = category == 'unverified_historical_receipt_reference'
        versions.append({
            'version_id': backup['backup_id'],
            'recorded_source_kind': (
                'historical_reference_unverified' if historical else
                'pinned_recorded_locally' if category == 'local_recorded_pinned_plan' else
                'unmanaged'),
            'recorded_plan_id': backup['historical_plan_reference'],
            'historical_upstream_reference_only': historical,
        })
    return versions


def _compare(left, right):
    a = {x['path']: x['sha256'] for x in left['_files']}
    b = {x['path']: x['sha256'] for x in right['_files']}
    common = set(a) & set(b)
    changed = sum(a[k] != b[k] for k in common)
    identical_files = (not changed and set(a) == set(b))
    left_plan, right_plan = left['recorded_plan_id'], right['recorded_plan_id']
    return {
        'left_version_id': left['version_id'],
        'right_version_id': right['version_id'],
        'same_local_file_inventory': identical_files,
        'files_added_on_right': len(set(b)-set(a)),
        'files_removed_on_right': len(set(a)-set(b)),
        'files_changed': changed,
        'same_recorded_plan_reference': (
            left_plan == right_plan if left_plan and right_plan else None),
        'proves_same_upstream_source': False,
        'proves_safe_or_trusted_content': False,
        'interpretation': (
            'Content matches at local SHA-256 inventory level only; source authenticity is unverified.'
            if identical_files else
            'Content differs locally; neither upstream origin nor safety was verified.'),
    }


def compare_codex_provenance(slug, selected_root, *, left_id=None, right_id=None):
    """One selected Git project, no filesystem changes, no external verification."""
    if os.name == 'nt':
        from codex_native_review import compare
        return compare(slug, selected_root, left_id=left_id, right_id=right_id)
    if (left_id is None) != (right_id is None):
        raise ValueError('Select both --left and --right for a comparison')
    if left_id is not None and left_id == right_id:
        raise ValueError('Comparison needs two distinct versions')
    root = _root(selected_root)
    review = review_codex_backups(slug, root)
    public = {
        'schema': SCHEMA,
        'status': 'codex_provenance_comparison_read_only',
        'host': 'codex', 'scope': 'project', 'slug': slug,
        'relative_target': review['relative_target'],
        'lifecycle': review['lifecycle'],
        'ownership_evidence': review['ownership_evidence'],
        'historical_project_ownership_verified': review.get('historical_project_ownership_verified'),
        'upstream_verification_performed': False,
        'network_requests_performed': False,
        'installation_or_recovery_performed': False,
        'third_party_skill_executed': False,
        'real_host_files_modified': False,
        'approval_granted': False,
        'versions': [],
        'comparison': None,
        'next_verification_steps': [
            'Independently inspect the source repository owner and publisher.',
            'Check recorded source commit and SKILL.md blob against the authoritative upstream repository.',
            'Review license, notices, instructions, dependencies and runtime behavior separately.',
            'Do not infer historical project ownership from archived content hashes or local Plan IDs.',
        ],
    }
    if review['lifecycle'] not in ('installed', 'uninstalled_owned', 'uninstalled_legacy'):
        public['blocked_reason'] = review['title']
        if left_id is not None:
            raise ValueError('Cannot compare versions in a blocked or empty lifecycle')
        return public

    indexed = {}
    for item in _version_inputs(review):
        v = _version(root, slug, review, item)
        indexed[v['version_id']] = v
        # Keep internal file inventory out of all JSON and formatted output.
        public['versions'].append({k: value for k, value in v.items() if k != '_files'})
    if any(
            v['evidence']['local_ownership_evidence']
            == 'manual_attestation_does_not_verify_historical_ownership'
            for v in public['versions']):
        public['historical_project_ownership_verified'] = False
    if left_id is not None:
        if left_id not in indexed or right_id not in indexed:
            raise ValueError('Both selected versions must exist in the verified local history')
        public['comparison'] = _compare(indexed[left_id], indexed[right_id])
    return public


def format_provenance_comparison(result):
    lines = [
        'GASL / Codex Version Provenance — READ ONLY',
        'Skill: '+result['slug']+'   State: '+result['lifecycle'],
        'Source verification: NOT PERFORMED (offline)',
        'Historical ownership is NOT proven by local file hashes or Plan IDs.',
        '',
    ]
    if result.get('blocked_reason'):
        lines.extend(['Blocked: '+result['blocked_reason'],
                      'No versions can be compared in this state.'])
    else:
        for index, item in enumerate(result['versions'], 1):
            evidence = item['evidence']
            lines.extend([
                str(index)+'. '+item['version_id']+' ('+item['role']+')',
                '   Local files: '+str(item['file_count'])
                +'; SHA-256 inventory: '+item['content_manifest_sha256'],
                '   Recorded source kind: '+item['recorded_source_kind'],
                '   Recorded Plan reference: '+(item['recorded_plan_id'] or 'NONE'),
                '   Local evidence: '+evidence['source_plan_reference_evidence']
                +'; '+evidence['local_ownership_evidence'],
                '   Upstream publisher/commit/license/safety: NOT CHECKED',
            ])
        if result['comparison']:
            c = result['comparison']
            lines.extend([
                '',
                'Comparing '+c['left_version_id']+' vs '+c['right_version_id'],
                'Same local file content: '+str(c['same_local_file_inventory']),
                'Right-side added/removed/changed files: '
                +str(c['files_added_on_right'])+'/'+str(c['files_removed_on_right'])
                +'/'+str(c['files_changed']),
                'Same recorded Plan reference: '+str(c['same_recorded_plan_reference']),
                'CAUTION: '+c['interpretation'],
            ])
    lines.extend(['', 'Next independent verification:', *(
        '- '+line for line in result['next_verification_steps']),
        '', 'No file was modified, no Skill executed and no approval granted.'])
    return '\n'.join(lines)
