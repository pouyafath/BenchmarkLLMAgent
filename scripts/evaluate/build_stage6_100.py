#!/usr/bin/env python3
"""
STAGE 6 (100-issue) — Phase 1: build all inputs (no Docker).
  1. Consolidated per-condition preds for the 100 (validated-50 sources + new-50 source).
  2. v1/v2/v3 eval datasets for the 100 (test_cmds/rebuild/_p2p_expected), per the proven recipes.
  3. gold preds (the dataset 'patch' field) for the gold-probe gate.

Sources (must match how the FINAL_100 matrix was assembled):
  validated-50  openhands/swe_agent -> rerun_slow50_20260625_234051   (corrected w=4)
  validated-50  aider               -> matrix50_node01_20260619_185640 (original, valid)
  new-50        all solvers         -> matrix100_new50_20260626_200219 (post artifact-recovery)
"""
from __future__ import annotations
import json, glob
from pathlib import Path

ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
VAL_SLOW = ROOT / "runs/rerun_slow50_20260625_234051"
VAL_AIDER = ROOT / "runs/matrix50_node01_20260619_185640"
NEW = ROOT / "runs/matrix100_new50_20260626_200219"
CONSOL = ROOT / "runs/stage6_100_consol/qwen3_32b/stage5"
PG = glob.glob("/home/22pf2/paul-RepoLaunch/workspace/*/playground")
STATES = ["baseline", "enh:openhands", "enh:swe_agent", "enh:aider"]
SOLVERS = ["openhands", "swe_agent", "aider"]

val_ids = [json.loads(l)["instance_id"] for l in open(ROOT / "data/matrix_sample50_node01.jsonl") if l.strip()]
new_ids = [json.loads(l)["instance_id"] for l in open(ROOT / "data/matrix_sample50new_node01.jsonl") if l.strip()]
all100 = {json.loads(l)["instance_id"]: json.loads(l)
          for f in ["data/matrix_sample50_node01.jsonl", "data/matrix_sample50new_node01.jsonl"]
          for l in open(ROOT / f) if l.strip()}


def cond(state, solver): return f"{state.replace(':', '_')}__solver_{solver}"
def loadp(run, c):
    f = run / "qwen3_32b" / "stage5" / c / "preds.json"
    return json.loads(f.read_text()) if f.exists() else {}


# ---- 1. consolidated preds (12 conditions x 100 instances) -------------------
n_written = 0
for state in STATES:
    for solver in SOLVERS:
        c = cond(state, solver)
        val_src = VAL_AIDER if solver == "aider" else VAL_SLOW
        valp, newp = loadp(val_src, c), loadp(NEW, c)
        merged = {}
        for iid in val_ids:
            if iid in valp: merged[iid] = valp[iid]
        for iid in new_ids:
            if iid in newp: merged[iid] = newp[iid]
        outf = CONSOL / c / "preds.json"
        outf.parent.mkdir(parents=True, exist_ok=True)
        outf.write_text(json.dumps(merged, indent=2))
        ne = sum(1 for v in merged.values() if (v.get("model_patch", "") or "").strip())
        n_written += 1
        print(f"  {c:<40} {len(merged)}/100 instances, {ne} non-empty")
print(f"consolidated {n_written} condition preds -> {CONSOL}\n")


# ---- 2. eval datasets v1/v2/v3 ----------------------------------------------
def pg_rec(iid):
    for r in PG:
        p = Path(r) / iid / "result.json"
        if p.exists():
            try: return json.load(open(p))
            except Exception: pass
    return None


def p2p_files(row):
    p2p = row.get("PASS_TO_PASS", []) or []
    if isinstance(p2p, str):
        try: p2p = json.loads(p2p.replace("'", '"'))
        except Exception: p2p = []
    f2p = row.get("FAIL_TO_PASS", []) or []
    if isinstance(f2p, str):
        try: f2p = json.loads(f2p.replace("'", '"'))
        except Exception: f2p = []
    files = sorted({t.split("::")[0] for t in (list(p2p) + list(f2p)) if "::" in t})
    return p2p, files


v1, v2, v3, gold, npg = [], [], [], {}, 0
for iid, row in all100.items():
    p2p, files = p2p_files(row)
    rec = pg_rec(iid)
    rebuild = (rec.get("rebuild_commands", []) if rec else []) or []
    # v3: label-agnostic — run the test files, raw pytest parse
    d3 = dict(row)
    d3["test_cmds"] = ["bash -lc 'python -m pytest -v -rA --continue-on-collection-errors "
                       + " ".join(files) + " > /tmp/s6.out 2>&1'"]
    d3["print_cmds"] = ["cat /tmp/s6.out"]; d3["rebuild_cmds"] = rebuild
    d3["log_parser"] = ""; d3["_p2p_expected"] = p2p
    v3.append(d3)
    # v2: real playground commands if present, else constructed
    d2 = dict(row)
    if rec and rec.get("test_commands"):
        d2["test_cmds"] = rec["test_commands"]; d2["rebuild_cmds"] = rec.get("rebuild_commands", []) or []
        d2["print_cmds"] = rec.get("print_commands", []) or []; d2["log_parser"] = rec.get("log_parser", "") or ""
        npg += 1
    else:
        d2["test_cmds"] = ["bash -lc 'python -m pytest -v -rA --continue-on-collection-errors " + " ".join(files) + "'"]
        d2["rebuild_cmds"] = rebuild; d2["print_cmds"] = []; d2["log_parser"] = ""
    d2["_p2p_expected"] = p2p
    v2.append(d2)
    # v1: generic pytest on P2P files
    d1 = dict(row)
    d1["test_cmds"] = ["bash -lc 'python -m pytest -v -rA --continue-on-collection-errors " + " ".join(files) + "'"]
    d1["rebuild_cmds"] = rebuild; d1["print_cmds"] = []; d1["log_parser"] = ""; d1["_p2p_expected"] = p2p
    v1.append(d1)
    # gold preds
    gold[iid] = {"instance_id": iid, "model_name_or_path": "gold", "model_patch": row.get("patch", "")}

for tag, rows in [("v1", v1), ("v2", v2), ("v3", v3)]:
    f = ROOT / f"data/stage6_100_{tag}.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"  wrote {f.name}: {len(rows)} rows")
gf = ROOT / "stage6/gold_preds_100.json"
gf.write_text(json.dumps(gold, indent=2))
print(f"  wrote gold preds: {gf} ({len(gold)} issues, playground-cmd coverage {npg}/100 for v2)")
print("\nPhase 1 done.")
