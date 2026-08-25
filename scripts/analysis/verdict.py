#!/usr/bin/env python3
"""
Apply the pre-registered decision rule to a repo-grounded scale-up run.

The pre-registration (docs/analysis/scaleup_prereg.md) fixes the RULE, not the number:
the threshold is the smallest k with P(>= k rescues) < 0.05 under the resample null,
k ~ Binomial(n_rescuable, 0.129). n_rescuable is determined by the fresh baseline in the
run itself, so the threshold is recomputed from the data using that same procedure.

Rates come from the 1,674-trial main matrix:
  P(fix   | baseline failed) = 0.129
  P(break | baseline passed) = 0.408

Usage:
  bench_env/bin/python scripts/analysis/verdict.py rge20_qwen3 [rge20_gpt5mini ...]
"""
from __future__ import annotations
import json, sys, pathlib
from math import comb

ROOT = pathlib.Path("/home/22pf2/BenchmarkLLMAgent")
P_FIX, P_BREAK, ALPHA = 0.129, 0.408, 0.05


def tail(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p)."""
    return sum(comb(n, i) * p**i * (1 - p)**(n - i) for i in range(k, n + 1))


def threshold(n: int) -> int | None:
    """Smallest k with P(>=k) < ALPHA; None if unreachable at this n."""
    for k in range(n + 1):
        if tail(k, n, P_FIX) < ALPHA:
            return k
    return None


def treated_set(label: str) -> set[str] | None:
    """Instances that actually received the treatment (enhancer wrote an output)."""
    for wd in ROOT.glob(f"runs/{label}_*/*/stage4_repo_grounded_work"):
        return {p.name for p in wd.iterdir()
                if (p / "workspace" / "enhanced_issue.md").exists()}
    return None


def report(label: str) -> None:
    rp = ROOT / f"runs/stage6_sample_{label}/result.json"
    if not rp.exists():
        print(f"\n{label}: not scored yet ({rp} missing)")
        return
    d = json.load(open(rp))
    b, e = d["resolved_baseline"], d["resolved_enh"]
    ids = sorted(b)
    rescuable = [i for i in ids if not b[i]]
    exposed   = [i for i in ids if b[i]]
    rescues   = [i for i in rescuable if e[i]]
    breaks    = [i for i in exposed if not e[i]]

    treated = treated_set(label)
    tr_rescues = ([i for i in rescues if i in treated] if treated else None)

    n_r = len(rescuable)
    k_req = threshold(n_r)
    obs = len(rescues)
    p_obs = tail(obs, n_r, P_FIX) if n_r else float("nan")

    print(f"\n{'='*66}\n{label}\n{'='*66}")
    print(f"  baseline {d['baseline']}/{d['n']}   enhanced {d['enh']}/{d['n']}   delta {d['delta']:+d}")
    print(f"  rescuable (baseline failed) : {n_r}")
    print(f"  exposed   (baseline passed) : {len(exposed)}")
    print(f"  RESCUES observed            : {obs}"
          + (f"   (of which treated: {len(tr_rescues)})" if tr_rescues is not None else ""))
    print(f"  breakages observed          : {len(breaks)}")
    print()
    print(f"  null expects  {n_r*P_FIX:.1f} rescues, {len(exposed)*P_BREAK:.1f} breakages, "
          f"net delta {n_r*P_FIX - len(exposed)*P_BREAK:+.1f}")
    print(f"  pre-registered threshold    : >= {k_req} rescues "
          f"(smallest k with P<{ALPHA} at n={n_r})" if k_req is not None
          else f"  threshold unreachable at n={n_r}")
    print(f"  P(>= {obs} rescues | null)        : {p_obs:.3f}")
    print()
    if k_req is not None and obs >= k_req:
        print("  VERDICT: BEATS THE RESAMPLE NULL — real effect.")
    else:
        print("  VERDICT: within the resample band — NULL HOLDS.")
    print("           (delta is not the criterion; rescues are)")
    if rescues:
        print(f"  rescued: {rescues}")
    if breaks:
        print(f"  broken : {breaks}")


if __name__ == "__main__":
    labels = sys.argv[1:] or ["rge20_qwen3", "rge20_gpt5mini"]
    for l in labels:
        report(l)
    print()
