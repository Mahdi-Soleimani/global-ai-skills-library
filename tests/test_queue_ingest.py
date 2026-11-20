import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from queue_ingest import make_plan, ingest, git_blob, package_location, validate_inventory

POLICY={"max_file_size_bytes":1000,"max_skill_size_bytes":2000}
COMMIT="a"*40
TREE="b"*40
FILES={"skills/demo/SKILL.md":b"---\nname: demo\ndescription: demo\n---\n","skills/demo/references/guide.md":b"guide"}


def entry(path,data,mode="100644"):
    return {"path":path,"type":"blob","mode":mode,"size":len(data),"sha":git_blob(data)}


def fixture():
    row={"repository":"Org/Repo","skill_path":"skills/demo/SKILL.md","commit_sha":COMMIT,"tree_sha":TREE,
         "skill_md_blob_sha":git_blob(FILES["skills/demo/SKILL.md"]),"license_spdx":None,"research_leads":["A"]}
    tree={"sha":TREE,"truncated":False,"tree":[entry(p,d) for p,d in FILES.items()]}
    return row,tree


class QueueIngestTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/"registry").mkdir()
        (self.root/"registry/download-manifest.json").write_text('{"schema_version":"0.1.0","downloads":[]}')

    def test_plan_exact_pin_and_nested_boundary(self):
        row,tree=fixture()
        tree["tree"].append(entry("skills/demo/child/SKILL.md",b"child"))
        tree["tree"].append(entry("skills/demo/child/README.md",b"child"))
        plan=make_plan(row,tree,POLICY)
        self.assertEqual(len(plan["files"]),2)
        self.assertEqual(plan["nested_skill_dirs_excluded"],["skills/demo/child"])

    def test_wrong_tree_and_blob_fail(self):
        row,tree=fixture()
        row["skill_md_blob_sha"]="c"*40
        with self.assertRaises(ValueError): make_plan(row,tree,POLICY)
        row,tree=fixture(); tree["sha"]="c"*40
        with self.assertRaises(ValueError): make_plan(row,tree,POLICY)

    def test_symlink_size_and_unsafe_paths_fail_closed(self):
        for p,data,mode in [("skills/demo/link",b"target","120000"),("skills/demo/large",b"x"*1001,"100644"),
                            ("skills/demo/../escape",b"x","100644")]:
            row,tree=fixture(); tree["tree"].append(entry(p,data,mode))
            with self.assertRaises(ValueError): make_plan(row,tree,POLICY)

    def test_case_collisions_fail(self):
        row,tree=fixture()
        tree["tree"].append(entry("skills/demo/References/other.md",b"x"))
        with self.assertRaises(ValueError): make_plan(row,tree,POLICY)

    def test_resume_and_idempotence(self):
        row,tree=fixture(); plan=make_plan(row,tree,POLICY)
        calls=[]
        def interrupted(plan,item):
            calls.append(item["path"])
            if len(calls)==2: raise RuntimeError("interrupt")
            return FILES[item["path"]]
        with self.assertRaises(RuntimeError): ingest(self.root,plan,interrupted)
        self.assertFalse(package_location(self.root,plan).exists())
        result=ingest(self.root,plan,lambda p,i:FILES[i["path"]])
        self.assertEqual(result["reused_files"],1)
        self.assertEqual(result["new_files"],1)
        again=ingest(self.root,plan,lambda *_:self.fail("network reuse"))
        self.assertEqual(again["status"],"already_verified")
        manifest=json.loads((self.root/"registry/download-manifest.json").read_text())
        self.assertEqual(len(manifest["downloads"][0]["skill_packages"]),1)
        meta=json.loads((package_location(self.root,plan)/"source.json").read_text())
        self.assertFalse(meta["execution_performed"])
        self.assertEqual(meta["license_status"],"repository_metadata_only_review_required")

    def test_wrong_download_never_promoted(self):
        row,tree=fixture(); plan=make_plan(row,tree,POLICY)
        with self.assertRaises(ValueError): ingest(self.root,plan,lambda p,i:b"bad")
        self.assertFalse(package_location(self.root,plan).exists())

    def test_existing_extra_file_is_rejected(self):
        row,tree=fixture(); plan=make_plan(row,tree,POLICY)
        ingest(self.root,plan,lambda p,i:FILES[i["path"]])
        (package_location(self.root,plan)/"extra").write_text("unexpected")
        with self.assertRaises(ValueError): ingest(self.root,plan,lambda *_:b"")

    def test_local_symlink_fails(self):
        row,tree=fixture(); plan=make_plan(row,tree,POLICY)
        (self.root/"catalog").symlink_to(self.root/"registry",target_is_directory=True)
        with self.assertRaises(ValueError): ingest(self.root,plan,lambda *_:b"")
