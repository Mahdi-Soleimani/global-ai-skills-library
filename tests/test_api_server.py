import json
import hashlib
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

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

    def test_canonical_relations_offline_authorized_and_exact(self):
        path = self.root / "registry" / "source-catalog.json"
        record = json.loads(path.read_text(encoding="utf-8"))["records"][0]
        def pinned(row):
            seed = "\0".join((row["repository"].casefold(),row["source_path"],row["commit_sha"]))
            return dict(row, source_record_id="GASL-SRC-"+hashlib.sha256(seed.encode()).hexdigest()[:20])
        first = pinned(record)
        second = pinned(dict(record, repository="another/skills"))
        third = pinned(dict(record, commit_sha="b"*40, skill_md_blob_sha=None))
        raw = json.dumps({"schema_version":"1.0.0","records":[first,second,third]}).encode()
        path.write_bytes(raw)
        endpoint = "/v1/skills/"+first["source_record_id"]+"/relations"
        with patch("safe_http.open_pinned_url", side_effect=AssertionError("Network forbidden")), \
             patch("canonical_lineage._get", side_effect=AssertionError("Network forbidden")):
            self.assertEqual(self.request(endpoint,auth=False)[0],401)
            status,body = self.request(endpoint)
            self.assertEqual(status,200)
            report=json.loads(body)
            self.assertEqual(report["source_record_id"],first["source_record_id"])
            self.assertEqual(len(report["related_groups"]),2)
            self.assertFalse(report["package_equivalence_established"])
            self.assertFalse(report["installation_or_execution_approved"])
            self.assertEqual(self.request(endpoint+"?verify_online=true")[0],400)
            self.assertEqual(self.request("/v1/skills/GASL-SRC-"+"0"*20+"/relations")[0],404)
            self.assertEqual(self.request("/v1/skills/invalid/relations")[0],400)
        self.assertEqual(path.read_bytes(),raw)

    def test_canonical_relations_fails_closed_for_invalid_catalog(self):
        path = self.root / "registry" / "source-catalog.json"
        path.write_text('{"schema_version":"1.0.0","records":[]}',encoding="utf-8")
        status,body=self.request("/v1/skills/GASL-SRC-"+"0"*20+"/relations")
        self.assertEqual(status,503)
        self.assertEqual(json.loads(body)["detail"],"Canonical catalog evidence unavailable.")

    def test_root_review_and_plan_require_explicit_read_only_request(self):
        from root_skill_review import inspect_inventory
        from tests.test_root_skill_review import fixture
        from tests.test_canonical_package import blob
        row,tree=fixture(blob("SKILL.md",b"# inert"),blob("LICENSE",b"terms"),blob("extra.txt",b"extra"))
        review=inspect_inventory(row,tree)
        sid=row["source_record_id"]
        endpoint="/v1/root-skill-review"
        plan_endpoint="/v1/root-skill-plan"
        body={"id":sid,"review_sha256":review["review_sha256"],"files":["SKILL.md"]}
        with patch("root_skill_review.inspect_root_skill",return_value=review) as inspect, \
             patch("root_skill_scope._fetch",side_effect=AssertionError("No blob fetch")), \
             patch("root_skill_scope.collect_scope",side_effect=AssertionError("No collection")):
            self.assertEqual(self.request(endpoint,"POST",{"id":sid},auth=False)[0],401)
            self.assertEqual(self.request(endpoint,"POST",{"id":sid,"execute":True})[0],400)
            self.assertEqual(self.request(plan_endpoint,"POST",{**body,"execute":True})[0],400)
            self.assertEqual(self.request(plan_endpoint,"POST",{**body,"files":["extra.txt"]})[0],400)
            self.assertEqual(self.request(endpoint)[0],404)
            inspect.assert_not_called()
            status,raw=self.request(endpoint,"POST",{"id":sid})
            self.assertEqual(status,200)
            self.assertEqual(json.loads(raw)["review_sha256"],review["review_sha256"])
            self.assertEqual(self.request(plan_endpoint,"POST",{**body,"review_sha256":"f"*64})[0],409)
            status,raw=self.request(plan_endpoint,"POST",body)
            self.assertEqual(status,200)
            plan=json.loads(raw)
            self.assertEqual([x["path"] for x in plan["plan"]["files"]],["LICENSE","SKILL.md"])
            self.assertEqual(plan["candidate_coverage"]["missing_candidate_paths"],["extra.txt"])
            self.assertFalse(plan["package_complete"])
            self.assertFalse(plan["installation_or_execution_approved"])
            self.assertFalse(plan["blob_contents_downloaded"])
        self.assertEqual(list((self.root/"private").iterdir()),[])

    def test_unknown_skill_returns_404(self):
        status, _ = self.request("/v1/skills/missing")
        self.assertEqual(status, 404)

    def test_invalid_query_returns_400(self):
        status, _ = self.request("/v1/search")
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
