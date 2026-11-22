import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_registry import parse_frontmatter
from skill_evaluation import build_evaluations
from skill_search import build_index
from gasl_service import health, search, skill_content, skill_details, route


class GaslServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name in ("registry", "public-catalog", "config", "catalog", "private"):
            (self.root / name).mkdir()
        self.skill_md = (
            "---\nname: python-api-security\ndescription: Review Python APIs for security issues.\n"
            "compatibility: Codex\n---\n\n# Python API Security\n\n"
            "Inspect authentication, authorization, input validation, and secrets.\n"
        )
        self.package_path = "catalog/example__skills/python-api-security"
        package = self.root / self.package_path
        package.mkdir(parents=True)
        (package / "SKILL.md").write_text(self.skill_md, encoding="utf-8")
        fixture_bytes = (package / "SKILL.md").read_bytes()
        blob_sha = hashlib.sha1(b"blob " + str(len(fixture_bytes)).encode("ascii") + b"\0" + fixture_bytes).hexdigest()
        record = {
            "source_record_id": "GASL-SRC-service-test",
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
            "security_status": "no_obvious_static_flags_not_approved",
            "install_status": "not_installed",
            "snapshot_status": "verified_commit_pinned",
            "research_leads": ["EN-675"],
            "ownership": "third_party",
            "gasl_claims_exclusive_ownership": False,
        }
        (self.root / "registry" / "source-catalog.json").write_text(
            json.dumps({"records": [record]}), encoding="utf-8")
        local_record = {
            "repository": "example/skills",
            "source_skill_path": "skills/python-api-security/SKILL.md",
            "commit_sha": "a" * 40,
            "skill_name": "python-api-security",
            "description": "Review Python APIs for security issues.",
            "package_path": self.package_path,
            "package_content_present": True,
            "package_type": "skill_candidate",
            "compatibility": "Codex",
            "security_status": "no_obvious_static_flags_not_approved",
        }
        (self.root / "registry" / "skills.json").write_text(
            json.dumps({"records": [local_record]}), encoding="utf-8")
        (self.root / "public-catalog" / "index.json").write_text(
            '{"packages":{}}', encoding="utf-8")
        (self.root / "config" / "taxonomy.json").write_text(
            json.dumps({"domains": [{"id": "security", "label": "Security",
                                    "keywords": ["security", "api", "امنیت"]}]}),
            encoding="utf-8")
        build_evaluations(self.root)
        build_index(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_health_reports_catalog_and_truthful_search_mode(self):
        result = health(self.root)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["source_record_count"], 1)
        self.assertFalse(result["semantic_search_enabled"])

    def test_search_uses_shared_core(self):
        result = search("python api security", root=self.root)
        self.assertEqual(result["search_mode"], "lexical_with_curated_cross_language_expansion")
        self.assertEqual(result["results"][0]["source_record_id"], "GASL-SRC-service-test")

    def test_details_preserve_source_and_evidence(self):
        result = skill_details("GASL-SRC-service-test", root=self.root)
        self.assertEqual(result["commit_sha"], "a" * 40)
        self.assertEqual(result["repository"], "example/skills")
        self.assertFalse(result["installation_allowed"])
        self.assertFalse(result["execution_allowed"])

    def test_content_is_loaded_from_local_package_and_marked_untrusted(self):
        result = skill_content("GASL-SRC-service-test", root=self.root)
        self.assertIn("# Python API Security", result["content"])
        self.assertEqual(result["content_source"], "local_package")
        self.assertTrue(result["untrusted_content"])
        self.assertFalse(result["executed"])

    def test_modified_local_skill_is_blocked(self):
        (self.root / self.package_path / "SKILL.md").write_bytes(b"tampered")
        with self.assertRaisesRegex(RuntimeError, "Git blob SHA mismatch"):
            skill_content("GASL-SRC-service-test", root=self.root)

    def test_remote_integrity_mismatch_is_rejected_before_caching(self):
        from gasl_service import verify_skill_blob
        with self.assertRaisesRegex(RuntimeError, "Git blob SHA mismatch"):
            verify_skill_blob(b"wrong", {"skill_md_blob_sha": "a" * 40})
        with self.assertRaisesRegex(RuntimeError, "Missing valid Git blob SHA"):
            verify_skill_blob(b"anything", {})

    def test_content_limit_is_enforced(self):
        result = skill_content("GASL-SRC-service-test", max_chars=20, root=self.root)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["content"]), 20)

    def test_unknown_skill_is_not_found(self):
        with self.assertRaises(KeyError):
            skill_details("GASL-SRC-missing", root=self.root)

    def test_remote_content_fetch_uses_exact_pinned_raw_github_url_and_private_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("registry", "public-catalog", "config", "private"):
                (root / name).mkdir()
            fixture_bytes = b"\xef\xbb\xbf# Remote Skill\r\nDo not execute this content.\r\n"
            blob_sha = hashlib.sha1(b"blob " + str(len(fixture_bytes)).encode("ascii") + b"\0" + fixture_bytes).hexdigest()
            record = {
                "source_record_id": "GASL-SRC-remote-test",
                "skill_name": "remote-skill",
                "description": "A remote test skill.",
                "repository": "example/remote-skills",
                "repository_owner": "example",
                "source_path": "skills/remote-skill/SKILL.md",
                "source_url": "https://github.com/example/remote-skills/blob/" + "c" * 40 + "/skills/remote-skill/SKILL.md",
                "commit_sha": "c" * 40,
                "skill_md_blob_sha": blob_sha,
                "license_spdx": "MIT",
                "content_status": "not_downloaded_reference_record",
                "security_status": "not_scanned",
                "install_status": "not_installed",
                "snapshot_status": "verified_commit_pinned",
                "research_leads": ["EN-675"],
                "ownership": "third_party",
                "gasl_claims_exclusive_ownership": False,
            }
            (root / "registry" / "source-catalog.json").write_text(
                json.dumps({"records": [record]}), encoding="utf-8")
            (root / "registry" / "skills.json").write_text('{"records":[]}', encoding="utf-8")
            (root / "public-catalog" / "index.json").write_text('{"packages":{}}', encoding="utf-8")
            (root / "config" / "taxonomy.json").write_text('{"domains":[]}', encoding="utf-8")
            build_evaluations(root)
            build_index(root)

            class FakeResponse:
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    return False
                def geturl(self):
                    return "https://raw.githubusercontent.com/example/remote-skills/" + "c" * 40 + "/skills/remote-skill/SKILL.md"
                def read(self, size):
                    return fixture_bytes

            with patch("gasl_service.open_pinned_url", return_value=FakeResponse()) as fetch:
                first = skill_content("GASL-SRC-remote-test", root=root)
                self.assertEqual(first["content_source"], "upstream_pinned_fetch")
                self.assertIn("raw.githubusercontent.com/example/remote-skills/" + "c" * 40, fetch.call_args.args[0].full_url)
                second = skill_content("GASL-SRC-remote-test", root=root)
                self.assertEqual(second["content_source"], "private_cache")
                self.assertEqual(fetch.call_count, 1)
                self.assertTrue(first["git_blob_verified"])
                self.assertEqual(first["content_sha256"], hashlib.sha256(fixture_bytes).hexdigest())
                self.assertEqual(first["content_sha256"], second["content_sha256"])
                self.assertEqual(first["content_bytes"], len(fixture_bytes))
                cache_file = next((root / "private" / "skill-cache").glob("*.md"))
                self.assertEqual(cache_file.read_bytes(), fixture_bytes)
                cache_file.write_bytes(b"tampered")
                with self.assertRaisesRegex(RuntimeError, "Git blob SHA mismatch"):
                    skill_content("GASL-SRC-remote-test", root=root, fetch_remote=False)
            self.assertTrue(list((root / "private" / "skill-cache").glob("*.md")))

    def test_single_backslash_in_source_path_is_rejected(self):
        from gasl_service import _pinned_raw_url
        record = {
            "repository": "example/repo",
            "commit_sha": "a" * 40,
            "source_path": r"skills\\private/SKILL.md",
        }
        with self.assertRaises(ValueError):
            _pinned_raw_url(record)

    def test_unpinned_or_unsafe_source_path_is_not_fetched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("registry", "public-catalog", "config", "private"):
                (root / name).mkdir()
            record = {
                "source_record_id": "GASL-SRC-unsafe-test",
                "skill_name": "unsafe",
                "repository": "example/unsafe",
                "source_path": "../outside/SKILL.md",
                "source_url": "https://github.com/example/unsafe",
                "commit_sha": "e" * 40,
                "content_status": "not_downloaded_reference_record",
                "security_status": "not_scanned",
                "install_status": "not_installed",
                "research_leads": [],
                "ownership": "third_party",
                "gasl_claims_exclusive_ownership": False,
            }
            (root / "registry" / "source-catalog.json").write_text(
                json.dumps({"records": [record]}), encoding="utf-8")
            (root / "registry" / "skills.json").write_text('{"records":[]}', encoding="utf-8")
            (root / "public-catalog" / "index.json").write_text('{"packages":{}}', encoding="utf-8")
            (root / "config" / "taxonomy.json").write_text('{"domains":[]}', encoding="utf-8")
            build_evaluations(root)
            build_index(root)
            with patch("gasl_service.open_pinned_url") as fetch:
                with self.assertRaises(ValueError):
                    skill_content("GASL-SRC-unsafe-test", root=root)
                fetch.assert_not_called()

    def test_route_does_not_install_or_execute(self):
        result = route("python api security", root=self.root)
        self.assertFalse(result["installation_performed"])
        self.assertFalse(result["execution_performed"])


    def test_health_reports_answerability_policy_is_not_calibrated(self):
        result = health(root=self.root)
        self.assertEqual(result["answerability_policy_status"], "experimental_heuristic_not_calibrated")
        self.assertEqual(result["answerability_policy_version"], "0.2.0-experimental")
        self.assertFalse(result["answerability_decisions_calibrated"])



if __name__ == "__main__":
    unittest.main()
