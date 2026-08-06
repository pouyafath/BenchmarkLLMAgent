import sys, json
sys.path.insert(0, "scripts/data")
from filter_pouya_dataset_2026_f2p_p2p import parse_test_patch

raw_issues = 0
raw_repos = set()

f2p_and_p2p = 0
f2p_and_p2p_repos = set()

p2p_only = 0
p2p_only_repos = set()

f2p_only = 0
f2p_only_repos = set()

neither = 0

with open("data/samples/pouya_dataset_2026/raw_candidates.jsonl") as f:
    for line in f:
        row = json.loads(line)
        raw_issues += 1
        repo = row["repo"]
        raw_repos.add(repo)
        
        f2p, p2p, _ = parse_test_patch(row.get("test_patch", ""))
        
        if f2p and p2p:
            f2p_and_p2p += 1
            f2p_and_p2p_repos.add(repo)
        elif not f2p and p2p:
            p2p_only += 1
            p2p_only_repos.add(repo)
        elif f2p and not p2p:
            f2p_only += 1
            f2p_only_repos.add(repo)
        else:
            neither += 1

print(f"Total Raw Candidates: {raw_issues} issues in {len(raw_repos)} repos")
print(f" - Both F2P and P2P: {f2p_and_p2p} issues in {len(f2p_and_p2p_repos)} repos")
print(f" - Only P2P (No F2P): {p2p_only} issues in {len(p2p_only_repos)} repos")
print(f" - Only F2P (No P2P): {f2p_only} issues in {len(f2p_only_repos)} repos")
print(f" - Neither F2P nor P2P: {neither} issues")
