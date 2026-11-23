#!/usr/bin/env python3
"""Read-only, path-bound Host Skill target assessment before a *future* install.

No writes, backups, user consent collection, Skill execution, Host launch or
production installation. The caller must explicitly select the existing root.
No absolute user/project paths or existing Skill file names are emitted.
"""
import hashlib
import json
import os
import re
from pathlib import Path

from fixture_bundle_install import _inventory, _read_bundle
from transaction_file_lock import is_redirected
from host_adapters import HOST_LAYOUTS, SLUG

SCHEMA = 'gasl-host-target-preflight-v1'
HEX64 = re.compile(r'^[0-9a-f]{64}$')


def _canonical_bytes(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':')).encode('utf-8')


def _explicit_root(selected_root):
    """Canonicalize a caller-chosen existing root, never discover HOME itself."""
    supplied = Path(selected_root)
    if not supplied.is_absolute() or is_redirected(supplied) or not supplied.is_dir():
        raise ValueError('An existing absolute, nonsymlink root must be explicitly supplied')
    return supplied.resolve(strict=True)


def _target_path(root, agent, scope, slug):
    if agent not in ('codex', 'cursor', 'claude-code'):
        raise ValueError('This preflight supports only local filesystem Host adapters')
    if scope not in ('project', 'user') or not SLUG.fullmatch(str(slug)):
        raise ValueError('Invalid Host scope or Skill folder name')
    base_relative = HOST_LAYOUTS[agent][scope]
    base = Path(base_relative)
    if base.is_absolute() or any(part in ('.', '..') for part in base.parts):
        raise ValueError('Unsafe documented Host directory')
    current = root
    for part in (*base.parts, slug):
        current = current / part
        if is_redirected(current):
            raise ValueError('Symlink in selected Host target path')
        if current.exists() and not current.is_dir():
            raise ValueError('Non-directory in selected Host target path')
    # A same-name Skill with differing case must not be silently treated as a
    # distinct installable target (even on case-sensitive Linux filesystems).
    parent = current.parent
    if parent.is_dir():
        for sibling in parent.iterdir():
            if sibling.name.casefold() == slug.casefold() and sibling.name != slug:
                raise ValueError('Case-insensitive Skill directory collision')
    return current, (base / slug).as_posix()


def inspect_selected_target(plan_id, agent, scope, selected_root, *, bundle_root):
    """One bounded preflight; no caller path contents returned, no filesystem mutation."""
    if not HEX64.fullmatch(str(plan_id)):
        raise ValueError('Exact pinned Plan ID is required')
    root = _explicit_root(selected_root)
    slug, _ = _read_bundle(bundle_root, plan_id, agent, scope)
    target, relative = _target_path(root, agent, scope, slug)
    present = target.exists()
    old_files = _inventory(target) if present else []
    inventory_digest = hashlib.sha256(_canonical_bytes(old_files)).hexdigest()
    source_base = Path(bundle_root).resolve() / 'private' / 'install-bundles'
    sidecar = source_base / (plan_id + '.json')
    meta = json.loads(sidecar.read_text(encoding='utf-8'))
    source_digest = meta['archive_sha256']
    if not HEX64.fullmatch(str(source_digest)):
        raise ValueError('Invalid private ZIP identity')
    path_binding = hashlib.sha256(os.fsencode(str(target))).hexdigest()
    selected_binding = {
        'schema_version': SCHEMA,
        'plan_id': plan_id,
        'archive_sha256': source_digest,
        'host': agent,
        'scope': scope,
        'selected_target_sha256': path_binding,
        'relative_skill_target': relative,
        'prior_target_state': 'existing_skill_collision' if present else 'target_absent',
        'existing_file_inventory_sha256': inventory_digest,
    }
    state_binding = hashlib.sha256(_canonical_bytes(selected_binding)).hexdigest()
    warnings = []
    if present:
        warnings.append('existing_target_must_not_be_replaced_without_separate_specific_approval')
    if meta.get('license_review_required', True):
        warnings.append('source_license_requires_review')
    if not meta.get('non_main_file_upstream_blob_evidence_complete', False):
        warnings.append('legacy_non_main_git_blob_evidence_incomplete')
    warnings.extend(('live_host_target_compatibility_not_validated',
                     'real_user_install_approval_not_collected',
                     'third_party_skill_execution_not_approved'))
    return {
        'schema_version': SCHEMA,
        'status': 'read_only_target_preflight_completed',
        'plan_id': plan_id,
        'host': agent,
        'scope': scope,
        'relative_target': relative,
        'selected_target_sha256': path_binding,
        'state_binding_id': state_binding,
        'bundle_sha256': source_digest,
        'prior_target_state': selected_binding['prior_target_state'],
        'existing_file_count': len(old_files),
        'existing_file_inventory_sha256': inventory_digest,
        'warnings': sorted(set(warnings)),
        'root_provided_explicitly': True,
        'root_actual_role_verified': False,
        'selected_directory_access_checked': True,
        'existing_files_read_only_for_hashing': bool(old_files),
        'existing_file_contents_included_in_output': False,
        'no_user_paths_or_file_names_in_output': True,
        'state_binding_is_authorization': False,
        'installation_allowed': False,
        'actual_install_enabled': False,
        'real_host_files_modified': False,
        'third_party_skill_executed': False,
    }


def verify_target_unchanged(plan_id, agent, scope, selected_root, expected_binding_id, *, bundle_root):
    if not HEX64.fullmatch(str(expected_binding_id)):
        raise ValueError('Exact prior state binding ID required')
    current = inspect_selected_target(plan_id, agent, scope, selected_root,
                                      bundle_root=bundle_root)
    if current['state_binding_id'] != expected_binding_id:
        raise ValueError('Selected Host target or ZIP has changed since the previous preflight')
    return {**current, 'state_binding_matches_previous_preflight': True}
