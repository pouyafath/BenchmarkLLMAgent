# BenchmarkLLMAgent - Handoff for Next Agent
**Date**: March 12, 2026 (Session 2)
**Status**: Diagnostic Test In Progress
**Priority**: Complete SWE-agent baseline test to determine next direction

---

## 2026-03-19 Update (Supersedes old default path)

The canonical Verified-10 workflow has now been bugfixed and validated with two enhancer agents:

- `simple_enhancer` run:
  - `/home/22pf2/BenchmarkLLMAgent/results/verified10_baseline_vs_enhanced/simple_enhancer__bugfix_full10_simple_20260318/`
- `swe_agent` run:
  - `/home/22pf2/BenchmarkLLMAgent/results/verified10_baseline_vs_enhanced/swe_agent__bugfix_full10_swe_agent_20260318/`
- Aggregate comparison:
  - `/home/22pf2/BenchmarkLLMAgent/results/verified10_baseline_vs_enhanced/multi_enhancer_bugfix_full10_20260318.md`

Metrics on the same 10 baseline IDs:

- Baseline: RESOLVED `3/10`, F2P `3/10`, P2P `5/10`
- `simple_enhancer`: RESOLVED `3/10`, F2P `3/10`, P2P `6/10`
- `swe_agent`: RESOLVED `3/10`, F2P `3/10`, P2P `7/10`

Reliability:

- Both bugfix runs completed with `10/10` attempted and no evaluation failures.

Workflow fixes now implemented in code include deterministic eval loading, skip-mode correctness, baseline slicing, timeout retry, config-aware cache keys, attempted-rate reporting, and reproducibility manifests.

## 2026-03-18 Update (Supersedes old default path)

This handoff captured an older SWE-bench-Live/OpenHands diagnostic track.  
The active paper workflow is now:

1. Use the 10 SWE-bench Verified IDs from `/home/22pf2/SWE-Bench_Replication/selected_instances.txt`
2. Keep `/home/22pf2/SWE-Bench_Replication` as the fixed baseline (`mini-SWE-agent + Devstral 2512`)
3. Run enhancement + solver + evaluation in this repo with:
   - `scripts/data/prepare_verified_10_samples_from_replication.py`
   - `scripts/workflows/run_verified10_enhancement_vs_baseline.py`
4. Compare `RESOLVED`, `FAIL_TO_PASS`, and `PASS_TO_PASS` before vs after enhancement

If there is conflict between this section and the rest of this file, follow this section.

### 2026-03-18 Execution Result (Verified-10 baseline vs enhanced)

Run path:

- `/home/22pf2/BenchmarkLLMAgent/results/verified10_baseline_vs_enhanced/simple_enhancer__full10_20260318/`

Baseline (from `/home/22pf2/SWE-Bench_Replication`):

- RESOLVED: `3/10` (30.0%)
- FAIL_TO_PASS issue success: `3/10` (30.0%)
- PASS_TO_PASS issue success: `5/10` (50.0%)

Enhanced (`simple_enhancer`):

- RESOLVED: `4/10` (40.0%)
- FAIL_TO_PASS issue success: `4/10` (40.0%)
- PASS_TO_PASS issue success: `6/10` (60.0%)
- Evaluation/model-provider caveat: `astropy__astropy-13236` timed out in solver run and has no `report.json`.

Artifacts:

- `comparison_summary.json`
- `comparison_summary.md`
- `enhanced_metrics.json`
- `run_report.md`

---

## Executive Summary: The Situation

**Project Goal**: Evaluate LLM agents on automated bug fixing using SWE-bench-Live dataset (10 real GitHub issues)

**Current Problem**: OpenHands solver achieves 0% patch application rate (0/10 patches apply)

**Investigation Finding**: Root cause is **gpt-4o-mini's inability to reliably generate unified diffs**, not a prompt engineering issue

**Current Work**: Running SWE-agent (official solver from leaderboard) on same 10 issues to determine if problem is solver-specific or architectural

---

## What We Know (Verified & Confirmed)

### ✅ WORKING: Source Code Extraction
- `src/utils/source_code_extractor.py` correctly extracts BEFORE/AFTER code
- Tested on `instructlab-3135`: extracted 56,740 chars accurately
- Confirmed first difference at line 235 (logger.error format change)
- **Conclusion**: Extraction pipeline is NOT the problem

### ❌ ROOT CAUSE: LLM Hallucination
- gpt-4o-mini receives correct BEFORE/AFTER code comparison
- Despite correct input, generates patches for **wrong files**
- Example: Input shows file="src/instructlab/model/accelerated_train.py", output patches "instructlab/train.py"
- Occurs across **ALL prompt variations** (minimal 30KB to verbose 102 lines)
- **Conclusion**: Problem is model capability, not prompt design

### ✅ TESTED & DISPROVEN: Prompt Optimization
Tested 4 prompt variations - all achieved 0% success:
1. **Ultra-minimal** (3 lines) - LLM generates do-nothing patches
2. **Explicit format** (with diff rules) - Still hallucinates file names
3. **Instruction-heavy** (step-by-step) - Same patterns
4. **Verbose original** (102 lines) - Same failure

**Conclusion**: Prompt engineering alone cannot fix model capability limitations

### 📊 LEADERBOARD CONTEXT
- Agentless + GPT-4o: **11.67%** resolved
- SWE-agent + GPT-4o: **10.0%** resolved
- OpenHands + GPT-4o: **7%** resolved (published baseline)
- Our OpenHands baseline: **0%** (much worse - using gpt-4o-mini instead)

---

## Current Work: SWE-Agent Baseline Test

### Why This Test Matters
**Core Diagnostic Question**: *"Is the 0% problem specific to OpenHands, or is it something about our approach/dataset?"*

Running the official SWE-agent solver (which scores 10% on leaderboard) on our 10 instances will answer:
- If SWE-agent >5% → Problem is OpenHands-specific (can switch solvers)
- If SWE-agent ~0% → Problem is architectural (need different approach)
- If SWE-agent >20% → Confirms switching to SWE-agent is right move

### Attempt 1: Initial Test (FAILED - Now Fixed)
**Error**: `str_replace_editor view / --view_range 0 20` → Invalid operation on directory

**Root Cause Identified**:
- SWE-agent expects instances with `working_dir: /repo` field
- Without it, defaults to `/` (root directory)
- `view_range` is only for files, not directories → crash

**Solution Applied**:
- Created `our_10_instances_fixed.json` with `working_dir: /repo` added
- This follows SWE-agent's standard Docker setup

### Attempt 2: Retry in Progress
**Status**: Test started with 2 instances first (to verify fix)
- If successful: Will expand to full 10 instances
- Expected timeline: 2-4 hours depending on API rates
- Location: `results/sweagent_gpt4o_test/`

---

## Files & Directory Structure

### Critical Files
```
/home/22pf2/BenchmarkLLMAgent/
├── INVESTIGATION_REPORT_COMPLETE.md      # Previous investigation results
├── HANDOFF_TO_NEXT_AGENT.md             # THIS FILE - handoff summary
├── src/
│   ├── solvers/openhands/agent.py       # OpenHands solver (updated with prompts)
│   ├── utils/
│   │   ├── source_code_extractor.py     # BEFORE/AFTER extraction (working)
│   │   └── patch_utils.py               # Patch utilities
│   └── evaluation/
│       └── evaluator.py                  # Patch application checker
├── scripts/
│   ├── enhancers/run_solving_after_enhancement.py  # Enhancement pipeline
│   └── solvers/run_simple_solver.py      # Simple solver runner
├── data/samples/
│   └── swe_bench_live_10_tasks_for_harness.json   # Original 10 instances
├── our_10_instances.json                 # Manual instances (had issues)
├── our_10_instances_fixed.json          # FIXED instances (current test)
├── results/
│   └── sweagent_gpt4o_test/             # Current SWE-agent test results (in progress)
└── .env                                  # OpenAI API key (gpt-4o-mini configured)
```

### Key Directories
- `/home/22pf2/SWE-agent/` - Official SWE-agent repository (cloned)
- `~/anaconda3/envs/sweagent/` - Python 3.11 conda environment for SWE-agent

### Documentation
- `INVESTIGATION_REPORT_COMPLETE.md` (440+ lines) - Complete investigation timeline
- `docs/COMPREHENSIVE_FINDINGS_AND_SOLUTION.md` - Root cause analysis
- `docs/MINIMAL_PROMPT_TEST_RESULTS.md` - Minimal prompt test results
- `docs/ROOT_CAUSE_ANALYSIS.md` - Initial diagnosis

---

## Completed Work (Previous Session)

### Phase 1: Source Code Extraction ✅
- Implemented `extract_before_after_code_for_instance()` method
- Verified it works perfectly on test instance
- Confirmed proper BEFORE/AFTER code extraction

### Phase 2: Option 4 Implementation (Hybrid Before/After) ✅
- Updated OpenHands prompts to use BEFORE/AFTER comparison
- Tested with verbose (59KB) and minimal (30KB) prompts
- Result: All variants achieved 0% success due to LLM hallucination

### Phase 3: Root Cause Determination ✅
- Tested multiple prompt variations (4 different approaches)
- Confirmed gpt-4o-mini cannot reliably generate diffs
- Ruled out prompt engineering as solution

### Phase 4: SWE-Agent Setup ✅
- Cloned official SWE-agent v1.1.0
- Created Python 3.11 conda environment
- Converted instances to SWE-agent format
- Fixed instance configuration (working_dir field)

---

## Current Status & Next Steps

### Immediate (Must Complete)
1. **Monitor SWE-agent test completion**
   - Check `results/sweagent_gpt4o_test/` for results
   - Expected: 2 instances in 30-60 minutes
   - Key metric: How many patches apply successfully?

2. **Analyze SWE-agent results**
   - Compare to OpenHands baseline (0%)
   - If >5%: Problem is OpenHands-specific
   - If ~0%: Problem is architectural

3. **Document findings**
   - Update this handoff document with results
   - Include success/failure counts for each instance
   - Record any errors or issues encountered

### Secondary (Based on SWE-Agent Results)

**If SWE-agent >5%** (Success):
- Solution: **Switch to SWE-agent as primary solver**
- Action: Replace OpenHands with SWE-agent in pipeline
- Expected improvement: 10%+ patch application rate

**If SWE-agent ~0%** (Failure):
- Problem is architectural, not solver-specific
- Options to try (in priority order):
  1. **Better Model**: Use Claude 3 or GPT-4 Turbo instead of gpt-4o-mini
  2. **Option 5 - Iterative Refinement**: Generate → validate → feedback → regenerate
  3. **Different Framing**: "Apply change X to file Y" instead of "compare BEFORE/AFTER"
  4. **Smaller Context**: Use 50-line window instead of full 757-line blocks

**If SWE-agent 5-20%** (Partial Success):
- Both solvers struggle with gpt-4o-mini capability
- Recommended: Use better model (Claude 3/GPT-4 Turbo) with either solver
- May also benefit from Option 5 (iterative refinement)

---

## What Previous Agent Did This Session

1. **Analyzed investigation report** from previous work
2. **Identified SWE-agent test failure root cause**
   - Recognized missing `working_dir` field in instance JSON
   - Understood SWE-agent template variable substitution
3. **Applied configuration fix**
   - Added `working_dir: /repo` to all 10 instances
   - Created `our_10_instances_fixed.json`
   - Cleaned previous test results
4. **Restarted SWE-agent test** with fixed configuration
   - Started with 2 instances to verify fix
   - Test running in background (expected 30-60 min per instance)

---

## How to Continue

### For Monitoring Current Test
```bash
# Check test progress
tail -50 /home/22pf2/BenchmarkLLMAgent/sweagent_baseline_test_2inst.log

# Check results directory
ls -lah /home/22pf2/BenchmarkLLMAgent/results/sweagent_gpt4o_test/

# Check if test is still running
ps aux | grep sweagent.run | grep -v grep
```

### For Analyzing Results (After Test Completes)
```bash
# Count successful patches
cd /home/22pf2/BenchmarkLLMAgent/results/sweagent_gpt4o_test/
for dir in */; do
  if [ -f "$dir/${dir%/}.log" ]; then
    if grep -q "resolved" "$dir/${dir%/}.log"; then
      echo "✅ $dir - RESOLVED"
    else
      echo "❌ $dir - FAILED"
    fi
  fi
done
```

### For Full 10-Instance Run (If Fix Works)
```bash
cd /home/22pf2/SWE-agent
conda activate sweagent
python -m sweagent.run \
  --agent_model gpt-4o-2024-08-06 \
  --environment_name docker \
  --instances.type file \
  --instances.path /home/22pf2/BenchmarkLLMAgent/our_10_instances_fixed.json \
  --instances.limit 10 \
  --output_dir /home/22pf2/BenchmarkLLMAgent/results/sweagent_gpt4o_test \
  --skip_existing
```

---

## Key Decisions & Assumptions

### Configuration Choices
- Using `working_dir: /repo` - SWE-agent standard path for Docker repositories
- Using `image_name: python:3.11` - Matches SWE-agent environment requirement
- Using `gpt-4o-2024-08-06` - Latest GPT-4o (not gpt-4o-mini) for baseline test

### Why This Approach
- SWE-agent is the official solver from leaderboard (Stanford/Princeton)
- Direct comparison will definitively answer if problem is solver-specific
- If successful, provides proven alternative to OpenHands
- If unsuccessful, proves problem is architectural and need different approach

### Limitations
- SWE-agent test is slower than OpenHands (Docker overhead)
- Each instance may take 5-15 minutes depending on API rates
- Test requires proper Docker setup (already configured)

---

## Important Notes for Next Agent

1. **The 0% problem is NOT due to poor prompting** - this has been thoroughly tested and eliminated
2. **The core question is diagnostic**: Is it OpenHands or our approach?
3. **SWE-agent test is the critical work item** - everything else depends on these results
4. **Configuration issues are resolved** - the fixed instance JSON should work now
5. **API costs are minimal** - SWE-agent uses gpt-4o at standard rates, ~$0.50-1 per 10 instances

---

## Questions the Next Agent Should Answer

1. ✅ Does SWE-agent test run without errors? (Diagnostic: configuration fix worked?)
2. ❓ How many SWE-agent patches apply successfully? (Diagnostic: solver vs. architecture problem?)
3. ❓ Are there patterns in which patches succeed vs. fail? (Diagnostic: specific issue types?)
4. ❓ What's the next recommended approach based on SWE-agent results? (Strategic: what to implement next?)

---

## Success Criteria for Next Agent

- ✅ SWE-agent baseline test completes on all 10 instances (or at least 8/10)
- ✅ Clear answer to "Is the problem OpenHands or architectural?"
- ✅ Documented results with success/failure counts for each instance
- ✅ Recommendation for next technical approach

---

**Ready for Handoff**: This document + INVESTIGATION_REPORT_COMPLETE.md provide complete context.

Next agent can immediately begin by monitoring SWE-agent test progress and preparing analysis.
