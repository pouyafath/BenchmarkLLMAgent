import sys, json
sys.path.insert(0, "scripts/data")
from filter_pouya_dataset_2026_f2p_p2p import parse_test_patch

count = 0
repos = set()

with open("data/samples/pouya_dataset_2026/raw_candidates.jsonl") as f:
    for line in f:
        row = json.loads(line)
        f2p, p2p, _ = parse_test_patch(row.get("test_patch", ""))
        if not f2p and p2p:
            count += 1
            repos.add(row["repo"])

print(f"Issues with P2P only (no F2P): {count}")
print(f"Unique repos: {len(repos)}")
