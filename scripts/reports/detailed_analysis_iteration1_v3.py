"""
Generate detailed analysis of SWE-bench iteration1_v3 results.
This script provides comprehensive insights into test outcomes, patch quality, and agent performance.
"""
import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent.parent

# Load aggregate report
with open(ROOT / "eval_results/swebench/iteration1_v3_aggregate_report.json") as f:
    aggregate = json.load(f)

# Load summary reports for each agent
summary_reports = {}
for report_file in ROOT.glob("*.iteration1_v3.json"):
    agent_name = report_file.stem.replace(".iteration1_v3", "")
    with open(report_file) as f:
        summary_reports[agent_name] = json.load(f)

# Collect detailed metrics per instance
instance_details = defaultdict(dict)
for agent, report in summary_reports.items():
    for inst_id in report.get("completed_ids", []):
        instance_details[inst_id][agent] = "completed"
    for inst_id in report.get("unresolved_ids", []):
        instance_details[inst_id][agent] = "unresolved"
    for inst_id in report.get("error_ids", []):
        instance_details[inst_id][agent] = "error"

print("=" * 100)
print("DETAILED ANALYSIS: SWE-bench Iteration1_v3 Results")
print("=" * 100)

# 1. Executive Summary
print("\n## 1. EXECUTIVE SUMMARY")
print("-" * 100)
total_instances = 10
total_agents = len(aggregate["summary"])
total_submissions = sum(s["submitted"] for s in aggregate["summary"].values())
total_completed = sum(s["completed"] for s in aggregate["summary"].values())
total_resolved = sum(s["resolved"] for s in aggregate["summary"].values())
patches_applied = sum(s["patches_applied"] for s in aggregate["summary"].values())

print(f"Total Instances: {total_instances}")
print(f"Total Agents Tested: {total_agents}")
print(f"Total Submissions: {total_submissions}")
print(f"Total Completed Evaluations: {total_completed}")
print(f"Total Resolved (FAIL→PASS): {total_resolved}")
print(f"Patches Successfully Applied: {patches_applied}/{total_submissions} ({patches_applied/total_submissions*100:.1f}%)")
print(f"Overall Resolution Rate: {total_resolved}/{total_submissions} ({total_resolved/total_submissions*100:.1f}%)")

# 2. Per-Agent Performance Breakdown
print("\n## 2. PER-AGENT PERFORMANCE BREAKDOWN")
print("-" * 100)
print(f"{'Agent':<35} {'Submit':>6} {'Done':>6} {'Resolved':>8} {'Errors':>7} {'Apply%':>7} {'Resolve%':>9}")
print("-" * 100)

for agent, stats in sorted(aggregate["summary"].items()):
    submit = stats["submitted"]
    done = stats["completed"]
    resolved = stats["resolved"]
    errors = stats["errors"]
    apply_pct = stats["patch_apply_rate"]
    resolve_pct = f"{resolved/submit*100:.1f}%" if submit > 0 else "N/A"
    print(f"{agent:<35} {submit:>6} {done:>6} {resolved:>8} {errors:>7} {apply_pct:>7} {resolve_pct:>9}")

# 3. Test Outcome Analysis
print("\n## 3. TEST OUTCOME ANALYSIS (FAIL_TO_PASS & PASS_TO_PASS)")
print("-" * 100)
print(f"{'Agent | Instance':<70} {'F2P✓':>6} {'F2P✗':>6} {'P2P✓':>6} {'P2P✗':>6} {'Status':>10}")
print("-" * 100)

for key, metrics in sorted(aggregate["test_metrics"].items()):
    f2p_success = metrics["f2p_success"]
    f2p_failure = metrics["f2p_failure"]
    p2p_success = metrics["p2p_success"]
    p2p_failure = metrics["p2p_failure"]

    # Determine status
    if f2p_success > 0 and f2p_failure == 0:
        status = "✅ RESOLVED"
    elif f2p_success > 0:
        status = "⚠️ PARTIAL"
    else:
        status = "❌ FAILED"

    print(f"{key:<70} {f2p_success:>6} {f2p_failure:>6} {p2p_success:>6} {p2p_failure:>6} {status:>10}")

# 4. Patch Application Matrix
print("\n## 4. PATCH APPLICATION MATRIX")
print("-" * 100)
agents = sorted(aggregate["summary"].keys())
instances = sorted(aggregate["patch_apply_matrix"].keys())

# Header
header = f"{'Instance':<50}"
for agent in agents:
    short_name = agent.replace("enhanced_", "").replace("baseline_no_enhancement", "baseline")[:10]
    header += f" {short_name:>10}"
print(header)
print("-" * len(header))

# Rows
for instance in instances:
    row = f"{instance:<50}"
    for agent in agents:
        status = aggregate["patch_apply_matrix"][instance].get(agent, "---")
        if status == "applied":
            symbol = "✓"
        elif status == "patch_fail":
            symbol = "✗"
        elif status == "not_submitted":
            symbol = "—"
        else:
            symbol = "?"
        row += f" {symbol:>10}"
    print(row)

# 5. Resolution Analysis
print("\n## 5. RESOLUTION ANALYSIS")
print("-" * 100)

resolved_instances = defaultdict(list)
for key in aggregate["test_metrics"].keys():
    agent, instance = key.split("|")
    metrics = aggregate["test_metrics"][key]
    if metrics["f2p_success"] > 0 and metrics["f2p_failure"] == 0:
        resolved_instances[instance].append(agent)

print(f"Instances with at least one resolution: {len(resolved_instances)}/{total_instances}")
for instance, agents_list in sorted(resolved_instances.items()):
    print(f"  {instance}: resolved by {len(agents_list)} agent(s) - {', '.join(agents_list)}")

# 6. Comparison: Baseline vs Enhanced
print("\n## 6. BASELINE vs ENHANCED COMPARISON")
print("-" * 100)

baseline_stats = aggregate["summary"].get("baseline_no_enhancement", {})
enhanced_stats = {k: v for k, v in aggregate["summary"].items() if k != "baseline_no_enhancement"}

print(f"Baseline:")
print(f"  - Submitted: {baseline_stats.get('submitted', 0)}")
print(f"  - Completed: {baseline_stats.get('completed', 0)}")
print(f"  - Resolved: {baseline_stats.get('resolved', 0)}")
print(f"  - Patch Apply Rate: {baseline_stats.get('patch_apply_rate', 'N/A')}")

print(f"\nEnhanced Agents (average):")
if enhanced_stats:
    avg_submit = sum(s["submitted"] for s in enhanced_stats.values()) / len(enhanced_stats)
    avg_complete = sum(s["completed"] for s in enhanced_stats.values()) / len(enhanced_stats)
    avg_resolved = sum(s["resolved"] for s in enhanced_stats.values()) / len(enhanced_stats)
    avg_apply_rate = sum(s["patches_applied"] for s in enhanced_stats.values()) / sum(s["submitted"] for s in enhanced_stats.values()) * 100

    print(f"  - Avg Submitted: {avg_submit:.1f}")
    print(f"  - Avg Completed: {avg_complete:.1f}")
    print(f"  - Avg Resolved: {avg_resolved:.1f}")
    print(f"  - Avg Patch Apply Rate: {avg_apply_rate:.1f}%")

# 7. Failure Analysis
print("\n## 7. FAILURE ANALYSIS")
print("-" * 100)

print(f"Instances with NO successful patches applied:")
no_apply_instances = []
for instance, matrix in aggregate["patch_apply_matrix"].items():
    if all(status != "applied" for status in matrix.values()):
        no_apply_instances.append(instance)
        reasons = set(matrix.values())
        print(f"  - {instance}: {reasons}")

print(f"\nTotal instances with zero patches applied: {len(no_apply_instances)}/{total_instances}")

print(f"\nInstances with patches applied but NO resolution:")
partial_instances = []
for instance, matrix in aggregate["patch_apply_matrix"].items():
    if any(status == "applied" for status in matrix.values()):
        if instance not in resolved_instances:
            partial_instances.append(instance)
            print(f"  - {instance}")

print(f"\nTotal: {len(partial_instances)}/{total_instances} had patches applied but couldn't resolve the issue")

# 8. Key Insights
print("\n## 8. KEY INSIGHTS")
print("-" * 100)

# Best performing agent
best_agent = max(enhanced_stats.items(), key=lambda x: x[1]["completed"])
print(f"1. Best Performing Agent (by completions): {best_agent[0]} ({best_agent[1]['completed']} completed)")

# Patch quality
print(f"\n2. Patch Quality:")
print(f"   - Only {total_resolved} instance fully resolved out of {total_submissions} submissions ({total_resolved/total_submissions*100:.1f}%)")
print(f"   - {patches_applied} patches applied successfully ({patches_applied/total_submissions*100:.1f}%)")
print(f"   - {patches_applied - total_completed} patches applied but tests didn't run or errored")

# Most challenging instances
print(f"\n3. Most Challenging Instances:")
for inst in no_apply_instances:
    print(f"   - {inst}: NO agent could apply a patch")

# Success stories
print(f"\n4. Success Story:")
if resolved_instances:
    for inst, agents_list in resolved_instances.items():
        print(f"   - {inst}: resolved by {agents_list}")
else:
    print(f"   - None yet on most instances")

print("\n" + "=" * 100)
print("END OF DETAILED ANALYSIS")
print("=" * 100)
