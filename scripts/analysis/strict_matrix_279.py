#!/usr/bin/env python3
"""
Rescore the main enhancer x solver matrix under the executed FAIL_TO_PASS criterion.

The paper's Table 1 is P2P-resolved: no regression on the pass-to-pass suite. That
criterion credits a patch that never applied, because an untouched repository keeps P2P
green. It was adopted because the shipped F2P labels were parsed from the test patch's
diff rather than executed -- they claim a fail->pass test for 225 of 279 instances while
execution finds one in 85, agreeing on 45.

data/stage6_all279_f2p_derived.json now carries executed labels. This rescores from the
per-test status.json the harness wrote during the original scoring passes, so it needs no
containers. Strictly resolved = every executed F2P test passes and every executed P2P test
passes.

Coverage is partial by construction. The first 100-issue tranche's scoring artifacts were
lost (recovered only as booleans, not per-test), so only the tranches that still hold
status.json can be rescored. Cells report their own n rather than assuming 279.
"""
import json, collections
from pathlib import Path
from scipy.stats import binomtest

ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
LAB  = json.load(open(ROOT/"data/stage6_all279_f2p_derived.json"))
ROOTS = [ROOT/"runs/stage6_new100_scores/matrix200_extra100_20260630_174724",
         ROOT/"runs/stage6_new182_scores/matrix382_extra182_20260706_134335"]

def status(arm: str, iid: str):
    for r in ROOTS:
        for h in (r/arm).glob(f"*/{iid}/status.json"):
            try: return json.load(open(h))
            except Exception: pass
    return None

def strict(arm: str, iid: str) -> bool:
    lab = LAB.get(iid)
    st = status(arm, iid)
    if st is None:
        return False                     # nothing evaluated -> unresolved
    return (all(st.get(t) == "pass" for t in lab["FAIL_TO_PASS"])
            and all(st.get(t, "pass") == "pass" for t in lab["PASS_TO_PASS"]))

# instances that are strictly gradeable AND have artifacts somewhere
gradeable = [i for i, v in LAB.items() if v["FAIL_TO_PASS"]]
SOLVERS   = ["openhands", "aider", "swe_agent"]
ENHANCERS = ["aider", "openhands", "swe_agent"]

print(f"executed-F2P gradeable instances overall: {len(gradeable)}\n")
print(f"{'cell':40s} {'n':>4} {'base':>5} {'enh':>4} {'Δ':>4} {'resc':>5} {'brk':>4} {'McNemar':>8}")
print("-"*82)
rows=[]
for s in SOLVERS:
    for e in ENHANCERS:
        barm, earm = f"baseline__solver_{s}", f"enh_{e}__solver_{s}"
        ids = [i for i in gradeable
               if status(barm, i) is not None or status(earm, i) is not None]
        if not ids:
            continue
        b = e_ = r = k = 0
        for i in ids:
            bb, ee = strict(barm, i), strict(earm, i)
            b += bb; e_ += ee; r += (not bb and ee); k += (bb and not ee)
        p = binomtest(r, r+k, 0.5).pvalue if r+k else 1.0
        print(f"{'enh:'+e+' -> sol:'+s:40s} {len(ids):4d} {b:5d} {e_:4d} {e_-b:+4d} "
              f"{r:5d} {k:4d} {p:8.3f}")
        rows.append((e, s, len(ids), b, e_, r, k, p))

print("-"*82)
tb=sum(x[3] for x in rows); te=sum(x[4] for x in rows)
tr=sum(x[5] for x in rows); tk=sum(x[6] for x in rows)
print(f"{'POOLED':40s} {sum(x[2] for x in rows):4d} {tb:5d} {te:4d} {te-tb:+4d} {tr:5d} {tk:4d} "
      f"{binomtest(tr,tr+tk,0.5).pvalue if tr+tk else 1.0:8.3f}")
sig=[x for x in rows if x[7]<0.05]
print(f"\ncells with McNemar p<0.05: {len(sig)}/{len(rows)}  {[(x[0],x[1]) for x in sig]}")
json.dump([{"enhancer":x[0],"solver":x[1],"n":x[2],"baseline":x[3],"enh":x[4],
            "rescues":x[5],"breakages":x[6],"mcnemar_p":x[7]} for x in rows],
          open(ROOT/"runs/strict_matrix_279.json","w"), indent=1)
print(f"Wrote {ROOT/'runs/strict_matrix_279.json'}")
