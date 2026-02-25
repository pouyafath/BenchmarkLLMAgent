# BenchmarkLLMAgent

**Benchmarking LLM-Based Agents for GitHub Issue Enhancement**

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
│   │   └── pilot_10_samples.json        # 10 pilot study issues
│   ├── ground_truth/                    # Ground truth patches (from PRs)
│   ├── processed/                       # Processed benchmark instances
│   └── raw/                             # Raw GitHub API data
│
├── results/                             # Experiment results
│   ├── pilot_solver_benchmark/          # Pilot solver study results
│   ├── enhancement_benchmark/           # Enhancement experiment results
│   └── solving_after_enhancement/       # Before/after solving comparison
│
├── docs/                                # Documentation
│   ├── research_plan.md                 # Active research plan
│   ├── pilot_study_report.md            # Pilot study findings
│   └── archive/                         # Previous iterations
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

```bash
# Run the pilot solver benchmark
python scripts/solvers/run_pilot_benchmark.py

# Generate pilot report
python scripts/reports/generate_full_report.py

# Recompute similarity metrics (diff-only)
python scripts/solvers/recompute_similarity.py
```

## Current Status

- **Pilot solver benchmark**: ✅ Complete (4/6 frameworks working on 10 issues)
- **10-issue dataset**: ✅ Ready (`data/samples/pilot_10_samples.json` + ground truth)
- **Enhancement agents**: ⏳ Not started
- **Next step**: Implement enhancement agents and run full workflow on 10 issues (Iteration 1)

**Iterative strategy:** Run full pipeline on 10 issues first, validate, then scale to 200 issues.

## Key Documents

| Document | Description |
|----------|-------------|
| **`ROADMAP.md`** | **Start here** — Step-by-step handoff for next agent/contributor |
| `docs/research_plan.md` | Active research plan (enhancement benchmark) |
| `docs/pilot_study_report.md` | Pilot study findings (solver benchmark) |
| `PINNED_MESSAGE.md` | Brief for contributors (pin in group chat) |
| `CONTRIBUTING.md` | How to add agents, run scripts, naming conventions |
| `docs/archive/research_plan_v1_solving.md` | Original solving-focused plan |
