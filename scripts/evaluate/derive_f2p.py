#!/usr/bin/env python3
"""
Re-derive FAIL_TO_PASS / PASS_TO_PASS labels from execution instead of diff parsing.

Why this is needed. Every instance in the 279-issue evaluable set carries
`f2p_p2p_derivation.method == "offline_test_patch_diff_parse"`: the labels were read off
the test patch's diff, never observed. The rows say so themselves ("F2P not required. F2P
stored for reference only"). The consequences are visible in the data:

  * 1193 of 1210 F2P-labelled tests never appear in the recorded `test_status` at all;
  * the labelled F2P set matches the observed failures for only 49 of 279 instances;
  * 54 instances carry no F2P label whatsoever.

So the paper reports P2P-resolved, a no-regression criterion, which credits a patch that
never applied: the repository is untouched, P2P stays green, and the instance scores as
solved. That is the largest construct threat in the study.

What this does. A test's class is defined by its behaviour, not by the diff:

    F2P = fails at base+test_patch, passes at base+test_patch+gold
    P2P = passes at base+test_patch, passes at base+test_patch+gold

The second half is already on disk. The gold probe ran exactly base+test_patch+gold for
all 279 instances under each one's assigned method and left a parsed per-test
`status.json`. Only the first half is missing, and it is the same harness call with an
empty solution patch, so this costs 279 container runs rather than 558.

Reusing the harness rather than parsing logs is deliberate: `evaluate_instance` already
handles the per-repo runner quirks, the /testbed-subdirectory corner case, and log
parsing.

Getting a no-op solution patch past the harness needs care. An *empty* pred_patch does not
work: run_instances() filters those out ("Empty patch...") and never starts a container, so
a first attempt produced 0/279 PRE runs while exiting 0. The patch string must therefore be
non-empty but must not modify the tree. We send a sentinel that is deliberately not a diff:
`git apply` rejects it with "unrecognized input", applies nothing (it is atomic, and with
--reject an unparseable input yields no hunks to reject), and container.apply_patch returns
False without raising. The repository is left at base+test_patch, which is the PRE state.

Usage:
    bench_env/bin/python scripts/evaluate/derive_f2p.py pre       # 279 container runs
    bench_env/bin/python scripts/evaluate/derive_f2p.py combine   # no Docker; writes labels
"""
from __future__ import annotations
import json, os, subprocess, sys, collections
from pathlib import Path

ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
EVAL = ROOT / "SWE-bench-Live-Collection/evaluation/evaluation.py"
PY   = "/home/22pf2/anaconda3/envs/paul-repolaunch/bin/python"
DATASETS = {"v3_fileLevel": ROOT/"data/stage6_all279_v3.jsonl",
            "v2_targeted":  ROOT/"data/stage6_all279_v2.jsonl",
            "v1_files":     ROOT/"data/stage6_all279_v1.jsonl"}
METHODS  = ROOT/"data/stage6_all279_methods.json"
OUT      = ROOT/"runs/f2p_rederive"
GOLDMAP  = OUT/"goldprobe_dirs.json"
LABELS   = ROOT/"data/stage6_all279_f2p_derived.json"
WORKERS  = int(os.environ.get("F2P_WORKERS", "4"))
TIMEOUT  = int(os.environ.get("HARNESS_TIMEOUT", "5400"))

MAP = {"v2": "v2_targeted", "v3": "v3_fileLevel", "v1": "v1_files"}


def gold_dirs() -> dict[str, str]:
    """Locate each instance's gold-probe output for its *assigned* method."""
    if GOLDMAP.exists():
        return json.load(open(GOLDMAP))
    methods = json.load(open(METHODS))
    loc: dict[str, dict[str, str]] = {}
    for d in ROOT.glob("runs/stage6_*goldprobe/*/*"):
        if (d/"status.json").exists():
            loc.setdefault(d.name, {})[MAP.get(d.parent.name, "?")] = str(d)
    out = {i: loc[i][m] for i, m in methods.items() if i in loc and m in loc[i]}
    GOLDMAP.parent.mkdir(parents=True, exist_ok=True)
    GOLDMAP.write_text(json.dumps(out, indent=1))
    return out


def cmd_pre() -> int:
    methods = json.load(open(METHODS))
    ids = list(methods)
    preds = OUT/"empty_preds.json"
    preds.parent.mkdir(parents=True, exist_ok=True)
    # Non-empty (so the harness does not skip it) but not a diff (so nothing is applied).
    NOOP = "# PRE-run sentinel: intentionally not a diff, so git apply is a no-op\n"
    preds.write_text(json.dumps({i: {"instance_id": i, "model_patch": NOOP} for i in ids}))

    by_method: dict[str, list[str]] = collections.defaultdict(list)
    for i, m in methods.items():
        by_method[m].append(i)

    for method, grp in by_method.items():
        odir = OUT/"pre"/method
        odir.mkdir(parents=True, exist_ok=True)
        todo = [i for i in grp if not (odir/i/"status.json").exists()]
        if not todo:
            print(f"[{method}] all {len(grp)} already done", flush=True); continue
        print(f"[{method}] running {len(todo)}/{len(grp)}", flush=True)
        try:
            r = subprocess.run(
                [PY, str(EVAL), "--dataset", str(DATASETS[method]),
                 "--patch_dir", str(preds.resolve()), "--platform", "linux",
                 "--workers", str(WORKERS), "--output_dir", str(odir.resolve()),
                 "--overwrite", "1", "--instance_ids", *todo],
                cwd=str(EVAL.parent), capture_output=True, text=True, timeout=TIMEOUT)
            if r.returncode != 0:
                print(f"  !! harness exit {r.returncode}", flush=True)
                for l in (r.stderr or r.stdout or "").strip().splitlines()[-5:]:
                    print("     "+l[:160], flush=True)
        except subprocess.TimeoutExpired:
            print(f"  !! harness TIMED OUT after {TIMEOUT}s on {method}", flush=True)
        done = sum(1 for i in grp if (odir/i/"status.json").exists())
        print(f"[{method}] {done}/{len(grp)} have PRE status", flush=True)
        if done == 0:
            print(f"  !! {method} produced NO artifacts at all. That is a setup failure, not "
                  f"a run of unlucky instances -- check that the harness accepted the patch "
                  f"(an empty model_patch is silently skipped).", flush=True)
    return 0


def cmd_combine() -> int:
    methods = json.load(open(METHODS))
    gold = gold_dirs()
    labels, skipped = {}, collections.Counter()

    for i, m in methods.items():
        pre_f = OUT/"pre"/m/i/"status.json"
        if not pre_f.exists():
            skipped["no PRE run"] += 1; continue
        if i not in gold:
            skipped["no gold probe"] += 1; continue
        pre  = json.load(open(pre_f))
        post = json.load(open(Path(gold[i])/"status.json"))
        f2p = sorted(t for t, s in post.items() if s == "pass" and pre.get(t) == "fail")
        p2p = sorted(t for t, s in post.items() if s == "pass" and pre.get(t) == "pass")
        labels[i] = {
            "FAIL_TO_PASS": f2p, "PASS_TO_PASS": p2p,
            "method": m, "derivation": "executed_pre_vs_gold",
            "n_pre": len(pre), "n_post": len(post),
            "unseen_in_pre": sorted(t for t in post if t not in pre)[:20],
        }

    LABELS.write_text(json.dumps(labels, indent=1))
    n_f2p = sum(1 for v in labels.values() if v["FAIL_TO_PASS"])
    old = {json.loads(l)["instance_id"]: json.loads(l)
           for l in open(ROOT/"data/stage6_all279_v2.jsonl")}
    old_f2p = sum(1 for i in labels if old.get(i, {}).get("FAIL_TO_PASS"))
    print(f"derived labels for {len(labels)}/{len(methods)} instances "
          f"({dict(skipped)} skipped)")
    print(f"  with >=1 executed F2P test : {n_f2p}  ({n_f2p/max(len(labels),1):.1%})")
    print(f"  had >=1 offline F2P label  : {old_f2p}")
    print(f"  median executed F2P per instance: "
          f"{sorted(len(v['FAIL_TO_PASS']) for v in labels.values())[len(labels)//2] if labels else 0}")
    agree = sum(1 for i, v in labels.items()
                if set(v["FAIL_TO_PASS"]) == set(old.get(i, {}).get("FAIL_TO_PASS") or []))
    print(f"  executed set == offline set: {agree}/{len(labels)}")
    print(f"Wrote {LABELS}")
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "pre"
    sys.exit(cmd_pre() if mode == "pre" else cmd_combine())
