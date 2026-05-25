# Next Steps: SWE-Agent Baseline Test Execution

> Superseded for current paper workflow (2026-03-18).
>
> Use the Verified-10 canonical workflow instead:
>
> ```bash
> cd /home/22pf2/BenchmarkLLMAgent
> /home/22pf2/SWE-Bench_Replication/.venv312/bin/python scripts/data/prepare_verified_10_samples_from_replication.py
> ./bench_env/bin/python scripts/workflows/run_verified10_enhancement_vs_baseline.py --enhancer-agent simple_enhancer --output-tag run1
> ```
>
> Latest completed run:
> `results/verified10_baseline_vs_enhanced/simple_enhancer__full10_20260318/`
> with enhanced metrics RESOLVED `4/10`, FAIL_TO_PASS issue success `4/10`, PASS_TO_PASS issue success `6/10`.

**Date**: March 12, 2026
**Status**: Ready to execute SWE-agent baseline test
**Prepared By**: Claude Code (previous agent)

---

## What Needs to Happen Now

The most critical task is to **complete the SWE-agent baseline test** to answer the core diagnostic question:

> **"Is the 0% patch application rate due to OpenHands solver, or is it an architectural problem with our approach/dataset?"**

---

## Quick Start Guide

### Option A: Run Full 10-Instance Test (Recommended)

```bash
cd /home/22pf2/BenchmarkLLMAgent
bash run_sweagent_baseline_test.sh
```

**Expected**:
- Takes 2-4 hours to complete (10-30 min per instance due to Docker overhead)
- Outputs results to `results/sweagent_gpt4o_test/`
- Each instance directory contains:
  - `<instance_id>.traj` - Full trajectory (agent's thinking and actions)
  - `<instance_id>.debug.log` - Detailed debug logs
  - `<instance_id>.info.log` - High-level info logs

### Option B: Test with 2 Instances First (Verification)

If you want to verify the configuration fix works:

```bash
cd /home/22pf2/SWE-agent
eval "$(conda shell.bash hook)"
conda activate sweagent
source /home/22pf2/BenchmarkLLMAgent/.env

python -m sweagent.run \
  --agent_model gpt-4o-2024-08-06 \
  --environment_name docker \
  --instances.type file \
  --instances.path /home/22pf2/BenchmarkLLMAgent/our_10_instances_fixed.json \
  --instances.limit 2 \
  --output_dir /home/22pf2/BenchmarkLLMAgent/results/sweagent_gpt4o_test \
  --skip_existing
```

**Expected**: 2 instances in 30-60 minutes

### Option C: Monitor Existing Test (If Already Running)

```bash
# Check if test is running
ps aux | grep "sweagent.run" | grep -v grep

# Check results as they come in
ls -lh /home/22pf2/BenchmarkLLMAgent/results/sweagent_gpt4o_test/

# Check latest logs
tail -20 /home/22pf2/BenchmarkLLMAgent/results/sweagent_gpt4o_test/*/debug.log 2>/dev/null | head -50
```

---

## After Test Completion

### Analyze Results

```bash
cd /home/22pf2/BenchmarkLLMAgent
python analyze_sweagent_results.py
```

This will output:
- Success count (how many patches applied successfully)
- Success percentage
- Comparison to OpenHands baseline (0%)
- Recommended next action

### Interpret Results

**If SWE-agent >5% success rate**:
- ✅ Problem is OpenHands-specific
- 🎯 Action: Switch to SWE-agent as primary solver
- 💰 Cost: Medium (requires Docker, slightly slower)
- ⏱️ Timeline: 1-2 days to integrate

**If SWE-agent ~0% success rate**:
- ❌ Problem is architectural (our approach/dataset)
- 🎯 Next action options (in priority order):
  1. **Try better model** (Claude 3 or GPT-4 Turbo)
     - Effort: Low (just change model)
     - Cost: Higher (~2x)
     - Time: 1 hour
  2. **Try Option 5 (Iterative Refinement)**
     - Generate patch → validate → feedback → regenerate
     - Effort: Medium
     - Expected improvement: 30-50% success
     - Time: 3-5 days
  3. **Try different framing**
     - Instead of "compare BEFORE/AFTER", try "apply this change to this file"
     - Effort: High (redesign approach)
     - Time: 5-7 days

**If SWE-agent 5-20%**:
- ⚠️ Both solvers struggle
- 🎯 Try better model first (Claude 3/GPT-4 Turbo)
- Then consider Option 5 if still insufficient

---

## Key Files to Reference

| File | Purpose |
|------|---------|
| `INVESTIGATION_REPORT_COMPLETE.md` | Full investigation history and findings |
| `HANDOFF_TO_NEXT_AGENT.md` | Comprehensive handoff document |
| `our_10_instances_fixed.json` | **CRITICAL** - Fixed instances with `working_dir` |
| `run_sweagent_baseline_test.sh` | Executable test script |
| `analyze_sweagent_results.py` | Results analysis script |
| `.env` | OpenAI API configuration |

---

## Important Notes

### Configuration is Fixed ✅
- Previous test failed due to missing `working_dir: /repo` in instances
- This has been added to `our_10_instances_fixed.json`
- No further configuration changes should be needed

### API Cost Estimate
- SWE-agent with gpt-4o-2024-08-06: ~$0.05-0.10 per instance
- 10 instances total: ~$0.50-1.00 USD
- Very reasonable for diagnostic test

### Docker Requirements
- SWE-agent requires Docker
- Uses `python:3.11` image (lightweight)
- Containers are spun up per instance and cleaned up
- No persistent Docker containers left behind

### Expected Failure Modes
1. **Docker not available**: Install Docker
2. **OpenAI API key invalid**: Check `.env` file
3. **Instance format wrong**: Use `our_10_instances_fixed.json` (already fixed)
4. **Out of memory**: Docker may need more RAM (usually not an issue)
5. **Timeout**: API latency or rate limiting (retry will handle)

---

## Success Criteria

- ✅ Test runs without configuration errors
- ✅ All 10 instances process (or at least 8/10)
- ✅ Clear success/failure counts for each instance
- ✅ Definitive answer to "OpenHands or architectural?"
- ✅ Documented recommendation for next direction

---

## Timeline Estimate

- **Setup & verification**: 5-10 minutes
- **Test execution**: 2-4 hours (running)
- **Result analysis**: 10-15 minutes
- **Decision & recommendation**: 15-30 minutes
- **Total**: ~2.5-4.5 hours

---

## Questions to Answer

After completing the test, the next agent should document answers to:

1. **How many patches applied successfully with SWE-agent?**
   - Number and percentage

2. **What's the pattern in successes vs failures?**
   - Are certain issue types more likely to succeed?
   - Specific errors or patterns?

3. **Is the problem OpenHands or architectural?**
   - Clear yes/no answer based on results

4. **What's the recommended next action?**
   - Based on SWE-agent results and previous findings

5. **Any configuration or setup issues encountered?**
   - Helps with future runs

---

## Contact & Handoff

- **Previous Agent**: Claude Code (Haiku 4.5)
- **Prepared**: March 12, 2026
- **Status**: Ready for execution
- **Next Phase**: Determined by SWE-agent results

---

**You are ready to proceed with the SWE-agent baseline test. Run the test script and analyze results.**
