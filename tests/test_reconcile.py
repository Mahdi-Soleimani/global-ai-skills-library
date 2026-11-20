import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from reconcile import repository_crosswalk, path_crosswalk, duplicate_candidates, downloaded_crosswalk


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.manifests = {
            "A": {"repositories": [{"source_id": "A-1", "report_id": "A", "repo_full_name": "Org/Old"}]},
            "B": {"repositories": [{"source_id": "B-1", "report_id": "B", "repo_full_name": "Org/New"}]},
        }
        self.verification = {
            "org/old": {"status": "verified", "canonical_repo_name": "Org/New", "redirected_alias": True},
            "org/new": {"status": "verified", "repo_full_name": "Org/New",
                        "skill_paths": ["skills/real/SKILL.md", "evals/fixtures/example/SKILL.md"],
                        "skill_file_count": 2, "owner_login": "Org", "tree_sha": "tree-ref"},
        }

    def test_alias_preserves_both_independent_sources(self):
        rows, repos = repository_crosswalk(self.manifests, self.verification)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(repos), 1)
        self.assertEqual(rows[0]["relationship"], "redirected_repository_alias")
        self.assertEqual({x["source_id"] for x in rows}, {"A-1", "B-1"})
        paths = path_crosswalk(rows, repos)
        self.assertEqual(len(paths), 2)
        self.assertTrue(all(x["source_reference_ids"] == "A-1;B-1" for x in paths))

    def test_fixture_and_unpinned_path_are_not_promoted(self):
        rows, repos = repository_crosswalk(self.manifests, self.verification)
        paths = path_crosswalk(rows, repos)
        self.assertEqual(sum(p["package_type"] == "test_fixture" for p in paths), 1)
        self.assertTrue(all(p["commit_sha"] == "" for p in paths))
        self.assertTrue(all(p["snapshot_status"] == "tree_ref_recorded_commit_unverified" for p in paths))
        self.assertTrue(all(p["scope"] == "repository_reference_only_not_source_skill_record" for p in paths))

    def test_missing_alias_target_is_rejected(self):
        del self.verification["org/new"]
        with self.assertRaises(ValueError):
            repository_crosswalk(self.manifests, self.verification)

    def test_duplicate_path_is_rejected(self):
        self.verification["org/new"]["skill_paths"] *= 2
        self.verification["org/new"]["skill_file_count"] = 4
        rows, repos = repository_crosswalk(self.manifests, self.verification)
        with self.assertRaises(ValueError):
            path_crosswalk(rows, repos)

    def test_exact_normalized_and_name_conflict_are_candidates_only(self):
        records = [
            {"skill_id": "a", "skill_name": "same", "skill_md_sha256_raw": "h1", "skill_md_sha256_normalized": "n1"},
            {"skill_id": "b", "skill_name": "same", "skill_md_sha256_raw": "h1", "skill_md_sha256_normalized": "n1"},
            {"skill_id": "c", "skill_name": "same", "skill_md_sha256_raw": "h2", "skill_md_sha256_normalized": "n2"},
            {"skill_id": "d", "skill_name": "other", "skill_md_sha256_raw": "h3", "skill_md_sha256_normalized": "n1"},
        ]
        relations = duplicate_candidates(records)
        self.assertEqual({r["relationship"] for r in relations},
                         {"exact_skill_md_digest", "normalized_skill_md_digest", "same_name"})
        self.assertTrue(all(r["decision"] == "candidate_only_no_merge" for r in relations))
        self.assertEqual(len(records), 4)

    def test_different_commit_versions_are_not_merged(self):
        records = [{"skill_id": x, "repository": "org/repo", "source_skill_path": "skills/a/SKILL.md",
                    "commit_sha": x} for x in ("c1", "c2")]
        relations = duplicate_candidates(records)
        self.assertEqual(len(relations), 1)
        self.assertEqual(relations[0]["relationship"], "same_path_different_commits")
        self.assertEqual(relations[0]["decision"], "candidate_only_no_merge")

    def test_downloaded_path_match_does_not_claim_same_commit(self):
        records = [{"skill_id": "a", "repository": "org/new", "source_skill_path": "skills/real/SKILL.md", "commit_sha": "c1"}]
        rows, repos = repository_crosswalk(self.manifests, self.verification)
        paths = path_crosswalk(rows, repos)
        self.assertEqual(downloaded_crosswalk(records, paths)[0]["snapshot_match"], "path_match_only_commit_unconfirmed")
        self.verification["org/new"]["commit_sha"] = "c2"
        paths = path_crosswalk(rows, repos)
        self.assertEqual(downloaded_crosswalk(records, paths)[0]["snapshot_match"], "different_recorded_commit")
        self.verification["org/new"]["commit_sha"] = "c1"
        paths = path_crosswalk(rows, repos)
        self.assertEqual(downloaded_crosswalk(records, paths)[0]["snapshot_match"], "same_recorded_commit")

    def test_unverified_source_is_preserved_without_claiming_canonical(self):
        rows, repos = repository_crosswalk({"A": self.manifests["A"]}, {})
        self.assertEqual(rows[0]["relationship"], "unverified_reference")
        self.assertEqual(rows[0]["canonical_repository"], "")
        self.assertEqual(repos, {})


if __name__ == "__main__":
    unittest.main()
