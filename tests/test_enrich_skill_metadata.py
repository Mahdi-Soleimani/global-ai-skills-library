import sys
import hashlib
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from enrich_skill_metadata import (
    MAX_SKILL_BYTES, OversizedSkillError, fetch_pinned_bytes, fetch_record,
    round_robin_by_repository, select_pending_records,
)


class MetadataEnrichmentOrderingTests(unittest.TestCase):
    def test_batches_are_interleaved_across_repositories(self):
        records = [
            {"repository": "alpha/repo", "source_record_id": "a1"},
            {"repository": "alpha/repo", "source_record_id": "a2"},
            {"repository": "alpha/repo", "source_record_id": "a3"},
            {"repository": "beta/repo", "source_record_id": "b1"},
            {"repository": "beta/repo", "source_record_id": "b2"},
            {"repository": "gamma/repo", "source_record_id": "c1"},
        ]
        result = round_robin_by_repository(records)
        self.assertEqual(
            [item["source_record_id"] for item in result],
            ["a1", "b1", "c1", "a2", "b2", "a3"],
        )

    def test_retry_errors_only_selects_cached_failures(self):
        records = [
            {"repository": "alpha/repo", "source_record_id": "ok", "source_path": "skills/ok/SKILL.md", "commit_sha": "a"},
            {"repository": "beta/repo", "source_record_id": "error", "source_path": "skills/error/SKILL.md", "commit_sha": "b"},
            {"repository": "gamma/repo", "source_record_id": "new", "source_path": "skills/new/SKILL.md", "commit_sha": "c"},
        ]
        cached = {
            "ok": {"repository": "alpha/repo", "source_path": "skills/ok/SKILL.md", "commit_sha": "a", "fetch_status": "ok"},
            "error": {"repository": "beta/repo", "source_path": "skills/error/SKILL.md", "commit_sha": "b", "fetch_status": "error"},
        }
        pending, hits, skipped = select_pending_records(
            records, cached, retry_errors=True
        )
        self.assertEqual([x["source_record_id"] for x in pending], ["error"])
        self.assertEqual(hits, 1)
        self.assertEqual(skipped, 1)

    def test_transient_network_error_is_retried(self):
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def geturl(self):
                return "https://raw.githubusercontent.com/example/repo/" + "a" * 40 + "/SKILL.md"
            def read(self, size):
                return b"# Skill\\n"

        with patch("enrich_skill_metadata.open_pinned_url",
                   side_effect=[urllib.error.URLError("temporary TLS EOF"), urllib.error.URLError("temporary TLS EOF"), FakeResponse()]) as fetch:
            with patch("enrich_skill_metadata.time.sleep"):
                result = fetch_pinned_bytes(
                    "https://raw.githubusercontent.com/example/repo/" + "a" * 40 + "/SKILL.md"
                )
        self.assertEqual(result, b"# Skill\\n")
        self.assertEqual(fetch.call_count, 3)

    def test_oversized_skill_is_rejected_by_fetch_size_limit(self):
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def geturl(self):
                return "https://raw.githubusercontent.com/example/repo/" + "a" * 40 + "/SKILL.md"
            def read(self, size):
                self.requested_size = size
                return b"x" * size

        with patch("enrich_skill_metadata.open_pinned_url", return_value=FakeResponse()):
            with self.assertRaises(OversizedSkillError):
                fetch_pinned_bytes(
                    "https://raw.githubusercontent.com/example/repo/" + "a" * 40 + "/SKILL.md"
                )

    def test_skipped_oversized_record_is_not_retried_as_a_network_error(self):
        records = [{
            "repository": "example/repo", "source_record_id": "large",
            "source_path": "skills/large/SKILL.md", "commit_sha": "a",
        }]
        cached = {
            "large": {
                "repository": "example/repo", "source_path": "skills/large/SKILL.md",
                "commit_sha": "a", "fetch_status": "skipped",
                "skip_reason": "safety_size_limit",
            }
        }
        pending, hits, skipped = select_pending_records(records, cached)
        self.assertEqual(pending, [])
        self.assertEqual(hits, 1)
        self.assertEqual(skipped, 0)

    def test_invalid_utf8_skill_content_is_rejected(self):
        record = {
            "source_record_id": "bad-utf8",
            "repository": "example/repo",
            "source_path": "skills/bad/SKILL.md",
            "commit_sha": "a" * 40,
            "skill_name": "bad-utf8",
            "skill_md_blob_sha": hashlib.sha1(b"blob 2\0" + bytes([255,254])).hexdigest(),
        }
        with patch("enrich_skill_metadata._pinned_raw_url", return_value="https://raw.githubusercontent.com/example/repo/" + "a" * 40 + "/skills/bad/SKILL.md"):
            with patch("enrich_skill_metadata.fetch_pinned_bytes", return_value=bytes([255, 254])):
                with self.assertRaisesRegex(RuntimeError, "not valid UTF-8"):
                    fetch_record(record, Path("/tmp/gasl-test-root"))

    def test_enrichment_rejects_content_with_mismatched_blob_hash(self):
        record = {"repository": "example/repo", "source_path": "skills/test/SKILL.md",
                  "commit_sha": "a" * 40, "skill_md_blob_sha": "b" * 40}
        with patch("enrich_skill_metadata.fetch_pinned_bytes", return_value=b"wrong"):
            with self.assertRaisesRegex(RuntimeError, "Git blob SHA mismatch"):
                fetch_record(record, Path("/tmp/gasl-test-root"))

    def test_enrichment_records_verified_blob(self):
        raw = b"# A Skill"
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        record = {"repository": "example/repo", "source_path": "skills/test/SKILL.md",
                  "commit_sha": "a" * 40, "skill_md_blob_sha": blob}
        with patch("enrich_skill_metadata.fetch_pinned_bytes", return_value=raw):
            result = fetch_record(record, Path("/tmp/gasl-test-root"))
        self.assertTrue(result["git_blob_verified"])
        self.assertEqual(result["git_blob_sha"], blob)

    def test_cached_metadata_must_match_repository_path_and_commit(self):
        records = [
            {"repository": "alpha/repo", "source_record_id": "same-id", "source_path": "skills/a/SKILL.md", "commit_sha": "a"},
        ]
        cached = {
            "same-id": {
                "repository": "alpha/repo",
                "source_path": "skills/old/SKILL.md",
                "commit_sha": "a",
                "fetch_status": "ok",
            }
        }
        pending, hits, skipped = select_pending_records(records, cached)
        self.assertEqual(len(pending), 1)
        self.assertEqual(hits, 0)
        self.assertEqual(skipped, 0)

    def test_ordering_preserves_all_records(self):
        records = [
            {"repository": "alpha/repo", "source_record_id": "a1"},
            {"repository": "alpha/repo", "source_record_id": "a2"},
            {"repository": "beta/repo", "source_record_id": "b1"},
        ]
        result = round_robin_by_repository(records)
        self.assertEqual(
            sorted(item["source_record_id"] for item in result),
            ["a1", "a2", "b1"],
        )


if __name__ == "__main__":
    unittest.main()
