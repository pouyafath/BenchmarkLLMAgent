"""
Generate enhancement benchmark report for multiple enhancer agents.

Parses: openai_agents_sdk_after_enhancement__{agent}__{owner}__{repo}__{issue}.json
Compares patch quality (content similarity) vs baseline for each enhancer.
Supports both SWE-bench-Live (data/ground_truth_swe_bench_live/) and the old
pilot dataset (data/ground_truth/), auto-detecting which GT directory to use.
"""

import json
from pathlib import Path
from collections import defaultdict

import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.patch_utils import strip_git_metadata
from difflib import SequenceMatcher

BASELINE_DIR = PROJECT_ROOT / "results" / "pilot_solver_benchmark"
AFTER_DIR    = PROJECT_ROOT / "results" / "solving_after_enhancement"
# Ground truth: prefer SWE-bench-Live dir, fall back to old pilot dir
GT_DIR_SWE  = PROJECT_ROOT / "data" / "ground_truth_swe_bench_live"
GT_DIR_OLD  = PROJECT_ROOT / "data" / "ground_truth"

# Solver prefixes used in solving-after-enhancement filenames
SOLVER_PREFIXES = [
    "openai_agents_sdk_after_enhancement",
    "simple_solver_after_enhancement",
]


def load_result(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def compute_similarity(agent_patch: str, gt_patch: str) -> float:
    gt_diff = strip_git_metadata(gt_patch)
    agent_diff = strip_git_metadata(agent_patch) if agent_patch and "diff --git" in agent_patch else (agent_patch or "")
    if not agent_diff or not gt_diff:
        return 0.0
    return SequenceMatcher(None, agent_diff, gt_diff).ratio()


def main():
    # Collect all solving-after-enhancement files regardless of solver prefix
    after_files = []
    for prefix in SOLVER_PREFIXES:
        after_files.extend(sorted(AFTER_DIR.glob(f"{prefix}__*.json")))
    after_files = sorted(set(after_files))

    if not after_files:
        print("No solving-after-enhancement results found.")
        return

    # Parse filenames: <solver_prefix>__<agent>__<owner>__<repo>__<issue>.json
    agent_rows = defaultdict(list)
    for af in after_files:
        stem = af.stem
        # Strip any known solver prefix
        for prefix in SOLVER_PREFIXES:
            if stem.startswith(prefix + "__"):
                stem = stem[len(prefix) + 2:]
                break
        parts = stem.split("__")
        if len(parts) < 4:
            continue
        agent_id, owner, repo = parts[0], parts[1], parts[2]
        try:
            issue_num = int(parts[3])
        except ValueError:
            continue
        issue_id = f"{owner}/{repo}#{issue_num}"

        # Locate ground truth: prefer SWE-bench-Live dir
        gt_path = GT_DIR_SWE / f"{owner}__{repo}__{issue_num}.json"
        if not gt_path.exists():
            gt_path = GT_DIR_OLD / f"{owner}__{repo}__{issue_num}.json"

        # Locate baseline: try both simple_solver and openai_agents_sdk prefixes
        baseline_path = BASELINE_DIR / f"simple_solver__{owner}__{repo}__{issue_num}.json"
        if not baseline_path.exists():
            baseline_path = BASELINE_DIR / f"openai_agents_sdk__{owner}__{repo}__{issue_num}.json"
        gt_data = load_result(gt_path)
        baseline_data = load_result(baseline_path)
        after_data = load_result(af)

        gt_patch = gt_data.get("patch", "")
        b_patch = baseline_data.get("patch", "")
        a_patch = after_data.get("patch", "")

        b_sim = compute_similarity(b_patch, gt_patch)
        a_sim = compute_similarity(a_patch, gt_patch)
        delta_sim = a_sim - b_sim

        agent_rows[agent_id].append({
            "issue_id": issue_id,
            "b_sim": b_sim,
            "a_sim": a_sim,
            "delta_sim": delta_sim,
        })

    # Summary table per agent
    print(f"\n{'='*100}")
    print(f"{'ENHANCEMENT BENCHMARK: Baseline vs Solving-After-Enhancement (by Enhancer Agent)':^100}")
    print(f"{'='*100}")

    summary = []
    for agent_id in sorted(agent_rows.keys()):
        rows = agent_rows[agent_id]
        n = len(rows)
        avg_b = sum(r["b_sim"] for r in rows) / n
        avg_a = sum(r["a_sim"] for r in rows) / n
        avg_delta = avg_a - avg_b
        improved = sum(1 for r in rows if r["delta_sim"] > 0)
        same = sum(1 for r in rows if r["delta_sim"] == 0)
        worse = sum(1 for r in rows if r["delta_sim"] < 0)
        summary.append({
            "agent": agent_id,
            "n": n,
            "avg_baseline": avg_b,
            "avg_after": avg_a,
            "avg_delta": avg_delta,
            "improved": improved,
            "same": same,
            "worse": worse,
        })

    print(f"\n{'Agent':<22} {'N':>4} {'Baseline':>9} {'After':>9} {'Delta':>9} {'Improv':>7} {'Same':>5} {'Worse':>6}")
    print("-" * 85)
    for s in sorted(summary, key=lambda x: -x["avg_delta"]):
        d_str = f"+{s['avg_delta']:.4f}" if s["avg_delta"] >= 0 else f"{s['avg_delta']:.4f}"
        print(f"{s['agent']:<22} {s['n']:>4} {s['avg_baseline']:>9.4f} {s['avg_after']:>9.4f} {d_str:>9} "
              f"{s['improved']:>7} {s['same']:>5} {s['worse']:>6}")

    # Per-issue detail for top agent
    best = max(summary, key=lambda x: x["avg_delta"])
    print(f"\n--- Per-issue detail (best enhancer: {best['agent']}) ---")
    print(f"{'Issue':<45} {'Baseline':>9} {'After':>9} {'Delta':>9}")
    print("-" * 80)
    for r in agent_rows[best["agent"]]:
        d_str = f"+{r['delta_sim']:.4f}" if r["delta_sim"] >= 0 else f"{r['delta_sim']:.4f}"
        print(f"{r['issue_id']:<45} {r['b_sim']:>9.4f} {r['a_sim']:>9.4f} {d_str:>9}")

    # Save JSON
    out_path = PROJECT_ROOT / "results" / "enhancement_benchmark" / "enhancement_report_multi_agent.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({
            "per_agent": summary,
            "per_agent_per_issue": {k: v for k, v in agent_rows.items()},
        }, f, indent=2)
    print(f"\nSaved: {out_path}")
    print(f"{'='*100}\n")


if __name__ == "__main__":
    main()
