#!/usr/bin/env python3
"""Select 5 diverse test issues from the groupC50 dataset.

Picks issues at 5 body-length percentiles (shortest, 25th, median, 75th, longest)
to cover both sparse and rich signal diversity for testing LLM append strategies.

Output:
  data/samples/llm_append_test_5/test_5_instance_ids.txt
  data/samples/llm_append_test_5/test_5_samples.json
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLES_JSON = ROOT / "data/samples/groupC_swebenchlive_50/groupC_50_samples.json"
OUT_DIR = ROOT / "data/samples/llm_append_test_5"


def main():
    with open(SAMPLES_JSON) as f:
        data = json.load(f)

    issues = data["issues"]
    # Sort by body length
    sorted_issues = sorted(issues, key=lambda x: len(x.get("body", "")))
    n = len(sorted_issues)

    # Pick 5 percentile indices: 0%, 25%, 50%, 75%, 100%
    indices = [0, n // 4, n // 2, 3 * n // 4, n - 1]
    # Deduplicate in case of small dataset
    seen = set()
    selected = []
    for idx in indices:
        iid = sorted_issues[idx]["issue_id"]
        if iid not in seen:
            seen.add(iid)
            selected.append(sorted_issues[idx])

    # Print selection info
    print(f"Selected {len(selected)} issues from {n} total:")
    for i, iss in enumerate(selected):
        body_len = len(iss.get("body", ""))
        print(f"  {i+1}. {iss['issue_id']} (body={body_len} chars, repo={iss['repo_name']})")

    # Write output
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ids_file = OUT_DIR / "test_5_instance_ids.txt"
    with open(ids_file, "w") as f:
        for iss in selected:
            f.write(iss["issue_id"] + "\n")
    print(f"\nWrote {ids_file}")

    samples_file = OUT_DIR / "test_5_samples.json"
    out_data = {
        "metadata": {
            "description": "5-issue test subset for LLM append enhancer strategies",
            "source": "groupC_swebenchlive_50",
            "selection": "body-length percentiles (0%, 25%, 50%, 75%, 100%)",
            "count": len(selected),
        },
        "issues": selected,
    }
    with open(samples_file, "w") as f:
        json.dump(out_data, f, indent=2)
    print(f"Wrote {samples_file}")


if __name__ == "__main__":
    main()
