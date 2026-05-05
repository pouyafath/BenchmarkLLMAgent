# Pouya-20 SWE-bench Experiment

**Date started:** 2026-05-04  
**Status:** Solver + enhancer comparison running  
**Dataset:** `data/samples/pouya_dataset_2026_swebench_style_f2p_p2p/dataset.jsonl`  
**Main script:** `scripts/workflows/run_pouya20_gpt54mini.py`

---

## Goal

Build a 20-instance SWE-bench-style gold-validated dataset from Pouya's 2026 GitHub issues collection, then run a baseline solver vs. multiple enhancer-conditioned solver comparisons, all using **gpt-5.4-mini**.

---

## Pipeline Overview

```
Stage 1: RepoLaunch (GPT-5.4-mini)
   paul.run → setup + organize each repo in Docker
   Output: repolaunch_passed.jsonl

Stage 2: Gold Evaluation
   Apply gold patch to each repo, run F2P + P2P tests
   Output: validated_instances.jsonl (20 gold-verified rows)

Stage 3a: Baseline Solver
   mini-SWE-agent (gpt-5.4-mini, temp=0.0) on raw problem statements
   Output: solver_baseline/preds.json

Stage 3b: Enhanced Solver (×N enhancers)
   Enhancer rewrites problem_statement → mini-SWE-agent solves enhanced version
   Output: solver_enhanced/preds.json per enhancer

Stage 4: Evaluation
   SWE-bench-Live harness checks F2P + P2P pass/fail per patch
   Output: solver_*_eval/*/report.json
```

---

## Dataset: 20 Gold-Validated Instances

Canonical file: `runs/pouya_final20b_20260505_050130/validated_instances.jsonl`

All 20 instances verified with `resolved: true` (gold patch passes all F2P tests).

| # | Instance ID | F2P Tests |
|---|---|---|
| 1 | Flexget__Flexget-4986 | 2 |
| 2 | MDAnalysis__mdanalysis-5071 | 1 |
| 3 | MDAnalysis__mdanalysis-5113 | 2 |
| 4 | PennyLaneAI__pennylane-7474 | 5 |
| 5 | PennyLaneAI__pennylane-7668 | 3 |
| 6 | SQLMesh__sqlmesh-5077 | 13 |
| 7 | SQLMesh__sqlmesh-5081 | 1 |
| 8 | a2aproject__a2a-python-564 | 4 |
| 9 | a2aproject__a2a-python-683 | 5 |
| 10 | ag2ai__faststream-2495 | 3 |
| 11 | ag2ai__faststream-2544 | 1 |
| 12 | amazon-science__chronos-forecasting-407 | 2 |
| 13 | anthropics__anthropic-sdk-python-1264 | 4 |
| 14 | astropy__astropy-18105 | 12 |
| 15 | astropy__astropy-18753 | 1 |
| 16 | aws-powertools__powertools-lambda-python-7026 | 2 |
| 17 | beeware__toga-3665 | 2 |
| 18 | dgtlmoon__changedetection.io-3659 | 1 |
| 19 | dlt-hub__dlt-2935 | 2 |
| 20 | dlt-hub__dlt-3048 | 16 (parametrized, via label repair) |

**Note on instance 20:** `dlt-hub__dlt-3048` F2P tests are parametrized (`test_get_nested_tables[0-True]`, etc.). The standard gold eval failed to collect them; the parametrized label repair pass discovered and validated all 16 variants.

---

## Excluded Instances (Known Issues)

Added to `DEFAULT_EXCLUDED_INSTANCE_IDS` in the workflow script:

| Instance | Reason |
|---|---|
| `aws-powertools__powertools-lambda-python-7940` | Poetry install hangs on network I/O (CLOSE-WAIT socket) |
| `aws-powertools__powertools-lambda-python-7028/7253/7901/7980/7083/8089/8092` | Same Poetry hang pattern |
| `dgtlmoon__changedetection.io-3465` | Gold patch fails F2P + P2P tests |
| `dlt-hub__dlt-2951` | Databricks cloud credentials required (`DatabricksCredentials`) |
| `dlt-hub__dlt-3096` + 13 others | Preemptive: cloud service dependencies or test ID mismatches |
| `GeoNode__geonode-13769` | Requires PostgreSQL/PostGIS infrastructure |

---

## Solver Configuration

**Solver:** mini-SWE-agent v2.2.5  
**Model:** `gpt-5.4-mini`, temperature=0.0 (deterministic)  
**Workers:** 2 parallel instances  
**Config files:**
- `SWE-Bench_Replication/mini-SWE-agent/src/minisweagent/config/benchmarks/swebench_backticks.yaml`
- `SWE-Bench_Replication/config/openai_gpt54mini_override.yaml`

The solver runs a ReAct loop (THOUGHT + bash command) inside each issue's Docker container (`/testbed`), edits source files, and submits a git diff patch.

---

## Enhancers Tested

All enhancers use **gpt-5.4-mini** via `https://api.openai.com/v1`.

| Enhancer ID | Tool | What it produces | Env vars |
|---|---|---|---|
| `llm_append_analysis` | Direct LLM call | Appends structured analysis block (root cause, affected components, fix direction) **below** the original issue text | `OPENAI_COMPAT_*` |
| `aider` | `bench_env/bin/aider` CLI | Rewrites/expands the issue with code context | `AIDER_MODEL`, `AIDER_API_BASE`, `AIDER_API_KEY` |
| `trae` | `/home/22pf2/trae-agent/.venv/bin/trae-cli` | Enhanced title + body from agent trajectory | `TRAE_BASE_URL`, `TRAE_MODEL`, `TRAE_API_KEY` |
| `openhands` | `python -m openhands.core.main` (headless) | Enhanced title + body with repro steps | `OPENHANDS_BASE_URL`, `OPENHANDS_MODEL`, `OPENHANDS_API_KEY` |
| `mini_swe_agent` | `bench_env/bin/mini` CLI | Enhanced title + body with file references | `MINI_BASE_URL`, `MINI_MODEL`, `MINI_API_KEY` |
| `swe_agent` | `bench_env/bin/sweagent` CLI | Enhanced title + body from agent output | `SWEAGENT_BASE_URL`, `SWEAGENT_MODEL`, `SWEAGENT_API_KEY` |

**Key distinction — `llm_append_analysis` vs native agents:**
- `llm_append_analysis`: never modifies original text; appends an analysis section. Non-agentic (single LLM call).
- Native agents (aider, trae, openhands, mini, sweagent): run a full agentic loop and produce a new `enhanced_body` that replaces `problem_statement` in the solver input.

---

## Baseline Results (Run Once, Reused for All Enhancer Comparisons)

**Run directory:** `runs/pouya_solver20_20260505_063614`

| Metric | Value |
|---|---|
| Instances | 20/20 |
| Resolved | **3/20 (15%)** |
| Resolved IDs | `a2aproject__a2a-python-683`, `ag2ai__faststream-2495`, `astropy__astropy-18753` |

The baseline is deterministic (temp=0.0) and is reused across all enhancer comparisons without re-running.

---

## Enhancer Comparison Results

**Run directories:** `runs/pouya_enhanced_{enhancer}_20260505_084500/`

> Results below are from in-progress evaluation (2026-05-05). Final numbers may change slightly for runs still completing.

| Enhancer | Resolved / 20 | Resolved IDs | vs Baseline |
|---|---|---|---|
| **Baseline** | **3** | `a2a-683`, `faststream-2495`, `astropy-18753` | — |
| `llm_append_analysis` | 3 | same 3 | = 0 |
| `aider` | 1* | `faststream-2495` | − 2 |
| `trae` | 2* | `faststream-2495`, `Flexget-4986` | − 1 / new: Flexget |
| `openhands` | 3* | `a2a-683`, `faststream-2495`, `astropy-18753` | = 0 |
| `mini_swe_agent` | 2* | `a2a-683`, `faststream-2495` | − 1 |
| `swe_agent` | — | running | — |

*Partial results — eval still completing.

**Notable finding:** `trae` unlocked `Flexget__Flexget-4986` which baseline/llm_append failed (baseline passed F2P but broke P2P; trae-enhanced version resolved cleanly).

---

## Run Directories Reference

| Purpose | Directory |
|---|---|
| 20-instance validated dataset | `runs/pouya_final20b_20260505_050130/` |
| Baseline solver (canonical) | `runs/pouya_solver20_20260505_063614/` |
| Enhanced: llm_append_analysis | `runs/pouya_solver20_20260505_063614/` (same run) |
| Enhanced: aider | `runs/pouya_enhanced_aider_20260505_084500/` |
| Enhanced: trae | `runs/pouya_enhanced_trae_20260505_084500/` |
| Enhanced: openhands | `runs/pouya_enhanced_openhands_20260505_084500/` |
| Enhanced: mini_swe_agent | `runs/pouya_enhanced_mini_swe_agent_20260505_084500/` |
| Enhanced: swe_agent | `runs/pouya_enhanced_swe_agent_20260505_084500/` |

---

## How to Re-Run or Extend

### Run a new enhancer on the same 20 instances

```bash
# 1. Create a run directory pre-seeded with validated instances + baseline preds
python3 - <<'EOF'
import json, os, shutil
from datetime import datetime, timezone

SRC = "runs/pouya_final20b_20260505_050130/validated_instances.jsonl"
BASELINE_PREDS = "runs/pouya_solver20_20260505_063614/solver_baseline/preds.json"
BASELINE_EVAL = "runs/pouya_solver20_20260505_063614/solver_baseline_eval"
RUN_DIR = "runs/pouya_enhanced_MYENHANCER_YYYYMMDD"
ENHANCER = "my_enhancer_id"

os.makedirs(RUN_DIR, exist_ok=True)
rows = [json.loads(l) for l in open(SRC) if l.strip()]
for fname in ["selected_20.jsonl", "repolaunch_passed.jsonl", "validated_instances.jsonl"]:
    with open(f"{RUN_DIR}/{fname}", "w") as f:
        for r in rows: f.write(json.dumps(r) + "\n")

os.makedirs(f"{RUN_DIR}/solver_baseline", exist_ok=True)
shutil.copy(BASELINE_PREDS, f"{RUN_DIR}/solver_baseline/preds.json")
shutil.copytree(BASELINE_EVAL, f"{RUN_DIR}/solver_baseline_eval", dirs_exist_ok=True)

# add launch_config.json and progress.json similarly to existing runs
EOF

# 2. Launch
OPENAI_API_KEY_FILE=$PWD/.claude/settings.local.json \
bench_env/bin/python scripts/workflows/run_pouya20_gpt54mini.py \
  --run-dir runs/pouya_enhanced_MYENHANCER_YYYYMMDD \
  --limit 20 \
  --skip-repolaunch \
  --skip-gold-eval \
  --skip-baseline \
  --enhancer my_enhancer_id
```

### Monitor all runs

```bash
# Dashboard (refreshes every 30s)
watch -n 30 'cd /home/22pf2/BenchmarkLLMAgent && bench_env/bin/python scripts/watch_enhancers.py --once'

# Per-enhancer solver progress
for e in aider trae openhands mini_swe_agent swe_agent; do
  traj=$(find runs/pouya_enhanced_${e}_20260505_084500/solver_enhanced -name "*.traj.json" 2>/dev/null | wc -l)
  resolved=$(find runs/pouya_enhanced_${e}_20260505_084500/solver_enhanced_eval -name "report.json" 2>/dev/null | xargs grep -l '"resolved": true' 2>/dev/null | wc -l)
  echo "$e: solver $traj/20 done, resolved $resolved"
done
```

---

## Known Bugs Fixed During This Experiment

| Bug | Symptom | Fix |
|---|---|---|
| `KeyError: 'failed_ids'` | Pre-seeded `progress.json` missing `failed_ids` key | `progress.setdefault("failed_ids", [])` in workflow |
| Stale `selected_N.jsonl` cache | Excluded instances still selected on re-run | Always use fresh run directories |
| Redundant baseline re-evaluation | 5 simultaneous chronos containers (35 min each) | Added cache-skip: if all `report.json` exist, skip re-eval subprocess |
| `aws-powertools` Poetry hang | `paul.run` stuck in CLOSE-WAIT socket state for 20+ min | Added all `aws-powertools-*` (except 7026) to exclusion list |
| `dlt-hub__dlt-2951` Databricks credentials | `ConfigFieldMissingException: Missing fields: ['catalog']` | Added to exclusion list |
| Module-level enhancer env vars | `TRAE_MODEL` etc. read at import time, not call time | Set env vars before first import of enhancer modules |
