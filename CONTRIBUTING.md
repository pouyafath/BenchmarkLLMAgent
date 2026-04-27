# Contributing to BenchmarkLLMAgent

## Working Model

This repo currently targets one canonical workflow:

- Fixed 10 SWE-bench Verified IDs (aligned with `/home/22pf2/SWE-Bench_Replication`)
- Baseline metrics from replication folder
- Enhanced run + solver + evaluation in this repo
- Comparison via `scripts/workflows/run_verified10_enhancement_vs_baseline.py`

## Core Rules

1. Do not change the baseline IDs when running baseline-vs-enhanced comparisons.
2. Keep run artifacts under `results/verified10_baseline_vs_enhanced/<agent>__<tag>/`.
3. Record exact commands in `commands_run.md` for every experiment directory.
4. Treat missing evaluation reports as failures, never silent drops.
5. Update docs when workflows, metrics, or assumptions change.

## Setup

```bash
cd /home/22pf2/BenchmarkLLMAgent
python -m venv bench_env
source bench_env/bin/activate
pip install -r requirements.txt
```

Solver/evaluator dependencies and mini-SWE-agent stack are in:

- `/home/22pf2/SWE-Bench_Replication/.venv312`
- `/home/22pf2/SWE-Bench_Replication/mini-SWE-agent`

## Run Commands (Canonical)

```bash
cd /home/22pf2/BenchmarkLLMAgent

# Prepare the exact Verified-10 sample from replication IDs
/home/22pf2/SWE-Bench_Replication/.venv312/bin/python \
  scripts/data/prepare_verified_10_samples_from_replication.py

# Run enhancement + solve + evaluate + compare
./bench_env/bin/python scripts/workflows/run_verified10_enhancement_vs_baseline.py \
  --enhancer-agent simple_enhancer \
  --output-tag run1
```

## Documentation to Update After Changes

- `README.md` for user-facing status and command changes
- `ROADMAP.md` for execution priorities
- `PINNED_MESSAGE.md` for contributor brief
- `docs/README.md` and `docs/MAIN.md` for index/navigation
- `docs/analysis/*` for metric updates and bug audits

## Code and Data Conventions

- Python: snake_case functions, PascalCase classes.
- Paths: use `pathlib.Path`.
- Secrets: environment variables only, no committed API keys.
- Outputs: keep raw logs and evaluation artifacts; do not overwrite prior run dirs.
