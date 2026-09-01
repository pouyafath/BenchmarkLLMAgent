#!/usr/bin/env python3
"""
Re-score stored solver runs under the executed FAIL_TO_PASS criterion.

The paper's headline metric is P2P-only (no regression), which credits a patch that never
applied: the repository stays untouched, P2P stays green, the instance scores as solved.
The reason was that the shipped F2P labels came from parsing the test patch's diff rather
than from running anything -- they claimed 225 of 279 instances, while execution finds a
real fail->pass test in only 85, and the two sets agree on 45.

data/stage6_all279_f2p_derived.json now holds executed labels (see derive_f2p.py). This
rescores from the per-test status.json the harness already wrote during scoring, so it
costs no containers. An instance counts as strictly resolved when every executed F2P test
passes and every executed P2P test passes.

Instances the harness never evaluated (empty or malformed submissions) have no status.json
and are unresolved under any criterion, which is the correct reading.
"""
import json, sys, collections
from pathlib import Path
from scipy.stats import binomtest

ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
LAB  = json.load(open(ROOT/"data/stage6_all279_f2p_derived.json"))
WORK = ROOT/"runs/stage6_run4_appendonly/work"
CELLS= json.load(open(ROOT/"runs/stage6_run4_appendonly/result.json"))

def strict(arm_tag: str, iid: str) -> bool | None:
    """True/False if evaluated; None if never run (no artifact)."""
    lab = LAB.get(iid)
    if not lab or not lab["FAIL_TO_PASS"]:
        return None                      # no executed F2P test -> not strictly gradeable
    hits = list((WORK/arm_tag).glob(f"*/{iid}/status.json"))
    if not hits:
        return False                     # submitted nothing / not evaluated -> unresolved
    st = json.load(open(hits[0]))
    f2p_ok = all(st.get(t) == "pass" for t in lab["FAIL_TO_PASS"])
    p2p_ok = all(st.get(t, "pass") == "pass" for t in lab["PASS_TO_PASS"])
    return f2p_ok and p2p_ok

SOLVERS   = ["openhands", "swe_agent", "aider"]
ENHANCERS = ["openhands", "trae", "mini_swe_agent"]
gradeable = None
print(f"{'cell':38s} {'n*':>3} {'base':>5} {'enh':>4} {'Δ':>4} {'resc':>5} {'brk':>4}")
print("-"*70)
rows=[]
for e in ENHANCERS:
    for s in SOLVERS:
        key=f"enh_{e}__solver_{s}"
        ids=[i for i in CELLS[key]["resolved_baseline"] if LAB.get(i,{}).get("FAIL_TO_PASS")]
        if gradeable is None: gradeable=len(ids)
        b=e_=r=k=0
        for i in ids:
            bb=strict(f"A__baseline__{s}", i)
            if bb is None: bb=strict(f"B__baseline__{s}", i)
            ee=strict(f"A__enh_{e}__{s}", i)
            if ee is None: ee=strict(f"B__enh_{e}__{s}", i)
            bb, ee = bool(bb), bool(ee)
            b+=bb; e_+=ee; r+= (not bb and ee); k+= (bb and not ee)
        print(f"{key:38s} {len(ids):3d} {b:5d} {e_:4d} {e_-b:+4d} {r:5d} {k:4d}")
        rows.append((key,len(ids),b,e_,r,k))

print(f"\nn* = run-4 instances carrying >=1 executed F2P test ({gradeable} of 80)")
tb=sum(x[2] for x in rows); te=sum(x[3] for x in rows)
tr=sum(x[4] for x in rows); tk=sum(x[5] for x in rows)
print(f"pooled: {tb} -> {te}  (Δ{te-tb:+d})   rescues {tr}, breakages {tk}")
if tr+tk: print(f"pooled McNemar p = {binomtest(tr,tr+tk,0.5).pvalue:.3f}")
