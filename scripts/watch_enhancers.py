#!/usr/bin/env python3
"""Monitor all native-enhancer runs: shows stage + X/20 progress per enhancer."""

import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_TS = "20260505_084500"
ENHANCERS = ["aider", "trae", "openhands", "mini_swe_agent", "swe_agent"]
TOTAL = 20


def _last_info(log_path: Path) -> str:
    if not log_path.exists():
        return ""
    lines = [l for l in log_path.read_text().splitlines() if "[INFO]" in l]
    return lines[-1] if lines else ""


def _count_dir(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for p in path.iterdir() if p.is_dir())


def _count_reports(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for p in path.glob("*/report.json"))


def _traj_count(solver_dir: Path) -> int:
    return sum(1 for p in solver_dir.glob("*/*.traj.json")) if solver_dir.exists() else 0


def _get_status(run_dir: Path, enhancer: str):
    last = _last_info(run_dir / "run.log")

    # Stage detection
    if "DONE." in last:
        m = re.search(r"Enhanced=(\d+)/(\d+)", last)
        enhanced = int(m.group(1)) if m else "?"
        return "DONE", f"enhanced resolved: {enhanced}/{TOTAL}", enhanced
    elif "enhanced_eval" in last and "resolved" in last:
        m = re.search(r"solver_enhanced_eval: (\d+)/(\d+)", last)
        done = int(m.group(1)) if m else _count_reports(run_dir / "solver_enhanced_eval")
        return "eval_done", f"enhanced resolved: {done}/{TOTAL}", done
    elif "enhanced solver done" in last or ("Evaluating" in last and "enhanced" in (run_dir / "run.log").read_text().split("Evaluating")[-1] if (run_dir / "run.log").exists() else False):
        done = _count_reports(run_dir / "solver_enhanced_eval")
        return "enhanced_eval", f"eval {done}/{TOTAL} instances checked", done
    elif "mini-SWE-agent enhanced" in last:
        done = _traj_count(run_dir / "solver_enhanced")
        return "solver_enhanced", f"{done}/{TOTAL} solver trajectories written", done
    elif "Enhancement done" in last:
        return "solver_start", f"0/{TOTAL} (solver launching)", 0
    elif "Running" in last and "enhancer" in last:
        # Enhancement in progress — count enhanced dataset lines written so far
        ds = run_dir / "solver_enhanced_dataset.jsonl"
        done = sum(1 for _ in open(ds) if _.strip()) if ds.exists() else 0
        return "enhancing", f"{done}/{TOTAL} issues enhanced", done
    elif "solver_baseline_eval" in last and "resolved" in last:
        return "baseline_eval_done", f"baseline done → starting enhancer", 0
    elif "Evaluating" in last or "solver_baseline_eval" in last:
        done = _count_reports(run_dir / "solver_baseline_eval")
        return "baseline_eval", f"baseline eval {done}/{TOTAL} reports", done
    else:
        return "starting", "initializing…", 0


def render_once():
    now = time.strftime("%H:%M:%S")
    print(f"\n{'─'*72}")
    print(f"  Enhancer Progress Monitor — {now}")
    print(f"{'─'*72}")
    print(f"  {'ENHANCER':<18} {'STAGE':<20} PROGRESS")
    print(f"  {'─'*18} {'─'*20} {'─'*28}")

    all_done = True
    for e in ENHANCERS:
        run_dir = ROOT / f"runs/pouya_enhanced_{e}_{BASE_TS}"
        stage, detail, count = _get_status(run_dir, e)
        bar_filled = int((count / TOTAL) * 20) if isinstance(count, int) and stage not in ("DONE",) else 20
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        done_marker = "✓" if stage == "DONE" else " "
        print(f"  {done_marker} {e:<17} {stage:<20} {detail}")
        if stage != "DONE":
            all_done = False

    # Also show the already-completed llm_append_analysis run
    print(f"\n  {'─'*18} {'─'*20} {'─'*28}")
    base_run = ROOT / "runs/pouya_solver20_20260505_063614"
    if (base_run / "summary.json").exists():
        s = json.loads((base_run / "summary.json").read_text())
        print(f"  ✓ {'llm_append_analysis':<17} {'DONE':<20} "
              f"baseline={s['baseline_resolved']}/{TOTAL}  enhanced={s['enhanced_resolved']}/{TOTAL}")
    print(f"{'─'*72}\n")
    return all_done


def main():
    once = "--once" in sys.argv
    if once:
        render_once()
        return

    print("Watching 5 enhancer runs (Ctrl+C to stop, refreshes every 30s)…")
    try:
        while True:
            done = render_once()
            if done:
                print("All runs complete!")
                break
            time.sleep(30)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
