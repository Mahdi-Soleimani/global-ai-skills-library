import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from on_demand import download_skill
from queue_ingest import git_blob

class OnDemandTests(unittest.TestCase):
    def test_selected_unknown_license_package_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "registry").mkdir()
            tracked = root / "registry/download-manifest.json"
            tracked.write_text('{"downloads":[]}')
            (root / "config/policy.json").write_text(json.dumps({
                "max_file_size_bytes":1000,"max_skill_size_bytes":2000,
                "public_mirror_spdx_allowlist":["MIT"]}))
            files = {"skills/demo/SKILL.md":b"# demo", "skills/demo/references/guide.md":b"guide"}
            row = {"repository":"Org/Repo","source_path":"skills/demo/SKILL.md",
                   "commit_sha":"a"*40,"tree_sha":"b"*40,
                   "skill_md_blob_sha":git_blob(files["skills/demo/SKILL.md"]),
                   "license_spdx":"NOASSERTION","snapshot_status":"verified_commit_pinned"}
            tree = {"sha":"b"*40,"truncated":False,"tree":[
                {"path":p,"type":"blob","mode":"100644","size":len(v),"sha":git_blob(v)}
                for p,v in files.items()]}
            from queue_ingest import ingest as actual_ingest
            with patch("on_demand.get_skill_by_id",return_value=row), \
                 patch("queue_ingest.fetch_tree",return_value=tree), \
                 patch("queue_ingest.ingest",side_effect=lambda *a,**kw:actual_ingest(
                     *a,fetch=lambda p,i:files[i["path"]],**kw)):
                planned=download_skill("demo",root=root)
                self.assertEqual(planned["status"],"planned")
                self.assertFalse(planned["installation_allowed"])
                self.assertFalse(planned["security_scan_performed"])
                self.assertFalse((root/"catalog").exists())
                actual=download_skill("demo",root=root,execute=True)
                self.assertEqual(actual["status"],"downloaded")
                self.assertFalse(actual["installed"])
                self.assertFalse(actual["executed"])
                self.assertFalse(actual["installation_allowed"])
                self.assertFalse(actual["execution_allowed"])
                self.assertEqual(actual["security_status"], "no_obvious_static_flags_not_approved")
                self.assertTrue(actual["integrity_ok"])
                self.assertTrue(actual["security_scan_performed"])
                self.assertTrue(actual["pinned_skill_blob_ok"])
                self.assertTrue((root/actual["security_report_path"]).is_file())
                self.assertEqual(actual["file_count"],2)
                again=download_skill("demo",root=root,execute=True)
                self.assertEqual(again["status"],"already_verified")
                self.assertEqual(tracked.read_text(),'{"downloads":[]}')
                self.assertTrue((root/"private/on-demand-manifest.json").is_file())
                with patch("security_gate.audit_local_package", return_value={
                    "integrity_ok": False,
                    "security_status": "integrity_failed",
                    "installation_allowed": False,
                    "execution_allowed": False,
                }):
                    blocked = download_skill("demo", root=root, execute=True)
                self.assertEqual(blocked["status"], "blocked_integrity_failure")
                self.assertFalse(blocked["installation_allowed"])
                meta=json.loads((root/actual["filesystem_path"]/"source.json").read_text())
                self.assertEqual(meta["license_spdx"],"NOASSERTION")
                self.assertTrue(meta["package_complete"])

    def test_unpinned_record_rejected_before_network(self):
        with patch("on_demand.get_skill_by_id",return_value={"snapshot_status":"legacy_snapshot_unpinned"}), \
             patch("queue_ingest.fetch_tree") as fetch:
            with self.assertRaisesRegex(ValueError,"commit-pinned"):
                download_skill("legacy")
            fetch.assert_not_called()
