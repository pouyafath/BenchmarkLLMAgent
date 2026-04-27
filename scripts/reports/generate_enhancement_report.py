"""
Generate enhancement benchmark report: baseline vs solving-after-enhancement.

Compares patch quality (file overlap, content similarity) for:
- Baseline: solver on original issues
- After: solver on enhanced issues

Usage:
    python scripts/reports/generate_enhancement_report.py
"""

import json
from pathlib import Path
from difflib import SequenceMatcher

import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

BASELINE_DIR = PROJECT_ROOT / "results" / "pilot_solver_benchmark"
AFTER_DIR = PROJECT_ROOT / "results" / "solving_after_enhancement"
GT_DIR = PROJECT_ROOT / "data" / "ground_truth"

from src.utils.patch_utils import strip_git_metadata


def load_result(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def compute_similarity_diff_only(agent_patch: str, gt_patch: str) -> float:
    gt_diff = strip_git_metadata(gt_patch)
    agent_diff = strip_git_metadata(agent_patch) if "diff --git" in agent_patch else agent_patch
    if not agent_diff or not gt_diff:
        return 0.0
    return SequenceMatcher(None, agent_diff, gt_diff).ratio()


def main():
    after_files = sorted(AFTER_DIR.glob("simple_solver_after_enhancement__*.json"))
    if not after_files:
        print("No solving-after-enhancement results found. Run run_solving_after_enhancement.py first.")
        return

    print(f"\n{'='*90}")
    print(f"{'ENHANCEMENT BENCHMARK REPORT: Baseline vs Solving-After-Enhancement':^90}")
    print(f"{'='*90}")

    rows = []
    for af in after_files:
        # Parse: simple_solver_after_enhancement__owner__repo__issue.json
        stem = af.stem.replace("simple_solver_after_enhancement__", "")
        parts = stem.split("__")
        if len(parts) < 3:
            continue
        owner, repo = parts[0], parts[1]
        try:
            issue_num = int(parts[2])
        except ValueError:
            continue
        issue_id = f"{owner}/{repo}#{issue_num}"

        baseline_path = BASELINE_DIR / f"simple_solver__{owner}__{repo}__{issue_num}.json"
        gt_path = GT_DIR / f"{owner}__{repo}__{issue_num}.json"

        after_data = load_result(af)
        baseline_data = load_result(baseline_path)
        gt_data = load_result(gt_path)

        gt_patch = gt_data.get("patch", "")
        gt_files = gt_data.get("pr_files", [])

        b_patch = baseline_data.get("patch", "")
        a_patch = after_data.get("patch", "")

        b_ev = baseline_data.get("evaluation", {})
        a_ev = after_data.get("evaluation", {})

        b_file_ovlp = b_ev.get("file_overlap", 0)
        a_file_ovlp = a_ev.get("file_overlap", 0)
        b_sim = compute_similarity_diff_only(b_patch, gt_patch)
        a_sim = compute_similarity_diff_only(a_patch, gt_patch)

        delta_file = a_file_ovlp - b_file_ovlp
        delta_sim = a_sim - b_sim

        rows.append({
            "issue_id": issue_id,
            "b_file_ovlp": b_file_ovlp,
            "a_file_ovlp": a_file_ovlp,
            "delta_file": delta_file,
            "b_sim": b_sim,
            "a_sim": a_sim,
            "delta_sim": delta_sim,
            "b_time": baseline_data.get("elapsed_s", 0),
            "a_time": after_data.get("elapsed_s", 0),
        })

    # Per-issue table
    print(f"\n{'Issue':<42} {'FileOvlp':^16} {'Sim (diff-only)':^18} {'Delta':^10}")
    print(f"{'':42} {'Baseline':>7} {'After':>7} {'B':>7} {'A':>7} {'Sim':>8}")
    print("-" * 95)

    for r in rows:
        d_f = r["delta_file"]
        d_s = r["delta_sim"]
        d_str = f"+{d_s:.3f}" if d_s >= 0 else f"{d_s:.3f}"
        print(f"{r['issue_id']:<42} {r['b_file_ovlp']:>7.3f} {r['a_file_ovlp']:>7.3f} "
              f"{r['b_sim']:>7.3f} {r['a_sim']:>7.3f} {d_str:>8}")

    # Summary
    n = len(rows)
    avg_b_sim = sum(r["b_sim"] for r in rows) / n
    avg_a_sim = sum(r["a_sim"] for r in rows) / n
    avg_delta_sim = avg_a_sim - avg_b_sim
    improved = sum(1 for r in rows if r["delta_sim"] > 0)
    same = sum(1 for r in rows if r["delta_sim"] == 0)
    worse = sum(1 for r in rows if r["delta_sim"] < 0)

    print("-" * 95)
    print(f"\n{'SUMMARY':^95}")
    print(f"\n  Issues: {n}")
    print(f"  Avg similarity (baseline):  {avg_b_sim:.4f}")
    print(f"  Avg similarity (after):     {avg_a_sim:.4f}")
    print(f"  Delta (after - baseline):   {avg_delta_sim:+.4f}")
    print(f"  Improved: {improved}  |  Same: {same}  |  Worse: {worse}")

    # Save JSON summary
    summary_path = PROJECT_ROOT / "results" / "enhancement_benchmark" / "enhancement_report_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump({
            "n_issues": n,
            "avg_similarity_baseline": round(avg_b_sim, 4),
            "avg_similarity_after": round(avg_a_sim, 4),
            "avg_delta_similarity": round(avg_delta_sim, 4),
            "improved": improved,
            "same": same,
            "worse": worse,
            "per_issue": rows,
        }, f, indent=2)
    print(f"\n  Saved: {summary_path}")
    print(f"\n{'='*90}\n")


if __name__ == "__main__":
    main()
