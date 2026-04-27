# BenchmarkLLMAgent

**Benchmarking LLM-Based Agents for GitHub Issue Enhancement**

## Status Update (2026-03-18)

The canonical 10-issue experiment has been switched from the older SWE-bench-Live setup to the **SWE-bench Verified 10-instance sample** aligned with `/home/22pf2/SWE-Bench_Replication`.

- Baseline is fixed from the replication run (`mini-SWE-agent + Devstral small 2512`), stored in `/home/22pf2/SWE-Bench_Replication`.
- This repository now focuses on **after-enhancement** runs on the same 10 Verified instances and direct baseline-vs-enhanced comparison.
- Use `scripts/workflows/run_verified10_enhancement_vs_baseline.py` as the main entry point.

### Latest Verified-10 Bugfix Runs (2026-03-19)

- Output dirs:
  - `results/verified10_baseline_vs_enhanced/simple_enhancer__bugfix_full10_simple_20260318/`
  - `results/verified10_baseline_vs_enhanced/swe_agent__bugfix_full10_swe_agent_20260318/`
- Baseline vs enhanced:
  - Baseline: RESOLVED `3/10`, FAIL_TO_PASS `3/10`, PASS_TO_PASS `5/10`
  - `simple_enhancer`: RESOLVED `3/10`, FAIL_TO_PASS `3/10`, PASS_TO_PASS `6/10`
  - `swe_agent`: RESOLVED `3/10`, FAIL_TO_PASS `3/10`, PASS_TO_PASS `7/10`
- Both bugfix runs completed `10/10` with `0` evaluation failures.

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

# Verified 10 (canonical as of 2026-03-18): baseline vs enhanced

```bash
cd /home/22pf2/BenchmarkLLMAgent

# Step 0: Prepare the exact 10 Verified instances used by the replication baseline
/home/22pf2/SWE-Bench_Replication/.venv312/bin/python \
  scripts/data/prepare_verified_10_samples_from_replication.py

# Step 1: Run enhancement + mini-SWE-agent (Devstral 2512) + SWE-bench evaluation
# Baseline comes from /home/22pf2/SWE-Bench_Replication (already measured)
./bench_env/bin/python scripts/workflows/run_verified10_enhancement_vs_baseline.py \
  --enhancer-agent simple_enhancer \
  --output-tag run1
```

Outputs:
- Prepared sample: `data/samples/swe_bench_verified_10_samples.json`
- Enhanced run artifacts: `results/verified10_baseline_vs_enhanced/<agent>__<tag>/`
- Baseline-vs-enhanced report: `comparison_summary.json` and `comparison_summary.md`

# Legacy: SWE-bench-Live 10-issue workflow (historical reference)

```bash
# Step 0: Prepare SWE-bench-Live 10-issue sample (run once)
HF_TOKEN="your_hf_token" ./bench_env/bin/python scripts/data/prepare_swe_bench_live_samples.py
# Outputs: data/samples/swe_bench_live_10_samples.json
#          data/ground_truth_swe_bench_live/

# Step 1: Run enhancement benchmark (both categories)
./bench_env/bin/python scripts/enhancers/run_enhancement_benchmark.py \
  --agents trae,simple_enhancer \
  --max-issues 10
#   Uses data/samples/swe_bench_live_10_samples.json by default

# Step 2: Run baseline solver (before enhancement)
./bench_env/bin/python scripts/solvers/run_simple_solver.py --max-issues 10
#   Uses data/samples/swe_bench_live_10_samples.json + data/ground_truth_swe_bench_live/ by default

# Step 3: Run solver after enhancement (vLLM + Gemma 3)
# First start vLLM: CUDA_VISIBLE_DEVICES=1,3,4,5 ./issue_enhancer_py312/bin/python -m vllm.entrypoints.openai.api_server \
#   --model google/gemma-3-12b-it --served-model-name gemma-3-12b-it --port 8001 --tensor-parallel-size 4
USE_VLLM=1 ./bench_env/bin/python scripts/enhancers/run_solving_after_enhancement.py \
  --solver openai_agents_sdk --max-issues 10
#   Uses data/ground_truth_swe_bench_live/ by default

# Step 4: Generate report
./bench_env/bin/python scripts/reports/generate_enhancement_report_multi_agent.py
```

**To use legacy pilot dataset instead:**
```bash
./bench_env/bin/python scripts/solvers/run_simple_solver.py \
  --samples data/samples/pilot_10_samples.json \
  --gt-dir data/ground_truth
```

## Current Status

- **Canonical dataset**: ✅ `data/samples/swe_bench_verified_10_samples.json` (10 Verified instances aligned with replication baseline)
- **Canonical solver setup**: ✅ mini-SWE-agent + Devstral small (2512), via `/home/22pf2/SWE-Bench_Replication`
- **Baseline reference**: ✅ `/home/22pf2/SWE-Bench_Replication/replication_report.md`
- **Current goal**: run enhancer-driven after-enhancement experiments on these same 10 issues and compare against fixed baseline

### Legacy status (historical)
- **Dataset**: ✅ `data/samples/swe_bench_live_10_samples.json` (SWE-bench-Live, 10 issues, seed=42)
- **LLM**: `gpt-oss:120b` via Ollama (localhost:11434) — all enhancement and solving
- **Enhancement benchmark**: ✅ Complete — TRAE (Cat A) + simple_enhancer (Cat B)
- **Baseline solver**: ✅ Done — `openai_agents_sdk` with `gpt-oss:120b` on Ollama
- **Iteration 1**: ✅ Complete — 10 issues, results: simple_enhancer +0.0361, TRAE +0.0330
- **Next step**: Scale to 200 issues (Iteration 2)

**Iteration 1 = exactly 10 issues.** The dataset is sourced from [SWE-bench-Live/SWE-bench-Live](https://huggingface.co/datasets/SWE-bench-Live/SWE-bench-Live) (microsoft/SWE-bench-Live), requiring a HuggingFace token.

### TRAE Agent Note
The `trae` agent (Category A) requires the `bytedance/trae-agent` repository to be cloned and installed via `uv sync` at `/home/22pf2/trae-agent`. The enhancer script automatically discovers it there and points it to the local vLLM server (port 8001) using the OpenAI-compatible API.

## Key Documents

| Document | Description |
|----------|-------------|
| **`ROADMAP.md`** | **Start here** — Step-by-step handoff for next agent/contributor |
| **`docs/analysis/VERIFIED10_BASELINE_ENHANCED_RESULTS_2026-03-18.md`** | Latest canonical baseline-vs-enhanced metrics |
| **`docs/analysis/VERIFIED10_WORKFLOW_BUG_AUDIT_2026-03-18.md`** | Current workflow bug list and debugging priorities |
| **`docs/analysis/VERIFIED10_MULTI_ENHANCER_BUGFIX_RESULTS_2026-03-19.md`** | Two-enhancer bugfix run results vs baseline |
| `docs/guides/VERIFIED10_BASELINE_ENHANCED_WORKFLOW.md` | Canonical execution guide for Verified-10 workflow |
| `docs/README.md` | Documentation overview and folder guide |
| `docs/MAIN.md` | Master documentation index |
| `PINNED_MESSAGE.md` | Brief for contributors (pin in group chat) |
| `CONTRIBUTING.md` | How to add agents, run scripts, naming conventions |
| `docs/archive/` | Historical plans and superseded workflow docs |
