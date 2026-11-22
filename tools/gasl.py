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


def cmd_download(args):
    from on_demand import download_skill
    print(json.dumps(download_skill(args.id, root=ROOT, execute=args.execute),
                     ensure_ascii=False, indent=2))


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
