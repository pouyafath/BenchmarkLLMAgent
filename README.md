# BenchmarkLLMAgent

**Benchmarking LLM-Based Agents for GitHub Issue Enhancement**

## Status Update (2026-05-05) — Pouya-20 Experiment

The project has scaled to a **20-instance gold-validated SWE-bench-style dataset** (Pouya-20), with a full baseline vs. 6 enhancer comparison running on **gpt-5.4-mini**.

- **Dataset**: 20 gold-validated instances from Pouya's 2026 GitHub issues collection — all `resolved: true` via F2P+P2P gold evaluation.
- **Main script**: `scripts/workflows/run_pouya20_gpt54mini.py`
- **Baseline**: `mini-SWE-agent v2.2.5 + gpt-5.4-mini` (deterministic, temp=0.0) → **3/20 resolved**
- **Enhancers tested**: `llm_append_analysis` (direct LLM), `aider`, `trae`, `openhands`, `mini_swe_agent`, `swe_agent` — all using gpt-5.4-mini
- **Monitoring**: `bench_env/bin/python scripts/watch_enhancers.py --once`

### Enhancer Comparison Results (in progress, 2026-05-05)

| Enhancer | Resolved / 20 | vs Baseline |
|---|---|---|
| **Baseline** | **3** | — |
| `llm_append_analysis` | 3 | = 0 |
| `aider` | 1* | − 2 |
| `trae` | 2* | − 1 (new: Flexget-4986) |
| `openhands` | 3* | = 0 |
| `mini_swe_agent` | 2* | − 1 |
| `swe_agent` | running | — |

*Partial results — eval still completing.

See [`docs/POUYA20_EXPERIMENT.md`](docs/POUYA20_EXPERIMENT.md) for full details.

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

### Pouya-20 (canonical as of 2026-05-05)

```bash
cd /home/22pf2/BenchmarkLLMAgent

# Run a new enhancer on the existing 20 gold-validated instances
# (skips RepoLaunch + Gold Eval + Baseline — reuses canonical results)
export OPENAI_API_KEY="your_key_here"
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

See [`docs/WORKFLOW_SCRIPT_REFERENCE.md`](docs/WORKFLOW_SCRIPT_REFERENCE.md) for all CLI flags, pipeline stages, and the full pre-seeding recipe.

### Legacy: Verified-10 (2026-03-18, historical reference)

```bash
cd /home/22pf2/BenchmarkLLMAgent
./bench_env/bin/python scripts/workflows/run_verified10_enhancement_vs_baseline.py \
  --enhancer-agent simple_enhancer \
  --output-tag run1
```

## Current Status

### Pouya-20 Experiment (active)

- **Gold-validated dataset**: ✅ `runs/pouya_final20b_20260505_050130/validated_instances.jsonl` (20 instances, all `resolved: true`)
- **Baseline solver**: ✅ `runs/pouya_solver20_20260505_063614/` — mini-SWE-agent + gpt-5.4-mini → **3/20 resolved**
- **Enhancer runs**: ⏳ 5 native-agent runs active in `runs/pouya_enhanced_*_20260505_084500/`
- **Next goal**: compile final comparison table once `swe_agent` enhancer completes

### Key run directories

| Purpose | Path |
|---------|------|
| Gold-validated dataset | `runs/pouya_final20b_20260505_050130/` |
| Canonical baseline | `runs/pouya_solver20_20260505_063614/` |
| Enhanced: aider | `runs/pouya_enhanced_aider_20260505_084500/` |
| Enhanced: trae | `runs/pouya_enhanced_trae_20260505_084500/` |
| Enhanced: openhands | `runs/pouya_enhanced_openhands_20260505_084500/` |
| Enhanced: mini_swe_agent | `runs/pouya_enhanced_mini_swe_agent_20260505_084500/` |
| Enhanced: swe_agent | `runs/pouya_enhanced_swe_agent_20260505_084500/` |

### Legacy status (historical)

- Verified-10 (2026-03-18): mini-SWE-agent + Devstral small 2512, 3/10 resolved across all enhancers
- SWE-bench-Live 10 (2026-03-01): gpt-oss:120b, simple_enhancer +0.0361, TRAE +0.0330

## Key Documents

| Document | Description |
|----------|-------------|
| **[`docs/POUYA20_EXPERIMENT.md`](docs/POUYA20_EXPERIMENT.md)** | **Start here** — Full Pouya-20 experiment: dataset, pipeline, results, run directories |
| **[`docs/WORKFLOW_SCRIPT_REFERENCE.md`](docs/WORKFLOW_SCRIPT_REFERENCE.md)** | CLI reference for `run_pouya20_gpt54mini.py`: all flags, pipeline stages, env vars, progress.json format |
| [`scripts/watch_enhancers.py`](scripts/watch_enhancers.py) | Live monitoring dashboard for all 5 enhancer runs |
| `ROADMAP.md` | Step-by-step handoff for next agent/contributor |
| `docs/README.md` | Documentation overview and folder guide |
| `docs/MAIN.md` | Master documentation index |
| `CONTRIBUTING.md` | How to add agents, run scripts, naming conventions |
| `docs/archive/` | Historical plans and superseded workflow docs (Verified-10, SWE-bench-Live) |
