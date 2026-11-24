"""Repository metadata and commit relationships must not become Skill equivalence."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools"))
from canonical_lineage import inspect_lineage, _ancestor, _repo_relations, _get, NoRedirect
from tests.test_canonical_index import record
import urllib.error
import urllib.request


def repo(name, ident, fork=False, **extra):
    return dict(full_name=name,id=ident,fork=fork,**extra)


class CanonicalLineageTests(unittest.TestCase):
    def fixture(self, rows):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        path = root/"registry/source-catalog.json"
        path.parent.mkdir()
        path.write_text(json.dumps({"schema_version":"1.0.0","records":rows}),encoding="utf-8")
        return root, path, [r["source_record_id"] for r in rows]

    def test_direct_fork_requires_matching_parent_id_and_name(self):
        a=repo("org/repo",1,True,parent=repo("other/repo",2))
        b=repo("other/repo",2)
        self.assertEqual(_repo_relations(a,b,"org/repo","other/repo"),
                         [{"relationship":"repository_direct_fork_of","from_repository":"org/repo","to_repository":"other/repo"}])
        for parent in (repo("other/repo",3),repo("wrong/repo",2)):
            with self.subTest(parent=parent), self.assertRaises(ValueError):
                _repo_relations(dict(a,parent=parent),b,"org/repo","other/repo")

    def test_mirror_requires_exact_explicit_github_identity(self):
        b=repo("other/repo",2)
        for url,expected in (("https://github.com/other/repo.git",True),
                             ("https://github.com.evil.invalid/other/repo",False),
                             ("https://user@github.com/other/repo",False),
                             ("https://github.com/other/repo?x=1",False),
                             (None,False)):
            with self.subTest(url=url):
                relations=_repo_relations(repo("org/repo",1,mirror_url=url),b,"org/repo","other/repo")
                self.assertEqual(bool(relations),expected)

    def test_compare_states_and_inconsistent_counts(self):
        a,b,c="a"*40,"b"*40,"c"*40
        for status, ahead,behind,merge,expected in (
            ("ahead",2,0,a,"left_commit_ancestor_of_right"),
            ("behind",0,2,b,"right_commit_ancestor_of_left"),
            ("diverged",2,1,c,"diverged_commits_reported")):
            data={"base_commit":{"sha":a},"merge_base_commit":{"sha":merge},
                  "status":status,"ahead_by":ahead,"behind_by":behind}
            self.assertEqual(_ancestor(data,a,b),expected)
            with self.assertRaises(ValueError):
                _ancestor(dict(data,base_commit={"sha":c}),a,b)
        with self.assertRaises(ValueError):
            _ancestor({"base_commit":None},a,b)

    def test_real_shape_same_repo_pin_requests_and_no_writes(self):
        rows=[record(),record(commit="c"*40,blob=None)]
        root,path,ids=self.fixture(rows)
        before=path.read_bytes()
        replies=[repo("org/repo",1),{"sha":"a"*40},{"sha":"c"*40},
                 {"base_commit":{"sha":"a"*40},"merge_base_commit":{"sha":"a"*40},
                  "status":"ahead","ahead_by":2,"behind_by":0}]
        def fetch(endpoint):
            return replies.pop(0),{"endpoint":endpoint,"response_sha256":"f"*64}
        with patch("canonical_lineage._get",side_effect=fetch) as get:
            report=inspect_lineage(ids,root=root)
        self.assertEqual(get.call_count,4)
        self.assertEqual(report["commit_ancestry_reported_by_github"],"left_commit_ancestor_of_right")
        self.assertFalse(report["skill_level_relations_established"])
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(list(root.rglob("*")),[path.parent,path])

    def test_equal_blob_not_repository_lineage_and_drift_refused(self):
        root,path,ids=self.fixture([record(),record(repo="other/repo")])
        responses=[repo("org/repo",1),repo("other/repo",2)]
        def fetch(endpoint):
            return responses.pop(0),{"endpoint":endpoint,"response_sha256":"f"*64}
        with patch("canonical_lineage._get",side_effect=fetch):
            report=inspect_lineage(ids,root=root)
        self.assertEqual(report["repository_relations_reported_by_github"],[])
        self.assertFalse(report["package_equivalence_established"])
        responses[:]=[repo("org/repo",1),repo("other/repo",2)]
        def changed(endpoint):
            path.write_bytes(path.read_bytes()+b" ")
            return fetch(endpoint)
        with patch("canonical_lineage._get",side_effect=changed),self.assertRaisesRegex(ValueError,"Catalog changed"):
            inspect_lineage(ids,root=root)

    def test_unrelated_pair_never_contacts_api(self):
        root,_,ids=self.fixture([record(),record(repo="other/repo",blob="f"*40)])
        with patch("canonical_lineage._get",side_effect=AssertionError("No network")),self.assertRaises(ValueError):
            inspect_lineage(ids,root=root)

    def test_metadata_transport_redirect_and_duplicate_json_refused(self):
        request=urllib.request.Request("https://api.github.com/repos/org/repo")
        with self.assertRaises(urllib.error.HTTPError):
            NoRedirect().redirect_request(request,None,302,"redirect",{},"https://api.github.com/repos/other/repo")
        response=MagicMock()
        response.__enter__.return_value=response
        response.geturl.return_value=request.full_url
        response.read.return_value=b'{"id":1,"id":2}'
        with patch("urllib.request.build_opener") as opener:
            opener.return_value.open.return_value=response
            with self.assertRaisesRegex(ValueError,"Duplicate metadata"):
                _get("/repos/org/repo")


if __name__=="__main__":
    unittest.main()
