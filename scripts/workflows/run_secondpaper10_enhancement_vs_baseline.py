#!/usr/bin/env python3
"""Run second-paper-10 enhancement experiment: baseline + enhanced solving + evaluation.

This script runs the full enhancement comparison pipeline for Group B
(10 second-paper issues with F2P/P2P). It:
1. Runs a baseline solver (no enhancement) on the original issues
2. Evaluates baseline with SWE-bench harness
3. For each enhancer agent:
   a. Enhances the issue descriptions
   b. Builds an enhanced JSONL dataset
   c. Runs the solver on enhanced issues
   d. Evaluates with SWE-bench harness
4. Compares baseline vs enhanced metrics
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import re
import shlex
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


def _detect_repo_root() -> Path:
    script_path = Path(__file__).resolve()
    direct_root = script_path.parent.parent.parent
    if (direct_root / "scripts").exists() and (direct_root / "src").exists():
        return direct_root
    parent_root = direct_root.parent
    if (parent_root / "scripts").exists() and (parent_root / "src").exists():
        return parent_root
    raise RuntimeError(f"Could not detect repository root from {script_path}.")


ROOT = _detect_repo_root()
DATA_DIR = ROOT / "data" / "samples" / "second_paper_final_10_f2p_p2p"
DEFAULT_DATASET_JSONL = DATA_DIR / "final_10_instances_with_f2p_p2p.jsonl"
DEFAULT_SAMPLES_JSON = DATA_DIR / "secondpaper10_samples.json"
DEFAULT_SELECTED_IDS = DATA_DIR / "secondpaper10_instance_ids.txt"
DEFAULT_REPLICATION_DIR = Path("/home/22pf2/SWE-Bench_Replication")
# Use bench_env for both solver and eval — it has live spec support + mini-SWE-agent
DEFAULT_SWEBENCH_PYTHON = ROOT / "bench_env" / "bin" / "python"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        try:
            return json.loads(value)
        except Exception:
            try:
                return ast.literal_eval(value)
            except Exception:
                return [value]
    return []


def _normalize_text(value: str) -> str:
    return " ".join((value or "").lower().split())


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_cmd(
    title: str,
    cmd: list[str],
    cwd: Path,
    log_dir: Path,
    env: dict | None = None,
    check: bool = True,
) -> tuple[Path, Path]:
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{title.replace(' ', '_').lower()}.stdout.log"
    stderr_path = log_dir / f"{title.replace(' ', '_').lower()}.stderr.log"
    print(f"  [{_utc_now()}] Running: {title}")
    with stdout_path.open("w") as out, stderr_path.open("w") as err:
        proc = subprocess.run(cmd, cwd=cwd, env=env, stdout=out, stderr=err, check=False)
    if check and proc.returncode != 0:
        # Print last 20 lines of stderr for debugging
        stderr_lines = stderr_path.read_text().splitlines()[-20:]
        print(f"  ERROR: {title} failed with exit code {proc.returncode}")
        for line in stderr_lines:
            print(f"    {line}")
        raise RuntimeError(
            f"{title} failed with exit code {proc.returncode}. "
            f"See {stdout_path} and {stderr_path}."
        )
    print(f"  [{_utc_now()}] Finished: {title} (exit={proc.returncode})")
    return stdout_path, stderr_path


def _load_ids(ids_path: Path) -> list[str]:
    ids = [line.strip() for line in ids_path.read_text().splitlines() if line.strip()]
    if not ids:
        raise ValueError(f"No instance IDs found in {ids_path}")
    return ids


def _build_filter_regex(instance_ids: list[str]) -> str:
    if not instance_ids:
        return "^$"
    escaped = [re.escape(i) for i in instance_ids]
    return "^(" + "|".join(escaped) + ")$"


def _safe_load_yaml(path: Path) -> dict:
    try:
        import yaml
        data = yaml.safe_load(path.read_text()) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _expected_model_dir_name_from_override(path: Path) -> str | None:
    config = _safe_load_yaml(path)
    model_name = (
        config.get("model", {}).get("model_name")
        if isinstance(config.get("model"), dict)
        else None
    )
    if not model_name or not isinstance(model_name, str):
        return None
    return model_name.replace("/", "__")


def _latest_exit_status_file(output_dir: Path) -> Path | None:
    files = list(output_dir.glob("exit_statuses_*.yaml"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _load_exit_status_by_instance(exit_status_path: Path | None) -> dict[str, str]:
    if not exit_status_path or not exit_status_path.exists():
        return {}
    payload = _safe_load_yaml(exit_status_path)
    by_status = payload.get("instances_by_exit_status")
    if not isinstance(by_status, dict):
        return {}
    out: dict[str, str] = {}
    for status, ids in by_status.items():
        if not isinstance(ids, list):
            continue
        for iid in ids:
            if isinstance(iid, str):
                out[iid] = str(status)
    return out


def _parse_harness_summary_from_log(log_path: Path | None) -> dict:
    if not log_path or not log_path.exists():
        return {}
    patterns = {
        "total_instances": r"^Total instances:\s+(\d+)$",
        "instances_submitted": r"^Instances submitted:\s+(\d+)$",
        "instances_completed": r"^Instances completed:\s+(\d+)$",
        "instances_incomplete": r"^Instances incomplete:\s+(\d+)$",
        "instances_resolved": r"^Instances resolved:\s+(\d+)$",
        "instances_unresolved": r"^Instances unresolved:\s+(\d+)$",
        "instances_with_empty_patches": r"^Instances with empty patches:\s+(\d+)$",
        "instances_with_errors": r"^Instances with errors:\s+(\d+)$",
    }
    result: dict[str, int] = {}
    for line in log_path.read_text().splitlines():
        text = line.strip()
        for key, pattern in patterns.items():
            m = re.match(pattern, text)
            if m:
                result[key] = int(m.group(1))
    return result


def _compute_metrics_from_reports(
    *,
    run_id: str,
    instance_ids: list[str],
    dataset_rows_by_id: dict[str, dict],
    expected_model_dir_name: str | None,
    harness_summary: dict,
    solver_status_by_instance: dict[str, str],
) -> dict:
    run_eval_dir = ROOT / "logs" / "run_evaluation" / run_id
    if not run_eval_dir.exists():
        return _compute_metrics_without_reports(
            instance_ids=instance_ids,
            dataset_rows_by_id=dataset_rows_by_id,
            harness_summary=harness_summary,
            solver_status_by_instance=solver_status_by_instance,
            reason=f"Evaluation log directory not found: {run_eval_dir}",
        )

    model_dirs = sorted([p for p in run_eval_dir.iterdir() if p.is_dir()], key=lambda p: p.name)
    if not model_dirs:
        return _compute_metrics_without_reports(
            instance_ids=instance_ids,
            dataset_rows_by_id=dataset_rows_by_id,
            harness_summary=harness_summary,
            solver_status_by_instance=solver_status_by_instance,
            reason="No model output directories found.",
        )

    # Select model dir
    model_dir = model_dirs[0]
    if expected_model_dir_name:
        for p in model_dirs:
            if p.name == expected_model_dir_name:
                model_dir = p
                break

    if len(model_dirs) > 1 and not expected_model_dir_name:
        scored = []
        for path in model_dirs:
            coverage = sum(1 for iid in instance_ids if (path / iid / "report.json").exists())
            scored.append((coverage, path.name, path))
        scored.sort(reverse=True)
        model_dir = scored[0][2]

    resolved_issue_count = 0
    f2p_issue_success_count = 0
    p2p_issue_success_count = 0
    f2p_tests_passed = 0
    f2p_tests_total = 0
    p2p_tests_passed = 0
    p2p_tests_total = 0
    attempted_issue_count = 0
    evaluation_failure_ids = []
    per_instance = []
    resolved_ids = []

    for iid in instance_ids:
        report_path = model_dir / iid / "report.json"
        expected_f2p = _normalize_list(dataset_rows_by_id[iid].get("FAIL_TO_PASS", []))
        expected_p2p = _normalize_list(dataset_rows_by_id[iid].get("PASS_TO_PASS", []))

        if not report_path.exists():
            evaluation_failure_ids.append(iid)
            f2p_tests_total += len(expected_f2p)
            p2p_tests_total += len(expected_p2p)
            per_instance.append({
                "instance_id": iid,
                "resolved": False,
                "fail_to_pass_issue_success": False,
                "pass_to_pass_issue_success": False,
                "fail_to_pass_passed": 0,
                "fail_to_pass_total": len(expected_f2p),
                "pass_to_pass_passed": 0,
                "pass_to_pass_total": len(expected_p2p),
                "evaluation_error": "report_not_found",
            })
            continue

        report = json.loads(report_path.read_text())
        attempted_issue_count += 1

        # SWE-bench report structure: {instance_id: {resolved, tests_status, ...}}
        # tests_status format: {FAIL_TO_PASS: {success: [...], failure: [...]}, ...}
        inst_report = report.get(iid, {})
        resolved_from_report = inst_report.get("resolved", False)
        f2p_status = inst_report.get("tests_status", {}).get("FAIL_TO_PASS", {})
        p2p_status = inst_report.get("tests_status", {}).get("PASS_TO_PASS", {})

        # Handle both formats: {success: [...], failure: [...]} and {test: "PASSED"}
        if "success" in f2p_status or "failure" in f2p_status:
            f2p_passed = len(f2p_status.get("success", []))
            f2p_failed = len(f2p_status.get("failure", []))
            f2p_total_from_report = f2p_passed + f2p_failed
        else:
            f2p_passed = sum(1 for v in f2p_status.values() if v == "PASSED")
            f2p_total_from_report = len(f2p_status)

        if "success" in p2p_status or "failure" in p2p_status:
            p2p_passed = len(p2p_status.get("success", []))
            p2p_failed = len(p2p_status.get("failure", []))
            p2p_total_from_report = p2p_passed + p2p_failed
        else:
            p2p_passed = sum(1 for v in p2p_status.values() if v == "PASSED")
            p2p_total_from_report = len(p2p_status)

        f2p_total = max(len(expected_f2p), f2p_total_from_report)
        p2p_total = max(len(expected_p2p), p2p_total_from_report)

        f2p_all_pass = f2p_passed == f2p_total and f2p_total > 0
        p2p_all_pass = p2p_passed == p2p_total
        resolved = resolved_from_report or (f2p_all_pass and p2p_all_pass)

        if resolved:
            resolved_issue_count += 1
            resolved_ids.append(iid)
        if f2p_all_pass:
            f2p_issue_success_count += 1
        if p2p_all_pass:
            p2p_issue_success_count += 1

        f2p_tests_passed += f2p_passed
        f2p_tests_total += f2p_total
        p2p_tests_passed += p2p_passed
        p2p_tests_total += p2p_total

        per_instance.append({
            "instance_id": iid,
            "resolved": resolved,
            "fail_to_pass_issue_success": f2p_all_pass,
            "pass_to_pass_issue_success": p2p_all_pass,
            "fail_to_pass_passed": f2p_passed,
            "fail_to_pass_total": f2p_total,
            "pass_to_pass_passed": p2p_passed,
            "pass_to_pass_total": p2p_total,
        })

    n = len(instance_ids)
    return {
        "num_issues": n,
        "attempted_issue_count": attempted_issue_count,
        "resolved_issue_count": resolved_issue_count,
        "resolved_issue_rate": (resolved_issue_count / n) if n else 0.0,
        "resolved_issue_rate_attempted": (resolved_issue_count / attempted_issue_count) if attempted_issue_count else 0.0,
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
        "evaluation_failure_count": len(evaluation_failure_ids),
        "evaluation_failure_ids": evaluation_failure_ids,
        "resolved_ids": resolved_ids,
        "per_instance": per_instance,
    }


def _compute_metrics_without_reports(
    *,
    instance_ids: list[str],
    dataset_rows_by_id: dict[str, dict],
    harness_summary: dict,
    solver_status_by_instance: dict[str, str],
    reason: str,
) -> dict:
    n = len(instance_ids)
    per_instance = []
    for iid in instance_ids:
        expected_f2p = _normalize_list(dataset_rows_by_id[iid].get("FAIL_TO_PASS", []))
        expected_p2p = _normalize_list(dataset_rows_by_id[iid].get("PASS_TO_PASS", []))
        per_instance.append({
            "instance_id": iid,
            "resolved": False,
            "fail_to_pass_issue_success": False,
            "pass_to_pass_issue_success": False,
            "fail_to_pass_passed": 0,
            "fail_to_pass_total": len(expected_f2p),
            "pass_to_pass_passed": 0,
            "pass_to_pass_total": len(expected_p2p),
            "evaluation_error": reason,
        })
    return {
        "num_issues": n,
        "attempted_issue_count": 0,
        "resolved_issue_count": 0,
        "resolved_issue_rate": 0.0,
        "resolved_issue_rate_attempted": 0.0,
        "fail_to_pass_issue_success_count": 0,
        "fail_to_pass_issue_success_rate": 0.0,
        "pass_to_pass_issue_success_count": 0,
        "pass_to_pass_issue_success_rate": 0.0,
        "fail_to_pass_tests_passed": 0,
        "fail_to_pass_tests_total": sum(len(_normalize_list(dataset_rows_by_id[iid].get("FAIL_TO_PASS", []))) for iid in instance_ids),
        "fail_to_pass_test_pass_rate": 0.0,
        "pass_to_pass_tests_passed": 0,
        "pass_to_pass_tests_total": sum(len(_normalize_list(dataset_rows_by_id[iid].get("PASS_TO_PASS", []))) for iid in instance_ids),
        "pass_to_pass_test_pass_rate": 0.0,
        "evaluation_failure_count": n,
        "evaluation_failure_ids": list(instance_ids),
        "resolved_ids": [],
        "per_instance": per_instance,
        "reason": reason,
    }


def _validate_enhancement_payload(
    *,
    original_title: str,
    original_body: str,
    enhanced_title: Any,
    enhanced_body: Any,
    max_body_chars: int,
    max_similarity: float,
    allow_identical: bool,
) -> dict:
    if not isinstance(enhanced_title, str):
        raise ValueError("enhanced_title must be a string")
    if not isinstance(enhanced_body, str):
        raise ValueError("enhanced_body must be a string")
    if len(enhanced_body) > max_body_chars:
        raise ValueError(f"enhanced_body length {len(enhanced_body)} exceeds max {max_body_chars}")

    title_similarity = SequenceMatcher(
        None, _normalize_text(original_title), _normalize_text(enhanced_title)
    ).ratio()
    body_similarity = SequenceMatcher(
        None, _normalize_text(original_body), _normalize_text(enhanced_body)
    ).ratio()
    near_identical = title_similarity >= max_similarity and body_similarity >= max_similarity
    if near_identical and not allow_identical:
        raise ValueError(
            f"enhancement rejected by quality gate (title_similarity={title_similarity:.3f}, "
            f"body_similarity={body_similarity:.3f})"
        )
    return {
        "title_similarity": title_similarity,
        "body_similarity": body_similarity,
        "near_identical": near_identical,
    }


def _build_enhanced_dataset_jsonl(
    *,
    instance_ids: list[str],
    dataset_rows_by_id: dict[str, dict],
    enhancement_dir: Path,
    enhancer_agent: str,
    samples_json: Path,
    output_jsonl: Path,
    max_body_chars: int,
    max_similarity: float,
    allow_identical: bool,
    require_native: bool,
) -> tuple[dict[str, dict], dict]:
    """Build enhanced dataset JSONL from local data (not HuggingFace)."""
    with samples_json.open() as f:
        sample_payload = json.load(f)
    sample_issues = sample_payload["issues"]
    sample_by_id = {issue["instance_id"]: issue for issue in sample_issues}

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)

    selected_rows: dict[str, dict] = {}
    quality_rows: list[dict] = []
    with output_jsonl.open("w") as f:
        for iid in instance_ids:
            if iid not in dataset_rows_by_id:
                raise ValueError(f"Instance {iid} not found in dataset")
            if iid not in sample_by_id:
                raise ValueError(f"Instance {iid} not found in samples JSON")

            sample = sample_by_id[iid]
            owner = sample["pr_owner"]
            repo = sample["pr_repo"]
            issue_number = sample["issue_number"]
            enh_file = enhancement_dir / f"{enhancer_agent}__{owner}__{repo}__{issue_number}.json"
            if not enh_file.exists():
                raise FileNotFoundError(f"Missing enhancement result for {iid}: {enh_file}")

            enh = json.loads(enh_file.read_text())
            metadata = enh.get("enhancement_metadata", {})
            enhancer_type = metadata.get("enhancer_type") if isinstance(metadata, dict) else None
            if require_native and enhancer_type != "real":
                raise ValueError(
                    f"native enhancer required, but {iid} has enhancer_type={enhancer_type!r} "
                    f"in {enh_file}"
                )
            enhanced_title = enh.get("enhanced_title", "")
            enhanced_body = enh.get("enhanced_body", "")
            quality = _validate_enhancement_payload(
                original_title=sample.get("title", "") or "",
                original_body=sample.get("body", "") or "",
                enhanced_title=enhanced_title,
                enhanced_body=enhanced_body,
                max_body_chars=max_body_chars,
                max_similarity=max_similarity,
                allow_identical=allow_identical,
            )
            # Track enhancement status for diagnostics
            quality["enhancer_type"] = enhancer_type
            quality["enhancement_noop"] = metadata.get("enhancement_noop", False) if isinstance(metadata, dict) else False
            quality["placeholder_detected"] = any(
                a.get("placeholder_detected", False)
                for a in (metadata.get("attempts", []) if isinstance(metadata, dict) else [])
            )
            quality_rows.append({"instance_id": iid, **quality})

            enhanced_problem_statement = f"{enhanced_title.strip()}\n\n{enhanced_body.strip()}".strip()
            row = dict(dataset_rows_by_id[iid])
            row["problem_statement"] = enhanced_problem_statement
            row["enhancement_agent"] = enhancer_agent
            row["enhancement_quality"] = quality

            f.write(json.dumps(row) + "\n")
            selected_rows[iid] = row

    near_identical_count = sum(1 for x in quality_rows if x["near_identical"])
    noop_count = sum(1 for x in quality_rows if x.get("enhancement_noop"))
    placeholder_count = sum(1 for x in quality_rows if x.get("placeholder_detected"))
    real_enhancement_count = sum(
        1 for x in quality_rows
        if not x.get("near_identical") and not x.get("enhancement_noop") and not x.get("placeholder_detected")
    )
    quality_summary = {
        "num_issues": len(quality_rows),
        "near_identical_count": near_identical_count,
        "near_identical_rate": (near_identical_count / len(quality_rows)) if quality_rows else 0.0,
        "noop_count": noop_count,
        "placeholder_count": placeholder_count,
        "real_enhancement_count": real_enhancement_count,
        "avg_title_similarity": (
            sum(x["title_similarity"] for x in quality_rows) / len(quality_rows) if quality_rows else 0.0
        ),
        "avg_body_similarity": (
            sum(x["body_similarity"] for x in quality_rows) / len(quality_rows) if quality_rows else 0.0
        ),
        "per_instance": quality_rows,
    }
    return selected_rows, quality_summary


def _comparison_markdown(comparison: dict) -> str:
    baseline = comparison["baseline"]
    enhanced = comparison.get("enhanced")
    lines = [
        "# Second-Paper-10 Baseline vs Enhanced Comparison",
        "",
        f"Generated at: {comparison['generated_at_utc']}",
        f"Enhancer agent: `{comparison['enhancer_agent']}`",
        "",
        "## Baseline (Unenhanced Solver)",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Issues | {baseline['num_issues']} |",
        f"| Resolved | {baseline['resolved_issue_count']}/{baseline['num_issues']} ({baseline['resolved_issue_rate']*100:.1f}%) |",
        f"| F2P issue success | {baseline['fail_to_pass_issue_success_count']}/{baseline['num_issues']} ({baseline['fail_to_pass_issue_success_rate']*100:.1f}%) |",
        f"| P2P issue success | {baseline['pass_to_pass_issue_success_count']}/{baseline['num_issues']} ({baseline['pass_to_pass_issue_success_rate']*100:.1f}%) |",
        "",
    ]
    if enhanced:
        delta = comparison.get("delta", {})
        lines += [
            "## Enhanced",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Issues | {enhanced['num_issues']} |",
            f"| Resolved | {enhanced['resolved_issue_count']}/{enhanced['num_issues']} ({enhanced['resolved_issue_rate']*100:.1f}%) |",
            f"| F2P issue success | {enhanced['fail_to_pass_issue_success_count']}/{enhanced['num_issues']} ({enhanced['fail_to_pass_issue_success_rate']*100:.1f}%) |",
            f"| P2P issue success | {enhanced['pass_to_pass_issue_success_count']}/{enhanced['num_issues']} ({enhanced['pass_to_pass_issue_success_rate']*100:.1f}%) |",
            "",
            "## Delta (Enhanced - Baseline)",
            "",
        ]
        if delta:
            lines += [
                f"| Metric | Delta |",
                f"|--------|-------|",
                f"| Resolved rate | {delta['resolved_issue_rate_delta']*100:+.1f}% |",
                f"| F2P issue success rate | {delta['fail_to_pass_issue_success_rate_delta']*100:+.1f}% |",
                f"| P2P issue success rate | {delta['pass_to_pass_issue_success_rate_delta']*100:+.1f}% |",
                "",
            ]
    else:
        lines += ["## Enhanced", "", "Enhanced metrics unavailable.", ""]

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run second-paper-10 enhancement vs baseline experiment")
    parser.add_argument("--enhancer-agent", type=str, required=True, help="Enhancer agent to use")
    parser.add_argument("--max-issues", type=int, default=10)
    parser.add_argument("--output-tag", type=str, default="latest")
    parser.add_argument("--dataset-jsonl", type=Path, default=DEFAULT_DATASET_JSONL)
    parser.add_argument("--samples-json", type=Path, default=DEFAULT_SAMPLES_JSON)
    parser.add_argument("--selected-ids-file", type=Path, default=DEFAULT_SELECTED_IDS)
    parser.add_argument(
        "--results-root", type=Path,
        default=ROOT / "results" / "secondpaper10_baseline_vs_enhanced",
    )
    parser.add_argument("--skip-baseline", action="store_true")
    parser.add_argument("--skip-enhancement", action="store_true")
    parser.add_argument("--skip-solver", action="store_true")
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--enhancer-api-base", type=str, default="http://127.0.0.1:18000/v1")
    parser.add_argument("--enhancer-api-key", type=str, default="local-devstral")
    parser.add_argument("--enhancer-model", type=str, default="Devstral-Small-2-24B-Instruct-2512")
    parser.add_argument("--enhancer-parallel", type=int, default=1)
    parser.add_argument(
        "--disable-enhancement-cache",
        action="store_true",
        help="Recompute enhancements instead of reusing cached enhancer outputs.",
    )
    parser.add_argument("--solver-workers", type=int, default=1)
    parser.add_argument("--eval-workers", type=int, default=1)
    parser.add_argument("--eval-timeout", type=int, default=1800)
    parser.add_argument("--namespace", type=str, default="none",
                        help='Docker image namespace for swebench harness (default: "none"). '
                             'Use "starryzhang" for SWE-bench-Live instances.')
    parser.add_argument("--max-enhanced-body-chars", type=int, default=20000)
    parser.add_argument("--max-enhancement-similarity", type=float, default=0.995)
    parser.add_argument("--allow-identical-enhancements", action="store_true")
    parser.add_argument("--require-native-enhancer", action="store_true")
    parser.add_argument(
        "--swebench-python", type=Path,
        default=DEFAULT_SWEBENCH_PYTHON,
    )
    parser.add_argument(
        "--mini-benchmark-config", type=Path,
        default=DEFAULT_REPLICATION_DIR / "mini-SWE-agent" / "src" / "minisweagent" / "config" / "benchmarks" / "swebench_backticks.yaml",
    )
    parser.add_argument(
        "--mini-model-override-config", type=Path,
        default=DEFAULT_REPLICATION_DIR / "config" / "devstral_vllm_override.yaml",
    )
    parser.add_argument(
        "--mini-model-class", type=str,
        default="minisweagent.models.litellm_textbased_model.LitellmTextbasedModel",
    )
    args = parser.parse_args()

    # ── Load dataset ──
    instances = []
    with args.dataset_jsonl.open() as f:
        for line in f:
            line = line.strip()
            if line:
                instances.append(json.loads(line))
    rows_by_id = {inst["instance_id"]: inst for inst in instances}

    instance_ids = _load_ids(args.selected_ids_file)[: args.max_issues]
    for iid in instance_ids:
        if iid not in rows_by_id:
            raise ValueError(f"Instance {iid} not found in dataset JSONL")

    expected_model_dir_name = _expected_model_dir_name_from_override(args.mini_model_override_config)

    experiment_dir = args.results_root / f"{args.enhancer_agent}__{args.output_tag}"
    log_dir = experiment_dir / "logs"
    enhancement_dir = experiment_dir / "enhancements"
    baseline_solver_dir = experiment_dir / "baseline_solver_run"
    enhanced_solver_dir = experiment_dir / "enhanced_solver_run"
    enhanced_dataset_jsonl = experiment_dir / f"secondpaper10_enhanced_{args.enhancer_agent}.jsonl"
    comparison_json = experiment_dir / "comparison_summary.json"
    comparison_md = experiment_dir / "comparison_summary.md"

    experiment_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    run_id_baseline = f"secondpaper10_baseline_{args.output_tag}".replace("-", "_")
    run_id_enhanced = f"secondpaper10_{args.enhancer_agent}_{args.output_tag}".replace("-", "_")

    filter_regex = _build_filter_regex(instance_ids)

    print(f"\n{'='*60}")
    print(f"Second-Paper-10 Enhancement Experiment")
    print(f"Enhancer: {args.enhancer_agent}")
    print(f"Instances: {len(instance_ids)}")
    print(f"Output: {experiment_dir}")
    print(f"{'='*60}\n")

    # ── Step 1: Baseline solver (unenhanced) ──
    baseline_preds_json = baseline_solver_dir / "preds.json"
    if not args.skip_baseline:
        print("\n── Step 1: Running baseline solver (no enhancement) ──")
        baseline_solver_cmd = [
            str(args.swebench_python),
            str(ROOT / "scripts" / "solvers" / "run_mini_sweagent_jsonl.py"),
            "--dataset-jsonl", str(args.dataset_jsonl),
            "--filter", filter_regex,
            "--workers", str(args.solver_workers),
            "--redo-existing",
            "--output", str(baseline_solver_dir),
            "--model-class", args.mini_model_class,
            "-c", str(args.mini_benchmark_config),
            "-c", str(args.mini_model_override_config),
        ]
        _run_cmd("baseline_solver", baseline_solver_cmd, ROOT, log_dir)
    else:
        print("\n── Step 1: Skipping baseline solver ──")

    # ── Step 2: Evaluate baseline ──
    baseline_eval_stdout: Path | None = None
    baseline_eval_executed = False
    if not args.skip_eval and baseline_preds_json.exists():
        print("\n── Step 2: Evaluating baseline solver ──")
        baseline_eval_cmd = [
            str(args.swebench_python),
            "-m", "swebench.harness.run_evaluation",
            "--dataset_name", str(args.dataset_jsonl),
            "--predictions_path", str(baseline_preds_json),
            "--instance_ids", *instance_ids,
            "--max_workers", str(args.eval_workers),
            "--timeout", str(args.eval_timeout),
            "--run_id", run_id_baseline,
            "--namespace", args.namespace,
        ]
        baseline_eval_stdout, _ = _run_cmd("baseline_evaluation", baseline_eval_cmd, ROOT, log_dir)
        baseline_eval_executed = True
    else:
        print("\n── Step 2: Skipping baseline evaluation ──")
        # Reuse previous logs only in explicit skip-eval mode.
        if args.skip_eval:
            candidate = log_dir / "baseline_evaluation.stdout.log"
            if candidate.exists():
                baseline_eval_stdout = candidate

    baseline_harness_summary = _parse_harness_summary_from_log(baseline_eval_stdout)

    # Compute baseline metrics
    baseline_solver_status = _load_exit_status_by_instance(_latest_exit_status_file(baseline_solver_dir))
    if baseline_eval_executed or args.skip_eval:
        baseline_metrics = _compute_metrics_from_reports(
            run_id=run_id_baseline,
            instance_ids=instance_ids,
            dataset_rows_by_id=rows_by_id,
            expected_model_dir_name=expected_model_dir_name,
            harness_summary=baseline_harness_summary,
            solver_status_by_instance=baseline_solver_status,
        )
    else:
        baseline_metrics = _compute_metrics_without_reports(
            instance_ids=instance_ids,
            dataset_rows_by_id=rows_by_id,
            harness_summary=baseline_harness_summary,
            solver_status_by_instance=baseline_solver_status,
            reason=(
                "Baseline evaluation did not run in this invocation "
                "(predictions missing or step skipped implicitly)."
            ),
        )
    print(f"\n  Baseline: {baseline_metrics['resolved_issue_count']}/{baseline_metrics['num_issues']} resolved "
          f"({baseline_metrics['resolved_issue_rate']*100:.1f}%)")

    # ── Step 3: Enhancement ──
    if not args.skip_enhancement:
        print(f"\n── Step 3: Running enhancement with {args.enhancer_agent} ──")
        enhance_env = dict(os.environ)
        enhance_env["OPENAI_COMPAT_BASE_URL"] = args.enhancer_api_base
        enhance_env["OPENAI_COMPAT_API_KEY"] = args.enhancer_api_key
        enhance_env["OPENAI_COMPAT_MODEL"] = args.enhancer_model
        # Ensure native TRAE enhancer uses the same OpenAI-compatible endpoint/model.
        enhance_env["TRAE_PROVIDER"] = "openai"
        enhance_env["TRAE_BASE_URL"] = args.enhancer_api_base
        enhance_env["TRAE_API_KEY"] = args.enhancer_api_key
        enhance_env["TRAE_MODEL"] = args.enhancer_model
        # Ensure native Aider enhancer uses the same OpenAI-compatible endpoint/model.
        enhance_env["AIDER_MODEL"] = f"openai/{args.enhancer_model}"
        enhance_env["AIDER_API_BASE"] = args.enhancer_api_base
        enhance_env["AIDER_API_KEY"] = args.enhancer_api_key
        enhance_env["OPENAI_API_KEY"] = args.enhancer_api_key
        enhance_env["OPENAI_API_BASE"] = args.enhancer_api_base
        # Ensure native SWE-agent enhancer uses the same OpenAI-compatible endpoint/model.
        enhance_env["SWEAGENT_BASE_URL"] = args.enhancer_api_base
        enhance_env["SWEAGENT_API_KEY"] = args.enhancer_api_key
        enhance_env["SWEAGENT_MODEL"] = args.enhancer_model
        # Ensure code-context enhancer can find the dataset JSONL.
        enhance_env["CODE_CONTEXT_DATASET_JSONL"] = str(args.dataset_jsonl)
        enhance_cmd = [
            sys.executable,
            str(ROOT / "scripts" / "enhancers" / "run_enhancement_benchmark.py"),
            "--agents", args.enhancer_agent,
            "--max-issues", str(len(instance_ids)),
            "--parallel", str(args.enhancer_parallel),
            "--samples", str(args.samples_json),
            "--output-dir", str(enhancement_dir),
        ]
        if args.disable_enhancement_cache:
            enhance_cmd.append("--disable-cache")
        _run_cmd("run_enhancement", enhance_cmd, ROOT, log_dir, env=enhance_env)
    else:
        print(f"\n── Step 3: Skipping enhancement ──")

    # ── Step 4: Build enhanced dataset JSONL ──
    print(f"\n── Step 4: Building enhanced dataset JSONL ──")
    enhanced_dataset_ready = False
    enhancement_build_error: str | None = None
    try:
        enhanced_rows, enhancement_quality = _build_enhanced_dataset_jsonl(
            instance_ids=instance_ids,
            dataset_rows_by_id=rows_by_id,
            enhancement_dir=enhancement_dir,
            enhancer_agent=args.enhancer_agent,
            samples_json=args.samples_json,
            output_jsonl=enhanced_dataset_jsonl,
            max_body_chars=args.max_enhanced_body_chars,
            max_similarity=args.max_enhancement_similarity,
            allow_identical=args.allow_identical_enhancements,
            require_native=args.require_native_enhancer,
        )
        enhanced_dataset_ready = True
    except (FileNotFoundError, ValueError) as e:
        print(f"  WARNING: Could not build enhanced dataset: {e}")
        enhancement_build_error = str(e)
        # Prevent stale enhanced datasets from previous runs from being reused.
        if enhanced_dataset_jsonl.exists():
            enhanced_dataset_jsonl.unlink()
        enhanced_rows = {}
        enhancement_quality = {"error": str(e)}

    # ── Step 5: Enhanced solver ──
    enhanced_preds_json = enhanced_solver_dir / "preds.json"
    enhanced_solver_executed = False
    if not args.skip_solver and enhanced_dataset_ready and enhanced_dataset_jsonl.exists():
        print(f"\n── Step 5: Running enhanced solver ──")
        enhanced_solver_cmd = [
            str(args.swebench_python),
            str(ROOT / "scripts" / "solvers" / "run_mini_sweagent_jsonl.py"),
            "--dataset-jsonl", str(enhanced_dataset_jsonl),
            "--filter", filter_regex,
            "--workers", str(args.solver_workers),
            "--redo-existing",
            "--output", str(enhanced_solver_dir),
            "--model-class", args.mini_model_class,
            "-c", str(args.mini_benchmark_config),
            "-c", str(args.mini_model_override_config),
        ]
        _run_cmd("enhanced_solver", enhanced_solver_cmd, ROOT, log_dir)
        enhanced_solver_executed = True
    else:
        print(f"\n── Step 5: Skipping enhanced solver ──")

    # ── Step 6: Evaluate enhanced solver ──
    enhanced_eval_stdout: Path | None = None
    enhanced_eval_executed = False
    can_evaluate_enhanced = enhanced_dataset_ready and enhanced_preds_json.exists()
    if not args.skip_eval and can_evaluate_enhanced:
        print(f"\n── Step 6: Evaluating enhanced solver ──")
        # Use the original JSONL (with correct patches/tests) for evaluation,
        # but the enhanced predictions
        enhanced_eval_cmd = [
            str(args.swebench_python),
            "-m", "swebench.harness.run_evaluation",
            "--dataset_name", str(args.dataset_jsonl),
            "--predictions_path", str(enhanced_preds_json),
            "--instance_ids", *instance_ids,
            "--max_workers", str(args.eval_workers),
            "--timeout", str(args.eval_timeout),
            "--run_id", run_id_enhanced,
            "--namespace", args.namespace,
        ]
        enhanced_eval_stdout, _ = _run_cmd("enhanced_evaluation", enhanced_eval_cmd, ROOT, log_dir)
        enhanced_eval_executed = True
    else:
        print(f"\n── Step 6: Skipping enhanced evaluation ──")
        # Reuse previous logs only in explicit skip-eval mode and when we have
        # a valid enhanced dataset/predictions context.
        if args.skip_eval and can_evaluate_enhanced:
            candidate = log_dir / "enhanced_evaluation.stdout.log"
            if candidate.exists():
                enhanced_eval_stdout = candidate

    enhanced_harness_summary = _parse_harness_summary_from_log(enhanced_eval_stdout)
    if enhanced_solver_executed or args.skip_solver:
        enhanced_solver_status = _load_exit_status_by_instance(_latest_exit_status_file(enhanced_solver_dir))
    else:
        enhanced_solver_status = {}

    enhanced_dataset_for_metrics = enhanced_rows if enhanced_rows else rows_by_id
    if not enhanced_dataset_ready:
        enhanced_metrics = _compute_metrics_without_reports(
            instance_ids=instance_ids,
            dataset_rows_by_id=enhanced_dataset_for_metrics,
            harness_summary=enhanced_harness_summary,
            solver_status_by_instance=enhanced_solver_status,
            reason=(
                "Enhanced dataset could not be built in this invocation: "
                f"{enhancement_build_error or 'unknown error'}"
            ),
        )
    elif not args.skip_eval and not enhanced_eval_executed:
        enhanced_metrics = _compute_metrics_without_reports(
            instance_ids=instance_ids,
            dataset_rows_by_id=enhanced_dataset_for_metrics,
            harness_summary=enhanced_harness_summary,
            solver_status_by_instance=enhanced_solver_status,
            reason=(
                "Enhanced evaluation did not run in this invocation "
                "(missing predictions or prior step skipped)."
            ),
        )
    else:
        enhanced_metrics = _compute_metrics_from_reports(
            run_id=run_id_enhanced,
            instance_ids=instance_ids,
            dataset_rows_by_id=enhanced_dataset_for_metrics,
            expected_model_dir_name=expected_model_dir_name,
            harness_summary=enhanced_harness_summary,
            solver_status_by_instance=enhanced_solver_status,
        )
    print(f"\n  Enhanced: {enhanced_metrics['resolved_issue_count']}/{enhanced_metrics['num_issues']} resolved "
          f"({enhanced_metrics['resolved_issue_rate']*100:.1f}%)")

    # ── Step 7: Comparison ──
    print(f"\n── Step 7: Computing comparison ──")
    comparison: dict[str, Any] = {
        "generated_at_utc": _utc_now(),
        "enhancer_agent": args.enhancer_agent,
        "instance_ids": instance_ids,
        "dataset_jsonl": str(args.dataset_jsonl),
        "group": "B_secondpaper10",
        "baseline": baseline_metrics,
        "enhanced": enhanced_metrics,
        "enhancement_quality": enhancement_quality if isinstance(enhancement_quality, dict) else {},
        "baseline_harness_summary": baseline_harness_summary,
        "enhanced_harness_summary": enhanced_harness_summary,
        "notes": [],
    }
    if enhancement_build_error:
        comparison["notes"].append(
            "Enhanced dataset build failed; enhanced metrics shown without report-based evaluation."
        )
    comparison["delta"] = {
        "resolved_issue_rate_delta": enhanced_metrics["resolved_issue_rate"] - baseline_metrics["resolved_issue_rate"],
        "fail_to_pass_issue_success_rate_delta": enhanced_metrics["fail_to_pass_issue_success_rate"] - baseline_metrics["fail_to_pass_issue_success_rate"],
        "pass_to_pass_issue_success_rate_delta": enhanced_metrics["pass_to_pass_issue_success_rate"] - baseline_metrics["pass_to_pass_issue_success_rate"],
    }

    comparison_json.write_text(json.dumps(comparison, indent=2))
    comparison_md.write_text(_comparison_markdown(comparison))

    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"Baseline:  {baseline_metrics['resolved_issue_count']}/{baseline_metrics['num_issues']} resolved ({baseline_metrics['resolved_issue_rate']*100:.1f}%)")
    print(f"Enhanced:  {enhanced_metrics['resolved_issue_count']}/{enhanced_metrics['num_issues']} resolved ({enhanced_metrics['resolved_issue_rate']*100:.1f}%)")
    delta = comparison["delta"]
    print(f"Delta:     {delta['resolved_issue_rate_delta']*100:+.1f}% resolved")
    print(f"           {delta['fail_to_pass_issue_success_rate_delta']*100:+.1f}% F2P success")
    print(f"           {delta['pass_to_pass_issue_success_rate_delta']*100:+.1f}% P2P success")
    print(f"\nComparison: {comparison_json}")
    print(f"Markdown:   {comparison_md}")


if __name__ == "__main__":
    main()
