"""Opt-in offline full-corpus E5 retrieval over public attributed metadata.

No network, automatic model acquisition, third-party Skill execution or changes
to the default lexical search/Router. The local derived cache is not published.
"""
import hashlib
import heapq
import json
import math
import os
import struct
import tempfile
from pathlib import Path

from canonical_index import ROOT, _read_catalog, build_index as validate_catalog
from path_rules import is_test_fixture_path
from queue_ingest import no_symlink
from search_features import load_features
from semantic_experiment import E5Encoder, MODEL_REPO, MODEL_REVISION, MODEL_FILES, MODEL_UPSTREAM_PATHS, passage
from transaction_file_lock import exclusive_lock_file

SCHEMA = "gasl-public-semantic-index-v1"
DIMENSIONS = 384
VECTOR = struct.Struct("<"+"f"*DIMENSIONS)
MAGIC = b"GASL-DENSE-V1\n"
MAX_HEADER = 16384
MAX_QUERY_CHARS = 4096
MAX_PASSAGE_CHARS = 4096
BATCH = 16
CACHE = "private/semantic-index-v1.bin"


def _json(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode("utf-8")


def _snapshot(root):
    records,catalog_digest = _read_catalog(root)
    validate_catalog(records)
    features=load_features(root,records)
    rows=[]
    digest=hashlib.sha256()
    for row in sorted(records,key=lambda r:r["source_record_id"]):
        if (row.get("snapshot_status")!="verified_commit_pinned"
                or is_test_fixture_path(row["source_path"])
                or row.get("package_type")=="test_fixture"
                or row.get("security_status")=="integrity_failed"):
            continue
        sid=row["source_record_id"]
        text=passage({**row,"verified_feature_terms":features.get(sid,{}).get("terms",[])})[:MAX_PASSAGE_CHARS]
        digest.update(_json([sid,text])+b"\n")
        rows.append((row,text))
    if not rows:
        raise ValueError("No eligible public catalog records for semantic retrieval")
    header={"schema":SCHEMA,"model_repository":MODEL_REPO,"model_revision":MODEL_REVISION,
            "model_files":{name:{"bytes":size,"sha256":sha,"upstream_path":MODEL_UPSTREAM_PATHS[name]} for name,(size,sha) in MODEL_FILES.items()},
            "dimensions":DIMENSIONS,"record_count":len(rows),"passage_sha256":digest.hexdigest(),
            "embedding_policy":"e5-mean-pool-l2-128-tokens-v1"}
    return rows,header,catalog_digest


def _vector(values):
    try:
        data=VECTOR.pack(*values)
        normalized=VECTOR.unpack(data)
    except (TypeError,ValueError,OverflowError,struct.error) as exc:
        raise ValueError("Invalid semantic vector dimension or value") from exc
    if (not all(math.isfinite(v) for v in normalized)
            or abs(math.fsum(v*v for v in normalized)-1)>0.002):
        raise ValueError("Semantic vector must be finite and unit-normalized")
    return data,normalized


def _encoder(model,threads,encoder_factory):
    if not 1<=threads<=4:
        raise ValueError("Semantic threads must be 1..4")
    if model is None:
        raise ValueError("Explicit local pinned model directory required")
    try:
        return encoder_factory(model,threads=threads)
    except ImportError as exc:
        raise ValueError("Optional numpy, onnxruntime and tokenizers are required; no automatic installation") from exc


def _read_exact(stream,size):
    data=stream.read(size)
    if len(data)!=size:
        raise ValueError("Truncated semantic cache")
    return data


def _scan_cache(root,header,visitor=None):
    path=no_symlink(root,root/CACHE)
    expected_header=_json(header)
    size=len(MAGIC)+4+len(expected_header)+header["record_count"]*VECTOR.size+32
    if not path.is_file():
        raise FileNotFoundError("Build the optional local semantic index first")
    if path.stat().st_size!=size:
        raise ValueError("Semantic cache is stale or damaged; rebuild explicitly")
    with path.open("rb") as stream:
        if _read_exact(stream,len(MAGIC))!=MAGIC:
            raise ValueError("Invalid semantic cache format")
        n=struct.unpack("<I",_read_exact(stream,4))[0]
        if not 0<n<=MAX_HEADER or _read_exact(stream,n)!=expected_header:
            raise ValueError("Semantic cache inputs changed; rebuild explicitly")
        digest=hashlib.sha256(expected_header)
        for i in range(header["record_count"]):
            raw=_read_exact(stream,VECTOR.size)
            _,values=_vector(VECTOR.unpack(raw))
            digest.update(raw)
            if visitor is not None:
                visitor(i,values)
        if _read_exact(stream,32)!=digest.digest() or stream.read(1):
            raise ValueError("Semantic cache digest mismatch")
    return digest.hexdigest()


def status(root=ROOT):
    root=Path(root).resolve()
    _,header,catalog_digest=_snapshot(root)
    try:
        digest=_scan_cache(root,header)
    except FileNotFoundError:
        return {"status":"not_built","index":header,"catalog_sha256":catalog_digest,"default_search_changed":False}
    except (OSError,ValueError):
        return {"status":"stale_or_invalid","index":header,"catalog_sha256":catalog_digest,"default_search_changed":False}
    return {"status":"verified_local_cache","index":header,"catalog_sha256":catalog_digest,"cache_payload_sha256":digest,
            "default_search_changed":False}


def build(model,*,root=ROOT,threads=2,encoder_factory=E5Encoder):
    root=Path(root).resolve()
    rows,header,catalog_digest=_snapshot(root)
    path=no_symlink(root,root/CACHE)
    encoder=_encoder(model,threads,encoder_factory)
    parent=no_symlink(root,path.parent)
    parent.mkdir(exist_ok=True)
    lock=no_symlink(root,parent/".semantic-index.lock")
    with exclusive_lock_file(lock,attempts=1,nonblocking=True):
        fd,name=tempfile.mkstemp(prefix=".gasl-dense-",suffix=".tmp",dir=parent)
        temp=Path(name)
        try:
            encoded=_json(header)
            digest=hashlib.sha256(encoded)
            with os.fdopen(fd,"wb") as stream:
                stream.write(MAGIC+struct.pack("<I",len(encoded))+encoded)
                for start in range(0,len(rows),BATCH):
                    batch=rows[start:start+BATCH]
                    vectors=encoder.encode([text for _,text in batch],batch=BATCH)
                    if len(vectors)!=len(batch):
                        raise ValueError("Semantic encoder returned wrong batch size")
                    for values in vectors:
                        raw,_=_vector(values)
                        stream.write(raw)
                        digest.update(raw)
                stream.write(digest.digest())
                stream.flush()
                os.fsync(stream.fileno())
            if _snapshot(root)[1]!=header:
                raise ValueError("Semantic inputs changed during build")
            no_symlink(root,path)
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
    return {"status":"built","index":header,"cache_payload_sha256":_scan_cache(root,header),
            "default_search_changed":False,"third_party_skill_executed":False}


def search(query,model,*,root=ROOT,limit=10,threads=2,license_spdx=None,
           encoder_factory=E5Encoder):
    if not isinstance(query,str) or not query.strip() or len(query)>MAX_QUERY_CHARS:
        raise ValueError("Nonempty semantic query up to 4096 characters required")
    if type(limit) is not int or not 1<=limit<=100:
        raise ValueError("Semantic limit must be 1..100")
    root=Path(root).resolve()
    rows,header,catalog_digest=_snapshot(root)
    # Reject stale data before loading the optional model.
    _scan_cache(root,header)
    encoder=_encoder(model,threads,encoder_factory)
    vectors=encoder.encode(["query: "+query.strip()],batch=1)
    if len(vectors)!=1:
        raise ValueError("Unexpected semantic query vector count")
    _,query_vector=_vector(vectors[0])
    heap=[]
    def score(i,vector):
        row=rows[i][0]
        if license_spdx and str(row.get("license_spdx") or "").casefold()!=license_spdx.casefold():
            return
        similarity=math.fsum(a*b for a,b in zip(vector,query_vector))
        # Tie break by stable ascending source ID (rows sorted by ID).
        item=(similarity,-i)
        if len(heap)<limit:
            heapq.heappush(heap,item)
        elif item>heap[0]:
            heapq.heapreplace(heap,item)
    digest=_scan_cache(root,header,score)
    _,fresh_header,fresh_catalog_digest=_snapshot(root)
    if fresh_header!=header or fresh_catalog_digest!=catalog_digest:
        raise ValueError("Semantic inputs changed during search")
    results=[]
    for similarity,negative_i in sorted(heap,reverse=True):
        row=rows[-negative_i][0]
        results.append({**{k:row.get(k) for k in ("source_record_id","skill_name","description",
            "repository","source_path","source_url","commit_sha","skill_md_blob_sha","license_spdx","security_status")},
            "semantic_similarity":round(similarity,6),"installation_allowed":False,
            "execution_allowed":False})
    return {"status":"experimental_public_metadata_dense_retrieval","query":query,
            "eligible_record_count":len(rows),"count":len(results),"results":results,
            "cache_payload_sha256":digest,"catalog_sha256":catalog_digest,"default_search_changed":False,"local_security_state_verified":False,
            "ranking_quality_independently_verified":False,"third_party_skill_executed":False}
