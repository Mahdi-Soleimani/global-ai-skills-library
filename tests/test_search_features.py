import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from search_features import refresh, fetch_feature, load_features, vocabulary, FeatureSizeLimitError
from queue_ingest import git_blob
from skill_search import search_skills


class SearchFeaturesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "registry").mkdir()
        (self.root / "config").mkdir()
        (self.root / "config/taxonomy.json").write_text(json.dumps({
            "domains": [],
            "query_expansions": [
                {"terms":["وردپرس"],"expand":["wordpress"]},
                {"terms":["plugin"],"expand":["plugin"]},
                {"terms":["development"],"expand":["development"]}
            ]
        }))
        self.raw = b"---\nname: content-guide\ndescription: WordPress plugin development. A unique private sentence.\n---\n# Unrelated body\n"
        self.record = {
            "source_record_id":"s1","repository":"example/skills","source_path":"skills/content-guide/SKILL.md",
            "skill_name":"content-guide","commit_sha":"a"*40,"skill_md_blob_sha":git_blob(self.raw),
            "license_spdx":"NOASSERTION","snapshot_status":"verified_commit_pinned"
        }
        (self.root / "registry/source-catalog.json").write_text(json.dumps({"records":[self.record]}))

    def test_verified_terms_only_and_incremental_reuse(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = self.raw
        with patch("search_features.open_pinned_url",return_value=response) as fetch:
            result = refresh(self.root, limit=1, workers=1)
            self.assertEqual(result["new_verified"], 1)
            again = refresh(self.root, limit=1, workers=1)
            self.assertEqual(again["attempted"], 0)
            self.assertEqual(fetch.call_count,1)
        data = (self.root/"registry/search-features.json").read_text()
        self.assertNotIn("A unique private sentence",data)
        self.assertNotIn("Unrelated body",data)
        self.assertNotIn('"description"',data)
        self.assertEqual(load_features(self.root,[self.record])["s1"]["terms"],
                         ["development","plugin","wordpress"])
        self.assertEqual(search_skills("توسعه وردپرس",root=self.root)[0]["source_record_id"],"s1")

    def test_wrong_blob_is_never_indexed(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"tampered"
        with patch("search_features.open_pinned_url",return_value=response):
            result = refresh(self.root, limit=1, workers=1)
        self.assertEqual(result["failed"],1)
        self.assertEqual(result["verified_records"],0)

    def test_changed_pin_and_unknown_term_ignore_old_features(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = self.raw
        with patch("search_features.open_pinned_url",return_value=response):
            refresh(self.root, limit=1, workers=1)
        self.assertEqual(load_features(self.root,[{**self.record,"commit_sha":"c"*40}]),{})
        path = self.root/"registry/search-features.json"
        value = json.loads(path.read_text()); value["records"]["s1"]["terms"].append("invented")
        path.write_text(json.dumps(value))
        self.assertEqual(load_features(self.root,[self.record]),{})

    def test_unchanged_blob_across_commit_reuses_verified_terms(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = self.raw
        with patch("search_features.open_pinned_url",return_value=response) as fetch:
            refresh(self.root, limit=1, workers=1)
            new = {**self.record, "source_record_id":"s2", "commit_sha":"c"*40}
            (self.root/"registry/source-catalog.json").write_text(json.dumps({"records":[new]}))
            result = refresh(self.root, limit=1, workers=1)
            self.assertEqual(result["reused_unchanged_blobs"],1)
            self.assertEqual(result["attempted"],0)
            self.assertEqual(fetch.call_count,1)
        row=load_features(self.root,[new])["s2"]
        self.assertEqual(row["verified_at_commit"],"a"*40)
        self.assertEqual(row["commit_sha"],"c"*40)

    def test_failed_record_does_not_starve_unattempted_and_can_retry(self):
        new = {**self.record, "source_record_id":"s2", "source_path":"skills/other/SKILL.md"}
        (self.root/"registry/source-catalog.json").write_text(json.dumps({"records":[self.record,new]}))
        calls = []
        def fake(r, terms):
            calls.append(r["source_record_id"])
            if calls == ["s1"]:
                raise OSError("temporary network error")
            return {"repository":r["repository"],"source_path":r["source_path"],
                    "commit_sha":r["commit_sha"],"verified_at_commit":r["commit_sha"],
                    "git_blob_sha":r["skill_md_blob_sha"],"terms":["wordpress"]}
        one = refresh(self.root,limit=1,workers=1,fetch=fake)
        self.assertEqual(one["pending_failure_records"],1)
        two = refresh(self.root,limit=1,workers=1,fetch=fake)
        self.assertEqual(two["verified_records"],1)
        three = refresh(self.root,limit=1,workers=1,fetch=fake)
        self.assertEqual(three["verified_records"],2)
        self.assertEqual(three["pending_failure_records"],0)
        self.assertEqual(calls,["s1","s2","s1"])


    def test_oversize_policy_failure_is_retained_without_retries(self):
        calls = []
        def too_large(record, terms):
            calls.append(record["source_record_id"])
            raise FeatureSizeLimitError("SKILL.md exceeds byte limit")

        first = refresh(self.root, limit=1, workers=1, fetch=too_large)
        self.assertEqual(first["failed"], 1)
        self.assertEqual(first["permanent_exclusions"], 1)
        saved = json.loads((self.root / "registry/search-features.json").read_text())
        self.assertEqual(saved["failures"]["s1"]["error_type"], "FeatureSizeLimitError")

        second = refresh(self.root, limit=1, workers=1, fetch=too_large)
        self.assertEqual(second["attempted"], 0)
        self.assertEqual(second["permanent_exclusions"], 1)
        self.assertEqual(second["pending_failure_records"], 1)
        self.assertEqual(calls, ["s1"])
