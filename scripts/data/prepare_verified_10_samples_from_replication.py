#!/usr/bin/env python3
"""Prepare the 10-issue SWE-bench Verified sample aligned with SWE-Bench_Replication.

This script reads instance IDs from the replication workspace and writes:
1) data/samples/swe_bench_verified_10_samples.json  (enhancer-friendly format)
2) data/samples/swe_bench_verified_10_dataset_original.jsonl (mini-SWE-agent dataset rows)
3) data/samples/swe_bench_verified_10_instance_ids.txt (ordered IDs)
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from datasets import load_dataset

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SELECTED_IDS = Path("/home/22pf2/SWE-Bench_Replication/selected_instances.txt")
DEFAULT_OUTPUT_SAMPLES = ROOT / "data" / "samples" / "swe_bench_verified_10_samples.json"
DEFAULT_OUTPUT_DATASET = ROOT / "data" / "samples" / "swe_bench_verified_10_dataset_original.jsonl"
DEFAULT_OUTPUT_IDS = ROOT / "data" / "samples" / "swe_bench_verified_10_instance_ids.txt"


def _parse_issue_number(instance_id: str) -> int:
    m = re.search(r"-(\d+)$", instance_id)
    if not m:
        raise ValueError(f"Cannot parse issue number from instance_id={instance_id}")
    return int(m.group(1))


def _extract_title(problem_statement: str) -> str:
    for line in problem_statement.splitlines():
        line = line.strip()
        if line:
            return line[:200]
    return ""


def _read_ids(path: Path) -> list[str]:
    ids = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if not ids:
        raise ValueError(f"No instance IDs found in {path}")
    return ids


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selected-ids", type=Path, default=DEFAULT_SELECTED_IDS)
    parser.add_argument("--dataset-name", type=str, default="SWE-bench/SWE-bench_Verified")
    parser.add_argument("--split", type=str, default="test")
    parser.add_argument("--output-samples", type=Path, default=DEFAULT_OUTPUT_SAMPLES)
    parser.add_argument("--output-dataset-jsonl", type=Path, default=DEFAULT_OUTPUT_DATASET)
    parser.add_argument("--output-instance-ids", type=Path, default=DEFAULT_OUTPUT_IDS)
    args = parser.parse_args()

    selected_ids = _read_ids(args.selected_ids)
    ds = load_dataset(args.dataset_name, split=args.split)
    rows_by_id = {row["instance_id"]: row for row in ds}

    missing = [iid for iid in selected_ids if iid not in rows_by_id]
    if missing:
        raise ValueError(f"Missing {len(missing)} IDs in dataset {args.dataset_name}: {missing}")

    rows = [rows_by_id[iid] for iid in selected_ids]

    issues: list[dict] = []
    for row in rows:
        owner, repo = row["repo"].split("/", 1)
        issue_number = _parse_issue_number(row["instance_id"])
        issue = {
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
            # Kept for compatibility with existing enhancer scripts.
            "pr_files": [],
        }
        issues.append(issue)

    sample_payload = {
        "metadata": {
            "description": "SWE-bench Verified fixed 10-issue sample aligned with SWE-Bench_Replication baseline",
            "dataset_name": args.dataset_name,
            "split": args.split,
            "count": len(issues),
            "source_instance_ids": str(args.selected_ids),
            "baseline_reference": "/home/22pf2/SWE-Bench_Replication/replication_report.md",
        },
        "issues": issues,
    }

    args.output_samples.parent.mkdir(parents=True, exist_ok=True)
    args.output_dataset_jsonl.parent.mkdir(parents=True, exist_ok=True)
    args.output_instance_ids.parent.mkdir(parents=True, exist_ok=True)

    args.output_samples.write_text(json.dumps(sample_payload, indent=2))
    args.output_instance_ids.write_text("\n".join(selected_ids) + "\n")
    with args.output_dataset_jsonl.open("w") as f:
        for row in rows:
            f.write(json.dumps(dict(row)) + "\n")

    print(f"Wrote samples JSON: {args.output_samples}")
    print(f"Wrote dataset JSONL: {args.output_dataset_jsonl}")
    print(f"Wrote instance IDs: {args.output_instance_ids}")
    print(f"Prepared {len(issues)} issues from {args.dataset_name}/{args.split}")


if __name__ == "__main__":
    main()

