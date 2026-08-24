#!/usr/bin/env python3
"""
Live progress monitor for Node1 2-Agent Pilot runs.
Shows per-pair status: Stage 4 enhancement, Stage 5 baseline/enhanced solving, Stage 6 report.

Usage:
    watch -n 60 -c bench_env/bin/python scripts/monitor_node1_2agent_pilot.py
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[1]
RUNS    = ROOT / "runs"
TOTAL   = 510

PAIRS = [
    {"name": "openhands", "run_dir": RUNS / "node1_2agent_pilot_openhands_20260610"},
    {"name": "swe_agent",  "run_dir": RUNS / "node1_2agent_pilot_swe_agent_20260610"},
]

# ANSI colors
RESET  = "\033[0m";  BOLD  = "\033[1m";  DIM   = "\033[2m"
GREEN  = "\033[92m"; YELLOW= "\033[93m"; RED   = "\033[91m"
CYAN   = "\033[96m"; BLUE  = "\033[94m"; WHITE = "\033[97m"
MAGENTA= "\033[95m"


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _rj(path: Path) -> dict:
    try: return json.loads(path.read_text())
    except Exception: return {}


def _preds_count(preds_path: Path) -> int:
    try: return len(json.loads(preds_path.read_text()))
    except Exception: return 0


def _is_active(name: str) -> bool:
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", f"run_node1_2agent_pilot_{name}"], text=True
        ).strip()
        return bool(out)
    except subprocess.CalledProcessError:
        return False


def _bar(done: int, total: int, width: int = 18) -> str:
    if total == 0: return "░" * width
    f = int(width * done / total)
    return "█" * f + "░" * (width - f)


def _pct(done: int, total: int) -> str:
    if total == 0: return "  0.0%"
    return f"{100 * done / total:5.1f}%"


def gather(pair: dict) -> dict:
    name    = pair["name"]
    run_dir = pair["run_dir"]

    if not run_dir.exists():
        return {"name": name, "status": "pending"}

    done_stage4    = (run_dir / ".done_stage4").exists()
    done_s5_bl_sol = (run_dir / ".done_stage5_baseline_solver").exists()
    done_s5_bl_ev  = (run_dir / ".done_stage5_baseline_eval").exists()
    done_s5_en_sol = (run_dir / ".done_stage5_enhanced_solver").exists()
    done_s5_en_ev  = (run_dir / ".done_stage5_enhanced_eval").exists()
    report_exists  = (run_dir / "stage6_report" / "REPORT.md").exists()
    summary_path   = run_dir / "stage6_report" / "summary.json"

    s4_summary = _rj(run_dir / "stage4_enhanced" / "stage4_summary.json")
    s4_enhanced = s4_summary.get("enhanced_count", 0)
    s4_total    = s4_summary.get("total_instances", TOTAL)
    s4_failed   = s4_summary.get("failure_count", 0)
    s4_done     = s4_total if done_stage4 else 0

    # If not done yet, count from progress log
    if not done_stage4:
        prog_log = run_dir / "progress.log"
        if prog_log.exists():
            lines = prog_log.read_text().splitlines()
            for line in reversed(lines):
                import re
                m = re.search(r"\[(\d+)/(\d+)\]", line)
                if m:
                    s4_done = int(m.group(1))
                    s4_total = int(m.group(2))
                    break

    # Stage 5 solver progress (count preds.json entries)
    bl_preds  = run_dir / "stage5_solver_eval/solver_baseline/preds.json"
    en_preds  = run_dir / "stage5_solver_eval/solver_enhanced/preds.json"
    bl_solved_count = _preds_count(bl_preds)
    en_solved_count = _preds_count(en_preds)

    # Stage 5 eval results
    bl_eval = _rj(run_dir / "stage5_solver_eval/eval_baseline/eval_results.json")
    en_eval = _rj(run_dir / "stage5_solver_eval/eval_enhanced/eval_results.json")
    bl_resolved = bl_eval.get("resolved", 0) if bl_eval else 0
    en_resolved = en_eval.get("resolved", 0) if en_eval else 0
    eval_n      = bl_eval.get("total", 0) if bl_eval else 0

    # Summary (Stage 6 done)
    summary = _rj(summary_path)
    if summary:
        bl_resolved = summary.get("baseline", {}).get("resolved", bl_resolved)
        en_resolved = summary.get("enhanced", {}).get("resolved", en_resolved)
        eval_n      = summary.get("baseline", {}).get("total", eval_n)

    is_active = _is_active(name)

    # Determine status string
    if report_exists or summary:
        status = "Stage 6 done"
    elif done_s5_en_ev:
        status = "Stage 6 pending"
    elif done_s5_en_sol:
        status = "S5 enhanced eval running" if is_active else "S5 enhanced eval done?"
    elif done_s5_bl_ev:
        status = "S5 enhanced solving" if is_active else "S5 enhanced solver stalled?"
    elif done_s5_bl_sol:
        status = "S5 baseline eval running" if is_active else "S5 baseline eval stalled?"
    elif done_stage4:
        status = "S5 baseline solving" if is_active else "S5 baseline solver stalled?"
    elif is_active:
        status = "Stage 4 running"
    elif s4_done > 0:
        status = "Stage 4 stalled?"
    else:
        status = "pending"

    # Last progress log timestamp
    last = ""
    prog_log = run_dir / "progress.log"
    if prog_log.exists():
        lines = prog_log.read_text().splitlines()
        for line in reversed(lines):
            if line.strip():
                last = line[:19]
                break

    return {
        "name": name, "status": status, "is_active": is_active,
        "s4_done": s4_done, "s4_total": s4_total, "s4_enhanced": s4_enhanced,
        "s4_failed": s4_failed, "done_stage4": done_stage4,
        "bl_preds": bl_solved_count, "en_preds": en_solved_count,
        "bl_resolved": bl_resolved, "en_resolved": en_resolved, "eval_n": eval_n,
        "last": last,
    }


def sc(status: str) -> str:
    s = status.lower()
    if "done" in s or "6" in s: return GREEN
    if "running" in s or "solving" in s or "eval" in s: return CYAN
    if "stalled" in s: return RED
    if "pending" in s: return DIM
    return YELLOW


def print_dashboard(rows: list[dict]) -> None:
    W = 132
    print(f"{BOLD}{CYAN}{'═' * W}{RESET}")
    print(f"{BOLD}{CYAN}  NODE1 2-AGENT PILOT PROGRESS MONITOR{RESET}")
    print(f"{DIM}  Pairs: openhands+openhands, swe_agent+swe_agent   "
          f"Enhancer: 4 threads   Solver: 4 workers   "
          f"LLM: gpt-oss:120b via Ollama:11435   "
          f"Dataset: {TOTAL} instances   Updated: {now_utc()}{RESET}")
    print(f"{BOLD}{CYAN}{'═' * W}{RESET}")

    # Header
    print(f"{BOLD}{WHITE}"
          f"  {'PAIR':<18}  {'STATUS':<28}  "
          f"{'── STAGE 4 ──':^30}  "
          f"{'── STAGE 5 SOLVING ──':^24}  "
          f"{'── STAGE 5/6 EVAL ──':^22}  "
          f"{'LAST LOG':<19}"
          f"{RESET}")
    print(f"{DIM}"
          f"  {'':18}  {'':28}  "
          f"{'Done':>6}/{'Tot':<4} {'Bar':<18} {'%':>6}  "
          f"{'Bl preds':>9} {'En preds':>9}  "
          f"{'Bl res':>7} {'En res':>7} {'Δ':>5}  "
          f"{'':19}"
          f"{RESET}")
    print(f"  {'─' * (W - 2)}")

    for r in rows:
        name   = r["name"]
        status = r.get("status", "pending")
        active = f" {CYAN}●{RESET}" if r.get("is_active") else "  "

        if status == "pending":
            print(f"{active}{BOLD}{name:<18}{RESET}  "
                  f"{DIM}{status:<28}{RESET}  "
                  f"{'—':>6} {'':4} {'':18} {'':>6}  "
                  f"{'—':>9} {'—':>9}  "
                  f"{'—':>7} {'—':>7} {'—':>5}  "
                  f"{DIM}{'not started':<19}{RESET}")
            continue

        s4d   = r["s4_done"]
        s4t   = r["s4_total"]
        s4e   = r["s4_enhanced"]
        done4 = r["done_stage4"]

        bar   = _bar(s4d, s4t)
        pct   = _pct(s4d, s4t)
        bc    = GREEN if done4 else YELLOW
        bar_s = f"{bc}{bar}{RESET}"

        bl_p  = r["bl_preds"]
        en_p  = r["en_preds"]
        bl_r  = r["bl_resolved"]
        en_r  = r["en_resolved"]
        ev_n  = r["eval_n"]
        delta = en_r - bl_r

        bl_p_s = f"{bl_p:>9}" if bl_p else f"{'—':>9}"
        en_p_s = f"{en_p:>9}" if en_p else f"{'—':>9}"
        bl_r_s = f"{bl_r:>5}/{ev_n}" if ev_n else f"{'—':>7}"
        en_r_s = f"{en_r:>5}/{ev_n}" if ev_n else f"{'—':>7}"
        d_s    = (f"{GREEN}+{delta}{RESET}" if delta > 0
                  else (f"{RED}{delta}{RESET}" if delta < 0 else f"{DIM}0{RESET}"))

        last = r.get("last", "")[-19:] if r.get("last") else "—"

        print(f"{active}{BOLD}{name:<18}{RESET}  "
              f"{sc(status)}{status:<28}{RESET}  "
              f"{bc}{s4d:>4}{RESET}/{s4t:<4} {bar_s} {bc}{pct}{RESET}  "
              f"{bl_p_s} {en_p_s}  "
              f"{bl_r_s} {en_r_s} {d_s:>5}  "
              f"{DIM}{last:<19}{RESET}")

    print(f"  {'─' * (W - 2)}")

    # Sub-stage legend
    active_c = sum(1 for r in rows if r.get("is_active"))
    total_s4 = sum(r.get("s4_done", 0) for r in rows if r.get("status") != "pending")
    total_t  = sum(r.get("s4_total", TOTAL) for r in rows if r.get("status") != "pending") or TOTAL * len(rows)
    print(f"  {BOLD}{'TOTALS':<18}{RESET}  "
          f"{'Active: ' + str(active_c) + ' pair(s)':<28}  "
          f"{BOLD}{total_s4:>4}{RESET}/{total_t:<4} "
          f"{YELLOW}{_bar(total_s4, total_t)}{RESET} "
          f"{BOLD}{_pct(total_s4, total_t)}{RESET}")
    print(f"{BOLD}{CYAN}{'═' * W}{RESET}")
    print(f"{DIM}  ● = active   Stage 5 columns: preds written so far (solving) / resolved (eval){RESET}")
    print(f"{DIM}  Δ = enhanced_resolved − baseline_resolved   Stage 4 bar = enhancement progress{RESET}")
    print(f"{DIM}  Sub-stages: S4→S5 baseline solve→S5 baseline eval→S5 enhanced solve→S5 enhanced eval→S6{RESET}")


def main() -> None:
    rows = [gather(p) for p in PAIRS]
    print_dashboard(rows)


if __name__ == "__main__":
    main()
