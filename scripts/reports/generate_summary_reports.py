"""
Generate per-agent summary JSON files from SWE-bench harness logs.

Output files are written to the project root as:
  <agent>.<iteration_name>.json
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SAMPLES = ROOT / "data" / "samples" / "swe_bench_live_10_samples.json"


def load_expected_instance_ids(samples_path: Path) -> list[str]:
    with open(samples_path) as f:
        data = json.load(f)

    issues = data["issues"] if isinstance(data, dict) and "issues" in data else data
    expected = []
    for issue in issues:
        instance_id = issue.get("_swe_live_instance_id") or issue.get("issue_id")
        if instance_id:
            expected.append(instance_id)
    return expected


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


def summarize_agent(agent_dir: Path, expected_ids: set[str]) -> dict:
    instance_dirs = sorted([d for d in agent_dir.iterdir() if d.is_dir()])

    submitted_ids = []
    completed_ids = []
    resolved_ids = []
    empty_patch_ids = []

    for inst_dir in instance_dirs:
        instance_id = inst_dir.name
        patch_file = inst_dir / "patch.diff"
        report_file = inst_dir / "report.json"

        has_submission_artifact = patch_file.exists() or report_file.exists() or (inst_dir / "run_instance.log").exists()
        if has_submission_artifact:
            submitted_ids.append(instance_id)

        if patch_file.exists() and patch_file.stat().st_size == 0:
            empty_patch_ids.append(instance_id)

        if report_file.exists():
            completed_ids.append(instance_id)
            report = load_report_instance(report_file, instance_id)
            if bool(report.get("resolved", False)):
                resolved_ids.append(instance_id)

    submitted_set = set(submitted_ids)
    completed_set = set(completed_ids)
    resolved_set = set(resolved_ids)

    unresolved_ids = sorted(completed_set - resolved_set)
    error_ids = sorted(submitted_set - completed_set)

    if expected_ids:
        incomplete_ids = sorted(expected_ids - submitted_set)
        total_instances = len(expected_ids)
    else:
        incomplete_ids = []
        total_instances = len(submitted_set)

    return {
        "total_instances": total_instances,
        "submitted_instances": len(submitted_set),
        "completed_instances": len(completed_set),
        "resolved_instances": len(resolved_set),
        "unresolved_instances": len(unresolved_ids),
        "empty_patch_instances": len(set(empty_patch_ids)),
        "error_instances": len(error_ids),
        "completed_ids": sorted(completed_set),
        "incomplete_ids": incomplete_ids,
        "empty_patch_ids": sorted(set(empty_patch_ids)),
        "submitted_ids": sorted(submitted_set),
        "resolved_ids": sorted(resolved_set),
        "unresolved_ids": unresolved_ids,
        "error_ids": error_ids,
        "schema_version": 2,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iteration-name", type=str, required=True)
    parser.add_argument("--logs-dir", type=str, default=None)
    parser.add_argument("--samples", type=str, default=str(DEFAULT_SAMPLES))
    args = parser.parse_args()

    logs_dir = Path(args.logs_dir) if args.logs_dir else ROOT / "logs" / "run_evaluation" / args.iteration_name
    if not logs_dir.exists():
        raise FileNotFoundError(f"Logs directory not found: {logs_dir}")

    expected_ids = set(load_expected_instance_ids(Path(args.samples))) if args.samples else set()

    agent_dirs = sorted([d for d in logs_dir.iterdir() if d.is_dir()])
    if not agent_dirs:
        raise RuntimeError(f"No agent directories found in {logs_dir}")

    for agent_dir in agent_dirs:
        agent_name = agent_dir.name
        summary = summarize_agent(agent_dir, expected_ids)

        out_file = ROOT / f"{agent_name}.{args.iteration_name}.json"
        with open(out_file, "w") as f:
            json.dump(summary, f, indent=2)

        print(
            f"{agent_name}: submitted={summary['submitted_instances']} "
            f"completed={summary['completed_instances']} resolved={summary['resolved_instances']} "
            f"errors={summary['error_instances']} -> {out_file}"
        )


if __name__ == "__main__":
    main()
