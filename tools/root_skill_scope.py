"""Collect explicitly selected root Skill files into isolated private review storage.

Never publish, promote to the ordinary catalog, install, or execute a Skill.
"""
import hashlib
import json
import os
import re
import stat
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import quote

from canonical_index import ROOT, _read_raw, _selected
from canonical_lineage import NoRedirect
from canonical_package import _context_kind
from root_skill_review import inspect_root_skill, MAX_FILES, MAX_BYTES, MAX_FILE_BYTES
from queue_ingest import safe_path, collision_key, git_blob
from transaction_file_lock import require_windows_filename_safety, exclusive_lock_file
from static_scan import scan_package

SHA = re.compile(r"[0-9a-f]{64}")
GIT_SHA = re.compile(r"[0-9a-f]{40}")
SOURCE_ID = re.compile(r"GASL-SRC-[0-9a-f]{20}")
SCHEMA = "gasl-root-selected-scope-v1"
MAX_PLAN_BYTES = 1024 * 1024


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",",":")).encode("utf-8")


def _digest(plan):
    return hashlib.sha256(_encoded(plan)).hexdigest()


def _matches(pattern, value):
    return isinstance(value,str) and pattern.fullmatch(value) is not None


def _validate_plan(plan):
    required = {"schema","source_record_id","repository","commit_sha","tree_sha",
                "review_sha256","requested_paths","files","bytes"}
    if (not isinstance(plan,dict) or set(plan)!=required or plan["schema"]!=SCHEMA
            or not _matches(SOURCE_ID,plan["source_record_id"])
            or not _matches(GIT_SHA,plan["commit_sha"]) or not _matches(GIT_SHA,plan["tree_sha"])
            or not _matches(SHA,plan["review_sha256"])
            or not isinstance(plan["repository"],str)
            or not isinstance(plan["requested_paths"],list)
            or not isinstance(plan["files"],list)
            or not 1 <= len(plan["files"]) <= MAX_FILES):
        raise ValueError("Invalid selected scope plan")
    if any(not isinstance(p,str) for p in plan["requested_paths"]):
        raise ValueError("Invalid requested paths")
    if plan["requested_paths"] != sorted(set(plan["requested_paths"])) or "SKILL.md" not in plan["requested_paths"]:
        raise ValueError("Explicit unique SKILL.md selection required")
    paths, spellings, leaves = [], {}, set()
    total = 0
    for item in plan["files"]:
        if (not isinstance(item,dict) or set(item)!={"path","mode","git_blob_sha","bytes"}
                or item["mode"] not in ("100644","100755") or not _matches(GIT_SHA,item["git_blob_sha"])
                or type(item["bytes"]) is not int or not 0 <= item["bytes"] <= MAX_FILE_BYTES):
            raise ValueError("Invalid selected file metadata")
        path = safe_path(item["path"])
        require_windows_filename_safety(path, portable=True)
        if any(p.casefold() in {"source.json","source.json.tmp",".gasl-download-checkpoint.json"} for p in path.split("/")):
            raise ValueError("Reserved selected file path")
        paths.append(path)
        total += item["bytes"]
        parts = path.split("/")
        for n in range(1,len(parts)+1):
            prefix = "/".join(parts[:n])
            key = collision_key(prefix)
            if key in spellings and spellings[key] != prefix:
                raise ValueError("Selected scope path collision")
            spellings[key] = prefix
        key = collision_key(path)
        if key in leaves:
            raise ValueError("Duplicate selected path")
        leaves.add(key)
    if (paths != sorted(paths) or not set(plan["requested_paths"]).issubset(paths)
            or type(plan["bytes"]) is not int or total != plan["bytes"] or total > MAX_BYTES):
        raise ValueError("Invalid selected scope inventory or size")
    if any("/".join(p.split("/")[:i]) in leaves for p in leaves for i in range(1,len(p.split("/")))):
        raise ValueError("Selected file/directory collision")
    return plan


def make_scope(review, requested):
    if (not isinstance(requested,(list,tuple)) or not requested
            or len(requested)>MAX_FILES or any(not isinstance(p,str) for p in requested)
            or len(set(requested))!=len(requested) or "SKILL.md" not in requested):
        raise ValueError("Select exact unique paths, including SKILL.md")
    if any(x["reason"]!="candidate_inventory_budget_exceeded" for x in review["blocked_entries"]):
        raise ValueError("Unsafe root inventory requires review before collection")
    files = {x["path"]:x for x in review["candidate_files"]}
    if any(p not in files for p in requested):
        raise ValueError("Selected path is not a verified inventory candidate")
    selected = set(requested)
    ancestors = {""}
    for path in requested:
        parts = path.split("/")
        ancestors.update("/".join(parts[:i]) for i in range(1,len(parts)))
    # Include ordinary root/ancestor license-notice candidates in the preview;
    # do not infer legal applicability or include unrelated repository contents.
    selected.update(p for p in files if p.rpartition("/")[0] in ancestors
                    and _context_kind(p.rsplit("/",1)[-1])=="license_notice_filename")
    plan = {"schema":SCHEMA,"source_record_id":review["source_record_id"],
            "repository":review["repository"],"commit_sha":review["commit_sha"],
            "tree_sha":review["tree_sha"],"review_sha256":review["review_sha256"],
            "requested_paths":sorted(requested),"files":[files[p] for p in sorted(selected)],
            "bytes":sum(files[p]["bytes"] for p in selected)}
    return _validate_plan(plan)


def _checked_path(root,path):
    current = root
    for part in path.relative_to(root).parts:
        current = current/part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info,"st_file_attributes",0)&0x400:
            raise ValueError("Redirected review storage path")
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise ValueError("Nonregular review storage path")
        if stat.S_ISREG(info.st_mode) and info.st_nlink!=1:
            raise ValueError("Hard-linked review storage file")
    return path


def _read(root,path,limit):
    _checked_path(root,path)
    if not path.is_file() or path.stat().st_size>limit:
        raise ValueError("Missing or oversized review file")
    with path.open("rb") as stream:
        raw=stream.read(limit+1)
    if len(raw)>limit:
        raise ValueError("Oversized review file")
    return raw


def _json(raw):
    def unique(items):
        out={}
        for k,v in items:
            if k in out:
                raise ValueError("Duplicate review JSON key")
            out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=unique)


def _fetch(plan,item):
    url="https://raw.githubusercontent.com/"+plan["repository"]+"/"+plan["commit_sha"]+"/"+quote(item["path"],safe="/")
    req=urllib.request.Request(url,headers={"User-Agent":"GASL/0.1","Accept":"application/octet-stream"})
    with urllib.request.build_opener(NoRedirect()).open(req,timeout=20) as response:
        if response.geturl()!=url:
            raise ValueError("Pinned raw endpoint changed")
        return response.read(item["bytes"]+1)


def _verify_bytes(data,item):
    if len(data)!=item["bytes"] or git_blob(data)!=item["git_blob_sha"]:
        raise ValueError("Selected file size or Git blob mismatch: "+item["path"])


def _write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_BINARY",0),0o600)
    with os.fdopen(fd,"wb") as stream:
        stream.write(data)


def _destination(root,source_id,plan_sha):
    if not _matches(SOURCE_ID,source_id) or not _matches(SHA,plan_sha):
        raise ValueError("Exact source ID and plan SHA-256 required")
    return _checked_path(root,root/"private"/"root-skill-scopes"/source_id/plan_sha)


def _verify_scope(root,folder,plan,plan_sha):
    if _digest(plan)!=plan_sha or _json(_read(root,folder/"plan.json",MAX_PLAN_BYTES))!=plan:
        raise ValueError("Selected plan digest or stored plan mismatch")
    package=folder/"catalog"/"selection"
    records=[]
    expected={"plan.json","catalog/selection/source.json"}
    for item in plan["files"]:
        local="catalog/selection/"+item["path"]
        data=_read(root,folder/local,item["bytes"])
        _verify_bytes(data,item)
        records.append({"source_path":item["path"],"local_path":local,"size_bytes":len(data),
                        "sha256":hashlib.sha256(data).hexdigest(),"git_blob_sha":item["git_blob_sha"]})
        expected.add(local)
    meta={"repository":plan["repository"],"source_skill_path":"SKILL.md",
          "commit_sha":plan["commit_sha"],"package_complete":False,
          "collection_scope":"private_root_selected_review_only","files":records}
    if _json(_read(root,package/"source.json",MAX_PLAN_BYTES))!=meta:
        raise ValueError("Selected review inventory changed")
    dirs={str(Path(p).parent.as_posix()) for p in expected}
    for p in list(dirs):
        dirs.update(a.as_posix() for a in Path(p).parents)
    actual=set()
    pending=[folder]
    count=0
    while pending:
        for path in pending.pop().iterdir():
            count+=1
            if count>MAX_FILES*(24)+10:
                raise ValueError("Review storage entry budget exceeded")
            _checked_path(root,path)
            rel=path.relative_to(folder).as_posix()
            if path.is_dir():
                if rel not in dirs:
                    raise ValueError("Unexpected review storage directory")
                pending.append(path)
            elif path.is_file():
                actual.add(rel)
    if actual!=expected:
        raise ValueError("Unexpected or missing selected review files")
    result=scan_package(package/"source.json",root=folder,persist=False)
    if not result["integrity_ok"]:
        raise ValueError("Selected review static scan integrity failure")
    return {k:result[k] for k in ("security_status","integrity_ok","finding_count",
                                 "actionable_finding_count","informational_finding_count","high_confidence_signals")}


def _result(plan,plan_sha,status,**extra):
    return {"status":status,"plan_sha256":plan_sha,"plan":plan,
            "package_complete":False,"complete_install_package_verified":False,
            "installation_or_execution_approved":False,"public_redistribution_approved":False,
            "ordinary_catalog_modified":False,"external_dependencies_verified":False,
            **extra}


def collect_scope(source_id,requested,*,root=ROOT,execute=False,acknowledge=None):
    root=Path(root).resolve()
    if execute and not _matches(SHA,acknowledge):
        raise ValueError("Execute requires the exact preview plan SHA-256")
    if not execute and acknowledge is not None:
        raise ValueError("Plan acknowledgement requires --execute")
    if (not isinstance(requested,(list,tuple)) or not requested or len(requested)>MAX_FILES
            or any(not isinstance(p,str) for p in requested)
            or len(set(requested))!=len(requested) or "SKILL.md" not in requested):
        raise ValueError("Select exact unique paths, including SKILL.md")
    review=inspect_root_skill(source_id,root=root)
    plan=make_scope(review,requested)
    plan_sha=_digest(plan)
    if not execute:
        return _result(plan,plan_sha,"planned",blob_contents_downloaded=False)
    if acknowledge!=plan_sha:
        raise ValueError("Selected plan changed or acknowledgement mismatch")
    dest=_destination(root,source_id,plan_sha)
    base=_checked_path(root,dest.parent)
    base.mkdir(parents=True,exist_ok=True)
    with exclusive_lock_file(_checked_path(root,base/".scope.lock"),attempts=1,nonblocking=True):
        if _read_raw(root)[1]!=review["catalog_sha256"]:
            raise ValueError("Catalog changed before collection")
        if dest.exists():
            scan=_verify_scope(root,dest,plan,plan_sha)
            return _result(plan,plan_sha,"already_verified",blob_contents_downloaded=False,
                           private_review_path=dest.relative_to(root).as_posix(),**scan)
        with tempfile.TemporaryDirectory(prefix=".gasl-root-stage-",dir=base) as temporary:
            folder=Path(temporary)/"scope"
            folder.mkdir(mode=0o700)
            records=[]
            for item in plan["files"]:
                data=_fetch(plan,item)
                _verify_bytes(data,item)
                local="catalog/selection/"+item["path"]
                _write(folder/local,data)
                records.append({"source_path":item["path"],"local_path":local,"size_bytes":len(data),
                                "sha256":hashlib.sha256(data).hexdigest(),"git_blob_sha":item["git_blob_sha"]})
            meta={"repository":plan["repository"],"source_skill_path":"SKILL.md",
                  "commit_sha":plan["commit_sha"],"package_complete":False,
                  "collection_scope":"private_root_selected_review_only","files":records}
            _write(folder/"plan.json",_encoded(plan))
            _write(folder/"catalog/selection/source.json",_encoded(meta))
            scan=_verify_scope(root,folder,plan,plan_sha)
            if _read_raw(root)[1]!=review["catalog_sha256"] or dest.exists():
                raise ValueError("Catalog or destination changed during collection")
            folder.rename(dest)
    return _result(plan,plan_sha,"collected_private_review",blob_contents_downloaded=True,
                   private_review_path=dest.relative_to(root).as_posix(),**scan)


def audit_scope(source_id,plan_sha,*,root=ROOT):
    root=Path(root).resolve()
    folder=_destination(root,source_id,plan_sha)
    plan=_validate_plan(_json(_read(root,folder/"plan.json",MAX_PLAN_BYTES)))
    if plan["source_record_id"]!=source_id or _digest(plan)!=plan_sha:
        raise ValueError("Selected scope identity or digest mismatch")
    rows,_,_=_selected(root,[source_id])
    row=rows[0]
    if (row.get("source_path")!="SKILL.md" or row.get("snapshot_status")!="verified_commit_pinned"
            or any(row.get(k)!=plan[k] for k in ("repository","commit_sha","tree_sha"))
            or next(x["git_blob_sha"] for x in plan["files"] if x["path"]=="SKILL.md")!=row.get("skill_md_blob_sha")):
        raise ValueError("Selected scope no longer matches exact catalog identity")
    scan=_verify_scope(root,folder,plan,plan_sha)
    return _result(plan,plan_sha,"offline_verified",blob_contents_downloaded=False,
                   private_review_path=folder.relative_to(root).as_posix(),**scan)
