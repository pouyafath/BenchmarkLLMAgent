#!/usr/bin/env python3
"""
Score one enh:Aider -> sol:OpenHands cell (baseline + enhanced) on a subset of the
279 gold-evaluable instances, using PER-INSTANCE the gold-probe method that validated:

  v3_fileLevel -> label-agnostic raw pytest (>=1 passed, 0 failed/error)
  v2_targeted  -> report.json PASS_TO_PASS (0 failure, >0 success)
  v1_files     -> report.json PASS_TO_PASS

This replaces the `scratchpad/score_sample.py` referenced by
docs/multimodel_capability_spread_experiment.md, which was lost. Method assignments
come from data/stage6_all279_methods.json (recovered from the stage6_*_scores matrices).

Usage:
  bench_env/bin/python scripts/evaluate/score_sample.py \
      runs/qwen3_32b_g5s20_rerun_20260824_180848/qwen3_32b \
      .secrets/sample20_gpt5solved.txt qwen3_32b_g5s20

Writes runs/stage6_sample_<label>/result.json in the same shape the capability-spread
table was built from: {label, n, baseline, enh, delta, resolved_baseline, resolved_enh}.

NOTE ON THE METRIC: resolution is PASS_TO_PASS-only (no FAIL_TO_PASS requirement), so a
patch that fails to apply leaves the repo untouched, keeps P2P green and is credited as a
solve. See docs/why_gpt5_outperforms_open_models_20260824.md. --require-applied filters
those out; it is off by default so numbers stay comparable with prior runs.
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys
from pathlib import Path

ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
EVAL = ROOT / "SWE-bench-Live-Collection/evaluation/evaluation.py"
PY   = "/home/22pf2/anaconda3/envs/paul-repolaunch/bin/python"
DATASETS = {"v3_fileLevel": ROOT/"data/stage6_all279_v3.jsonl",
            "v2_targeted":  ROOT/"data/stage6_all279_v2.jsonl",
            "v1_files":     ROOT/"data/stage6_all279_v1.jsonl"}
METHODS = ROOT/"data/stage6_all279_methods.json"
ARMS = {"baseline": "baseline__solver_openhands", "enhanced": "enh_aider__solver_openhands"}
# --enh-dir overrides the enhanced arm for cells other than enh:aider
# (e.g. enh_repo_grounded__solver_openhands).


def label_agnostic_pass(logfile: Path) -> bool:
    if not logfile.exists(): return False
    t = logfile.read_text(errors="replace")
    passed = sum(int(x) for x in re.findall(r'(\d+) passed', t))
    failed = sum(int(x) for x in re.findall(r'(\d+) failed', t))
    errors = sum(int(x) for x in re.findall(r'(\d+) error', t))
    return failed == 0 and errors == 0 and passed > 0


def report_p2p_pass(report: Path) -> bool:
    if not report.exists(): return False
    p = json.load(open(report)).get("PASS_TO_PASS", {})
    return len(p.get("failure", [])) == 0 and len(p.get("success", [])) > 0


def applied_cleanly(patch: str) -> bool:
    """A submission we would count as a genuine fix attempt.

    Accepts any well-formed *unified* diff, not just git-format ones: OpenHands agents
    frequently emit bare `--- a/x` / `+++ b/x` / `@@` hunks with no `diff --git` header,
    and those apply fine with `git apply -p1`. Requiring the git header would wrongly
    discard legitimate patches.

    Rejects: empty output, prose or raw source with no hunks, and whole-tree dumps
    (the `diff -ruN /testbed /workspace` mass-deletion pattern seen when an agent
    destroys its workspace). See docs/why_gpt5_outperforms_open_models_20260824.md.
    """
    if not patch or not patch.strip(): return False
    if len(patch) > 1_000_000: return False          # whole-tree dump
    if not re.search(r'^@@ .* @@', patch, re.M): return False      # no hunks -> not a diff
    if not re.search(r'^--- ', patch, re.M) or not re.search(r'^\+\+\+ ', patch, re.M):
        return False
    # mass deletion: every hunk removing a whole file against an absent target
    if len(re.findall(r'^@@ -\d+,\d+ \+0,0 @@', patch, re.M)) > 5: return False
    return True


def run_group(dataset: Path, preds: Path, ids: list[str], outdir: Path, workers: int) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    # harness runs with cwd=EVAL.parent, so output_dir MUST be absolute
    r = subprocess.run([PY, str(EVAL), "--dataset", str(dataset), "--patch_dir", str(preds.resolve()),
                        "--platform", "linux", "--workers", str(workers),
                        "--output_dir", str(outdir.resolve()), "--overwrite", "1",
                        "--instance_ids", *ids],
                       cwd=str(EVAL.parent), capture_output=True, text=True)
    # A harness crash writes no report.json, and a missing report scores as UNRESOLVED.
    # Silently attributing infrastructure failures to the solver would bias the results,
    # so surface them loudly instead.
    if r.returncode != 0:
        print(f"  !! harness exited {r.returncode} for {outdir.name} "
              f"({len(ids)} instances) — these will score as unresolved", flush=True)
        tail = (r.stderr or r.stdout or "").strip().splitlines()[-5:]
        for line in tail:
            print(f"     {line[:160]}", flush=True)
    missing = [i for i in ids
               if not (outdir/i/"report.json").exists()
               and not (outdir/i/"post_patch_log.txt").exists()]
    if missing:
        print(f"  !! no harness artifact for {len(missing)}/{len(ids)} instances in "
              f"{outdir.name}: {missing[:5]}{'...' if len(missing) > 5 else ''}", flush=True)


def score_arm(rundir: Path, arm: str, ids: list[str], methods: dict, out: Path,
              workers: int, require_applied: bool) -> dict:
    preds_path = rundir / ARMS[arm] / "preds.json"
    if not preds_path.exists():
        print(f"  [{arm}] MISSING {preds_path}", flush=True)
        return {}
    preds = json.load(open(preds_path))
    resolved = {i: False for i in ids}

    by_method: dict[str, list[str]] = {}
    for i in ids:
        m = methods.get(i)
        if not m:
            print(f"  [{arm}] no gold-probe method for {i}, skipping", flush=True); continue
        patch = (preds.get(i, {}) or {}).get("model_patch", "") or ""
        if not patch.strip():
            continue                      # empty submission -> unresolved, no need to run
        if require_applied and not applied_cleanly(patch):
            continue                      # malformed/whole-tree dump -> not a fix attempt
        by_method.setdefault(m, []).append(i)

    for method, grp in by_method.items():
        odir = out / arm / method
        run_group(DATASETS[method], preds_path, grp, odir, workers)
        for iid in grp:
            resolved[iid] = (label_agnostic_pass(odir/iid/"post_patch_log.txt")
                             if method == "v3_fileLevel"
                             else report_p2p_pass(odir/iid/"report.json"))
    print(f"  [{arm}] {sum(resolved.values())}/{len(ids)} resolved "
          f"({sum(len(v) for v in by_method.values())} actually evaluated)", flush=True)
    return resolved


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rundir", help="run dir containing baseline__/enh_aider__ solver subdirs")
    ap.add_argument("instances_file")
    ap.add_argument("label")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--baseline-dir", default=None,
                    help="subdir of the baseline arm (default baseline__solver_openhands)")
    ap.add_argument("--enh-dir", default=None,
                    help="subdir of the enhanced arm (default enh_aider__solver_openhands)")
    ap.add_argument("--require-applied", action="store_true",
                    help="only count solves whose patch is a non-empty, <1MB git diff")
    a = ap.parse_args()
    if a.baseline_dir: ARMS["baseline"] = a.baseline_dir
    if a.enh_dir:      ARMS["enhanced"] = a.enh_dir

    rundir = Path(a.rundir) if Path(a.rundir).is_absolute() else ROOT/a.rundir
    ids = [l.strip() for l in open(a.instances_file) if l.strip()]
    methods = json.load(open(METHODS))
    out = ROOT/"runs"/f"stage6_sample_{a.label}"
    out.mkdir(parents=True, exist_ok=True)
    print(f"Scoring {a.label}: n={len(ids)} from {rundir}"
          f"{' [require-applied]' if a.require_applied else ''}", flush=True)

    rb = score_arm(rundir, "baseline", ids, methods, out, a.workers, a.require_applied)
    re_ = score_arm(rundir, "enhanced", ids, methods, out, a.workers, a.require_applied)
    b, e = sum(rb.values()), sum(re_.values())
    res = {"label": a.label, "n": len(ids), "baseline": b, "enh": e, "delta": e-b,
           "require_applied": a.require_applied,
           "resolved_baseline": rb, "resolved_enh": re_}
    (out/"result.json").write_text(json.dumps(res, indent=1))
    print(f"\n{a.label}: baseline {b}/{len(ids)}  enhanced {e}/{len(ids)}  delta {e-b:+d}")
    print(f"Wrote {out/'result.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
