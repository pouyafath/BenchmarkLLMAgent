# Pilot40-Style Evaluation Workflow

## When This Applies

Any run that uses a **P2P-gated dataset** (i.e., datasets where `PASS_TO_PASS > 0` is the resolution gate and `FAIL_TO_PASS` is metadata-only). This includes:

- All pilot-40 runs from the Stage 2 full track
- Any future runs built from the same Stage 3 export or similar P2P-gated exports

## The Problem

The standard SWE-bench evaluator determines resolution by requiring `FAIL_TO_PASS > 0`. The pilot40 dataset uses `PASS_TO_PASS > 0` as the gate instead. Additionally, the evaluator's parsed test names may include:

- `/testbed/` prefix (e.g., `/testbed/tests/test_foo.py::TestBar::test_baz`)
- Parameterized suffixes (e.g., `test_foo[param1]`, `test_foo[param2]`)

These mismatches cause false negatives in the raw evaluation output.

## Corrected Resolution Criteria

An instance is **resolved** if and only if:

1. **No P2P failures**: Every expected `PASS_TO_PASS` test that was found in the status output must have passed
2. **At least one P2P pass**: At least one `PASS_TO_PASS` test was found and passed (prevents vacuous resolution)
3. **F2P is informational**: `FAIL_TO_PASS` results are recorded but do not gate resolution

## Test Name Normalization

When matching parsed test names against expected names:

1. Strip `/testbed/` prefix from parsed names
2. For parameterized tests (`test_foo[X]`), match against base name `test_foo`
   - All parameterized variants must pass for the base test to count as passing

## Standard Execution Sequence

For any pilot40-style run, stages must execute in this order:

```
Stage 4: Enhancement
    ↓
Stage 5a: Solver (baseline)
Stage 5b: Evaluation (baseline)  ← raw SWE-bench eval
Stage 5c: Solver (enhanced)
Stage 5d: Evaluation (enhanced)  ← raw SWE-bench eval
    ↓
Stage 5e: P2P-gated re-evaluation  ← MANDATORY before Stage 6
    ↓
Stage 6: Report generation
```

### Running the re-evaluation

```bash
cd /home/22pf2/BenchmarkLLMAgent

# Generic (any pilot40-style run):
bench_env/bin/python scripts/workflows/pilot40_reeval_lib.py \
    --run-dir runs/<RUN_DIR_NAME> \
    --expected-count 40

# Specific wrappers (for existing runs):
bench_env/bin/python scripts/workflows/reeval_pilot40.py           # 2026-05-26 llm_append run
bench_env/bin/python scripts/workflows/reeval_pilot40_openhands.py  # 2026-06-01 openhands run
```

The re-eval script:
- Reads existing `status.json` files (does NOT re-run tests)
- Applies normalized test name matching + P2P-gated criteria
- Overwrites `report.json` and `eval_results.json` per instance
- Must complete before any report generation step

### Why this step is mandatory

Without re-evaluation, raw SWE-bench eval will:
- Report ~1/40 resolved instead of the correct ~9/40 (baseline)
- Produce numbers that are not comparable across runs
- Gate on FAIL_TO_PASS which is metadata-only in this dataset

## Creating a New Pilot40-Style Run

When creating a new enhancer run on the pilot40 dataset:

1. Copy the dataset from the immutable Stage 3 export
2. Run Stages 4-5d as normal
3. **Before Stage 6**, run `pilot40_reeval_lib.py --run-dir <your_run>`
4. Generate the Stage 6 report from the corrected eval results
5. Add a comparability note referencing this methodology

## Artifacts

| File | Purpose |
|------|---------|
| `scripts/workflows/pilot40_reeval_lib.py` | Shared re-eval library (CLI + importable) |
| `scripts/workflows/reeval_pilot40.py` | Thin wrapper for 2026-05-26 run |
| `scripts/workflows/reeval_pilot40_openhands.py` | Thin wrapper for 2026-06-01 run |
| `scripts/workflows/regenerate_pilot40_report.py` | Report regenerator for 2026-05-26 run |

## Verified Results (Corrected)

| Run | Enhancer | Baseline | Enhanced | Delta |
|---|---|---:|---:|---:|
| 2026-06-01 | openhands | 9/40 | 10/40 | +1 |
| 2026-05-26 | llm_append_analysis | 9/40 | 8/40 | -1 |
| 2026-05-27 | llm_append_analysis (gpt-oss solver) | 0/40 | 0/40 | 0 |
