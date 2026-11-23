#!/usr/bin/env python3
"""GASL Phase-1 CLI. Python 3.9+, standard library only. No downloaded code is executed."""
import argparse
import csv
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

CONFIG = ROOT / "config" / "source-repositories.json"
REGISTRY = ROOT / "registry"
API = "https://api.github.com"
UA = "GASL-Collector/0.1 (local research library)"


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load(path, default=None):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


def get_json(url):
    cmd = ["curl", "--fail", "--silent", "--show-error", "--location",
           "--retry", "3", "--retry-delay", "1", "--max-time", "45",
           "--user-agent", UA,
           "-H", "Accept: application/vnd.github+json",
           "-H", "X-GitHub-Api-Version: 2022-11-28"]
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        cmd.extend(["-H", "Authorization: Bearer " + token])
    result = subprocess.run(cmd + [url], capture_output=True, check=False)
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError("GitHub request failed: " + (detail or str(result.returncode)))
    return json.loads(result.stdout.decode("utf-8"))


def all_repos(cfg):
    by_name = {}
    for report_id, report in cfg["reports"].items():
        for repo in report["explicit_github_repositories"]:
            key = repo.lower()
            if key not in by_name:
                by_name[key] = {"repo_full_name": repo, "source_reports": []}
            if report_id not in by_name[key]["source_reports"]:
                by_name[key]["source_reports"].append(report_id)
    return sorted(by_name.values(), key=lambda x: x["repo_full_name"].lower())


def cmd_summary(args):
    cfg = load(CONFIG, {})
    print("GASL source inventory")
    for report_id, report in cfg.get("reports", {}).items():
        count = report.get("record_count_claimed", report.get("reported_unique_skills"))
        print("{} [{}]: record_count_claimed={}, sample_rows={}, explicit GitHub repos={}".format(
            report_id, report.get("dataset_role", "unspecified"), count,
            report.get("embedded_csv_sample_rows", "not embedded"),
            len(report.get("explicit_github_repositories", []))))
    repos = all_repos(cfg)
    overlap = sum(1 for r in repos if len(r["source_reports"]) > 1)
    verified = load(REGISTRY / "source-verification.json", {"repositories": {}}).get("repositories", {})
    canonical = {str(x.get("canonical_repo_name", x.get("repo_full_name", k))).lower()
                 for k, x in verified.items() if x.get("status") == "verified"}
    print("Repository mentions: {}".format(sum(len(x["explicit_github_repositories"]) for x in cfg["reports"].values())))
    print("Distinct source repository references: {}".format(len(repos)))
    print("Cross-referenced repository references: {}".format(overlap))
    print("Live-verified source references: {}".format(sum(x.get("status") == "verified" for x in verified.values())))
    print("Canonical GitHub repositories: {}".format(len(canonical)))
    print("No skills downloaded or installed by summary.")


def cmd_bootstrap(args):
    cfg = load(CONFIG, {})
    for report_id, report in cfg["reports"].items():
        records = []
        for i, repo in enumerate(report["explicit_github_repositories"], 1):
            records.append({
                "source_id": "{}-SRC-{:04d}".format(report_id, i),
                "report_id": report_id,
                "repo_full_name": repo,
                "repository_url": "https://github.com/" + repo,
                "verification_status": "not_yet_verified_live"
            })
        manifest = {
            "manifest_version": "0.2.0",
            "report_id": report_id,
            "dataset_role": report.get("dataset_role"),
            "language": report.get("language"),
            "source_file": report["source_file"],
            "source_sha256": report["source_sha256"],
            "source_size_bytes": report.get("source_size_bytes"),
            "record_count_claimed": report.get("record_count_claimed", report.get("reported_unique_skills")),
            "record_count_semantics": report.get("record_count_semantics"),
            "database_artifacts_available": report.get("database_artifacts_available"),
            "missing_artifacts": report.get("missing_artifacts", []),
            "reported_counts": {k: v for k, v in report.items() if k.startswith("reported_")},
            "embedded_skill_record_rows": report.get("embedded_csv_sample_rows"),
            "repositories": records,
            "note": "Explicit repository references extracted from this exact report only. This is not a replacement for its full skill-record database."
        }
        save(ROOT / "research" / report_id / "source-manifest.json", manifest)
        with (ROOT / "research" / report_id / "source-manifest.csv").open("w", encoding="utf-8-sig", newline="") as f:
            fields = ["source_id", "report_id", "repo_full_name", "repository_url", "verification_status"]
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(records)

    repos = all_repos(cfg)
    with (ROOT / "reconciliation" / "repository-overlap.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["repo_full_name", "source_reports", "primary_sources", "supplemental_sources", "note"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for item in repos:
            source_ids = item["source_reports"]
            primary = [x for x in source_ids if cfg["reports"][x].get("dataset_role") == "primary_independent_dataset"]
            supplemental = [x for x in source_ids if cfg["reports"][x].get("dataset_role") != "primary_independent_dataset"]
            w.writerow({
                "repo_full_name": item["repo_full_name"],
                "source_reports": ";".join(source_ids),
                "primary_sources": ";".join(primary),
                "supplemental_sources": ";".join(supplemental),
                "note": "Repository cross-reference only; no skill records merged, deduplicated, or removed."
            })
    print("Bootstrapped {} independent report manifests; {} repository names, {} cross-referenced.".format(
        len(cfg["reports"]), len(repos), sum(1 for r in repos if len(r["source_reports"]) > 1)))


def cmd_verify(args):
    cfg = load(CONFIG, {})
    targets = all_repos(cfg)
    if args.only:
        wanted = set(x.lower() for x in args.only)
        targets = [x for x in targets if x["repo_full_name"].lower() in wanted]
    if args.limit:
        targets = targets[:args.limit]
    state_path = REGISTRY / "source-verification.json"
    state = load(state_path, {"schema_version": "0.1.0", "repositories": {}})
    state.setdefault("repositories", {})
    for i, source in enumerate(targets, 1):
        name = source["repo_full_name"]
        key = name.lower()
        print("[{}/{}] {}".format(i, len(targets), name), flush=True)
        result = {
            "repo_full_name": name,
            "repository_url": "https://github.com/" + name,
            "source_reports": source["source_reports"],
            "checked_at": now()
        }
        try:
            repo = get_json(API + "/repos/" + name)
            lic = repo.get("license") or {}
            result.update({
                "status": "verified",
                "id": repo.get("id"),
                "owner_login": (repo.get("owner") or {}).get("login"),
                "default_branch": repo.get("default_branch"),
                "archived": repo.get("archived"),
                "private": repo.get("private"),
                "visibility": repo.get("visibility"),
                "size_kb": repo.get("size"),
                "stars": repo.get("stargazers_count"),
                "forks": repo.get("forks_count"),
                "updated_at": repo.get("updated_at"),
                "pushed_at": repo.get("pushed_at"),
                "license_spdx": lic.get("spdx_id"),
                "license_name": lic.get("name"),
                "html_url": repo.get("html_url")
            })
            if args.trees:
                branch = urllib.parse.quote(repo.get("default_branch", "main"), safe="")
                tree = get_json(API + "/repos/" + name + "/git/trees/" + branch + "?recursive=1")
                paths = [x.get("path") for x in tree.get("tree", [])
                         if x.get("type") == "blob" and x.get("path", "").split("/")[-1].lower() == "skill.md"]
                result["skill_paths"] = paths
                result["skill_file_count"] = len(paths)
                result["tree_truncated"] = tree.get("truncated", False)
                result["tree_status"] = "truncated" if tree.get("truncated") else "complete"
        except urllib.error.HTTPError as exc:
            result["status"] = "http_error"
            result["error"] = "HTTP {}".format(exc.code)
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)
        state["repositories"][key] = result
        state["updated_at"] = now()
        save(state_path, state)
        time.sleep(max(0.0, args.delay))

    fields = ["repo_full_name", "status", "owner_login", "default_branch", "archived",
              "visibility", "size_kb", "stars", "forks", "updated_at", "pushed_at",
              "license_spdx", "skill_file_count", "tree_status", "error", "source_reports"]
    with (REGISTRY / "source-verification.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for item in sorted(state["repositories"].values(), key=lambda x: x["repo_full_name"].lower()):
            row = dict(item)
            row["source_reports"] = ";".join(row.get("source_reports", []))
            w.writerow({k: row.get(k, "") for k in fields})
    print("Saved {} repository verification records.".format(len(state["repositories"])))


def cmd_domains(args):
    path = ROOT / "config" / "taxonomy.json"
    taxonomy = load(path, {"domains": []})
    domains = taxonomy.get("domains", [])
    if args.json:
        print(json.dumps(domains, ensure_ascii=False, indent=2))
        return
    for item in domains:
        print("{} — {} ({} keywords)".format(
            item["id"], item.get("label", item["id"]), len(item.get("keywords", []))))


def cmd_evaluate(args):
    from skill_evaluation import build_evaluations
    print(json.dumps(build_evaluations(ROOT), ensure_ascii=False, indent=2))


def cmd_index(args):
    from skill_search import build_index, search_skills
    result = build_index(ROOT)
    if args.check:
        result["smoke_query_count"] = len(search_skills("security audit", limit=3, root=ROOT))
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_benchmark(args):
    from search_benchmark import run_benchmark
    result = run_benchmark(ROOT, args.dataset, args.k, args.mrr_k)
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + ".tmp")
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(output)
    print(json.dumps({
        "benchmark_status": result["benchmark_status"],
        "query_count": result["query_count"],
        "judgment_count": result["judgment_count"],
        "k": result["k"],
        "mrr_k": result["mrr_k"],
        "averages": result["averages"],
        "language_averages": result["language_averages"],
        "output": str(args.output) if args.output else None,
    }, ensure_ascii=False, indent=2))


def cmd_search(args):
    from skill_search import search_skills
    results = search_skills(
        args.query, limit=args.limit, domain=args.domain,
        license_spdx=args.license_spdx, security_status=args.security_status,
        public_only=args.public_only, content_only=args.content_only, root=ROOT
    )
    if args.json:
        print(json.dumps({"query": args.query, "count": len(results), "results": results},
                         ensure_ascii=False, indent=2))
        return
    print("GASL search: {} result(s) for {!r}".format(len(results), args.query))
    for i, item in enumerate(results, 1):
        domains = ", ".join(x["id"] for x in item["inferred_domains"]) or "uncategorized"
        print("{:>2}. [{:5.1f} | coverage {:4.0f}%] {} — {}".format(i, item["relevance_score"],
              100 * item.get("query_coverage", 0.0), item["skill_name"], item["repository"]))
        print("    {} | license={} ({}) | security={} | domains={}".format(
            item["source_path"], item["license_spdx"] or "unknown",
            item["license_status"], item["security_status"], domains))
        if item.get("description"):
            print("    {}".format(item["description"][:240]))
        print("    {}".format(item["source_url"] or "source URL unavailable"))


def cmd_route(args):
    from skill_router import route_task
    result = route_task(
        args.task, top_k=args.top_k, domain=args.domain, license_spdx=args.license_spdx,
        agent=args.agent, strict_agent=args.strict_agent,
        public_only=args.public_only, content_only=args.content_only, root=ROOT
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print("GASL route: {} candidate(s) for {!r}".format(result["returned_count"], args.task))
    answerability = result["answerability"]
    print("Answerability: {} ({})".format(
        answerability["decision"].upper(), answerability["policy_status"]))
    print("Status: {} (experimental; not calibrated).".format(result['recommendation_status']))
    print("Reason: {}".format(answerability['reason_code']))
    if answerability['unmatched_technical_identifiers']:
        print("Unmatched technical identifiers: {}".format(", ".join(answerability['unmatched_technical_identifiers'])))
    print("Ranked candidates are not installation/security approvals.")
    print("Ranking: {}".format(result["ranking_method"]))
    for i, item in enumerate(result["results"], 1):
        print("{:>2}. [{:5.1f} | coverage {:4.0f}%] {} — {}".format(i, item["route_score"],
              100 * item.get("query_coverage", 0.0), item["skill_name"], item["repository"]))
        print("    decision={} | security={} | license={} ({}) | agent={}".format(
            item["decision"], item["security_status"], item["license_spdx"] or "unknown",
            item["license_assessment"], item["agent_compatibility_status"]))
        if item.get("description"):
            print("    {}".format(item["description"][:240]))
        print("    {}".format(item["source_url"] or "source URL unavailable"))
    print(result["note"])


def cmd_get(args):
    from gasl_service import skill_content
    print(json.dumps(skill_content(args.id, max_chars=args.max_chars, root=ROOT,
                                   fetch_remote=not args.offline), ensure_ascii=False, indent=2))


def cmd_host_probe(args):
    from host_probe import probe_hosts
    print(json.dumps(probe_hosts(), ensure_ascii=False, indent=2))


def cmd_host_transaction(args):
    from host_transaction_fixture import rehearse_interrupted_transaction
    result = rehearse_interrupted_transaction(args.agent, args.scope,
                                             upgrade=(args.kind == 'upgrade'),
                                             stop_after=args.interrupt_after)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_host_adapters(args):
    from host_adapters import list_host_adapters
    print(json.dumps(list_host_adapters(), ensure_ascii=False, indent=2))


def cmd_host_rehearsal(args):
    from host_adapters import rehearse_host_fixture
    print(json.dumps(rehearse_host_fixture(args.agent, args.scope, args.scenario),
                     ensure_ascii=False, indent=2))


def cmd_install_plan(args):
    from install_lifecycle import plan_install
    result = plan_install(args.id, args.agent, args.scope, root=ROOT)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_install_simulate(args):
    from install_lifecycle import plan_install, simulate
    plan = None
    if args.action == 'apply':
        if not args.id or not args.agent:
            raise SystemExit('Simulated apply requires --id and --agent')
        plan = plan_install(args.id, args.agent, args.scope, root=ROOT)
    result = simulate(args.action, args.plan_id,
                      acknowledgement=args.acknowledge_plan_id, root=ROOT, plan=plan)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_interactive_fixture_consent(args):
    import sys
    if args.acknowledge_fixture_only != 'GASL_DISPOSABLE_FIXTURE_ONLY':
        raise SystemExit('Exact disposable fixture acknowledgment is required')
    if not sys.stdin.isatty():
        raise SystemExit('Interactive TTY required; automated approval is never treated as human consent')
    from fixture_explicit_consent import request_fixture_consent, confirm_fixture_consent
    from fixture_transaction_v2 import (
        preview_fixture_consent, enact_fixture_transaction, recover_fixture_transaction)
    from fixture_bundle_install import _read_bundle
    from host_transaction_fixture import _new_root
    from host_adapters import _path_within_fixture, _target_for_fixture
    with _new_root()[0] as temporary:
        fixture = Path(temporary)
        _path_within_fixture(fixture, 'workspace' if args.scope == 'project' else 'home').mkdir()
        if args.action == 'replace':
            slug, _ = _read_bundle(ROOT, args.plan_id, args.agent, args.scope)
            target = _target_for_fixture(fixture, args.agent, args.scope, slug)
            target.mkdir(parents=True)
            (target / 'SKILL.md').write_bytes(b'---\nname: gasl-old-inert\n---\n')
            (target / 'user-note.txt').write_bytes(b'GASL_INERT_FIXTURE_NOTE\n')
        request = request_fixture_consent(fixture, ROOT, args.plan_id,
                    args.agent, args.scope, args.action)
        print(json.dumps({**request,
            'disposable_fixture_only': True,
            'user_profile_installation_allowed': False,
            'third_party_skill_execution_allowed': False,
        }, ensure_ascii=False, indent=2))
        print('Review the exact Plan ID, ZIP SHA-256, Host, scope and action above.')
        try:
            answer = input('Type the displayed confirmation phrase exactly (or press Enter to cancel): ')
        except (KeyboardInterrupt, EOFError):
            raise SystemExit('Fixture confirmation cancelled; no installation occurred')
        confirm_fixture_consent(fixture, ROOT, request['request_id'], answer)
        preview = preview_fixture_consent(fixture, ROOT, args.plan_id,
                                          args.agent, args.scope, args.action)
        applied = enact_fixture_transaction(fixture, ROOT, args.plan_id,
            args.agent, args.scope, args.action, preview['approval_challenge'],
            consent_request_id=request['request_id'])
        restored = recover_fixture_transaction(fixture)
        print(json.dumps({
            'status': 'interactive_fixture_consent_and_rollback_verified',
            'receipt_consumed_once': applied['one_time_fixture_receipt_consumed'],
            'original_fixture_state_restored': restored['previous_files_restored'],
            'human_phrase_entered_in_local_tty': True,
            'real_user_identity_verified': False,
            'real_host_files_modified': False,
            'production_installation_enabled': False,
            'third_party_skill_executed': False,
        }, ensure_ascii=False, indent=2))


def cmd_codex_pinned_bundle_e2e(args):
    from codex_pinned_bundle_e2e import verify_pinned_bundle_lifecycle
    result = verify_pinned_bundle_lifecycle(
        args.codex_bin, args.plan_id, args.acknowledge_fixture_only,
        bundle_root=ROOT)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result['status'] != 'real_codex_pinned_full_bundle_discovery_and_rollback_verified':
        raise SystemExit(1)


def cmd_codex_transaction_e2e(args):
    from codex_transaction_e2e import verify_full_codex_lifecycle
    result = verify_full_codex_lifecycle(args.codex_bin, scope=args.scope,
        require_one_time_fixture_receipt=args.test_one_time_receipt)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result['status'] != 'real_codex_inert_install_discovery_rollback_verified':
        raise SystemExit(1)


def cmd_locked_bundle_fixture(args):
    from fixture_transaction_v2 import rehearse_locked_transaction
    if args.acknowledge_fixture_only != 'GASL_DISPOSABLE_FIXTURE_ONLY':
        raise SystemExit('Explicit GASL_DISPOSABLE_FIXTURE_ONLY acknowledgement is required')
    result = rehearse_locked_transaction(args.plan_id, args.agent, args.scope,
        args.acknowledge_plan_id, bundle_root=ROOT, action=args.action,
        checkpoint=args.checkpoint)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_target_preflight(args):
    from host_target_preflight import inspect_selected_target, verify_target_unchanged
    if args.expect_state_binding_id:
        result = verify_target_unchanged(args.plan_id, args.agent, args.scope,
            args.selected_root, args.expect_state_binding_id, bundle_root=ROOT)
    else:
        result = inspect_selected_target(args.plan_id, args.agent, args.scope,
            args.selected_root, bundle_root=ROOT)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_bundle_fixture(args):
    from fixture_bundle_install import rehearse_private_bundle
    result = rehearse_private_bundle(args.plan_id, args.agent, args.scope,
        args.acknowledge_plan_id, bundle_root=ROOT,
        scenario=args.scenario, stop_after=args.stop_after)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_install_bundle(args):
    from install_bundle import prepare_private_bundle, verify_private_bundle
    if args.verify_plan_id:
        result = verify_private_bundle(args.verify_plan_id, root=ROOT)
    elif args.id and args.agent and args.acknowledge_plan_id:
        result = prepare_private_bundle(args.id, args.agent, args.scope,
                                        args.acknowledge_plan_id, root=ROOT)
    else:
        raise SystemExit('Provide --verify-plan-id OR --id --agent --acknowledge-plan-id')
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_host_format_review(args):
    from host_format_review import review_host_format
    result = review_host_format(args.plan_id, args.host, args.scope, root=ROOT)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_codex_project_install(args):
    from codex_project_install import (
        preview_install, install_fresh, preview_replace, replace_existing,
        list_backups, preview_restore, restore_backup, uninstall, recover)
    from codex_uninstalled_restore import (
        list_uninstalled_backups, preview_reinstall, reinstall_backup)
    from codex_legacy_reconcile import (
        audit_legacy_backups, preview_legacy_reinstall, reinstall_legacy_backup)
    if args.action in ('audit-legacy-backups','preview-legacy-reinstall','reinstall-legacy-backup'):
        if not args.skill_name:
            raise SystemExit('Legacy backup review requires --skill-name')
        if args.action == 'audit-legacy-backups':
            result = audit_legacy_backups(args.skill_name, args.selected_root)
        elif args.action == 'preview-legacy-reinstall':
            if not args.backup_id:
                raise SystemExit('Legacy preview requires --backup-id')
            result = preview_legacy_reinstall(args.skill_name, args.selected_root, args.backup_id)
        else:
            if not args.backup_id or not args.state_binding_id:
                raise SystemExit('Legacy reinstall requires --backup-id and --state-binding-id')
            result = reinstall_legacy_backup(args.skill_name, args.selected_root,
                                             args.backup_id, args.state_binding_id)
    elif args.action in ('list-uninstalled-backups','preview-reinstall','reinstall-backup'):
        if not args.skill_name:
            raise SystemExit('Archived reinstatement requires --skill-name')
        if args.action == 'list-uninstalled-backups':
            result = list_uninstalled_backups(args.skill_name, args.selected_root)
        elif args.action == 'preview-reinstall':
            if not args.backup_id:
                raise SystemExit('Previewing reinstall requires --backup-id')
            result = preview_reinstall(args.skill_name, args.selected_root, args.backup_id)
        else:
            if not args.backup_id or not args.state_binding_id:
                raise SystemExit('Reinstall requires --backup-id and --state-binding-id')
            result = reinstall_backup(args.skill_name, args.selected_root,
                                      args.backup_id, args.state_binding_id)
    elif args.action == 'list-backups':
        if not args.skill_name:
            raise SystemExit('Listing backups requires --skill-name')
        result = list_backups(args.skill_name, args.selected_root)
    elif args.action in ('preview-restore', 'restore-backup'):
        if not args.skill_name or not args.backup_id:
            raise SystemExit('Restore requires --skill-name and --backup-id')
        if args.action == 'preview-restore':
            result = preview_restore(args.skill_name, args.selected_root, args.backup_id)
        else:
            if not args.state_binding_id:
                raise SystemExit('Restore requires --state-binding-id from preview-restore')
            result = restore_backup(args.skill_name, args.selected_root,
                                    args.backup_id, args.state_binding_id)
    elif args.action in ('preview', 'install', 'preview-replace', 'replace'):
        if not args.plan_id:
            raise SystemExit('This action requires --plan-id')
        if args.action == 'preview':
            result = preview_install(args.plan_id, args.selected_root, bundle_root=ROOT)
        elif args.action == 'preview-replace':
            result = preview_replace(args.plan_id, args.selected_root, bundle_root=ROOT)
        else:
            if not args.state_binding_id:
                raise SystemExit('Real write requires the exact --state-binding-id from preview')
            if args.action == 'install':
                result = install_fresh(args.plan_id, args.selected_root,
                                       args.state_binding_id, bundle_root=ROOT)
            else:
                result = replace_existing(args.plan_id, args.selected_root,
                                           args.state_binding_id, bundle_root=ROOT)
    else:
        if not args.skill_name:
            raise SystemExit('Uninstall/recover requires --skill-name')
        result = (uninstall(args.skill_name, args.selected_root) if args.action == 'uninstall'
                  else recover(args.skill_name, args.selected_root))
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_host_project_install(args):
    import host_project_install as hp
    host,project=args.host,args.selected_root
    action=args.action
    if action in ('preview','install','preview-replace','replace'):
        if not args.plan_id:
            raise SystemExit('This action requires --plan-id from a verified private ZIP')
        if action=='preview':
            result=hp.preview_install(args.plan_id,project,host,bundle_root=ROOT)
        elif action=='preview-replace':
            result=hp.preview_replace(args.plan_id,project,host,bundle_root=ROOT)
        else:
            if not args.state_binding_id:
                raise SystemExit('Write action requires exact --state-binding-id from preview')
            handler=hp.install if action=='install' else hp.replace
            result=handler(args.plan_id,project,host,args.state_binding_id,
                           bundle_root=ROOT)
    else:
        if not args.skill_name:
            raise SystemExit('Backup/uninstall/recovery requires --skill-name')
        slug=args.skill_name
        if action=='list-backups':
            result=hp.list_backups(host,project,slug)
        elif action=='preview-uninstall':
            result=hp.preview_uninstall(host,project,slug)
        elif action=='uninstall':
            if not args.state_binding_id:
                raise SystemExit('Uninstall requires --state-binding-id from preview')
            result=hp.uninstall(host,project,slug,args.state_binding_id)
        elif action=='recover':
            result=hp.recover(host,project,slug)
        else:
            if not args.backup_id:
                raise SystemExit('Restore/reinstall requires exact --backup-id')
            if action=='preview-restore':
                result=hp.preview_restore(host,project,slug,args.backup_id)
            elif action=='preview-reinstall':
                result=hp.preview_reinstall(host,project,slug,args.backup_id)
            else:
                if not args.state_binding_id:
                    raise SystemExit('Restore/reinstall requires --state-binding-id')
                operation=hp.restore if action=='restore' else hp.reinstall
                result=operation(host,project,slug,args.backup_id,args.state_binding_id)
    print(json.dumps(result,ensure_ascii=False,indent=2))


def cmd_host_project_wizard(args):
    from host_project_wizard import inspect_handoff, install_from_explorer
    if args.action=='preview':
        result=inspect_handoff(args.id,args.selected_root,args.host,root=ROOT)
    else:
        result=install_from_explorer(
            args.id,args.selected_root,args.host,action=args.action,
            root=ROOT,download_if_missing=args.download_if_missing)
    print(json.dumps(result,ensure_ascii=False,indent=2))


def cmd_user_profile_install(args):
    import user_profile_install as hp
    host,profile=args.host,args.selected_home
    action=args.action
    if action in ('preview','install','preview-replace','replace'):
        if not args.plan_id:
            raise SystemExit('This action requires --plan-id from a verified private ZIP')
        if action=='preview':
            result=hp.preview_install(args.plan_id,profile,host,bundle_root=ROOT)
        elif action=='preview-replace':
            result=hp.preview_replace(args.plan_id,profile,host,bundle_root=ROOT)
        else:
            if not args.state_binding_id:
                raise SystemExit('Write action requires exact --state-binding-id from preview')
            handler=hp.install if action=='install' else hp.replace
            result=handler(args.plan_id,profile,host,args.state_binding_id,
                           bundle_root=ROOT)
    else:
        if not args.skill_name:
            raise SystemExit('Backup/uninstall/recovery requires --skill-name')
        slug=args.skill_name
        if action=='list-backups':
            result=hp.list_backups(host,profile,slug)
        elif action=='preview-uninstall':
            result=hp.preview_uninstall(host,profile,slug)
        elif action=='uninstall':
            if not args.state_binding_id:
                raise SystemExit('Uninstall requires --state-binding-id from preview')
            result=hp.uninstall(host,profile,slug,args.state_binding_id)
        elif action=='recover':
            result=hp.recover(host,profile,slug)
        else:
            if not args.backup_id:
                raise SystemExit('Restore/reinstall requires exact --backup-id')
            if action=='preview-restore':
                result=hp.preview_restore(host,profile,slug,args.backup_id)
            elif action=='preview-reinstall':
                result=hp.preview_reinstall(host,profile,slug,args.backup_id)
            else:
                if not args.state_binding_id:
                    raise SystemExit('Restore/reinstall requires --state-binding-id')
                operation=hp.restore if action=='restore' else hp.reinstall
                result=operation(host,profile,slug,args.backup_id,args.state_binding_id)
    print(json.dumps(result,ensure_ascii=False,indent=2))


def cmd_user_profile_wizard(args):
    from user_profile_wizard import inspect_handoff, install_from_explorer
    if args.action=='preview':
        result=inspect_handoff(args.id,args.selected_home,args.host,root=ROOT)
    else:
        result=install_from_explorer(
            args.id,args.selected_home,args.host,action=args.action,
            root=ROOT,download_if_missing=args.download_if_missing)
    print(json.dumps(result,ensure_ascii=False,indent=2))


def cmd_release_draft(args):
    from release_draft import inspect_release, build_release_draft, verify_release_draft
    result = {
        'inspect': inspect_release,
        'build': build_release_draft,
        'verify': verify_release_draft,
    }[args.action](root=ROOT)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_codex_install_wizard(args):
    from codex_explorer_handoff import inspect_handoff, install_from_explorer
    if args.action == 'preview':
        result = inspect_handoff(args.id, args.selected_root, root=ROOT)
    else:
        result = install_from_explorer(
            args.id, args.selected_root, action=args.action, root=ROOT,
            download_if_missing=args.download_if_missing)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_backup_review(args):
    from codex_backup_review import review_codex_backups, format_backup_review
    report = review_codex_backups(args.skill_name, args.selected_root,
                                  backup_id=args.backup_id)
    if args.format == 'json':
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_backup_review(report))


def cmd_provenance_compare(args):
    from codex_provenance_compare import (
        compare_codex_provenance, format_provenance_comparison)
    report = compare_codex_provenance(
        args.skill_name, args.selected_root,
        left_id=args.left, right_id=args.right)
    if args.format == 'json':
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_provenance_comparison(report))


def cmd_install_status(args):
    from install_lifecycle import simulation_status
    print(json.dumps(simulation_status(args.plan_id, root=ROOT), ensure_ascii=False, indent=2))


def cmd_download(args):
    from on_demand import download_skill
    print(json.dumps(download_skill(args.id, root=ROOT, execute=args.execute),
                     ensure_ascii=False, indent=2))


def cmd_sandbox(args):
    if args.verify_canary:
        from sandbox_canary_runner import run_benign_canary
        if not args.image_id:
            raise SystemExit('--verify-canary requires --image-id sha256:...')
        result = run_benign_canary(args.image_id)
        content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        print(content, end='')
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content, encoding='utf-8')
        if not result['benign_canary_verified']:
            raise SystemExit(1)
    else:
        from sandbox_gate import sandbox_status
        print(json.dumps(sandbox_status(), ensure_ascii=False, indent=2))


def cmd_audit(args):
    from security_gate import audit_local_package
    print(json.dumps(audit_local_package(args.id, root=ROOT),
                     ensure_ascii=False, indent=2))


def cmd_auto_review(args):
    """Run a reproducible local proxy review without pretending the labels are gold."""
    from auto_review import evaluate
    report = evaluate(ROOT, ROOT / 'private' / 'benchmark-review')
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    summary = {key: value for key, value in report.items() if key not in ('candidate_grades', 'queries')}
    summary['output'] = str(output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def cmd_mcp(args):
    """Run the local MCP server over STDIO; no hosted service is involved."""
    try:
        from mcp_server import create_mcp_server
    except ImportError as exc:
        raise SystemExit(
            "MCP dependency is missing. Run ./install.sh first "
            "or install requirements-mcp.txt."
        ) from exc
    create_mcp_server(ROOT).run(transport="stdio")


def cmd_serve(args):
    """Run the optional local-only REST API and Explorer."""
    if args.host not in ("127.0.0.1", "localhost", "::1") and not os.environ.get("GASL_API_TOKEN"):
        raise SystemExit(
            "Binding outside localhost requires GASL_API_TOKEN. "
            "For Agent integrations, prefer the default STDIO MCP transport."
        )
    from api_server import create_server
    server = create_server(args.host, args.port, root=ROOT)
    print("GASL Explorer: http://{}:{}/".format(args.host, server.server_address[1]), flush=True)
    print("Local-only process. Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping GASL local API...", flush=True)
    finally:
        server.server_close()


def cmd_features(args):
    from search_features import refresh
    # For ordinary users the source catalog is the published public index.
    print(json.dumps(refresh(ROOT, args.limit, args.workers), ensure_ascii=False, indent=2))


def cmd_enrich(args):
    from enrich_skill_metadata import enrich
    enrich(
        root=ROOT, limit=None if args.all else args.limit, workers=args.workers,
        refresh=args.refresh, retry_errors=args.retry_errors,
    )


def main():
    p = argparse.ArgumentParser(prog="gasl", description="Global AI Skills Library")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("summary")
    s.set_defaults(func=cmd_summary)
    b = sub.add_parser("bootstrap")
    b.set_defaults(func=cmd_bootstrap)
    v = sub.add_parser("verify")
    v.add_argument("--limit", type=int, default=0)
    v.add_argument("--only", nargs="*")
    v.add_argument("--trees", action="store_true")
    v.add_argument("--delay", type=float, default=0.5)
    v.set_defaults(func=cmd_verify)
    r = sub.add_parser("reconcile", help="Build source crosswalks from local snapshot and registry")
    def cmd_reconcile(args):
        from reconcile import run
        print(json.dumps(run(), indent=2))
    r.set_defaults(func=cmd_reconcile)
    domains = sub.add_parser("domains", help="List the domain taxonomy used by Skill search")
    domains.add_argument("--json", action="store_true")
    domains.set_defaults(func=cmd_domains)
    e = sub.add_parser("evaluate", help="Build evidence-only assessments; behavioral quality remains unrated")
    e.set_defaults(func=cmd_evaluate)
    i = sub.add_parser("index", help="Build the local SQLite FTS5 search index")
    i.add_argument("--check", action="store_true")
    i.set_defaults(func=cmd_index)
    benchmark = sub.add_parser("benchmark", help="Run the provisional bilingual search relevance benchmark")
    benchmark.add_argument("--dataset", type=Path, default=ROOT / "benchmarks" / "search-gold-v1.json")
    benchmark.add_argument("--k", type=int, default=5)
    benchmark.add_argument("--mrr-k", type=int, default=10)
    benchmark.add_argument("--output", type=Path)
    benchmark.set_defaults(func=cmd_benchmark)
    auto_review = sub.add_parser('auto-review', help='Run independent-from-rank internal proxy assessment; not human gold')
    auto_review.add_argument('--output', type=Path, default=ROOT / 'private' / 'benchmark-review' / 'AUTOMATED-PROXY-EVALUATION-V1.json')
    auto_review.set_defaults(func=cmd_auto_review)
    sandbox = sub.add_parser('sandbox', help='Read-only readiness or explicitly requested inert Linux CI isolation canary')
    sandbox.add_argument('--verify-canary', action='store_true', help='Run only self-authored benign canary on Linux; no Skill execution')
    sandbox.add_argument('--image-id', help='Immutable local Docker image ID for the inert canary')
    sandbox.add_argument('--output', type=Path, help='Optional result JSON path (canary mode)')
    sandbox.set_defaults(func=cmd_sandbox)
    audit = sub.add_parser('audit', help='Offline static security audit of one previously downloaded pinned Skill')
    audit.add_argument('--id', required=True, help='Exact source_record_id; must already be downloaded')
    audit.set_defaults(func=cmd_audit)
    q = sub.add_parser("search", help="Search attributed Skill source records")
    q.add_argument("--query", required=True)
    q.add_argument("--limit", type=int, default=10)
    q.add_argument("--domain")
    q.add_argument("--license", dest="license_spdx")
    q.add_argument("--security-status")
    q.add_argument("--public-only", action="store_true")
    q.add_argument("--content-only", action="store_true")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_search)
    route = sub.add_parser("route", help="Rank Skill candidates for a task; does not install or execute")
    route.add_argument("--task", required=True)
    route.add_argument("--top-k", type=int, default=5)
    route.add_argument("--domain")
    route.add_argument("--license", dest="license_spdx")
    route.add_argument("--agent")
    route.add_argument("--strict-agent", action="store_true")
    route.add_argument("--public-only", action="store_true")
    route.add_argument("--content-only", action="store_true")
    route.add_argument("--json", action="store_true")
    route.set_defaults(func=cmd_route)

    get = sub.add_parser("get", help="Retrieve one verified SKILL.md from the pinned source")
    get.add_argument("--id", required=True)
    get.add_argument("--max-chars", type=int, default=20000)
    get.add_argument("--offline", action="store_true")
    get.set_defaults(func=cmd_get)
    host_probe = sub.add_parser('host-probe', help='Read-only CLI presence probe; never launches real Hosts')
    host_probe.set_defaults(func=cmd_host_probe)
    host_transaction = sub.add_parser('host-transaction-rehearsal',
        help='Inert fixture crash-recovery test; never installs a real Skill')
    host_transaction.add_argument('--agent', required=True, choices=('codex', 'cursor', 'claude-code'))
    host_transaction.add_argument('--scope', choices=('project', 'user'), default='project')
    host_transaction.add_argument('--kind', choices=('fresh', 'upgrade'), default='upgrade')
    host_transaction.add_argument('--interrupt-after', choices=('prepared', 'old_backed_up', 'new_activated'),
                                  default='new_activated')
    host_transaction.set_defaults(func=cmd_host_transaction)

    host_adapters = sub.add_parser('host-adapters', help='Show documented Skill host layout matrix; no real host probing')
    host_adapters.set_defaults(func=cmd_host_adapters)
    host_rehearsal = sub.add_parser('host-rehearsal', help='Inert fixture-only adapter install/rollback test; no actual Agent files')
    host_rehearsal.add_argument('--agent', required=True, choices=('codex', 'cursor', 'claude-code', 'claude-desktop', 'generic-mcp'))
    host_rehearsal.add_argument('--scope', choices=('project', 'user'), default='project')
    host_rehearsal.add_argument('--scenario', choices=('fresh', 'upgrade', 'conflict', 'symlink'), default='upgrade')
    host_rehearsal.set_defaults(func=cmd_host_rehearsal)

    install_plan = sub.add_parser('install-plan', help='Read-only pinned Skill install preview; never install')
    install_plan.add_argument('--id', required=True, help='Source Record ID')
    install_plan.add_argument('--agent', required=True, choices=('codex', 'cursor', 'claude-code', 'claude-desktop', 'generic-mcp'))
    install_plan.add_argument('--scope', choices=('user', 'project'), default='user')
    install_plan.set_defaults(func=cmd_install_plan)

    install_simulate = sub.add_parser('install-simulate', help='Simulation-only apply/rollback event; never touch Agent files')
    install_simulate.add_argument('--action', required=True, choices=('apply', 'rollback'))
    install_simulate.add_argument('--plan-id', required=True, help='SHA-256 plan ID')
    install_simulate.add_argument('--acknowledge-plan-id', required=True,
                                  help='Explicitly repeat exact plan ID; simulated approval only')
    install_simulate.add_argument('--id', help='Source Record ID, required for simulated apply')
    install_simulate.add_argument('--agent', choices=('codex', 'cursor', 'claude-code', 'claude-desktop', 'generic-mcp'),
                                  help='Required for simulated apply')
    install_simulate.add_argument('--scope', choices=('user', 'project'), default='user')
    install_simulate.set_defaults(func=cmd_install_simulate)

    interactive_consent = sub.add_parser('consent-fixture-interactive',
        help='Require real TTY phrase for ONE private ZIP transaction in a disposable fixture only')
    interactive_consent.add_argument('--plan-id', required=True)
    interactive_consent.add_argument('--agent', required=True, choices=('codex','cursor','claude-code'))
    interactive_consent.add_argument('--scope', required=True, choices=('project','user'))
    interactive_consent.add_argument('--action', required=True, choices=('install','replace'))
    interactive_consent.add_argument('--acknowledge-fixture-only', required=True)
    interactive_consent.set_defaults(func=cmd_interactive_fixture_consent)

    pinned_codex = sub.add_parser('codex-pinned-bundle-e2e',
        help='Exact pinned full ZIP -> temporary Codex HOME -> skills/list -> rollback; never installs for a user')
    pinned_codex.add_argument('--codex-bin', required=True, type=Path)
    pinned_codex.add_argument('--plan-id', required=True)
    pinned_codex.add_argument('--acknowledge-fixture-only', required=True,
        help='Exactly GASL_DISPOSABLE_CODEX_BUNDLE_ONLY; never grants production approval')
    pinned_codex.set_defaults(func=cmd_codex_pinned_bundle_e2e)

    codex_e2e = sub.add_parser('codex-transaction-e2e',
        help='Query real Codex after fixture-only install and rollback of inert Skill (no account/model)')
    codex_e2e.add_argument('--codex-bin', required=True, type=Path,
        help='Absolute path to locally installed trusted Codex CLI executable')
    codex_e2e.add_argument('--scope', choices=('project','user'), default='project',
        help='Use a disposable HOME; user scope targets its isolated ~/.agents/skills')
    codex_e2e.add_argument('--test-one-time-receipt', action='store_true',
        help='CI-only simulated confirmation in disposable fixture; NOT human approval')
    codex_e2e.set_defaults(func=cmd_codex_transaction_e2e)

    locked_fixture = sub.add_parser('locked-bundle-fixture',
        help='Test-only exact ZIP+target challenge, POSIX process lock and crash recovery in fresh temp profile')
    locked_fixture.add_argument('--plan-id', required=True)
    locked_fixture.add_argument('--acknowledge-plan-id', required=True)
    locked_fixture.add_argument('--agent', required=True, choices=('codex','cursor','claude-code'))
    locked_fixture.add_argument('--scope', required=True, choices=('project','user'))
    locked_fixture.add_argument('--action', required=True, choices=('install','replace'))
    locked_fixture.add_argument('--checkpoint', default='activated',
        choices=('staged','backed_up','activated'))
    locked_fixture.add_argument('--acknowledge-fixture-only', required=True,
        help='Type GASL_DISPOSABLE_FIXTURE_ONLY; this never authorizes a real Host install')
    locked_fixture.set_defaults(func=cmd_locked_bundle_fixture)

    target_preflight = sub.add_parser('target-preflight',
        help='READ-ONLY check of an explicitly selected Host root; never install, approve or modify')
    target_preflight.add_argument('--plan-id', required=True)
    target_preflight.add_argument('--agent', required=True, choices=('codex','cursor','claude-code'))
    target_preflight.add_argument('--scope', required=True, choices=('project','user'))
    target_preflight.add_argument('--selected-root', required=True, type=Path,
        help='Exact pre-existing project root or user home root; never autodetected')
    target_preflight.add_argument('--expect-state-binding-id',
        help='Optional prior read-only binding to detect target/package drift; NOT install authorization')
    target_preflight.set_defaults(func=cmd_target_preflight)

    bundle_fixture = sub.add_parser('bundle-fixture',
        help='Materialize a PRIVATE ZIP in a temporary isolated Host profile, then restore; never touch user Agents')
    bundle_fixture.add_argument('--plan-id', required=True)
    bundle_fixture.add_argument('--acknowledge-plan-id', required=True,
        help='Explicit acknowledgment for TEMPORARY PROFILE only; not actual Host install permission')
    bundle_fixture.add_argument('--agent', required=True, choices=('codex','cursor','claude-code'))
    bundle_fixture.add_argument('--scope', default='project', choices=('project','user'))
    bundle_fixture.add_argument('--scenario', default='fresh', choices=('fresh','upgrade','conflict'))
    bundle_fixture.add_argument('--stop-after', default='activated',
        choices=('staged','backed_up','activated'))
    bundle_fixture.set_defaults(func=cmd_bundle_fixture)

    install_bundle = sub.add_parser('install-bundle', help='Private reviewed ZIP handoff ONLY; no Skill installation or execution')
    install_bundle.add_argument('--id', help='Pinned Source Record ID to bundle')
    install_bundle.add_argument('--agent', choices=('codex', 'cursor', 'claude-code', 'claude-desktop'),
                                help='Intended Host label; not an installation approval')
    install_bundle.add_argument('--scope', choices=('user', 'project'), default='user')
    install_bundle.add_argument('--acknowledge-plan-id', help='Exact plan ID from install-plan; explicitly prepare ZIP')
    install_bundle.add_argument('--verify-plan-id', help='Check a previously created private ZIP without extraction')
    install_bundle.set_defaults(func=cmd_install_bundle)

    host_format = sub.add_parser('host-format-review',
        help='Check pinned ZIP Skill metadata for a Host without installing or running it')
    host_format.add_argument('--plan-id', required=True, help='Previously verified private bundle Plan ID')
    host_format.add_argument('--host', required=True, choices=('codex', 'cursor', 'claude-code'))
    host_format.add_argument('--scope', default='user', choices=('user', 'project'))
    host_format.set_defaults(func=cmd_host_format_review)

    codex_project = sub.add_parser('codex-project-install',
        help='Explicit Codex project Skill install/replace/restore/archived reinstall/uninstall')
    codex_project.add_argument('--action', required=True,
        choices=('preview','install','preview-replace','replace',
                 'list-backups','preview-restore','restore-backup',
                 'list-uninstalled-backups','preview-reinstall','reinstall-backup',
                 'audit-legacy-backups','preview-legacy-reinstall','reinstall-legacy-backup',
                 'uninstall','recover'))
    codex_project.add_argument('--selected-root', type=Path, required=True,
        help='Existing absolute Git project root, never real user HOME')
    codex_project.add_argument('--plan-id', help='Exact pinned private ZIP Plan ID for preview, fresh install or replacement')
    codex_project.add_argument('--state-binding-id',
        help='Exact binding from read-only preview; required before install, replace or backup restore')
    codex_project.add_argument('--skill-name', help='Exact managed Skill name for restore/reinstall/uninstall/recover')
    codex_project.add_argument('--backup-id',
        help='Exact backup ID for restore or archived reinstall')
    codex_project.set_defaults(func=cmd_codex_project_install)

    project_host = sub.add_parser('host-project-install',
        help='Real transactional CURSOR / CLAUDE-CODE project Skill install and recovery')
    project_host.add_argument('--host',required=True,choices=('codex','cursor','claude-code'),
        help='Windows supports all three; POSIX Codex uses its existing dedicated command')
    project_host.add_argument('--action',required=True,choices=(
        'preview','install','preview-replace','replace',
        'list-backups','preview-restore','restore',
        'preview-uninstall','uninstall','preview-reinstall','reinstall','recover'))
    project_host.add_argument('--selected-root',required=True,type=Path,
        help='Explicit absolute Git project root; never user HOME')
    project_host.add_argument('--plan-id',help='Exact Plan ID of verified Host-scoped private ZIP')
    project_host.add_argument('--state-binding-id',help='Exact state binding from preview')
    project_host.add_argument('--skill-name',help='Exact Skill folder for backup/uninstall/recovery')
    project_host.add_argument('--backup-id',help='Exact owned backup ID for restore/reinstall')
    project_host.set_defaults(func=cmd_host_project_install)

    host_wizard = sub.add_parser('host-project-wizard',
        help='Explorer-selected Cursor/Claude Code project installation with exact local TTY approvals')
    host_wizard.add_argument('--host',required=True,choices=('codex','cursor','claude-code'),
        help='Windows supports all three; POSIX Codex uses codex-install-wizard')
    host_wizard.add_argument('--id',required=True,help='Pinned source record ID')
    host_wizard.add_argument('--selected-root',required=True,type=Path,
        help='Existing absolute Git project root')
    host_wizard.add_argument('--action',choices=('preview','install','replace'),default='preview')
    host_wizard.add_argument('--download-if-missing',action='store_true',
        help='Opt-in pinned download requiring separate exact local TTY approval')
    host_wizard.set_defaults(func=cmd_host_project_wizard)

    user_host = sub.add_parser('user-profile-install',
        help='POSIX current-user transactions; Windows User Profile is gated pending native SID/ACL CI')
    user_host.add_argument('--host',required=True,choices=('codex','cursor','claude-code'))
    user_host.add_argument('--action',required=True,choices=(
        'preview','install','preview-replace','replace',
        'list-backups','preview-restore','restore',
        'preview-uninstall','uninstall','preview-reinstall','reinstall','recover'))
    user_host.add_argument('--selected-home',required=True,type=Path,
        help='Exact current OS profile; POSIX passwd/UID or Windows token/SID validation')
    user_host.add_argument('--plan-id',help='Exact Plan ID of verified Host-scoped private ZIP')
    user_host.add_argument('--state-binding-id',help='Exact state binding from preview')
    user_host.add_argument('--skill-name',help='Exact Skill folder for backup/uninstall/recovery')
    user_host.add_argument('--backup-id',help='Exact owned backup ID for restore/reinstall')
    user_host.set_defaults(func=cmd_user_profile_install)

    user_wizard = sub.add_parser('user-profile-wizard',
        help='Local-TTY user-profile installation for Codex, Cursor and Claude Code')
    user_wizard.add_argument('--host',required=True,choices=('codex','cursor','claude-code'))
    user_wizard.add_argument('--id',required=True,help='Pinned source record ID')
    user_wizard.add_argument('--selected-home',required=True,type=Path,
        help='Existing absolute OS profile; must not be an arbitrary directory')
    user_wizard.add_argument('--action',choices=('preview','install','replace'),default='preview')
    user_wizard.add_argument('--download-if-missing',action='store_true',
        help='Opt-in pinned download requiring separate exact local TTY approval')
    user_wizard.set_defaults(func=cmd_user_profile_wizard)

    release_draft = sub.add_parser('release-draft',
        help='Inspect/build/verify a PRIVATE reproducible MVP ZIP; never publish or grant a license')
    release_draft.add_argument('--action', required=True,
        choices=('inspect', 'build', 'verify'),
        help='Public release is blocked until license and other release gates are resolved')
    release_draft.set_defaults(func=cmd_release_draft)

    codex_wizard = sub.add_parser(
        'codex-install-wizard',
        help='Local interactive Codex project install handoff; NO installation via HTTP')
    codex_wizard.add_argument('--id', required=True, help='Exact pinned Skill source record ID')
    codex_wizard.add_argument('--selected-root', required=True, type=Path,
        help='Absolute existing Git project root; never auto-detect or use the user HOME')
    codex_wizard.add_argument('--action', choices=('preview', 'install', 'replace'),
        default='preview',
        help='Preview is read-only; install/replace need exact local interactive TTY approval')
    codex_wizard.add_argument('--download-if-missing', action='store_true',
        help='For install/replace only: separate exact TTY consent for pinned GitHub download')
    codex_wizard.set_defaults(func=cmd_codex_install_wizard)

    backup_review = sub.add_parser('backup-review',
        help='READ-ONLY one-screen Codex project Backup review, provenance, warnings and next steps')
    backup_review.add_argument('--selected-root', required=True, type=Path,
        help='Explicit existing Git project root; no implicit HOME or project discovery')
    backup_review.add_argument('--skill-name', required=True,
        help='Exact single Codex project Skill slug')
    backup_review.add_argument('--backup-id',
        help='Optional exact retained Backup ID for a read-only binding-bound recovery preview')
    backup_review.add_argument('--format', choices=('text','json'), default='text',
        help='Human-readable review by default, or machine-readable JSON; no writes in either format')
    backup_review.set_defaults(func=cmd_backup_review)

    provenance_compare = sub.add_parser('provenance-compare',
        help='READ-ONLY local evidence matrix and two-version comparison; does not check upstream authenticity')
    provenance_compare.add_argument('--selected-root', required=True, type=Path,
        help='Explicit existing Git project root; no implicit HOME or project discovery')
    provenance_compare.add_argument('--skill-name', required=True, help='Exact Codex project Skill slug')
    provenance_compare.add_argument('--left',
        help='Exact Backup ID or active (when installed); both --left and --right required')
    provenance_compare.add_argument('--right',
        help='Exact Backup ID or active (when installed); both --left and --right required')
    provenance_compare.add_argument('--format', choices=('text','json'), default='text',
        help='Human-readable evidence matrix by default; JSON for reports, never writes')
    provenance_compare.set_defaults(func=cmd_provenance_compare)

    install_status = sub.add_parser('install-status', help='Read-only simulated install state for a plan ID')
    install_status.add_argument('--plan-id', required=True)
    install_status.set_defaults(func=cmd_install_status)

    download = sub.add_parser("download", help="Plan one complete local Skill package; --execute downloads without installing")
    download.add_argument("--id", required=True)
    download.add_argument("--execute", action="store_true")
    download.set_defaults(func=cmd_download)

    mcp = sub.add_parser(
        "mcp",
        help="Run the local MCP server over STDIO for Claude, Cursor, Codex, and other MCP hosts",
    )
    mcp.set_defaults(func=cmd_mcp)

    serve = sub.add_parser(
        "serve",
        help="Run the optional local REST API and Explorer (no hosted server required)",
    )
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8787)
    serve.set_defaults(func=cmd_serve)

    features = sub.add_parser("features", help="Incrementally extract verified standard search vocabulary")
    features.add_argument("--limit", type=int, default=100)
    features.add_argument("--workers", type=int, default=4)
    features.set_defaults(func=cmd_features)

    enrich = sub.add_parser(
        "enrich",
        help="Fetch pinned SKILL.md metadata into the ignored local cache; never execute content",
    )
    enrich.add_argument("--limit", type=int, default=100, help="Maximum records per run (default: 100)")
    enrich.add_argument("--all", action="store_true", help="Explicitly process all remaining source records")
    enrich.add_argument("--workers", type=int, default=4)
    enrich.add_argument("--refresh", action="store_true")
    enrich.add_argument("--retry-errors", action="store_true", help="Retry cached failures only; do not fetch new records")
    enrich.set_defaults(func=cmd_enrich)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
