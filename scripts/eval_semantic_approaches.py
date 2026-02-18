#!/usr/bin/env python3
"""Evaluate embedding-first, frame-first, and hybrid-light approaches.

Train on repo-level train split and evaluate on repo-level eval split.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import tempfile
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from spec_eng.dual_spec import load_vocab
from spec_eng.interrogation import InterrogationError, interrogate_iteration


STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "your", "are", "was", "will", "not",
    "all", "can", "has", "have", "using", "via", "same", "across", "over", "only", "must", "before", "after",
    "then", "given", "when", "under", "between", "through", "their", "there", "where", "while", "also",
}

SUBS = {
    "schema": "contract",
    "platform": "workspace",
    "service": "capability",
    "repository": "store",
    "endpoint": "capability",
    "json": "document",
    "http": "request",
    "function": "behavior",
    "method": "behavior",
    "class": "entity",
    "controller": "coordinator",
    "orm": "mapping",
    "sql": "query",
    "table": "records",
    "framework": "workflow",
}

UA_HEADERS = {"User-Agent": "spec-eng-approach-eval/0.1"}


@dataclass
class EvalRow:
    split: str
    owner: str
    repo: str
    approach: str
    status: str
    approved: bool
    iterations: int
    alignment_recall: float
    token_overlap: int
    readme_tokens: int
    error: str = ""


def tokenize(text: str) -> list[str]:
    return [
        w for w in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
        if w not in STOPWORDS
    ]


def token_set(text: str) -> set[str]:
    return set(tokenize(text))


def cosine_sparse(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def fetch_readme(owner: str, repo: str, branch: str) -> str:
    for name in ("README.md", "readme.md", "README.rst", "README.txt"):
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{name}"
        try:
            req = Request(url, headers=UA_HEADERS)
            with urlopen(req, timeout=12) as resp:  # noqa: S310
                txt = resp.read().decode("utf-8", "ignore")
                if len(txt.strip()) >= 200:
                    return txt
        except (HTTPError, URLError):
            continue
    return ""


def sanitize(text: str, banned: set[str]) -> str:
    out = text
    for b in sorted(banned, key=len, reverse=True):
        out = re.sub(rf"\b{re.escape(b)}\b", SUBS.get(b, "behavior"), out, flags=re.IGNORECASE)
    return out


def top_terms(text: str, n: int = 10) -> list[str]:
    freq = Counter(tokenize(text))
    return [w for w, _ in freq.most_common(n)]


def slug(owner: str, repo: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", f"{owner}-{repo}".lower()).strip("-")[:96] or "repo-spec"


class EmbeddingFirst:
    def __init__(self, train_vectors: dict[tuple[str, str], Counter[str]], train_answers: dict[tuple[str, str], dict[str, str]]):
        self.train_vectors = train_vectors
        self.train_answers = train_answers

    def generate(self, owner: str, repo: str, description: str, readme: str) -> tuple[str, dict[str, str]]:
        vec = Counter(tokenize(readme or description))
        best_key = None
        best_score = -1.0
        for key, train_vec in self.train_vectors.items():
            score = cosine_sparse(vec, train_vec)
            if score > best_score:
                best_score, best_key = score, key

        if best_key and best_key in self.train_answers:
            base = self.train_answers[best_key]
            ans = {
                "success_criteria": re.sub(r"\b[a-zA-Z0-9_-]+\b", repo, base["success_criteria"], count=1),
                "failure_case": base["failure_case"],
                "constraints": base["constraints"],
            }
        else:
            terms = ", ".join(top_terms(readme or description, 4))
            ans = {
                "success_criteria": f"{repo} produces observable outcomes for {terms}",
                "failure_case": f"invalid inputs in {repo} are rejected with actionable guidance",
                "constraints": f"{repo} behavior remains deterministic and traceable across reruns",
            }

        terms = ", ".join(top_terms(readme or description, 4))
        idea = f"{repo} behavior where {description}. Primary concepts include {terms}"
        return idea, ans


class FrameFirst:
    ACTION_HINTS = ["build", "deploy", "analyze", "generate", "manage", "orchestrate", "visualize", "benchmark"]

    def generate(self, owner: str, repo: str, description: str, readme: str) -> tuple[str, dict[str, str]]:
        text = (readme[:3000] + "\n" + description).lower()
        actor = "user" if "user" in text else "system"
        action = next((a for a in self.ACTION_HINTS if a in text), "operate")
        objects = ", ".join(top_terms(text, 3))

        idea = f"{repo} behavior where {actor} needs to {action} {objects}"
        ans = {
            "success_criteria": f"{actor} can {action} {objects} with expected outcomes",
            "failure_case": f"invalid {objects} inputs are rejected with actionable guidance",
            "constraints": f"{repo} behavior remains deterministic and traceable across reruns",
        }
        return idea, ans


class HybridLight:
    def __init__(self, embed: EmbeddingFirst, frame: FrameFirst):
        self.embed = embed
        self.frame = frame

    def generate(self, owner: str, repo: str, description: str, readme: str) -> tuple[str, dict[str, str]]:
        e_idea, e_ans = self.embed.generate(owner, repo, description, readme)
        f_idea, f_ans = self.frame.generate(owner, repo, description, readme)

        # Frame scaffold + embedding enrichment terms
        idea = f_idea
        ans = {
            "success_criteria": e_ans["success_criteria"],
            "failure_case": f_ans["failure_case"],
            "constraints": e_ans["constraints"],
        }
        return idea, ans


def run_repo(
    split: str,
    owner: str,
    repo: str,
    branch: str,
    description: str,
    approach_name: str,
    approach: Any,
    vocab_path: Path,
) -> EvalRow:
    readme = fetch_readme(owner, repo, branch)
    vocab = load_vocab(vocab_path)
    banned = set(vocab.lints["implementation_leakage"].get("banned_tokens", []))

    idea, answers = approach.generate(owner, repo, description, readme)
    idea = sanitize(idea, banned)
    answers = {k: sanitize(v, banned) for k, v in answers.items()}

    try:
        with tempfile.TemporaryDirectory(prefix="approach_eval_") as td:
            td = Path(td)
            (td / ".spec-eng").mkdir(parents=True, exist_ok=True)
            (td / "specs").mkdir(parents=True, exist_ok=True)
            (td / ".spec-eng" / "config.json").write_text(
                '{"version":"0.1.0","language":"python","framework":"pytest"}\n'
            )
            shutil.copy(vocab_path, td / "specs" / "vocab.yaml")

            s, _ = interrogate_iteration(td, idea=idea, slug=slug(owner, repo), answers={}, approve=False)
            s, _ = interrogate_iteration(td, idea=idea, slug=s.slug, answers=answers, approve=False)
            s, _ = interrogate_iteration(td, idea=idea, slug=s.slug, answers=answers, approve=False)
            s, _ = interrogate_iteration(td, idea=idea, slug=s.slug, answers=answers, approve=True)

            gwt = (td / "specs" / f"{s.slug}.txt").read_text()
            dal = (td / "specs" / f"{s.slug}.dal").read_text()

        rset = token_set(readme)
        oset = token_set(gwt + "\n" + dal)
        overlap = len(rset & oset)
        recall = overlap / max(1, len(rset))

        return EvalRow(
            split=split,
            owner=owner,
            repo=repo,
            approach=approach_name,
            status="ok",
            approved=s.approved,
            iterations=s.iteration,
            alignment_recall=round(recall, 3),
            token_overlap=overlap,
            readme_tokens=len(rset),
        )
    except InterrogationError as exc:
        return EvalRow(
            split=split,
            owner=owner,
            repo=repo,
            approach=approach_name,
            status="failed",
            approved=False,
            iterations=0,
            alignment_recall=0.0,
            token_overlap=0,
            readme_tokens=len(token_set(readme)),
            error=str(exc),
        )


def load_split(split_path: Path) -> dict[str, list[tuple[str, str]]]:
    data = json.loads(split_path.read_text())
    train = [(x["owner"], x["repo"]) for x in data["train"]]
    eval_ = [(x["owner"], x["repo"]) for x in data["eval"]]
    return {"train": train, "eval": eval_}


def load_source(dataset_dir: Path, owner: str, repo: str) -> dict[str, Any]:
    p = dataset_dir / f"{owner}__{repo}" / "source.json"
    return json.loads(p.read_text())


def build_embedding_train_state(dataset_dir: Path, train: list[tuple[str, str]]) -> tuple[dict[tuple[str, str], Counter[str]], dict[tuple[str, str], dict[str, str]]]:
    vectors: dict[tuple[str, str], Counter[str]] = {}
    answers: dict[tuple[str, str], dict[str, str]] = {}
    for owner, repo in train:
        src = load_source(dataset_dir, owner, repo)
        readme = fetch_readme(owner, repo, src.get("default_branch") or "main")
        vectors[(owner, repo)] = Counter(tokenize(readme or src.get("description", "")))

        run_meta_path = dataset_dir / f"{owner}__{repo}" / "run.json"
        if run_meta_path.exists():
            run_meta = json.loads(run_meta_path.read_text())
            answers[(owner, repo)] = dict(run_meta.get("answers", {}))
    return vectors, answers


def summarize(rows: list[EvalRow]) -> dict[str, Any]:
    by: dict[tuple[str, str], list[EvalRow]] = {}
    for r in rows:
        by.setdefault((r.approach, r.split), []).append(r)

    out: dict[str, Any] = {}
    for (approach, split), group in by.items():
        ok = [r for r in group if r.status == "ok"]
        out[f"{approach}:{split}"] = {
            "total": len(group),
            "ok": len(ok),
            "failed": len(group) - len(ok),
            "approval_rate": round(sum(1 for r in ok if r.approved) / max(1, len(group)), 3),
            "avg_iterations_ok": round(sum(r.iterations for r in ok) / max(1, len(ok)), 3),
            "avg_alignment_recall_ok": round(sum(r.alignment_recall for r in ok) / max(1, len(ok)), 3),
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate semantic approaches on repo-level split")
    parser.add_argument("--dataset-dir", default="datasets/repo_pairs")
    parser.add_argument("--split", default="datasets/repo_pairs_split.json")
    parser.add_argument("--vocab", default="specs/vocab.yaml")
    parser.add_argument("--out-prefix", default="reports/approach_eval")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)
    split = load_split(Path(args.split))

    train_vectors, train_answers = build_embedding_train_state(dataset_dir, split["train"])

    approaches = {
        "embedding-first": EmbeddingFirst(train_vectors, train_answers),
        "frame-first": FrameFirst(),
    }
    approaches["hybrid-light"] = HybridLight(
        embed=approaches["embedding-first"],
        frame=approaches["frame-first"],
    )

    rows: list[EvalRow] = []
    for approach_name, approach in approaches.items():
        for owner, repo in split["train"]:
            src = load_source(dataset_dir, owner, repo)
            rows.append(
                run_repo(
                    split="train",
                    owner=owner,
                    repo=repo,
                    branch=src.get("default_branch") or "main",
                    description=src.get("description") or f"{repo} workflow",
                    approach_name=approach_name,
                    approach=approach,
                    vocab_path=Path(args.vocab),
                )
            )
        for owner, repo in split["eval"]:
            src = load_source(dataset_dir, owner, repo)
            rows.append(
                run_repo(
                    split="eval",
                    owner=owner,
                    repo=repo,
                    branch=src.get("default_branch") or "main",
                    description=src.get("description") or f"{repo} workflow",
                    approach_name=approach_name,
                    approach=approach,
                    vocab_path=Path(args.vocab),
                )
            )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_json = Path(f"{args.out_prefix}_{ts}.json")
    out_md = Path(f"{args.out_prefix}_{ts}.md")

    summary = summarize(rows)
    payload = {
        "generated_at_utc": ts,
        "train_count": len(split["train"]),
        "eval_count": len(split["eval"]),
        "summary": summary,
        "rows": [asdict(r) for r in rows],
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2) + "\n")

    lines = [
        f"# Approach Eval ({ts})",
        "",
        f"- Train repos: `{len(split['train'])}`",
        f"- Eval repos: `{len(split['eval'])}`",
        "",
        "## Summary",
        "",
        "| Approach | Total | OK | Failed | Approval Rate | Avg Iter (OK) | Avg Recall (OK) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, s in summary.items():
        lines.append(
            f"| {name} | {s['total']} | {s['ok']} | {s['failed']} | {s['approval_rate']:.3f} | "
            f"{s['avg_iterations_ok']:.3f} | {s['avg_alignment_recall_ok']:.3f} |"
        )

    out_md.write_text("\n".join(lines) + "\n")
    print(out_json)
    print(out_md)


if __name__ == "__main__":
    main()
