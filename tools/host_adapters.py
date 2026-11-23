#!/usr/bin/env python3
"""Read-only host Skill layout declarations and *inert* disposable fixture tests.

Never resolves a real user's home, changes Agent config, runs third-party Skill
content, or installs anything. Claude Desktop is account-UI ZIP upload, not
Claude Code's local .claude/skills directory.
"""
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from transaction_file_lock import is_redirected, require_windows_filename_safety

HOST_LAYOUTS = {
    'codex': {
        'kind': 'filesystem_skill_directory',
        'project': '.agents/skills', 'user': '.agents/skills',
        'docs': 'https://developers.openai.com/api/reference/cli',
        'verified_with_real_host': True,
        'verified_capabilities': ['project_skill_discovery', 'user_skill_discovery',
                                  'skills_list', 'isolated_fixture_rollback'],
        'verification_scope': 'disposable_home_only',
        'verification_report': 'docs/reports/PHASE-31-CODEX-ISOLATED-USER-SCOPE-2026-11-22.md',
    },
    'cursor': {
        'kind': 'filesystem_skill_directory',
        'project': '.cursor/skills', 'user': '.cursor/skills',
        'docs': 'https://cursor.com/help/customization/skills',
        'verified_with_real_host': False,
        'verified_capabilities': [],
        'verification_scope': None,
        'verification_report': None,
    },
    'claude-code': {
        'kind': 'filesystem_skill_directory',
        'project': '.claude/skills', 'user': '.claude/skills',
        'docs': 'https://code.claude.com/docs/en/skills',
        'verified_with_real_host': False,
        'verified_capabilities': [],
        'verification_scope': None,
        'verification_report': None,
    },
    'claude-desktop': {
        'kind': 'manual_account_zip_upload',
        'project': None, 'user': None,
        'docs': 'https://support.claude.com/en/articles/12512180-use-skills-in-claude',
        'verified_with_real_host': False,
        'verified_capabilities': [],
        'verification_scope': None,
        'verification_report': None,
    },
    'generic-mcp': {
        'kind': 'no_standard_skill_directory',
        'project': None, 'user': None,
        'docs': None,
        'verified_with_real_host': False,
        'verified_capabilities': [],
        'verification_scope': None,
        'verification_report': None,
    },
}
SCOPES = ('project', 'user')
SLUG = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$')
MARKER = '.gasl-inert-host-fixture-v1'
FIXTURE_PREFIX = 'gasl-host-fixture-'
SKILL_V1 = b'---\nname: fixture-skill\ndescription: GASL inert adapter test only\n---\n# Inert Skill v1\n'
SKILL_V2 = b'---\nname: fixture-skill\ndescription: GASL inert adapter test only\n---\n# Inert Skill v2\n'


def list_host_adapters():
    return {'schema_version': 'gasl-host-adapters-v1',
            'status': 'codex_isolated_discovery_verified_other_hosts_unverified',
            'agents': HOST_LAYOUTS,
            # Separate transactional installers exist, but live Host discovery
            # remains verified only for isolated Codex fixtures.
            'real_installation_available': True,
            'real_installation_supported_hosts': ['codex', 'cursor', 'claude-code'],
            'real_installation_scope': 'project_and_current_os_user_profile',
            'real_user_profile_requires_os_home_match': True,
            'user_profile_writes_require_local_tty': True,

            'real_installation_platform': 'POSIX_project_and_user_Windows_project_only',
            'real_installation_platform_scopes': {
                'POSIX': ['project', 'user'],
                'Windows': ['project'],
            },
            # Windows User Profile remains disabled until its native SID/ACL
            # and disposable transaction CI is green.
            'windows_native_project_fixture_verified': True,
            'windows_native_user_profile_security_verified': False,
            'windows_live_host_discovery_verified': False,
            'windows_user_profile_installer_enabled': False,
            'real_installation_requires_local_tty': True,
            'cursor_and_claude_live_host_discovery_verified': False,
            'real_host_probe_performed': True,
            'real_host_probe_scope': 'disposable_home_only',
            'third_party_skill_executed': False}


def _checked_fixture(root):
    """Fixture file operations are allowed ONLY under a newly created temp root."""
    root = Path(root).absolute()
    temp = Path(tempfile.gettempdir()).resolve()
    if (is_redirected(root) or not root.name.startswith(FIXTURE_PREFIX)
            or root.parent.resolve() != temp or not root.is_dir()):
        raise ValueError('Only a dedicated temporary GASL host fixture root is allowed')
    if os.name == 'nt':
        from windows_user_profile import assert_no_reparse_components
        assert_no_reparse_components(root)
    marker = root / MARKER
    if (is_redirected(marker) or not marker.is_file()
            or marker.read_bytes() != b'INERT_HOST_FIXTURE_ONLY\n'):
        raise ValueError('Host fixture marker missing, altered or symlinked')
    return root


def _path_within_fixture(root, relative):
    if (not isinstance(relative, str) or not relative or '\\' in relative
            or Path(relative).is_absolute() or any(x in ('..', '.') for x in relative.split('/'))):
        raise ValueError('Invalid or escaping fixture-relative path')
    require_windows_filename_safety(relative)
    target = root / relative
    current = root
    for part in target.relative_to(root).parts:
        current = current / part
        if is_redirected(current):
            raise ValueError('Symlink or junction in fixture target path')
    if os.name == 'nt':
        from windows_user_profile import assert_no_reparse_components
        assert_no_reparse_components(target)
    return target


def _target_for_fixture(root, agent, scope, slug):
    if agent not in HOST_LAYOUTS:
        raise ValueError('Unknown host adapter')
    if scope not in SCOPES:
        raise ValueError('Unknown host scope')
    if not SLUG.fullmatch(str(slug)):
        raise ValueError('Unsafe Skill slug')
    spec = HOST_LAYOUTS[agent]
    if spec['kind'] != 'filesystem_skill_directory':
        return None
    relative = ('workspace/' if scope == 'project' else 'home/') + spec[scope] + '/' + slug
    return _path_within_fixture(root, relative)


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _test_at_fixture(root, agent, scope, scenario):
    root = _checked_fixture(root)
    target = _target_for_fixture(root, agent, scope, 'fixture-skill')
    if target is None:
        return {
            'schema_version': 'gasl-host-rehearsal-v1', 'agent': agent, 'scope': scope,
            'scenario': scenario, 'status': 'no_filesystem_adapter',
            'supported_install_channel': HOST_LAYOUTS[agent]['kind'],
            'real_host_files_modified': False, 'real_skill_installed': False,
            'third_party_code_executed': False, 'fixture_rollback_performed': False,
        }
    if scenario not in ('fresh', 'upgrade', 'conflict', 'symlink'):
        raise ValueError('Unknown inert fixture scenario')
    backup = _path_within_fixture(root, 'rollback-backup/fixture-skill')
    target.parent.mkdir(parents=True, exist_ok=True)
    if scenario in ('upgrade', 'conflict'):
        target.mkdir()
        (target / 'SKILL.md').write_bytes(SKILL_V1)
        (target / 'user-note.txt').write_text('USER_MODIFICATION_SHOULD_SURVIVE\n', encoding='utf-8')
    elif scenario == 'symlink':
        outside = _path_within_fixture(root, 'outside-sentinel')
        outside.write_text('NEVER_TOUCH\n', encoding='utf-8')
        target.symlink_to(outside)

    def check_no_symlink():
        _path_within_fixture(root, target.relative_to(root).as_posix())

    original = _hash(target / 'SKILL.md') if scenario in ('upgrade', 'conflict') else None
    if scenario == 'conflict':
        # Collision detected, no overwrite without planned backup/approval.
        return {
            'schema_version': 'gasl-host-rehearsal-v1', 'agent': agent, 'scope': scope,
            'scenario': scenario, 'status': 'existing_target_requires_explicit_backup',
            'existing_skill_preserved': (target / 'SKILL.md').read_bytes() == SKILL_V1,
            'user_note_preserved': (target / 'user-note.txt').exists(),
            'real_host_files_modified': False, 'real_skill_installed': False,
            'third_party_code_executed': False, 'fixture_rollback_performed': False,
        }
    if scenario == 'symlink':
        try:
            check_no_symlink()
        except ValueError:
            outside = _path_within_fixture(root, 'outside-sentinel')
            return {
                'schema_version': 'gasl-host-rehearsal-v1', 'agent': agent, 'scope': scope,
                'scenario': scenario, 'status': 'blocked_symlink_target',
                'external_fixture_sentinel_preserved': outside.read_text() == 'NEVER_TOUCH\n',
                'real_host_files_modified': False, 'real_skill_installed': False,
                'third_party_code_executed': False, 'fixture_rollback_performed': False,
            }
        raise AssertionError('Symlink guard unexpectedly allowed target')

    # Only deterministic, GASL-authored fixture bytes enter this ephemeral root.
    check_no_symlink()
    version = SKILL_V2 if scenario == 'upgrade' else SKILL_V1
    if target.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        target.rename(backup)  # Atomic on same fixture filesystem.
    try:
        target.mkdir()
        (target / 'SKILL.md').write_bytes(version)
        expected_hash = hashlib.sha256(version).hexdigest()
        if _hash(target / 'SKILL.md') != expected_hash:
            raise ValueError('Inert fixture staged-content verification failed')
    finally:
        if target.exists():
            shutil.rmtree(target)
        if backup.exists():
            backup.rename(target)
    original_restored = ((target / 'SKILL.md').is_file()
                         and _hash(target / 'SKILL.md') == original) if original else not target.exists()
    note_restored = ((target / 'user-note.txt').read_text() == 'USER_MODIFICATION_SHOULD_SURVIVE\n'
                     if scenario == 'upgrade' else True)
    status = 'fixture_rollback_verified' if original_restored and note_restored else 'fixture_rollback_failed'
    return {
        'schema_version': 'gasl-host-rehearsal-v1', 'agent': agent, 'scope': scope,
        'scenario': scenario, 'status': status,
        'fixture_target_relative': target.relative_to(root).as_posix(),
        'staged_content_sha256': hashlib.sha256(version).hexdigest(),
        'original_version_restored': original_restored,
        'user_note_preserved': note_restored,
        'real_host_files_modified': False, 'real_skill_installed': False,
        'third_party_code_executed': False, 'fixture_rollback_performed': True,
    }


def rehearse_host_fixture(agent, scope='project', scenario='upgrade'):
    """Create and discard an isolated temp fixture. No caller-supplied write path."""
    if agent not in HOST_LAYOUTS or scope not in SCOPES:
        raise ValueError('Unknown Agent/scope')
    if scenario not in ('fresh', 'upgrade', 'conflict', 'symlink'):
        raise ValueError('Unknown fixture scenario')
    with tempfile.TemporaryDirectory(prefix=FIXTURE_PREFIX) as scratch:
        root = Path(scratch)
        (root / MARKER).write_bytes(b'INERT_HOST_FIXTURE_ONLY\n')
        return _test_at_fixture(root, agent, scope, scenario)
