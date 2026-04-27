"""
Aggregate and analyze 101-issue experiment results.

Reads comparison_summary.json files from both Group A and Group B experiments
and generates comprehensive tables with Resolved, F2P, and P2P metrics.

Usage:
    python scripts/reports/analyze_101_issue_results.py
"""
import json
import sys
from pathlib import Path
from typing import Dict, List
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent.parent


def load_comparison_summary(results_dir: Path) -> Dict:
    """Load comparison_summary.json from experiment results directory."""
    summary_file = results_dir / "comparison_summary.json"
    if not summary_file.exists():
        raise FileNotFoundError(f"No comparison summary found: {summary_file}")

    with open(summary_file) as f:
        return json.load(f)


def format_rate(value: float) -> str:
    """Format rate as percentage with 1 decimal."""
    return f"{value * 100:.1f}%"


def format_fraction(count: int, total: int) -> str:
    """Format count/total (rate%)."""
    rate = count / total * 100 if total > 0 else 0.0
    return f"{count}/{total} ({rate:.1f}%)"


def extract_metrics(data: Dict, section: str) -> Dict:
    """Extract Resolved, F2P, and P2P metrics from baseline or enhanced section."""
    sec = data.get(section, {})
    return {
        "num_issues": sec.get("num_issues", 0),
        "resolved_count": sec.get("resolved_issue_count", 0),
        "resolved_rate": sec.get("resolved_issue_rate", 0.0),
        "f2p_count": sec.get("fail_to_pass_issue_success_count", 0),
        "f2p_rate": sec.get("fail_to_pass_issue_success_rate", 0.0),
        "p2p_count": sec.get("pass_to_pass_issue_success_count", 0),
        "p2p_rate": sec.get("pass_to_pass_issue_success_rate", 0.0),
    }


def compute_delta(baseline: Dict, enhanced: Dict) -> Dict:
    """Compute delta metrics (enhanced - baseline)."""
    return {
        "resolved_delta": enhanced["resolved_rate"] - baseline["resolved_rate"],
        "f2p_delta": enhanced["f2p_rate"] - baseline["f2p_rate"],
        "p2p_delta": enhanced["p2p_rate"] - baseline["p2p_rate"],
    }


def print_group_summary(group_name: str, experiments: Dict[str, Dict]):
    """Print comprehensive summary table for a group."""
    print(f"\n{'='*100}")
    print(f"GROUP {group_name} - 101-ISSUE RESULTS")
    print(f"{'='*100}")

    for agent_name, data in sorted(experiments.items()):
        print(f"\n## {agent_name.upper()}")
        print("-" * 100)

        baseline = extract_metrics(data, "baseline")
        enhanced = extract_metrics(data, "enhanced")
        delta = compute_delta(baseline, enhanced)

        # Baseline table
        print(f"\n**Baseline (Unenhanced Solver)**")
        print(f"  Issues:    {baseline['num_issues']}")
        print(f"  Resolved:  {format_fraction(baseline['resolved_count'], baseline['num_issues'])}")
        print(f"  F2P:       {format_fraction(baseline['f2p_count'], baseline['num_issues'])}")
        print(f"  P2P:       {format_fraction(baseline['p2p_count'], baseline['num_issues'])}")

        # Enhanced table
        print(f"\n**Enhanced**")
        print(f"  Issues:    {enhanced['num_issues']}")
        print(f"  Resolved:  {format_fraction(enhanced['resolved_count'], enhanced['num_issues'])}")
        print(f"  F2P:       {format_fraction(enhanced['f2p_count'], enhanced['num_issues'])}")
        print(f"  P2P:       {format_fraction(enhanced['p2p_count'], enhanced['num_issues'])}")

        # Delta table
        print(f"\n**Delta (Enhanced - Baseline)**")
        print(f"  Resolved:  {delta['resolved_delta']:+.1%}")
        print(f"  F2P:       {delta['f2p_delta']:+.1%}")
        print(f"  P2P:       {delta['p2p_delta']:+.1%}")


def generate_comparison_table(group_a: Dict[str, Dict], group_b: Dict[str, Dict]):
    """Generate side-by-side comparison table."""
    print(f"\n{'='*120}")
    print("CROSS-GROUP COMPARISON - BASELINE RESOLVE RATES")
    print(f"{'='*120}")

    print(f"\n{'Agent':<20} | {'Group A (Verified)':<35} | {'Group B (Community)':<35} | {'Delta (A-B)':<15}")
    print("-" * 120)

    all_agents = sorted(set(group_a.keys()) | set(group_b.keys()))

    for agent in all_agents:
        a_data = group_a.get(agent, {})
        b_data = group_b.get(agent, {})

        a_baseline = extract_metrics(a_data, "baseline") if a_data else None
        b_baseline = extract_metrics(b_data, "baseline") if b_data else None

        a_str = format_fraction(a_baseline['resolved_count'], a_baseline['num_issues']) if a_baseline else "N/A"
        b_str = format_fraction(b_baseline['resolved_count'], b_baseline['num_issues']) if b_baseline else "N/A"

        if a_baseline and b_baseline:
            delta = a_baseline['resolved_rate'] - b_baseline['resolved_rate']
            delta_str = f"{delta:+.1%}"
        else:
            delta_str = "N/A"

        print(f"{agent:<20} | {a_str:<35} | {b_str:<35} | {delta_str:<15}")


def generate_markdown_table(group_name: str, experiments: Dict[str, Dict]) -> str:
    """Generate markdown table for documentation."""
    lines = [
        f"## Group {group_name} - 101-Issue Results\n",
        "| Agent | Baseline Resolved | Enhanced Resolved | Δ Resolved | Baseline F2P | Enhanced F2P | Δ F2P | Baseline P2P | Enhanced P2P | Δ P2P |",
        "|-------|-------------------|-------------------|------------|--------------|--------------|-------|--------------|--------------|-------|",
    ]

    for agent_name, data in sorted(experiments.items()):
        baseline = extract_metrics(data, "baseline")
        enhanced = extract_metrics(data, "enhanced")
        delta = compute_delta(baseline, enhanced)

        row = (
            f"| {agent_name} "
            f"| {format_fraction(baseline['resolved_count'], baseline['num_issues'])} "
            f"| {format_fraction(enhanced['resolved_count'], enhanced['num_issues'])} "
            f"| {delta['resolved_delta']:+.1%} "
            f"| {format_fraction(baseline['f2p_count'], baseline['num_issues'])} "
            f"| {format_fraction(enhanced['f2p_count'], enhanced['num_issues'])} "
            f"| {delta['f2p_delta']:+.1%} "
            f"| {format_fraction(baseline['p2p_count'], baseline['num_issues'])} "
            f"| {format_fraction(enhanced['p2p_count'], enhanced['num_issues'])} "
            f"| {delta['p2p_delta']:+.1%} |"
        )
        lines.append(row)

    return "\n".join(lines)


def main():
    """Main entry point."""
    print("="*100)
    print("101-ISSUE EXPERIMENT RESULTS ANALYSIS")
    print(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("="*100)

    # Define experiment directories
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

    # Load all experiment data
    group_a_data = {}
    group_b_data = {}

    print("\n## Loading experiment results...")
    print("-" * 100)

    for agent, path in experiments["Group A"].items():
        try:
            group_a_data[agent] = load_comparison_summary(path)
            print(f"✓ Loaded Group A - {agent}: {path.name}")
        except FileNotFoundError as e:
            print(f"⚠ Missing Group A - {agent}: {e}")

    for agent, path in experiments["Group B"].items():
        try:
            group_b_data[agent] = load_comparison_summary(path)
            print(f"✓ Loaded Group B - {agent}: {path.name}")
        except FileNotFoundError as e:
            print(f"⚠ Missing Group B - {agent}: {e}")

    # Generate reports
    if group_a_data:
        print_group_summary("A (SWE-bench Verified)", group_a_data)
    else:
        print("\n⚠ No Group A data available")

    if group_b_data:
        print_group_summary("B (Community)", group_b_data)
    else:
        print("\n⚠ No Group B data available")

    if group_a_data and group_b_data:
        generate_comparison_table(group_a_data, group_b_data)

    # Generate markdown tables for documentation
    print(f"\n\n{'='*100}")
    print("MARKDOWN TABLES FOR DOCUMENTATION")
    print(f"{'='*100}\n")

    if group_a_data:
        print(generate_markdown_table("A", group_a_data))
        print()

    if group_b_data:
        print(generate_markdown_table("B", group_b_data))

    # Save structured output
    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "group_a": {},
        "group_b": {},
    }

    for agent, data in group_a_data.items():
        output["group_a"][agent] = {
            "baseline": extract_metrics(data, "baseline"),
            "enhanced": extract_metrics(data, "enhanced"),
            "delta": compute_delta(
                extract_metrics(data, "baseline"),
                extract_metrics(data, "enhanced")
            ),
        }

    for agent, data in group_b_data.items():
        output["group_b"][agent] = {
            "baseline": extract_metrics(data, "baseline"),
            "enhanced": extract_metrics(data, "enhanced"),
            "delta": compute_delta(
                extract_metrics(data, "baseline"),
                extract_metrics(data, "enhanced")
            ),
        }

    output_file = results_root / "101_issue_aggregate_results.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Saved structured results to: {output_file}")
    print("\n" + "="*100)


if __name__ == "__main__":
    main()
