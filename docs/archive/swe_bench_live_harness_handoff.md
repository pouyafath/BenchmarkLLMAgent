# BenchmarkLLMAgent — SWE-bench Harness Migration Handoff

> **For the next agent:** Read this entire file before taking any action. It contains everything you need to understand the project, its current state, and your specific task.

---

## 1. Project Goal

This project benchmarks **LLM-based Issue Enhancement Agents** for GitHub issues.

The core loop:
```
Original Issue → Enhancement Agent → Enhanced Issue → Solver Agent → Patch
```

We measure whether enhancement improves the **solver's patch quality**, using:
- **Content similarity** (patch vs. ground truth PR diff)
- **File overlap** (did the solver touch the right files?)
- **FAIL→PASS / PASS→PASS test outcomes** via the SWE-bench harness

**Paper 3** (IEEE TSE target) benchmarks 5+ enhancement agents (Category A: ready-to-use, and Category B: framework-built) on 10–200 GitHub issues from SWE-bench-Live.

---

## 2. Research Questions

| RQ | Question |
|----|----------|
| **RQ1** | How do ready-to-use agents (Category A) compare at enhancing GitHub issues? |
| **RQ2** | How do framework-built agents (Category B) compare? |
| **RQ3** | Does enhancement actually improve automated solver performance? |
| **RQ4** | How do results vary by issue type and complexity? |

---

## 3. Environment & Setup

### Directory
```
/home/22pf2/BenchmarkLLMAgent/
```

### Python Virtual Environment
```bash
# Use bench_env for all scripts
source /home/22pf2/BenchmarkLLMAgent/bench_env/bin/activate
# Or prefix commands with ./bench_env/bin/python
```

### LLM Inference
- **Ollama** (port 11434): `gpt-oss:120b` — used for enhancement and solving
- **vLLM** (port 8001): `gemma-3-12b-it` — used when Ollama is too slow
  - Start vLLM: `CUDA_VISIBLE_DEVICES=1,3,4,5 ./issue_enhancer_py312/bin/python -m vllm.entrypoints.openai.api_server --model google/gemma-3-12b-it --served-model-name gemma-3-12b-it --port 8001 --tensor-parallel-size 4`
  - Then set `USE_VLLM=1` before running scripts

### TRAE Agent (Category A, requires special setup)
```bash
# Located at /home/22pf2/trae-agent
# Must be installed via uv sync
cd /home/22pf2/trae-agent && uv sync
```

---

## 4. Project Structure

```
BenchmarkLLMAgent/
├── src/
│   ├── enhancers/
│   │   ├── ready_to_use/          # Category A agents (trae, openhands, mini_swe_agent, live_swe_agent, simple_enhancer)
│   │   └── framework_built/       # Category B agents (simple_enhancer etc.)
│   ├── solvers/                   # Solving agents (openai_agents_sdk, autogen, etc.)
│   ├── evaluation/                # Statistical analysis tools
│   └── utils/                    # GitHub client, patch utils, LLM client
├── scripts/
│   ├── data/
│   │   └── prepare_swe_bench_live_samples.py   # Downloads 10 issues from HuggingFace
│   ├── enhancers/
│   │   ├── run_enhancement_benchmark.py        # Runs enhancers on all issues
│   │   └── run_solving_after_enhancement.py    # Runs solver after enhancement
│   ├── solvers/
│   │   └── run_simple_solver.py                # Baseline solver (no enhancement)
│   ├── reports/
│   │   └── generate_enhancement_report_multi_agent.py  # Summary report
│   └── evaluate/
│       ├── run_swe_bench_evaluation.sh         # Official SWE-bench harness runner ← KEY FILE
│       ├── run_instance.py                     # Custom lightweight evaluator (deprecated as primary)
│       ├── run_instance_custom_backup.py       # Backup of custom evaluator
│       └── run_evaluation_pipeline.py          # Pipeline wrapper for run_instance.py
├── data/
│   ├── samples/swe_bench_live_10_samples.json  # 10 issues (seed=42, verified split)
│   └── ground_truth_swe_bench_live/            # Full SWE-bench-Live rows with FAIL_TO_PASS etc.
├── results/
│   ├── enhancement_benchmark/                  # Per-issue enhancement outputs
│   └── solving_after_enhancement/             # Per-issue solver patch outputs
├── eval_results/
│   ├── swebench/                               # SWE-bench harness output goes here
│   │   └── iteration1_eval/                   # Results from SWE-bench harness run
│   ├── iteration1_eval_preds.jsonl             # Predictions JSONL for SWE-bench harness ← IMPORTANT
│   └── predictions.jsonl                       # Earlier prediction file (check if valid)
├── docs/
│   ├── ITERATION1_REPORT.md                   # Full Iteration 1 results report
│   ├── research_plan.md                       # Active research plan
│   └── swe_bench_live_harness_handoff.md      # THIS FILE
├── ROADMAP.md                                  # Handoff guide; keep updated
└── README.md                                  # Full project overview
```

---

## 5. Dataset

- **Source**: HuggingFace `SWE-bench-Live/SWE-bench-Live` (`verified` split, seed=42)
- **Size for Iteration 1**: 10 issues
- **Sample file**: `data/samples/swe_bench_live_10_samples.json`
- **Ground truth directory**: `data/ground_truth_swe_bench_live/` (full HuggingFace rows, including `FAIL_TO_PASS`, `PASS_TO_PASS`, `test_patch`, `base_commit`)

The 10 issues are:
| Instance ID | Repo |
|-------------|------|
| `instructlab__instructlab-3135` | instructlab/instructlab |
| `matplotlib__matplotlib-28734` | matplotlib/matplotlib |
| `instructlab__instructlab-1762` | instructlab/instructlab |
| `theoehrly__fast-f1-701` | theOehrly/Fast-F1 |
| `aws-cloudformation__cfn-lint-3764` | aws-cloudformation/cfn-lint |
| `reflex-dev__reflex-4129` | reflex-dev/reflex |
| `pytorch__torchtune-1697` | pytorch/torchtune |
| `reflex-dev__reflex-3842` | reflex-dev/reflex |
| `koxudaxi__datamodel-code-generator-2334` | koxudaxi/datamodel-code-generator |
| `keras-team__keras-20125` | keras-team/keras |

> **Note**: The ground truth files in `data/ground_truth_swe_bench_live/` use the filename pattern `{owner}__{repo}__{issue_number}.json`. The SWE-bench harness uses `instance_id` which follows the format `{owner}__{repo}-{pull_number}`.

---

## 6. Iteration 1: What Has Been Done

### Enhancement Results ✅
All 5 enhancers ran on 10 issues. Results are in `results/enhancement_benchmark/`:
- Files: `{agent}__{owner}__{repo}__{issue_num}.json`
- Contains: `enhanced_title`, `enhanced_body`, timing, metadata

### Solving Results ✅
The solver (`openai_agents_sdk` with `gpt-oss:120b`) ran:
- **Baseline**: `results/pilot_solver_benchmark/simple_solver__*.json`
- **After enhancement**: `results/solving_after_enhancement/openai_agents_sdk_after_enhancement__{agent}__*.json`
- Each file contains a `patch` field with the unified diff

### Content-Similarity Metrics ✅
- Computed and reported in `results/enhancement_benchmark/enhancement_report_multi_agent.json`
- Summary: `simple_enhancer` (+0.0361 delta), `trae` (+0.0330), `mini_swe_agent` (+0.0218)

### SWE-bench Harness: PARTIALLY STARTED ❌
- A `predictions.jsonl` file was generated at `eval_results/iteration1_eval_preds.jsonl`
- A script `scripts/evaluate/run_swe_bench_evaluation.sh` exists to invoke the harness
- **The harness has NOT successfully completed** — zombie processes were killed; results in `eval_results/swebench/iteration1_eval/` are incomplete or wrong

---

## 7. Current Problem & Next Task

### Decision Made
The **custom lightweight evaluator** (`run_instance.py`) was originally planned for testing, but it:
- Hangs on pip install for ML-heavy repos (e.g., `instructlab` with vLLM, PyTorch)
- Doesn't use the correct isolated per-repo Docker images
- Is not publishable-grade for the paper

**Decision: Migrate to the official SWE-bench harness** (`swebench.harness.run_evaluation`), which:
- Uses pre-built Docker images for every SWE-bench-Live instance
- Automatically applies `test_patch` and runs `test_cmds` correctly
- Produces `report.json` with FAIL_TO_PASS/PASS_TO_PASS matrices
- Is the standard referenced in all SWE-bench publications

### Your Next Task: End-to-End SWE-bench Harness Evaluation

**Goal**: Use `swebench.harness.run_evaluation` to evaluate all Iteration 1 patches through the official test harness and produce a final `report.json` for each agent–issue pair.

---

## 8. Step-by-Step Instructions for Next Agent

### Step 1: Verify swebench is installed
```bash
./bench_env/bin/python -c "import swebench; print(swebench.__version__)"
```
If not installed:
```bash
./bench_env/bin/pip install swebench
```

### Step 2: Understand the predictions format
The SWE-bench harness requires a JSONL file where each line has:
```json
{"instance_id": "owner__repo-NNNN", "model_patch": "diff --git ...", "model_name_or_path": "agent_name"}
```

> **CRITICAL**: `instance_id` must match the SWE-bench-Live dataset exactly (format: `{owner}__{repo}-{pull_number}`, e.g., `instructlab__instructlab-3136`).

### Step 3: Build the predictions JSONL

The solver patches are in `results/solving_after_enhancement/`. You need to convert them to the harness format. Write a script like:

```python
# scripts/evaluate/build_predictions_jsonl.py
import json
from pathlib import Path

SOLVING_DIR = Path("results/solving_after_enhancement")
OUTPUT_FILE = Path("eval_results/swebench/iteration1_eval_preds.jsonl")
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

# Map from (owner, repo, issue_num) -> SWE-bench instance_id
# You'll need to load data/samples/swe_bench_live_10_samples.json
# and data/ground_truth_swe_bench_live/*.json to get the right instance_id

with open("data/samples/swe_bench_live_10_samples.json") as f:
    samples = {
        f"{s['pr_owner']}__{s['pr_repo']}__{s['issue_number']}": s['_swe_live_instance_id']
        for s in json.load(f)['issues']
    }

with open(OUTPUT_FILE, "w") as out:
    for pred_file in sorted(SOLVING_DIR.glob("*.json")):
        parts = pred_file.stem.split("__")
        if len(parts) != 5:
            continue
        # parts: [solver_id, agent_id, owner, repo, issue_num]
        owner, repo, num = parts[2], parts[3], parts[4]
        key = f"{owner}__{repo}__{num}"
        instance_id = samples.get(key)
        if not instance_id:
            print(f"WARNING: no instance_id for {key}")
            continue
        
        with open(pred_file) as f:
            pred = json.load(f)
        patch = pred.get("patch", "")
        if not patch:
            continue
        
        agent_id = parts[1]
        record = {
            "instance_id": instance_id,
            "model_patch": patch,
            "model_name_or_path": f"openai_agents_sdk_after_{agent_id}"
        }
        out.write(json.dumps(record) + "\n")

print(f"Written to {OUTPUT_FILE}")
```

### Step 4: Run the SWE-bench harness

```bash
./bench_env/bin/python -m swebench.harness.run_evaluation \
  --predictions_path eval_results/swebench/iteration1_eval_preds.jsonl \
  --max_workers 4 \
  --run_id iteration1_eval \
  --dataset_name SWE-bench-Live/SWE-bench-Live \
  --split verified \
  --cache_level env
```

> **Note**: `--max_workers 4` runs 4 Docker containers in parallel. Reduce to 1 if memory is limited.
> **Note**: Docker must be running. Each instance uses a pre-built image.
> **Note**: This can take a long time (hours) for many instances. Start with 1 instance to verify:
>
> Filter to just 1 instance by using `--filter instance_id=instructlab__instructlab-3136` if the harness supports it, or create a jsonl with just 1 line.

### Step 5: Inspect results

The harness writes results to `eval_results/swebench/iteration1_eval/`:
```
eval_results/swebench/iteration1_eval/
├── logs/
│   └── {instance_id}/
│       ├── test_output.txt       # Full pytest output
│       ├── report.json           # PASS/FAIL per test
│       └── instance.log          # Container logs
└── predictions.json              # Summary of resolved instances
```

Parse `report.json` for:
- `tests_status`: dict of test_name → PASSED/FAILED
- `resolved` (bool): whether all FAIL_TO_PASS tests now pass

### Step 6: Aggregate results into the paper metric

Write a report script in `scripts/reports/` that:
1. Reads each `report.json` from `eval_results/swebench/iteration1_eval/logs/`
2. Counts `resolved=True` per (agent, issue)
3. Computes per-agent `%_resolved` (SWE-bench resolution rate)
4. Compares baseline (no enhancement) patches vs. after-enhancement patches
5. Outputs a table similar to Section 5.1 in `docs/ITERATION1_REPORT.md`

---

## 9. Existing Files of Interest

| File | Purpose |
|------|---------|
| `scripts/evaluate/run_swe_bench_evaluation.sh` | Existing partial harness invocation script |
| `eval_results/iteration1_eval_preds.jsonl` | Existing predictions file (verify format before using) |
| `eval_results/swebench/iteration1_eval/` | Partial harness output (incomplete, may need to re-run) |
| `scripts/evaluate/run_instance_custom_backup.py` | Old custom evaluator (backup, do not use as primary) |
| `results/solving_after_enhancement/` | All 44 agent–issue patches to evaluate |

---

## 10. Key Warnings

> **WARNING: Zombie processes**
> Several long-running background Python processes (`run_instance.py`, `run_evaluation_pipeline.py`) were running for 160+ hours and may still be alive. Kill them before starting:
> ```bash
> pkill -f "run_instance.py"
> pkill -f "run_evaluation_pipeline.py"
> docker ps -q | xargs docker kill
> ```

> **WARNING: instance_id format**
> The SWE-bench harness uses `instance_id` in the format `owner__repo-PULL_NUMBER` (pull number, NOT issue number). The `_swe_live_instance_id` field in `data/samples/swe_bench_live_10_samples.json` contains the correct value.

> **WARNING: HuggingFace token**
> Loading SWE-bench-Live from HuggingFace requires a valid `HF_TOKEN` environment variable. Set it before running any HF dataset commands.

---

## 11. Contact & Paper Context

- **PI**: Pouya Fathollahzadeh (pouya.f@...)
- **Post-doc advisor (Hao)**: Suggested using the official SWE-bench Docker harness for reproducibility
- **Target venue**: IEEE Transactions on Software Engineering (TSE)
- **Metric goal**: Show that our enhancement agents improve the SWE-bench resolution rate (`resolved=True`) compared to the non-enhanced baseline
