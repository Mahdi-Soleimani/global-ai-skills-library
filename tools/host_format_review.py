#!/usr/bin/env python3
"""Read-only, evidence-bound Agent Skill format check for a verified private ZIP.

This is NOT a Host discovery test, installation approval, or execution.
It never extracts files or accesses an Agent's home/configuration.
"""
import json
import re
import zipfile
from pathlib import Path

from host_adapters import HOST_LAYOUTS, SCOPES
from install_bundle import verify_private_bundle
from install_lifecycle import plan_install
from queue_ingest import git_blob, no_symlink
from skill_search import ROOT

HOSTS = ('codex', 'cursor', 'claude-code')
MAX_SKILL_MD = 256 * 1024
NAME = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?\Z')


def _simple_frontmatter(data):
    """Only inspect the simple key: scalar subset; never interpret Skill body."""
    problems = []
    try:
        value = data.decode('utf-8')
    except UnicodeError:
        return {}, ['invalid_utf8']
    lines = value.splitlines()
    if not lines or lines[0] != '---':
        return {}, ['missing_frontmatter_opening']
    try:
        end = lines.index('---', 1)
    except ValueError:
        return {}, ['missing_frontmatter_closing']
    if end < 2 or end > 128:
        return {}, ['frontmatter_bounds_invalid']
    values = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if line[:1].isspace():
            # Indented and nested YAML is not interpreted by this lightweight review.
            problems.append('complex_yaml_requires_manual_review')
            continue
        match = re.fullmatch(r'([A-Za-z][A-Za-z0-9_-]*):\s*(.*)', line)
        if not match:
            problems.append('non_simple_frontmatter_line')
            continue
        key, raw = match.groups()
        if key in values:
            problems.append('duplicate_frontmatter_key')
        values[key] = raw.strip()
    for field in ('name', 'description'):
        if field not in values or not values[field]:
            problems.append('missing_'+field)
        elif values[field] in ('|', '>', '|-', '>-'):
            problems.append('multiline_'+field+'_requires_review')
    if 'name' in values:
        raw = values['name']
        if len(raw) >= 2 and raw[0] in ('"', "'") and raw[-1] == raw[0]:
            raw = raw[1:-1]
        if not NAME.fullmatch(raw):
            problems.append('nonportable_name')
            values['name'] = None  # Do not echo arbitrary invalid names.
        else:
            values['name'] = raw
    return values, sorted(set(problems))


def review_host_format(plan_id, host, scope='user', *, root=ROOT, lookup=None):
    """Inspect original SKILL.md from an exact verified ZIP, without extraction."""
    if host not in HOSTS or scope not in SCOPES:
        raise ValueError('Select a supported filesystem Skill Host and scope')
    root = Path(root).resolve()
    evidence = verify_private_bundle(plan_id, root=root)
    storage = no_symlink(root, root/'private'/'install-bundles')
    sidecar = no_symlink(root, storage/(plan_id+'.json'))
    meta = json.loads(sidecar.read_text(encoding='utf-8'))
    source_id, bundle_host, bundle_scope = (
        meta['source_record_id'], meta['agent'], meta['scope'])
    current = plan_install(source_id, bundle_host, bundle_scope, root=root, lookup=lookup)
    if (current['plan_id'] != plan_id
            or current['pinned_version']['commit_sha'] != meta['source_commit_sha']
            or current['pinned_version']['skill_md_blob_sha'] != meta['pinned_skill_md_blob_sha']
            or current['local_package']['integrity_ok'] is not True
            or current['local_package']['actionable_findings'] != 0):
        raise ValueError('Pinned catalog, local package, or static review no longer matches private bundle')

    candidates = [item['archive_path'] for item in meta['entries']
                  if item['archive_path'].count('/') == 1
                  and item['archive_path'].endswith('/SKILL.md')]
    if len(candidates) != 1:
        raise ValueError('Bundle must have exactly one root SKILL.md')
    entry = candidates[0]
    with zipfile.ZipFile(no_symlink(root, storage/(plan_id+'.zip'))) as archive:
        info = archive.getinfo(entry)
        if info.file_size > MAX_SKILL_MD:
            raise ValueError('SKILL.md exceeds bounded review size')
        data = archive.read(info)
    if git_blob(data) != meta['pinned_skill_md_blob_sha']:
        raise ValueError('Pinned source Git Blob mismatch')
    fields, problems = _simple_frontmatter(data)
    bundle_slug = entry.split('/')[0]
    if fields.get('name') and fields['name'] != bundle_slug:
        problems.append('frontmatter_name_differs_from_bundle_directory')
    # A compatibility field often describes runtime requirements, NOT supported Hosts.
    if fields.get('compatibility'):
        problems.append('upstream_compatibility_is_not_host_discovery_evidence')

    return {
        'schema_version': 'gasl-static-host-format-review-v1',
        'status': 'read_only_format_review_completed',
        'format_status': ('simple_frontmatter_shape_detected'
                          if not [x for x in problems if x != 'upstream_compatibility_is_not_host_discovery_evidence']
                          else 'manual_format_review_required'),
        'host': host, 'scope': scope,
        'documented_skill_directory': HOST_LAYOUTS[host][scope],
        'source_record_id': source_id,
        'source_git_blob_verified': True,
        'private_bundle_sha256_verified': evidence['archive_sha256'],
        'skill_name': fields.get('name'),
        'frontmatter_description_present': bool(fields.get('description')),
        'checks': sorted(set(problems)),
        'host_discovery_verified_by_this_check': False,
        'cross_host_compatibility_proven': False,
        'installation_allowed': False,
        'real_host_files_modified': False,
        'third_party_skill_executed': False,
        'model_turn_started': False,
    }
