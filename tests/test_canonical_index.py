"""Recorded identity evidence, never canonical package or security approval."""
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from canonical_index import build_index, inspect, lookup, compare, comparison_evidence


def record(repo="org/repo", path="skills/a/SKILL.md", commit="a"*40, blob="b"*40):
    seed = "\0".join((repo.casefold(), path, commit))
    return {"source_record_id": "GASL-SRC-" + hashlib.sha256(seed.encode()).hexdigest()[:20],
            "repository": repo, "source_path": path, "commit_sha": commit,
            "skill_md_blob_sha": blob}


class CanonicalIndexTests(unittest.TestCase):
    def test_equal_blobs_cross_repository_not_equivalence(self):
        rows = [record(), record(repo="another/repo")]
        result = build_index(rows)
        self.assertEqual(result["recorded_blob_group_count"], 1)
        self.assertEqual(result["recorded_blob_group_member_count"], 2)
        self.assertFalse(result["package_equivalence_established"])
        self.assertFalse(result["source_records_merged"])
        self.assertFalse(result["independent_content_verification_performed"])

    def test_revision_states_are_distinct(self):
        rows = [record(), record(commit="c"*40),
                record(path="b/SKILL.md"), record(path="b/SKILL.md",commit="c"*40,blob="d"*40),
                record(path="c/SKILL.md"), record(path="c/SKILL.md",commit="c"*40,blob=None)]
        result = build_index(rows)
        self.assertEqual({x["source_path"]: x["blob_comparison"] for x in result["path_revision_groups"]},
                         {"skills/a/SKILL.md":"same_recorded_blob", "b/SKILL.md":"different_recorded_blobs",
                          "c/SKILL.md":"incomplete_blob_evidence"})
        self.assertFalse(result["ancestry_established"])
        self.assertEqual(result["records_without_blob_evidence"], [rows[-1]["source_record_id"]])

    def test_missing_blobs_never_form_equal_group(self):
        result = build_index([record(blob=None), record(repo="other/repo",blob=None)])
        self.assertEqual(result["recorded_blob_group_count"], 0)
        self.assertEqual(len(result["records_without_blob_evidence"]), 2)

    def test_order_independent_and_nonmutating(self):
        rows = [record(), record(repo="other/repo"), record(commit="c"*40)]
        before = json.dumps(rows)
        self.assertEqual(build_index(rows), build_index(list(reversed(rows))))
        self.assertEqual(json.dumps(rows), before)

    def test_duplicate_immutable_identity_refused(self):
        with self.assertRaisesRegex(ValueError, "Duplicate immutable"):
            build_index([record(), record(repo="ORG/Repo")])

    def test_tampered_id_and_invalid_pins_refused(self):
        for change in ({"source_record_id":"forged"}, {"commit_sha":"bad"},
                       {"skill_md_blob_sha":"bad"}, {"source_path":"../SKILL.md"},
                       {"repository":"../repo"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                build_index([dict(record(), **change)])

    def pair_fixture(self, rows):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        path = root/"registry/source-catalog.json"
        path.parent.mkdir()
        path.write_bytes(json.dumps({"schema_version":"1.0.0","records":rows}).encode())
        return root, path

    def test_lookup_and_offline_pair_never_fetch(self):
        rows = [record(), record(repo="other/repo"), record(commit="c"*40, blob=None),
                record(repo="unique/repo", blob="f"*40)]
        root, path = self.pair_fixture(rows)
        before = path.read_bytes()
        with patch("safe_http.open_pinned_url", side_effect=AssertionError("No network")):
            info = lookup(rows[0]["source_record_id"], root=root)
            self.assertEqual(len(info["related_groups"]), 2)
            self.assertEqual(lookup(rows[3]["source_record_id"],root=root)["related_groups"], [])
            pair = compare([r["source_record_id"] for r in rows[:2]], root=root)
            self.assertEqual(pair["blob_comparison"], "same_recorded_blob")
            self.assertIsNone(pair["skill_md_bytes_equal"])
            with self.assertRaisesRegex(ValueError, "Unknown exact"):
                lookup("missing", root=root)
        self.assertEqual(before, path.read_bytes())

    def test_online_requires_distinct_related_records_and_valid_pins(self):
        rows = [record(), record(commit="c"*40,blob=None), record(repo="unrelated/repo",blob="f"*40)]
        root, _ = self.pair_fixture(rows)
        with patch("safe_http.open_pinned_url", side_effect=AssertionError("No network")):
            for pair in ([rows[0],rows[0]], [rows[0],rows[1]], [rows[0],rows[2]]):
                with self.assertRaises(ValueError):
                    compare([r["source_record_id"] for r in pair], root=root, verify_online=True)

    def test_online_two_independent_pins_verified_without_cache(self):
        raw = b"# INERT fixture\n"
        blob = hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
        rows = [record(blob=blob), record(repo="other/repo",blob=blob)]
        root, path = self.pair_fixture(rows)
        before = path.read_bytes()
        def response(request, timeout):
            result = MagicMock()
            result.__enter__.return_value = result
            result.geturl.return_value = request.full_url
            result.read.return_value = raw
            return result
        with patch("safe_http.open_pinned_url", side_effect=response) as opener:
            report = compare([r["source_record_id"] for r in rows],root=root,verify_online=True)
        self.assertEqual(opener.call_count, 2)
        self.assertTrue(report["skill_md_bytes_equal"])
        self.assertTrue(report["upstream_blob_verification_performed"])
        self.assertFalse(report["package_equivalence_established"])
        self.assertFalse(report["ancestry_established"])
        self.assertEqual(report["verified_sources"][0]["sha256"],hashlib.sha256(raw).hexdigest())
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(list(root.rglob("*")),[path.parent,path])

    def test_online_rejects_wrong_blob_redirect_oversize_and_drift(self):
        raw = b"# INERT fixture\n"
        blob = hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
        rows = [record(blob=blob), record(repo="other/repo",blob=blob)]
        root,path = self.pair_fixture(rows)
        ids = [r["source_record_id"] for r in rows]
        for mode in ("wrong_blob","redirect","oversize","drift"):
            with self.subTest(mode=mode):
                def response(request,timeout):
                    result = MagicMock()
                    result.__enter__.return_value = result
                    result.geturl.return_value = ("https://raw.githubusercontent.com/other" if mode=="redirect" else request.full_url)
                    result.read.return_value = (b"modified" if mode=="wrong_blob" else b"x"*(256*1024+1) if mode=="oversize" else raw)
                    if mode=="drift":
                        path.write_bytes(path.read_bytes()+b" ")
                    return result
                with patch("safe_http.open_pinned_url",side_effect=response), self.assertRaises((ValueError,RuntimeError)):
                    compare(ids,root=root,verify_online=True)
                self.assertFalse((root/"private").exists())

    def test_cache_exact_digest_and_copy_isolation(self):
        import canonical_index
        rows = [record(), record(repo="other/repo")]
        root, path = self.pair_fixture(rows)
        sid = rows[0]["source_record_id"]
        with patch("canonical_index.build_index", wraps=canonical_index.build_index) as build:
            # Force a fresh input digest independent of other fixtures.
            path.write_bytes(path.read_bytes()+b"  ")
            first = lookup(sid, root=root)
            first["related_groups"][0]["members"].clear()
            self.assertEqual(len(lookup(sid,root=root)["related_groups"][0]["members"]),2)
            snapshot = inspect(root)
            snapshot["recorded_blob_groups"].clear()
            self.assertEqual(inspect(root)["recorded_blob_group_count"],1)
            self.assertEqual(build.call_count,1)
            import os
            stat=path.stat()
            raw=path.read_bytes()
            changed=raw.replace(b"b"*40,b"c"*40,1)
            self.assertEqual(len(raw),len(changed))
            path.write_bytes(changed)
            os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns))
            self.assertEqual(lookup(sid,root=root)["related_groups"],[])
            self.assertEqual(build.call_count,2)
            path.write_bytes(b"invalid")
            with self.assertRaises(ValueError):
                lookup(sid,root=root)

    def test_comparison_pairs_all_three_and_identity_mismatch(self):
        rows=[record(),record(repo="other/repo"),record(commit="c"*40,blob=None)]
        root,_=self.pair_fixture(rows)
        result=comparison_evidence(rows,root=root)
        self.assertEqual(len(result["pairs"]),3)
        self.assertEqual([p["blob_comparison"] for p in result["pairs"]],
                         ["same_recorded_blob","incomplete_blob_evidence","incomplete_blob_evidence"])
        self.assertTrue(result["pairs"][1]["same_repository_path"])
        self.assertFalse(result["package_equivalence_established"])
        with self.assertRaises(ValueError):
            comparison_evidence([dict(rows[0],commit_sha="d"*40),rows[1]],root=root)

    def test_readonly_exact_catalog_digest_and_duplicate_json_refusal(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            path = root/"registry/source-catalog.json"
            path.parent.mkdir()
            raw = json.dumps({"schema_version":"1.0.0","records":[record()]}).encode()
            path.write_bytes(raw)
            self.assertEqual(inspect(root)["catalog_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(list(root.rglob("*")), [path.parent, path])
            path.write_bytes(b'{"schema_version":"1.0.0","records":[],"records":[]}')
            with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
                inspect(root)


if __name__ == "__main__":
    unittest.main()
