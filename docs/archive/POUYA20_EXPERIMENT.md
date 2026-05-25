# Pouya-20 SWE-bench Experiment

**Date started:** 2026-05-04  
**Status:** Complete (2026-05-11)
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

## Native CLI Validation (Pouya-5, 2026-05-09)

Before relaunching the full native-agent enhancement pipeline, the five native CLI enhancers were validated on the first 5 canonical Pouya-20 instances.

**Command:**

```bash
bench_env/bin/python scripts/enhancers/run_native_cli_pouya5_validation.py \
  --limit 5 \
  --output-dir runs/native_cli_pouya5_20260509
```

**Artifacts:**
- Summary: `runs/native_cli_pouya5_20260509/SUMMARY.json`
- Raw per-agent/per-issue results: `runs/native_cli_pouya5_20260509/raw_results/*.json`
- Detailed report: `docs/analysis/NATIVE_CLI_POUYA5_VALIDATION_2026-05-09.md`

| Agent | Real / Total | Failures | Weak Outputs | Parse Source |
|---|---:|---:|---:|---|
| `aider` | 5/5 | 0 | 0 | `explicit_markers` x5 |
| `trae` | 5/5 | 0 | 0 | `trajectory` x5 |
| `openhands` | 5/5 | 0 | 0 | `strict_markers` x5 |
| `mini_swe_agent` | 5/5 | 0 | 0 | `strict_markers` x5 |
| `swe_agent` | 5/5 | 0 | 0 | `trajectory` x5 |

Corrected result after reviewer follow-up: 25/25 final native CLI calls returned `enhancer_type: real`, changed title/body text, and passed basic output-quality checks. One SWE-agent result (`PennyLaneAI__pennylane-7668`) was recovered from valid trajectory output after the CLI timed out before calling `submit`; it is marked with timeout metadata.

Two SWE-agent parser safeguards were added during this validation:
- accept only trajectory content for SWE-agent benchmark parsing, not stdout/stderr logs
- reject timeout-contaminated or structurally weak trajectory bodies before marking a result as real
- scan `history`, `trajectory`, `messages`, and `info.submission` trajectory schemas
- preserve parseable trajectory output when the CLI times out after writing the enhancement

All five native enhancers are clean on this enhancer-only 5-issue validation.

---

## Native CLI Solver Comparison (Pouya-5, 2026-05-09)

The validated native enhancer outputs were then passed to the canonical mini-SWE-agent solver and evaluated with the SWE-bench-Live harness.

**Command:**

```bash
bench_env/bin/python scripts/enhancers/run_pouya5_solver_comparison.py \
  --output-dir runs/pouya5_native_solver_comparison_20260509 \
  --solver-workers 2 \
  --eval-workers 2
```

**Artifacts:**
- Summary: `runs/pouya5_native_solver_comparison_20260509/summary.json`
- Run report: `runs/pouya5_native_solver_comparison_20260509/ANALYSIS.md`
- Detailed report: `docs/analysis/POUYA5_NATIVE_SOLVER_COMPARISON_2026-05-09.md`

| Condition | Solver Inputs | Predictions | Enhancement Failures | Solver Missing | Empty Patches | Resolved / Evaluated | Effective Resolved / 5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 5 | 5 | 0 | 0 | 0 | 0/5 | 0/5 |
| `aider` | 5 | 5 | 0 | 0 | 0 | 0/5 | 0/5 |
| `trae` | 5 | 5 | 0 | 0 | 0 | 0/5 | 0/5 |
| `openhands` | 5 | 5 | 0 | 0 | 0 | 0/5 | 0/5 |
| `mini_swe_agent` | 5 | 5 | 0 | 0 | 0 | 0/5 | 0/5 |
| `swe_agent` | 5 | 5 | 0 | 0 | 1 | 0/5 | 0/5 |

No native enhancer improved the final `resolved` score on this five-issue subset. `aider`, `trae`, and `mini_swe_agent` did improve `PennyLaneAI__pennylane-7474` from 5 failing F2P tests to 0 failing F2P tests, but all still failed 20 P2P tests, so the issue remained unresolved.

Pre-full-run blockers:
- `swe_agent` still produced one empty solver patch on `PennyLaneAI__pennylane-7474`.
- All five native enhancers are runnable end to end on Pouya-5, but this pre-flight does not show a resolution improvement.

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

## Enhancer Comparison Results (Final — 2026-05-10)

**Canonical report:** `runs/pouya20_native_solver_comparison_fixed/ANALYSIS.md`

| Condition | Enh. Failures | Empty Patches | Resolved / 20 | Delta |
|---|:---:|:---:|:---:|:---:|
| **Baseline** | 0 | 0* | **3/20 (15%)** | — |
| **aider** | 0 | 3 | **3/20 (15%)** | 0 |
| **trae** | 0 | 3 | **2/20 (10%)** | −1 |
| **openhands** | 0 | 3 | **2/20 (10%)** | −1 |
| **mini_swe_agent** | 3→0** | 2 | **2/20 (10%)** | −1 |
| **swe_agent** | 1 | 3 | **1/20 (5%)** | −2 |

*Baseline 0 empty patches because it ran on 2026-05-05 when dlt-hub Docker images still existed. Those images have since been deleted. See [Docker Image Status](#docker-image-status) below.

**mini_swe_agent originally had 3 enhancement failures (template leak bug); fixed and rerun on 2026-05-11.

**Key findings:**
- Enhancement does **not** improve solver success rate. All enhancers match or underperform baseline.
- The same 3 baseline-solvable issues dominate; no enhancer unlocks new resolutions.
- `dlt-hub` issues produce empty solver patches due to missing Docker images (infrastructure, not agent quality).

Resolved IDs:
- Baseline / aider: `a2aproject__a2a-python-683`, `ag2ai__faststream-2495`, `astropy__astropy-18753`
- trae: `a2aproject__a2a-python-683`, `ag2ai__faststream-2495`
- openhands: `ag2ai__faststream-2495`, `astropy__astropy-18753`
- mini_swe_agent: `ag2ai__faststream-2495`, `astropy__astropy-18753`
- swe_agent: `a2aproject__a2a-python-683`

---

## Second Solver Check: SWE-agent Solver (2026-05-11)

To test whether the enhancer conclusion depends on the mini-SWE-agent solver, the same 20 validated Pouya instances and the same five native-enhanced datasets were rerun with SWE-agent as the solver.

**Artifacts:**
- Summary: `runs/pouya20_sweagent_solver_comparison_20260511/summary.json`
- Report: `runs/pouya20_sweagent_solver_comparison_20260511/ANALYSIS.md`
- Runner: `scripts/enhancers/run_pouya20_sweagent_solver_comparison.py`

| Condition | Solver Inputs | Enhancement Failures | Empty Patches | Resolved / 20 | Delta vs SWE-agent baseline |
|---|---:|---:|---:|---:|---:|
| Baseline | 20 | 0 | 2 | **3/20** | -- |
| `aider` | 20 | 0 | 3 | **3/20** | 0 |
| `trae` | 20 | 0 | 2 | **3/20** | 0 |
| `openhands` | 20 | 0 | 2 | **2/20** | -1 |
| `mini_swe_agent` | 20 | 0 | 1 | **1/20** | -2 |
| `swe_agent` | 19 | 1 | 4 | **1/20** | -2 |

Resolved IDs:
- Baseline / aider / trae: `a2aproject__a2a-python-683`, `ag2ai__faststream-2495`, `astropy__astropy-18753`
- openhands: `ag2ai__faststream-2495`, `astropy__astropy-18753`
- mini_swe_agent: `ag2ai__faststream-2495`
- swe_agent: `a2aproject__a2a-python-683`

`amazon-science__chronos-forecasting-407` repeatedly hung during SWE-bench-Live evaluation and was conservatively counted unresolved for every condition. The `swe_agent` enhanced dataset has 19 solver inputs because `astropy__astropy-18753` remains an enhancement failure in that condition.

This second-solver check supports the same project-level conclusion as the mini-SWE-agent v2 run: native issue enhancement did not improve final resolved count on Pouya-20.

---

## Third Solver Check: Aider Solver (2026-05-11)

To add another solver architecture, the same 20 validated Pouya instances and same five native-enhanced datasets were rerun with native Aider CLI as the solver. Aider solved by copying each RepoLaunch Docker image's `/testbed` checkout to a local Git worktree, running `bench_env/bin/aider`, and evaluating the resulting git diff with the same SWE-bench-Live evaluator.

**Artifacts:**
- Summary: `runs/pouya20_aider_solver_comparison_20260511/summary.json`
- Report: `runs/pouya20_aider_solver_comparison_20260511/ANALYSIS.md`
- Runner: `scripts/enhancers/run_pouya20_aider_solver_comparison.py`

| Condition | Solver Inputs | Enhancement Failures | Empty Patches | Resolved / 20 | Delta vs Aider baseline |
|---|---:|---:|---:|---:|---:|
| Baseline | 20 | 0 | 9 | **2/20** | -- |
| `aider` | 20 | 0 | 0 | **3/20** | +1 |
| `trae` | 20 | 0 | 2 | **2/20** | 0 |
| `openhands` | 20 | 0 | 1 | **1/20** | -1 |
| `mini_swe_agent` | 20 | 0 | 2 | **2/20** | 0 |
| `swe_agent` | 19 | 1 | 4 | **1/20** | -1 |

Resolved IDs:
- Baseline: `a2aproject__a2a-python-683`, `ag2ai__faststream-2495`
- aider: `a2aproject__a2a-python-683`, `ag2ai__faststream-2495`, `aws-powertools__powertools-lambda-python-7026`
- trae: `a2aproject__a2a-python-683`, `ag2ai__faststream-2495`
- openhands: `ag2ai__faststream-2495`
- mini_swe_agent: `a2aproject__a2a-python-564`, `ag2ai__faststream-2495`
- swe_agent: `ag2ai__faststream-2495`

This third-solver check is more mixed than the mini-SWE-agent and SWE-agent solver checks. The `aider` enhancer produced one additional resolved issue for the Aider solver, but the gain was not reproduced by the other enhancers and did not shift the broader conclusion that enhancement quality is not reliably translating into solver success on Pouya-20. The Aider baseline also produced 9 empty patches, while enhanced inputs generally reduced empty patches; however, most additional non-empty patches still failed evaluation.

`amazon-science__chronos-forecasting-407` again timed out during evaluation and was counted unresolved. `astropy__astropy-18753` also timed out for several Aider-solver enhanced conditions under the 300 second per-instance cap. The `swe_agent` enhanced dataset has 19 solver inputs because `astropy__astropy-18753` remains an enhancement failure in that condition.

---

## Comprehensive Cross-Solver Report (2026-05-11)

The combined report aggregates all completed Pouya-20 solver/enhancer setups:

- 3 solvers: mini-SWE-agent, SWE-agent, Aider
- 6 conditions per solver: baseline plus `aider`, `trae`, `openhands`, `mini_swe_agent`, `swe_agent`
- 18 total solver/condition cells

Artifacts:
- Report: `runs/pouya20_comprehensive_solver_enhancer_report_20260511/REPORT.md`
- Machine-readable summary: `runs/pouya20_comprehensive_solver_enhancer_report_20260511/summary.json`
- Builder: `scripts/enhancers/build_pouya20_comprehensive_report.py`

Overall result matrix:

| Solver | baseline | aider | trae | openhands | mini_swe_agent | swe_agent |
|---|---:|---:|---:|---:|---:|---:|
| mini-SWE-agent | 3/20 | 3/20 | 2/20 | 2/20 | 2/20 | 1/20 |
| SWE-agent | 3/20 | 3/20 | 3/20 | 2/20 | 1/20 | 1/20 |
| Aider | 2/20 | 3/20 | 2/20 | 1/20 | 2/20 | 1/20 |

Conclusion: the broad project hypothesis is still not supported as a general claim. The only positive resolved-count delta is the Aider-enhancer/Aider-solver pairing (+1). That is worth analyzing qualitatively, but it is too narrow to claim that native issue enhancement reliably improves solver success.

---

## Docker Image Status

### How Docker images are built

Each of the 20 Pouya instances requires a dedicated Docker image containing the repo at the correct base commit with dependencies installed. These are built by **Paul/RepoLaunch** — a wrapper around Microsoft's RepoLaunch that uses an LLM agent (GPT-5.4-mini) to clone each repo, install dependencies, verify tests, and commit the resulting container as a named Docker image.

**Paul does NOT require Qdrant or any vector database.** All outputs are saved to the local filesystem:

```
paul-RepoLaunch/workspace/<run_name>/
├── playground/<instance_id>/
│   ├── result.json        # Setup/organize results and docker_image name
│   ├── setup.log          # Full setup agent log
│   ├── llm/               # Per-step LLM interaction logs (Markdown)
│   └── instance.json      # Input instance data
├── setup.jsonl            # One line per instance: setup result summary
└── organize.jsonl         # One line per instance: docker_image + test_cmds
```

The `organize.jsonl` file contains the `docker_image` field (e.g., `pouya20gpt-stage12/dev:dlt-hub__dlt-2935_linux`) that the solver uses to launch the container.

**Paul config for OpenAI usage** (`configs/dlt_hub_rebuild_config.json`):
```json
{
    "llm_provider_name": "OpenAI",
    "model_config": {"model_name": "gpt-5.4-mini", "temperature": 0.0},
    "mode": {"setup": true, "organize": true},
    "image_prefix": "pouya20gpt-stage12/dev",
    "disable_timemachine": true
}
```

Key config notes:
- `mode.organize: true` is **required** to produce a Docker image. The `local_config.json` defaults to `organize: false` — only `server_8gpu_config.json` and the rebuild config enable it.
- `llm_provider_name: "OpenAI"` skips the Ollama monkey-patch; the upstream RepoLaunch LLM code calls OpenAI directly via the standard API.
- `image_prefix` determines the Docker image name: `<image_prefix>:<instance_id>_linux`.
- `disable_timemachine: true` prevents Docker containers from using the PyPI time-machine proxy (avoids `host.docker.internal` network timeouts in some setups).

### Current image status (2026-05-11)

| Status | Count | Notes |
|---|:---:|---|
| **Working images** | 20/20 | All canonical Pouya-20 instances have usable Docker images |
| **Missing images** | 0/20 | Previous dlt-hub image gap was rebuilt before the clean v2 comparison |

**Missing images:**
- None in the current canonical dataset. The earlier missing `dlt-hub__dlt-2935` and `dlt-hub__dlt-3048` images were rebuilt under the `pouya20gpt-stage12/dev:*` prefix.

**Rebuild completed (2026-05-11):** Paul/RepoLaunch was run with `image_prefix: "pouya20gpt-stage12/dev"` and `gpt-5.4-mini` to rebuild the two dlt-hub images. Config: `paul-RepoLaunch/configs/dlt_hub_rebuild_config.json`. Dataset: `paul-RepoLaunch/data/dlt_hub_rebuild.jsonl`.

`validated_instances.jsonl` now points at the rebuilt images used by `runs/pouya20_solver_comparison_v2/` and `runs/pouya20_sweagent_solver_comparison_20260511/`.

### Infrastructure notes on dlt-hub issues

The `dlt-hub__dlt-2935` and `dlt-hub__dlt-3048` issues are solvable in principle (their gold patches pass F2P tests). Earlier empty patches tied to missing dlt-hub images were infrastructure artifacts. In the clean v2 run, all agents evaluated both dlt instances and all failed them. In the SWE-agent-solver check, some dlt empty patches remain, but those are solver-output failures rather than missing-image failures.

---

## Run Directories Reference

| Purpose | Directory |
|---|---|
| 20-instance validated dataset | `runs/pouya_final20b_20260505_050130/` |
| Baseline solver (canonical) | `runs/pouya_solver20_20260505_063614/` |
| Merged 20-issue enhancement results | `runs/native_cli_gpt54mini_20issues_merged/` |
| Solver comparison (final) | `runs/pouya20_native_solver_comparison_fixed/` |
| Solver comparison v2 (authoritative mini-SWE-agent) | `runs/pouya20_solver_comparison_v2/` |
| SWE-agent solver comparison | `runs/pouya20_sweagent_solver_comparison_20260511/` |
| Aider solver comparison | `runs/pouya20_aider_solver_comparison_20260511/` |
| Comprehensive cross-solver report | `runs/pouya20_comprehensive_solver_enhancer_report_20260511/` |
| dlt-hub Docker rebuild | `paul-RepoLaunch/workspace/dlt_hub_rebuild/` |

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

## Planned Next Experiment: Quality-Stratified Pouya-20

**Rationale — why the current dataset confounds the enhancer hypothesis**

All 20 issues in the current Pouya-20 dataset are `detailed` quality bucket (3–5 quality signals: `has_code_block`, `has_traceback`, `has_reproduction_steps`, `has_expected_behavior`, and/or long body). These are already well-specified problems statements with reproduction steps, error tracebacks, and code snippets. An enhancement agent has minimal room to add information value to an already-detailed issue, which is the most likely explanation for the null result (baseline 3/20 = best or tied-best across all 18 solver/condition cells).

The scientific hypothesis being tested is:

> **Enhancement agents improve solver success rates by enriching low-quality problem statements with information the solver needs to locate and fix the bug.**

This hypothesis is only testable when the input issues are information-poor. Testing on exclusively `detailed` issues creates a ceiling-effect confound: there is no gap for the enhancer to close.

**Option A (chosen): Select vague/moderate issues from the existing 282**

The 282-issue dataset already contains:
- **46 vague** issues (0–1 quality signals)
- **112 moderate** issues (2 quality signals)
- **124 detailed** issues (3–5 quality signals)

All 282 are already Docker-validated (F2P>0, P2P>0) and formatted as SWE-bench instances — zero re-collection effort. The next 20-issue experiment will deliberately include a mix of quality buckets.

**Proposed composition for Pouya-20-v2:**
- ~7 vague issues (quality_bucket = "vague") — maximum enhancement headroom
- ~7 moderate issues (quality_bucket = "moderate") — medium headroom
- ~6 detailed issues (quality_bucket = "detailed") — control group (replicates current null result)

**Expected outcome:** Enhancement agents should show a significantly larger resolved-count improvement on vague issues than on detailed issues. If even vague issues show no improvement, the enhancer hypothesis is falsified more cleanly than it currently is.

**Selection procedure:** From the 46 vague issues in the 282, exclude any already in the current Pouya-20 dataset, then sample by repo diversity (avoid >2 issues from the same repo). Same procedure for moderate. Preserve the detailed control group from the existing 20 where possible to reuse pre-built Docker images.

**Dataset filter note:** All 282 issues pass F2P>0 and P2P>0. This selection does not require any changes to the data collection pipeline.

---

## Planned Dataset Extension: Refactoring and Feature Request Issues

**Why the current 282 excludes refactoring/feature issues**

SWE-bench validation requires:
1. **F2P > 0**: at least one test that fails before the patch and passes after — this captures behavioral changes (bug fixes, new features)
2. **P2P > 0**: at least one test that passes both before and after — this is a regression guard

Refactoring PRs (code smell removal, structural improvements without behavior change) typically have **F2P = 0**: the code behavior does not change, so no previously-failing test now passes. These issues are eliminated at Docker validation. Feature request PRs with no existing test infrastructure may also have P2P = 0.

**Filter relaxation options**

| Goal | Relaxation | Keeps | Loses |
|---|---|---|---|
| Feature requests | P2P ≥ 0 (keep F2P > 0) | Issues where new feature adds passing tests, regardless of pre-existing test suite | Regression guard |
| Refactoring | F2P ≥ 0 (keep P2P > 0) | Issues where existing tests stay green but no new behavioral tests added | Behavioral change proof |
| Both | P2P ≥ 0 AND F2P ≥ 0 | All Docker-runnable issues | Both guards |

**Recommendation:** Run two separate validation passes on the 941 raw_candidates:
1. `F2P > 0, P2P ≥ 0` → feature request candidate pool
2. `F2P ≥ 0, P2P > 0` → refactoring candidate pool

Then apply issue-type classification (LLM or keyword-based: "refactor", "cleanup", "improve", "extract", "rename") to label each issue, and manually verify a sample.

**Why keep relaxations separate:** Mixing F2P=0 and P2P=0 cases in one pool produces ambiguous instances where neither test type is available, making it impossible to verify gold patch correctness.

**Note on starting point:** No re-crawling is needed. The 941 issues in `data/samples/pouya_dataset_2026/raw_candidates.jsonl` already contain refactoring and feature issues that were excluded only at Docker validation. Re-run the Docker validation with relaxed criteria against the existing raw_candidates.

---

## Refactoring Issue Evaluation: Metrics from Cordeiro et al. (TOSEM 2026)

**Paper:** Cordeiro, Noei, Zou — "LLM Refactoring Capability Study", TOSEM 2026 (co-authored by Shayan Noei, SEAL lab, Queen's University).

**Their metrics (Java, DesigniteJava + Understand tool):**
- **SRR (Smell Reduction Rate):** `(A_before - A_after) / A_before × 100` where A = count of code smells detected
- **Code quality metrics:** coupling, cohesion, modularity, cyclomatic complexity
- **pass@k:** pass@1/3/5 — fraction of k generated refactoring attempts where at least one passes correctness tests

**Applicability to Python refactoring instances:**

| Cordeiro et al. (Java) | Python equivalent | Tool |
|---|---|---|
| DesigniteJava smell detection | pylint / flake8 / ruff | `pylint --output-format=json`, ruff |
| Cyclomatic complexity | radon | `radon cc -j <path>` |
| Maintainability index | radon | `radon mi -j <path>` |
| Halstead metrics | radon | `radon hal <path>` |
| Coupling (fan-out) | pylint import checker | `pylint --disable=all --enable=W0611` |
| Cohesion | flake8-cohesion plugin | `flake8 --select=H` |
| pass@k | P2P test pass rate | SWE-bench harness, same infrastructure |

**SRR is directly reusable** with Python smell tools. Run pylint/ruff before and after the patch, count total warnings/errors (treating each warning as a "smell"), apply the SRR formula. Use the same Docker environment as the SWE-bench harness to ensure consistent Python and dependency versions.

**Correctness oracle:** For refactoring instances (F2P=0), correctness = all P2P tests still pass after the patch. For feature instances (P2P=0), correctness = all F2P tests pass. This maps cleanly to the existing SWE-bench evaluation infrastructure.

**Alignment motivation:** Shayan Noei's co-authorship creates a direct methodological bridge. Using the same SRR metric and pass@k framing allows direct comparison with Cordeiro et al.'s findings and strengthens the positioning of this work within the SEAL lab's refactoring research program.

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
