import json
import hashlib
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from skill_evaluation import build_evaluations
from skill_search import build_index
from api_server import create_server


class ApiServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name in ("registry", "public-catalog", "config", "catalog", "private", "web"):
            (self.root / name).mkdir()
        (self.root / "web" / "index.html").write_text("<html>GASL Explorer</html>", encoding="utf-8")
        package_path = "catalog/example__skills/python-api-security"
        package = self.root / package_path
        package.mkdir(parents=True)
        (package / "SKILL.md").write_text(
            "---\nname: python-api-security\ndescription: Review Python APIs for security issues.\n---\n# Security\n",
            encoding="utf-8")
        fixture_bytes = (package / "SKILL.md").read_bytes()
        blob_sha = hashlib.sha1(b"blob " + str(len(fixture_bytes)).encode("ascii") + b"\0" + fixture_bytes).hexdigest()
        record = {
            "source_record_id": "GASL-SRC-api-test",
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
        self.server = create_server("127.0.0.1", 0, root=self.root, api_token="test-secret")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:{}".format(self.server.server_address[1])

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def request(self, path, method="GET", data=None, auth=True):
        headers = {}
        if auth:
            headers["Authorization"] = "Bearer test-secret"
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def test_explorer_is_served(self):
        status, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("GASL Explorer", body)

    def test_health_is_public_and_truthful(self):
        status, body = self.request("/health", auth=False)
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["search_engine"], "sqlite-fts5")
        self.assertFalse(payload["semantic_search_enabled"])
        self.assertEqual(payload["answerability_policy_status"], "experimental_heuristic_not_calibrated")
        self.assertFalse(payload["answerability_decisions_calibrated"])

    def test_api_requires_bearer_token(self):
        status, _ = self.request("/v1/search?q=python%20security", auth=False)
        self.assertEqual(status, 401)
        req = urllib.request.Request(self.base + "/v1/search?q=python", method="GET")
        try:
            urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.headers.get("WWW-Authenticate"), "Bearer")

    def test_domains_endpoint_returns_taxonomy_list(self):
        status, body = self.request("/v1/domains")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["domains"][0]["id"], "security")

    def test_search_and_details(self):
        status, body = self.request("/v1/search?q=python%20security")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["results"][0]["source_record_id"], "GASL-SRC-api-test")
        status, body = self.request("/v1/skills/GASL-SRC-api-test")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["repository"], "example/skills")

    def test_on_demand_content_endpoint(self):
        status, body = self.request("/v1/skills/GASL-SRC-api-test/content")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload["untrusted_content"])
        self.assertIn("# Security", payload["content"])

    def test_route_endpoint(self):
        status, body = self.request("/v1/route", method="POST", data={"task": "python security"})
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertFalse(payload["execution_performed"])
        self.assertIn(payload["routing_decision"], ("recommend", "abstain", "undetermined"))
        self.assertIn(payload["recommendation_status"],
                      ("provisional_candidate_to_inspect", "no_confident_candidate_in_retrieved_pool", "candidate_discovery_only"))
        self.assertEqual(payload["answerability"]["policy_status"], "experimental_heuristic_not_calibrated")

    def test_route_rejects_string_boolean(self):
        status, body = self.request(
            "/v1/route", method="POST",
            data={"task": "python security", "strict_agent": "false"})
        self.assertEqual(status, 400)
        self.assertIn("JSON boolean", json.loads(body)["detail"])

    def test_unknown_skill_returns_404(self):
        status, _ = self.request("/v1/skills/missing")
        self.assertEqual(status, 404)

    def test_invalid_query_returns_400(self):
        status, _ = self.request("/v1/search")
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
