#!/usr/bin/env python3
"""Orchestrate verified100 expansion from existing verified10 seed artifacts.

Pipeline:
1) Wait for baseline new-90 solver predictions.
2) Merge old-10 + new-90 predictions into a full-100 baseline prediction file.
3) Run SWE-bench evaluation on all 100 issues.
4) Write baseline `summary.json` and `metrics_breakdown.json` in replication100 dir.
5) Run 13 enhancer-agent experiments on 100 issues in a separate results root.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

AGENTS = [
    "openhands",
    "swe_agent",
    "github_copilot",
    "sweep",
    "aider",
    "cline",
    "magis",
    "copilot_workspace",
    "chatbr",
    "coderabbit",
    "mini_swe_agent",
    "live_swe_agent",
    "trae",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def log(*parts: object) -> None:
    print(f"[{utc_now()}]", *parts, flush=True)


def normalize_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value]
    if isinstance(value, str):
        v = value.strip()
        if not v:
            return []
        if v.startswith("[") and v.endswith("]"):
            try:
                parsed = ast.literal_eval(v)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except Exception:
                return [v]
        return [v]
    return []


def read_ids(path: Path) -> list[str]:
    return [x.strip() for x in path.read_text().splitlines() if x.strip()]


def load_jsonl_rows_by_id(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        rows[obj["instance_id"]] = obj
    return rows


def save_status(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def parse_args() -> argparse.Namespace:
    root = Path("/home/22pf2/BenchmarkLLMAgent")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=root)
    parser.add_argument(
        "--python", type=Path, default=Path("/home/22pf2/SWE-Bench_Replication/.venv312/bin/python")
    )
    parser.add_argument("--rep10", type=Path, default=Path("/home/22pf2/SWE-Bench_Replication"))
    parser.add_argument("--rep100", type=Path, default=Path("/home/22pf2/SWE-Bench_Replication_100"))
    parser.add_argument(
        "--results-root",
        type=Path,
        default=Path("/home/22pf2/BenchmarkLLMAgent/results/verified100_baseline_vs_enhanced"),
    )
    parser.add_argument("--output-tag", type=str, default="all13_full100_defaultdevstral_20260320")
    parser.add_argument("--run-id-baseline", type=str, default="devstral2512_verified100_eval")
    parser.add_argument("--enhancer-parallel", type=int, default=4)
    parser.add_argument("--solver-workers", type=int, default=4)
    parser.add_argument("--eval-workers", type=int, default=4)
    parser.add_argument("--cuda-visible-devices", type=str, default="1,2,3,4,5,6,7")
    parser.add_argument("--api-base", type=str, default="http://127.0.0.1:18000/v1")
    parser.add_argument("--api-key", type=str, default="local-devstral")
    parser.add_argument("--model", type=str, default="Devstral-Small-2-24B-Instruct-2512")
    parser.add_argument("--max-enhanced-body-chars", type=int, default=3000)
    parser.add_argument("--allow-identical-enhancements", action="store_true", default=True)
    parser.add_argument("--poll-seconds", type=int, default=60)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_verified = args.root / "scripts" / "workflows" / "run_verified10_enhancement_vs_baseline.py"

    ids100 = read_ids(args.rep100 / "selected_instances.txt")
    if len(ids100) != 100:
        raise ValueError(f"Expected 100 selected IDs, got {len(ids100)}")

    # 1) Wait for complete new-90 baseline solver output
    new90_preds = args.rep100 / "runs" / "full_100_new90" / "preds.json"
    expected_new90 = len(ids100) - 10
    log("Waiting for baseline new-90 preds:", new90_preds, "expected entries:", expected_new90)
    while True:
        if not (new90_preds.exists() and new90_preds.stat().st_size > 0):
            time.sleep(max(args.poll_seconds, 5))
            continue
        try:
            new_map_probe = json.loads(new90_preds.read_text())
            if isinstance(new_map_probe, dict) and len(new_map_probe) >= expected_new90:
                break
        except Exception:
            pass
        time.sleep(max(args.poll_seconds, 5))
    log("Detected complete baseline new-90 preds file.")

    # 2) Merge old-10 + new-90 into full-100 preds
    old10_preds = args.rep10 / "runs" / "full_10" / "preds.json"
    full100_dir = args.rep100 / "runs" / "full_100"
    full100_dir.mkdir(parents=True, exist_ok=True)
    full100_preds = full100_dir / "preds.json"
    old_map = json.loads(old10_preds.read_text())
    new_map = json.loads(new90_preds.read_text())
    merged = dict(old_map)
    merged.update(new_map)
    full100_preds.write_text(json.dumps(merged, indent=2))
    log("Merged prediction count:", len(merged), "->", full100_preds)

    # 3) Evaluate on all 100
    eval_cmd = [
        str(args.python),
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        "SWE-bench/SWE-bench_Verified",
        "--split",
        "test",
        "--predictions_path",
        str(full100_preds),
        "--instance_ids",
        *ids100,
        "--max_workers",
        str(args.eval_workers),
        "--timeout",
        "1800",
        "--run_id",
        args.run_id_baseline,
        "--report_dir",
        str(args.rep100 / "eval_reports"),
    ]
    log("Running baseline-100 evaluation...")
    eval_rc = subprocess.run(eval_cmd, cwd=str(args.rep100), env=os.environ.copy()).returncode
    log("Baseline evaluation return code:", eval_rc)

    # 4) Build baseline metrics files for workflow slicing logic
    rows_by_id = load_jsonl_rows_by_id(
        args.root / "data" / "samples" / "swe_bench_verified_100_dataset_original.jsonl"
    )
    run_eval_dir = args.root / "logs" / "run_evaluation" / args.run_id_baseline
    model_dirs = [p for p in run_eval_dir.iterdir() if p.is_dir()] if run_eval_dir.exists() else []
    model_dir = model_dirs[0] if model_dirs else None
    log("Run eval dir:", run_eval_dir)
    log("Model dir:", model_dir)

    resolved_count = 0
    f2p_issue_success_count = 0
    p2p_issue_success_count = 0
    f2p_tests_passed = 0
    f2p_tests_total = 0
    p2p_tests_passed = 0
    p2p_tests_total = 0
    resolved_ids: list[str] = []
    per_instance: list[dict] = []
    eval_failure_ids: list[str] = []

    for iid in ids100:
        row = rows_by_id[iid]
        expected_f2p = normalize_list(row.get("FAIL_TO_PASS", []))
        expected_p2p = normalize_list(row.get("PASS_TO_PASS", []))

        report_path = (model_dir / iid / "report.json") if model_dir else None
        if not report_path or not report_path.exists():
            eval_failure_ids.append(iid)
            f2p_tests_total += len(expected_f2p)
            p2p_tests_total += len(expected_p2p)
            per_instance.append(
                {
                    "instance_id": iid,
                    "resolved": False,
                    "fail_to_pass_issue_success": False,
                    "pass_to_pass_issue_success": False,
                    "fail_to_pass_passed": 0,
                    "fail_to_pass_total": len(expected_f2p),
                    "pass_to_pass_passed": 0,
                    "pass_to_pass_total": len(expected_p2p),
                    "evaluation_report_missing": True,
                }
            )
            continue

        report_obj = json.loads(report_path.read_text()).get(iid, {})
        tests = report_obj.get("tests_status", {})
        f2p = tests.get("FAIL_TO_PASS", {})
        p2p = tests.get("PASS_TO_PASS", {})
        f2p_success = normalize_list(f2p.get("success", []))
        f2p_failure = normalize_list(f2p.get("failure", []))
        p2p_success = normalize_list(p2p.get("success", []))
        p2p_failure = normalize_list(p2p.get("failure", []))

        resolved = bool(report_obj.get("resolved", False))
        f2p_issue_success = len(f2p_failure) == 0 and len(f2p_success) == len(expected_f2p)
        p2p_issue_success = len(p2p_failure) == 0 and len(p2p_success) == len(expected_p2p)

        if resolved:
            resolved_count += 1
            resolved_ids.append(iid)
        if f2p_issue_success:
            f2p_issue_success_count += 1
        if p2p_issue_success:
            p2p_issue_success_count += 1

        f2p_tests_passed += len(f2p_success)
        f2p_tests_total += len(expected_f2p)
        p2p_tests_passed += len(p2p_success)
        p2p_tests_total += len(expected_p2p)

        per_instance.append(
            {
                "instance_id": iid,
                "resolved": resolved,
                "fail_to_pass_issue_success": f2p_issue_success,
                "pass_to_pass_issue_success": p2p_issue_success,
                "fail_to_pass_passed": len(f2p_success),
                "fail_to_pass_total": len(expected_f2p),
                "pass_to_pass_passed": len(p2p_success),
                "pass_to_pass_total": len(expected_p2p),
            }
        )

    n = len(ids100)
    metrics = {
        "dataset_source": "SWE-bench/SWE-bench_Verified",
        "subset": "verified",
        "split": "test",
        "selected_issue_ids": ids100,
        "resolved_issue_count": resolved_count,
        "resolved_issue_rate": (resolved_count / n) if n else 0.0,
        "fail_to_pass_issue_success_count": f2p_issue_success_count,
        "fail_to_pass_issue_success_rate": (f2p_issue_success_count / n) if n else 0.0,
        "pass_to_pass_issue_success_count": p2p_issue_success_count,
        "pass_to_pass_issue_success_rate": (p2p_issue_success_count / n) if n else 0.0,
        "fail_to_pass_tests_passed": f2p_tests_passed,
        "fail_to_pass_tests_total": f2p_tests_total,
        "fail_to_pass_test_pass_rate": (f2p_tests_passed / f2p_tests_total) if f2p_tests_total else 0.0,
        "pass_to_pass_tests_passed": p2p_tests_passed,
        "pass_to_pass_tests_total": p2p_tests_total,
        "pass_to_pass_test_pass_rate": (p2p_tests_passed / p2p_tests_total) if p2p_tests_total else 0.0,
        "per_instance": per_instance,
    }
    (args.rep100 / "metrics_breakdown.json").write_text(json.dumps(metrics, indent=2))

    summary = {
        "target_agent": "mini-SWE-agent",
        "target_model": "mistralai/Devstral-Small-2-24B-Instruct-2512",
        "dataset": "SWE-bench",
        "subset": "verified",
        "split": "test",
        "num_issues": n,
        "selected_issue_ids": ids100,
        "exact_model_available": True,
        "exact_scaffold_version_pinned": False,
        "recorded_scaffold_version": "mini-SWE-agent 2.2.7",
        "recorded_scaffold_commit": "a9b635ab0f79b52e9354e676f5a90a534d4c6afa",
        "run_completed": True,
        "attempted_count": n - len(eval_failure_ids),
        "resolved_count": resolved_count,
        "resolved_rate": (resolved_count / n) if n else 0.0,
        "fail_to_pass_issue_success_count": f2p_issue_success_count,
        "fail_to_pass_issue_success_rate": (f2p_issue_success_count / n) if n else 0.0,
        "pass_to_pass_issue_success_count": p2p_issue_success_count,
        "pass_to_pass_issue_success_rate": (p2p_issue_success_count / n) if n else 0.0,
        "fail_to_pass_tests_passed": f2p_tests_passed,
        "fail_to_pass_tests_total": f2p_tests_total,
        "fail_to_pass_test_pass_rate": (f2p_tests_passed / f2p_tests_total) if f2p_tests_total else 0.0,
        "pass_to_pass_tests_passed": p2p_tests_passed,
        "pass_to_pass_tests_total": p2p_tests_total,
        "pass_to_pass_test_pass_rate": (p2p_tests_passed / p2p_tests_total) if p2p_tests_total else 0.0,
        "resolved_ids": resolved_ids,
        "unresolved_count": n - resolved_count,
        "infrastructure_failures": 0,
        "model_provider_failures": 0,
        "evaluation_failures": len(eval_failure_ids),
        "notes": [
            "Built from existing 10-issue baseline artifacts plus 90 new Verified issues.",
            "Selected IDs strategy: old 10 first, then first 90 remaining in dataset order.",
        ],
    }
    (args.rep100 / "summary.json").write_text(json.dumps(summary, indent=2))
    log("Wrote baseline metrics and summary for 100 issues.")

    # 5) Run full 13-agent 100-issue batch
    status = {"tag": args.output_tag, "started_at_utc": utc_now(), "runs": {}}
    status_path = args.results_root / f"batch_status_{args.output_tag}.json"
    args.results_root.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["CUDA_VISIBLE_DEVICES"] = args.cuda_visible_devices
    env["OPENAI_COMPAT_API_BASE"] = args.api_base
    env["OPENAI_COMPAT_API_KEY"] = args.api_key
    env["OPENAI_COMPAT_MODEL"] = args.model

    for agent in AGENTS:
        exp_dir = args.results_root / f"{agent}__{args.output_tag}"
        comp = exp_dir / "comparison_summary.json"
        if comp.exists():
            status["runs"][agent] = {
                "state": "completed",
                "returncode": 0,
                "comparison_summary_exists": True,
                "comparison_summary": str(comp),
                "experiment_dir": str(exp_dir),
                "updated_at_utc": utc_now(),
                "resume_skip_reason": "already_completed",
            }
            save_status(status_path, status)
            continue

        cmd = [
            str(args.python),
            str(run_verified),
            "--enhancer-agent",
            agent,
            "--max-issues",
            "100",
            "--output-tag",
            args.output_tag,
            "--results-root",
            str(args.results_root),
            "--replication-dir",
            str(args.rep100),
            "--replication-selected-ids",
            str(args.rep100 / "selected_instances.txt"),
            "--samples-json",
            str(args.root / "data" / "samples" / "swe_bench_verified_100_samples.json"),
            "--selected-ids-file",
            str(args.root / "data" / "samples" / "swe_bench_verified_100_instance_ids.txt"),
            "--enhancer-parallel",
            str(args.enhancer_parallel),
            "--solver-workers",
            str(args.solver_workers),
            "--eval-workers",
            str(args.eval_workers),
            "--max-enhanced-body-chars",
            str(args.max_enhanced_body_chars),
        ]
        if args.allow_identical_enhancements:
            cmd.append("--allow-identical-enhancements")

        status["runs"][agent] = {
            "state": "running",
            "command": cmd,
            "experiment_dir": str(exp_dir),
            "updated_at_utc": utc_now(),
        }
        save_status(status_path, status)
        log("Starting agent:", agent)
        rc = subprocess.run(cmd, cwd=str(args.root), env=env).returncode
        comp_exists = comp.exists()
        status["runs"][agent] = {
            "state": "completed" if rc == 0 and comp_exists else "failed",
            "returncode": rc,
            "comparison_summary_exists": comp_exists,
            "comparison_summary": str(comp) if comp_exists else "",
            "experiment_dir": str(exp_dir),
            "updated_at_utc": utc_now(),
        }
        save_status(status_path, status)
        log("Finished agent:", agent, "rc=", rc, "comparison=", comp_exists)

    status["finished_at_utc"] = utc_now()
    save_status(status_path, status)
    log("Verified100 pipeline complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
