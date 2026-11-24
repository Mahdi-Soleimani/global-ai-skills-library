"""Explicit public GitHub metadata evidence, never Skill-level equivalence."""
import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlsplit

from canonical_index import _selected, _identity, _read_catalog, SHA1, ROOT

MAX_RESPONSE = 4 * 1024 * 1024
API = "https://api.github.com"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Metadata redirect refused", headers, fp)


def _get(path):
    url = API + path
    request = urllib.request.Request(url, headers={"User-Agent":"GASL/0.1",
            "Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as response:
            if response.geturl() != url:
                raise ValueError("Metadata endpoint changed")
            raw = response.read(MAX_RESPONSE + 1)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ValueError("Public GitHub metadata unavailable; relation remains unverified") from exc
    if len(raw) > MAX_RESPONSE:
        raise ValueError("Metadata response exceeds limit")
    def unique(pairs):
        out = {}
        for k,v in pairs:
            if k in out:
                raise ValueError("Duplicate metadata JSON key")
            out[k] = v
        return out
    data = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(data, dict):
        raise ValueError("Invalid GitHub metadata response")
    return data, {"endpoint":url,"response_sha256":hashlib.sha256(raw).hexdigest()}


def _repo_identity(data, name):
    if (not isinstance(data, dict) or type(data.get("id")) is not int or data["id"] <= 0
            or not isinstance(data.get("full_name"),str)
            or data["full_name"].casefold() != name.casefold()):
        raise ValueError("Repository metadata identity mismatch")
    return data["id"]


def _mirror_matches(value, name):
    if not isinstance(value,str):
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == "https" and parsed.netloc.lower() == "github.com"
                and not parsed.query and not parsed.fragment
                and parsed.path.rstrip("/").removesuffix(".git").casefold() == "/"+name.casefold())
    except ValueError:
        return False


def _repo_relations(left, right, left_name, right_name):
    lid, rid = _repo_identity(left,left_name), _repo_identity(right,right_name)
    if lid == rid:
        raise ValueError("Distinct repository names share a repository ID; alias review required")
    relations = []
    for child, parent, cname, pname, pid in (
        (left,right,left_name,right_name,rid), (right,left,right_name,left_name,lid)):
        if type(child.get("fork")) is not bool or type(parent.get("fork")) is not bool:
            raise ValueError("Invalid repository fork metadata")
        if child["fork"] and isinstance(child.get("parent"),dict):
            ref = child["parent"]
            if ref.get("id") == pid or str(ref.get("full_name","")).casefold() == pname.casefold():
                _repo_identity(ref,pname)
                if ref["id"] != pid:
                    raise ValueError("Fork parent repository ID mismatch")
                relations.append({"relationship":"repository_direct_fork_of",
                                  "from_repository":cname,"to_repository":pname})
        if _mirror_matches(child.get("mirror_url"),pname):
            relations.append({"relationship":"repository_reported_mirror_of",
                              "from_repository":cname,"to_repository":pname})
    return relations


def _sha(value):
    if not isinstance(value,str) or not SHA1.fullmatch(value):
        raise ValueError("Invalid commit metadata pin")
    return value


def _ancestor(data, base, head):
    base_data, merge_data = data.get("base_commit"), data.get("merge_base_commit")
    if not isinstance(base_data,dict) or not isinstance(merge_data,dict):
        raise ValueError("Missing compare commit metadata")
    if _sha(base_data.get("sha")) != base:
        raise ValueError("Compare base pin mismatch")
    merge = _sha(merge_data.get("sha"))
    ahead, behind = data.get("ahead_by"), data.get("behind_by")
    if any(type(x) is not int or x < 0 for x in (ahead,behind)):
        raise ValueError("Invalid compare counts")
    status = data.get("status")
    if status == "ahead" and ahead > 0 and behind == 0 and merge == base:
        return "left_commit_ancestor_of_right"
    if status == "behind" and behind > 0 and ahead == 0 and merge == head:
        return "right_commit_ancestor_of_left"
    if status == "diverged" and ahead > 0 and behind > 0 and merge not in (base,head):
        return "diverged_commits_reported"
    if status == "identical" and ahead == behind == 0 and base == head == merge:
        return "identical_commit"
    raise ValueError("Inconsistent compare metadata")


def inspect_lineage(ids, *, root=ROOT):
    if (not isinstance(ids,(list,tuple)) or len(ids)!=2
            or any(not isinstance(x,str) for x in ids) or ids[0]==ids[1]):
        raise ValueError("Two distinct exact source IDs required")
    rows, _, digest = _selected(root, ids)
    left,right = rows
    lk,lb,_ = _identity(left)
    rk,rb,_ = _identity(right)
    if lk[:2] != rk[:2] and (lb is None or lb != rb):
        raise ValueError("Lineage inspection requires a recorded relation candidate")
    evidence = []
    def fetch(path):
        data,receipt = _get(path)
        evidence.append(receipt)
        return data
    relations = []
    repositories = []
    ancestry = "not_checked_across_repositories"
    if lk[0] == rk[0]:
        repo = lk[0]
        data = fetch("/repos/"+repo)
        repositories.append({"repository":repo,"repository_id":_repo_identity(data,repo)})
        for pin in sorted({lk[2],rk[2]}):
            commit = fetch("/repos/"+repo+"/git/commits/"+pin)
            if _sha(commit.get("sha")) != pin:
                raise ValueError("Commit endpoint pin mismatch")
        if lk[2] == rk[2]:
            ancestry = "identical_commit"
        else:
            data = fetch("/repos/"+repo+"/compare/"+lk[2]+"..."+rk[2]+"?per_page=1")
            ancestry = _ancestor(data,lk[2],rk[2])
    else:
        a = fetch("/repos/"+lk[0])
        b = fetch("/repos/"+rk[0])
        relations = _repo_relations(a,b,lk[0],rk[0])
        repositories = [{"repository":name,"repository_id":_repo_identity(item,name),
                         "fork_flag":item["fork"]}
                        for name,item in ((lk[0],a),(rk[0],b))]
    if _read_catalog(root)[1] != digest:
        raise ValueError("Catalog changed during lineage inspection")
    return {"schema":"gasl-canonical-lineage-v1","catalog_sha256":digest,
            "source_record_ids":list(ids),"observed_at":datetime.now(timezone.utc).isoformat(),
            "repository_metadata":repositories,
            "repository_relations_reported_by_github":relations,
            "commit_ancestry_reported_by_github":ancestry,
            "evidence":evidence,"skill_level_relations_established":False,
            "package_equivalence_established":False,"publisher_authenticity_established":False,
            "source_records_modified":False,"source_records_merged":False,
            "installation_or_execution_approved":False,
            "limitations":["GitHub API metadata observation, not independent Git graph reconstruction.",
                           "Missing fork/mirror evidence is not proof of absence.",
                           "Commit ancestry does not establish Skill supersession."]}
