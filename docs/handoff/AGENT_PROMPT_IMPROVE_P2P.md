# Agent Prompt: Improve P2P Performance on 50-Issue SWE-bench-Live

## Current Status

**Best result**: 27/50 F2P (54%), 4/50 P2P (8%), 1/50 Resolved (2%)

**Bottleneck**: 23 out of 27 F2P-passing instances break existing tests (fail P2P). We need to improve the solver's ability to avoid regressions without losing F2P fixes.

**Solver stack**:
- Agent: mini-SWE-agent v2.2.7
- Model: Devstral-Small-2-24B-Instruct-2512 (local vLLM)
- Verified to match official SWE-bench leaderboard (56.40% on Verified benchmark)
- Current prompt: `swebench_backticks_regression_guard.yaml` (our custom, includes explicit test-running instructions)

**Enhancement**: Code-context (deterministic, no LLM) — appends source code, developer hints, failing test names, test specification to issue body.

---

## What Has Been Tried

| Approach | Result | F2P | P2P | Notes |
|----------|--------|:---:|:---:|-------|
| A: Include P2P test names in description | ❌ No improvement | 22/50 | 1/50 | Data alone doesn't help |
| B: Regression guard prompt ✅ BEST | ✅ Best | 27/50 | 4/50 | Prompt engineering works |
| C: Retry loop with failure feedback | ❌ Worse | 17/21 | 0/21 | Non-determinism counterproductive |

**Lesson**: Prompt engineering > data engineering for P2P. The solver needs instructions to test, not just data about tests.

---

## Your Task: Improve P2P Beyond 4/50 (8%)

### Step 1: Analyze the 23 F2P-pass / P2P-fail Instances

These 23 instances are where the solver fixes the bug but breaks existing tests.

**Read**:
- `results/groupC50_p2p_approachB/code_context__code_context_devstral_tp_regguard_groupC50_20260414/comparison_summary.json` — comparison of baseline vs enhanced runs

**For each F2P-pass / P2P-fail instance**:
1. Find the generated patch: `enhanced_solver_run/<instance_id>/patch.txt`
2. Look at evaluation log for P2P failures
3. Identify failure patterns:
   - **Overly broad changes** — patch modifies too much
   - **Missing imports/side effects** — breaks dependencies
   - **Test infrastructure** — environmental issues
   - **Fundamental conflicts** — impossible to fix without breaking tests

**Output**: Write findings to `docs/analysis/p2p_failure_analysis.md` — categorize the 23 failures by root cause.

### Step 2: Improve the Regression Guard Prompt

Based on Step 1 findings, modify `swebench_backticks_regression_guard.yaml` to address the most common P2P failure patterns.

**File path**: `/home/22pf2/SWE-Bench_Replication/mini-SWE-agent/src/minisweagent/config/benchmarks/swebench_backticks_regression_guard.yaml`

**Current `<CRITICAL_REGRESSION_GUARD>` block** (lines 54–70):
- Tells solver to identify and run test suite
- Tells solver to revise if regressions detected
- Tells solver to make minimal changes

**Potential improvements** (choose based on Step 1 analysis):
1. **Pre-patch baseline**: "Run the test suite BEFORE making any changes, record results, then verify tests still pass after your changes"
2. **Patch minimality**: "Only modify the minimum necessary lines. Avoid refactoring, renaming, or restructuring"
3. **Targeted test instructions**: If most failures are in specific patterns (imports, integration, etc.), add explicit guidance
4. **Two-phase validation**: "First ensure your fix passes FAIL_TO_PASS tests, then verify PASS_TO_PASS tests, then refine if needed"
5. **Dependency checks**: "Before submitting, verify all imports, dependencies, and type hints are correct"

**Edit the `<CRITICAL_REGRESSION_GUARD>` block** with improvements, keeping total prompt length reasonable (~270 lines, matching current).

### Step 3: Re-run Pipeline with Improved Prompt

After modifying the prompt:

```bash
# Ensure vLLM is running (should be persistent)
# Check: curl http://127.0.0.1:18000/v1/models

# Set environment variables
export CODE_CONTEXT_DATASET_JSONL=data/samples/groupC_swebenchlive_50/groupC50_dataset.jsonl
export CODE_CONTEXT_INCLUDE_SOURCE=1
export CODE_CONTEXT_INCLUDE_HINTS=1
export CODE_CONTEXT_INCLUDE_FAILING_TESTS=1
export CODE_CONTEXT_INCLUDE_TEST_PATCH=1

# Run the pipeline
# NOTE: --skip-baseline reuses existing baseline from previous experiment
bench_env/bin/python scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py \
  --enhancer-agent code_context \
  --output-tag code_context_devstral_tp_regguard_v2_groupC50_$(date +%Y%m%d) \
  --dataset-jsonl data/samples/groupC_swebenchlive_50/groupC50_dataset.jsonl \
  --selected-ids-file data/samples/groupC_swebenchlive_50/groupC50_instance_ids.txt \
  --samples-json data/samples/groupC_swebenchlive_50/groupC50_samples.json \
  --max-issues 50 \
  --namespace starryzhang \
  --allow-identical-enhancements \
  --max-enhanced-body-chars 30000 \
  --solver-workers 4 \
  --eval-workers 4 \
  --skip-baseline \
  --results-root results/groupC50_p2p_improved \
  --benchmark-config swebench_backticks_regression_guard.yaml
```

**Important**: The `--skip-baseline` flag reuses the existing baseline from a previous run. If you're starting fresh, you may need to run without this flag once.

### Step 4 (Optional): Try Stronger Solver Model

If available (GPT-4o, Claude Sonnet), it might follow regression guard instructions better:

1. Create model override YAML: `/home/22pf2/SWE-Bench_Replication/config/<new_model>_override.yaml`
2. Run with: `--model-override-config <new_model>_override.yaml`

---

## Success Criteria

| Metric | Current | Target |
|--------|:-------:|:------:|
| **F2P** | 27/50 (54%) | Maintain or improve |
| **P2P** | 4/50 (8%) | **>8/50 (>16%)** |
| **Resolved** | 1/50 (2%) | **>2/50 (>4%)** |

**Primary goal**: Improve P2P without losing F2P.

---

## Key Files

| Path | Purpose |
|------|---------|
| `src/enhancers/ready_to_use/code_context_enhancer.py` | Enhancer (don't modify) |
| `/home/22pf2/SWE-Bench_Replication/mini-SWE-agent/src/minisweagent/config/benchmarks/swebench_backticks_regression_guard.yaml` | **EDIT THIS** — solver prompt |
| `scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py` | Workflow (don't modify) |
| `data/samples/groupC_swebenchlive_50/` | 50-issue dataset |
| `results/groupC50_p2p_approachB/code_context__code_context_devstral_tp_regguard_groupC50_20260414/` | Current best results |
| `docs/groupC_50_issue_experiment_report.md` | Full report (sections 12.12–12.16 most relevant) |
| `docs/handoff/HANDOFF_IMPROVE_ENHANCER_PERFORMANCE.md` | Detailed handoff document |

---

## Constraints

- **Do NOT modify the code-context enhancer** — it's working well
- **Do NOT use standard `swebench_backticks.yaml`** — always use regression guard version
- **Do NOT retry loops** — counterproductive
- **Do NOT change the dataset** — 50-issue SWE-bench-Live is fixed
- **Do NOT modify ground-truth patches/tests** — fixed data

---

## Research Context

Our pipeline enhances issue descriptions before feeding them to an automated bug-fixing solver. The code-context enhancer uniquely helps by adding **real information** (source code, test specs) instead of just **rewriting** the issue like other enhancers do.

- LLM-based enhancers (TRAE, SWE-agent, Aider): 0% to -14% effect
- Code-context (deterministic): +26% F2P, +4% P2P (our best)

The bottleneck is now P2P (regressions), not F2P (fixing bugs). Prompt engineering has proven more effective than data engineering for this problem.

---

## Questions?

Refer to:
1. `docs/handoff/HANDOFF_IMPROVE_ENHANCER_PERFORMANCE.md` — comprehensive handoff
2. `docs/groupC_50_issue_experiment_report.md` — full experiment details
3. `docs/MAIN.md` — documentation index
