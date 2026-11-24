"""Exercise only the project's own code from a verified private draft.

No external Skill files, installation, user profile, network fetch or publication.
The REST check uses a loopback socket; optional MCP uses local STDIO.
"""
import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from release_draft import verify_release_draft, _inputs, _regular_bytes, MAX_ARCHIVE_BYTES


def extract_verified(source, output):
    report = verify_release_draft(source)
    source, _, items, commit = _inputs(source)
    if report["source_commit"] != commit or not report["canonical_archive_encoding_verified"]:
        raise ValueError("Canonical draft of current commit required")
    archive = source / "private" / "release-drafts" / ("gasl-mvp-" + commit[:12] + ".zip")
    raw = _regular_bytes(source, archive, MAX_ARCHIVE_BYTES)
    if hashlib.sha256(raw).hexdigest() != report["archive_sha256"]:
        raise ValueError("Draft changed after verification")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for item in items:
            data = z.read("gasl-mvp/" + item["path"])
            if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise ValueError("Unexpected draft bytes")
            target = output / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(data)
            if os.name == "posix" and item["path"] in ("gasl", "install.sh"):
                target.chmod(0o755)
    return report


def smoke(source=ROOT, *, mcp=False, setup_runtime=False):
    with tempfile.TemporaryDirectory(prefix="gasl-private-draft-smoke-") as temporary:
        base = Path(temporary).resolve()
        package = base / "package with spaces"
        package.mkdir()
        report = extract_verified(source, package)
        home = base / "home"
        home.mkdir()
        env = {k: os.environ[k] for k in ("PATH", "SystemRoot", "WINDIR", "COMSPEC",
                "SYSTEMDRIVE", "PATHEXT", "LD_LIBRARY_PATH") if k in os.environ}
        env.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home),
                   LOCALAPPDATA=str(home), TMPDIR=str(home), TEMP=str(home), TMP=str(home),
                   PYTHONUTF8="1", PYTHONIOENCODING="utf-8", GASL_HTTP_LOG="0")
        python = sys.executable
        if setup_runtime:
            assert mcp, "Runtime setup smoke requires MCP checks"
            # Use the actual shipped installer, not the runner's preinstalled SDK.
            setup_env = dict(env)
            setup_env["PYTHONPATH"] = str(base/"nonexistent-injected-pythonpath")
            setup_env["PYTHONHOME"] = str(base/"nonexistent-injected-pythonhome")
            setup_command = [sys.executable, "-I", "-B", "-X", "utf8",
                             str(package/"tools/runtime_setup.py")]
            if os.name == "posix":
                # Shell wrapper uses python3; use the exact runner interpreter via PATH.
                setup_env["PATH"] = str(Path(sys.executable).parent)+os.pathsep+env.get("PATH","")
                setup_command = [str(package/"install.sh")]
            subprocess.run(setup_command, cwd=base, env=setup_env, check=True,
                           capture_output=True, timeout=240)
            subprocess.run(setup_command+["--check"], cwd=base, env=setup_env, check=True,
                           capture_output=True, timeout=60)
            python = str(package/".venv"/("Scripts/python.exe" if os.name=="nt" else "bin/python"))
        def run(*args):
            proc = subprocess.run([python, "-I", "-B", "-X", "utf8", *args], cwd=package,
                                  env=env, check=True, capture_output=True,
                                  encoding="utf-8", timeout=120)
            return json.loads(proc.stdout)
        version = run("-c", "import json,sys; print(json.dumps(list(sys.version_info[:3])))")
        assert version[:2] == list(sys.version_info[:2]), "Unexpected installed Python version"
        def cli(*args):
            if not setup_runtime:
                return run("tools/runtime_launch.py", *args)
            # Test the documented command from outside the package, using the base
            # Python (not the already-activated venv) and poisoned Python variables.
            launcher = [sys.executable, "-I", "-B", "-X", "utf8",
                        str(package/"tools/runtime_launch.py")]
            if os.name == "posix":
                launcher = [str(package/"gasl")]
            proc = subprocess.run([*launcher, *args], cwd=base, env=setup_env,
                                  check=True, capture_output=True, encoding="utf-8", timeout=120)
            return json.loads(proc.stdout)
        semantic = cli("semantic","--action","status")
        assert semantic["status"] == "not_built"
        assert semantic["index"]["record_count"] > 0
        assert semantic["default_search_changed"] is False
        assert not (package/"private/semantic-index-v1.bin").exists()
        search = cli("search", "--query", "python security audit", "--limit", "5", "--json")
        assert 0 < search["count"] <= 5
        route = cli("route", "--task", "بررسی امنیت API پایتون", "--top-k", "5", "--json")
        assert route["returned_count"] > 0
        assert route["installation_performed"] is False and route["execution_performed"] is False
        # Start the real packaged API, bind only loopback with an OS-assigned port,
        # and inspect HTTP responses in the same isolated child process.
        rest = run("-c", r'''
import json, sys, threading, urllib.request, urllib.error
from pathlib import Path
sys.path.insert(0, str(Path.cwd()/"tools"))
from api_server import create_server
server = create_server("127.0.0.1", 0, root=Path.cwd())
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
base = "http://127.0.0.1:" + str(server.server_address[1])
def get(path):
    with opener.open(base+path, timeout=10) as response:
        return response.read()
try:
    health = json.loads(get("/health"))
    assert health["status"] == "ok" and health["source_record_count"] > 0
    assert not health["installation_enabled"] and not health["execution_enabled"]
    assert b"GASL" in get("/")
    domains = json.loads(get("/v1/domains"))
    assert domains["count"] == len(domains["domains"]) > 0
    result = json.loads(get("/v1/search?q=python%20security&limit=3"))
    assert result["count"] > 0
    ident = result["results"][0]["source_record_id"]
    details = json.loads(get("/v1/skills/"+ident))
    assert not details["installation_allowed"] and not details["execution_allowed"]
    relations = json.loads(get("/v1/skills/"+ident+"/relations"))
    assert relations["source_record_id"] == ident
    assert isinstance(relations["related_groups"], list)
    assert not relations["installation_or_execution_approved"]
    assert not relations["independent_content_verification_performed"]

    # Both root-scope endpoints must ship, and must reject execution options
    # before any upstream metadata lookup or writes.
    from unittest.mock import patch
    from root_skill_scope import make_scope
    from root_skill_review import inspect_root_skill
    with patch("root_skill_review.inspect_root_skill", side_effect=AssertionError("Network forbidden")):
        for endpoint in ("/v1/root-skill-review", "/v1/root-skill-plan"):
            req = urllib.request.Request(base+endpoint,
                data=json.dumps({"id":ident,"execute":True}).encode("utf-8"),
                headers={"Content-Type":"application/json"},method="POST")
            try:
                opener.open(req,timeout=10)
            except urllib.error.HTTPError as exc:
                assert exc.code == 400
            else:
                raise AssertionError("Root scope API accepted execution option")
    assert not (Path.cwd()/"private/root-skill-scopes").exists()

    try:
        get("/v1/skills/"+ident+"/content?fetch_remote=false")
    except urllib.error.HTTPError as exc:
        assert exc.code == 502
        assert "not cached" in json.loads(exc.read())["detail"]
    else:
        raise AssertionError("Metadata-only archive unexpectedly has Skill content")
    print(json.dumps({"source_record_count": health["source_record_count"], "rest_verified": True, "root_scope_api_read_only_verified": True}))
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
''')
        mcp_verified = False
        mcp_tools_exercised = 0
        if mcp:
            result = run("-c", r'''
import asyncio, json, os, sys
from pathlib import Path
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
async def main():
    package = Path.cwd()
    if sys.argv[1] == "setup":
        # Exercise the README MCP configuration: POSIX launcher or Windows
        # absolute venv Python and exact CLI script.
        if os.name == "posix":
            command = str(package/"gasl")
            args = ["mcp"]
        else:
            command = sys.executable
            args = ["-I","-B","-X","utf8",str(package/"tools/gasl.py"),"mcp"]
        child_env = dict(os.environ)
        child_env["PATH"] = str(Path(sys.base_prefix)/("Scripts" if os.name=="nt" else "bin")) + os.pathsep + child_env.get("PATH","")
        child_env["PYTHONHOME"] = str(package.parent/"invalid-home")
        child_env["PYTHONPATH"] = str(package.parent/"invalid-path")
        cwd = str(package.parent)
    else:
        command = sys.executable
        args = ["-I","-B","-X","utf8",str(package/"tools/runtime_launch.py"),"mcp"]
        child_env = dict(os.environ)
        cwd = str(package)
    params = StdioServerParameters(command=command,args=args,env=child_env,cwd=cwd)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {t.name for t in tools.tools} == {
                "gasl_search_skills", "gasl_get_skill_details", "gasl_get_skill_content",
                "gasl_route_task", "gasl_list_domains", "gasl_health"}
            async def call(name, arguments):
                reply = await session.call_tool(name, arguments)
                assert not reply.is_error
                return json.loads(reply.content[0].text)
            health = await call("gasl_health", {})
            assert health["status"] == "ok" and not health["execution_enabled"]
            assert not health["installation_enabled"]
            domains = await call("gasl_list_domains", {})
            assert domains["domains"]
            search = await call("gasl_search_skills", {"query":"python security audit", "limit":5})
            assert 0 < search["count"] <= 5
            ident = search["results"][0]["source_record_id"]
            detail = await call("gasl_get_skill_details", {"source_record_id":ident})
            assert detail["source_record_id"] == ident
            assert len(detail["commit_sha"]) == 40
            assert not detail["installation_allowed"] and not detail["execution_allowed"]
            content = await call("gasl_get_skill_content",
                                 {"source_record_id":ident,"fetch_remote":False})
            assert content["error"] == "content_unavailable" and "not cached" in content["message"]
            route = await call("gasl_route_task", {"task":"بررسی امنیت API پایتون","top_k":5})
            assert route["returned_count"] > 0
            assert route["routing_decision"] in ("recommend","abstain","undetermined")
            assert not route["installation_performed"] and not route["execution_performed"]
            print(json.dumps({"mcp_verified":True,"mcp_tools_exercised":6}))
asyncio.run(main())
''', "setup" if setup_runtime else "existing")
            mcp_verified = result["mcp_verified"]
            mcp_tools_exercised = result["mcp_tools_exercised"]
        assert not any((package / p).exists() for p in (
            ".git", ".agents", ".cursor", ".claude", "catalog", "public-catalog/packages",
            "private/install-bundles", "private/skill-cache"))
        if setup_runtime:
            # venv/pip may use the disposable temporary directory; no real profile access.
            assert not any((home / p).exists() for p in (".agents",".cursor",".claude",".codex"))
        else:
            assert not any(home.iterdir())
        return {"status": "private_draft_standalone_smoke_passed",
                "source_commit": report["source_commit"], "archive_sha256": report["archive_sha256"],
                "source_record_count": rest["source_record_count"], "cli_search_verified": True,
                "shipped_runtime_setup_verified": setup_runtime,
                "runtime_python_version": ".".join(map(str, version)),
                "documented_entrypoints_verified": setup_runtime,
                "bilingual_route_verified": True, "rest_explorer_verified": rest["rest_verified"],
                "root_scope_api_read_only_verified": rest["root_scope_api_read_only_verified"],
                "optional_semantic_status_verified": True,
                "mcp_stdio_verified": mcp_verified, "mcp_tools_exercised": mcp_tools_exercised,
                "third_party_skill_executed": False,
                "public_release_allowed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--mcp", action="store_true")
    parser.add_argument("--setup", action="store_true", help="Install the pinned SDK in the extracted temporary package")
    args = parser.parse_args()
    print(json.dumps(smoke(args.root, mcp=args.mcp, setup_runtime=args.setup), indent=2))
