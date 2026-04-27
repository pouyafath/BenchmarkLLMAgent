#!/usr/bin/env python3
"""
Derive F2P/P2P counts from sklearn baseline+gold test outputs,
merge with Flask/Requests v2 qualifying issues,
and produce the final 10-issue second-paper dataset.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from swebench.harness.grading import get_logs_eval, test_failed, test_passed
from swebench.harness.test_spec.test_spec import make_test_spec
from swebench.harness.constants import MAP_REPO_VERSION_TO_SPECS, MAP_REPO_TO_EXT


# ---------- paths ----------
SKLEARN_DIR = ROOT / "data" / "samples" / "second_paper_sklearn_exact_f2p_p2p_v1"
SKLEARN_INSTANCES = SKLEARN_DIR / "custom_instances_raw.jsonl"

FLASK_DIR = ROOT / "data" / "samples" / "second_paper_flask_requests_exact_f2p_p2p_v2"
FLASK_INSTANCES = FLASK_DIR / "custom_instances_with_f2p_p2p.jsonl"
FLASK_SUMMARY = FLASK_DIR / "f2p_p2p_derivation_summary.json"

BASELINE_RUN_ID = "secondpaper_custom_baseline_probe_second_paper_sklearn_exact_f2p_p2p_v1"
GOLD_RUN_ID = "secondpaper_custom_gold_probe_second_paper_sklearn_exact_f2p_p2p_v1"
BASELINE_MODEL = "baseline_noop_patch_probe"
GOLD_MODEL = "gold_patch_probe"

OUTPUT_DIR = ROOT / "data" / "samples" / "second_paper_final_10_f2p_p2p"


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def derive_sklearn_f2p_p2p() -> tuple[list[dict], list[dict]]:
    """Parse sklearn baseline+gold test outputs and derive F2P/P2P."""
    instances = load_jsonl(SKLEARN_INSTANCES)

    baseline_dir = ROOT / "logs" / "run_evaluation" / BASELINE_RUN_ID / BASELINE_MODEL
    gold_dir = ROOT / "logs" / "run_evaluation" / GOLD_RUN_ID / GOLD_MODEL

    results = []
    summaries = []

    for inst in instances:
        iid = inst["instance_id"]
        b_log = baseline_dir / iid / "test_output.txt"
        g_log = gold_dir / iid / "test_output.txt"

        if not b_log.exists() or not g_log.exists():
            summaries.append({
                "instance_id": iid,
                "repo": inst["repo"],
                "issue_number": inst["issue_number"],
                "error": "missing_test_output",
                "baseline_log_exists": b_log.exists(),
                "gold_log_exists": g_log.exists(),
            })
            continue

        test_spec = make_test_spec(inst)
        b_status, b_ok = get_logs_eval(test_spec, str(b_log))
        g_status, g_ok = get_logs_eval(test_spec, str(g_log))

        if not b_ok or not g_ok:
            summaries.append({
                "instance_id": iid,
                "repo": inst["repo"],
                "issue_number": inst["issue_number"],
                "error": "unparseable_test_output",
                "baseline_log_ok": b_ok,
                "gold_log_ok": g_ok,
            })
            continue

        all_tests = sorted(set(b_status.keys()) | set(g_status.keys()))
        f2p, p2p, f2f, p2f = [], [], [], []

        for t in all_tests:
            b_pass = test_passed(t, b_status)
            g_pass = test_passed(t, g_status)
            b_fail = test_failed(t, b_status)
            g_fail = test_failed(t, g_status)

            if b_fail and g_pass:
                f2p.append(t)
            elif b_pass and g_pass:
                p2p.append(t)
            elif b_fail and g_fail:
                f2f.append(t)
            elif b_pass and g_fail:
                p2f.append(t)

        # Update instance with derived F2P/P2P
        updated = dict(inst)
        updated.pop("_baseline_patch", None)
        updated["FAIL_TO_PASS"] = f2p
        updated["PASS_TO_PASS"] = p2p
        results.append(updated)

        summaries.append({
            "instance_id": iid,
            "repo": inst["repo"],
            "issue_number": inst["issue_number"],
            "baseline_tests_seen": len(b_status),
            "gold_tests_seen": len(g_status),
            "all_tests_union": len(all_tests),
            "FAIL_TO_PASS_count": len(f2p),
            "PASS_TO_PASS_count": len(p2p),
            "FAIL_TO_FAIL_count": len(f2f),
            "PASS_TO_FAIL_count": len(p2f),
        })

    return results, summaries


def load_flask_qualifying() -> tuple[list[dict], list[dict]]:
    """Load Flask/Requests qualifying instances (F2P>0 and P2P>0)."""
    summary_data = json.loads(FLASK_SUMMARY.read_text())
    instances = load_jsonl(FLASK_INSTANCES)

    qualifying = []
    qualifying_summaries = []

    inst_map = {inst["instance_id"]: inst for inst in instances}

    for entry in summary_data["per_instance"]:
        if entry.get("FAIL_TO_PASS_count", 0) > 0 and entry.get("PASS_TO_PASS_count", 0) > 0:
            iid = entry["instance_id"]
            if iid in inst_map:
                qualifying.append(inst_map[iid])
                qualifying_summaries.append(entry)

    return qualifying, qualifying_summaries


def main():
    print("=== Deriving sklearn F2P/P2P from test outputs ===")
    sklearn_instances, sklearn_summaries = derive_sklearn_f2p_p2p()

    print("\nSklearn results:")
    sklearn_qualifying = []
    sklearn_qualifying_summaries = []
    for s in sklearn_summaries:
        f2p = s.get("FAIL_TO_PASS_count", 0)
        p2p = s.get("PASS_TO_PASS_count", 0)
        err = s.get("error", "")
        status = f"F2P={f2p} P2P={p2p}" if not err else f"ERROR: {err}"
        qualifying_mark = " *** QUALIFYING ***" if f2p > 0 and p2p > 0 else ""
        print(f"  {s['instance_id']}: {status}{qualifying_mark}")
        if f2p > 0 and p2p > 0:
            # Find matching instance
            for inst in sklearn_instances:
                if inst["instance_id"] == s["instance_id"]:
                    sklearn_qualifying.append(inst)
                    sklearn_qualifying_summaries.append(s)
                    break

    print(f"\nSklearn qualifying: {len(sklearn_qualifying)}")

    print("\n=== Loading Flask/Requests qualifying ===")
    flask_qualifying, flask_summaries = load_flask_qualifying()
    print(f"Flask/Requests qualifying: {len(flask_qualifying)}")
    for s in flask_summaries:
        print(f"  {s['instance_id']}: F2P={s['FAIL_TO_PASS_count']} P2P={s['PASS_TO_PASS_count']}")

    # Merge
    all_qualifying = flask_qualifying + sklearn_qualifying
    all_summaries = flask_summaries + sklearn_qualifying_summaries
    print(f"\n=== Total qualifying: {len(all_qualifying)} ===")

    if len(all_qualifying) < 10:
        print(f"WARNING: Only {len(all_qualifying)} qualifying issues found, need 10.")
    elif len(all_qualifying) > 10:
        print(f"NOTE: {len(all_qualifying)} qualifying, selecting first 10.")
        all_qualifying = all_qualifying[:10]
        all_summaries = all_summaries[:10]

    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    final_jsonl = OUTPUT_DIR / "final_10_instances_with_f2p_p2p.jsonl"
    summary_json = OUTPUT_DIR / "final_derivation_summary.json"
    sklearn_summary_json = OUTPUT_DIR / "sklearn_derivation_summary.json"

    with open(final_jsonl, "w") as f:
        for inst in all_qualifying:
            f.write(json.dumps(inst) + "\n")

    summary_data = {
        "total_qualifying": len(all_qualifying),
        "flask_qualifying": len(flask_qualifying),
        "sklearn_qualifying": len(sklearn_qualifying),
        "instance_ids": [i["instance_id"] for i in all_qualifying],
        "per_instance": all_summaries,
    }
    summary_json.write_text(json.dumps(summary_data, indent=2))

    sklearn_summary_data = {
        "total_instances": 14,
        "instances_with_results": len(sklearn_instances),
        "qualifying": len(sklearn_qualifying),
        "per_instance": sklearn_summaries,
    }
    sklearn_summary_json.write_text(json.dumps(sklearn_summary_data, indent=2))

    print(f"\nWrote final JSONL: {final_jsonl}")
    print(f"Wrote summary: {summary_json}")
    print(f"Wrote sklearn summary: {sklearn_summary_json}")

    # Print final dataset overview
    print("\n=== FINAL DATASET ===")
    for s in all_summaries:
        print(f"  {s['instance_id']}: F2P={s.get('FAIL_TO_PASS_count', 0)} P2P={s.get('PASS_TO_PASS_count', 0)}")


if __name__ == "__main__":
    main()
