#!/usr/bin/env python3
"""Live status dashboard for the smoke2 run. Run via: watch -n 5 python3 scripts/ops/smoke_status.py"""
import json, re, time, os
from pathlib import Path

import sys, glob

# Auto-detect the latest node1_full383 run dir + its log, or accept a run dir as argv[1].
if len(sys.argv) > 1:
    RD = Path(sys.argv[1])
else:
    runs = sorted(glob.glob("/home/22pf2/BenchmarkLLMAgent/runs/node1_full383_qwen3_*"))
    RD = Path(runs[-1]) if runs else Path("/nonexistent")
# Newest matching /tmp log (batch60 or smoke), else the run dir's own test.log
_logs = sorted(glob.glob("/tmp/node1_batch60_*.log") + glob.glob("/tmp/node1_smoke2_*.log"),
               key=lambda p: Path(p).stat().st_mtime if Path(p).exists() else 0)
LOG = Path(_logs[-1]) if _logs else (RD / "test.log")

text = LOG.read_text() if LOG.exists() else ""
now  = time.time()

def patch_count(preds):
    return sum(1 for v in preds.values() if (v.get("model_patch") or "").strip())

def running_instances(work_dir, done_set):
    if not work_dir.exists():
        return []
    result = []
    for d in sorted(work_dir.iterdir()):
        if not d.is_dir() or d.name in done_set:
            continue
        log_f = d / "openhands.log"
        if log_f.exists():
            age = int(now - log_f.stat().st_mtime)
            result.append(f"{d.name.split('__')[-1][:22]}({age}s)")
    return result

print(f"{'='*60}")
print(f"  Smoke-2 Dashboard  —  {time.strftime('%H:%M:%S UTC', time.gmtime())}")
print(f"{'='*60}")

# ── Stage 4 ──────────────────────────────────────────────────
s4_done = re.search(r"Stage 4 DONE: (\d+)/(\d+) enhanced, (\d+) fallback", text)
s4_prog = re.findall(r"\[(\d+)/(\d+)\] \S+: (?:ENHANCED|FALLBACK)", text)
if s4_done:
    tot = int(s4_done.group(1)) + int(s4_done.group(3))
    print(f"Stage 4   : {tot}/{tot} DONE  ({s4_done.group(1)} enhanced, {s4_done.group(3)} fallback)  ✓")
elif s4_prog:
    cur, tot = s4_prog[-1]
    print(f"Stage 4   : {cur}/{tot} done  |  {int(tot)-int(cur)} in progress")
else:
    print("Stage 4   : not started yet")

# ── Stage 5 baseline ─────────────────────────────────────────
pbase = RD / "stage5_solver_eval/solver_baseline/preds.json"
wbase = RD / "stage5_solver_eval/solver_baseline/work"
if pbase.exists():
    preds = json.loads(pbase.read_text())
    done  = len(preds)
    patches = patch_count(preds)
    m = re.search(r"SOLVER \(baseline\) — (\d+) inst", text)
    tot = m.group(1) if m else "?"
    if "Solver (baseline) DONE" in text:
        print(f"Stage 5B  : {done}/{done} DONE  ({patches} patches)  ✓")
    else:
        running = running_instances(wbase, set(preds.keys()))
        print(f"Stage 5B  : {done}/{tot} done  ({patches} patches)  |  {len(running)} running")
        for r in running:
            print(f"            • {r}")
elif "STAGE 5" in text:
    print("Stage 5B  : starting...")
else:
    print("Stage 5B  : waiting for Stage 4")

# ── Stage 5 enhanced ─────────────────────────────────────────
penh = RD / "stage5_solver_eval/solver_enhanced/preds.json"
wenh = RD / "stage5_solver_eval/solver_enhanced/work"
if penh.exists():
    preds = json.loads(penh.read_text())
    done  = len(preds)
    patches = patch_count(preds)
    m = re.search(r"SOLVER \(enhanced\) — (\d+) inst", text)
    tot = m.group(1) if m else "?"
    if "Solver (enhanced) DONE" in text:
        print(f"Stage 5E  : {done}/{done} DONE  ({patches} patches)  ✓")
    else:
        running = running_instances(wenh, set(preds.keys()))
        print(f"Stage 5E  : {done}/{tot} done  ({patches} patches)  |  {len(running)} running")
        for r in running:
            print(f"            • {r}")
elif "Solver (baseline) DONE" in text:
    print("Stage 5E  : starting...")
else:
    print("Stage 5E  : waiting for Stage 5B")

# ── result.json ──────────────────────────────────────────────
res = RD / "result.json"
if res.exists():
    r = json.loads(res.read_text())
    print(f"result.json: READY ✓  baseline={r.get('baseline_nonempty','?')}/{r.get('n_instances','?')}  enhanced={r.get('enhanced_nonempty','?')}/{r.get('n_instances','?')}")
else:
    print("result.json: not yet")

# ── Resources ────────────────────────────────────────────────
st = os.statvfs("/")
disk_free = st.f_bavail * st.f_frsize / 1e9
print(f"Disk free : {disk_free:.0f} GB")
print(f"{'='*60}")
