"""Portable isolated queue-download tests; Windows CI exercises native msvcrt locks.

No network, actual Agent directories, third-party execution, or user HOME writes.
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import queue_ingest as qi
from on_demand import download_skill
from tests.test_queue_ingest import FILES, POLICY, entry, fixture


class QueueLockTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="gasl-queue-inert-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "registry" / "discovery").mkdir(parents=True)
        (self.root / "config").mkdir()
        (self.root / "config" / "policy.json").write_text(json.dumps({
            **POLICY,
            "max_repository_download_bytes": 5000,
            "public_mirror_spdx_allowlist": ["MIT"],
        }))
        (self.root / "registry" / "download-manifest.json").write_text(
            '{"schema_version":"0.1.0","downloads":[]}')
        self.row, self.tree = fixture()
        self.row.update({
            "install_status": "not_approved",
            "status": "pending_package_plan",
            "discovery_status": "verified_metadata_only",
        })
        (self.root / "registry" / "discovery" / "download-queue.json").write_text(
            json.dumps([self.row]))

    def _run_queue(self, *options):
        argv = ["queue_ingest.py", "--repo", "Org/Repo", *options]
        real_ingest = qi.ingest
        with patch.object(qi, "ROOT", self.root), \
             patch.object(sys, "argv", argv), \
             patch.object(qi, "fetch_tree", return_value=self.tree), \
             patch.object(qi, "ingest", side_effect=lambda root, plan: real_ingest(
                 root, plan, fetch=lambda p, i: FILES[i["path"]])), \
             contextlib.redirect_stdout(io.StringIO()):
            qi.main()

    def test_queue_plan_and_download_are_inert_and_idempotent(self):
        self._run_queue("--execute")
        dest = qi.package_location(self.root, qi.make_plan(self.row, self.tree, {
            **POLICY, "max_repository_download_bytes": 5000}))
        self.assertEqual((dest / "SKILL.md").read_bytes(), FILES["skills/demo/SKILL.md"])
        metadata = json.loads((dest / "source.json").read_text())
        self.assertTrue(metadata["package_complete"])
        self.assertFalse(metadata["execution_performed"])
        self.assertEqual(metadata["public_mirror_status"], "not_eligible_license_policy")
        self.assertTrue((self.root / "registry" / "discovery" / ".ingest.lock").is_file())
        self._run_queue("--execute", "--verify-existing")
        results = json.loads((self.root / "registry" / "discovery" / "ingest-results.json").read_text())
        self.assertEqual(results[0]["status"], "already_verified")
        self.assertEqual(len(json.loads((self.root / "registry" / "download-manifest.json").read_text())["downloads"]), 1)

    def test_second_process_cannot_plan_or_write_through_held_lock(self):
        script = (
            "import sys,time\n"
            "sys.path.insert(0, sys.argv[2])\n"
            "from queue_ingest import ingestion_lock\n"
            "with ingestion_lock(sys.argv[1]):\n"
            "    print('LOCKED', flush=True)\n"
            "    time.sleep(2.0)\n"
        )
        process = subprocess.Popen(
            [sys.executable, "-c", script, str(self.root), str(ROOT / "tools")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), "LOCKED")
            with patch.object(qi, "ROOT", self.root), \
                 patch.object(sys, "argv", ["queue_ingest.py", "--repo", "Org/Repo"]), \
                 patch.object(qi, "fetch_tree") as fetch:
                with self.assertRaises((BlockingIOError, ValueError)):
                    qi.main()
                fetch.assert_not_called()
            self.assertFalse((self.root / "registry" / "discovery" / "ingest-plan.json").exists())
            process.wait(timeout=6)
            self.assertEqual(process.returncode, 0, process.stderr.read())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
            process.stderr.close()
        # The permanent lock file survives, but is reusable after release.
        self._run_queue()
        self.assertTrue((self.root / "registry" / "discovery" / "ingest-plan.json").is_file())

    def test_on_demand_uses_same_queue_lock(self):
        record = {
            **self.row, "source_path": self.row["skill_path"],
            "snapshot_status": "verified_commit_pinned",
        }
        with qi.ingestion_lock(self.root), \
             patch("on_demand.get_skill_by_id", return_value=record), \
             patch.object(qi, "fetch_tree", return_value=self.tree), \
             patch.object(qi, "ingest") as ingest:
            with self.assertRaises((BlockingIOError, ValueError)):
                download_skill("inert-id", root=self.root, execute=True)
            ingest.assert_not_called()
        self.assertFalse((self.root / "catalog").exists())

    def test_corrupted_checkpoint_is_retained_and_not_promoted(self):
        plan = qi.make_plan(self.row, self.tree, POLICY)
        calls = []
        def interrupt(_plan, item):
            calls.append(item["path"])
            if len(calls) == 2:
                raise RuntimeError("simulated interruption")
            return FILES[item["path"]]
        with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
            qi.ingest(self.root, plan, interrupt)
        stage = (self.root / "quarantine" / "queue-ingest" /
                 qi.package_location(self.root, plan).parent.name /
                 qi.package_location(self.root, plan).name)
        existing = next(stage.rglob("SKILL.md"))
        existing.write_bytes(b"TAMPERED")
        with self.assertRaisesRegex(ValueError, "Corrupt checkpoint"):
            qi.ingest(self.root, plan, lambda p, i: FILES[i["path"]])
        self.assertEqual(existing.read_bytes(), b"TAMPERED")
        self.assertFalse(qi.package_location(self.root, plan).exists())

    def test_hard_linked_lock_file_is_refused_without_touching_alias(self):
        sentinel = self.root / "SENTINEL-DO-NOT-TOUCH"
        sentinel.write_bytes(b"PRIVATE CONTENT")
        lock_path = self.root / "registry" / "discovery" / ".ingest.lock"
        os.link(sentinel, lock_path)
        with self.assertRaisesRegex(ValueError, "hard-link"):
            with qi.ingestion_lock(self.root):
                self.fail("Hard-linked queue lock must not be acquired")
        self.assertEqual(sentinel.read_bytes(), b"PRIVATE CONTENT")

    def test_nonregular_queue_lock_is_rejected(self):
        (self.root / "registry" / "discovery" / ".ingest.lock").mkdir()
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            with qi.ingestion_lock(self.root):
                self.fail("Directory cannot be used as a queue lock")

    @unittest.skipUnless(os.name == "nt", "Windows-only reserved/ADS names")
    def test_windows_queue_path_names_fail_before_disk_access(self):
        for name in ("CON", "NUL.txt", "part:ADS", "trailing.", "trailing "):
            with self.subTest(name=name):
                row, tree = fixture()
                tree["tree"].append(entry("skills/demo/" + name, b"inert"))
                with self.assertRaisesRegex(ValueError, "Windows"):
                    qi.make_plan(row, tree, POLICY)
        row, tree = fixture()
        row["skill_path"] = "skills/CON/SKILL.md"
        with self.assertRaisesRegex(ValueError, "Windows"):
            qi.make_plan(row, tree, POLICY)


if __name__ == "__main__":
    unittest.main()
