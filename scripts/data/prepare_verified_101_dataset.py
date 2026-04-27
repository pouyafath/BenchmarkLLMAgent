#!/usr/bin/env python3
"""Prepare a 101-issue Group A dataset from SWE-bench Verified.

Selection strategy (diverse repos, avoids django dominance):
- 22 astropy (all available)
- 32 scikit-learn (all available)
- 22 pydata/xarray (all available)
- 19 pytest-dev/pytest (all available)
- 6 matplotlib (to reach 101)

All selected issues have FAIL_TO_PASS > 0 AND PASS_TO_PASS > 0.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from datasets import load_dataset

ROOT = Path(__file__).resolve().parent.parent.parent

# Repo selection priority and max counts
REPO_SELECTION = [
    ("astropy/astropy", None),           # all 22
    ("scikit-learn/scikit-learn", None),  # all 32
    ("pydata/xarray", None),             # all 22
    ("pytest-dev/pytest", None),         # all 19
    ("matplotlib/matplotlib", 6),        # 6 to reach 101
]

TARGET_COUNT = 101


def _parse_issue_number(instance_id: str) -> int:
    m = re.search(r"-(\d+)$", instance_id)
    if not m:
        raise ValueError(f"Cannot parse issue number from {instance_id}")
    return int(m.group(1))


def _extract_title(problem_statement: str) -> str:
    for line in problem_statement.splitlines():
        line = line.strip()
        if line:
            return line[:200]
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare 101-issue Group A dataset")
    parser.add_argument("--dataset-name", default="SWE-bench/SWE-bench_Verified")
    parser.add_argument("--split", default="test")
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "data" / "samples" / "101_issues_experiments" / "group_a_101")
    parser.add_argument("--target-count", type=int, default=TARGET_COUNT)
    args = parser.parse_args()

    ds = load_dataset(args.dataset_name, split=args.split)
    print(f"Loaded {len(ds)} issues from {args.dataset_name}/{args.split}")

    # Group by repo, filter for F2P>0 AND P2P>0
    by_repo: dict[str, list] = {}
    for row in ds:
        f2p = json.loads(row.get("FAIL_TO_PASS", "[]"))
        p2p = json.loads(row.get("PASS_TO_PASS", "[]"))
        if len(f2p) > 0 and len(p2p) > 0:
            repo = row["repo"]
            by_repo.setdefault(repo, []).append(row)

    print(f"Issues with F2P>0 AND P2P>0 by repo:")
    for repo, rows in sorted(by_repo.items(), key=lambda x: -len(x[1])):
        print(f"  {repo}: {len(rows)}")

    # Select issues according to priority
    selected = []
    for repo, max_count in REPO_SELECTION:
        candidates = by_repo.get(repo, [])
        # Sort by instance_id for determinism
        candidates.sort(key=lambda r: r["instance_id"])
        take = min(len(candidates), max_count) if max_count else len(candidates)
        selected.extend(candidates[:take])
        print(f"Selected {take}/{len(candidates)} from {repo}")
        if len(selected) >= args.target_count:
            selected = selected[:args.target_count]
            break

    if len(selected) < args.target_count:
        print(f"WARNING: Only {len(selected)} issues selected (target: {args.target_count})")

    print(f"\nTotal selected: {len(selected)}")

    # Sort by instance_id
    selected.sort(key=lambda r: r["instance_id"])
    instance_ids = [r["instance_id"] for r in selected]

    # Build samples JSON (enhancer-friendly format)
    issues = []
    for row in selected:
        owner, repo = row["repo"].split("/", 1)
        issue_number = _parse_issue_number(row["instance_id"])
        issues.append({
            "repo_name": row["repo"],
            "issue_number": issue_number,
            "issue_id": f"{row['repo']}#{issue_number}",
            "title": _extract_title(row["problem_statement"]),
            "body": row["problem_statement"],
            "problem_statement": row["problem_statement"],
            "pr_owner": owner,
            "pr_repo": repo,
            "pr_base_sha": row["base_commit"],
            "base_commit": row["base_commit"],
            "instance_id": row["instance_id"],
            "FAIL_TO_PASS": row["FAIL_TO_PASS"],
            "PASS_TO_PASS": row["PASS_TO_PASS"],
            "pr_files": [],
        })

    sample_payload = {
        "metadata": {
            "description": f"SWE-bench Verified {len(selected)}-issue Group A dataset (diverse repos)",
            "dataset_name": args.dataset_name,
            "split": args.split,
            "count": len(issues),
            "repo_selection": {repo: max_c for repo, max_c in REPO_SELECTION},
        },
        "issues": issues,
    }

    # Write outputs
    args.output_dir.mkdir(parents=True, exist_ok=True)
    samples_path = args.output_dir / "group_a_101_samples.json"
    dataset_path = args.output_dir / "group_a_101_dataset.jsonl"
    ids_path = args.output_dir / "group_a_101_instance_ids.txt"

    samples_path.write_text(json.dumps(sample_payload, indent=2))
    ids_path.write_text("\n".join(instance_ids) + "\n")
    with dataset_path.open("w") as f:
        for row in selected:
            f.write(json.dumps(dict(row)) + "\n")

    print(f"\nWrote samples JSON: {samples_path}")
    print(f"Wrote dataset JSONL: {dataset_path}")
    print(f"Wrote instance IDs: {ids_path}")

    # Summary
    repo_counts = {}
    for iid in instance_ids:
        repo = "__".join(iid.split("__")[:-1]).replace("__", "/")
        repo_counts[repo] = repo_counts.get(repo, 0) + 1
    print(f"\nRepo distribution:")
    for repo, count in sorted(repo_counts.items(), key=lambda x: -x[1]):
        print(f"  {repo}: {count}")


if __name__ == "__main__":
    main()
