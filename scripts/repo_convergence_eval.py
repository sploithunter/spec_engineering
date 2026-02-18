#!/usr/bin/env python3
"""Batch convergence evaluator for repository-driven interrogation specs.

Runs deterministic interrogation loops against repo ideas, compiles GWT/DAL/IR,
and computes lightweight alignment metrics versus README content.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from spec_eng.interrogation import InterrogationError, interrogate_iteration
from spec_eng.dual_spec import load_vocab


STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "your", "are", "was", "will",
    "not", "all", "can", "has", "have", "using", "via", "same", "across", "over", "only", "must",
    "before", "after", "then", "given", "when", "under", "into", "between", "through",
}

SUBSTITUTIONS = {
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


@dataclass
class RepoResult:
    repo: str
    status: str
    iterations: int
    approved: bool
    alignment_recall: float
    token_overlap: int
    readme_tokens: int
    slug: str
    error: str = ""


def gh_json(url: str) -> Any:
    with urlopen(url, timeout=12) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def readme_text(owner: str, repo: str, branch: str = "main") -> str:
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
    try:
        with urlopen(url, timeout=10) as resp:  # noqa: S310
            return resp.read().decode("utf-8", "ignore")
    except URLError:
        return ""


def tokens(text: str) -> set[str]:
    return {
        t
        for t in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower())
        if t not in STOPWORDS
    }


def sanitize(text: str, banned: set[str]) -> str:
    out = text
    for b in sorted(banned, key=len, reverse=True):
        pat = re.compile(rf"\b{re.escape(b)}\b", re.IGNORECASE)
        out = pat.sub(SUBSTITUTIONS.get(b, "behavior"), out)
    return out


def default_idea(repo_name: str, description: str) -> str:
    repo_phrase = repo_name.replace("-", " ").replace("_", " ").strip()
    desc = description.strip() if description else f"{repo_phrase} workflow"
    return f"{repo_phrase} behavior where {desc}"


def default_answers(repo_name: str, description: str) -> dict[str, str]:
    topic = repo_name.replace("-", " ").replace("_", " ")
    base = description.strip() if description else f"{topic} workflow"
    return {
        "success_criteria": f"{topic} produces observable outcomes for {base}",
        "failure_case": f"invalid inputs for {topic} are rejected with actionable guidance",
        "constraints": f"{topic} behavior remains deterministic and traceable across reruns",
    }


def evaluate_repo(repo_meta: dict[str, Any], vocab_path: Path) -> RepoResult:
    repo = repo_meta["name"]
    desc = repo_meta.get("description") or ""
    readme = readme_text("sploithunter", repo, repo_meta.get("default_branch") or "main")

    vocab = load_vocab(vocab_path)
    banned = set(vocab.lints["implementation_leakage"].get("banned_tokens", []))

    idea = sanitize(default_idea(repo, desc), banned)
    answers = {k: sanitize(v, banned) for k, v in default_answers(repo, desc).items()}

    try:
        with tempfile.TemporaryDirectory(prefix="convergence_eval_") as td:
            tdp = Path(td)
            (tdp / ".spec-eng").mkdir(parents=True, exist_ok=True)
            (tdp / "specs").mkdir(parents=True, exist_ok=True)
            (tdp / ".spec-eng" / "config.json").write_text(
                '{"version":"0.1.0","language":"python","framework":"pytest"}\n'
            )
            shutil.copy(vocab_path, tdp / "specs" / "vocab.yaml")

            s, _ = interrogate_iteration(tdp, idea=idea, slug=None, answers={}, approve=False)
            s, _ = interrogate_iteration(tdp, idea=idea, slug=s.slug, answers=answers, approve=False)
            s, _ = interrogate_iteration(tdp, idea=idea, slug=s.slug, answers=answers, approve=False)
            s, _ = interrogate_iteration(tdp, idea=idea, slug=s.slug, answers=answers, approve=True)

            gwt = (tdp / "specs" / f"{s.slug}.txt").read_text()
            dal = (tdp / "specs" / f"{s.slug}.dal").read_text()

        readme_tok = tokens(readme)
        out_tok = tokens(gwt + "\n" + dal)
        overlap = len(readme_tok & out_tok)
        denom = max(1, len(readme_tok))

        return RepoResult(
            repo=repo,
            status="ok",
            iterations=s.iteration,
            approved=s.approved,
            alignment_recall=round(overlap / denom, 3),
            token_overlap=overlap,
            readme_tokens=len(readme_tok),
            slug=s.slug,
        )
    except InterrogationError as exc:
        return RepoResult(
            repo=repo,
            status="failed",
            iterations=0,
            approved=False,
            alignment_recall=0.0,
            token_overlap=0,
            readme_tokens=len(tokens(readme)),
            slug="",
            error=str(exc),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch evaluate repo convergence")
    parser.add_argument("--owner", default="sploithunter")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out-prefix", default="reports/convergence")
    parser.add_argument("--vocab", default="specs/vocab.yaml")
    args = parser.parse_args()

    repos = gh_json(f"https://api.github.com/users/{args.owner}/repos?per_page=100")
    repos = [r for r in repos if not r.get("fork") and not r.get("archived")][: args.limit]

    vocab_path = Path(args.vocab)
    results: list[RepoResult] = []

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futs = [pool.submit(evaluate_repo, repo, vocab_path) for repo in repos]
        for fut in as_completed(futs):
            results.append(fut.result())

    results.sort(key=lambda r: (r.status != "ok", -r.alignment_recall, r.repo))

    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_json = Path(f"{args.out_prefix}_{now}.json")
    out_md = Path(f"{args.out_prefix}_{now}.md")
    out_json.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "owner": args.owner,
        "generated_at_utc": now,
        "limit": args.limit,
        "workers": args.workers,
        "summary": {
            "total": len(results),
            "ok": sum(1 for r in results if r.status == "ok"),
            "failed": sum(1 for r in results if r.status != "ok"),
            "avg_alignment_recall": round(
                sum(r.alignment_recall for r in results if r.status == "ok")
                / max(1, sum(1 for r in results if r.status == "ok")),
                3,
            ),
        },
        "results": [asdict(r) for r in results],
    }
    out_json.write_text(json.dumps(payload, indent=2) + "\n")

    lines = [
        f"# Convergence Report ({now})",
        "",
        f"- Owner: `{args.owner}`",
        f"- Total: `{payload['summary']['total']}`",
        f"- OK: `{payload['summary']['ok']}`",
        f"- Failed: `{payload['summary']['failed']}`",
        f"- Avg alignment recall: `{payload['summary']['avg_alignment_recall']}`",
        "",
        "| Repo | Status | Iterations | Approved | Recall | Overlap/README |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r.repo} | {r.status} | {r.iterations} | {str(r.approved).lower()} | "
            f"{r.alignment_recall:.3f} | {r.token_overlap}/{r.readme_tokens} |"
        )
    out_md.write_text("\n".join(lines) + "\n")

    print(out_json)
    print(out_md)


if __name__ == "__main__":
    main()
