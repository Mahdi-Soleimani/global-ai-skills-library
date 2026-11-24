"""Inert selected root files: plan binding, verified collection and isolated audit."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from root_skill_scope import collect_scope, audit_scope, make_scope
from root_skill_review import inspect_inventory
from tests.test_root_skill_review import fixture
from tests.test_canonical_package import blob, tree, directory
from canonical_index import _read_raw


class RootSkillScopeTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(prefix="gasl-root-scope-")
        self.addCleanup(t.cleanup)
        self.root=Path(t.name).resolve()
        self.contents={"SKILL.md":b"# inert fixture","LICENSE":b"fixture terms",
                       "unrelated.txt":b"not selected","scripts/demo.py":b"# inert"}
        nested=tree(blob("demo.py",self.contents["scripts/demo.py"]))
        self.row,self.tree=fixture(blob("SKILL.md",self.contents["SKILL.md"]),
            blob("LICENSE",self.contents["LICENSE"]),blob("unrelated.txt",self.contents["unrelated.txt"]),
            directory("scripts",nested))
        self.tree["tree"].append(dict(nested["tree"][0],path="scripts/demo.py"))
        self.sid=self.row["source_record_id"]
        self.path=self.root/"registry/source-catalog.json"
        self.path.parent.mkdir()
        self.path.write_text(json.dumps({"schema_version":"1.0.0","records":[self.row]}),encoding="utf-8")
        self.review={**inspect_inventory(self.row,self.tree),"catalog_sha256":_read_raw(self.root)[1]}
        self.addCleanup(patch.stopall)
        self.inspect=patch("root_skill_scope.inspect_root_skill",return_value=self.review).start()
        self.fetch=patch("root_skill_scope._fetch",side_effect=lambda p,i:self.contents[i["path"]]).start()

    def plan(self,paths=None):
        return collect_scope(self.sid,paths or ["SKILL.md","scripts/demo.py"],root=self.root)

    def collect(self,preview=None):
        preview=preview or self.plan()
        return collect_scope(self.sid,preview["plan"]["requested_paths"],root=self.root,
                             execute=True,acknowledge=preview["plan_sha256"])

    def test_preview_and_explicit_scope_license_and_budget(self):
        p=self.plan()
        self.assertEqual([x["path"] for x in p["plan"]["files"]],["LICENSE","SKILL.md","scripts/demo.py"])
        self.assertFalse((self.root/"private").exists())
        self.fetch.assert_not_called()
        self.assertFalse(p["package_complete"])
        for paths in (["scripts/demo.py"],["SKILL.md","SKILL.md"],["SKILL.md","missing"]):
            with self.subTest(paths=paths),self.assertRaises(ValueError):
                self.plan(paths)
        self.review["blocked_entries"]=[{"path":".","reason":"candidate_inventory_budget_exceeded"}]
        self.assertEqual(self.plan()["plan_sha256"],p["plan_sha256"])
        self.review["blocked_entries"]=[{"path":"link","reason":"nonregular_entry"}]
        with self.assertRaises(ValueError):self.plan()

    def test_acknowledgement_mismatch_before_write_or_fetch(self):
        p=self.plan()
        for ack in (None,"f"*64):
            with self.subTest(ack=ack),self.assertRaises(ValueError):
                collect_scope(self.sid,p["plan"]["requested_paths"],root=self.root,execute=True,acknowledge=ack)
        self.assertFalse((self.root/"private").exists())
        self.fetch.assert_not_called()

    def test_real_collection_offline_audit_reuse_and_no_normal_catalog(self):
        p=self.plan();result=self.collect(p)
        self.assertEqual(result["status"],"collected_private_review")
        self.assertTrue(result["integrity_ok"])
        self.assertFalse(result["installation_or_execution_approved"])
        folder=self.root/result["private_review_path"]
        self.assertFalse((self.root/"catalog").exists())
        self.assertFalse((folder/"catalog/selection/unrelated.txt").exists())
        self.assertFalse(json.loads((folder/"catalog/selection/source.json").read_text())["package_complete"])
        self.assertEqual(self.fetch.call_count,3)
        with patch("root_skill_scope.inspect_root_skill",side_effect=AssertionError("Offline")):
            audit=audit_scope(self.sid,p["plan_sha256"],root=self.root)
        self.assertEqual(audit["status"],"offline_verified")
        self.assertEqual(self.collect(p)["status"],"already_verified")
        self.assertEqual(self.fetch.call_count,3)

    def test_bad_blob_never_publishes_or_leaves_stage(self):
        p=self.plan();self.fetch.side_effect=lambda *_:b"wrong"
        with self.assertRaisesRegex(ValueError,"Git blob mismatch"):self.collect(p)
        base=self.root/"private/root-skill-scopes"/self.sid
        self.assertFalse((base/p["plan_sha256"]).exists())
        self.assertFalse(list(base.glob(".gasl-root-stage-*")))
        self.assertFalse((self.root/"catalog").exists())

    def test_modified_file_and_extra_path_fail_audit_and_reuse(self):
        p=self.plan();result=self.collect(p);folder=self.root/result["private_review_path"]
        target=folder/"catalog/selection/SKILL.md"
        target.write_bytes(b"tamper")
        with self.assertRaises(ValueError):audit_scope(self.sid,p["plan_sha256"],root=self.root)
        with self.assertRaises(ValueError):self.collect(p)
        target.write_bytes(self.contents["SKILL.md"])
        (folder/"unexpected").write_bytes(b"inert")
        with self.assertRaisesRegex(ValueError,"Unexpected"):audit_scope(self.sid,p["plan_sha256"],root=self.root)

    def test_hardlink_and_catalog_drift_refused(self):
        p=self.plan();result=self.collect(p);folder=self.root/result["private_review_path"]
        target=folder/"catalog/selection/SKILL.md"
        alias=self.root/"alias"
        os.link(target,alias)
        with self.assertRaisesRegex(ValueError,"Hard-linked"):audit_scope(self.sid,p["plan_sha256"],root=self.root)
        self.assertEqual(alias.read_bytes(),self.contents["SKILL.md"])
        alias.unlink()
        self.path.write_bytes(self.path.read_bytes()+b" ")
        with self.assertRaisesRegex(ValueError,"Catalog changed"):self.collect(p)

    def test_plan_tamper_refused(self):
        p=self.plan();result=self.collect(p);folder=self.root/result["private_review_path"]
        path=folder/"plan.json";plan=json.loads(path.read_text());plan["review_sha256"]="e"*64
        path.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError,"digest mismatch"):audit_scope(self.sid,p["plan_sha256"],root=self.root)


if __name__=="__main__":
    unittest.main()
