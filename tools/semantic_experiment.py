#!/usr/bin/env python3
"""Optional offline E5 semantic reranking experiment; not used by production search.

Requires numpy, onnxruntime, tokenizers and the exact explicitly downloaded
model files. No network, agent calls, skill execution or dependency install
takes place in this script.
"""
import argparse
import json
try:
    import resource
except ImportError:
    resource = None  # Windows does not provide resource.getrusage.
import statistics
import sys
import time
from pathlib import Path

from search_benchmark import load_dataset, metrics_for_results, sha256_file
from skill_search import ROOT, search_skills, file_fingerprint

MODEL_REPO = "Xenova/multilingual-e5-small"
MODEL_REVISION = "761b726dd34fb83930e26aab4e9ac3899aa1fa78"
MODEL_FILES = {
    "model.onnx": (118054593, "4d24e2bc01a447951524466ef533e52944bf48509e6552810bcee1a2711cb02c"),
    "tokenizer.json": (17082730, "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39"),
}


def verify_model(directory):
    for name, (size, digest) in MODEL_FILES.items():
        path = Path(directory) / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != size or sha256_file(path) != digest:
            raise ValueError("Missing or mismatched pinned model file: " + name)


def passage(item):
    """Public retrieval evidence only, no instructions or unrelated domain aliases."""
    return "passage: " + " | ".join(str(t) for t in (
        str(item.get("skill_name", "")).replace("-", " "),
        item.get("description"),
        item.get("source_path"),
        item.get("repository"),
        " ".join(item.get("verified_feature_terms", [])),
    ) if t)


def hybrid_order(similarities, semantic_weight=0.35, rank_constant=60):
    """Reciprocal rank fusion of lexical and semantic candidate rankings."""
    if not 0 <= semantic_weight <= 1:
        raise ValueError("semantic_weight must be between zero and one")
    semantic = sorted(range(len(similarities)), key=lambda i: (-similarities[i], i))
    ranks = {index: rank for rank, index in enumerate(semantic, 1)}
    return sorted(range(len(similarities)), key=lambda i: (
        -((1-semantic_weight)/(rank_constant+i+1)
          + semantic_weight/(rank_constant+ranks[i])), i))


class E5Encoder:
    def __init__(self, directory, threads=2):
        verify_model(directory)
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.np = np
        self.tokenizer = Tokenizer.from_file(str(Path(directory)/"tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=128)
        self.tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
        config = ort.SessionOptions()
        config.intra_op_num_threads = threads
        config.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(Path(directory)/"model.onnx"),
                                            sess_options=config, providers=["CPUExecutionProvider"])
        self.inputs = {x.name for x in self.session.get_inputs()}
        if not self.inputs.issubset({"input_ids", "attention_mask", "token_type_ids"}):
            raise RuntimeError("Unexpected model inputs")
        self.outputs = {x.name for x in self.session.get_outputs()}
        if "last_hidden_state" not in self.outputs:
            raise RuntimeError("Unexpected model outputs")

    def encode(self, texts, batch=16):
        np = self.np
        vectors = []
        for start in range(0, len(texts), batch):
            enc = self.tokenizer.encode_batch(texts[start:start+batch])
            inputs = {"input_ids": np.array([x.ids for x in enc], dtype=np.int64),
                      "attention_mask": np.array([x.attention_mask for x in enc], dtype=np.int64),
                      "token_type_ids": np.array([x.type_ids for x in enc], dtype=np.int64)}
            hidden = self.session.run(["last_hidden_state"],
                                      {k:v for k,v in inputs.items() if k in self.inputs})[0]
            mask = inputs["attention_mask"][:, :, None].astype(np.float32)
            mean = (hidden * mask).sum(axis=1) / mask.sum(axis=1).clip(min=1)
            norms = np.linalg.norm(mean, axis=1, keepdims=True)
            if not np.isfinite(mean).all() or (norms <= 0).any():
                raise RuntimeError("Non-finite or empty embedding")
            vectors.append((mean / norms).astype(np.float32))
        return np.concatenate(vectors, axis=0)


def run(root, dataset_path, model, candidates=30, threads=2):
    if not 10 <= candidates <= 100 or not 1 <= threads <= 4:
        raise ValueError("candidates must be 10..100; threads 1..4")
    root = Path(root)
    if (root/"private/skill-metadata-cache.json").exists() or (root/"registry/skills.json").exists():
        raise ValueError("Use a clean public-only workspace for comparable semantic experiments")
    dataset = load_dataset(dataset_path)
    start = time.perf_counter()
    encoder = E5Encoder(model, threads)
    load_seconds = time.perf_counter()-start
    rows = [(q, search_skills(q["query"], limit=candidates, root=root)) for q in dataset["queries"]]
    docs = {}
    for _, items in rows:
        for item in items:
            docs[item["source_record_id"]] = passage(item)
    doc_ids = list(docs)
    print("Encoding", len(doc_ids), "unique candidates", file=sys.stderr, flush=True)
    start = time.perf_counter()
    vectors = encoder.encode([docs[sid] for sid in doc_ids])
    encode_seconds = time.perf_counter()-start
    doc_index = {sid:i for i,sid in enumerate(doc_ids)}
    results = {"lexical":[], "semantic_rerank":[], "hybrid_rrf": []}
    durations = []
    query_rows = []
    for q, items in rows:
        start = time.perf_counter()
        vec = encoder.encode(["query: "+q["query"]])[0]
        similarities = [float(vectors[doc_index[item["source_record_id"]]] @ vec) for item in items]
        semantic = sorted(range(len(items)), key=lambda i: (-similarities[i], i))
        hybrid = hybrid_order(similarities)
        variants = {"lexical":items, "semantic_rerank":[items[i] for i in semantic],
                    "hybrid_rrf":[items[i] for i in hybrid]}
        line = {"id":q["id"],"language":q.get("language","unknown")}
        for name, variant in variants.items():
            metrics = metrics_for_results(variant, q["relevant"],
                                           relevant_threshold=dataset.get("relevant_threshold",2))
            results[name].append(metrics)
            line[name] = metrics
        durations.append((time.perf_counter()-start)*1000)
        query_rows.append(line)
    key_names = ("precision_at_k","recall_at_k","mrr_at_k","ndcg_at_k")
    averages = {name:{key:round(statistics.mean(x[key] for x in values),4)
                     for key in key_names} for name,values in results.items()}
    by_language = {lang:{name:{key:round(statistics.mean(
        q[name][key] for q in query_rows if q["language"]==lang),4)
        for key in key_names} for name in results}
        for lang in sorted({q["language"] for q in query_rows})}
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else None
    return {"model_repository":MODEL_REPO,"model_revision":MODEL_REVISION,
            "model_files":MODEL_FILES,"dataset_sha256":sha256_file(dataset_path),
            "input_fingerprint":file_fingerprint(root),"ranking_code_sha256":sha256_file(Path(__file__).with_name("skill_search.py")),
            "experiment_code_sha256":sha256_file(Path(__file__)),
            "query_count":len(rows),"candidate_limit":candidates,"unique_candidates":len(doc_ids),
            "threads":threads,"model_load_seconds":round(load_seconds,2),
            "candidate_embedding_seconds":round(encode_seconds,2),
            "median_query_embedding_and_rerank_ms":round(statistics.median(durations),2),
            "peak_process_rss_mib":round(peak/(1024*1024 if sys.platform=="darwin" else 1024),2) if peak is not None else None,
            "averages":averages,"language_averages":by_language,"queries":query_rows,
            "limitations":["Provisional development set; not independent.",
                           "Semantic reranking of lexical candidates only, not full-corpus dense retrieval.",
                           "Candidate pool differs from a normal top-10 lexical search.",
                           "Reranking weight fixed at 0.35 before evaluation.",
                           "No model or dependency is required by default GASL."]}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--dataset",type=Path,default=ROOT/"benchmarks/search-gold-v1.json")
    p.add_argument("--model",type=Path,required=True)
    p.add_argument("--candidates",type=int, default=30)
    p.add_argument("--threads",type=int,default=2)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    report=run(args.root,args.dataset,args.model,args.candidates,args.threads)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="queries"},indent=2))


if __name__=="__main__":
    main()
