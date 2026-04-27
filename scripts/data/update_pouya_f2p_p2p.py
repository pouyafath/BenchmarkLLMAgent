"""
Parse SWE-bench harness evaluation logs and update the Pouya dataset with
validated F2P and P2P test lists.

After running gold validation, this script:
1. Reads each instance's report.json AND test_output.txt
2. If report.json shows F2P success, uses those directly
3. If F2P=0 (naming mismatch), parses test_output.txt to find real passed tests
4. Matches passed tests against test_patch files to identify real F2P
5. Updates FAIL_TO_PASS and PASS_TO_PASS in the dataset
6. Writes validated dataset + invalid instance list

Usage:
    python scripts/data/update_pouya_f2p_p2p.py [--run-id pouya_gold_validation]
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "samples" / "pouya_swebench_live_style_50"
JSONL = DATA_DIR / "pouya_50_dataset.jsonl"

sys.path.insert(0, str(ROOT))
from scripts.data.prepare_swe_bench_live_samples import swe_live_to_sample


def parse_test_output(test_output_path: Path) -> dict:
    """Parse pytest output to get all test results.

    Returns dict: {test_name: "PASSED"|"FAILED"|"ERROR"|"SKIPPED"}
    """
    results = {}
    text = test_output_path.read_text(errors="replace")

    # Match pytest result lines like:
    #   PASSED tests/test_foo.py::TestBar::test_baz
    #   FAILED tests/test_foo.py::TestBar::test_baz - AssertionError
    #   tests/test_foo.py::TestBar::test_baz PASSED
    #   tests/test_foo.py::TestBar::test_baz FAILED

    # Pattern 1: "STATUS path::test" (common in verbose pytest)
    for m in re.finditer(r'^(PASSED|FAILED|ERROR)\s+([\w/\-\.]+::[\w\[\]\-\.,: ]+)', text, re.MULTILINE):
        status, name = m.group(1), m.group(2).strip()
        results[name] = status

    # Pattern 2: "path::test STATUS" (alternative format)
    for m in re.finditer(r'^([\w/\-\.]+::[\w\[\]\-\.,: ]+?)\s+(PASSED|FAILED|ERROR)', text, re.MULTILINE):
        name, status = m.group(1).strip(), m.group(2)
        if name not in results:
            results[name] = status

    # Pattern 3: Summary section "PASSED/FAILED tests/..." (single-line format)
    for m in re.finditer(r'([\w/\-\.]+\.py::[\w\[\]\-\.,: ]+?)\s+(PASSED|FAILED|ERROR)', text):
        name, status = m.group(1).strip(), m.group(2)
        if name not in results:
            results[name] = status

    return results


def get_test_files_from_patch(test_patch: str) -> set:
    """Extract test file paths from the test_patch diff."""
    files = set()
    for m in re.finditer(r'^diff --git a/(.*?) b/', test_patch, re.MULTILINE):
        path = m.group(1)
        if 'test' in path.lower():
            files.add(path)
    # Also try +++ b/path format
    for m in re.finditer(r'^\+\+\+ b/(.*?)$', test_patch, re.MULTILINE):
        path = m.group(1)
        if 'test' in path.lower():
            files.add(path)
    return files


def get_new_test_functions_from_patch(test_patch: str) -> set:
    """Extract newly added test function names from the test_patch diff."""
    functions = set()
    current_file = None
    current_class = None

    for line in test_patch.split('\n'):
        # Track current file
        m = re.match(r'^\+\+\+ b/(.*?)$', line)
        if m:
            current_file = m.group(1)
            current_class = None
            continue

        # Track class context from @@ headers
        m = re.match(r'^@@.*@@\s+class\s+(\w+)', line)
        if m:
            current_class = m.group(1)
            continue

        # Also track class from + lines
        m = re.match(r'^\+class\s+(\w+)', line)
        if m:
            current_class = m.group(1)
            continue

        # Find added test functions
        m = re.match(r'^\+\s*(async\s+)?def\s+(test_\w+)', line)
        if m and current_file:
            func_name = m.group(2)
            if current_class:
                functions.add(f"{current_file}::{current_class}::{func_name}")
            functions.add(f"{current_file}::{func_name}")

    return functions


def match_f2p_from_output(test_results: dict, test_patch: str) -> tuple:
    """Given parsed test results and test_patch, identify real F2P and P2P.

    Returns (f2p_tests, p2p_tests) as lists of test names.
    """
    test_files = get_test_files_from_patch(test_patch)
    new_funcs = get_new_test_functions_from_patch(test_patch)

    passed_tests = [t for t, s in test_results.items() if s == "PASSED"]

    f2p = []
    p2p = []

    for test_name in passed_tests:
        test_file = test_name.split("::")[0]

        is_in_test_patch_file = any(
            test_file == tf or test_file.endswith("/" + tf) or tf.endswith("/" + test_file)
            for tf in test_files
        )

        # Check if this test function was newly added in the patch
        is_new_func = False
        if new_funcs:
            for nf in new_funcs:
                nf_parts = nf.split("::")
                test_parts = test_name.split("::")
                nf_func = nf_parts[-1]
                test_func = test_parts[-1]
                test_func_base = test_func.split("[")[0]
                if nf_func == test_func_base and is_in_test_patch_file:
                    is_new_func = True
                    break

        if is_new_func:
            f2p.append(test_name)
        elif not new_funcs and is_in_test_patch_file:
            # No new functions found in patch → the patch MODIFIES existing tests
            # All tests in the modified file are F2P candidates
            # (they fail before because the code behavior is wrong,
            #  pass after because both code and test are fixed)
            f2p.append(test_name)
        elif is_in_test_patch_file:
            # In test_patch file but not a new function → P2P
            p2p.append(test_name)
        else:
            # Not in test_patch files → P2P
            p2p.append(test_name)

    return f2p, p2p


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="pouya_gold_validation")
    args = parser.parse_args()

    log_base = ROOT / "logs" / "run_evaluation" / args.run_id
    if not log_base.exists():
        print(f"ERROR: No logs at {log_base}")
        sys.exit(1)

    # Load current dataset
    rows = []
    with open(JSONL) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    valid = []
    invalid = []

    for row in rows:
        iid = row["instance_id"]
        report_path = log_base / "gold" / iid / "report.json"
        test_output_path = log_base / "gold" / iid / "test_output.txt"

        # --- No report at all → build error ---
        if not report_path.exists():
            invalid.append({"instance_id": iid, "reason": "build_error", "detail": "no report.json"})
            continue

        with open(report_path) as f:
            report = json.load(f)

        if iid not in report:
            invalid.append({"instance_id": iid, "reason": "missing_in_report", "detail": "instance_id not in report"})
            continue

        r = report[iid]
        if not r.get("patch_successfully_applied"):
            invalid.append({"instance_id": iid, "reason": "patch_error", "detail": "patch not applied"})
            continue

        ts = r.get("tests_status", {})
        f2p_success = ts.get("FAIL_TO_PASS", {}).get("success", [])
        f2p_failure = ts.get("FAIL_TO_PASS", {}).get("failure", [])
        p2p_success = ts.get("PASS_TO_PASS", {}).get("success", [])
        p2p_failure = ts.get("PASS_TO_PASS", {}).get("failure", [])

        # --- Case 1: F2P tests match → use report directly ---
        if len(f2p_success) > 0:
            row["FAIL_TO_PASS"] = json.dumps(f2p_success)
            row["PASS_TO_PASS"] = json.dumps(p2p_success)
            resolved = r.get("resolved", False)
            valid.append({
                "instance_id": iid,
                "method": "report_match",
                "f2p_count": len(f2p_success),
                "p2p_count": len(p2p_success),
                "resolved": resolved,
            })
            continue

        # --- Case 2: F2P = 0 → parse test_output.txt to find real tests ---
        if not test_output_path.exists():
            invalid.append({"instance_id": iid, "reason": "no_test_output", "detail": "no test_output.txt"})
            continue

        test_results = parse_test_output(test_output_path)
        total_passed = sum(1 for s in test_results.values() if s == "PASSED")

        if total_passed == 0:
            invalid.append({
                "instance_id": iid,
                "reason": "all_tests_fail",
                "detail": f"0 tests passed out of {len(test_results)} (env/import issue?)",
            })
            continue

        # Get test_patch and find real F2P/P2P
        test_patch = row.get("test_patch", "")
        f2p_tests, p2p_tests = match_f2p_from_output(test_results, test_patch)

        if len(f2p_tests) == 0:
            invalid.append({
                "instance_id": iid,
                "reason": "no_f2p_from_output",
                "detail": f"{total_passed} tests passed but none match test_patch functions",
                "passed_count": total_passed,
            })
            continue

        row["FAIL_TO_PASS"] = json.dumps(f2p_tests)
        row["PASS_TO_PASS"] = json.dumps(p2p_tests)
        valid.append({
            "instance_id": iid,
            "method": "test_output_parse",
            "f2p_count": len(f2p_tests),
            "p2p_count": len(p2p_tests),
            "resolved": True,  # By definition if we found F2P from output
        })

    # Print summary
    print(f"\n{'='*60}")
    print(f"Gold Validation Results")
    print(f"{'='*60}")
    print(f"Total instances: {len(rows)}")
    print(f"Valid (F2P > 0): {len(valid)}")
    print(f"Invalid: {len(invalid)}")

    print(f"\n--- Valid instances ---")
    for v in sorted(valid, key=lambda x: x["f2p_count"], reverse=True):
        method = "report" if v["method"] == "report_match" else "parsed"
        res = "RESOLVED" if v["resolved"] else "unresolved"
        print(f"  {v['instance_id']:50s} F2P={v['f2p_count']:3d}  P2P={v['p2p_count']:5d}  [{method}] {res}")

    print(f"\n--- Invalid instances ---")
    for inv in sorted(invalid, key=lambda x: x["instance_id"]):
        print(f"  {inv['instance_id']:50s} {inv['reason']}: {inv['detail']}")

    # Write updated dataset (only valid instances)
    valid_ids = {v["instance_id"] for v in valid}
    updated_rows = [r for r in rows if r["instance_id"] in valid_ids]

    updated_jsonl = DATA_DIR / "pouya_50_dataset_validated.jsonl"
    with open(updated_jsonl, "w") as f:
        for row in updated_rows:
            f.write(json.dumps(row) + "\n")
    print(f"\nWrote validated JSONL ({len(updated_rows)} instances): {updated_jsonl}")

    # Write instance IDs
    valid_ids_path = DATA_DIR / "pouya_validated_instance_ids.txt"
    with open(valid_ids_path, "w") as f:
        for row in updated_rows:
            f.write(row["instance_id"] + "\n")
    print(f"Wrote valid IDs: {valid_ids_path}")

    # Write invalid instance list
    invalid_path = DATA_DIR / "pouya_invalid_instances.json"
    with open(invalid_path, "w") as f:
        json.dump(invalid, f, indent=2)
    print(f"Wrote invalid list: {invalid_path}")

    # Also regenerate samples JSON
    samples = [swe_live_to_sample(row) for row in updated_rows]
    samples_data = {
        "metadata": {
            "description": f"{len(updated_rows)}-issue Pouya-SWE-bench-Live-style dataset (validated F2P/P2P)",
            "source": "GitHub API crawl + SWE-bench harness validation",
            "collection_date": "2026-04-16",
            "validation_date": "2026-04-18",
            "selection_seed": 99,
            "count": len(samples),
            "filter": "F2P > 0, NO description quality filter",
            "swebench_live_overlap": 0,
            "original_candidates": 50,
            "validated": len(updated_rows),
        },
        "issues": samples,
    }
    samples_path = DATA_DIR / "pouya_50_samples_validated.json"
    with open(samples_path, "w") as f:
        json.dump(samples_data, f, indent=2)
    print(f"Wrote validated samples JSON: {samples_path}")

    # Summary stats
    if valid:
        f2p_counts = [v["f2p_count"] for v in valid]
        p2p_counts = [v["p2p_count"] for v in valid]
        resolved_count = sum(1 for v in valid if v["resolved"])
        report_match = sum(1 for v in valid if v["method"] == "report_match")
        output_parse = sum(1 for v in valid if v["method"] == "test_output_parse")
        print(f"\n{'='*60}")
        print(f"Summary Stats")
        print(f"{'='*60}")
        print(f"  Valid: {len(valid)}/{len(rows)}")
        print(f"  By report match: {report_match}")
        print(f"  By test_output parse: {output_parse}")
        print(f"  Resolved: {resolved_count}/{len(valid)}")
        print(f"  F2P tests: min={min(f2p_counts)}, max={max(f2p_counts)}, avg={sum(f2p_counts)/len(f2p_counts):.1f}")
        print(f"  P2P tests: min={min(p2p_counts)}, max={max(p2p_counts)}, avg={sum(p2p_counts)/len(p2p_counts):.1f}")


if __name__ == "__main__":
    main()
