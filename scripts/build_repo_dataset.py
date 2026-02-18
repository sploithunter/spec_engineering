#!/usr/bin/env python3
"""Build repo-level GWT/DAL dataset from public GitHub repositories.

Selection policy:
- medium-size repos by stars and size
- non-fork, non-archived
- has readable README content

Generation policy:
- deterministic interrogation loop to stable/approved state
- persist GWT/DAL/canonical/IR per repo
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from spec_eng.interrogation import InterrogationError, interrogate_iteration


HEADERS = {
    "User-Agent": "spec-eng-dataset-builder/0.1",
    "Accept": "application/vnd.github+json",
}

STOP = {
    "the", "and", "for", "with", "that", "this", "from", "into", "your", "are", "was", "will", "not",
    "all", "can", "has", "have", "using", "via", "same", "across", "over", "only", "must", "before", "after",
    "then", "given", "when", "into", "between", "through", "their", "there", "where", "while", "also",
}


@dataclass
class RepoRecord:
    owner: str
    repo: str
    stars: int
    size_kb: int
    language: str
    default_branch: str
    description: str


@dataclass
class BuildResult:
    owner: str
    repo: str
    status: str
    iterations: int
    approved: bool
    slug: str
    error: str = ""


def gh_json(url: str, token: str | None = None) -> Any:
    req = Request(url, headers=_headers(token))
    with urlopen(req, timeout=20) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def get_text(url: str, token: str | None = None) -> str:
    req = Request(url, headers=_headers(token))
    with urlopen(req, timeout=20) as resp:  # noqa: S310
        return resp.read().decode("utf-8", "ignore")


def _headers(token: str | None) -> dict[str, str]:
    headers = dict(HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def discover_repos(target: int, token: str | None = None) -> list[RepoRecord]:
    records: list[RepoRecord] = []
    # medium-ish repos: stars 50..5000 and non-fork/non-archived
    # pull a few pages and filter by README quality.
    for page in range(1, 6):
        if len(records) >= target * 2:
            break
        q = "stars:50..5000 fork:false archived:false"
        url = (
            "https://api.github.com/search/repositories"
            f"?q={q.replace(' ', '+')}&sort=stars&order=desc&per_page=100&page={page}"
        )
        try:
            payload = gh_json(url, token=token)
        except HTTPError as exc:
            if exc.code == 403:
                break
            raise
        for item in payload.get("items", []):
            owner = item["owner"]["login"]
            repo = item["name"]
            desc = item.get("description") or ""
            if not desc.strip():
                continue
            size = int(item.get("size") or 0)
            if size < 200:  # tiny repos usually too sparse
                continue
            records.append(
                RepoRecord(
                    owner=owner,
                    repo=repo,
                    stars=int(item.get("stargazers_count") or 0),
                    size_kb=size,
                    language=item.get("language") or "",
                    default_branch=item.get("default_branch") or "main",
                    description=desc.strip(),
                )
            )

    # de-dup preserve order
    seen: set[tuple[str, str]] = set()
    uniq: list[RepoRecord] = []
    for r in records:
        key = (r.owner.lower(), r.repo.lower())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    return uniq


def fetch_readme(owner: str, repo: str, branch: str, token: str | None = None) -> str:
    candidates = ["README.md", "readme.md", "README.rst", "README.txt"]
    for name in candidates:
        raw = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{name}"
        try:
            text = get_text(raw, token=token)
            if len(text.strip()) >= 400:
                return text
        except (HTTPError, URLError):
            continue
    return ""


def summarize_concepts(readme: str, limit: int = 6) -> list[str]:
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", readme)]
    freq: dict[str, int] = {}
    for w in words:
        if w in STOP:
            continue
        if w.isdigit():
            continue
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:limit]]


def idea_and_answers(rec: RepoRecord, readme: str) -> tuple[str, dict[str, str]]:
    concepts = summarize_concepts(readme)
    concept_phrase = ", ".join(concepts[:4]) if concepts else rec.language.lower() or "core behavior"
    idea = (
        f"{rec.repo} behavior where {rec.description}. "
        f"Primary concepts include {concept_phrase}"
    )
    answers = {
        "success_criteria": f"{rec.repo} produces observable outcomes for {concept_phrase}",
        "failure_case": f"invalid inputs in {rec.repo} are rejected with actionable guidance",
        "constraints": f"{rec.repo} behavior remains deterministic and traceable across reruns",
    }
    return idea, answers


def build_one(
    rec: RepoRecord,
    readme: str,
    out_dir: Path,
    vocab_path: Path,
) -> BuildResult:
    repo_dir = out_dir / f"{rec.owner}__{rec.repo}"
    repo_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "owner": rec.owner,
        "repo": rec.repo,
        "stars": rec.stars,
        "size_kb": rec.size_kb,
        "language": rec.language,
        "default_branch": rec.default_branch,
        "description": rec.description,
        "readme_chars": len(readme),
    }
    (repo_dir / "source.json").write_text(json.dumps(meta, indent=2) + "\n")

    idea, answers = idea_and_answers(rec, readme)
    stable_slug = re.sub(r"[^a-z0-9-]+", "-", f"{rec.owner}-{rec.repo}".lower()).strip("-")
    if not stable_slug:
        stable_slug = "repo-spec"
    stable_slug = stable_slug[:96]

    try:
        with tempfile.TemporaryDirectory(prefix="repo_dataset_") as td:
            tdp = Path(td)
            (tdp / ".spec-eng").mkdir(parents=True, exist_ok=True)
            (tdp / "specs").mkdir(parents=True, exist_ok=True)
            (tdp / ".spec-eng" / "config.json").write_text(
                '{"version":"0.1.0","language":"python","framework":"pytest"}\n'
            )
            shutil.copy(vocab_path, tdp / "specs" / "vocab.yaml")

            s, _ = interrogate_iteration(tdp, idea=idea, slug=stable_slug, answers={}, approve=False)
            s, _ = interrogate_iteration(tdp, idea=idea, slug=s.slug, answers=answers, approve=False)
            s, _ = interrogate_iteration(tdp, idea=idea, slug=s.slug, answers=answers, approve=False)
            s, _ = interrogate_iteration(tdp, idea=idea, slug=s.slug, answers=answers, approve=True)

            src_gwt = tdp / "specs" / f"{s.slug}.txt"
            src_dal = tdp / "specs" / f"{s.slug}.dal"
            src_canon = tdp / "specs" / f"{s.slug}.txt.canonical"
            src_ir = tdp / "acceptance-pipeline" / "ir" / f"{s.slug}.json"

            shutil.copy(src_gwt, repo_dir / "spec.txt")
            shutil.copy(src_dal, repo_dir / "spec.dal")
            shutil.copy(src_canon, repo_dir / "spec.txt.canonical")
            shutil.copy(src_ir, repo_dir / "ir.json")

            run_meta = {
                "idea": idea,
                "answers": answers,
                "slug": s.slug,
                "iterations": s.iteration,
                "approved": s.approved,
            }
            (repo_dir / "run.json").write_text(json.dumps(run_meta, indent=2) + "\n")

            return BuildResult(
                owner=rec.owner,
                repo=rec.repo,
                status="ok",
                iterations=s.iteration,
                approved=s.approved,
                slug=s.slug,
            )
    except Exception as exc:  # keep batch robust for large-scale runs
        return BuildResult(
            owner=rec.owner,
            repo=rec.repo,
            status="failed",
            iterations=0,
            approved=False,
            slug="",
            error=str(exc),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build repo-level GWT/DAL dataset")
    parser.add_argument("--target", type=int, default=100)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--dataset-dir", default="datasets/repo_pairs")
    parser.add_argument("--manifest", default="datasets/repo_pairs_manifest.json")
    parser.add_argument("--token", default="")
    parser.add_argument("--vocab", default="specs/vocab.yaml")
    args = parser.parse_args()

    token = args.token.strip() or None
    dataset_dir = Path(args.dataset_dir)
    dataset_dir.mkdir(parents=True, exist_ok=True)

    discovered = discover_repos(target=max(args.target * 2, 200), token=token)

    eligible: list[tuple[RepoRecord, str]] = []
    for rec in discovered:
        if len(eligible) >= args.target:
            break
        readme = fetch_readme(rec.owner, rec.repo, rec.default_branch, token=token)
        if not readme:
            continue
        eligible.append((rec, readme))

    results: list[BuildResult] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futs = [
            pool.submit(build_one, rec, readme, dataset_dir, Path(args.vocab))
            for rec, readme in eligible
        ]
        for fut in as_completed(futs):
            try:
                results.append(fut.result())
            except Exception as exc:  # should be rare due to per-item guard
                results.append(
                    BuildResult(
                        owner="<unknown>",
                        repo="<unknown>",
                        status="failed",
                        iterations=0,
                        approved=False,
                        slug="",
                        error=f"worker exception: {exc}",
                    )
                )

    results.sort(key=lambda r: (r.status != "ok", r.owner.lower(), r.repo.lower()))

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target": args.target,
        "eligible": len(eligible),
        "ok": sum(1 for r in results if r.status == "ok"),
        "failed": sum(1 for r in results if r.status != "ok"),
        "results": [asdict(r) for r in results],
    }
    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n")

    print(json.dumps({
        "dataset_dir": str(dataset_dir),
        "manifest": str(manifest_path),
        "ok": payload["ok"],
        "failed": payload["failed"],
        "eligible": payload["eligible"],
    }, indent=2))


if __name__ == "__main__":
    main()
