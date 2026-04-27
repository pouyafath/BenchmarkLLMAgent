#!/usr/bin/env python3
"""Build a deterministic, repo-diverse 10-issue sample from SWE-bench Verified."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from datasets import load_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-name", type=str, default="SWE-bench/SWE-bench_Verified")
    parser.add_argument("--split", type=str, default="test")
    parser.add_argument("--max-issues", type=int, default=10)
    parser.add_argument(
        "--output-ids",
        type=Path,
        default=Path("data/samples/swe_bench_verified_10_stratified_instance_ids.txt"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("data/samples/swe_bench_verified_10_stratified_samples.json"),
    )
    args = parser.parse_args()

    rows = load_dataset(args.dataset_name, split=args.split)
    # Deterministic order by repo then issue id.
    ordered = sorted(
        rows,
        key=lambda r: (
            r.get("repo", ""),
            r.get("instance_id", ""),
        ),
    )

    selected = []
    used_repos = set()
    for row in ordered:
        repo = row.get("repo", "")
        if repo in used_repos:
            continue
        selected.append(row)
        used_repos.add(repo)
        if len(selected) >= args.max_issues:
            break

    if len(selected) < args.max_issues:
        raise RuntimeError(
            f"Could only select {len(selected)} unique-repo instances, expected {args.max_issues}"
        )

    args.output_ids.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)

    ids = [row["instance_id"] for row in selected]
    args.output_ids.write_text("\n".join(ids) + "\n")
    args.output_json.write_text(
        json.dumps(
            {
                "dataset_name": args.dataset_name,
                "split": args.split,
                "selection_strategy": "deterministic_unique_repo_sorted",
                "issues": selected,
            },
            indent=2,
            default=str,
        )
    )
    print(f"Wrote {args.output_ids}")
    print(f"Wrote {args.output_json}")


if __name__ == "__main__":
    main()
