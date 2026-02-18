#!/usr/bin/env python3
"""Create deterministic repo-level train/eval split (80/20 by default)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def stable_key(owner: str, repo: str, seed: str) -> int:
    h = hashlib.sha256(f"{seed}:{owner}/{repo}".encode("utf-8")).hexdigest()
    return int(h[:16], 16)


def main() -> None:
    parser = argparse.ArgumentParser(description="Split repo dataset into train/eval")
    parser.add_argument("--manifest", default="datasets/repo_pairs_manifest.json")
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--seed", default="repo-split-v1")
    parser.add_argument("--out", default="datasets/repo_pairs_split.json")
    args = parser.parse_args()

    payload = json.loads(Path(args.manifest).read_text())
    rows = [r for r in payload.get("results", []) if r.get("status") == "ok"]
    rows.sort(key=lambda r: stable_key(r["owner"], r["repo"], args.seed))

    n = len(rows)
    cut = int(n * args.train_ratio)
    train = rows[:cut]
    eval_ = rows[cut:]

    out = {
        "seed": args.seed,
        "train_ratio": args.train_ratio,
        "total_ok": n,
        "train_count": len(train),
        "eval_count": len(eval_),
        "train": [{"owner": r["owner"], "repo": r["repo"]} for r in train],
        "eval": [{"owner": r["owner"], "repo": r["repo"]} for r in eval_],
    }
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({"out": args.out, "train": len(train), "eval": len(eval_)}, indent=2))


if __name__ == "__main__":
    main()
