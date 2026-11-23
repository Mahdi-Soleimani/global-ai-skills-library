#!/usr/bin/env python3
"""Phase 45: one read-only, provenance-aware Codex project Backup review.

This module chooses an *existing* verified lifecycle instead of creating a new
installation route. It never authorizes, stages, installs or executes a Skill.
"""
import os

from codex_project_install import (
    _root, _paths, _receipt, _journal, list_backups, preview_restore,
)
from codex_uninstalled_restore import (
    _marker_path, list_uninstalled_backups, preview_reinstall,
)
from codex_legacy_reconcile import audit_legacy_backups, preview_legacy_reinstall

REVIEW_SCHEMA = 'gasl-codex-backup-review-v1'

LIFECYCLES = {
    'installed': {
        'title': 'Installed Skill with managed backup history',
        'ownership_evidence': 'local_managed_receipt',
        'preview_action': 'preview-restore',
        'write_action': 'restore-backup',
    },
    'uninstalled_owned': {
        'title': 'Uninstalled Skill with a project-bound ownership marker',
        'ownership_evidence': 'local_project_bound_uninstall_marker',
        'preview_action': 'preview-reinstall',
        'write_action': 'reinstall-backup',
    },
    'uninstalled_legacy': {
        'title': 'Legacy backups without historical project ownership proof',
        'ownership_evidence': 'no_historical_ownership_proof',
        'preview_action': 'preview-legacy-reinstall',
        'write_action': 'reinstall-legacy-backup',
    },
}

PROJECT_VAR = '\"$GASL_SELECTED_PROJECT\"'


def _command(action, slug, backup_id=None, binding=None):
    # _paths validates slug; backup_id originates from existing validated
    # history or from the exact requested identifier that passed preflight.
    command = ('./gasl codex-project-install --action ' + action
               + ' --selected-root ' + PROJECT_VAR + ' --skill-name ' + slug)
    if backup_id:
        command += ' --backup-id ' + backup_id
    if binding:
        command += ' --state-binding-id ' + binding
    return command


def _summary_row(row, lifecycle):
    backup_id = row['backup_id']
    recorded_upstream = (
        row.get('upstream_plan_id')
        if lifecycle != 'uninstalled_legacy'
        else row.get('upstream_plan_id_in_historical_receipt'))
    if lifecycle == 'uninstalled_legacy':
        provenance = 'unverified_historical_receipt_reference' if recorded_upstream else 'unmanaged_historical'
        can_restore = True
        evidence = 'historical_project_ownership_unverified'
    else:
        provenance = ('local_recorded_pinned_plan' if row['source_kind'] == 'pinned'
                      else 'local_unmanaged_version')
        can_restore = row.get('eligible_for_restore', True)
        evidence = ('local_managed_receipt' if lifecycle == 'installed'
                    else 'local_project_bound_uninstall_marker')
    return {
        'backup_id': backup_id,
        'file_count': row['file_count'],
        'file_integrity_verified': row['backup_integrity_verified'],
        'provenance': provenance,
        'historical_plan_reference': recorded_upstream,
        'ownership_evidence': evidence,
        'eligible_for_recovery': can_restore,
        'last_active_before_uninstall': row.get('last_active_before_uninstall', False),
    }


def review_codex_backups(slug, selected_root, *, backup_id=None):
    """Return a useful, read-only review for one explicitly selected project.

    Never auto-discover projects, accept an implicit HOME or claim that local
    hash integrity establishes historical ownership.
    """
    if os.name == 'nt':
        from codex_native_review import review
        return review(slug, selected_root, backup_id=backup_id)
    root = _root(selected_root)
    target, relative, state = _paths(root, slug)
    journal = _journal(state, slug)
    receipt = _receipt(state, slug)
    marker = _marker_path(state, slug)

    # An interrupted transaction takes priority over all presentation and
    # preview actions. Do not touch potentially ambiguous file inventories.
    if journal.exists() or journal.is_symlink():
        lifecycle, data = 'pending_transaction', None
    elif target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_dir():
            lifecycle, data = 'occupied_unsafe_target', None
        elif receipt.is_symlink():
            lifecycle, data = 'invalid_ownership_record', None
        elif receipt.exists():
            lifecycle, data = 'installed', list_backups(slug, root)
            # A project can retain an uninstall marker after a successful
            # Phase-43 reinstall. Refuse mismatched or tampered ownership
            # history instead of labeling the state trusted by default.
            if marker.exists() or marker.is_symlink():
                from codex_uninstalled_restore import _read_marker
                from codex_project_install import _load, _checked_receipt
                historical = _read_marker(root, slug, state)
                current = _checked_receipt(_load(receipt), slug)
                if (historical is None
                        or current['backup_ids'][:len(historical['backup_ids'])]
                           != historical['backup_ids']):
                    raise ValueError('Installed Skill receipt differs from previous uninstall history')
        else:
            lifecycle, data = 'unmanaged_target', None
    elif receipt.exists() or receipt.is_symlink():
        lifecycle, data = 'missing_target_with_receipt', None
    elif marker.exists() or marker.is_symlink():
        # Fail closed on malformed/symlink ownership evidence. The existing
        # listing verifies every retained backup and the complete marker.
        lifecycle, data = 'uninstalled_owned', list_uninstalled_backups(slug, root)
    else:
        folder = state/'backups'/slug
        if folder.is_dir() and any(folder.iterdir()):
            lifecycle, data = 'uninstalled_legacy', audit_legacy_backups(slug, root)
        else:
            lifecycle, data = 'no_backups', None

    base = {
        'schema': REVIEW_SCHEMA,
        'status': 'codex_backup_review_read_only',
        'host': 'codex', 'scope': 'project', 'slug': slug,
        'relative_target': relative,
        'lifecycle': lifecycle, 'backup_count': 0, 'backups': [],
        'project_path_disclosed': False,
        'real_host_files_modified': False,
        'third_party_skill_executed': False,
        'approval_granted': False,
        'upstream_provenance_revalidated': False,
    }
    if lifecycle not in LIFECYCLES:
        explanations = {
            'pending_transaction': (
                'A pending transaction exists. Review and recover the journal before any backup operation.'),
            'occupied_unsafe_target': (
                'The Skill destination is occupied by an unsafe entry. Do not overwrite it.'),
            'invalid_ownership_record': (
                'An ownership receipt is a symlink. Manual investigation is required.'),
            'unmanaged_target': (
                'A Skill exists but has no matching GASL receipt. Do not claim its backup history.'),
            'missing_target_with_receipt': (
                'A GASL receipt exists without its Skill directory. Inspect before changes.'),
            'no_backups': (
                'No retained Backup history was found for the selected Skill.'),
        }
        base.update({
            'title': explanations[lifecycle],
            'available_recovery': False,
            'ownership_evidence': 'not_established',
            'next_steps': ([_command('recover', slug)] if lifecycle == 'pending_transaction'
                           else []),
            'safety_notice': ('No backup installation is offered in this state. '
                              'Recover does not guarantee success for modified transactions.'),
        })
        if backup_id is not None:
            raise ValueError('No backup selection is available in this blocked or empty state')
        return base

    config = LIFECYCLES[lifecycle]
    rows = [_summary_row(item, lifecycle) for item in data['backups']]
    base.update({
        'title': config['title'],
        'backup_count': len(rows),
        'backups': rows,
        'ownership_evidence': config['ownership_evidence'],
        'historical_project_ownership_verified': False if lifecycle == 'uninstalled_legacy' else None,
        'manual_ownership_attestation_required': lifecycle == 'uninstalled_legacy',
        'available_recovery': any(x['eligible_for_recovery'] for x in rows),
        'preview_action': config['preview_action'],
        'write_action': config['write_action'],
        'recovery_effect': {
            'installed': (
                'Restores the selected version and first saves the active version to a new Backup.'),
            'uninstalled_owned': (
                'Reinstalls the selected archived version into the currently empty Skill destination.'),
            'uninstalled_legacy': (
                'After human ownership attestation, copies the selected historical version '
                'into the empty Skill destination without changing existing Backups.'),
        }[lifecycle],
        'review_command_template': (
            './gasl backup-review --selected-root ' + PROJECT_VAR
            + ' --skill-name ' + slug + ' --backup-id BACKUP_ID'),
        'safety_notice': (
            'Local file hashes and backup receipts do NOT prove historical project ownership.'
            if lifecycle == 'uninstalled_legacy'
            else 'Backup integrity and locally recorded provenance do not certify upstream safety.'),
    })
    if lifecycle == 'installed':
        from codex_project_install import _load
        active = _load(receipt)
        base['current_version'] = {
            'local_plan_id': active['plan_id'],
            'source_kind': active.get('source_kind', 'pinned'),
            'historical_project_ownership_verified': (
                active.get('historical_project_ownership_verified')),
            'manual_ownership_attested': active.get('manual_ownership_attested', False),
        }
        # A historically manual recovery remains so even after it is managed.
        if active.get('historical_project_ownership_verified') is False:
            base['safety_notice'] += (
                ' Active Skill was manually reconciled; its earlier ownership remains unverified.')
    if backup_id is not None:
        selected = next((item for item in rows if item['backup_id'] == backup_id), None)
        if selected is None:
            raise ValueError('Selected backup not present in the verified history')
        if not selected['eligible_for_recovery']:
            raise ValueError('Selected Backup is identical to the active Skill; no recovery is needed')
        preview = {
            'installed': preview_restore,
            'uninstalled_owned': preview_reinstall,
            'uninstalled_legacy': preview_legacy_reinstall,
        }[lifecycle](slug, root, backup_id)
        binding = preview['state_binding_id']
        base['selected'] = {
            **selected,
            'state_binding_id': binding,
            'preview_completed_read_only': True,
            'requires_real_local_tty_confirmation': True,
            'manual_ownership_attestation_required': lifecycle == 'uninstalled_legacy',
            'recovery_command': _command(
                config['write_action'], slug, backup_id, binding),
        }
    return base


def format_backup_review(report):
    """Human-readable overview: no paths or installation action is executed."""
    lines = [
        'GASL / Codex Backup Review — READ ONLY',
        'Skill: ' + report['slug'] + '   Scope: project',
        'State: ' + report['lifecycle'],
        report['title'],
        'Ownership evidence: ' + report['ownership_evidence'],
        'Verified Backup count: ' + str(report['backup_count']),
        '',
    ]
    if report.get('current_version'):
        v = report['current_version']
        lines.append('Active local Plan ID: ' + v['local_plan_id'])
        lines.append('Active source record kind: ' + v['source_kind'])
        if v.get('historical_project_ownership_verified') is False:
            lines.append('Warning: active version was manually attested; earlier ownership UNVERIFIED')
        lines.append('')
    if report['backups']:
        lines.append('Backups (every listed archive passed SHA-256 and history checks):')
        for idx, row in enumerate(report['backups'], 1):
            label = ('recoverable' if row['eligible_for_recovery']
                     else 'same as active / not recoverable')
            lines.extend([
                str(idx) + '. ' + row['backup_id'] + ' — ' + label,
                '   Files: ' + str(row['file_count'])
                + ' | Recorded source: ' + row['provenance'],
                '   Ownership: ' + row['ownership_evidence'],
            ])
            if row['historical_plan_reference']:
                lines.append('   Historical Plan reference (not freshly verified): '
                             + row['historical_plan_reference'])
            if row['last_active_before_uninstall']:
                lines.append('   Last active version before uninstall')
        lines.append('')
    if report.get('recovery_effect'):
        lines.append('Recovery effect: ' + report['recovery_effect'])
    lines.append('Important: ' + report['safety_notice'])
    if report.get('manual_ownership_attestation_required'):
        lines.append('WARNING: Original project ownership is UNKNOWN; manual attestation required.')
    if report.get('selected'):
        selected = report['selected']
        lines.extend([
            '',
            'Selected Backup: ' + selected['backup_id'],
            'Read-only state binding: ' + selected['state_binding_id'],
            'Next step requires exact interactive TTY approval; this review did NOT approve it:',
            selected['recovery_command'],
            ('First set in PowerShell: $env:GASL_SELECTED_PROJECT = "C:\\path\\to\\project"'
             if report.get('ownership_store') == 'native_host_scoped' else
             'First set: export GASL_SELECTED_PROJECT=/absolute/path/to/your/existing/git/project'),
        ])
    elif report.get('available_recovery'):
        lines.extend([
            '',
            'Select a Backup for a read-only, binding-bound preview:',
            report['review_command_template'],
            ('First set in PowerShell: $env:GASL_SELECTED_PROJECT = "C:\\path\\to\\project"'
             if report.get('ownership_store') == 'native_host_scoped' else
             'First set: export GASL_SELECTED_PROJECT=/absolute/path/to/your/existing/git/project'),
        ])
    elif report.get('next_steps'):
        lines.extend([
            '',
            'Possible recovery action (inspect journal first; may refuse unsafe state):',
            *report['next_steps'],
        ])
    lines.extend(['', 'No Skill was installed, executed, modified or approved by this review.'])
    return '\n'.join(lines)
