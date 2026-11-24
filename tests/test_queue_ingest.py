import hashlib
import json
import os
import urllib.error
import urllib.request
from unittest.mock import patch, MagicMock
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from queue_ingest import make_plan, ingest, git_blob, package_location, validate_inventory, public_mirror_rejection, merge_manifest

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
        (self.root/"config").mkdir()
        (self.root/"config/policy.json").write_text(json.dumps({"public_mirror_spdx_allowlist":["MIT"]}))
        (self.root/"registry/download-manifest.json").write_text('{"schema_version":"0.1.0","downloads":[]}')

    def test_plan_exact_pin_and_nested_boundary(self):
        row,tree=fixture()
        tree["tree"].append(entry("skills/demo/child/SKILL.md",b"child"))
        tree["tree"].append(entry("skills/demo/child/README.md",b"child"))
        plan=make_plan(row,tree,POLICY)
        self.assertEqual(len(plan["files"]),2)
        self.assertEqual(plan["nested_skill_dirs_excluded"],["skills/demo/child"])

    def test_plan_bundles_applicable_upstream_license_and_notice_files(self):
        row,tree=fixture()
        tree["tree"].extend([
            entry("LICENSE",b"MIT root text"),
            entry("skills/LICENSE",b"MIT skills text"),
            entry("skills/demo/NOTICE",b"Upstream notice")
        ])
        plan=make_plan(row,tree,{"max_file_size_bytes":1000,"max_skill_size_bytes":5000})
        paths={x["path"] for x in plan["files"]}
        relatives={x["relative"] for x in plan["files"]}
        self.assertIn("__upstream_licenses__/"+hashlib.sha256(b"LICENSE").hexdigest()[:10]+"-license",relatives)
        self.assertIn("__upstream_licenses__/"+hashlib.sha256(b"skills/LICENSE").hexdigest()[:10]+"-license",relatives)
        self.assertIn("NOTICE",relatives)
        self.assertEqual(len(plan["license_evidence"]),3)

    def test_nested_license_files_inside_package_are_preserved_as_evidence(self):
        row,tree=fixture()
        tree["tree"].append(entry("LICENSE",b"MIT root"))
        tree["tree"].append(entry("skills/demo/assets/LICENSE",b"asset license"))
        plan=make_plan(row,tree,{"max_file_size_bytes":1000,"max_skill_size_bytes":5000})
        evidence={x["source_path"] for x in plan["license_evidence"]}
        self.assertIn("LICENSE",evidence)
        self.assertIn("skills/demo/assets/LICENSE",evidence)

    def test_package_local_license_is_not_added_twice(self):
        row,tree=fixture()
        tree["tree"].append(entry("skills/demo/LICENSE",b"MIT"))
        plan=make_plan(row,tree,POLICY)
        self.assertEqual(sum(x["relative"]=="LICENSE" for x in plan["files"]),1)
        self.assertEqual(len(plan["license_evidence"]),1)

    def test_public_mirror_requires_allowlisted_license_and_bundled_evidence(self):
        row,tree=fixture()
        plan=make_plan(row,tree,POLICY)
        policy={"public_mirror_spdx_allowlist":["MIT"]}
        self.assertIn("allowlist",public_mirror_rejection(row,plan,policy))
        row["license_spdx"]="MIT"
        self.assertIn("LICENSE",public_mirror_rejection(row,plan,policy))
        tree["tree"].append(entry("LICENSE",b"MIT"))
        plan=make_plan(row,tree,POLICY)
        self.assertIsNone(public_mirror_rejection(row,plan,policy))

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
        self.assertEqual(meta["license_status"],"license_unknown_no_evidence")
        self.assertEqual(meta["collection_status"],"collected")
        self.assertEqual(meta["collection_scope"],"private_local_catalog")
        self.assertFalse(meta["gasl_claims_exclusive_ownership"])

    def test_download_metadata_preserves_upstream_license_and_non_ownership(self):
        row,tree=fixture()
        row["license_spdx"]="MIT"
        tree["tree"].append(entry("LICENSE",b"MIT License"))
        plan=make_plan(row,tree,{"max_file_size_bytes":1000,"max_skill_size_bytes":5000})
        result=ingest(self.root,plan,lambda p,item:(
            b"MIT License" if item["path"]=="LICENSE" else FILES[item["path"]]))
        meta=json.loads((package_location(self.root,plan)/"source.json").read_text())
        self.assertEqual(meta["license_status"],"license_evidence_bundled_pending_scan")
        self.assertEqual(meta["license_evidence"][0]["source_path"],"LICENSE")
        self.assertEqual(meta["ownership"],"third_party")
        self.assertIsNone(meta["original_author"])
        self.assertFalse(meta["gasl_claims_exclusive_ownership"])
        self.assertIn(COMMIT,meta["source_url"])


    def test_non_allowlisted_license_is_still_collected_with_attribution(self):
        row,tree=fixture()
        row["license_spdx"]="GPL-3.0-only"
        tree["tree"].append(entry("LICENSE",b"GNU GPL v3"))
        plan=make_plan(row,tree,{"max_file_size_bytes":1000,"max_skill_size_bytes":5000})
        result=ingest(self.root,plan,lambda p,item:(
            b"GNU GPL v3" if item["path"]=="LICENSE" else FILES[item["path"]]))
        self.assertEqual(result["status"],"downloaded")
        meta=json.loads((package_location(self.root,plan)/"source.json").read_text())
        self.assertEqual(meta["license_spdx"],"GPL-3.0-only")
        self.assertEqual(meta["license_status"],"license_evidence_bundled_pending_scan")
        self.assertEqual(meta["collection_status"],"collected")
        self.assertEqual(meta["public_mirror_status"],"not_eligible_license_policy")
        self.assertEqual(meta["ownership"],"third_party")
        self.assertFalse(meta["gasl_claims_exclusive_ownership"])

    def test_unknown_license_with_license_file_is_collected_but_not_publicly_eligible(self):
        row,tree=fixture()
        row["license_spdx"]="NOASSERTION"
        tree["tree"].append(entry("LICENSE",b"Terms supplied by upstream"))
        plan=make_plan(row,tree,{"max_file_size_bytes":1000,"max_skill_size_bytes":5000})
        ingest(self.root,plan,lambda p,item:(
            b"Terms supplied by upstream" if item["path"]=="LICENSE" else FILES[item["path"]]))
        meta=json.loads((package_location(self.root,plan)/"source.json").read_text())
        self.assertEqual(meta["license_status"],"license_unknown_evidence_bundled")
        self.assertEqual(meta["public_mirror_status"],"not_eligible_license_policy")

    def test_known_license_without_notice_is_collected(self):
        row,tree=fixture()
        row["license_spdx"]="MIT"
        plan=make_plan(row,tree,POLICY)
        ingest(self.root,plan,lambda p,item:FILES[item["path"]])
        meta=json.loads((package_location(self.root,plan)/"source.json").read_text())
        self.assertEqual(meta["license_status"],"license_evidence_missing_content_collected")
        self.assertEqual(meta["collection_status"],"collected")
        self.assertEqual(meta["public_mirror_status"],"blocked_missing_license_evidence")

    def test_wrong_download_never_promoted(self):
        row,tree=fixture(); plan=make_plan(row,tree,POLICY)
        with self.assertRaises(ValueError): ingest(self.root,plan,lambda p,i:b"bad")
        self.assertFalse(package_location(self.root,plan).exists())

    def test_manifest_refreshes_inventory_when_license_evidence_is_added(self):
        row,tree=fixture()
        plan=make_plan(row,tree,POLICY)
        dest=package_location(self.root,plan)
        manifest={"schema_version":"0.1.0","downloads":[{
            "repository":row["repository"],"commit_sha":COMMIT,
            "skill_packages":[{"skill_path":row["skill_path"],"package_path":str(dest.relative_to(self.root)),
                              "file_count":1,"bytes":10}]
        }]}
        (self.root/"registry/download-manifest.json").write_text(json.dumps(manifest))
        plan["files"].append({"path":"LICENSE","relative":"__upstream_licenses__/license",
                              "size":5,"sha":git_blob(b"MIT!!")})
        plan["bytes"]+=5
        merge_manifest(self.root,plan,dest)
        saved=json.loads((self.root/"registry/download-manifest.json").read_text())
        item=saved["downloads"][0]["skill_packages"][0]
        self.assertEqual(item["file_count"],3)
        self.assertEqual(item["bytes"],plan["bytes"])

    def test_manifest_rejects_different_package_path_for_same_identity(self):
        row,tree=fixture()
        plan=make_plan(row,tree,POLICY)
        dest=package_location(self.root,plan)
        manifest={"schema_version":"0.1.0","downloads":[{
            "repository":row["repository"],"commit_sha":COMMIT,
            "skill_packages":[{"skill_path":row["skill_path"],"package_path":"catalog/other",
                              "file_count":1,"bytes":10}]
        }]}
        (self.root/"registry/download-manifest.json").write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            merge_manifest(self.root,plan,dest)

    def test_existing_extra_file_is_rejected(self):
        row,tree=fixture(); plan=make_plan(row,tree,POLICY)
        ingest(self.root,plan,lambda p,i:FILES[i["path"]])
        (package_location(self.root,plan)/"extra").write_text("unexpected")
        with self.assertRaises(ValueError): ingest(self.root,plan,lambda *_:b"")

    def test_fetch_tree_reconstructs_every_git_object_before_planning(self):
        from queue_ingest import fetch_tree
        from tests.test_canonical_package import blob, tree, directory
        guide=tree(blob("guide.md",b"guide"))
        package=tree(blob("SKILL.md",FILES["skills/demo/SKILL.md"]),directory("references",guide))
        skills=tree(directory("demo",package))
        top=tree(directory("skills",skills),blob("LICENSE",b"terms"))
        entries=top["tree"]+[dict(x,path="skills/"+x["path"]) for x in skills["tree"]]+[
            dict(x,path="skills/demo/"+x["path"]) for x in package["tree"]]+[
            dict(x,path="skills/demo/references/"+x["path"]) for x in guide["tree"]]
        raw=dict(top,tree=entries)
        row,_=fixture();row["tree_sha"]=top["sha"]
        repo={"id":1,"full_name":"Org/Repo"}
        commit={"sha":COMMIT,"tree":{"sha":top["sha"]}}
        with patch("queue_ingest.github_json",side_effect=[repo,commit,raw]) as get:
            plan=make_plan(row,fetch_tree(row),POLICY)
            self.assertEqual(len(plan["files"]),3)
            self.assertEqual(get.call_count,3)
        for bad in (dict(raw,truncated=True),dict(raw,tree=entries[:-1]),
                    dict(raw,tree=entries+[entries[0]]),
                    dict(raw,tree=[dict(x,sha="f"*40) if x["path"]=="LICENSE" else x for x in entries])):
            with self.subTest(bad=bad),patch("queue_ingest.github_json",side_effect=[repo,commit,bad]):
                with self.assertRaises(ValueError):
                    fetch_tree(row)
        with patch("queue_ingest.github_json",return_value={"id":1,"full_name":"other/repo"}) as get:
            with self.assertRaisesRegex(ValueError,"identity mismatch"):
                fetch_tree(row)
            self.assertEqual(get.call_count,1)
        with patch("queue_ingest.github_json",side_effect=[repo,dict(commit,tree=None)]) as get:
            with self.assertRaisesRegex(ValueError,"Commit/tree"):
                fetch_tree(row)
            self.assertEqual(get.call_count,2)

    def test_pinned_transport_bounds_hash_and_redirect(self):
        from queue_ingest import fetch_blob
        from canonical_lineage import NoRedirect
        plan={"repository":"Org/Repo","commit_sha":COMMIT}
        data=b"fixture"
        item={"path":"skills/demo/space name.md","size":len(data),"sha":git_blob(data)}
        url="https://raw.githubusercontent.com/Org/Repo/"+COMMIT+"/skills/demo/space%20name.md"
        response=MagicMock()
        response.__enter__.return_value=response
        response.geturl.return_value=url
        response.read.return_value=data
        with patch("queue_ingest.urllib.request.build_opener") as opener:
            opener.return_value.open.return_value=response
            self.assertEqual(fetch_blob(plan,item),data)
            self.assertIsInstance(opener.call_args.args[0],NoRedirect)
            self.assertEqual(opener.return_value.open.call_args.args[0].full_url,url)
            response.read.assert_called_with(len(data)+1)
            for bad in (b"changed",data+b"x",b""):
                response.read.return_value=bad
                with self.subTest(data=bad),self.assertRaisesRegex(ValueError,"size/hash"):
                    fetch_blob(plan,item)
            response.geturl.return_value=url+"/redirected"
            with self.assertRaisesRegex(ValueError,"endpoint changed"):
                fetch_blob(plan,item)
            opener.return_value.open.side_effect=urllib.error.URLError("fixture failure")
            with self.assertRaisesRegex(RuntimeError,"unavailable"):
                fetch_blob(plan,item)
        with self.assertRaises(urllib.error.HTTPError):
            NoRedirect().redirect_request(urllib.request.Request(url),
                None,302,"redirect",{},"https://raw.githubusercontent.com/elsewhere")

    def test_portable_names_and_boolean_size_rejected(self):
        for name in ("CON","NUL.txt","part:ADS","trailing.","trailing "):
            row,tree=fixture();tree["tree"].append(entry("skills/demo/"+name,b"x"))
            with self.subTest(name=name),self.assertRaises(ValueError):
                make_plan(row,tree,POLICY)
        row,tree=fixture();tree["tree"][0]["size"]=True
        with self.assertRaises(ValueError):
            make_plan(row,tree,POLICY)

    def test_hardlinked_checkpoint_refused(self):
        row,tree=fixture();plan=make_plan(row,tree,POLICY)
        dest=package_location(self.root,plan)
        stage=self.root/"quarantine/queue-ingest"/dest.parent.name/dest.name
        stage.mkdir(parents=True)
        alias=self.root/"sentinel"
        alias.write_bytes(FILES["skills/demo/SKILL.md"])
        os.link(alias,stage/"SKILL.md")
        with self.assertRaisesRegex(ValueError,"hard-linked"):
            ingest(self.root,plan,lambda *_:self.fail("No fetch"))
        self.assertEqual(alias.read_bytes(),FILES["skills/demo/SKILL.md"])
        self.assertFalse(dest.exists())

    def test_atomic_metadata_does_not_touch_fixed_sidecar_or_hardlink(self):
        row,tree=fixture();plan=make_plan(row,tree,POLICY)
        manifest=self.root/"registry/download-manifest.json"
        sentinel=self.root/"sentinel"
        sentinel.write_bytes(b"inert")
        fixed=manifest.with_suffix(".json.tmp")
        os.link(sentinel,fixed)
        merge_manifest(self.root,plan,package_location(self.root,plan))
        self.assertEqual(sentinel.read_bytes(),b"inert")
        self.assertEqual(fixed.read_bytes(),b"inert")
        self.assertFalse(list(manifest.parent.glob(".gasl-metadata-*")))
        manifest.unlink()
        os.link(sentinel,manifest)
        with self.assertRaisesRegex(ValueError,"hard-linked"):
            merge_manifest(self.root,plan,package_location(self.root,plan))

    def test_root_location_requires_explicit_review(self):
        row,_=fixture()
        with self.assertRaisesRegex(ValueError,"root-skill-scope"):
            package_location(self.root,dict(row,skill_path="SKILL.md"))

    def test_local_symlink_fails(self):
        row,tree=fixture(); plan=make_plan(row,tree,POLICY)
        (self.root/"catalog").symlink_to(self.root/"registry",target_is_directory=True)
        with self.assertRaises(ValueError): ingest(self.root,plan,lambda *_:b"")
