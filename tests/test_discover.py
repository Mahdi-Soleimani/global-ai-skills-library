import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from discover import discover_target, enumerate_paths, pending_queue

COMMIT = "a" * 40
TREE = "b" * 40
BLOB = "c" * 40


def entry(path, mode="100644"):
    return {"path": path, "mode": mode, "sha": BLOB, "type": "blob", "size": 100}


def sample_tree(*entries):
    return {"sha": TREE, "truncated": False, "tree": entries}


class DiscoveryTests(unittest.TestCase):
    def test_commit_tree_and_blob_are_distinct(self):
        calls = []
        def request(endpoint):
            calls.append(endpoint)
            if endpoint == "/repos/Org/Repo":
                return {"full_name": "Org/Repo", "id": 1, "owner": {"login": "Org"},
                        "private": False, "default_branch": "main", "license": {"spdx_id": "MIT"}}
            if endpoint == "/repos/Org/Repo/commits/main":
                return {"sha": COMMIT, "commit": {"tree": {"sha": TREE}}}
            if endpoint == "/repos/Org/Repo/git/trees/" + TREE + "?recursive=1":
                return sample_tree(entry("skills/a/SKILL.md"))
            raise AssertionError(endpoint)
        result = discover_target({"repository": "Org/Repo", "research_leads": ["A"]}, request)
        self.assertEqual(result["commit_sha"], COMMIT)
        self.assertEqual(result["tree_sha"], TREE)
        self.assertEqual(result["paths"][0]["blob_sha"], BLOB)
        self.assertEqual(len(calls), 3)
        self.assertEqual(result["extraction_status"], "tree_enumerated_content_not_read")

    def test_incomplete_or_mismatched_tree_fails(self):
        for tree in ({"sha": TREE, "truncated": True, "tree": []},
                     {"sha": COMMIT, "truncated": False, "tree": []},
                     {"sha": TREE, "tree": []}):
            with self.assertRaises(ValueError):
                enumerate_paths(tree, TREE)

    def test_reject_unsafe_and_duplicate_paths(self):
        for entries in ((entry("../SKILL.md"),),
                        (entry("a/SKILL.md"), entry("a/SKILL.md"))):
            with self.assertRaises(ValueError):
                enumerate_paths(sample_tree(*entries), TREE)

    def test_fixture_symlink_and_regular_skill_classified_separately(self):
        rows = enumerate_paths(sample_tree(entry("tests/fixtures/a/SKILL.md"),
                                           entry("skills/link/SKILL.md", "120000"),
                                           entry("skills/a/SKILL.md")), TREE)
        result = {r["path"]: r["classification"] for r in rows}
        self.assertEqual(result["tests/fixtures/a/SKILL.md"], "excluded_test_fixture")
        self.assertEqual(result["skills/link/SKILL.md"], "excluded_non_regular")
        self.assertEqual(result["skills/a/SKILL.md"], "skill_path_candidate")

    def test_queue_does_not_install_or_reuse_another_revision(self):
        record = {"repository": "Org/Repo", "commit_sha": COMMIT, "tree_sha": TREE,
                  "license_spdx": None, "research_leads": ["A"], "status": "verified_metadata_only",
                  "paths": enumerate_paths(sample_tree(entry("skills/a/SKILL.md"),
                                                        entry("tests/fixtures/a/SKILL.md")), TREE)}
        prior = {"repository": "org/repo", "source_skill_path": "skills/a/SKILL.md",
                 "commit_sha": TREE, "package_complete": True}
        queue = pending_queue([record], [prior])
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["status"], "pending_package_plan")
        self.assertEqual(queue[0]["install_status"], "not_approved")
        prior["commit_sha"] = COMMIT
        self.assertEqual(pending_queue([record], [prior])[0]["status"], "existing_complete_metadata")
        prior["package_complete"] = False
        self.assertEqual(pending_queue([record], [prior])[0]["status"], "pending_package_plan")

    def test_repository_redirect_requires_review(self):
        with self.assertRaises(ValueError):
            discover_target({"repository": "Org/Old"}, lambda _: {"full_name": "Org/New"})


if __name__ == "__main__":
    unittest.main()
