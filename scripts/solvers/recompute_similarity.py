"""
Recompute content similarity using only the actual diff content,
stripping git commit metadata (From, Author, Date, Subject, ---, stat lines).

Usage:
    python -m scripts.solvers.recompute_similarity
"""

import json
import sys
from pathlib import Path
from difflib import SequenceMatcher

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GT_DIR = PROJECT_ROOT / "data" / "ground_truth"
RES_DIR = PROJECT_ROOT / "results" / "pilot_solver_benchmark"

sys.path.insert(0, str(PROJECT_ROOT))
from src.utils.patch_utils import strip_git_metadata

SAMPLES = json.load(open(PROJECT_ROOT / "data" / "samples" / "pilot_10_samples.json"))

FRAMEWORKS = ["autogen", "crewai", "langgraph", "openai_agents_sdk"]

header = f"{'Issue':<42} {'Framework':<22} {'OldSim':>8} {'NewSim':>8} {'Delta':>7}"
print(header)
print("-" * len(header))

updates = []
for fw in FRAMEWORKS:
    for issue in SAMPLES["issues"]:
        iid = f"{issue['repo_name']}#{issue['issue_number']}"
        gt_file = GT_DIR / f"{issue['pr_owner']}__{issue['pr_repo']}__{issue['issue_number']}.json"
        gt = json.load(open(gt_file)) if gt_file.exists() else {}
        gt_patch_full = gt.get("patch", "")
        gt_patch_diff = strip_git_metadata(gt_patch_full)
        gt_files = {f["filename"] for f in gt.get("pr_files", [])}

        res_file = RES_DIR / f"{fw}__{issue['repo_name'].replace('/','__')}__{issue['issue_number']}.json"
        if not res_file.exists():
            continue
        r = json.load(open(res_file))
        if r.get("error"):
            continue

        agent_patch = r.get("patch", "")
        if fw == "crewai":
            agent_patch = agent_patch.replace("\\n", "\n").replace("\\t", "\t")

        agent_diff = strip_git_metadata(agent_patch) if "diff --git" in agent_patch else agent_patch

        old_sim = r.get("evaluation", {}).get("content_similarity", 0)
        new_sim = SequenceMatcher(None, agent_diff, gt_patch_diff).ratio() if agent_diff and gt_patch_diff else 0

        delta = new_sim - old_sim
        print(f"{iid:<42} {fw:<22} {old_sim:>8.4f} {new_sim:>8.4f} {delta:>+7.4f}")

        r["evaluation"]["content_similarity"] = new_sim
        r["evaluation"]["content_similarity_method"] = "diff_only"
        updates.append((res_file, r))

for path, data in updates:
    path.write_text(json.dumps(data, indent=2))

print(f"\nUpdated {len(updates)} result files with diff-only similarity")

# Print framework averages
print(f"\n{'Framework':<22} {'Avg Old':>10} {'Avg New':>10} {'Improvement':>12}")
print("-" * 58)
for fw in FRAMEWORKS:
    old_vals = []
    new_vals = []
    for issue in SAMPLES["issues"]:
        iid = f"{issue['repo_name']}#{issue['issue_number']}"
        res_file = RES_DIR / f"{fw}__{issue['repo_name'].replace('/','__')}__{issue['issue_number']}.json"
        if not res_file.exists():
            continue
        r = json.load(open(res_file))
        if not r.get("error"):
            new_vals.append(r["evaluation"]["content_similarity"])
    avg_new = sum(new_vals) / len(new_vals) if new_vals else 0
    print(f"{fw:<22} {'':>10} {avg_new:>10.4f}")
