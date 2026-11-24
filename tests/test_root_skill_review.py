"""Root Skill scope review: real Git tree evidence and bounded inert fixtures."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from root_skill_review import inspect_inventory, inspect_root_skill, verify_recursive_tree
from tests.test_canonical_index import record
from tests.test_canonical_package import blob, tree, directory


def fixture(main, *children):
    top = tree(main, *children)
    row = record(path="SKILL.md", blob=main["sha"])
    row.update(tree_sha=top["sha"],snapshot_status="verified_commit_pinned")
    return row, top


class RootSkillReviewTests(unittest.TestCase):
    def test_real_git_recursive_tree_and_no_content_fetch(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            subprocess.run(["git","init","-q","--object-format=sha1",str(root)],check=True)
            for name,data in {"SKILL.md":b"root inert", "scripts/demo.py":b"# inert",
                              "child/SKILL.md":b"child inert","child/guide.md":b"guide",
                              "LICENSE":b"fixture terms"}.items():
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            subprocess.run(["git","-C",str(root),"-c","core.autocrlf=false","add","."],check=True)
            oid=subprocess.check_output(["git","-C",str(root),"write-tree"],text=True).strip()
            raw=subprocess.check_output(["git","-C",str(root),"ls-tree","-r","-t","-l","-z",oid])
            entries=[]
            for line in raw.split(b"\0"):
                if not line:continue
                meta,name=line.split(b"\t",1)
                mode,kind,sha,size=meta.decode().split()
                item={"path":name.decode(),"mode":mode,"type":kind,"sha":sha}
                if size!="-":item["size"]=int(size)
                entries.append(item)
            row=record(path="SKILL.md",blob=next(x["sha"] for x in entries if x["path"]=="SKILL.md"))
            row["tree_sha"]=oid
            report=inspect_inventory(row,{"sha":oid,"truncated":False,"tree":entries})
            self.assertEqual(report["candidate_file_count"],3)
            self.assertEqual(report["nested_skill_directories"],["child"])
            self.assertEqual(len(report["excluded_entries"]),2)
            self.assertFalse(report["download_approved"])
            self.assertFalse(report["package_scope_confirmed"])

    def test_tamper_or_truncation_or_omission_refused(self):
        main=blob("SKILL.md");child=tree(blob("data"))
        row,top=fixture(main,directory("folder",child))
        data=dict(top,tree=top["tree"]+[dict(child["tree"][0],path="folder/data")])
        verify_recursive_tree(data,row["tree_sha"])
        for bad in (dict(data,truncated=True),dict(data,tree=data["tree"][:-1]),
                    dict(data,tree=data["tree"]+[data["tree"][0]]),
                    dict(data,tree=[dict(main,sha="f"*40),*data["tree"][1:]])):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                inspect_inventory(row,bad)

    def test_nonportable_nonregular_and_metadata_exclusions(self):
        row,data=fixture(blob("SKILL.md"),blob("CON"),blob("link",mode="120000"),
                         blob("source.json"),blob("A"),blob("a"))
        report=inspect_inventory(row,data)
        self.assertEqual(report["status"],"blocked_inventory")
        reasons={x["reason"] for x in report["blocked_entries"]}
        self.assertEqual(reasons,{"nonportable_path","nonregular_entry","case_or_unicode_collision"})
        self.assertEqual(report["excluded_entries"][0]["path"],"source.json")
        self.assertFalse(report["installation_or_execution_approved"])

    def test_missing_pin_and_budget(self):
        row,data=fixture(blob("SKILL.md"),blob("more"))
        with self.assertRaises(ValueError):
            inspect_inventory(dict(row,skill_md_blob_sha="f"*40),data)
        with patch("root_skill_review.MAX_FILES",1):
            self.assertEqual(inspect_inventory(row,data)["status"],"blocked_inventory")

    def test_explicit_online_review_and_catalog_drift(self):
        row,data=fixture(blob("SKILL.md"),blob("guide"))
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);path=root/"registry/source-catalog.json";path.parent.mkdir()
            raw=json.dumps({"schema_version":"1.0.0","records":[row]}).encode();path.write_bytes(raw)
            replies=[{"id":1,"full_name":row["repository"]},{"sha":row["commit_sha"],"tree":{"sha":row["tree_sha"]}},data]
            def fetch(endpoint):
                return replies.pop(0),{"endpoint":endpoint}
            with patch("root_skill_review._get",side_effect=fetch) as get:
                report=inspect_root_skill(row["source_record_id"],root=root)
            self.assertEqual(get.call_count,3)
            self.assertTrue(report["tree_object_hashes_verified"])
            self.assertEqual(path.read_bytes(),raw)
            self.assertEqual(list(root.rglob("*")),[path.parent,path])
            self.assertEqual(report["status"],"scope_review_required")
            replies[:]=[{"id":1,"full_name":row["repository"]},{"sha":row["commit_sha"],"tree":{"sha":row["tree_sha"]}},data]
            def changed(endpoint):
                path.write_bytes(raw+b" ")
                return fetch(endpoint)
            with patch("root_skill_review._get",side_effect=changed),self.assertRaisesRegex(ValueError,"Catalog changed"):
                inspect_root_skill(row["source_record_id"],root=root)


if __name__=="__main__":
    unittest.main()
