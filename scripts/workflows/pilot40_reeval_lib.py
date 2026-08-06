#!/usr/bin/env python3
"""
Shared P2P-gated re-evaluation logic for pilot40-style runs.

This module provides reusable functions for re-evaluating Stage 5 results
with corrected test name matching and P2P-gated resolution criteria.

The SWE-bench-Live evaluator has two issues for pilot40-type datasets:
  1. Test name mismatch: parsed names may have /testbed/ prefix or
     parameterized suffixes [param] that don't match the dataset's
     PASS_TO_PASS / FAIL_TO_PASS lists.
  2. Resolution gate: the evaluator requires FAIL_TO_PASS success > 0,
     but pilot40 datasets use PASS_TO_PASS > 0 as the gate
     (FAIL_TO_PASS is metadata only per the handoff doc).

This script reads existing status.json files (no re-running of tests),
applies corrected matching, and overwrites report.json + eval_results.json.

Usage as standalone:
    cd /home/22pf2/BenchmarkLLMAgent
    bench_env/bin/python scripts/workflows/pilot40_reeval_lib.py \\
        --run-dir runs/paul_pilot40_openhands_20260601

Usage as library:
    from scripts.workflows.pilot40_reeval_lib import reeval_run
    results = reeval_run(run_dir, conditions=["baseline", "enhanced"])
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file into a list of dicts."""
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def normalize_test_name(name: str) -> str:
    """Strip /testbed/ prefix from parsed test names."""
    if name.startswith("/testbed/"):
        return name[len("/testbed/"):]
    return name


def match_tests(
    parsed: set[tuple[str, str]], expected_names: set[str]
) -> tuple[set[str], set[str]]:
    """Match parsed test names against expected, handling normalization.

    Handles two mismatches:
      - /testbed/ prefix in parsed names
      - Parameterized test suffixes: test_foo[param] matches test_foo
        (all parameterized variants must pass for the base to count as passing)

    Args:
        parsed: set of (test_name, status) tuples where status is "pass"/"fail"
        expected_names: set of expected test names from the dataset

    Returns:
        (matched_pass, matched_fail) from the expected_names perspective.
    """
    # Build normalized lookup
    norm_map: dict[str, str] = {}
    for name, status in parsed:
        norm = normalize_test_name(name)
        norm_map[norm] = status

    matched_pass: set[str] = set()
    matched_fail: set[str] = set()

    for expected in expected_names:
        # Try exact match first
        if expected in norm_map:
            if norm_map[expected] == "pass":
                matched_pass.add(expected)
            elif norm_map[expected] == "fail":
                matched_fail.add(expected)
            continue

        # Try parameterized match: collect all variants where base matches
        variants = {n: s for n, s in norm_map.items() if n.split("[")[0] == expected}
        if variants:
            all_pass = all(s == "pass" for s in variants.values())
            any_fail = any(s == "fail" for s in variants.values())
            if all_pass:
                matched_pass.add(expected)
            elif any_fail:
                matched_fail.add(expected)

    return matched_pass, matched_fail


def reeval_condition(
    run_dir: Path, label: str, instances: list[dict], *, verbose: bool = True
) -> dict[str, Any]:
    """Re-evaluate one condition (baseline or enhanced) within a run directory.

    Reads existing status.json files, applies P2P-gated resolution criteria
    with normalized test names, and writes corrected report.json + eval_results.json.

    Args:
        run_dir: Root of the pilot40-style run directory
        label: Condition label (e.g. "baseline", "enhanced")
        instances: List of instance dicts with PASS_TO_PASS / FAIL_TO_PASS fields
        verbose: Print per-instance details

    Returns:
        Dict with resolved count, resolved_ids, failed_ids, and per-instance details.
    """
    eval_dir = run_dir / f"stage5_solver_eval/eval_{label}"
    all_ids = [inst["instance_id"] for inst in instances]

    resolved_ids: list[str] = []
    failed_ids: list[str] = []
    details: dict[str, Any] = {}

    for inst in instances:
        iid = inst["instance_id"]
        status_path = eval_dir / iid / "status.json"
        report_path = eval_dir / iid / "report.json"

        p2p_expected = set(inst.get("PASS_TO_PASS", []))
        f2p_expected = set(inst.get("FAIL_TO_PASS", []))

        if not status_path.exists():
            failed_ids.append(iid)
            details[iid] = {"reason": "no_status_json", "resolved": False}
            report = {
                "instance_id": iid,
                "resolved": False,
                "PASS_TO_PASS": {"success": [], "failure": []},
                "FAIL_TO_PASS": {"success": [], "failure": []},
                "reeval_note": "no status.json — tests did not produce output",
            }
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2))
            continue

        status = json.loads(status_path.read_text())
        if not status:
            failed_ids.append(iid)
            details[iid] = {"reason": "empty_status", "resolved": False}
            report = {
                "instance_id": iid,
                "resolved": False,
                "PASS_TO_PASS": {"success": [], "failure": []},
                "FAIL_TO_PASS": {"success": [], "failure": []},
                "reeval_note": "empty status.json — no tests parsed",
            }
            report_path.write_text(json.dumps(report, indent=2))
            continue

        # Handle evaluation framework error: status.json written as an error string
        if isinstance(status, str):
            failed_ids.append(iid)
            details[iid] = {"reason": "eval_framework_error", "resolved": False,
                            "error_snippet": status[:200]}
            report = {
                "instance_id": iid,
                "resolved": False,
                "PASS_TO_PASS": {"success": [], "failure": []},
                "FAIL_TO_PASS": {"success": [], "failure": []},
                "reeval_note": f"eval framework error — status.json is a string: {status[:120]}",
            }
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2))
            continue

        # Build parsed set with status
        parsed = {(normalize_test_name(k), v) for k, v in status.items()}

        # Match against expected test names
        p2p_pass, p2p_fail = match_tests(parsed, p2p_expected)
        f2p_pass, f2p_fail = match_tests(parsed, f2p_expected)

        # Resolution criteria for P2P-gated dataset:
        # 1. No P2P failures
        # 2. At least one P2P test was actually found and passed
        #    (avoid vacuous resolution when tests didn't run)
        # 3. F2P is informational — reported but not gating
        p2p_clean = len(p2p_fail) == 0
        p2p_evidence = len(p2p_pass) > 0
        resolved = p2p_clean and p2p_evidence

        detail = {
            "resolved": resolved,
            "p2p_expected": len(p2p_expected),
            "p2p_pass": sorted(p2p_pass),
            "p2p_fail": sorted(p2p_fail),
            "f2p_expected": len(f2p_expected),
            "f2p_pass": sorted(f2p_pass),
            "f2p_fail": sorted(f2p_fail),
            "total_parsed_tests": len(status),
        }
        details[iid] = detail

        if resolved:
            resolved_ids.append(iid)
        else:
            failed_ids.append(iid)

        # Write corrected report.json
        report = {
            "instance_id": iid,
            "resolved": resolved,
            "PASS_TO_PASS": {
                "success": sorted(p2p_pass),
                "failure": sorted(p2p_fail),
            },
            "FAIL_TO_PASS": {
                "success": sorted(f2p_pass),
                "failure": sorted(f2p_fail),
            },
            "reeval_note": "Re-evaluated with normalized test names and P2P-gated criteria",
        }
        report_path.write_text(json.dumps(report, indent=2))

    # Write corrected eval_results.json
    result: dict[str, Any] = {
        "resolved": len(resolved_ids),
        "total": len(all_ids),
        "resolved_ids": sorted(resolved_ids),
        "failed_ids": sorted(failed_ids),
        "reeval_details": details,
    }
    (eval_dir / "eval_results.json").write_text(json.dumps(result, indent=2))

    return result


def reeval_run(
    run_dir: Path,
    conditions: list[str] | None = None,
    *,
    instances_path: Path | None = None,
    expected_count: int | None = None,
    verbose: bool = True,
) -> dict[str, dict[str, Any]]:
    """Re-evaluate all conditions in a pilot40-style run directory.

    Args:
        run_dir: Root of the run directory (must contain validated_instances.jsonl
                 and stage5_solver_eval/)
        conditions: List of condition labels to re-evaluate.
                    Defaults to ["baseline", "enhanced"].
        instances_path: Path to the instances JSONL. Defaults to
                        run_dir / "validated_instances.jsonl".
        expected_count: If set, assert instance count matches.
        verbose: Print progress.

    Returns:
        Dict mapping condition label -> reeval result dict.
    """
    if conditions is None:
        conditions = ["baseline", "enhanced"]

    inst_path = instances_path or (run_dir / "validated_instances.jsonl")
    instances = load_jsonl(inst_path)

    if expected_count is not None:
        assert len(instances) == expected_count, (
            f"Expected {expected_count} instances, got {len(instances)}"
        )

    if verbose:
        print(f"Re-evaluating {run_dir.name} with P2P-gated criteria "
              f"({len(instances)} instances)\n")

    results: dict[str, dict[str, Any]] = {}

    for label in conditions:
        eval_dir = run_dir / f"stage5_solver_eval/eval_{label}"
        if not eval_dir.exists():
            if verbose:
                print(f"  SKIP {label}: no eval dir")
            continue

        result = reeval_condition(run_dir, label, instances, verbose=verbose)
        results[label] = result
        resolved_ids = result["resolved_ids"]

        if verbose:
            print(f"  {label}: {result['resolved']}/{result['total']} resolved")
            for iid in resolved_ids:
                d = result["reeval_details"][iid]
                itype = next(
                    (i.get("issue_type", "?") for i in instances
                     if i["instance_id"] == iid),
                    "?",
                )
                print(f"    {iid} ({itype}): "
                      f"P2P {len(d['p2p_pass'])}/{d['p2p_expected']} pass")

    return results


# ── CLI entrypoint ──────────────────────────────────────────────────────────

def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="P2P-gated re-evaluation for pilot40-style runs")
    parser.add_argument(
        "--run-dir", required=True, type=Path,
        help="Root of the pilot40-style run directory")
    parser.add_argument(
        "--conditions", nargs="+", default=["baseline", "enhanced"],
        help="Condition labels to re-evaluate (default: baseline enhanced)")
    parser.add_argument(
        "--expected-count", type=int, default=None,
        help="Assert instance count matches this value")
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    if not run_dir.exists():
        print(f"ERROR: run directory not found: {run_dir}")
        return 1

    results = reeval_run(
        run_dir,
        conditions=args.conditions,
        expected_count=args.expected_count,
    )

    if not results:
        print("\nNo conditions were re-evaluated.")
        return 1

    print("\nDone. Re-evaluation complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
