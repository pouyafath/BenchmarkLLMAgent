"""
Prepare a deterministic 10-issue sample from SWE-bench-Live for Iteration 1.

Dataset source: HuggingFace  SWE-bench-Live/SWE-bench-Live
  Splits available: test, lite, verified, full

Outputs:
  data/samples/swe_bench_live_10_samples.json
  data/ground_truth_swe_bench_live/<owner>__<repo>__<issue_number>.json

Schema mapping:
  instance_id       -> parse owner, repo, issue_number
                       format: "owner__repo-<N>" or "owner__repo__<N>"
  pull_number       -> pr_number  (string; cast to int)
  issue_numbers[0]  -> issue_number fallback (string; cast to int)
  base_commit       -> pr_base_sha
  problem_statement -> title (first non-empty line) + body (full text)
  patch             -> ground_truth_patch
  patch diff headers-> pr_files  (filenames parsed from diff --git lines)

No secrets or tokens are hardcoded; use env var:
  GH_TOKEN / GITHUB_TOKEN   — optional, for higher GitHub rate limits

Usage:
  ./bench_env/bin/python scripts/data/prepare_swe_bench_live_samples.py
  ./bench_env/bin/python scripts/data/prepare_swe_bench_live_samples.py --n 10 --seed 42
  ./bench_env/bin/python scripts/data/prepare_swe_bench_live_samples.py \\
      --dataset SWE-bench-Live/SWE-bench-Live \\
      --output-samples data/samples/swe_bench_live_10_samples.json \\
      --output-gt-dir data/ground_truth_swe_bench_live
"""

import argparse
import json
import os
import random
import re
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_root))


# ---------------------------------------------------------------------------
# Field-mapping helpers
# ---------------------------------------------------------------------------

def _parse_pr_files_from_patch(patch: str) -> list[dict]:
    """Extract changed-file metadata from a unified-diff patch string."""
    files = []
    seen = set()
    for line in patch.splitlines():
        m = re.match(r"^diff --git a/(.+?) b/(.+)$", line)
        if m:
            filename = m.group(2)
            if filename not in seen:
                seen.add(filename)
                # Count + / - lines in this hunk (rough estimate)
                files.append({
                    "filename": filename,
                    "status": "modified",
                    "additions": 0,
                    "deletions": 0,
                    "changes": 0,
                })
    # Second pass: fill in additions / deletions
    current_file = None
    for line in patch.splitlines():
        m = re.match(r"^diff --git a/(.+?) b/(.+)$", line)
        if m:
            current_file = m.group(2)
        elif current_file:
            for f in files:
                if f["filename"] == current_file:
                    if line.startswith("+") and not line.startswith("+++"):
                        f["additions"] += 1
                        f["changes"] += 1
                    elif line.startswith("-") and not line.startswith("---"):
                        f["deletions"] += 1
                        f["changes"] += 1
    return files


def _parse_issue_number(instance_id: str, pull_number: str | int,
                         issue_numbers: list) -> int:
    """
    Derive a stable integer issue number.

    Priority:
    1. issue_numbers[0] if non-empty and numeric
    2. pull_number if non-empty and numeric
    3. trailing digit group in instance_id
    4. deterministic hash fallback
    """
    # 1. issue_numbers
    for raw in (issue_numbers or []):
        try:
            return int(str(raw).strip())
        except ValueError:
            pass
    # 2. pull_number
    try:
        if pull_number:
            return int(str(pull_number).strip())
    except ValueError:
        pass
    # 3. instance_id trailing digits (e.g. "owner__repo-1234" or "owner__repo__1234")
    m = re.search(r"[-_](\d+)$", str(instance_id))
    if m:
        return int(m.group(1))
    # 4. hash fallback
    return abs(hash(instance_id)) % 99999 + 1


def _parse_owner_repo(instance_id: str, repo_field: str) -> tuple[str, str]:
    """
    Return (owner, repo) from the SWE-bench-Live instance_id.

    Format is typically:  owner__repo-<PR>  or  owner/repo
    """
    # Try repo_field (e.g. "samtools/samtools")
    if "/" in repo_field:
        parts = repo_field.split("/", 1)
        return parts[0], parts[1]
    # Parse from instance_id: "owner__repo-NNN"
    m = re.match(r"^([^_]+)__([^-]+)-?\d*$", instance_id)
    if m:
        return m.group(1), m.group(2)
    # Fallback: use repo_field as both
    return repo_field, repo_field


def swe_live_to_sample(row: dict) -> dict:
    """Convert one SWE-bench-Live row to our run_enhancement_benchmark schema."""
    repo_field = row.get("repo", "")
    instance_id = row.get("instance_id", "")
    owner, repo_name = _parse_owner_repo(instance_id, repo_field)

    pull_number = row.get("pull_number", "")
    issue_numbers = row.get("issue_numbers") or []
    issue_num = _parse_issue_number(instance_id, pull_number, issue_numbers)

    # Title: first non-empty line of problem_statement
    problem_stmt = row.get("problem_statement", "") or ""
    lines = [ln.strip() for ln in problem_stmt.splitlines() if ln.strip()]
    title = lines[0] if lines else instance_id

    patch = row.get("patch", "") or ""
    pr_files = _parse_pr_files_from_patch(patch)

    try:
        pr_num = int(str(pull_number).strip())
    except (ValueError, TypeError):
        pr_num = issue_num

    return {
        "repo_name": f"{owner}/{repo_name}",
        "issue_number": issue_num,
        "issue_id": instance_id,           # stable string identifier
        "title": title,
        "body": problem_stmt,
        "pr_owner": owner,
        "pr_repo": repo_name,
        "pr_number": pr_num,
        "pr_base_sha": row.get("base_commit", "") or "",
        "pr_files": pr_files,
        "ground_truth_patch": patch,
        # Extra provenance fields (not required by runners, but useful)
        "_swe_live_instance_id": instance_id,
        "_swe_live_created_at": str(row.get("created_at", "")),
    }


def swe_live_to_ground_truth(row: dict, sample: dict) -> dict:
    """Build the ground_truth/*.json schema for one issue."""
    return {
        "issue_id": sample["issue_id"],
        "pr_number": sample["pr_number"],
        "pr_base_sha": sample["pr_base_sha"],
        "pr_files": sample["pr_files"],
        "patch": sample["ground_truth_patch"],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Prepare 10-issue SWE-bench-Live sample for Iteration 1."
    )
    parser.add_argument("--dataset", default="SWE-bench-Live/SWE-bench-Live",
                        help="HuggingFace dataset identifier (default: SWE-bench-Live/SWE-bench-Live)")
    parser.add_argument("--splits", default="verified",
                        help="Comma-separated splits to include, or 'all' (default: verified)")
    parser.add_argument("--n", type=int, default=10,
                        help="Number of issues to sample (default: 10)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for deterministic selection (default: 42)")
    parser.add_argument("--output-samples",
                        default=str(_root / "data" / "samples" / "swe_bench_live_10_samples.json"),
                        help="Output path for samples JSON")
    parser.add_argument("--output-gt-dir",
                        default=str(_root / "data" / "ground_truth_swe_bench_live"),
                        help="Output directory for ground-truth JSONs")
    args = parser.parse_args()

    # Resolve HF_TOKEN from env (no hardcoding)
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or None

    print(f"Loading dataset: {args.dataset}")
    try:
        from datasets import load_dataset
    except ImportError:
        print("ERROR: 'datasets' package not installed. Run: pip install datasets")
        sys.exit(1)

    load_kwargs = {"trust_remote_code": False}
    if hf_token:
        load_kwargs["token"] = hf_token

    try:
        raw_dataset = load_dataset(args.dataset, **load_kwargs)
    except Exception as e:
        print(f"ERROR: Could not load '{args.dataset}': {e}")
        sys.exit(1)

    available_splits = list(raw_dataset.keys())
    print(f"  Available splits: {available_splits}")

    if args.splits == "all":
        selected_splits = available_splits
    else:
        selected_splits = [s.strip() for s in args.splits.split(",") if s.strip()]
        missing = [s for s in selected_splits if s not in available_splits]
        if missing:
            print(f"ERROR: splits not found: {missing}. Available: {available_splits}")
            sys.exit(1)

    # Collect all rows from selected splits
    all_rows = []
    for split in selected_splits:
        split_data = raw_dataset[split]
        all_rows.extend(split_data.to_list())

    print(f"  Total instances across splits: {len(all_rows)}")

    if len(all_rows) < args.n:
        print(f"ERROR: only {len(all_rows)} rows available, but requested n={args.n}")
        sys.exit(1)

    # Deterministic selection
    rng = random.Random(args.seed)
    chosen = rng.sample(all_rows, args.n)
    print(f"  Selected {args.n} instances (seed={args.seed})")

    # Convert to project schema
    samples = [swe_live_to_sample(row) for row in chosen]

    # Validate uniqueness
    ids = [s["issue_id"] for s in samples]
    if len(set(ids)) != len(ids):
        print("WARNING: duplicate instance_ids in sample; this is unexpected")

    # Write samples JSON
    samples_path = Path(args.output_samples)
    samples_path.parent.mkdir(parents=True, exist_ok=True)
    output_data = {
        "metadata": {
            "description": f"10-issue SWE-bench-Live sample for Iteration 1 (seed={args.seed})",
            "source": args.dataset,
            "splits_used": selected_splits,
            "selection_seed": args.seed,
            "count": len(samples),
        },
        "issues": samples,
    }
    with open(samples_path, "w") as f:
        json.dump(output_data, f, indent=2)
    print(f"Saved {len(samples)} samples to {samples_path}")

    # Write ground-truth files
    gt_dir = Path(args.output_gt_dir)
    gt_dir.mkdir(parents=True, exist_ok=True)
    for row, sample in zip(chosen, samples):
        gt = swe_live_to_ground_truth(row, sample)
        fname = f"{sample['pr_owner']}__{sample['pr_repo']}__{sample['issue_number']}.json"
        with open(gt_dir / fname, "w") as f:
            json.dump(gt, f, indent=2)
    print(f"Saved {len(samples)} ground-truth files to {gt_dir}/")
    print(f"\ncount={len(samples)}")


if __name__ == "__main__":
    main()
