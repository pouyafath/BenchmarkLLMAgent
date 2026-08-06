#!/usr/bin/env python3
"""A/B solver-model comparison on the smoke-2 set (10 instances).

Isolates the SOLVER MODEL variable: reuses smoke-2's already-produced Stage-4
baseline + enhanced issues and re-runs only the OpenHands solver with each
candidate model on the dedicated A/B Ollama (:11436, GPU 0), so it does NOT
touch the production :11435 endpoint / the running batch60.

qwen3:32b arm is taken from the existing smoke-2 result.json (no re-run).
"""
from __future__ import annotations
import json, time, sys, os
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.solvers.openhands_solver import run_batch  # noqa: E402

SMOKE = ROOT / "runs/node1_full383_qwen3_20260615_164539"
AB_BASE_URL = "http://localhost:11436/v1"
API_KEY = "ollama"
WORKERS = int(os.environ.get("AB_WORKERS", "2"))   # env-overridable so a relaunch can use freed GPUs
MAX_ITER = 30
TIMEOUT = 3600

# Candidate solver models. native_tool_calling forced True (both support tools;
# OpenHands' pattern list recognizes qwen3-coder but not devstral by name).
MODELS = [
    ("qwen3-coder:30b", True),
    ("devstral",        True),
]

# qwen3:32b reference from smoke-2 result.json (same 10 instances, same Stage-4)
REF_MODEL = "qwen3:32b (smoke-2 ref)"

def _load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]

def _patches(preds: dict) -> int:
    return sum(1 for v in preds.values() if (v.get("model_patch") or "").strip())

def main():
    # AB_OUT_DIR lets a relaunch resume into the same dir (run_batch skips done instances).
    out_dir = Path(os.environ.get("AB_OUT_DIR",
                   str(ROOT / "runs" / f"ab_solver_{datetime.now().strftime('%Y%m%d_%H%M%S')}")))
    out_dir.mkdir(parents=True, exist_ok=True)
    log = out_dir / "ab.log"
    def say(m):
        line = f"[{datetime.now(timezone.utc):%H:%M:%S} UTC] {m}"
        print(line, flush=True)
        with open(log, "a") as f: f.write(line + "\n")

    baseline = _load(SMOKE / "stage4_enhanced/baseline.jsonl")
    enhanced = _load(SMOKE / "stage4_enhanced/enhanced_all.jsonl")
    say(f"Loaded {len(baseline)} baseline + {len(enhanced)} enhanced issues from smoke-2")

    ref = json.loads((SMOKE / "result.json").read_text())
    results = {REF_MODEL: {"baseline": ref["baseline_nonempty"], "enhanced": ref["enhanced_nonempty"],
                           "n": ref["n_instances"], "secs": ref["total_seconds"]}}

    for model, ntc in MODELS:
        say(f"=== {model} (native_tool_calling={ntc}) ===")
        mdir = out_dir / model.replace(":", "_").replace("/", "_")
        t0 = time.time()
        say(f"  [{model}] baseline solving ...")
        bl = run_batch(baseline, API_KEY, mdir / "baseline_work", mdir / "baseline_preds.json",
                       model=model, base_url=AB_BASE_URL, max_iter=MAX_ITER, timeout=TIMEOUT,
                       workers=WORKERS, native_tool_calling=ntc)
        say(f"  [{model}] enhanced solving ...")
        en = run_batch(enhanced, API_KEY, mdir / "enhanced_work", mdir / "enhanced_preds.json",
                       model=model, base_url=AB_BASE_URL, max_iter=MAX_ITER, timeout=TIMEOUT,
                       workers=WORKERS, native_tool_calling=ntc)
        secs = time.time() - t0
        results[model] = {"baseline": _patches(bl), "enhanced": _patches(en),
                          "n": len(baseline), "secs": round(secs, 1)}
        say(f"  [{model}] baseline={results[model]['baseline']}/{len(baseline)} "
            f"enhanced={results[model]['enhanced']}/{len(enhanced)} time={secs/60:.0f}min")

    say("")
    say("================== A/B RESULT ==================")
    say(f"{'model':28s} {'baseline':>10s} {'enhanced':>10s} {'time':>10s}")
    for m, r in results.items():
        t = f"{r['secs']/60:.0f}min" if r.get("secs") else "—"
        say(f"{m:28s} {str(r['baseline'])+'/'+str(r['n']):>10s} "
            f"{str(r['enhanced'])+'/'+str(r['n']):>10s} {t:>10s}")
    (out_dir / "ab_result.json").write_text(json.dumps(results, indent=2))
    say(f"Wrote {out_dir/'ab_result.json'}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
