"""
Select sample issues from Paper 2's golden dataset.

Criteria:
  - closure_type == "pull_request"
  - PR is in the same repo (not cross-repo)
  - Mix of bug and feature labels
  - Prefer smaller, focused issues

Usage:
    python -m scripts.data.select_samples
"""

import json
import re
import os
import sys
import time
import requests
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

GOLDEN_DATASET = "/home/22pf2/LLMforGithubIssuesRefactor/data/rq3/400_golden_dataset_filtered.json"
OUTPUT_PATH = str(PROJECT_ROOT / "data" / "samples" / "pilot_10_samples.json")
GT_DIR = str(PROJECT_ROOT / "data" / "ground_truth")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"Accept": "application/vnd.github.v3+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"


def extract_pr_info(closure_url, repo_name):
    """Extract owner, repo, and PR number from closure_url. Return None if cross-repo."""
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", closure_url)
    if not match:
        return None
    owner, repo, pr_num = match.group(1), match.group(2), int(match.group(3))
    url_repo = f"{owner}/{repo}"
    if url_repo.lower() != repo_name.lower():
        return None
    return owner, repo, pr_num


def fetch_pr_details(owner, repo, pr_num):
    """Fetch PR details and check if it's merged with code changes."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_num}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        print(f"  PR fetch failed: HTTP {resp.status_code}")
        return None
    data = resp.json()
    if not data.get("merged"):
        print(f"  PR not merged")
        return None
    return data


def fetch_pr_files(owner, repo, pr_num):
    """Fetch files changed in the PR."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_num}/files"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        return []
    return resp.json()


def fetch_pr_patch(owner, repo, pr_num):
    """Fetch the full PR patch content."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_num}"
    h = {**HEADERS, "Accept": "application/vnd.github.v3.patch"}
    resp = requests.get(url, headers=h, timeout=60)
    if resp.status_code == 200:
        return resp.text
    return ""


def score_candidate(issue, pr_files):
    """Score a candidate issue for suitability. Lower is better."""
    n_files = len(pr_files)
    total_changes = sum(f.get("changes", 0) for f in pr_files)
    body_len = len(issue.get("source_repo_entry", {}).get("body", ""))

    if n_files == 0 or n_files > 10:
        return 9999
    if total_changes > 500:
        return 9999

    score = n_files * 10 + total_changes * 0.1
    if body_len < 50:
        score += 50
    return score


def main():
    print("Loading golden dataset...")
    with open(GOLDEN_DATASET) as f:
        data = json.load(f)
    issues = data["issues"]
    print(f"Total issues: {len(issues)}")

    candidates = []
    for issue in issues:
        entry = issue.get("source_repo_entry", {})
        closure_type = entry.get("closure_type", "")
        closure_url = entry.get("closure_url", "")
        repo_name = issue.get("repo_name", "")
        label = entry.get("label_classification", "")

        if closure_type != "pull_request":
            continue
        pr_info = extract_pr_info(closure_url, repo_name)
        if pr_info is None:
            continue

        candidates.append({
            "repo_name": repo_name,
            "issue_number": issue["issue_number"],
            "issue_id": issue.get("issue_id"),
            "title": entry.get("title", ""),
            "body": entry.get("body", ""),
            "label": label,
            "difficulty": entry.get("difficulty_to_solve", ""),
            "closure_url": closure_url,
            "pr_owner": pr_info[0],
            "pr_repo": pr_info[1],
            "pr_number": pr_info[2],
            "lightgbm_score": issue.get("lightgbm_score", 0),
        })

    print(f"Candidates with same-repo PRs: {len(candidates)}")

    bugs = [c for c in candidates if c["label"] == "bug"]
    features = [c for c in candidates if c["label"] in ("feature", "enhancement")]
    other = [c for c in candidates if c["label"] not in ("bug", "feature", "enhancement")]
    print(f"  Bugs: {len(bugs)}, Features: {len(features)}, Other: {len(other)}")

    print("\nFetching PR details to find best candidates...")
    scored = []

    all_candidates = bugs + features + other
    for i, cand in enumerate(all_candidates):
        if len(scored) >= 30:
            break

        owner, repo, pr_num = cand["pr_owner"], cand["pr_repo"], cand["pr_number"]
        print(f"[{i+1}/{len(all_candidates)}] {owner}/{repo}#{cand['issue_number']} PR#{pr_num} ({cand['label']})...", end="")

        pr_data = fetch_pr_details(owner, repo, pr_num)
        if pr_data is None:
            continue

        pr_files = fetch_pr_files(owner, repo, pr_num)
        if not pr_files:
            print(f"  No files")
            continue

        has_code = any(
            f["filename"].endswith(('.py', '.js', '.ts', '.java', '.go', '.rb', '.rs', '.cpp', '.c', '.cs', '.php'))
            for f in pr_files
        )
        if not has_code:
            print(f"  No code files")
            continue

        score = score_candidate(cand, pr_files)
        if score >= 9999:
            print(f"  Too large/small")
            continue

        cand["score"] = score
        cand["pr_files_count"] = len(pr_files)
        cand["pr_changes"] = sum(f.get("changes", 0) for f in pr_files)
        cand["pr_merge_sha"] = pr_data.get("merge_commit_sha", "")
        cand["pr_base_sha"] = pr_data.get("base", {}).get("sha", "")
        cand["pr_files"] = [{"filename": f["filename"], "status": f["status"],
                             "additions": f.get("additions", 0), "deletions": f.get("deletions", 0),
                             "changes": f.get("changes", 0)} for f in pr_files]
        scored.append(cand)
        print(f" OK (files={len(pr_files)}, changes={cand['pr_changes']}, score={score:.1f})")

        time.sleep(0.5)

    scored.sort(key=lambda x: x["score"])

    selected_bugs = [s for s in scored if s["label"] == "bug"][:5]
    selected_features = [s for s in scored if s["label"] in ("feature", "enhancement")][:5]
    selected = selected_bugs + selected_features

    if len(selected) < 10:
        remaining = [s for s in scored if s not in selected]
        selected.extend(remaining[:10 - len(selected)])

    selected = selected[:10]

    print(f"\n=== Selected {len(selected)} issues ===")
    for i, s in enumerate(selected):
        print(f"  {i+1}. {s['repo_name']}#{s['issue_number']} [{s['label']}] "
              f"files={s['pr_files_count']} changes={s['pr_changes']} - {s['title'][:60]}")

    print("\nFetching full PR patches for ground truth...")
    os.makedirs(GT_DIR, exist_ok=True)
    for s in selected:
        patch = fetch_pr_patch(s["pr_owner"], s["pr_repo"], s["pr_number"])
        s["ground_truth_patch"] = patch
        gt_file = os.path.join(GT_DIR, f"{s['pr_owner']}__{s['pr_repo']}__{s['issue_number']}.json")
        with open(gt_file, "w") as f:
            json.dump({
                "issue_id": f"{s['repo_name']}#{s['issue_number']}",
                "pr_number": s["pr_number"],
                "pr_merge_sha": s["pr_merge_sha"],
                "pr_base_sha": s["pr_base_sha"],
                "pr_files": s["pr_files"],
                "patch": patch,
            }, f, indent=2)
        print(f"  Saved GT for {s['repo_name']}#{s['issue_number']} ({len(patch)} chars)")
        time.sleep(0.3)

    output_data = {
        "metadata": {
            "description": "10 initial sample issues for BenchmarkLLMAgent pilot",
            "source": "Paper 2 golden dataset (400_golden_dataset_filtered.json)",
            "selection_criteria": "Same-repo merged PRs with code changes, balanced bug/feature",
            "count": len(selected),
        },
        "issues": selected,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\nSaved {len(selected)} samples to {OUTPUT_PATH}")
    print(f"Ground truth saved to {GT_DIR}/")


if __name__ == "__main__":
    main()
