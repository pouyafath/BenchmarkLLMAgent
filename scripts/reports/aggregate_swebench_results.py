"""
Aggregate SWE-bench harness results into a paper-ready report.

Reads report.json files from the harness output and produces:
1. Per-agent resolution rate table
2. Baseline vs. enhanced comparison
3. Per-issue resolution matrix
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def load_harness_reports(run_id: str) -> dict:
    """Load all report.json files from harness output."""
    base = ROOT / "logs" / "run_evaluation" / run_id
    results = {}

    if not base.exists():
        print(f"ERROR: Run directory not found: {base}")
        sys.exit(1)

    for model_dir in sorted(base.iterdir()):
        if not model_dir.is_dir():
            continue
        model_name = model_dir.name
        for instance_dir in sorted(model_dir.iterdir()):
            if not instance_dir.is_dir():
                continue
            instance_id = instance_dir.name
            report_file = instance_dir / "report.json"
            if report_file.exists():
                with open(report_file) as f:
                    report = json.load(f)
                results[(model_name, instance_id)] = report
    return results


def load_summary_reports(run_id: str) -> dict:
    """Load the top-level summary JSON reports per model."""
    reports = {}
    for f in ROOT.glob(f"*.{run_id}.json"):
        model_name = f.stem.replace(f".{run_id}", "")
        with open(f) as fp:
            reports[model_name] = json.load(fp)
    return reports


def main():
    run_id = sys.argv[1] if len(sys.argv) > 1 else "iteration1_full"

    # Load summary reports
    summaries = load_summary_reports(run_id)
    if not summaries:
        print(f"No summary reports found for run_id={run_id}")
        print("Looking for files matching: *.{run_id}.json")
        sys.exit(1)

    # Collect per-model metrics
    print("=" * 80)
    print(f"SWE-bench Harness Results — Run: {run_id}")
    print("=" * 80)

    # Table: Per-agent resolution rate
    print("\n## Per-Agent Resolution Rate\n")
    print(f"{'Agent':<35} {'Submitted':>10} {'Completed':>10} {'Resolved':>10} {'Rate':>8}")
    print("-" * 80)

    all_resolved = {}
    all_unresolved = {}
    for model, report in sorted(summaries.items()):
        submitted = report.get("submitted_instances", 0)
        completed = report.get("completed_instances", 0)
        resolved = report.get("resolved_instances", 0)
        rate = f"{resolved/submitted*100:.1f}%" if submitted > 0 else "N/A"
        print(f"{model:<35} {submitted:>10} {completed:>10} {resolved:>10} {rate:>8}")
        all_resolved[model] = set(report.get("resolved_ids", []))
        all_unresolved[model] = set(report.get("unresolved_ids", []))

    # Baseline vs. enhanced comparison
    baseline_key = "baseline_no_enhancement"
    enhanced_models = [m for m in summaries if m != baseline_key]

    if baseline_key in summaries:
        print("\n\n## Baseline vs. Enhanced Comparison\n")
        baseline_resolved = all_resolved.get(baseline_key, set())
        baseline_total = summaries[baseline_key].get("submitted_instances", 0)
        baseline_rate = len(baseline_resolved) / baseline_total * 100 if baseline_total > 0 else 0

        print(f"{'Agent':<35} {'Resolved':>10} {'Rate':>8} {'Delta':>8}")
        print("-" * 65)
        print(f"{baseline_key:<35} {len(baseline_resolved):>10} {baseline_rate:>7.1f}%")

        for model in sorted(enhanced_models):
            resolved = all_resolved.get(model, set())
            total = summaries[model].get("submitted_instances", 0)
            rate = len(resolved) / total * 100 if total > 0 else 0
            delta = rate - baseline_rate
            print(f"{model:<35} {len(resolved):>10} {rate:>7.1f}% {delta:>+7.1f}%")

    # Per-issue resolution matrix
    all_instances = set()
    for report in summaries.values():
        all_instances.update(report.get("resolved_ids", []))
        all_instances.update(report.get("unresolved_ids", []))
    all_instances = sorted(all_instances)

    if all_instances:
        print("\n\n## Per-Issue Resolution Matrix\n")
        models = sorted(summaries.keys())
        # Header
        header = f"{'Instance ID':<50}"
        for m in models:
            short = m.replace("enhanced_", "").replace("baseline_no_enhancement", "baseline")[:12]
            header += f" {short:>12}"
        print(header)
        print("-" * len(header))

        for inst in all_instances:
            row = f"{inst:<50}"
            for m in models:
                if inst in all_resolved.get(m, set()):
                    row += f" {'PASS':>12}"
                elif inst in all_unresolved.get(m, set()):
                    row += f" {'FAIL':>12}"
                else:
                    row += f" {'---':>12}"
            print(row)

    # Detailed per-instance reports (from report.json)
    detailed = load_harness_reports(run_id)
    if detailed:
        print("\n\n## Detailed Test Results (from report.json)\n")
        for (model, instance), report in sorted(detailed.items()):
            resolved = report.get("resolved", False)
            f2p = report.get(f"FAIL_TO_PASS", {})
            p2p = report.get(f"PASS_TO_PASS", {})
            status = "RESOLVED" if resolved else "UNRESOLVED"
            print(f"  {model}/{instance}: {status}")
            if f2p:
                f2p_pass = sum(1 for v in f2p.values() if v == "PASSED")
                f2p_total = len(f2p)
                print(f"    FAIL_TO_PASS: {f2p_pass}/{f2p_total}")
            if p2p:
                p2p_pass = sum(1 for v in p2p.values() if v == "PASSED")
                p2p_total = len(p2p)
                print(f"    PASS_TO_PASS: {p2p_pass}/{p2p_total}")

    # Save structured output
    output_file = ROOT / "eval_results" / "swebench" / f"{run_id}_aggregate_report.json"
    output = {
        "run_id": run_id,
        "per_model": {
            model: {
                "submitted": report.get("submitted_instances", 0),
                "completed": report.get("completed_instances", 0),
                "resolved": report.get("resolved_instances", 0),
                "resolved_ids": report.get("resolved_ids", []),
                "unresolved_ids": report.get("unresolved_ids", []),
                "error_ids": report.get("error_ids", []),
            }
            for model, report in summaries.items()
        },
    }
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n\nStructured report saved to: {output_file}")


if __name__ == "__main__":
    main()
