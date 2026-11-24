import asyncio
import json
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from skill_evaluation import build_evaluations
from skill_search import build_index
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp_server import create_mcp_server


class McpServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name in ("registry", "public-catalog", "config", "catalog", "private"):
            (self.root / name).mkdir()
        package_path = "catalog/example__skills/python-api-security"
        package = self.root / package_path
        package.mkdir(parents=True)
        (package / "SKILL.md").write_text("# Python API Security\n", encoding="utf-8")
        fixture_bytes = (package / "SKILL.md").read_bytes()
        blob_sha = hashlib.sha1(b"blob " + str(len(fixture_bytes)).encode("ascii") + b"\0" + fixture_bytes).hexdigest()
        record = {
            "source_record_id": "GASL-SRC-mcp-test",
            "skill_name": "python-api-security",
            "description": "Review Python APIs for security issues.",
            "repository": "example/skills",
            "repository_owner": "example",
            "repository_url": "https://github.com/example/skills",
            "source_path": "skills/python-api-security/SKILL.md",
            "source_url": "https://github.com/example/skills/blob/" + "a" * 40 + "/skills/python-api-security/SKILL.md",
            "commit_sha": "a" * 40,
            "skill_md_blob_sha": blob_sha,
            "license_spdx": "MIT",
            "license_evidence_path": "LICENSE",
            "license_assessment": "repository_license_metadata_only",
            "content_status": "downloaded_and_hashed_locally",
            "security_status": "not_scanned",
            "install_status": "not_installed",
            "snapshot_status": "verified_commit_pinned",
            "research_leads": ["EN-675"],
            "ownership": "third_party",
            "gasl_claims_exclusive_ownership": False,
        }
        (self.root / "registry" / "source-catalog.json").write_text(
            json.dumps({"records": [record]}), encoding="utf-8")
        (self.root / "registry" / "skills.json").write_text(json.dumps({"records": [{
            "repository": "example/skills",
            "source_skill_path": "skills/python-api-security/SKILL.md",
            "commit_sha": "a" * 40,
            "skill_name": "python-api-security",
            "description": "Review Python APIs for security issues.",
            "package_path": package_path,
            "package_content_present": True,
            "package_type": "skill_candidate",
        }]}), encoding="utf-8")
        (self.root / "public-catalog" / "index.json").write_text('{"packages":{}}', encoding="utf-8")
        (self.root / "config" / "taxonomy.json").write_text(
            json.dumps({"domains": [{"id": "security", "label": "Security", "keywords": ["security", "api"]}]}),
            encoding="utf-8")
        build_evaluations(self.root)
        build_index(self.root)
        self.server = create_mcp_server(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def call_tool(self, name, arguments):
        async def call():
            return await self.server.call_tool(name, arguments)
        return asyncio.run(call())

    def test_tool_registry_contains_discovery_and_content_tools(self):
        async def list_tools():
            return await self.server.list_tools()
        tools = asyncio.run(list_tools())
        names = {tool.name for tool in tools}
        self.assertEqual(names, {
            "gasl_search_skills", "gasl_get_skill_details", "gasl_get_skill_content",
            "gasl_route_task", "gasl_list_domains", "gasl_health",
        })

    def test_search_tool_returns_json_and_source_identity(self):
        result = self.call_tool("gasl_search_skills", {"query": "python security"})
        payload = json.loads(result.content[0].text)
        self.assertEqual(payload["results"][0]["source_record_id"], "GASL-SRC-mcp-test")

    def test_details_and_content_tools(self):
        detail = self.call_tool("gasl_get_skill_details", {"source_record_id": "GASL-SRC-mcp-test"})
        content = self.call_tool("gasl_get_skill_content", {"source_record_id": "GASL-SRC-mcp-test"})
        self.assertEqual(json.loads(detail.content[0].text)["repository"], "example/skills")
        content_payload = json.loads(content.content[0].text)
        self.assertTrue(content_payload["untrusted_content"])
        self.assertFalse(content_payload["executed"])

    def test_route_tool_never_installs_or_executes(self):
        result = self.call_tool("gasl_route_task", {"task": "python security"})
        payload = json.loads(result.content[0].text)
        self.assertFalse(payload["installation_performed"])
        self.assertFalse(payload["execution_performed"])
        self.assertIn(payload["routing_decision"], ("recommend", "abstain", "undetermined"))
        self.assertIn(payload["recommendation_status"],
                      ("provisional_candidate_to_inspect", "no_confident_candidate_in_retrieved_pool", "candidate_discovery_only"))
        self.assertEqual(payload["answerability"]["policy_status"], "experimental_heuristic_not_calibrated")
        self.assertFalse(payload["answerability"]["empty_results_prove_no_relevant_skill"])

    def test_domains_tool_returns_taxonomy_list(self):
        result = self.call_tool("gasl_list_domains", {})
        self.assertEqual(json.loads(result.content[0].text)["domains"][0]["id"], "security")

    def test_health_tool_reports_search_mode(self):
        result = self.call_tool("gasl_health", {})
        payload = json.loads(result.content[0].text)
        self.assertEqual(payload["search_engine"], "sqlite-fts5")
        self.assertEqual(payload["answerability_policy_status"], "experimental_heuristic_not_calibrated")
        self.assertFalse(payload["answerability_decisions_calibrated"])

    def test_real_stdio_transport_handshake_and_tool_call(self):
        async def run():
            env = dict(os.environ)
            env["GASL_ROOT"] = str(self.root)
            params = StdioServerParameters(
                command=sys.executable,
                args=[str(ROOT / "tools" / "mcp_server.py"), "--transport", "stdio"],
                env=env,
                cwd=str(ROOT),
            )
            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    initialized = await session.initialize()
                    self.assertEqual(initialized.server_info.name, "gasl")
                    tools = await session.list_tools()
                    self.assertIn("gasl_search_skills", {tool.name for tool in tools.tools})
                    result = await session.call_tool("gasl_health", {})
                    payload = json.loads(result.content[0].text)
                    self.assertEqual(payload["source_record_count"], 1)
                    self.assertFalse(payload["execution_enabled"])
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
