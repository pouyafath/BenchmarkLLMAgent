#!/usr/bin/env python3
"""
Live progress monitor for node1_all494 Stage 4-6 runs.
Auto-refreshes every 60 seconds.

Usage:
    watch -n 60 bench_env/bin/python scripts/monitor_node1_all494.py
  or for color + clear:
    watch -n 60 -c bench_env/bin/python scripts/monitor_node1_all494.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "runs"

ENHANCERS = [
    "openhands",
    "swe_agent",
    "aider",
    "mini_swe_agent",
    "live_swe_agent",
    "trae",
    "cl_enhanced_gemma3",
    "simple_enhancer",
]

SOLVER = "mini_swe_agent"
SOLVER_MODEL = "gpt-oss:120b"
TOTAL_EXPECTED = 510

# ANSI colors
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"
WHITE  = "\033[97m"


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _find_active_pids(enhancer: str) -> list[int]:
    """Find running python processes for this enhancer's workflow script."""
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", f"run_node1_all494_{enhancer}"],
            text=True,
        ).strip()
        return [int(p) for p in out.splitlines() if p.strip()]
    except subprocess.CalledProcessError:
        return []


def _parse_stage4_progress(log: list[str], total: int) -> tuple[int, int, int]:
    """Return (done, enhanced, failed) from Stage 4 log lines."""
    done = enhanced = failed = 0
    pattern = re.compile(r"\[(\d+)/\d+\]")
    for line in log:
        m = pattern.search(line)
        if m:
            done = int(m.group(1))
        if "enhanced" in line.lower():
            enhanced += 1
        if "failed" in line.lower() or "error" in line.lower() or "unchanged" in line.lower():
            failed += 1
    return done, enhanced, failed


def _parse_stage5_progress(log: list[str]) -> tuple[int, int]:
    """Return (solved_baseline, solved_enhanced) from Stage 5/6 log lines."""
    baseline = enhanced = 0
    for line in log:
        if "baseline" in line.lower() and "/" in line:
            m = re.search(r"baseline.*?(\d+)\s*/\s*(\d+)", line, re.IGNORECASE)
            if m:
                baseline = int(m.group(1))
        if "enhanced" in line.lower() and "/" in line:
            m = re.search(r"enhanced.*?(\d+)\s*/\s*(\d+)", line, re.IGNORECASE)
            if m:
                enhanced = int(m.group(1))
    return baseline, enhanced


def _bar(done: int, total: int, width: int = 20) -> str:
    if total == 0:
        return " " * width
    filled = int(width * done / total)
    bar = "█" * filled + "░" * (width - filled)
    return bar


def _pct(done: int, total: int) -> str:
    if total == 0:
        return "  0.0%"
    return f"{100 * done / total:5.1f}%"


def gather_run_info(enhancer: str) -> dict:
    """Gather all available info for one enhancer run."""
    # Find the run directory (may or may not exist yet)
    pattern = f"node1_all494_{enhancer}_"
    candidates = [d for d in RUNS_DIR.iterdir() if d.is_dir() and d.name.startswith(pattern)]
    if not candidates:
        return {"enhancer": enhancer, "status": "pending"}

    run_dir = sorted(candidates)[-1]  # take latest if multiple

    progress_path = run_dir / "progress.json"
    checkpoint_path = run_dir / "stage4_checkpoint.json"
    summary_path = run_dir / "summary.json"
    report_path = run_dir / "REPORT.md"

    progress = _read_json(progress_path)
    checkpoint = _read_json(checkpoint_path)
    summary = _read_json(summary_path)

    active_pids = _find_active_pids(enhancer)
    is_active = len(active_pids) > 0

    log = progress.get("log", [])
    total = progress.get("total_instances", TOTAL_EXPECTED)
    last_update = progress.get("last_update", "")

    # Determine current stage
    if summary:
        stage = "Stage 6 done"
    elif report_path.exists():
        stage = "Stage 6 done"
    elif checkpoint.get("stage4_done"):
        if is_active:
            stage = "Stage 5/6 running"
        else:
            stage = "Stage 4 done (awaiting S5)"
    elif is_active:
        stage = "Stage 4 running"
    elif log:
        stage = "Stage 4 stalled?"
    else:
        stage = "pending"

    # Stage 4 progress
    s4_done, s4_enhanced, s4_failed = _parse_stage4_progress(log, total)
    s4_total = checkpoint.get("enhancement_summary", {}).get("total_instances", total) if checkpoint else total
    if checkpoint.get("stage4_done"):
        s4_done = checkpoint.get("enhancement_summary", {}).get("total_instances", s4_done)
        s4_enhanced = checkpoint.get("enhancement_summary", {}).get("truly_enhanced", s4_enhanced)
        s4_failed = checkpoint.get("enhancement_summary", {}).get("failures", s4_failed)

    # Stage 5/6 results
    baseline_solved = enhanced_solved = eval_total = 0
    if summary:
        baseline_solved = summary.get("baseline", {}).get("resolved", 0)
        enhanced_solved = summary.get("enhanced", {}).get("resolved", 0)
        eval_total = summary.get("baseline", {}).get("total", 0)
    else:
        b, e = _parse_stage5_progress(log)
        baseline_solved, enhanced_solved = b, e

    return {
        "enhancer": enhancer,
        "status": stage,
        "run_dir": run_dir.name,
        "total": total,
        "s4_done": s4_done,
        "s4_enhanced": s4_enhanced,
        "s4_failed": s4_failed,
        "baseline_solved": baseline_solved,
        "enhanced_solved": enhanced_solved,
        "eval_total": eval_total,
        "last_update": last_update,
        "is_active": is_active,
        "pids": active_pids,
    }


def status_color(status: str) -> str:
    if "done" in status.lower():
        return GREEN
    if "running" in status.lower():
        return CYAN
    if "stalled" in status.lower():
        return RED
    if "awaiting" in status.lower():
        return YELLOW
    return DIM  # pending


def print_table(runs: list[dict]) -> None:
    print(f"{BOLD}{CYAN}{'═' * 120}{RESET}")
    print(f"{BOLD}{CYAN}  NODE1 ALL-494 STAGE 4-6 PROGRESS MONITOR{RESET}")
    print(f"{DIM}  Solver: {SOLVER} via {SOLVER_MODEL} (Ollama:11435, NUM_PARALLEL=4)   "
          f"Stage4: 4 threads/enhancer   Stage5: SOLVER_WORKERS=4   "
          f"Dataset: 510 instances   Updated: {now_utc()}{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 120}{RESET}")

    # Header
    hdr = (
        f"  {'ENHANCER':<20}  {'STATUS':<22}  "
        f"{'STAGE 4':^28}  "
        f"{'STAGE 5/6':^24}  "
        f"{'LAST UPDATE':<22}"
    )
    print(f"{BOLD}{WHITE}{hdr}{RESET}")
    sub = (
        f"  {'':20}  {'':22}  "
        f"{'Done':>6} {'Bar':<20} {'%':>6}  "
        f"{'Base':>5} {'Enh':>5} {'Δ':>5} {'N':>5}  "
        f"{'':22}"
    )
    print(f"{DIM}{sub}{RESET}")
    print(f"  {'─' * 116}")

    total_s4_done = total_s4_total = 0
    active_count = 0

    for r in runs:
        enhancer = r["enhancer"]
        status = r.get("status", "pending")
        sc = status_color(status)
        active_marker = f" {CYAN}●{RESET}" if r.get("is_active") else "  "

        if status == "pending":
            row = (
                f"{active_marker}{BOLD}{enhancer:<20}{RESET}  "
                f"{DIM}{status:<22}{RESET}  "
                f"{'—':>6} {'':20} {'':>6}  "
                f"{'—':>5} {'—':>5} {'—':>5} {'—':>5}  "
                f"{DIM}{'not started':<22}{RESET}"
            )
            print(row)
            continue

        total = r.get("total", TOTAL_EXPECTED)
        s4_done = r.get("s4_done", 0)
        s4_enhanced = r.get("s4_enhanced", 0)

        bar = _bar(s4_done, total)
        pct = _pct(s4_done, total)
        bar_colored = f"{GREEN}{bar}{RESET}" if s4_done == total else f"{YELLOW}{bar}{RESET}"

        baseline = r.get("baseline_solved", 0)
        enhanced_s = r.get("enhanced_solved", 0)
        eval_n = r.get("eval_total", 0)
        delta = enhanced_s - baseline
        delta_str = f"{GREEN}+{delta}{RESET}" if delta > 0 else (f"{RED}{delta}{RESET}" if delta < 0 else f"{DIM}0{RESET}")

        eval_base_str = f"{baseline:>3}/{eval_n}" if eval_n else f"{'—':>5}"
        eval_enh_str  = f"{enhanced_s:>3}/{eval_n}" if eval_n else f"{'—':>5}"

        last = r.get("last_update", "")[-19:] if r.get("last_update") else "—"

        row = (
            f"{active_marker}{BOLD}{enhancer:<20}{RESET}  "
            f"{sc}{status:<22}{RESET}  "
            f"{GREEN if s4_done == total else YELLOW}{s4_done:>4}{RESET}/{total:<4} "
            f"{bar_colored} {GREEN if s4_done == total else YELLOW}{pct}{RESET}  "
            f"{eval_base_str:>8} {eval_enh_str:>8} {delta_str:>5} {eval_n if eval_n else '—':>5}  "
            f"{DIM}{last:<22}{RESET}"
        )
        print(row)

        total_s4_done += s4_done
        total_s4_total += total
        if r.get("is_active"):
            active_count += 1

    print(f"  {'─' * 116}")

    # Totals row
    total_pct = _pct(total_s4_done, total_s4_total) if total_s4_total else "  0.0%"
    total_bar = _bar(total_s4_done, total_s4_total)
    print(
        f"  {BOLD}{'TOTAL (Stage 4)':<20}{RESET}  "
        f"{'Active: ' + str(active_count) + ' agent(s)':<22}  "
        f"{BOLD}{total_s4_done:>4}{RESET}/{total_s4_total:<4} "
        f"{YELLOW}{total_bar}{RESET} {BOLD}{total_pct}{RESET}"
    )

    print(f"{BOLD}{CYAN}{'═' * 120}{RESET}")
    print(f"{DIM}  ● = active process running   Stage 5/6 columns show resolved/total counts{RESET}")
    print(f"{DIM}  Δ = enhanced_solved − baseline_solved (pp improvement){RESET}")


def main() -> None:
    runs = [gather_run_info(e) for e in ENHANCERS]
    print_table(runs)


if __name__ == "__main__":
    main()
