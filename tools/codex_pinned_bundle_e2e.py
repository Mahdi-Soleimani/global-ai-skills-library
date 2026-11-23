#!/usr/bin/env python3
"""Phase 39: pinned full-ZIP Codex discovery/rollback in a DISPOSABLE profile.

Never writes to the real Codex profile, invokes a model, starts a Skill,
executes a package script, or installs dependencies. This is NOT a real-user
installer, even if the selected ZIP contains genuine third-party content.
"""
import argparse
import json
import re
from pathlib import Path

from codex_third_party_discovery import _query_codex
from fixture_bundle_install import _inventory, _read_bundle
from fixture_transaction_v2 import (
    enact_fixture_transaction, preview_fixture_consent, recover_fixture_transaction,
)
from host_adapters import _target_for_fixture
from host_format_review import review_host_format
from host_target_preflight import inspect_selected_target, verify_target_unchanged
from host_transaction_fixture import _new_root
from skill_search import ROOT

SCHEMA = 'gasl-codex-pinned-bundle-fixture-e2e-v1'
ACKNOWLEDGEMENT = 'GASL_DISPOSABLE_CODEX_BUNDLE_ONLY'
HEX64 = re.compile(r'^[0-9a-f]{64}$')


def verify_pinned_bundle_lifecycle(codex_binary, plan_id, acknowledgement, *,
                                   bundle_root=ROOT, query=_query_codex, lookup=None):
    """Use exact, previously reviewed source bytes in a marked temporary HOME."""
    result = {
        'schema_version': SCHEMA,
        'host': 'codex',
        'scope': 'user',
        'plan_id': plan_id,
        'status': 'blocked',
        'reason_code': 'not_started',
        'pinned_package_and_format_checked': False,
        'target_preflight_state_bound': False,
        'absent_before_install': False,
        'full_pinned_zip_temporarily_staged_and_activated': False,
        'exact_skill_discovered_and_enabled': False,
        'fixture_rollback_verified': False,
        'absent_after_rollback': False,
        'temporary_profile_deleted': False,
        'file_count': 0,
        'real_user_authorization_collected': False,
        'real_home_or_codex_profile_accessed': False,
        'real_host_files_modified': False,
        'third_party_skill_executed': False,
        'skill_commands_or_dependencies_executed': False,
        'model_turn_started': False,
        'authentication_performed': False,
        'production_installation_enabled': False,
    }
    binary = Path(codex_binary)
    if not binary.is_absolute() or binary.is_symlink() or not binary.is_file():
        result['reason_code'] = 'absolute_regular_codex_executable_required'
        return result
    if not HEX64.fullmatch(str(plan_id)) or acknowledgement != ACKNOWLEDGEMENT:
        result['reason_code'] = 'exact_disposable_bundle_acknowledgement_required'
        return result

    # No fixture or Host process exists until the source, bundle and content
    # pass the current catalog identity, static-scan and format gates.
    try:
        reviewed = review_host_format(plan_id, 'codex', 'user', root=bundle_root, lookup=lookup)
        if (reviewed['format_status'] != 'simple_frontmatter_shape_detected'
                or not reviewed['skill_name']):
            result['reason_code'] = 'skill_format_requires_manual_review'
            return result
        slug, entries = _read_bundle(bundle_root, plan_id, 'codex', 'user')
        if slug != reviewed['skill_name']:
            result['reason_code'] = 'pinned_skill_name_mismatch'
            return result
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        result['reason_code'] = 'pinned_bundle_verification_failed'
        return result
    result['pinned_package_and_format_checked'] = True
    expected_inventory = sorted(
        [{'path': rel, 'sha256': sha} for _, rel, _, sha in entries],
        key=lambda item: item['path'])
    result['file_count'] = len(expected_inventory)

    directory, fixture = _new_root()
    try:
        for part in ('workspace', 'home', 'codex-home', 'cache', 'xdg-config', 'tmp'):
            (fixture / part).mkdir()
        project = fixture / 'workspace'
        target = _target_for_fixture(fixture, 'codex', 'user', slug)
        skill_file = target / 'SKILL.md'
        preflight = inspect_selected_target(plan_id, 'codex', 'user', fixture / 'home',
                                            bundle_root=bundle_root)
        if (preflight['prior_target_state'] != 'target_absent'
                or preflight['relative_target'] != '.agents/skills/' + slug):
            result['reason_code'] = 'disposable_target_preflight_not_empty'
        else:
            bound = verify_target_unchanged(plan_id, 'codex', 'user', fixture / 'home',
                                            preflight['state_binding_id'],
                                            bundle_root=bundle_root)
            result['target_preflight_state_bound'] = bool(
                bound['state_binding_matches_previous_preflight'])
            before = query(binary, fixture, project, slug, skill_file)
            if before:
                result['reason_code'] = 'skill_preexists_in_disposable_codex'
            else:
                result['absent_before_install'] = True
                preview = preview_fixture_consent(fixture, bundle_root, plan_id,
                                                  'codex', 'user', 'install')
                if preview['state_binding_id'] != preflight['state_binding_id']:
                    raise ValueError('Fixture target changed between preflight and transaction')
                applied = enact_fixture_transaction(
                    fixture, bundle_root, plan_id, 'codex', 'user', 'install',
                    preview['approval_challenge'], checkpoint='activated')
                if (applied['status'] != 'fixture_bundle_activated'
                        or applied['file_count'] != len(expected_inventory)
                        or _inventory(target) != expected_inventory):
                    raise ValueError('Full pinned ZIP materialization failed')
                result['full_pinned_zip_temporarily_staged_and_activated'] = True
                matches = query(binary, fixture, project, slug, skill_file)
                exact = (
                    len(matches) == 1 and
                    isinstance(matches[0].get('path'), str) and
                    Path(matches[0]['path']).resolve() == skill_file.resolve() and
                    matches[0].get('enabled') is True
                )
                if not exact:
                    result['reason_code'] = 'codex_did_not_discover_exact_enabled_skill'
                else:
                    result['exact_skill_discovered_and_enabled'] = True
                    rollback = recover_fixture_transaction(fixture)
                    result['fixture_rollback_verified'] = (
                        rollback['previous_files_restored'] is True
                        and not target.exists()
                    )
                    if not result['fixture_rollback_verified']:
                        result['reason_code'] = 'fixture_rollback_not_verified'
                    else:
                        result['absent_after_rollback'] = not query(
                            binary, fixture, project, slug, skill_file)
                        if result['absent_after_rollback']:
                            result['status'] = 'real_codex_pinned_full_bundle_discovery_and_rollback_verified'
                            result['reason_code'] = 'exact_full_zip_lifecycle_verified_in_disposable_profile'
                        else:
                            result['reason_code'] = 'codex_still_discovers_removed_skill'
    except (OSError, ValueError, TimeoutError, BrokenPipeError, TypeError):
        result['reason_code'] = 'temporary_transaction_or_codex_protocol_failed'
    finally:
        # On any discovery/protocol failure, try the same locked rollback
        # before deleting the whole disposable fixture. Never attempt this
        # against a user-selected or real Host directory.
        journal = fixture / '.gasl-bundle-fixture-transaction.json'
        if journal.exists():
            try:
                recover_fixture_transaction(fixture)
                result['fixture_rollback_verified'] = not target.exists()
            except (OSError, ValueError):
                result['status'] = 'blocked'
                result['reason_code'] = 'fixture_recovery_refused_or_failed'
        directory.cleanup()
        result['temporary_profile_deleted'] = not fixture.exists()
        if result['status'].startswith('real_codex_') and not result['temporary_profile_deleted']:
            result['status'] = 'blocked'
            result['reason_code'] = 'temporary_profile_cleanup_failed'
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Verify exact full ZIP install/list/rollback in disposable Codex HOME ONLY')
    parser.add_argument('--codex-bin', required=True, type=Path)
    parser.add_argument('--plan-id', required=True)
    parser.add_argument('--acknowledge-fixture-only', required=True,
                        help='Must be GASL_DISPOSABLE_CODEX_BUNDLE_ONLY; never authorizes real installs')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = verify_pinned_bundle_lifecycle(
        args.codex_bin, args.plan_id, args.acknowledge_fixture_only)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    print(payload, end='')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding='utf-8')
    return 0 if report['status'] == (
        'real_codex_pinned_full_bundle_discovery_and_rollback_verified') else 1


if __name__ == '__main__':
    raise SystemExit(main())
