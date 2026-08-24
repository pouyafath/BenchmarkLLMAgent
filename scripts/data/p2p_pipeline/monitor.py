#!/usr/bin/env python3
"""
P2P Pipeline — Live Monitor.

Shows current status across all pipeline stages, including enhanced run
with memory pool + error feedback and GPT-5.4-mini fallback.

Usage:
    python scripts/data/p2p_pipeline/monitor.py
    watch -n 30 python scripts/data/p2p_pipeline/monitor.py   # auto-refresh every 30s
"""

import json
import pathlib
import subprocess
import time

ROOT       = pathlib.Path(__file__).resolve().parents[3]
PIPELINE   = ROOT / "data/samples/pouya_p2p_pipeline"
PAUL_BASE  = pathlib.Path("/home/22pf2/paul-RepoLaunch/workspace")
RUNS_DIR   = ROOT / "runs"

# All Paul workspaces to track
PAUL_WORKSPACES = {
    "Original (gpt-oss)":         PAUL_BASE / "p2p_pipeline_stage2_20260515",
    "Retry (GPT-5.4-mini)":       PAUL_BASE / "p2p_pipeline_retry_gpt54mini",
    "Enhanced (memory+feedback)": PAUL_BASE / "p2p_pipeline_enhanced",
    "Fallback (GPT-5.4-mini)":    PAUL_BASE / "p2p_pipeline_fallback_gpt54mini",
    "Stage2 Full 2026 [ACTIVE]":  PAUL_BASE / "stage2_2026_full",
}


def check_stage1():
    # New 2026 dataset takes priority
    ds = ROOT / "data/samples/pouya_dataset_2026_stage1/dataset.jsonl"
    summary = ROOT / "data/samples/pouya_dataset_2026_stage1/summary.json"
    if not ds.exists():
        ds = PIPELINE / "stage1_approach1/dataset.jsonl"
        summary = PIPELINE / "stage1_approach1/summary.json"
    if not ds.exists():
        return "NOT STARTED", {}
    rows = [json.loads(l) for l in open(ds)]
    total = len(rows)
    from collections import Counter
    by_type = Counter(r.get("issue_type") for r in rows if r.get("issue_type") in {"bug","feature","refactoring","unknown"})
    labeled = sum(by_type.values())
    status = "DONE" if labeled == total else f"CLASSIFYING {labeled}/{total}"
    return status, {"total": total, **dict(by_type)}


def _scan_paul_workspace(ws_path):
    """Scan a Paul workspace and return stats."""
    if not ws_path.exists():
        return None
    playground = ws_path / "playground"
    if not playground.exists():
        return None

    completed = 0
    docker_built = 0
    nonetype_fail = 0
    launch_fail = 0
    other_fail = 0

    for rf in playground.glob("*/result.json"):
        try:
            r = json.loads(rf.read_text())
            completed += 1
            if r.get("docker_image"):
                docker_built += 1
            else:
                exc = r.get("exception", "") or ""
                if "NoneType" in exc:
                    nonetype_fail += 1
                elif "Launch failed" in exc:
                    launch_fail += 1
                else:
                    other_fail += 1
        except Exception:
            pass

    return {
        "completed": completed,
        "docker_built": docker_built,
        "nonetype_fail": nonetype_fail,
        "launch_fail": launch_fail,
        "other_fail": other_fail,
    }


def check_stage2_all():
    """Check all Paul workspaces and aggregate."""
    results = {}
    for name, ws in PAUL_WORKSPACES.items():
        stats = _scan_paul_workspace(ws)
        if stats:
            results[name] = stats

    # Check which Paul processes are running
    try:
        out = subprocess.run(["pgrep", "-af", "paul.run"], capture_output=True, text=True).stdout
    except Exception:
        out = ""

    running = {}
    for name, ws in PAUL_WORKSPACES.items():
        ws_dir = ws.name
        running[name] = ws_dir in out

    return results, running


def _get_global_success_ids():
    """Get all unique successful instance IDs across all workspaces."""
    success_ids = set()
    for name, ws in PAUL_WORKSPACES.items():
        playground = ws / "playground"
        if not playground.exists():
            continue
        for rf in playground.glob("*/result.json"):
            try:
                r = json.loads(rf.read_text())
                if r.get("docker_image"):
                    success_ids.add(r["instance_id"])
            except Exception:
                pass
    return success_ids


def check_stage3():
    ds = PIPELINE / "stage3_approach3/dataset.jsonl"
    if not ds.exists():
        return "NOT STARTED", {}
    rows = sum(1 for _ in open(ds))
    return "DONE", {"total": rows}


def check_experiments():
    """Check all experiment runs."""
    results = []
    for run_dir in sorted(RUNS_DIR.glob("p2p_experiment_*")):
        progress = run_dir / "progress.json"
        if not progress.exists():
            results.append((run_dir.name, "NO PROGRESS", {}))
            continue
        p = json.loads(progress.read_text())
        step = p.get("step", "?")
        total = p.get("total_instances", 0)
        baseline = p.get("baseline_resolved", [])
        enhanced = p.get("enhanced_resolved", [])

        analysis = run_dir / "analysis.json"
        analysis_data = {}
        if analysis.exists():
            analysis_data = json.loads(analysis.read_text())

        results.append((run_dir.name, step, {
            "total": total,
            "baseline_resolved": len(baseline) if isinstance(baseline, list) else baseline,
            "enhanced_resolved": len(enhanced) if isinstance(enhanced, list) else enhanced,
            "improvement_pp": analysis_data.get("improvement_pp", "—"),
            "issue_types": p.get("issue_types", {}),
        }))
    return results


def main():
    print("=" * 75)
    print(f"  P2P PIPELINE MONITOR — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 75)

    # Stage 1
    s1_status, s1_info = check_stage1()
    total = s1_info.get("total", 0)
    print(f"\n  STAGE 1 (Static Parse + LLM Classify):  [{s1_status}]")
    if s1_info:
        bug = s1_info.get("bug", 0)
        feat = s1_info.get("feature", 0)
        refact = s1_info.get("refactoring", 0)
        unk = s1_info.get("unknown", 0)
        print(f"    Total: {total}  |  Bug: {bug}  Feature: {feat}  Refactoring: {refact}  Unknown: {unk}")

    # Stage 2 — All workspaces
    ws_results, ws_running = check_stage2_all()
    global_success = _get_global_success_ids()

    print(f"\n  STAGE 2 (Paul/RepoLaunch Docker):  [{len(global_success)}/{total} total success]")
    print(f"  {'Workspace':<35} {'Done':>5} {'OK':>4} {'NoneT':>5} {'LaunchF':>7} {'Other':>5} {'Run':>4}")
    print(f"  {'-'*69}")
    for name in PAUL_WORKSPACES:
        stats = ws_results.get(name)
        if stats:
            is_running = "YES" if ws_running.get(name) else "no"
            print(f"  {name:<35} {stats['completed']:>5} {stats['docker_built']:>4} "
                  f"{stats['nonetype_fail']:>5} {stats['launch_fail']:>7} {stats['other_fail']:>5} {is_running:>4}")

    # Global success by repo (top contributors)
    if global_success:
        from collections import Counter
        repos = Counter()
        for iid in global_success:
            repo = iid.rsplit("-", 1)[0]
            repos[repo] += 1
        top = repos.most_common(5)
        print(f"\n  Top repos: {', '.join(f'{r}({c})' for r,c in top)}")

    # Stage 3
    s3_status, s3_info = check_stage3()
    print(f"\n  STAGE 3 (Full Test Suite):               [{s3_status}]")
    if s3_info:
        print(f"    Total: {s3_info['total']}")

    # Experiments
    experiments = check_experiments()
    print(f"\n  EXPERIMENTS:")
    if not experiments:
        print("    No experiment runs found yet.")
    for name, step, info in experiments:
        total_exp = info.get("total", 0)
        bl = info.get("baseline_resolved", "—")
        en = info.get("enhanced_resolved", "—")
        imp = info.get("improvement_pp", "—")
        types = info.get("issue_types", {})
        print(f"    [{step:25s}] {name}")
        print(f"      Instances: {total_exp}  |  Types: {types}")
        print(f"      Baseline: {bl}/{total_exp}  |  Enhanced: {en}/{total_exp}  |  Improvement: {imp}pp")

    print("\n" + "=" * 75)
    print("  Commands:")
    print("    Monitor:    watch -n 30 python scripts/data/p2p_pipeline/monitor.py")
    print("    Enhanced:   tail -f ~/paul-RepoLaunch/workspace/p2p_pipeline_enhanced/p2p_pipeline_enhanced_run.log")
    print("    Auto-chain: tail -f runs/p2p_enhanced_fallback_auto.log")
    print("    Exp log:    tail -f runs/p2p_experiment_*/progress.log")
    print("=" * 75)


if __name__ == "__main__":
    main()
