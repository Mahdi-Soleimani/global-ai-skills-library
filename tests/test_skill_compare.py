"""Phase 47: compare source-record evidence and the local Explorer workflow."""
import copy
import json
import shutil
import subprocess
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from skill_compare import compare_skills
from skill_evaluation import build_evaluations
from skill_search import build_index
from api_server import create_server
from tests.test_gasl_service import GaslServiceTests


class CompareFixtures(unittest.TestCase):
    def setUp(self):
        self.fixture = GaslServiceTests("test_search_uses_shared_core")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root
        source = self.root / "registry" / "source-catalog.json"
        catalog = json.loads(source.read_text())
        original = catalog["records"][0]
        other = copy.deepcopy(original)
        other.update({
            "source_record_id": "GASL-SRC-other-test",
            "skill_name": "database-backup",
            "description": "Create database backup plans and data migration tooling.",
            "repository": "second/example",
            "repository_owner": "second",
            "source_path": "skills/database-backup/SKILL.md",
            "source_url": "https://github.com/second/example/blob/" + "b"*40 + "/skills/database-backup/SKILL.md",
            "commit_sha": "b"*40,
            "license_spdx": "Apache-2.0",
            "security_status": "manual_review_required",
            "compatibility": "Cursor",
            "content_status": "not_downloaded_reference_record",
        })
        catalog["records"].append(other)
        source.write_text(json.dumps(catalog), encoding="utf-8")
        build_evaluations(self.root)
        build_index(self.root)
        self.ids = ["GASL-SRC-service-test", "GASL-SRC-other-test"]

    def test_comparison_preserves_selected_order_and_distinct_evidence(self):
        result = compare_skills(self.ids, root=self.root)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["source_record_ids"], self.ids)
        self.assertEqual(result["items"][0]["source_record_id"], self.ids[0])
        self.assertEqual(result["items"][1]["source_record_id"], self.ids[1])
        self.assertEqual(result["items"][0]["license_spdx"], "MIT")
        self.assertEqual(result["items"][1]["license_spdx"], "Apache-2.0")
        self.assertIn("license_spdx", result["different_fields"])
        self.assertIn("security_status", result["different_fields"])
        self.assertIn("compatibility", result["different_fields"])
        self.assertFalse(result["winner_selected"])
        self.assertFalse(result["quality_scoring_performed"])
        self.assertFalse(result["source_authenticity_independently_verified"])
        self.assertFalse(result["installation_performed"])
        self.assertFalse(result["execution_performed"])

    def test_reverse_selection_order_does_not_reassign_evidence(self):
        report = compare_skills(self.ids[::-1], root=self.root)
        self.assertEqual([x["source_record_id"] for x in report["items"]], self.ids[::-1])
        self.assertEqual(report["items"][0]["license_spdx"], "Apache-2.0")

    def test_three_distinct_choices_are_allowed(self):
        # Third evidence row uses its own stable local record.
        source = self.root / "registry" / "source-catalog.json"
        catalog = json.loads(source.read_text())
        third = copy.deepcopy(catalog["records"][1])
        third["source_record_id"] = "GASL-SRC-third-test"
        third["skill_name"] = "deployment-check"
        third["source_path"] = "skills/deployment-check/SKILL.md"
        catalog["records"].append(third)
        source.write_text(json.dumps(catalog))
        build_evaluations(self.root)
        build_index(self.root)
        report = compare_skills(self.ids + ["GASL-SRC-third-test"], root=self.root)
        self.assertEqual(report["count"], 3)

    def test_invalid_cardinality_is_rejected(self):
        for values in (None, [], [self.ids[0]], self.ids*2, "not a list"):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    compare_skills(values, root=self.root)

    def test_duplicate_records_are_refused(self):
        with self.assertRaisesRegex(ValueError, "distinct"):
            compare_skills([self.ids[0], self.ids[0]], root=self.root)

    def test_unknown_or_malformed_ids_are_refused(self):
        for bad in ("GASL-SRC-missing", "../etc/passwd", "GASL-SRC-'; rm -rf /", "GASL-SRC-"+"a"*110):
            with self.subTest(bad=bad):
                with self.assertRaises((KeyError, ValueError)):
                    compare_skills([self.ids[0], bad], root=self.root)

    def test_non_string_source_ids_are_refused(self):
        with self.assertRaises(ValueError):
            compare_skills([self.ids[0], 1234], root=self.root)

    def test_comparison_requires_no_remote_fetch_or_skill_execution(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("NETWORK")), patch(
            "subprocess.run", side_effect=AssertionError("SKILL_EXECUTION")
        ):
            result = compare_skills(self.ids, root=self.root)
        self.assertEqual(result["count"], 2)
        self.assertFalse(result["execution_performed"])

    def test_only_explicit_evidence_fields_are_returned(self):
        report = compare_skills(self.ids, root=self.root)
        for item in report["items"]:
            self.assertNotIn("content", item)
            self.assertNotIn("api_key", item)
            self.assertFalse(item["installation_allowed"])
            self.assertFalse(item["execution_allowed"])

    def test_comparison_does_not_modify_catalog_files(self):
        files = [self.root/"registry"/"source-catalog.json",
                 self.root/"registry"/"skills.json"]
        before = {str(path): path.read_bytes() for path in files}
        compare_skills(self.ids, root=self.root)
        self.assertEqual(before, {str(path): path.read_bytes() for path in files})


class CompareApiTests(CompareFixtures):
    def setUp(self):
        super().setUp()
        self.server = create_server("127.0.0.1", 0, root=self.root, api_token="test-secret")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.base = "http://127.0.0.1:{}".format(self.server.server_address[1])

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def post(self, payload, authorized=True, path="/v1/compare"):
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["Authorization"] = "Bearer test-secret"
        request = urllib.request.Request(self.base + path, method="POST", data=body, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def test_compare_endpoint_returns_distinct_verified_source_fields(self):
        status, result = self.post({"ids": self.ids})
        self.assertEqual(status, 200)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["source_record_ids"], self.ids)
        self.assertFalse(result["winner_selected"])

    def test_compare_endpoint_requires_bearer_token(self):
        status, _ = self.post({"ids": self.ids}, authorized=False)
        self.assertEqual(status, 401)

    def test_invalid_input_is_http_400(self):
        for ids in ([self.ids[0]], ["GASL-SRC-invalid!"]*2,
                    [self.ids[0], self.ids[0]], ["bad", "bad"]):
            with self.subTest(ids=ids):
                code, _ = self.post({"ids": ids})
                self.assertEqual(code, 400)

    def test_unknown_valid_id_is_404(self):
        code, payload = self.post({"ids": [self.ids[0], "GASL-SRC-not-found"]})
        self.assertEqual(code, 404)
        self.assertIn("not found", payload["detail"])

    def test_route_endpoint_still_works(self):
        code, result = self.post({"task": "python api security", "top_k": 2}, path="/v1/route")
        self.assertEqual(code, 200)
        self.assertFalse(result["installation_performed"])
        self.assertFalse(result["execution_performed"])


class ExplorerWorkflowMarkupTests(unittest.TestCase):
    def test_explorer_has_three_step_select_compare_review_flow(self):
        from html.parser import HTMLParser

        class IdCollector(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = set()
            def handle_starttag(self, tag, attrs):
                self.ids.update(value for key, value in attrs if key == "id")

        text = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        parser = IdCollector()
        parser.feed(text)
        self.assertTrue({
            "recommendButton", "searchButton", "query", "agent",
            "results", "comparePanel", "compareButton", "compareBody",
            "selectionPanel", "selectionBody"
        }.issubset(parser.ids))
        self.assertIn("/v1/route", text)
        self.assertIn("/v1/compare", text)
        self.assertIn("بررسی این گزینه", text)
        self.assertIn("install-plan", text)
        self.assertIn("textContent", text)

    @unittest.skipUnless(shutil.which("node"), "Node is optional for syntax validation")
    def test_inline_script_has_valid_javascript_syntax(self):
        import tempfile
        text = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = text.split("<script>", 1)[1].split("</script>", 1)[0]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "explorer.js"
            path.write_text(script, encoding="utf-8")
            subprocess.run(["node", "--check", str(path)], check=True, capture_output=True)
