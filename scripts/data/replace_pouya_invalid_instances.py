"""
Replace invalid instances in the Pouya dataset with candidates from repos
that have confirmed working Docker environments.

This script:
1. Reads the current 50-instance dataset and the invalid list
2. Reads the full 159-candidate pool from _collection_progress.json
3. Selects replacements from repos with working instances (Tier 1)
4. Updates the dataset JSONL, gold_predictions.json, and instance_ids.txt
"""

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "samples" / "pouya_swebench_live_style_50"
PROGRESS = DATA_DIR / "_collection_progress.json"
DATASET_JSONL = DATA_DIR / "pouya_50_dataset.jsonl"
INVALID_JSON = DATA_DIR / "pouya_invalid_instances.json"
VALIDATED_IDS = DATA_DIR / "pouya_validated_instance_ids.txt"

sys.path.insert(0, str(ROOT))
from scripts.data.prepare_swe_bench_live_samples import swe_live_to_sample


def candidate_to_dataset_row(cand: dict) -> dict:
    """Convert a candidate from progress file to a dataset JSONL row."""
    repo = cand["repo"]
    owner, name = repo.split("/")
    # Build image_name same as original collection
    instance_id = cand["instance_id"]
    safe_id = instance_id.replace("/", "__").replace(".", "_")

    return {
        "instance_id": instance_id,
        "repo": repo,
        "base_commit": cand["base_commit"],
        "patch": cand["patch"],
        "test_patch": cand["test_patch"],
        "problem_statement": cand["problem_statement"],
        "hints_text": "",
        "created_at": cand["created_at"],
        "version": "1.0",
        "FAIL_TO_PASS": json.dumps(cand["FAIL_TO_PASS"]),
        "PASS_TO_PASS": json.dumps(cand["PASS_TO_PASS"]),
        "pull_number": cand["pr_number"],
        "issue_numbers": cand["issue_numbers"],
        "environment_setup_commit": cand["base_commit"],
        "image_name": f"none/sweb.eval.x86_64.{safe_id}:latest",
    }


def main():
    # Load current dataset
    rows = []
    with open(DATASET_JSONL) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    current_ids = {r["instance_id"] for r in rows}
    print(f"Current dataset: {len(rows)} instances")

    # Load invalid list
    with open(INVALID_JSON) as f:
        invalid = json.load(f)
    invalid_ids = {inv["instance_id"] for inv in invalid}
    print(f"Invalid instances: {len(invalid_ids)}")

    # Load validated IDs
    valid_ids = set()
    with open(VALIDATED_IDS) as f:
        for line in f:
            iid = line.strip()
            if iid:
                valid_ids.add(iid)
    print(f"Valid instances: {len(valid_ids)}")

    # Repos with working instances
    working_repos = set()
    for row in rows:
        if row["instance_id"] in valid_ids:
            working_repos.add(row["repo"])
    print(f"Repos with working instances: {working_repos}")

    # Load candidate pool
    with open(PROGRESS) as f:
        progress = json.load(f)
    all_candidates = progress["candidates"]
    print(f"Total candidates in pool: {len(all_candidates)}")

    # Find replacement candidates from working repos
    tier1_candidates = [
        c for c in all_candidates
        if c["repo"] in working_repos
        and c["instance_id"] not in current_ids
    ]
    print(f"Tier 1 candidates (working repos, not in dataset): {len(tier1_candidates)}")

    # Sort by repo to distribute evenly, then shuffle within repo
    random.seed(99)
    random.shuffle(tier1_candidates)

    # Select replacements
    needed = len(invalid_ids)
    if len(tier1_candidates) < needed:
        print(f"WARNING: Only {len(tier1_candidates)} Tier 1 candidates, need {needed}")
        # Could add Tier 2 here if needed

    replacements = tier1_candidates[:needed]
    print(f"\nSelected {len(replacements)} replacements:")
    from collections import Counter
    repo_counts = Counter(c["repo"] for c in replacements)
    for repo, cnt in repo_counts.most_common():
        print(f"  {repo}: {cnt}")

    # Remove invalid instances, add replacements
    new_rows = [r for r in rows if r["instance_id"] not in invalid_ids]
    print(f"\nAfter removing invalid: {len(new_rows)} instances")

    for cand in replacements:
        new_rows.append(candidate_to_dataset_row(cand))
    print(f"After adding replacements: {len(new_rows)} instances")

    # Write updated dataset JSONL
    with open(DATASET_JSONL, "w") as f:
        for row in new_rows:
            f.write(json.dumps(row) + "\n")
    print(f"Wrote updated JSONL: {DATASET_JSONL}")

    # Write all instance IDs
    ids_path = DATA_DIR / "pouya_50_instance_ids.txt"
    with open(ids_path, "w") as f:
        for row in new_rows:
            f.write(row["instance_id"] + "\n")
    print(f"Wrote instance IDs: {ids_path}")

    # Regenerate gold predictions
    gold_preds = []
    for row in new_rows:
        gold_preds.append({
            "instance_id": row["instance_id"],
            "model_patch": row["patch"],
            "model_name_or_path": "gold",
        })
    gold_path = DATA_DIR / "gold_predictions.json"
    with open(gold_path, "w") as f:
        json.dump(gold_preds, f, indent=2)
    print(f"Wrote gold predictions: {gold_path}")

    # Print replacement mapping
    print(f"\n{'='*60}")
    print("Replacement Details")
    print(f"{'='*60}")
    for cand in replacements:
        print(f"  + {cand['instance_id']:50s} (repo={cand['repo']})")
    print(f"\nRemoved:")
    for iid in sorted(invalid_ids):
        print(f"  - {iid}")


if __name__ == "__main__":
    main()
