#!/usr/bin/env python3
"""Read-only capability inventory, not a claim that a real Agent loaded a Skill.

Do not launch Host binaries, read their settings or expose executable paths.
"""
import shutil
from host_adapters import HOST_LAYOUTS

CLI_NAMES = {'codex': 'codex', 'cursor': 'cursor', 'claude-code': 'claude'}


def probe_hosts(which=None):
    if which is None:
        which = shutil.which
    entries = {}
    for agent, adapter in HOST_LAYOUTS.items():
        binary = CLI_NAMES.get(agent)
        available = bool(which(binary)) if binary else False
        entries[agent] = {
            'filesystem_adapter_documented': adapter['kind'] == 'filesystem_skill_directory',
            'cli_name': binary,
            'cli_visible_on_path': available,
            'host_launched': False,
            'host_skill_discovery_verified': False,
            'integration_status': ('binary_detected_not_executed' if available else
                                   'cli_not_available_for_probe' if binary else
                                   'not_an_automated_local_cli_adapter'),
        }
    return {
        'schema_version': 'gasl-read-only-host-probe-v1',
        'read_only': True,
        'real_host_files_modified': False,
        'host_process_executed': False,
        'skill_discovery_verified': False,
        'hosts': entries,
    }
