# Workflow Script Reference: `run_pouya20_gpt54mini.py`

**Location:** `scripts/workflows/run_pouya20_gpt54mini.py`  
**Python:** `bench_env/bin/python` (Python 3.12)  
**Purpose:** End-to-end pipeline — dataset validation → solver → enhancer comparison

---

## CLI Arguments

```
--run-dir PATH          Run directory (must contain launch_config.json)  [required]
--limit INT             Number of instances to select (default: 20)
--skip-repolaunch       Load repolaunch_passed.jsonl instead of running paul.run
--skip-gold-eval        Load validated_instances.jsonl instead of running gold eval
--skip-baseline         Skip running the baseline solver (reuse existing preds.json)
--skip-enhanced         Skip the enhanced solver
--stop-after-gold-eval  Exit after Stage 2 (useful for dataset validation only)
--enhancer NAME         Enhancer for the enhanced condition (default: llm_append_analysis)
                        Choices: llm_append_analysis, aider, trae, openhands,
                                 mini_swe_agent, swe_agent
--repolaunch-workers N  Parallel paul.run workers (default: 4)
--repolaunch-timeout N  Max seconds per paul.run instance (default: 2400)
--gold-workers N        Parallel gold eval workers (default: 4)
--include-known-bad     Disable DEFAULT_EXCLUDED_INSTANCE_IDS filter
```

---

## Pipeline Stages

### Stage 0 — Instance Selection

Loads `selected_{limit}.jsonl` from the run directory if it exists (cached), otherwise calls `select_instances()` from the dataset.

`select_instances()` applies:
1. `DEFAULT_EXCLUDED_INSTANCE_IDS` — known-bad instances (cloud creds, Poetry hangs, etc.)
2. `SERVICE_HEAVY_REPOS` — repos requiring external services (RabbitMQ, PostGIS, etc.)
3. Repo diversity cap — at most 2 instances per repo
4. Returns first `limit` instances meeting all criteria

> **Important:** Delete `selected_N.jsonl` when changing exclusion lists to force re-selection.

### Stage 1 — RepoLaunch (paul.run)

Calls `paul.run` for each instance to:
1. Build a Docker image with the repo at the correct commit
2. Install dependencies (`pip install -e .`, poetry, etc.)
3. Run "organize" step: identify test commands and verify environment

Output per instance: one of `organize_passed`, `organize_missing`, `setup_failed`, `timeout`, `infra_complex`.

Only `organize_passed` instances proceed to Stage 2.

**Hang detection:** `aws-powertools` repos use `poetry install --extras "all redis ..."` which hangs on network I/O. Symptom: `ss -tnp` shows CLOSE-WAIT socket to `172.66.*.*/443`. Fix: `kill <paul.run PID>` + `docker kill <container>`.

### Stage 2 — Gold Evaluation

Applies the gold patch to each repo and runs F2P + P2P tests via the SWE-bench-Live harness.

An instance is **validated** if `resolved: true` (all F2P tests pass after patch, no P2P regressions).

**Parametrized label repair:** Some instances have parametrized test IDs (e.g., `test_func[param1-True]`) that don't match the non-parametrized IDs stored in the dataset. The script automatically detects these from `post_patch_log.txt` and reruns gold eval with the expanded IDs.

Output: `validated_instances.jsonl`

**Cache skip:** If all `report.json` files already exist in `solver_*_eval/`, evaluation is skipped automatically (avoids redundant Docker runs).

### Stage 3a — Baseline Solver

Runs mini-SWE-agent on original `problem_statement` for each validated instance.

```python
# image_name is overridden with docker_image (our RepoLaunch-built image)
# to prevent mini-SWE-agent from using the original SWE-bench images
row["image_name"] = row["docker_image"]
```

Output: `solver_baseline/preds.json`, `solver_baseline/*/traj.json`

### Stage 3b — Enhanced Solver

1. **Enhancement phase:** Calls the selected enhancer on each validated instance.
   - Enhancer receives `issue` dict (with `problem_statement`, `title`, `repo`, etc.)
   - Returns `{"enhanced_body": "...", "enhanced_title": "...", "enhancement_metadata": {...}}`
   - `enhanced_body` replaces `problem_statement` in the solver input
   - Original text is preserved in enhanced versions that use `append_analysis` strategy

2. **Solver phase:** Runs mini-SWE-agent on enhanced problem statements.

Output: `solver_enhanced_dataset.jsonl`, `solver_enhanced/preds.json`

### Stage 4 — Evaluation

Runs SWE-bench-Live evaluation harness for both baseline and enhanced preds.

For each instance:
- `FAIL_TO_PASS.success` = F2P tests that now pass (good)
- `FAIL_TO_PASS.failure` = F2P tests still failing (bad)
- `PASS_TO_PASS.failure` = previously-passing tests now broken (regression)
- `resolved: true` = all F2P pass AND no P2P regressions

---

## Enhancer Environment Variables

Each enhancer reads its model/endpoint from env vars at **import time** (module-level globals). The workflow sets these before importing the enhancer modules:

| Enhancer | Key env vars | Model format |
|---|---|---|
| `llm_append_analysis` | `OPENAI_COMPAT_MODEL`, `OPENAI_COMPAT_BASE_URL`, `OPENAI_COMPAT_API_KEY` | `gpt-5.4-mini` |
| `aider` | `AIDER_MODEL`, `AIDER_API_BASE`, `AIDER_API_KEY` | `openai/gpt-5.4-mini` |
| `trae` | `TRAE_MODEL`, `TRAE_BASE_URL`, `TRAE_API_KEY` | `gpt-5.4-mini` |
| `openhands` | `OPENHANDS_MODEL`, `OPENHANDS_BASE_URL`, `OPENHANDS_API_KEY` | `gpt-5.4-mini` (→ `openai/gpt-5.4-mini` in config.toml) |
| `mini_swe_agent` | `MINI_MODEL`, `MINI_BASE_URL`, `MINI_API_KEY` | `gpt-5.4-mini` |
| `swe_agent` | `SWEAGENT_MODEL`, `SWEAGENT_BASE_URL`, `SWEAGENT_API_KEY` | `gpt-5.4-mini` (→ `openai/gpt-5.4-mini` in YAML) |

> Since these are module-level globals, env vars **must be set before the first import** of the enhancer module. This works correctly when each enhancer run is a separate OS process.

---

## Progress File Structure (`progress.json`)

```json
{
  "done": 20,
  "remaining": 0,
  "stage": "gold_eval_done",
  "completed_ids": ["Flexget__Flexget-4986", ...],
  "failed_ids": [],
  "repolaunch_passed": [...],
  "repolaunch_failed": [],
  "repolaunch_results": {"Flexget__Flexget-4986": "organize_passed", ...},
  "validated_ids": [...],
  "gold_passed": [...],
  "baseline_resolved": ["ag2ai__faststream-2495", ...],
  "enhanced_resolved": [...],
  "solver_baseline_done": [...],
  "solver_enhanced_done": [...],
  "started_at": "2026-05-05T...",
  "updated_at": "2026-05-05T..."
}
```

> **All keys must be present** in pre-seeded progress files. Missing keys (especially `failed_ids`) cause `KeyError` crashes.

---

## Pre-Seeding a Run (Skip RepoLaunch + Gold Eval)

To reuse existing validated instances in a new run:

```bash
python3 - <<'EOF'
import json, os, shutil
from datetime import datetime, timezone

VALIDATED_SRC = "runs/pouya_final20b_20260505_050130/validated_instances.jsonl"
RUN_DIR = "runs/my_new_run"
os.makedirs(RUN_DIR, exist_ok=True)

rows = [json.loads(l) for l in open(VALIDATED_SRC) if l.strip()]
already_done = [r["instance_id"] for r in rows]

for fname in ["selected_20.jsonl", "repolaunch_passed.jsonl", "validated_instances.jsonl"]:
    with open(f"{RUN_DIR}/{fname}", "w") as f:
        for r in rows: f.write(json.dumps(r) + "\n")

# Copy baseline preds + eval results so --skip-baseline works
os.makedirs(f"{RUN_DIR}/solver_baseline", exist_ok=True)
shutil.copy("runs/pouya_solver20_20260505_063614/solver_baseline/preds.json",
            f"{RUN_DIR}/solver_baseline/preds.json")
shutil.copytree("runs/pouya_solver20_20260505_063614/solver_baseline_eval",
                f"{RUN_DIR}/solver_baseline_eval", dirs_exist_ok=True)

now = datetime.now(tz=timezone.utc).isoformat()
progress = {
    "done": 20, "remaining": 0, "stage": "solver_baseline_eval_done",
    "last_instance_id": already_done[-1],
    "completed_ids": already_done, "failed_ids": [],
    "repolaunch_passed": already_done, "repolaunch_failed": [],
    "repolaunch_results": {iid: "organize_passed" for iid in already_done},
    "validated_ids": already_done, "gold_passed": already_done,
    "baseline_resolved": ["a2aproject__a2a-python-683",
                          "ag2ai__faststream-2495", "astropy__astropy-18753"],
    "enhanced_resolved": [],
    "started_at": now, "updated_at": now,
    "all_instance_ids": already_done,
    "solver_baseline_done": already_done, "solver_enhanced_done": [],
}
with open(f"{RUN_DIR}/progress.json", "w") as f:
    json.dump(progress, f, indent=2)

with open(f"{RUN_DIR}/launch_config.json", "w") as f:
    json.dump({
        "llm_provider_name": "OpenAI",
        "model_config": {"model_name": "gpt-5.4-mini", "temperature": 0.0},
        "mode": {"setup": True, "organize": True},
        "disable_timemachine": True, "max_workers": 1, "max_trials": 1,
        "max_steps_setup": 12, "max_steps_verify": 4, "max_steps_organize": 15,
        "cmd_timeout": 30, "os": "linux", "overwrite": False,
        "print_to_console": True, "image_prefix": "pouya20gpt-stage12/dev",
    }, f, indent=2)
print(f"Run dir ready: {RUN_DIR}")
EOF

OPENAI_API_KEY_FILE=$PWD/.claude/settings.local.json \
bench_env/bin/python scripts/workflows/run_pouya20_gpt54mini.py \
  --run-dir runs/my_new_run \
  --limit 20 \
  --skip-repolaunch \
  --skip-gold-eval \
  --skip-baseline \
  --enhancer my_enhancer_id
```

---

## Monitoring

```bash
# One-shot dashboard
cd /home/22pf2/BenchmarkLLMAgent && bench_env/bin/python scripts/watch_enhancers.py --once

# Live dashboard (30s refresh)
watch -n 30 'cd /home/22pf2/BenchmarkLLMAgent && bench_env/bin/python scripts/watch_enhancers.py --once'

# Solver progress per enhancer
for e in aider trae openhands mini_swe_agent swe_agent; do
  traj=$(find runs/pouya_enhanced_${e}_20260505_084500/solver_enhanced \
         -name "*.traj.json" 2>/dev/null | wc -l)
  resolved=$(find runs/pouya_enhanced_${e}_20260505_084500/solver_enhanced_eval \
             -name "report.json" 2>/dev/null \
             | xargs grep -l '"resolved": true' 2>/dev/null | wc -l)
  echo "$e: solver $traj/20 done | resolved $resolved"
done

# Check stale processes
ps -eo pid,ppid,stat,etime,cmd \
  | grep -E 'run_pouya20_gpt54mini|mini_sweagent|evaluation\.py|paul\.run' \
  | grep -v grep

# Check running Docker containers
docker ps --format 'table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Names}}' \
  | grep 'git-launch\|minisweagent'
```
