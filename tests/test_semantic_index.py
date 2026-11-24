"""Full-corpus cache and ranking tests using deterministic inert encoder fixtures."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from semantic_index import build, search, status, CACHE, DIMENSIONS
from tests.test_canonical_index import record

class InertEncoder:
    def __init__(self,model,threads=2):
        pass
    def encode(self,texts,batch=16):
        vectors=[]
        for text in texts:
            # Query and matching public record deliberately share a test vector.
            index=0 if "match" in text else 1
            vector=[0.0]*DIMENSIONS;vector[index]=1.0
            vectors.append(vector)
        return vectors

class SemanticIndexTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name).resolve()
        self.catalog=self.root/"registry/source-catalog.json"
        self.catalog.parent.mkdir()
        self.rows=[]
        for path,name,license in (("a/SKILL.md","unrelated","MIT"),("b/SKILL.md","match","GPL-3.0"),
            ("tests/fixtures/c/SKILL.md","match","MIT"),("d/SKILL.md","match","MIT")):
            row=record(path=path)
            row.update(skill_name=name,description="",license_spdx=license,snapshot_status="verified_commit_pinned")
            self.rows.append(row)
        self.rows[-1]["security_status"]="integrity_failed"
        self.save()

    def save(self):
        self.catalog.write_text(json.dumps({"schema_version":"1.0.0","records":self.rows}),encoding="utf-8")

    def build(self):
        return build("fixture",root=self.root,encoder_factory=InertEncoder)

    def test_full_corpus_cache_ranking_filters_and_no_default_index(self):
        self.assertEqual(status(self.root)["status"],"not_built")
        self.assertFalse((self.root/"private").exists())
        report=self.build()
        self.assertEqual(report["index"]["record_count"],2)
        self.assertEqual(status(self.root)["status"],"verified_local_cache")
        self.assertFalse((self.root/"registry/gasl-search.sqlite3").exists())
        result=search("match","fixture",root=self.root,encoder_factory=InertEncoder)
        self.assertEqual(result["count"],2)
        self.assertEqual(result["results"][0]["source_path"],"b/SKILL.md")
        self.assertEqual(result["results"][0]["semantic_similarity"],1.0)
        self.assertFalse(result["results"][0]["installation_allowed"])
        filtered=search("match","fixture",root=self.root,license_spdx="mit",encoder_factory=InertEncoder)
        self.assertEqual([x["source_path"] for x in filtered["results"]],["a/SKILL.md"])
        self.assertFalse(result["default_search_changed"])

    def test_metadata_change_and_cache_corruption_fail_closed(self):
        self.build()
        self.rows[0]["description"]="changed metadata";self.save()
        self.assertEqual(status(self.root)["status"],"stale_or_invalid")
        with self.assertRaises(ValueError):
            search("match","fixture",root=self.root,encoder_factory=InertEncoder)
        self.build()
        path=self.root/CACHE
        raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
        self.assertEqual(status(self.root)["status"],"stale_or_invalid")

    def test_bad_encoder_does_not_replace_prior_cache(self):
        self.build();path=self.root/CACHE;before=path.read_bytes()
        class BadEncoder(InertEncoder):
            def encode(self,texts,batch=16):
                return [[float("nan")]*DIMENSIONS for _ in texts]
        with self.assertRaisesRegex(ValueError,"finite"):
            build("fixture",root=self.root,encoder_factory=BadEncoder)
        self.assertEqual(path.read_bytes(),before)
        self.assertFalse(list(path.parent.glob(".gasl-dense-*.tmp")))

    def test_metadata_drift_during_query_is_rejected_even_without_vector_change(self):
        self.build()
        outer=self
        class DriftEncoder(InertEncoder):
            def encode(self,texts,batch=16):
                outer.rows[1]["license_spdx"]="MIT"
                outer.save()
                return super().encode(texts,batch)
        with self.assertRaisesRegex(ValueError,"inputs changed during search"):
            search("match","fixture",root=self.root,encoder_factory=DriftEncoder)
        self.assertEqual(status(self.root)["status"],"verified_local_cache")

    def test_public_metadata_only_and_missing_model_no_writes(self):
        private=self.root/"private";private.mkdir()
        (private/"skill-metadata-cache.json").write_text('{"records":{"private":"ignored"}}')
        with self.assertRaisesRegex(ValueError,"Explicit local pinned"):
            build(None,root=self.root,encoder_factory=InertEncoder)
        self.assertFalse((self.root/CACHE).exists())
        before=self.build()["index"]["passage_sha256"]
        (private/"skill-metadata-cache.json").write_text('{"records":{"changed":"ignored"}}')
        self.assertEqual(status(self.root)["index"]["passage_sha256"],before)

if __name__=="__main__":
    unittest.main()
