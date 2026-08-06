#!/usr/bin/env python3
"""
Run a SINGLE enhancer x solver cell on REAL OpenAI models.

Default cell: enh:aider -> sol:openhands (the one you asked about). Reuses the pipeline's
enhance()/solve() but points the model endpoint at the OpenAI API instead of the local Ollama.
A baseline (no-enhancement) OpenHands solve is included by default so you also get the delta.

The OpenAI key is read from (in order):
    1) $OPENAI_API_KEY
    2) .secrets/openai_api_key.txt   (first non-comment, non-blank line)
It is never printed or logged. .secrets/ is gitignored.

Model-string handling (matches the existing solvers):
    - Aider enhancer wants the litellm prefix ->  openai/<model>
    - OpenHands solver wants the bare id       ->  <model>   (it prepends openai/ internally)

Examples:
    # 3-issue smoke test (cheap, ~$0.2):
    bench_env/bin/python scripts/workflows/run_openai_cell.py --limit 3 --model gpt-5-mini --tag smoke_oai
    # full 382:
    bench_env/bin/python scripts/workflows/run_openai_cell.py --model gpt-5-mini --tag oai_aider_oh_382
    # a specific instance list (e.g. the 279 evaluable):
    bench_env/bin/python scripts/workflows/run_openai_cell.py --instances id1,id2,id3 --model gpt-5-mini
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
sys.path.insert(0, str(ROOT))

OPENAI_BASE_URL = "https://api.openai.com/v1"
KEY_FILE = ROOT / ".secrets" / "openai_api_key.txt"


def load_key() -> str:
    k = os.environ.get("OPENAI_API_KEY", "").strip()
    if k:
        return k
    if KEY_FILE.exists():
        for line in KEY_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    return ""


def openai_preflight(base_url: str, key: str, model_bare: str) -> bool:
    """One tiny chat completion to prove key+model work. Never prints the key."""
    import requests
    is_gpt5 = model_bare.split("/")[-1].lower().startswith("gpt-5")
    payload = {"model": model_bare, "messages": [{"role": "user", "content": "Say OK"}]}
    payload["max_completion_tokens" if is_gpt5 else "max_tokens"] = 16
    if not is_gpt5:
        payload["temperature"] = 0
    try:
        r = requests.post(base_url.rstrip("/") + "/chat/completions", json=payload,
                          headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                          timeout=60)
    except Exception as e:
        print(f"  [preflight] OpenAI request FAILED: {e}"); return False
    if r.status_code != 200:
        # surface the error body but it never contains the key
        print(f"  [preflight] OpenAI returned {r.status_code}: {r.text[:300]}"); return False
    msg = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    print(f"  [preflight] OpenAI OK — model={model_bare!r} replied {msg[:30]!r}")
    return True


def images_present(instances) -> int:
    miss = 0
    for inst in instances:
        img = inst.get("docker_image", "")
        if subprocess.run(["docker", "image", "inspect", img, "--format", "{{.Id}}"],
                          capture_output=True).returncode != 0:
            miss += 1
            print(f"  [preflight] MISSING image: {img} ({inst['instance_id']})")
    return miss


def scan_cost(work_dir: Path) -> float:
    """Best-effort: sum any 'accumulated_cost'/'cost' fields OpenHands/aider left in the work dir."""
    import re
    total = 0.0
    for p in work_dir.rglob("*.json"):
        try:
            txt = p.read_text()
        except Exception:
            continue
        for m in re.finditer(r'"accumulated_cost"\s*:\s*([0-9.]+)', txt):
            total += float(m.group(1))
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(ROOT / "data" / "matrix_sample382_node01.jsonl"))
    ap.add_argument("--model", default="gpt-5-mini",
                    help="OpenAI model id (bare), e.g. gpt-5-mini, gpt-5.4-mini, gpt-4o-mini")
    ap.add_argument("--enhancer", default="aider")
    ap.add_argument("--solver", default="openhands")
    ap.add_argument("--limit", type=int, default=0, help="run first N instances that have images")
    ap.add_argument("--instances", default="", help="comma-separated instance_ids to run")
    ap.add_argument("--instances-file", default="", help="file with one instance_id per line")
    ap.add_argument("--workers", type=int, default=0, help="override solver concurrency (0=pipeline default)")
    ap.add_argument("--tag", default="oai_cell")
    ap.add_argument("--no-baseline", action="store_true", help="skip the baseline (no-enh) solve")
    ap.add_argument("--enh-timeout", type=int, default=600)
    ap.add_argument("--solve-timeout", type=int, default=1800)
    ap.add_argument("--dry-run", action="store_true", help="preflight only; do not call the agents")
    a = ap.parse_args()

    model_bare = a.model                      # openhands wants bare
    model_pref = f"openai/{a.model}"          # aider/litellm wants prefix

    key = load_key()
    if not key:
        print("\n✗ No OpenAI API key found.")
        print(f"  Paste your key into: {KEY_FILE}")
        print("  (or run:  export OPENAI_API_KEY=sk-...)\n")
        return 2
    print(f"✓ OpenAI key loaded (…{key[-4:]}), {len(key)} chars")   # last 4 only, never the whole key

    # ── point the pipeline at OpenAI ─────────────────────────────────────────
    import scripts.workflows.run_matrix_test as rmt
    rmt.BASE_URL = OPENAI_BASE_URL
    rmt.API_KEY = key
    rmt.ENH_TIMEOUT = a.enh_timeout
    rmt.SOLVE_TIMEOUT = a.solve_timeout
    if a.workers:
        rmt.WORKERS = a.workers
        rmt.SOLVER_WORKERS = {k: a.workers for k in rmt.SOLVER_WORKERS}
        print(f"solver concurrency overridden -> workers={a.workers}")
    os.environ.update({
        "USE_OLLAMA": "0",
        "OPENAI_API_KEY": key,
        # aider enhancer
        "AIDER_MODEL": model_pref, "AIDER_API_BASE": OPENAI_BASE_URL, "AIDER_API_KEY": key,
        "AIDER_TIMEOUT": str(a.enh_timeout),
        # openhands solver
        "OH_SOLVER_MODEL": model_bare, "OH_SOLVER_BASE_URL": OPENAI_BASE_URL, "OH_SOLVER_API_KEY": key,
        "OH_SOLVER_TIMEOUT": str(a.solve_timeout), "OH_SOLVER_MAX_ITER": "30",
    })

    # ── select instances ─────────────────────────────────────────────────────
    from scripts.workflows.run_matrix_test import _load, enhance, solve
    all_inst = _load(a.dataset)
    if a.instances_file:
        want = set(l.strip() for l in Path(a.instances_file).read_text().splitlines() if l.strip())
        by_id = {i["instance_id"]: i for i in all_inst}
        instances = [by_id[i] for i in want if i in by_id]  # keep only ids present in the dataset
        print(f"instances-file: {len(want)} ids requested, {len(instances)} matched in dataset")
    elif a.instances:
        want = set(s.strip() for s in a.instances.split(",") if s.strip())
        instances = [i for i in all_inst if i["instance_id"] in want]
    elif a.limit:
        # first N with a present docker image
        instances, seen = [], 0
        for i in all_inst:
            img = i.get("docker_image", "")
            if subprocess.run(["docker", "image", "inspect", img, "--format", "{{.Id}}"],
                              capture_output=True).returncode == 0:
                instances.append(i)
                if len(instances) >= a.limit:
                    break
    else:
        instances = all_inst
    if not instances:
        print("✗ No instances selected."); return 2
    print(f"Selected {len(instances)} instance(s): {', '.join(i['instance_id'] for i in instances)}")

    # ── preflight ────────────────────────────────────────────────────────────
    print("\n=== PREFLIGHT ===")
    ok = openai_preflight(OPENAI_BASE_URL, key, model_bare)
    miss = images_present(instances)
    if miss:
        print(f"✗ {miss} docker image(s) missing — aborting."); return 2
    print(f"✓ all {len(instances)} docker images present")
    if not ok:
        print("✗ OpenAI preflight failed — fix the key/model and retry."); return 2
    if a.dry_run:
        print("\n[dry-run] preflight passed; not calling the agents."); return 0

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = ROOT / "runs" / f"{a.tag}_{ts}" / a.model.replace("/", "_").replace(".", "")
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nRun dir: {run_dir}")
    summary = {"model": a.model, "cell": f"enh:{a.enhancer} -> sol:{a.solver}",
               "n": len(instances), "instances": [i["instance_id"] for i in instances]}

    # ── baseline: solver on ORIGINAL text ────────────────────────────────────
    if not a.no_baseline:
        print(f"\n=== BASELINE: {a.solver} on original ({len(instances)} issues) ===")
        t0 = time.time()
        base_dir = run_dir / f"baseline__solver_{a.solver}"
        base_preds = solve(a.solver, instances, base_dir, model_bare)
        b_ne = sum(1 for i in instances if (base_preds.get(i["instance_id"], {}).get("model_patch", "") or "").strip())
        summary["baseline"] = {"nonempty": b_ne, "n": len(instances), "elapsed_min": (time.time()-t0)/60,
                               "cost_scanned": scan_cost(base_dir)}
        print(f"[baseline] non-empty patches: {b_ne}/{len(instances)}  ({(time.time()-t0)/60:.1f} min)")

    # ── enhance (aider) -> solve (openhands) ─────────────────────────────────
    print(f"\n=== ENHANCE: {a.enhancer} ({len(instances)} issues) ===")
    t0 = time.time()
    edir = run_dir / f"stage4_{a.enhancer}"
    rows, n_ok = enhance(a.enhancer, instances, edir, model_bare)
    print(f"[enhance:{a.enhancer}] {n_ok}/{len(instances)} truly enhanced  ({(time.time()-t0)/60:.1f} min)")

    print(f"\n=== SOLVE: {a.solver} on enh:{a.enhancer} ({len(rows)} issues) ===")
    t0 = time.time()
    sdir = run_dir / f"enh_{a.enhancer}__solver_{a.solver}"
    enh_preds = solve(a.solver, rows, sdir, model_bare)
    e_ne = sum(1 for i in rows if (enh_preds.get(i["instance_id"], {}).get("model_patch", "") or "").strip())
    summary["enhanced"] = {"truly_enhanced": n_ok, "nonempty": e_ne, "n": len(rows),
                           "elapsed_min": (time.time()-t0)/60, "cost_scanned": scan_cost(sdir)}
    print(f"[enh->{a.solver}] non-empty patches: {e_ne}/{len(rows)}  ({(time.time()-t0)/60:.1f} min)")

    (run_dir.parent / "openai_cell_summary.json").write_text(json.dumps(summary, indent=2))
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))
    scanned = summary.get("enhanced", {}).get("cost_scanned", 0) + summary.get("baseline", {}).get("cost_scanned", 0)
    if scanned:
        print(f"\nScanned agent-reported cost: ${scanned:.4f} (OpenHands accumulated_cost; "
              f"check platform.openai.com/usage for the authoritative spend).")
    else:
        print("\n(No agent-reported cost fields found — check platform.openai.com/usage for actual spend.)")
    print("\nNOTE: this smoke run reports NON-EMPTY PATCH counts (did the agents produce a diff). "
          "Correctness (P2P-resolved) still requires the Stage-6 scorer on the evaluable subset.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
