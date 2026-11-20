import sys
import unittest
import json
import tempfile
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from discover import discover_target, enumerate_paths, pending_queue, run

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

    def test_discovery_preserves_repository_license_and_exact_license_file(self):
        def request(endpoint):
            if endpoint == "/repos/Org/Repo":
                return {"full_name":"Org/Repo","id":7,"owner":{"login":"Org"},
                        "private":False,"default_branch":"main",
                        "html_url":"https://github.com/Org/Repo",
                        "license":{"spdx_id":"Apache-2.0","name":"Apache License 2.0","key":"apache-2.0","url":"https://api.github.com/licenses/apache-2.0"}}
            if endpoint == "/repos/Org/Repo/commits/main":
                return {"sha":COMMIT,"commit":{"tree":{"sha":TREE}}}
            if endpoint == "/repos/Org/Repo/git/trees/"+TREE+"?recursive=1":
                return sample_tree(entry("LICENSE"),entry("skills/a/SKILL.md"))
            raise AssertionError(endpoint)
        record=discover_target({"repository":"Org/Repo","research_leads":["A"]},request)
        self.assertEqual(record["license_spdx"],"Apache-2.0")
        self.assertEqual(record["license_name"],"Apache License 2.0")
        self.assertEqual(record["license_files"][0]["path"],"LICENSE")
        queue=pending_queue([record],[])
        self.assertEqual(queue[0]["license_evidence_path"],"LICENSE")
        self.assertIn(COMMIT,queue[0]["source_url"])
        self.assertFalse(queue[0]["gasl_claims_exclusive_ownership"])

    def test_queue_detects_license_evidence_inside_skill_subtree(self):
        record={"repository":"Org/Repo","research_leads":["A"],"status":"verified_metadata_only",
                "commit_sha":COMMIT,"tree_sha":TREE,"license_spdx":"MIT","license_name":"MIT",
                "license_files":[{"path":"skills/demo/assets/LICENSE","blob_sha":BLOB}],
                "paths":[{"path":"skills/demo/SKILL.md","blob_sha":BLOB,"classification":"skill_path_candidate"}],
                "checked_at":"now"}
        row=pending_queue([record],[])[0]
        self.assertEqual(row["license_evidence_path"],"skills/demo/assets/LICENSE")
        self.assertEqual(row["license_evidence_paths"],["skills/demo/assets/LICENSE"])
        self.assertIn("MIT",row["license_spdx"])

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

    def test_run_works_on_clean_ci_checkout_and_publishes_tracked_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"config").mkdir(); (root/"registry").mkdir(); (root/"reconciliation").mkdir()
            (root/"config/discovery-targets.json").write_text(json.dumps({"targets":[
                {"repository":"Org/Repo","research_leads":["A"],"reason":"test"}
            ]}))
            record={"repository":"Org/Repo","research_leads":["A"],"status":"verified_metadata_only",
                    "commit_sha":COMMIT,"tree_sha":TREE,"license_spdx":"MIT","checked_at":"now",
                    "paths":[{"path":"skills/a/SKILL.md","blob_sha":BLOB,"classification":"skill_path_candidate"}]}
            with patch("discover.discover_target",return_value=record):
                summary=run(root,1,refresh=True)
            self.assertEqual(summary["verified_targets"],1)
            self.assertEqual(summary["baseline_source"],"none")
            self.assertEqual(summary["downloaded_registry_records"],0)
            tracked=json.loads((root/"registry/download-queue.json").read_text())
            local=json.loads((root/"registry/discovery/download-queue.json").read_text())
            self.assertEqual(tracked,local)
            self.assertEqual(tracked[0]["status"],"pending_package_plan")
            state=json.loads((root/"registry/discovery-state.json").read_text())
            self.assertEqual(state["repositories"]["org/repo"]["commit_sha"],COMMIT)
            self.assertIsNone(summary["repositories"][0]["new_paths_vs_prior_snapshot"])

    def test_run_preserves_baseline_when_a_target_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for folder in ("config","registry","reconciliation"): (root/folder).mkdir()
            (root/"config/discovery-targets.json").write_text(json.dumps({"targets":[
                {"repository":"Org/Repo","research_leads":["A"]},
                {"repository":"Org/Fail","research_leads":["B"]}
            ]}))
            (root/"registry/discovery-state.json").write_text(json.dumps({"repositories":{
                "org/repo":{"repository":"Org/Repo","commit_sha":"d"*40,"tree_sha":"e"*40,"skill_paths":["old/SKILL.md"]},
                "org/fail":{"repository":"Org/Fail","commit_sha":"f"*40,"tree_sha":"1"*40,"skill_paths":["keep/SKILL.md"]}
            }}))
            old_queue=[{"repository":"Org/Fail","skill_path":"skills/old/SKILL.md","commit_sha":"f"*40,
                        "tree_sha":"1"*40,"skill_md_blob_sha":"2"*40,"license_spdx":"MIT",
                        "research_leads":["B"],"status":"pending_package_plan","install_status":"not_approved"}]
            (root/"registry/download-queue.json").write_text(json.dumps(old_queue))
            fresh={"repository":"Org/Repo","research_leads":["A"],"status":"verified_metadata_only",
                   "commit_sha":COMMIT,"tree_sha":TREE,"license_spdx":"MIT","checked_at":"now",
                   "paths":[{"path":"new/SKILL.md","blob_sha":BLOB,"classification":"skill_path_candidate"}]}
            def fake(target):
                if target["repository"]=="Org/Fail": raise RuntimeError("rate limited")
                return fresh
            with patch("discover.discover_target",side_effect=fake):
                summary=run(root,2,refresh=True)
            self.assertEqual(summary["errors"],1)
            self.assertEqual(summary["repositories"][0]["new_paths_vs_prior_snapshot"],1)
            state=json.loads((root/"registry/discovery-state.json").read_text())["repositories"]
            self.assertEqual(state["org/fail"]["commit_sha"],"f"*40)
            self.assertEqual(state["org/repo"]["commit_sha"],COMMIT)
            queue=json.loads((root/"registry/download-queue.json").read_text())
            stale=[r for r in queue if r["repository"]=="Org/Fail"]
            self.assertEqual(len(stale),1)
            self.assertEqual(stale[0]["discovery_status"],"stale_fallback")
            self.assertEqual(summary["stale_fallback_records"],1)

    def test_refresh_bypasses_successful_local_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for folder in ("config","registry","reconciliation","registry/discovery"): (root/folder).mkdir(exist_ok=True)
            (root/"config/discovery-targets.json").write_text(json.dumps({"targets":[{"repository":"Org/Repo","research_leads":[]}]}))
            key=__import__("hashlib").sha256(b"org/repo").hexdigest()[:20]
            cached={"repository":"Org/Repo","status":"verified_metadata_only","commit_sha":COMMIT,
                    "tree_sha":TREE,"paths":[],"research_leads":[],"license_spdx":"MIT","checked_at":"old"}
            (root/"registry/discovery"/(key+".json")).write_text(json.dumps(cached))
            with patch("discover.discover_target",side_effect=AssertionError("must use cache")):
                run(root,1)
            with patch("discover.discover_target",return_value={**cached,"checked_at":"new"}) as mocked:
                run(root,1,refresh=True)
            mocked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
