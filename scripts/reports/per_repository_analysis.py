"""
Per-repository breakdown of 101-issue experiment results.

Analyzes results at the repository level to identify patterns across different
codebases (e.g., astropy vs sklearn vs matplotlib).

Usage:
    python scripts/reports/per_repository_analysis.py
"""
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent.parent


def parse_repo_from_instance_id(instance_id: str) -> str:
    """Extract repository name from instance_id (e.g., 'astropy__astropy-123' -> 'astropy')."""
    parts = instance_id.split("__")
    if len(parts) >= 2:
        return parts[0]
    return "unknown"


def load_comparison_summary(results_dir: Path) -> Dict:
    """Load comparison_summary.json from experiment results directory."""
    summary_file = results_dir / "comparison_summary.json"
    if not summary_file.exists():
        return None

    with open(summary_file) as f:
        return json.load(f)


def analyze_per_repository(data: Dict, section: str) -> Dict[str, Dict]:
    """
    Analyze results per repository.

    Returns:
        Dict mapping repo -> {resolved_count, total_count, resolved_ids}
    """
    per_instance = data.get(section, {}).get("per_instance", [])
    repo_stats = defaultdict(lambda: {"resolved_ids": [], "total_ids": []})

    for item in per_instance:
        instance_id = item["instance_id"]
        resolved = item.get("resolved", False)
        repo = parse_repo_from_instance_id(instance_id)

        repo_stats[repo]["total_ids"].append(instance_id)
        if resolved:
            repo_stats[repo]["resolved_ids"].append(instance_id)

    # Compute counts and rates
    results = {}
    for repo, stats in repo_stats.items():
        total = len(stats["total_ids"])
        resolved = len(stats["resolved_ids"])
        rate = resolved / total if total > 0 else 0.0

        results[repo] = {
            "total_count": total,
            "resolved_count": resolved,
            "resolved_rate": rate,
            "resolved_ids": stats["resolved_ids"],
            "total_ids": stats["total_ids"],
        }

    return results


def print_repo_table(group_name: str, agent_name: str, baseline_repos: Dict, enhanced_repos: Dict):
    """Print per-repository comparison table."""
    print(f"\n{'='*100}")
    print(f"{group_name} - {agent_name.upper()} - Per-Repository Breakdown")
    print(f"{'='*100}")

    all_repos = sorted(set(baseline_repos.keys()) | set(enhanced_repos.keys()))

    print(f"\n{'Repository':<25} | {'Baseline':<25} | {'Enhanced':<25} | {'Delta':<15}")
    print("-" * 100)

    for repo in all_repos:
        b_data = baseline_repos.get(repo, {})
        e_data = enhanced_repos.get(repo, {})

        b_total = b_data.get("total_count", 0)
        b_resolved = b_data.get("resolved_count", 0)
        b_rate = b_data.get("resolved_rate", 0.0)

        e_total = e_data.get("total_count", 0)
        e_resolved = e_data.get("resolved_count", 0)
        e_rate = e_data.get("resolved_rate", 0.0)

        b_str = f"{b_resolved}/{b_total} ({b_rate*100:.1f}%)" if b_total > 0 else "N/A"
        e_str = f"{e_resolved}/{e_total} ({e_rate*100:.1f}%)" if e_total > 0 else "N/A"

        if b_total > 0 and e_total > 0:
            delta = e_rate - b_rate
            delta_str = f"{delta:+.1%}"
        else:
            delta_str = "N/A"

        print(f"{repo:<25} | {b_str:<25} | {e_str:<25} | {delta_str:<15}")


def generate_repo_comparison_across_agents(group_name: str, experiments: Dict[str, Dict]):
    """Compare repository performance across all agents."""
    print(f"\n{'='*100}")
    print(f"{group_name} - Repository Performance Across Agents (Baseline)")
    print(f"{'='*100}")

    # Collect all repos and agents
    all_repos = set()
    agent_repo_data = {}

    for agent_name, data in experiments.items():
        if data:
            baseline_repos = analyze_per_repository(data, "baseline")
            agent_repo_data[agent_name] = baseline_repos
            all_repos.update(baseline_repos.keys())

    all_repos = sorted(all_repos)
    agents = sorted(agent_repo_data.keys())

    # Print table header
    header = f"{'Repository':<25}"
    for agent in agents:
        header += f" | {agent:<20}"
    print(f"\n{header}")
    print("-" * (25 + len(agents) * 23))

    # Print each repository
    for repo in all_repos:
        row = f"{repo:<25}"
        for agent in agents:
            repo_data = agent_repo_data[agent].get(repo, {})
            total = repo_data.get("total_count", 0)
            resolved = repo_data.get("resolved_count", 0)
            rate = repo_data.get("resolved_rate", 0.0)

            if total > 0:
                cell = f"{resolved}/{total} ({rate*100:.1f}%)"
            else:
                cell = "N/A"
            row += f" | {cell:<20}"
        print(row)


def main():
    """Main entry point."""
    print("="*100)
    print("PER-REPOSITORY ANALYSIS - 101-ISSUE EXPERIMENTS")
    print(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("="*100)

    results_root = ROOT / "data/samples/101_issues_experiments"

    experiments = {
        "Group A": {
            "trae": results_root / "results_group_a/trae__devstral101_groupA_20260327",
            "aider": results_root / "results_group_a/aider__devstral101_groupA_20260327",
            "swe_agent": results_root / "results_group_a/swe_agent__devstral101_groupA_20260327",
        },
        "Group B": {
            "trae": results_root / "results_group_b/trae__devstral101_groupB_20260327",
            "aider": results_root / "results_group_b/aider__devstral101_groupB_20260327",
            "swe_agent": results_root / "results_group_b/swe_agent__devstral101_groupB_20260327",
        }
    }

    # Load and analyze each experiment
    for group_name, group_experiments in experiments.items():
        group_data = {}

        print(f"\n\n{'#'*100}")
        print(f"# {group_name.upper()}")
        print(f"{'#'*100}")

        for agent_name, path in sorted(group_experiments.items()):
            data = load_comparison_summary(path)
            if data:
                group_data[agent_name] = data
                baseline_repos = analyze_per_repository(data, "baseline")
                enhanced_repos = analyze_per_repository(data, "enhanced")
                print_repo_table(group_name, agent_name, baseline_repos, enhanced_repos)
            else:
                print(f"\n⚠ Missing data for {agent_name}: {path}")

        # Cross-agent comparison for this group
        if group_data:
            generate_repo_comparison_across_agents(group_name, group_data)

    # Save structured output
    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "group_a": {},
        "group_b": {},
    }

    for agent_name, path in experiments["Group A"].items():
        data = load_comparison_summary(path)
        if data:
            output["group_a"][agent_name] = {
                "baseline_per_repo": analyze_per_repository(data, "baseline"),
                "enhanced_per_repo": analyze_per_repository(data, "enhanced"),
            }

    for agent_name, path in experiments["Group B"].items():
        data = load_comparison_summary(path)
        if data:
            output["group_b"][agent_name] = {
                "baseline_per_repo": analyze_per_repository(data, "baseline"),
                "enhanced_per_repo": analyze_per_repository(data, "enhanced"),
            }

    output_file = results_root / "101_issue_per_repository_analysis.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n\n{'='*100}")
    print(f"✓ Saved structured results to: {output_file}")
    print("="*100)


if __name__ == "__main__":
    main()
