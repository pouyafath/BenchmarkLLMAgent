"""
Build a 50-issue SWE-bench-Live dataset from the HuggingFace test split.

Selection criteria (same as Group C 10-issue):
  - FAIL_TO_PASS > 0  AND  PASS_TO_PASS > 0
  - Diverse repositories preferred
  - Deterministic random selection (seed=42)

Outputs:
  data/samples/groupC_swebenchlive_50/groupC_50_dataset.jsonl
  data/samples/groupC_swebenchlive_50/groupC_50_instance_ids.txt
  data/samples/groupC_swebenchlive_50/groupC_50_samples.json

Usage:
  bench_env/bin/python scripts/data/prepare_swebenchlive_50_dataset.py
  bench_env/bin/python scripts/data/prepare_swebenchlive_50_dataset.py --n 50 --seed 42
"""

import argparse
import datetime
import json
import os
import random
import re
import sys
from collections import Counter
from pathlib import Path


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)

_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_root))

# Import helpers from existing script
from scripts.data.prepare_swe_bench_live_samples import (
    swe_live_to_sample,
    swe_live_to_ground_truth,
)


def get_image_name(instance_id: str) -> str:
    """Compute the starryzhang Docker image name for a SWE-bench-Live instance."""
    name = instance_id.replace("__", "_1776_").lower()
    return f"starryzhang/sweb.eval.x86_64.{name}:latest"


def main():
    parser = argparse.ArgumentParser(
        description="Build 50-issue SWE-bench-Live dataset."
    )
    parser.add_argument("--dataset", default="SWE-bench-Live/SWE-bench-Live",
                        help="HuggingFace dataset ID")
    parser.add_argument("--split", default="test",
                        help="Split to sample from (default: test)")
    parser.add_argument("--n", type=int, default=50,
                        help="Number of issues to select (default: 50)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default: 42)")
    parser.add_argument("--output-dir",
                        default=str(_root / "data" / "samples" / "groupC_swebenchlive_50"),
                        help="Output directory")
    parser.add_argument("--include-group-c10", action="store_true", default=True,
                        help="Ensure original 10 Group C issues are included")
    args = parser.parse_args()

    # Load original Group C 10 instance IDs
    gc10_ids_path = _root / "data" / "samples" / "groupC_swebenchlive_10" / "groupC_instance_ids.txt"
    gc10_ids = set()
    if gc10_ids_path.exists() and args.include_group_c10:
        gc10_ids = {line.strip() for line in gc10_ids_path.read_text().splitlines() if line.strip()}
        print(f"Will include {len(gc10_ids)} original Group C-10 issues as subset")

    # Load HuggingFace dataset
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or None
    print(f"Loading dataset: {args.dataset} (split={args.split})")

    try:
        from datasets import load_dataset
    except ImportError:
        print("ERROR: 'datasets' package not installed. Run: pip install datasets")
        sys.exit(1)

    load_kwargs = {"trust_remote_code": False}
    if hf_token:
        load_kwargs["token"] = hf_token

    raw_dataset = load_dataset(args.dataset, **load_kwargs)
    if args.split not in raw_dataset:
        print(f"ERROR: split '{args.split}' not found. Available: {list(raw_dataset.keys())}")
        sys.exit(1)

    all_rows = raw_dataset[args.split].to_list()
    print(f"  Total instances in '{args.split}' split: {len(all_rows)}")

    # Filter: F2P > 0 AND P2P > 0
    filtered = []
    for row in all_rows:
        f2p = row.get("FAIL_TO_PASS") or []
        p2p = row.get("PASS_TO_PASS") or []
        if len(f2p) > 0 and len(p2p) > 0:
            filtered.append(row)

    print(f"  After F2P>0 AND P2P>0 filter: {len(filtered)}")

    if len(filtered) < args.n:
        print(f"WARNING: only {len(filtered)} qualifying instances, requested {args.n}")
        print(f"  Using all {len(filtered)} qualifying instances")
        args.n = len(filtered)

    # Separate Group C-10 instances from the rest
    gc10_rows = [r for r in filtered if r["instance_id"] in gc10_ids]
    other_rows = [r for r in filtered if r["instance_id"] not in gc10_ids]

    print(f"  Group C-10 instances found in filtered set: {len(gc10_rows)}/{len(gc10_ids)}")

    # Deterministic selection: include all GC10, then fill remaining from other_rows
    remaining_needed = args.n - len(gc10_rows)
    rng = random.Random(args.seed)
    if remaining_needed > 0:
        extra = rng.sample(other_rows, min(remaining_needed, len(other_rows)))
    else:
        extra = []

    chosen = gc10_rows + extra
    # Shuffle for random order
    rng.shuffle(chosen)
    print(f"  Selected {len(chosen)} instances (seed={args.seed})")

    # Show repo distribution
    repos = Counter(r.get("repo", "unknown") for r in chosen)
    print(f"\n  Repository distribution ({len(repos)} repos):")
    for repo, count in repos.most_common(20):
        print(f"    {repo}: {count}")

    # Create output directory
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write JSONL (full SWE-bench format with image_name)
    jsonl_path = out_dir / "groupC_50_dataset.jsonl"
    with open(jsonl_path, "w") as f:
        for row in chosen:
            # Add image_name for mini-SWE-agent compatibility
            row_copy = dict(row)
            row_copy["image_name"] = get_image_name(row["instance_id"])
            f.write(json.dumps(row_copy, cls=DateTimeEncoder) + "\n")
    print(f"\nSaved JSONL: {jsonl_path} ({len(chosen)} lines)")

    # 2. Write instance IDs
    ids_path = out_dir / "groupC_50_instance_ids.txt"
    with open(ids_path, "w") as f:
        for row in chosen:
            f.write(row["instance_id"] + "\n")
    print(f"Saved IDs:   {ids_path}")

    # 3. Write samples JSON (enhancer-friendly format)
    samples = [swe_live_to_sample(row) for row in chosen]
    samples_data = {
        "metadata": {
            "description": f"{len(chosen)}-issue SWE-bench-Live sample (seed={args.seed})",
            "source": args.dataset,
            "split": args.split,
            "selection_seed": args.seed,
            "count": len(samples),
            "filter": "FAIL_TO_PASS > 0 AND PASS_TO_PASS > 0",
            "includes_group_c10": True,
        },
        "issues": samples,
    }
    samples_path = out_dir / "groupC_50_samples.json"
    with open(samples_path, "w") as f:
        json.dump(samples_data, f, indent=2)
    print(f"Saved JSON:  {samples_path}")

    # Summary statistics
    total_f2p = sum(len(r.get("FAIL_TO_PASS", [])) for r in chosen)
    total_p2p = sum(len(r.get("PASS_TO_PASS", [])) for r in chosen)
    desc_lengths = [len(r.get("problem_statement", "")) for r in chosen]
    print(f"\nDataset summary:")
    print(f"  Issues: {len(chosen)}")
    print(f"  Repos: {len(repos)}")
    print(f"  Total F2P tests: {total_f2p}")
    print(f"  Total P2P tests: {total_p2p}")
    print(f"  Avg description length: {sum(desc_lengths)/len(desc_lengths):.0f} chars")
    print(f"  Min/Max description: {min(desc_lengths)}/{max(desc_lengths)} chars")


if __name__ == "__main__":
    main()
