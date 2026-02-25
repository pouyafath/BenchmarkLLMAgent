# Contributing to BenchmarkLLMAgent

## Project Overview

This project benchmarks LLM-based agents for GitHub issue enhancement.
See `docs/research_plan.md` for the full research plan.

**Iterative workflow:** We run the full pipeline on 10 issues first (Iteration 1), validate, then scale to 200 issues (Iteration 2). See **`ROADMAP.md`** for step-by-step handoff instructions.

## Project Structure

```
BenchmarkLLMAgent/
├── configs/              # Configuration files and prompt templates
│   ├── benchmark_config.yaml
│   └── prompts/
│       ├── solver/       # Prompts for solver agents
│       └── enhancer/     # Prompts for enhancement agents
│
├── src/                  # All source code
│   ├── utils/            # Shared utilities (GitHub client, patch tools)
│   ├── solvers/          # Issue-solving agents (6 frameworks)
│   ├── enhancers/        # Issue-enhancement agents
│   │   ├── ready_to_use/ # Category A: pre-built agents
│   │   └── framework_built/ # Category B: framework-built agents
│   └── evaluation/       # Evaluation metrics and statistical analysis
│
├── scripts/              # Runnable scripts (not imported as modules)
│   ├── data/             # Dataset selection and construction
│   ├── solvers/          # Solver benchmark scripts
│   ├── enhancers/        # Enhancement benchmark scripts
│   └── reports/          # Report generation
│
├── data/                 # Data files (samples, ground truth)
│   ├── samples/          # Selected issue samples
│   ├── ground_truth/     # Ground truth patches from merged PRs
│   ├── processed/        # Processed benchmark instances
│   └── raw/              # Raw data from GitHub API
│
├── results/              # Experiment results
│   ├── pilot_solver_benchmark/      # Pilot study (10 issues x 6 frameworks)
│   ├── enhancement_benchmark/       # Enhancement experiment results
│   └── solving_after_enhancement/   # Solving before/after enhancement
│
├── docs/                 # Documentation
│   ├── research_plan.md             # Active research plan (enhancement focus)
│   ├── pilot_study_report.md        # Pilot study report (solver benchmark)
│   └── archive/                     # Archived documents
│
└── papers/               # Paper drafts, figures, tables
```

## Setup

```bash
cd /home/22pf2/BenchmarkLLMAgent
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running Scripts

All scripts should be run from the project root:

```bash
# Dataset selection
python scripts/data/select_samples.py

# Run pilot solver benchmark
python scripts/solvers/run_pilot_benchmark.py

# Generate reports
python scripts/reports/generate_pilot_report.py
python scripts/reports/generate_full_report.py

# Recompute similarity metrics
python scripts/solvers/recompute_similarity.py
```

## Naming Conventions

- **Directories**: lowercase with underscores (`ready_to_use/`, `pilot_solver_benchmark/`)
- **Python files**: lowercase with underscores (`run_pilot_benchmark.py`)
- **Classes**: PascalCase (`GitHubMultiTokenClient`, `BaseAgent`)
- **Functions/variables**: snake_case (`extract_patch_from_response`)
- **Constants**: UPPER_SNAKE_CASE (`OLLAMA_MODEL`, `MAX_WORKERS`)

## Adding a New Enhancement Agent

### Category A (Ready-to-Use)

1. Create `src/enhancers/ready_to_use/<agent_name>.py`
2. Implement the agent wrapper following the interface in `src/enhancers/`
3. Add configuration to `configs/benchmark_config.yaml`
4. Add a runner script to `scripts/enhancers/`

### Category B (Framework-Built)

1. Create `src/enhancers/framework_built/<framework_name>/agent.py`
2. Inherit from the base enhancer class
3. Keep the same LLM, prompt, and tools as other framework agents

## Adding a New Solver Framework

1. Create `src/solvers/<framework_name>/agent.py`
2. Inherit from `src/solvers/base_agent.py:BaseAgent`
3. Register in `scripts/solvers/run_full_benchmark.py:FRAMEWORK_REGISTRY`

## Iteration 1 vs 2

- **Iteration 1:** Use `data/samples/pilot_10_samples.json`, pass `--max-issues 10` (or equivalent) to benchmark scripts. Validate end-to-end.
- **Iteration 2:** Use `data/samples/primary_200_samples.json` (create via `scripts/data/select_samples.py` with appropriate filters). Run full benchmark.

## Code Quality

- All shared utilities go in `src/utils/`
- Keep secrets (tokens, API keys) in environment variables or `.env` (never commit)
- Use `pathlib.Path` for file paths
- Add docstrings to all public functions and classes
