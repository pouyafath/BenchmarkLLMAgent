# BenchmarkLLMAgent

**Benchmarking LLM-Based Agents for GitHub Issue Enhancement**

> 📖 **Start here (current docs, 2026-06-17):**
> - **[WORKFLOW.md](WORKFLOW.md)** — the two-part pipeline (Stages 1-3 / 4-6), every script,
>   and **which node** each runs on; private-Ollama setup; image persistence; run order.
> - **[PIPELINE_STATE.md](PIPELINE_STATE.md)** — live per-node, per-process status, results,
>   and open decisions (with timestamps).
>
> The dated "Status Update" sections below are historical.

## Status Update (2026-06-01) — OpenHands Enhancer Pilot-40 Complete

The project is running a **7-stage Enhancer+Solver workflow** on a 2,900-issue dataset, while a 48-instance pilot subset has been pushed through all stages including downstream enhancement and solving experiments.

- **Dataset**: 2,900 viable issues
- **Workflow**: Collection -> Classification -> Setup -> Organize -> Validate -> Enhance -> Solve
- **Environment automation**: local `paul-RepoLaunch` wrapper using `gpt-oss:120b` via Ollama
- **Full-run live phase**: Stage 1 setup is still active
- **Pilot continuation phase**: Stage 4-6 experiments completed on 40-row pilot

### Current Full-Run / Pilot Split
1. **Stage 0:** Collection & Filtering complete
2. **Stage 0.5:** Classification & Viability complete
3. **Stage 1:** Full 2,900-instance RepoLaunch setup run active
4. **Stage 2:** Pilot subset completed on 41 / 48 rows
5. **Stage 3:** Pilot subset completed on 40 / 41 rows
6. **Stage 4-6:** Three pilot-40 runs completed (see below)

### Pilot-40 Stage 4-6 Runs

| Run | Enhancer | Solver Model | Baseline | Enhanced | Delta | Report |
|---|---|---|---:|---:|---:|---|
| 2026-06-01 | openhands | gpt-5.4-mini | 9/40 | 10/40 | **+1** | `runs/paul_pilot40_openhands_20260601/stage6_report/REPORT.md` |
| 2026-05-26 | llm_append_analysis | gpt-5.4-mini | 9/40 | 8/40 | -1 | `runs/paul_pilot40_stage4_stage6_20260526/stage6_report/REPORT.md` |
| 2026-05-27 | llm_append_analysis | gpt-oss:120b | 0/40 | 0/40 | 0 | `runs/paul_pilot40_gptoss_solver_20260527/stage6_report/REPORT.md` |

All runs use P2P-gated resolution criteria with normalized test names (see `COMPARABILITY_AUDIT.md` in the openhands run directory for the methodology reconciliation).

**Key finding (2026-06-01):** OpenHands as an enhancer (gpt-5.4-mini, 39/40 truly enhanced) gains `Diaoul__subliminal-1328` (+2.5 pp). This is the first positive enhancement delta on the pilot-40 dataset.

**Evaluation note:** The accepted pilot40 comparison uses the shared P2P-gated re-eval workflow, not raw SWE-bench resolved semantics. The earlier `1/40 -> 1/40` raw reading was reconciled to `9/40 -> 10/40` by the comparability audit. The single Stage 4 failure `Azure__azure-cli-32339` is treated as a likely OpenHands/runtime outlier, but its exact root cause is not fully proven.

**OpenClaw status:** No local OpenClaw runtime, binary, or Python module was found on `docjk-gpu-01`. Integration was not attempted because the only option would have been a proxy/fake enhancer, which does not meet the benchmark's real-integration standard.

### Current authoritative pilot artifacts

- RepoLaunch handoff:
  - `/home/22pf2/paul-RepoLaunch/docs/PROJECT_STATUS_HANDOFF_2026-05-26.md`
- Immutable pilot stage exports:
  - `/home/22pf2/paul-RepoLaunch/runs/stage2_2026_full_pilot48_stage_exports_20260526_1552_utc/`
- Authoritative next-stage dataset:
  - `/home/22pf2/paul-RepoLaunch/runs/stage2_2026_full_pilot48_stage_exports_20260526_1552_utc/stage3_validation_completed40.jsonl`
- Pre-seeded continuation run:
  - `/home/22pf2/BenchmarkLLMAgent/runs/paul_stage4_stage6_from_stage3pilot40_20260526/`

Important branch rule:

- For the current P2P-oriented pipeline, `PASS_TO_PASS > 0` is the gate.
- `FAIL_TO_PASS` is preserved for analysis but is not the downstream handoff filter.

---

## Historical: Pouya-20 Track (2026-05-11)

### Full 20-Issue Native Enhancer Results (2026-05-11)

| Solver | Baseline | aider | trae | openhands | mini_swe_agent | swe_agent |
| --- | --- | --- | --- | --- | --- | --- |
| mini-SWE-agent | 3/20 | 3/20 | 2/20 | 2/20 | 2/20 | 1/20 |
| SWE-agent | 3/20 | 3/20 | 3/20 | 2/20 | 1/20 | 1/20 |
| Aider | 2/20 | 3/20 | 2/20 | 1/20 | 2/20 | 1/20 |

Raw LLM follow-up: mini-SWE-agent 3/20, SWE-agent 3/20, Aider 1/20. It is included in the comprehensive report as the `raw_llm` column.

Key finding: native enhancement does **not** improve solver success rate in general. The only positive resolved-count delta is `aider` enhancement with the Aider solver, which solves `aws-powertools__powertools-lambda-python-7026`.

- **Comprehensive report**: `runs/pouya20_comprehensive_solver_enhancer_report_20260511/REPORT.md`
- **Raw LLM follow-up**: `docs/analysis/POUYA20_RAW_LLM_ENHANCER_2026-05-11.md`
- **Enhancement data**: `runs/native_cli_gpt54mini_20issues_merged/`
- **Main script**: `scripts/workflows/run_pouya20_gpt54mini.py`
- **Solver comparison**: `scripts/enhancers/run_pouya5_solver_comparison.py --limit 20`

---

### Previous: Verified-10 Runs (2026-03-19, historical)

- Baseline: RESOLVED `3/10` | `simple_enhancer`: `3/10` | `swe_agent`: `3/10`
- Both completed `10/10` with `0` evaluation failures.

Paper 3 in a research trilogy on LLM-assisted software engineering:

| Paper | Focus | Venue |
|-------|-------|-------|
| Paper 1: SENIR | Understanding developer questions via NER/intent in chatrooms | TSE (published) |
| Paper 2: Issue Enhancer | Enhancing GitHub issue descriptions with LLM agents | ASE 2026 (submitted) |
| **Paper 3: This work** | **Benchmarking issue enhancement agents + downstream solving impact** | **TSE (target)** |

## Research Questions

| RQ | Question |
|----|----------|
| **RQ1** | How do ready-to-use agents (Category A) compare in their ability to enhance GitHub issue descriptions? |
| **RQ2** | How do framework-built agents (Category B) compare when specifically designed for issue enhancement? |
| **RQ3** | Does issue enhancement improve the performance of automated issue-solving agents? |
| **RQ4** | How do enhancement quality and downstream solving improvement vary across issue types and complexity? |

## Two Categories of Enhancement Agents

| Category | Description | Examples |
|----------|-------------|---------|
| **A: Ready-to-Use** | Pre-built agents directed to enhance issues out-of-the-box | OpenHands, SWE-Agent, Copilot, Sweep, Aider, Cline, etc. |
| **B: Framework-Built** | Custom agents built with agent-building frameworks | LangGraph, AutoGen, CrewAI, OpenAI Agents SDK, LlamaIndex, Semantic Kernel |

## Evaluation: The Solving-as-Evaluation Loop

Enhancement quality is measured both directly (completeness, clarity, actionability) and indirectly by using solver agents to attempt fixes before and after enhancement:

```
Enhancement Value = Solver_performance(enhanced_issue) - Solver_performance(original_issue)
```

## Project Structure

```
BenchmarkLLMAgent/
├── configs/                             # Configuration
│   ├── benchmark_config.yaml            # Master configuration
│   └── prompts/
│       ├── solver/                      # Solver agent prompts
│       └── enhancer/                    # Enhancement agent prompts
│
├── src/                                 # Source code
│   ├── utils/                           # Shared utilities
│   │   ├── github_client.py             # Multi-token GitHub API client
│   │   └── patch_utils.py              # Patch extraction & evaluation
│   ├── solvers/                         # Issue-solving agents
│   │   ├── base_agent.py                # Abstract agent interface
│   │   ├── shared_tools.py              # Shared tool implementations
│   │   ├── autogen/                     # AutoGen solver
│   │   ├── crewai/                      # CrewAI solver
│   │   ├── langgraph/                   # LangGraph solver
│   │   ├── llamaindex/                  # LlamaIndex solver
│   │   ├── openai_agents_sdk/           # OpenAI Agents SDK solver
│   │   └── semantic_kernel/             # Semantic Kernel solver
│   ├── enhancers/                       # Issue-enhancement agents
│   │   ├── ready_to_use/               # Category A agents
│   │   └── framework_built/            # Category B agents
│   └── evaluation/                      # Metrics & statistical analysis
│       ├── evaluator.py                 # Correctness, efficiency, alignment
│       └── statistical_analysis.py      # Wilcoxon, Cliff's delta, bootstrap
│
├── scripts/                             # Runnable scripts
│   ├── data/                            # Dataset construction
│   │   ├── select_samples.py            # Select issues from golden dataset
│   │   └── build_dataset.py             # Full dataset builder
│   ├── solvers/                         # Solver benchmarks
│   │   ├── run_pilot_benchmark.py       # Pilot: 10 issues x 6 frameworks
│   │   ├── run_full_benchmark.py        # Full benchmark orchestrator
│   │   └── recompute_similarity.py      # Recompute metrics (diff-only)
│   ├── enhancers/                       # Enhancement benchmarks
│   └── reports/                         # Report generation
│       ├── generate_pilot_report.py     # Pilot summary report
│       └── generate_full_report.py      # Comprehensive report
│
├── data/                                # Data files
│   ├── samples/                         # Selected issue samples
│   │   ├── pilot_10_samples.json        # Legacy pilot study issues (historical)
│   │   └── swe_bench_live_10_samples.json  # Iteration 1: 10 SWE-bench-Live issues
│   ├── ground_truth/                    # Legacy ground truth (historical)
│   ├── ground_truth_swe_bench_live/     # Iteration 1 ground truth (SWE-bench-Live)
│   ├── processed/                       # Processed benchmark instances
│   └── raw/                             # Raw GitHub API data
│
├── results/                             # Experiment results
│   ├── pilot_solver_benchmark/          # Pilot solver study results
│   ├── enhancement_benchmark/           # Enhancement experiment results
│   └── solving_after_enhancement/       # Before/after solving comparison
│
├── docs/                                # Documentation
│   ├── analysis/                        # Canonical results + bug audits
│   ├── guides/                          # Workflow guides
│   ├── handoff/                         # Continuation docs
│   ├── iterations/                      # Historical iteration snapshots
│   ├── investigation/                   # Historical deep-dive investigations
│   ├── archive/                         # Deprecated/superseded docs
│   ├── README.md                        # Docs overview
│   └── MAIN.md                          # Docs index
│
├── ROADMAP.md                           # Handoff guide — start here for next steps
│
├── papers/                              # Paper artifacts
│   ├── drafts/
│   ├── figures/
│   └── tables/
│
├── CONTRIBUTING.md                      # Team collaboration guide
├── PINNED_MESSAGE.md                    # Brief for contributors (pin in chat)
├── requirements.txt                     # Python dependencies
└── .gitignore
```

## Setup

```bash
cd /home/22pf2/BenchmarkLLMAgent
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Quick Start

### Stage 2 Full Track (2026-05-24, active)

```bash
cd /home/22pf2/paul-RepoLaunch
conda activate paul-repolaunch
python -m paul.run configs/stage2_2026_full.json
```
*(Currently running with 4 workers. Do not exceed 4 workers due to Ollama 120B model constraints).*

See [`paul-RepoLaunch/README.md`](../paul-RepoLaunch/README.md) and [`docs/guides/POUYA_DATASET_2026_WORKFLOW.md`](docs/guides/POUYA_DATASET_2026_WORKFLOW.md) for full execution details.

### Legacy: Pouya-20 (canonical as of 2026-05-05)

```bash
cd /home/22pf2/BenchmarkLLMAgent

# Run a new enhancer on the existing 20 gold-validated instances.
# Keep the real key in an ignored local file; see docs/archive/API_KEY_HANDLING.md.
export OPENAI_API_KEY_FILE="$PWD/.claude/settings.local.json"
bench_env/bin/python scripts/workflows/run_pouya20_gpt54mini.py \
  --run-dir runs/my_new_run \
  --limit 20 \
  --skip-repolaunch \
  --skip-gold-eval \
  --skip-baseline \
  --enhancer llm_append_analysis   # or: aider, trae, openhands, mini_swe_agent, swe_agent

# Monitor all active enhancer runs
bench_env/bin/python scripts/watch_enhancers.py --once

# Live dashboard (30s refresh)
watch -n 30 'cd /home/22pf2/BenchmarkLLMAgent && bench_env/bin/python scripts/watch_enhancers.py --once'
```

See [`docs/archive/WORKFLOW_SCRIPT_REFERENCE.md`](docs/archive/WORKFLOW_SCRIPT_REFERENCE.md) for all CLI flags, pipeline stages, and the full pre-seeding recipe.

### Legacy: Verified-10 (2026-03-18, historical reference)

```bash
cd /home/22pf2/BenchmarkLLMAgent
./bench_env/bin/python scripts/workflows/run_verified10_enhancement_vs_baseline.py \
  --enhancer-agent simple_enhancer \
  --output-tag run1
```

## Current Status

### Stage 2 Full Pipeline (active)

- **Dataset**: `paul-RepoLaunch/data/stage2_2026_viable.jsonl` (2,900 issues)
- **Status**: Stage 1 (Setup) is currently executing via `paul-RepoLaunch`.
- **Dashboard**: Run `watch -c -n 30 python3 /home/22pf2/paul-RepoLaunch/dashboard.py`

### Legacy status (historical)

- Pouya-20 (2026-05-11): 5 native-agent runs completed. No enhancement improvement observed on Aider/SWE-agent.
- Verified-10 (2026-03-18): mini-SWE-agent + Devstral small 2512, 3/10 resolved across all enhancers.
- SWE-bench-Live 10 (2026-03-01): gpt-oss:120b, simple_enhancer +0.0361, TRAE +0.0330

## Key Documents

| Document | Description |
|----------|-------------|
| **[`docs/guides/POUYA_DATASET_2026_WORKFLOW.md`](docs/guides/POUYA_DATASET_2026_WORKFLOW.md)** | **Start here** — Overview of the current 7-stage dataset and execution workflow. |
| **[`../paul-RepoLaunch/README.md`](../paul-RepoLaunch/README.md)** | Guide to running Stages 1 and 2 locally via Ollama. |
| [`docs/README.md`](docs/README.md) | Documentation overview and folder guide |
| [`docs/MAIN.md`](docs/MAIN.md) | Master documentation index |
| [`docs/archive/POUYA20_EXPERIMENT.md`](docs/archive/POUYA20_EXPERIMENT.md) | Historical full Pouya-20 experiment: dataset, pipeline, results, run directories |
| [`docs/archive/WORKFLOW_SCRIPT_REFERENCE.md`](docs/archive/WORKFLOW_SCRIPT_REFERENCE.md) | CLI reference for legacy scripts |
| [`scripts/watch_enhancers.py`](scripts/watch_enhancers.py) | Live monitoring dashboard for all 5 enhancer runs |
| `ROADMAP.md` | Step-by-step handoff for next agent/contributor |
| `docs/README.md` | Documentation overview and folder guide |
| `docs/MAIN.md` | Master documentation index |
| `CONTRIBUTING.md` | How to add agents, run scripts, naming conventions |
| `docs/archive/` | Historical plans and superseded workflow docs (Verified-10, SWE-bench-Live) |

### Multi-Node Parallelization
The `paul-RepoLaunch` Stage 1 & 2 processes are distributed across `docjk-gpu-01` and `docjk-gpu-02`. Because Docker instances are not shared across the NFS mount, both nodes utilize a bidirectional "meet-in-the-middle" execution queue to avoid conflicting builds while still saving outputs to a unified network folder. Future stages (e.g. Stage 3 Validation) will also run bidirectionally to maintain Docker context locality.
