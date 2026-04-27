"""
Comprehensive Metrics Computation for SWE-bench Evaluation.

Computes ALL metrics for benchmarking Issue Enhancer + Solver agents:
1. Fix Rate (SWE-EVO)
2. Regression Rate
3. No-Regression Rate
4. Patch Apply Rate
5. F2P Progress Rate (without regression penalty)
6. File Overlap (Jaccard similarity)
7. Content Similarity (SequenceMatcher)
8. Efficiency Metrics (tokens, cost, time)
9. Trajectory Metrics (turns, tool calls)
"""
import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
import statistics
from difflib import SequenceMatcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent


class ComprehensiveMetrics:
    """Compute all metrics for agent evaluation."""

    # Model pricing (per 1K tokens)
    COST_PER_1K_INPUT = {
        "gpt-4o": 0.0025,
        "gpt-4o-mini": 0.00015,
        "claude-3-5-sonnet": 0.003,
        "claude-sonnet-4": 0.003,
    }
    COST_PER_1K_OUTPUT = {
        "gpt-4o": 0.01,
        "gpt-4o-mini": 0.0006,
        "claude-3-5-sonnet": 0.015,
        "claude-sonnet-4": 0.015,
    }

    def __init__(self, aggregate_report_path: Path, ground_truth_path: Optional[Path] = None):
        """Initialize with paths to reports."""
        with open(aggregate_report_path) as f:
            self.aggregate = json.load(f)

        self.ground_truth = {}
        if ground_truth_path and ground_truth_path.exists():
            with open(ground_truth_path) as f:
                data = json.load(f)
                issues = data.get("issues", data if isinstance(data, list) else [])
                for issue in issues:
                    for key in (
                        issue.get("issue_id"),
                        issue.get("_swe_live_instance_id"),
                    ):
                        if key:
                            self.ground_truth[key] = issue

    def compute_fix_rate(self, f2p_success: int, f2p_total: int, p2p_failures: int) -> float:
        """Fix Rate = (F2P_passed / F2P_total) if no P2P regressions, else 0."""
        if f2p_total == 0:
            return 0.0
        if p2p_failures > 0:
            return 0.0
        return f2p_success / f2p_total

    def compute_f2p_progress_rate(self, f2p_success: int, f2p_total: int) -> float:
        """F2P Progress Rate = F2P_passed / F2P_total (no regression penalty)."""
        if f2p_total == 0:
            return 0.0
        return f2p_success / f2p_total

    def compute_regression_rate(self, p2p_failures: int, p2p_total: int) -> float:
        """Regression Rate = P2P_failures / P2P_total."""
        if p2p_total == 0:
            return 0.0
        return p2p_failures / p2p_total

    def extract_files_from_patch(self, patch: str) -> set:
        """Extract modified file paths from patch."""
        files = set()
        for line in patch.splitlines():
            if line.startswith("+++ b/") or line.startswith("--- a/"):
                filepath = line.split(" ", 1)[1]
                if filepath.startswith("a/") or filepath.startswith("b/"):
                    filepath = filepath[2:]
                if filepath != "/dev/null":
                    files.add(filepath)
        return files

    def compute_file_overlap(self, agent_patch: str, gt_patch: str) -> float:
        """Compute Jaccard similarity of modified files."""
        agent_files = self.extract_files_from_patch(agent_patch)
        gt_files = self.extract_files_from_patch(gt_patch)

        if not agent_files and not gt_files:
            return 1.0
        if not agent_files or not gt_files:
            return 0.0

        intersection = agent_files & gt_files
        union = agent_files | gt_files
        return len(intersection) / len(union)

    def compute_content_similarity(self, agent_patch: str, gt_patch: str) -> float:
        """Compute content similarity using SequenceMatcher."""
        if not agent_patch.strip() and not gt_patch.strip():
            return 1.0
        if not agent_patch.strip() or not gt_patch.strip():
            return 0.0

        matcher = SequenceMatcher(None, agent_patch, gt_patch)
        return matcher.ratio()

    def load_report_json(self, report_path: Path) -> Optional[dict]:
        """Load report.json for an agent-instance pair."""
        if not report_path.exists():
            return None
        try:
            with open(report_path) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load {report_path}: {e}")
            return None

    def compute_all_metrics(self, logs_dir: Path) -> dict:
        """Compute comprehensive metrics for all agents and instances."""

        results = {
            "metadata": {
                "description": "Comprehensive metrics for SWE-bench evaluation",
                "metrics_included": [
                    "Fix Rate", "Regression Rate", "No-Regression Rate",
                    "Patch Apply Rate", "F2P Progress Rate", "F2P Rate",
                    "P2P Rate", "Resolved Rate", "File Overlap",
                    "Content Similarity", "Efficiency Metrics", "Trajectory Metrics"
                ]
            },
            "per_agent_summary": {},
            "per_instance_metrics": {},
            "baseline_comparison": {}
        }

        # Collect all metrics per agent-instance
        agent_metrics = defaultdict(lambda: {
            "fix_rates": [],
            "f2p_progress_rates": [],
            "regression_rates": [],
            "no_regression_count": 0,
            "total_count": 0,
            "f2p_success_total": 0,
            "f2p_total": 0,
            "p2p_success_total": 0,
            "p2p_total": 0,
            "file_overlaps": [],
            "content_similarities": [],
            "total_tokens": [],
            "costs_usd": [],
            "wall_clock_ms": [],
            "num_turns": [],
            "num_tool_calls": [],
        })

        instance_metrics = defaultdict(dict)

        # Ensure agents with zero completed tests still appear in summaries.
        for agent in self.aggregate.get("summary", {}):
            _ = agent_metrics[agent]

        # Process test metrics from aggregate report
        for key, test_data in self.aggregate.get("test_metrics", {}).items():
            agent, instance = key.split("|", 1)

            f2p_success = test_data["f2p_success"]
            f2p_failure = test_data["f2p_failure"]
            f2p_total = f2p_success + f2p_failure

            p2p_success = test_data["p2p_success"]
            p2p_failure = test_data["p2p_failure"]
            p2p_total = p2p_success + p2p_failure

            # Core metrics
            fix_rate = self.compute_fix_rate(f2p_success, f2p_total, p2p_failure)
            f2p_progress = self.compute_f2p_progress_rate(f2p_success, f2p_total)
            regression_rate = self.compute_regression_rate(p2p_failure, p2p_total)

            agent_metrics[agent]["fix_rates"].append(fix_rate)
            agent_metrics[agent]["f2p_progress_rates"].append(f2p_progress)
            agent_metrics[agent]["regression_rates"].append(regression_rate)
            agent_metrics[agent]["total_count"] += 1
            agent_metrics[agent]["f2p_success_total"] += f2p_success
            agent_metrics[agent]["f2p_total"] += f2p_total
            agent_metrics[agent]["p2p_success_total"] += p2p_success
            agent_metrics[agent]["p2p_total"] += p2p_total

            if p2p_failure == 0:
                agent_metrics[agent]["no_regression_count"] += 1

            # Load report.json for additional metrics
            report_path = logs_dir / agent / instance / "report.json"
            report_data = self.load_report_json(report_path)

            agent_patch = ""
            file_overlap = 0.0
            content_sim = 0.0
            tokens = 0
            cost = 0.0
            wall_clock = 0.0
            turns = 0
            tool_calls = 0

            # Load patch from patch.diff file
            patch_file = report_path.parent / "patch.diff"
            if patch_file.exists():
                try:
                    with open(patch_file) as f:
                        agent_patch = f.read()
                except Exception as e:
                    logger.warning(f"Could not read {patch_file}: {e}")

            # Compute alignment metrics
            if agent_patch and instance in self.ground_truth:
                gt_patch = self.ground_truth[instance].get("ground_truth_patch", "")
                file_overlap = self.compute_file_overlap(agent_patch, gt_patch)
                content_sim = self.compute_content_similarity(agent_patch, gt_patch)

                agent_metrics[agent]["file_overlaps"].append(file_overlap)
                agent_metrics[agent]["content_similarities"].append(content_sim)

            if report_data:

                # Extract efficiency metrics
                info = report_data.get("info", {})
                tokens = info.get("total_tokens", 0)

                # Estimate cost
                model = info.get("model_name", "gpt-4o")
                input_rate = self.COST_PER_1K_INPUT.get(model, 0.005)
                output_rate = self.COST_PER_1K_OUTPUT.get(model, 0.015)
                cost = (input_rate * tokens * 0.6 + output_rate * tokens * 0.4) / 1000

                wall_clock = info.get("total_time_ms", 0.0)

                agent_metrics[agent]["total_tokens"].append(tokens)
                agent_metrics[agent]["costs_usd"].append(cost)
                agent_metrics[agent]["wall_clock_ms"].append(wall_clock)

                # Extract trajectory metrics
                turns = info.get("total_turns", 0)
                tool_calls = info.get("total_tool_calls", 0)

                agent_metrics[agent]["num_turns"].append(turns)
                agent_metrics[agent]["num_tool_calls"].append(tool_calls)

            # Store instance-level metrics
            instance_metrics[instance][agent] = {
                "fix_rate": fix_rate,
                "f2p_progress_rate": f2p_progress,
                "regression_rate": regression_rate,
                "file_overlap": file_overlap,
                "content_similarity": content_sim,
                "f2p_success": f2p_success,
                "f2p_total": f2p_total,
                "p2p_failures": p2p_failure,
                "p2p_total": p2p_total,
                "tokens": tokens,
                "cost_usd": cost,
                "wall_clock_ms": wall_clock,
                "turns": turns,
                "tool_calls": tool_calls,
                "resolved": (f2p_success == f2p_total and f2p_total > 0 and p2p_failure == 0)
            }

        # Compute per-agent summary statistics
        for agent, metrics in agent_metrics.items():
            summary_base = self.aggregate.get("summary", {}).get(agent, {})
            submitted = int(summary_base.get("submitted", 0))
            completed = int(summary_base.get("completed", 0))
            resolved = int(summary_base.get("resolved", 0))
            patches_applied = int(summary_base.get("patches_applied", 0))

            f2p_rate = metrics["f2p_success_total"] / metrics["f2p_total"] if metrics["f2p_total"] > 0 else 0.0
            p2p_rate = metrics["p2p_success_total"] / metrics["p2p_total"] if metrics["p2p_total"] > 0 else 0.0
            resolved_rate = resolved / completed if completed > 0 else 0.0
            patch_apply_rate = patches_applied / submitted if submitted > 0 else 0.0

            summary = {
                # Core metrics
                "mean_fix_rate": statistics.mean(metrics["fix_rates"]) if metrics["fix_rates"] else 0.0,
                "mean_f2p_progress_rate": statistics.mean(metrics["f2p_progress_rates"]) if metrics["f2p_progress_rates"] else 0.0,
                "mean_regression_rate": statistics.mean(metrics["regression_rates"]) if metrics["regression_rates"] else 0.0,
                "no_regression_rate": metrics["no_regression_count"] / metrics["total_count"] if metrics["total_count"] > 0 else 0.0,
                "f2p_rate": f2p_rate,
                "p2p_rate": p2p_rate,
                "resolved_rate": resolved_rate,
                "patch_apply_rate": patch_apply_rate,

                # Alignment metrics
                "mean_file_overlap": statistics.mean(metrics["file_overlaps"]) if metrics["file_overlaps"] else 0.0,
                "mean_content_similarity": statistics.mean(metrics["content_similarities"]) if metrics["content_similarities"] else 0.0,

                # Efficiency metrics
                "mean_tokens": statistics.mean(metrics["total_tokens"]) if metrics["total_tokens"] else 0,
                "total_cost_usd": sum(metrics["costs_usd"]),
                "mean_cost_usd": statistics.mean(metrics["costs_usd"]) if metrics["costs_usd"] else 0.0,
                "mean_wall_clock_ms": statistics.mean(metrics["wall_clock_ms"]) if metrics["wall_clock_ms"] else 0.0,

                # Trajectory metrics
                "mean_turns": statistics.mean(metrics["num_turns"]) if metrics["num_turns"] else 0,
                "mean_tool_calls": statistics.mean(metrics["num_tool_calls"]) if metrics["num_tool_calls"] else 0,

                # Counts
                "total_instances": metrics["total_count"],
                "instances_no_regression": metrics["no_regression_count"],
                "submitted_instances": submitted,
                "completed_instances": completed,
                "resolved_instances": resolved,
                "patches_applied": patches_applied,
                "f2p_success_total": metrics["f2p_success_total"],
                "f2p_total": metrics["f2p_total"],
                "p2p_success_total": metrics["p2p_success_total"],
                "p2p_total": metrics["p2p_total"],
            }

            results["per_agent_summary"][agent] = summary

        results["per_instance_metrics"] = dict(instance_metrics)

        # Compute baseline comparison
        baseline_agent = "baseline_no_enhancement"
        if baseline_agent in results["per_agent_summary"]:
            baseline = results["per_agent_summary"][baseline_agent]

            for agent, summary in results["per_agent_summary"].items():
                if agent == baseline_agent:
                    continue

                results["baseline_comparison"][agent] = {
                    "delta_fix_rate": summary["mean_fix_rate"] - baseline["mean_fix_rate"],
                    "delta_f2p_progress": summary["mean_f2p_progress_rate"] - baseline["mean_f2p_progress_rate"],
                    "delta_regression_rate": summary["mean_regression_rate"] - baseline["mean_regression_rate"],
                    "delta_file_overlap": summary["mean_file_overlap"] - baseline["mean_file_overlap"],
                    "delta_content_similarity": summary["mean_content_similarity"] - baseline["mean_content_similarity"],
                    "delta_tokens": summary["mean_tokens"] - baseline["mean_tokens"],
                    "delta_cost_usd": summary["mean_cost_usd"] - baseline["mean_cost_usd"],
                }

        return results


def print_comprehensive_report(results: dict):
    """Print human-readable comprehensive report."""
    print("=" * 120)
    print("COMPREHENSIVE METRICS REPORT")
    print("=" * 120)

    print("\n## 1. CORE METRICS (Fix Rate, F2P Progress, Regression)")
    print("-" * 120)
    print(f"{'Agent':<35} {'Fix Rate':>10} {'F2P Prog':>10} {'Reg Rate':>10} {'No-Reg%':>10} {'#Inst':>8}")
    print("-" * 120)

    for agent, metrics in sorted(results["per_agent_summary"].items()):
        print(f"{agent:<35} "
              f"{metrics['mean_fix_rate']:>10.3f} "
              f"{metrics['mean_f2p_progress_rate']:>10.3f} "
              f"{metrics['mean_regression_rate']:>10.3f} "
              f"{metrics['no_regression_rate']*100:>9.1f}% "
              f"{metrics['total_instances']:>8}")

    print("\n## 2. ALIGNMENT METRICS (File Overlap, Content Similarity)")
    print("-" * 120)
    print(f"{'Agent':<35} {'File Overlap':>15} {'Content Sim':>15}")
    print("-" * 120)

    for agent, metrics in sorted(results["per_agent_summary"].items()):
        print(f"{agent:<35} "
              f"{metrics['mean_file_overlap']:>15.3f} "
              f"{metrics['mean_content_similarity']:>15.3f}")

    print("\n## 3. EFFICIENCY METRICS (Tokens, Cost, Time)")
    print("-" * 120)
    print(f"{'Agent':<35} {'Avg Tokens':>12} {'Avg Cost':>12} {'Total Cost':>12} {'Avg Time(s)':>12}")
    print("-" * 120)

    for agent, metrics in sorted(results["per_agent_summary"].items()):
        avg_time_s = metrics['mean_wall_clock_ms'] / 1000 if metrics['mean_wall_clock_ms'] > 0 else 0
        print(f"{agent:<35} "
              f"{int(metrics['mean_tokens']):>12} "
              f"${metrics['mean_cost_usd']:>11.4f} "
              f"${metrics['total_cost_usd']:>11.4f} "
              f"{avg_time_s:>12.1f}")

    print("\n## 4. TRAJECTORY METRICS (Turns, Tool Calls)")
    print("-" * 120)
    print(f"{'Agent':<35} {'Avg Turns':>12} {'Avg Tool Calls':>15}")
    print("-" * 120)

    for agent, metrics in sorted(results["per_agent_summary"].items()):
        print(f"{agent:<35} "
              f"{metrics['mean_turns']:>12.1f} "
              f"{metrics['mean_tool_calls']:>15.1f}")

    if results["baseline_comparison"]:
        print("\n## 5. BASELINE COMPARISON (Delta Metrics)")
        print("-" * 120)
        print(f"{'Agent':<35} {'ΔFix':>8} {'ΔF2P':>8} {'ΔReg':>8} {'ΔFile':>8} {'ΔCont':>8} {'ΔTokens':>10}")
        print("-" * 120)

        for agent, deltas in sorted(results["baseline_comparison"].items()):
            print(f"{agent:<35} "
                  f"{deltas['delta_fix_rate']:>+8.3f} "
                  f"{deltas['delta_f2p_progress']:>+8.3f} "
                  f"{deltas['delta_regression_rate']:>+8.3f} "
                  f"{deltas['delta_file_overlap']:>+8.3f} "
                  f"{deltas['delta_content_similarity']:>+8.3f} "
                  f"{int(deltas['delta_tokens']):>+10}")

    print("\n" + "=" * 120)


def main():
    """Run comprehensive metrics computation."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--aggregate-report",
        type=Path,
        default=ROOT / "eval_results/swebench/iteration1_v3_aggregate_report.json",
        help="Path to aggregate report JSON",
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=ROOT / "data/samples/swe_bench_live_10_samples.json",
        help="Path to samples/ground-truth JSON",
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=ROOT / "logs/run_evaluation/iteration1_v3",
        help="Harness logs directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "eval_results/swebench/iteration1_v3_comprehensive_metrics.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    print("Computing comprehensive metrics...")

    metrics_computer = ComprehensiveMetrics(args.aggregate_report, args.ground_truth)
    results = metrics_computer.compute_all_metrics(args.logs_dir)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)

    print(f"✓ Saved comprehensive metrics to: {args.output}\n")
    print_comprehensive_report(results)

    return results


if __name__ == "__main__":
    main()
