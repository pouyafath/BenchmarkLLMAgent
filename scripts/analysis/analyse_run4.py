#!/usr/bin/env python3
"""
Run-4 (append-only) analysis: paired significance plus the resample null.

Two questions, and the second is the one that matters. McNemar asks whether the enhanced
arm differs from the baseline arm. The resample null asks whether it differs from simply
running the solver a second time -- the standing comparison in this project, since
enhancement costs a full agent run. A cell can post a healthy +6 and still be exactly what
re-rolling the dice predicts.

Resample rates measured earlier on this pipeline: P(fix|failed)=0.199, P(break|passed)=0.408.
"""
import json, sys
from scipy.stats import binomtest

P_FIX, P_BREAK = 0.199, 0.408
cells = json.load(open("runs/stage6_run4_appendonly/result.json"))

print(f"{'cell':38s} {'base':>4} {'enh':>4} {'Δ':>4} {'McNemar':>9}   "
      f"{'resc':>5} {'exp':>5} {'p':>7}   {'brk':>4} {'exp':>5} {'p':>7}")
print("-"*108)
rows=[]
for name, c in cells.items():
    b, e = c["baseline"], c["enh"]
    resc, brk = c["rescues"], c["breakages"]
    n_fail, n_pass = c["n"] - b, b
    mc = binomtest(resc, resc+brk, 0.5).pvalue if resc+brk else 1.0
    # one-sided: more rescues than a resample would give / fewer breakages than it would
    p_r = binomtest(resc, n_fail, P_FIX, alternative="greater").pvalue if n_fail else 1.0
    p_b = binomtest(brk, n_pass, P_BREAK, alternative="less").pvalue if n_pass else 1.0
    er, eb = P_FIX*n_fail, P_BREAK*n_pass
    print(f"{name:38s} {b:4d} {e:4d} {e-b:+4d} {mc:9.3f}   "
          f"{resc:5d} {er:5.1f} {p_r:7.3f}   {brk:4d} {eb:5.1f} {p_b:7.3f}")
    rows.append((name, e-b, mc, resc, er, p_r, brk, eb, p_b))

print("\nMcNemar = paired test vs baseline (two-sided).")
print("resc p  = one-sided, observed rescues vs a resample's 0.199 x (baseline failures).")
print("brk  p  = one-sided, observed breakages vs a resample's 0.408 x (baseline solves).")

sig_m = [r for r in rows if r[2] < 0.05]
sig_r = [r for r in rows if r[5] < 0.05]
sig_b = [r for r in rows if r[8] < 0.05]
print(f"\ncells significant on McNemar        : {len(sig_m)}/9  {[r[0] for r in sig_m]}")
print(f"cells rescuing ABOVE the resample   : {len(sig_r)}/9  {[r[0] for r in sig_r]}")
print(f"cells breaking BELOW the resample   : {len(sig_b)}/9  {[r[0] for r in sig_b]}")

tot_r = sum(r[3] for r in rows); tot_er = sum(r[4] for r in rows)
tot_b = sum(r[6] for r in rows); tot_eb = sum(r[7] for r in rows)
print(f"\npooled rescues   {tot_r:3d} vs {tot_er:5.1f} expected  ({tot_r/tot_er:.2f}x)")
print(f"pooled breakages {tot_b:3d} vs {tot_eb:5.1f} expected  ({tot_b/tot_eb:.2f}x)")
