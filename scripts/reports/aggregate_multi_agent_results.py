"""
Aggregate multi-agent SWE-bench harness results into a unified JSON report.

Output schema:
- run_id
- summary
- patch_apply_matrix
- test_metrics
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SAMPLES = ROOT / "data" / "samples" / "swe_bench_live_10_samples.json"


def load_expected_instances(samples_path: Path) -> list[str]:
    with open(samples_path) as f:
        data = json.load(f)

    issues = data["issues"] if isinstance(data, dict) and "issues" in data else data
    ids = []
    for issue in issues:
        instance_id = issue.get("_swe_live_instance_id") or issue.get("issue_id")
        if instance_id:
            ids.append(instance_id)
    return ids


def load_summary_files(iteration_name: str) -> dict[str, dict]:
    summaries = {}
    for summary_file in sorted(ROOT.glob(f"*.{iteration_name}.json")):
        agent = summary_file.stem.replace(f".{iteration_name}", "")
        with open(summary_file) as f:
            summaries[agent] = json.load(f)
    return summaries


def load_report_instance(report_path: Path, instance_id: str) -> dict:
    with open(report_path) as f:
        report_data = json.load(f)

    if isinstance(report_data, dict) and instance_id in report_data:
        return report_data[instance_id]
    if isinstance(report_data, dict) and len(report_data) == 1:
        only_value = next(iter(report_data.values()))
        if isinstance(only_value, dict):
            return only_value
    return report_data if isinstance(report_data, dict) else {}


def get_patch_status(instance_dir: Path, instance_id: str) -> tuple[str, dict | None]:
    report_file = instance_dir / "report.json"
    patch_file = instance_dir / "patch.diff"

    if not instance_dir.exists():
        return "not_submitted", None

    if report_file.exists():
        report = load_report_instance(report_file, instance_id)
        if bool(report.get("patch_successfully_applied", False)):
            return "applied", report
        if bool(report.get("patch_exists", False)) or patch_file.exists():
            return "patch_fail", report
        return "not_submitted", report

    if patch_file.exists():
        return "patch_fail", None

    return "not_submitted", None


def get_test_counts(report: dict | None) -> dict | None:
    if not report:
        return None

    tests_status = report.get("tests_status")
    if not isinstance(tests_status, dict):
        return None

    f2p = tests_status.get("FAIL_TO_PASS", {})
    p2p = tests_status.get("PASS_TO_PASS", {})

    return {
        "f2p_success": len(f2p.get("success", [])),
        "f2p_failure": len(f2p.get("failure", [])),
        "p2p_success": len(p2p.get("success", [])),
        "p2p_failure": len(p2p.get("failure", [])),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iteration-name", type=str, required=True)
    parser.add_argument("--logs-dir", type=str, default=None)
    parser.add_argument("--samples", type=str, default=str(DEFAULT_SAMPLES))
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    logs_dir = Path(args.logs_dir) if args.logs_dir else ROOT / "logs" / "run_evaluation" / args.iteration_name
    if not logs_dir.exists():
        raise FileNotFoundError(f"Logs directory not found: {logs_dir}")

    summaries = load_summary_files(args.iteration_name)
    if not summaries:
        raise RuntimeError(
            f"No summary files found for iteration '{args.iteration_name}'. "
            f"Run scripts/reports/generate_summary_reports.py first."
        )

    expected_instances = load_expected_instances(Path(args.samples))
    instances = set(expected_instances)

    agents = sorted(summaries.keys())
    for agent in agents:
        agent_dir = logs_dir / agent
        if agent_dir.exists():
            for inst_dir in agent_dir.iterdir():
                if inst_dir.is_dir():
                    instances.add(inst_dir.name)

    instances = sorted(instances)

    patch_apply_matrix: dict[str, dict[str, str]] = {}
    test_metrics: dict[str, dict] = {}

    for instance in instances:
        patch_apply_matrix[instance] = {}
        for agent in agents:
            agent_instance_dir = logs_dir / agent / instance
            status, report = get_patch_status(agent_instance_dir, instance)
            patch_apply_matrix[instance][agent] = status

            counts = get_test_counts(report)
            if counts is not None:
                test_metrics[f"{agent}|{instance}"] = counts

    summary_out: dict[str, dict] = {}
    for agent in agents:
        s = summaries[agent]
        submitted = int(s.get("submitted_instances", 0))
        completed = int(s.get("completed_instances", 0))
        resolved = int(s.get("resolved_instances", 0))
        errors = int(s.get("error_instances", 0))

        patches_applied = sum(1 for inst in instances if patch_apply_matrix[inst].get(agent) == "applied")
        patch_apply_rate = f"{(patches_applied / submitted * 100):.0f}%" if submitted > 0 else "0%"

        summary_out[agent] = {
            "submitted": submitted,
            "completed": completed,
            "resolved": resolved,
            "errors": errors,
            "patches_applied": patches_applied,
            "patch_apply_rate": patch_apply_rate,
        }

    out = {
        "run_id": args.iteration_name,
        "summary": summary_out,
        "patch_apply_matrix": patch_apply_matrix,
        "test_metrics": test_metrics,
    }

    output_path = (
        Path(args.output)
        if args.output
        else ROOT / "eval_results" / "swebench" / f"{args.iteration_name}_aggregate_report.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"Saved aggregate report: {output_path}")
    print(f"Agents: {len(agents)}")
    print(f"Instances: {len(instances)}")
    print(f"Test metric entries: {len(test_metrics)}")


if __name__ == "__main__":
    main()
