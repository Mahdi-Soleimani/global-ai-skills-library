"""Verify Git tree metadata without downloading or executing Skill contents."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools"))
from canonical_package import checked_tree, compare_packages
from tests.test_canonical_index import record


def blob(name, content=b"fixture", mode="100644"):
    return {"path":name,"mode":mode,"type":"blob","size":len(content),
            "sha":hashlib.sha1(b"blob "+str(len(content)).encode()+b"\0"+content).hexdigest()}


def tree(*entries):
    # Test helper for adversarial API fixtures. Independent Git-generated test below.
    ordered=sorted(entries,key=lambda x:x["path"].encode()+ (b"/" if x["type"]=="tree" else b""))
    raw=b"".join(x["mode"].lstrip("0").encode()+b" "+x["path"].encode()+b"\0"+
                 bytes.fromhex(x["sha"]) for x in ordered)
    sha=hashlib.sha1(b"tree "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
    return {"sha":sha,"truncated":False,"tree":list(entries)}


def directory(name, value):
    return {"path":name,"mode":"040000","type":"tree","sha":value["sha"]}


class CanonicalPackageTests(unittest.TestCase):
    def fixture(self, left, right, *, same_repo=False, historical=False, extra=(), contexts=((),())):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root=Path(temporary.name)
        path=root/"registry/source-catalog.json"
        path.parent.mkdir()
        main=next(x for x in left["tree"] if x["path"]=="SKILL.md")
        other=next(x for x in right["tree"] if x["path"]=="SKILL.md")
        rows=[record(repo="org/repo",path="skill/SKILL.md",blob=None if historical else main["sha"]),
              record(repo="org/repo" if same_repo else "other/repo",path="skill/SKILL.md",
                     commit="c"*40,blob=other["sha"])]
        endpoints={}
        for i,(row,folder) in enumerate(zip(rows,(left,right))):
            repo=row["repository"]
            top=tree(directory("skill",folder),*contexts[i])
            endpoints["/repos/"+repo]={"id":1 if repo=="org/repo" else 2,"full_name":repo}
            endpoints["/repos/"+repo+"/git/commits/"+row["commit_sha"]]={"sha":row["commit_sha"],"tree":{"sha":top["sha"]}}
            row["tree_sha"]=top["sha"]
            for t in (top,folder,*extra):
                endpoints["/repos/"+repo+"/git/trees/"+t["sha"]]=t
        path.write_text(json.dumps({"schema_version":"1.0.0","records":rows}),encoding="utf-8")
        ids=[r["source_record_id"] for r in rows]
        return root,path,ids,endpoints

    def call(self, root, ids, endpoints):
        def fetch(endpoint):
            return endpoints[endpoint],{"endpoint":endpoint,"response_sha256":"f"*64}
        with patch("canonical_package._get",side_effect=fetch) as get:
            report=compare_packages(ids,root=root)
        return report,get

    def test_git_generated_tree_hash_including_directory_sort(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            subprocess.run(["git","init","--quiet","--object-format=sha1",str(root)],check=True)
            (root/"a").mkdir()
            (root/"a"/"file").write_bytes(b"x")
            (root/"a.c").write_bytes(b"y")
            (root/"SKILL.md").write_bytes(b"fixture")
            subprocess.run(["git","-C",str(root),"-c","core.autocrlf=false","add","."],check=True)
            oid=subprocess.check_output(["git","-C",str(root),"write-tree"],text=True).strip()
            raw=subprocess.check_output(["git","-C",str(root),"ls-tree","-z",oid])
            items=[]
            for line in raw.split(b"\0"):
                if line:
                    meta,name=line.split(b"\t",1)
                    mode,kind,sha=meta.decode().split()
                    items.append({"path":name.decode(),"mode":mode,"type":kind,"sha":sha})
            checked_tree({"sha":oid,"truncated":False,"tree":list(reversed(items))},oid)

    def test_equal_complete_directory_no_writes_no_blob_fetch(self):
        nested=tree(blob("data.txt",b"nested"))
        package=tree(blob("SKILL.md"),blob("run.py"),directory("nested",nested))
        root,path,ids,endpoints=self.fixture(package,package,extra=(nested,))
        before=path.read_bytes()
        report,get=self.call(root,ids,endpoints)
        self.assertTrue(report["directory_tree_identity_equal"])
        self.assertTrue(report["recorded_file_inventory_equal"])
        self.assertTrue(report["git_tree_object_hashes_verified"])
        self.assertEqual(report["packages"][0]["file_count"],3)
        self.assertFalse(report["full_install_bundle_equivalence_established"])
        self.assertFalse(report["blob_contents_downloaded"])
        self.assertFalse(report["installation_or_execution_approved"])
        self.assertFalse(any("/git/blobs/" in x.args[0] for x in get.call_args_list))
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(list(root.rglob("*")),[path.parent,path])

    def test_same_skill_different_files_and_modes(self):
        left=tree(blob("SKILL.md"),blob("run.py"),blob("left.txt"))
        right=tree(blob("SKILL.md"),blob("run.py",mode="100755"),blob("right.txt"))
        root,_,ids,endpoints=self.fixture(left,right)
        report,_=self.call(root,ids,endpoints)
        self.assertFalse(report["directory_tree_identity_equal"])
        self.assertFalse(report["recorded_file_inventory_equal"])
        self.assertEqual(report["changed_files"],["run.py"])
        self.assertEqual(report["only_left"],["left.txt"])
        self.assertEqual(report["only_right"],["right.txt"])

    def test_historical_missing_blob_pin_preserved(self):
        root,_,ids,endpoints=self.fixture(tree(blob("SKILL.md",b"old")),
                                         tree(blob("SKILL.md",b"new")),same_repo=True,historical=True)
        report,_=self.call(root,ids,endpoints)
        self.assertFalse(report["packages"][0]["catalog_skill_blob_pin_present"])
        self.assertEqual(report["changed_files"],["SKILL.md"])

    def test_tree_mismatch_truncation_duplicate_and_tamper_refused(self):
        valid=tree(blob("SKILL.md"),blob("data"))
        mutations=[dict(valid,truncated=True),dict(valid,sha="a"*40),
                   dict(valid,tree=valid["tree"][:1]),
                   dict(valid,tree=valid["tree"]+[valid["tree"][0]]),
                   dict(valid,tree=[dict(valid["tree"][0],mode="100755"),valid["tree"][1]])]
        for changed in mutations:
            with self.subTest(changed=changed),self.assertRaises(ValueError):
                checked_tree(changed,valid["sha"])

    def test_nonregular_and_case_collision_refused(self):
        main=blob("SKILL.md")
        for bad in (tree(main,blob("link",mode="120000")),
                    tree(main,{"path":"module","mode":"160000","type":"commit","sha":"d"*40}),
                    tree(main,blob("Foo"),blob("foo")),
                    tree(main,blob("CON"))):
            root,_,ids,endpoints=self.fixture(bad,bad)
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                self.call(root,ids,endpoints)

    def test_pin_mismatch_drift_and_request_budget_refused(self):
        package=tree(blob("SKILL.md"))
        root,path,ids,endpoints=self.fixture(package,package)
        with patch("canonical_package.MAX_REQUESTS",1),self.assertRaisesRegex(ValueError,"request budget"):
            self.call(root,ids,endpoints)
        endpoint="/repos/org/repo/git/commits/"+"a"*40
        original=endpoints[endpoint]
        endpoints[endpoint]=dict(original,sha="d"*40)
        with self.assertRaisesRegex(ValueError,"Commit pin"):
            self.call(root,ids,endpoints)
        endpoints[endpoint]=original
        def fetch(endpoint):
            path.write_bytes(path.read_bytes()+b" ")
            return endpoints[endpoint],{"endpoint":endpoint}
        with patch("canonical_package._get",side_effect=fetch),self.assertRaisesRegex(ValueError,"Catalog changed"):
            compare_packages(ids,root=root)

    def test_equal_directory_different_ancestor_license_and_manifest(self):
        package=tree(blob("SKILL.md"),blob("requirements.txt"))
        root,_,ids,endpoints=self.fixture(package,package,
            contexts=((blob("LICENSE",b"terms A"),blob("pyproject.toml")),
                      (blob("LICENSE",b"terms B"),blob("pyproject.toml"))))
        report,_=self.call(root,ids,endpoints)
        self.assertTrue(report["directory_tree_identity_equal"])
        context=report["ancestor_context_comparison"]
        self.assertFalse(context["license_notice_filename"]["recorded_candidates_equal"])
        self.assertTrue(context["dependency_manifest_filename"]["recorded_candidates_equal"])
        self.assertFalse(report["license_applicability_verified"])
        self.assertFalse(report["dependency_resolution_performed"])
        self.assertFalse(report["runtime_dependencies_verified"])
        self.assertEqual(report["packages"][0]["directory_context_candidates"][0]["source_path"],
                         "requirements.txt")

    def test_empty_context_is_unknown_not_equal(self):
        package=tree(blob("SKILL.md"))
        root,_,ids,endpoints=self.fixture(package,package)
        report,_=self.call(root,ids,endpoints)
        self.assertTrue(all(x["recorded_candidates_equal"] is None
                           for x in report["ancestor_context_comparison"].values()))

    def test_nonregular_ancestor_candidate_is_not_ordinary_file(self):
        package=tree(blob("SKILL.md"))
        root,_,ids,endpoints=self.fixture(package,package,
            contexts=((blob("LICENSE",mode="120000"),),()))
        report,_=self.call(root,ids,endpoints)
        self.assertFalse(report["packages"][0]["ancestor_context_candidates"][0]["ordinary_file"])
        self.assertFalse(report["license_applicability_verified"])
        self.assertFalse(report["ancestor_context_comparison"]["license_notice_filename"]["recorded_candidates_equal"])

    def test_unrelated_pair_never_contacts_api(self):
        root,_,ids,endpoints=self.fixture(tree(blob("SKILL.md",b"left")),
                                         tree(blob("SKILL.md",b"right")))
        with patch("canonical_package._get",side_effect=AssertionError("No network")),self.assertRaises(ValueError):
            compare_packages(ids,root=root)


if __name__=="__main__":
    unittest.main()
