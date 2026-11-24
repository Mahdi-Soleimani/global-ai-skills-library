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


def smoke(source=ROOT, *, mcp=False):
    with tempfile.TemporaryDirectory(prefix="gasl-private-draft-smoke-") as temporary:
        base = Path(temporary).resolve()
        package = base / "package"
        package.mkdir()
        report = extract_verified(source, package)
        home = base / "home"
        home.mkdir()
        env = {k: os.environ[k] for k in ("PATH", "SystemRoot", "WINDIR", "COMSPEC",
                "SYSTEMDRIVE", "PATHEXT", "LD_LIBRARY_PATH") if k in os.environ}
        env.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home),
                   LOCALAPPDATA=str(home), TMPDIR=str(home), TEMP=str(home), TMP=str(home),
                   PYTHONUTF8="1", PYTHONIOENCODING="utf-8", GASL_HTTP_LOG="0")
        def run(*args):
            proc = subprocess.run([sys.executable, "-I", "-B", "-X", "utf8", *args], cwd=package,
                                  env=env, check=True, capture_output=True,
                                  encoding="utf-8", timeout=120)
            return json.loads(proc.stdout)
        search = run("tools/gasl.py", "search", "--query", "python security audit",
                     "--limit", "5", "--json")
        assert 0 < search["count"] <= 5
        route = run("tools/gasl.py", "route", "--task", "بررسی امنیت API پایتون",
                    "--top-k", "5", "--json")
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
    result = json.loads(get("/v1/search?q=python%20security&limit=3"))
    assert result["count"] > 0
    ident = result["results"][0]["source_record_id"]
    details = json.loads(get("/v1/skills/"+ident))
    assert not details["installation_allowed"] and not details["execution_allowed"]
    try:
        get("/v1/skills/"+ident+"/content?fetch_remote=false")
    except urllib.error.HTTPError as exc:
        assert exc.code == 502
        assert "not cached" in json.loads(exc.read())["detail"]
    else:
        raise AssertionError("Metadata-only archive unexpectedly has Skill content")
    print(json.dumps({"source_record_count": health["source_record_count"], "rest_verified": True}))
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
''')
        mcp_verified = False
        if mcp:
            result = run("-c", r'''
import asyncio, json, os, sys
from pathlib import Path
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
async def main():
    params = StdioServerParameters(command=sys.executable,
        args=["-I","-B","-X","utf8",str(Path.cwd()/"tools"/"gasl.py"),"mcp"],
        env=dict(os.environ),cwd=str(Path.cwd()))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {t.name for t in tools.tools} == {
                "gasl_search_skills", "gasl_get_skill_details", "gasl_get_skill_content",
                "gasl_route_task", "gasl_list_domains", "gasl_health"}
            reply = await session.call_tool("gasl_health", {})
            payload = json.loads(reply.content[0].text)
            assert payload["status"] == "ok" and not payload["execution_enabled"]
            print(json.dumps({"mcp_verified":True}))
asyncio.run(main())
''')
            mcp_verified = result["mcp_verified"]
        assert not any((package / p).exists() for p in (
            ".git", ".agents", ".cursor", ".claude", "catalog", "public-catalog/packages",
            "private/install-bundles", "private/skill-cache"))
        assert not any(home.iterdir())
        return {"status": "private_draft_standalone_smoke_passed",
                "source_commit": report["source_commit"], "archive_sha256": report["archive_sha256"],
                "source_record_count": rest["source_record_count"], "cli_search_verified": True,
                "bilingual_route_verified": True, "rest_explorer_verified": rest["rest_verified"],
                "mcp_stdio_verified": mcp_verified, "third_party_skill_executed": False,
                "public_release_allowed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--mcp", action="store_true")
    args = parser.parse_args()
    print(json.dumps(smoke(args.root, mcp=args.mcp), indent=2))
