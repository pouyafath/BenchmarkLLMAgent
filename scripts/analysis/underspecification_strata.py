#!/usr/bin/env python3
"""
Does enhancement help more where the original report is thin?

This addresses the strongest objection to the paper's null. Execution benchmarks keep an
instance only if a real fix was merged and its tests discriminate, so they select for issues
that are already actionable, which is exactly the population where rewriting has least room
to help. If the null is an artifact of that selection, the effect should be visible on the
thinnest reports the corpus does contain.

Informativeness is scored by counting the diagnostic elements Bettenburg et al. identify as
what developers want and most often lack, rather than by a learned composite, so the split
is interpretable: reproduction steps, expected behaviour, actual behaviour, stack trace,
error message, logs, environment info, code blocks, and any file reference. Range 0-9.

Two units of analysis are reported because they disagree in an instructive way. Pooling
every paired observation treats ~16 cells per instance as independent, which they are not;
the instance-level statistic avoids that. The pooled deltas show a gradient that the
instance-level test does not support.

Only Qwen3-32B matrix cells are used for the chance comparison, because the resample rates
(P(fix|failed)=0.199, P(break|passed)=0.408) were measured in that configuration; pooling in
the capability-spread runs, where weak models resolve almost nothing, would invalidate it.
"""
from __future__ import annotations
import json, sys, collections, statistics as st
from pathlib import Path

sys.path.insert(0, "/home/22pf2/LLMforGithubIssuesRefactor/src")
from issue_enhancer_agent_llm_based.feature_extraction_utils import extract_base_features
from scipy.stats import binomtest, mannwhitneyu

ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
P_FIX, P_BREAK = 0.199, 0.408
ELEMENTS = ["body_has_reproduction_steps", "body_has_expected_behavior",
            "body_has_actual_behavior", "body_has_stack_trace", "body_has_error_message",
            "body_has_logs", "body_has_environment_info", "has_code_blocks"]


def informativeness() -> dict[str, int]:
    out = {}
    for line in open(ROOT/"data/stage6_all279_v2.jsonl"):
        r = json.loads(line)
        ps = r.get("problem_statement", "") or ""
        title, _, body = ps.partition("\n")
        f = extract_base_features({"title": title, "body": body}).iloc[0].to_dict()
        s = sum(1 for e in ELEMENTS if bool(f.get(e)))
        if float(f.get("num_file_references") or 0) > 0:
            s += 1
        out[r["instance_id"]] = s
    return out


def paired(info: dict[str, int]) -> list[dict]:
    rows = []
    for f in ROOT.glob("runs/stage6_sample_*/result.json"):
        try: r = json.load(open(f))
        except Exception: continue
        rb, re_ = r.get("resolved_baseline"), r.get("resolved_enh")
        if not isinstance(rb, dict) or not isinstance(re_, dict): continue
        cell = r.get("label") or f.parent.name
        for i in set(rb) & set(re_):
            if i in info:
                rows.append({"iid": i, "base": bool(rb[i]), "enh": bool(re_[i]),
                             "cell": cell, "score": info[i]})
    cells = json.load(open(ROOT/"data/stage6_run4_appendonly_cells.json"))
    for k, v in cells.items():
        for i in set(v["resolved_baseline"]) & set(v["resolved_enh"]):
            if i in info:
                rows.append({"iid": i, "base": bool(v["resolved_baseline"][i]),
                             "enh": bool(v["resolved_enh"][i]), "cell": "run4_"+k,
                             "score": info[i]})
    return rows


def stratum(s: int) -> str:
    return "thin (0-2)" if s <= 2 else ("mid (3-5)" if s <= 5 else "rich (6-9)")


def main() -> int:
    info = informativeness()
    d = collections.Counter(info.values())
    print("Informativeness of the 279 original reports (diagnostic elements present, 0-9)")
    for k in sorted(d):
        print(f"   {k}: {'#'*d[k]} {d[k]}")
    sc = list(info.values())
    print(f"   median {st.median(sc)}, lower quartile {st.quantiles(sc)[0]:.1f}\n")

    rows = paired(info)
    keep = [x for x in rows if x["cell"].startswith(("run4", "m1_", "m3_"))]
    print(f"Qwen3-32B matrix cells: {len(keep)} paired observations, "
          f"{len({x['iid'] for x in keep})} instances, {len({x['cell'] for x in keep})} cells\n")

    agg = collections.defaultdict(lambda: {"nf": 0, "np": 0, "r": 0, "k": 0})
    for x in keep:
        a = agg[stratum(x["score"])]
        if x["base"]:
            a["np"] += 1; a["k"] += (not x["enh"])
        else:
            a["nf"] += 1; a["r"] += x["enh"]
    print(f"{'stratum':13s} {'rescue rate':>20} {'chance':>7} {'p(>)':>7}   "
          f"{'breakage rate':>20} {'chance':>7} {'p(<)':>7}")
    for s in ["thin (0-2)", "mid (3-5)", "rich (6-9)"]:
        a = agg[s]
        if not a["nf"] or not a["np"]: continue
        pr = binomtest(a["r"], a["nf"], P_FIX, alternative="greater").pvalue
        pk = binomtest(a["k"], a["np"], P_BREAK, alternative="less").pvalue
        print(f"{s:13s} {a['r']:5d}/{a['nf']:<6d}={a['r']/a['nf']:.3f} {P_FIX:7.3f} {pr:7.3f}   "
              f"{a['k']:5d}/{a['np']:<6d}={a['k']/a['np']:.3f} {P_BREAK:7.3f} {pk:7.3f}")

    per = collections.defaultdict(lambda: {"r": 0, "k": 0, "n": 0, "score": 0})
    for x in keep:
        p = per[x["iid"]]
        p["n"] += 1; p["score"] = x["score"]
        p["r"] += (not x["base"] and x["enh"]); p["k"] += (x["base"] and not x["enh"])
    g = collections.defaultdict(list)
    for _, p in per.items():
        g[stratum(p["score"])].append((p["r"] - p["k"]) / p["n"])
    print("\nInstance-level net benefit per cell (the unit the pooled counts violate)")
    for s in ["thin (0-2)", "mid (3-5)", "rich (6-9)"]:
        print(f"  {s:13s} n={len(g[s]):3d}  mean {sum(g[s])/len(g[s]):+.4f}  "
              f"median {st.median(g[s]):+.4f}")
    p = mannwhitneyu(g["thin (0-2)"], g["rich (6-9)"], alternative="greater").pvalue
    print(f"\n  thin > rich, Mann-Whitney one-sided: p = {p:.4f}")
    print("  Between-strata n is 20 vs 22 instances, so this excludes a large gradient,")
    print("  not a modest one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
