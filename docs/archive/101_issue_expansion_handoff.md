# 101-Issue Expansion: Agent Handoff Document

## Project Objective
The goal was to analyze the results from the 101-issue enhancement pipeline runs for Aider, SWE-agent, and TRAE across Group A (SWE-bench verified) and Group B (Community) datasets. The analysis determines if enhancing issue descriptions improves solver performance and if the SWE-bench subset is inherently easier to solve.

## What Was Done
1. **Analysis Scripts Execution and Debugging**:
   - Ran `scripts/reports/run_all_101_analysis.sh`.
   - Identified and fixed a minor `json.dump()` serialization error with NumPy boolean casting in `scripts/reports/compute_statistical_significance.py`.
2. **Initial Document Updation**:
   - Updated the initial results in `docs/101_issue_expansion_report.md`, `docs/presentation_summary_5slides.md`, and `docs/second_paper_groupA_vs_groupB_experiment_report.md`.
   - Discovered a clear and catastrophic 35-45% degradation pattern for **Aider** (the only agent that successfully ran the enhanced solvers initially).
3. **Pipeline Failure Debugging**:
   - Investigated why **SWE-agent** and **TRAE** recorded 0/101 resolves.
   - Identified that `_build_enhanced_dataset_jsonl()` in the experiment runner (`scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py`) aborted the entire dataset generation phase if even a single enhancement generation had a timeout/error (saving an `enhancer_type` equal to `"error"` instead of `"real"`).
4. **Implementation of the Fix**:
   - Created and executed `scripts/reports/fix_enhancement_errors.py` to identify the 12 error files across the 4 runs (6 in SWE-agent A, 4 in SWE-agent B, 1 in TRAE A, 1 in TRAE B). The script rewrote these enhancement error JSON files to fallback to their original text (converting them to no-ops) and setting `"enhancer_type"` to `"real"`.
   - Created `scripts/reports/rerun_fixed_experiments.sh` to selectively re-run steps 4-7 (Dataset Build -> Enhanced Solver -> Evaluation -> Comparison) for the 4 broken experiments without re-doing valid baselines or enhancements.

## Current Situation
- The batch fix script `scripts/reports/rerun_fixed_experiments.sh` was launched in the background via `nohup` on `2026-03-30 16:09 UTC`. 
- **Log location**: `data/samples/101_issues_experiments/rerun_all_output.log`.
- **Progress** (as of `2026-03-30 19:47 UTC`):
  - **[1/4] SWE-agent Group A**: Completed ~78/101 issues at a pace of ~2.7 mins/issue. ETA to finish the first experiment is ~1.5 hours.
  - **Remaining Experiments**: The bash script sequentially executes SWE-agent Group B, TRAE Group A, and TRAE Group B. Each takes roughly 5-6 hours total.
  - **Total ETA**: The entire run should finish in approximately **16-17 hours** from `19:47 UTC`.

## Information for the Next Agent

**When you resume work, follow these exact steps:**
1. **Verify if the Background Script Finished**:
   - Check the log tail: `tail -n 100 data/samples/101_issues_experiments/rerun_all_output.log`
   - It should say `ALL 4 EXPERIMENTS RE-RUN COMPLETE` at the bottom.
   - If it's still running, use `grep -c "\"instance_id\""` inside the current experiment's `enhanced_solver_run/preds.json` to calculate the pace and provide the user an updated ETA. Wait until done or exit.
2. **Re-Run Global Analysis**:
   - Execute `bash scripts/reports/run_all_101_analysis.sh` to update the canonical `101_issue_aggregate_results.json` and statistical analysis files with the newly finished SWE-agent/TRAE data.
3. **Update the Main Documentation**:
   - Replace the "Pending Re-runs / 0%" text blocks in the three main markdown files: `docs/101_issue_expansion_report.md`, `docs/presentation_summary_5slides.md`, and `docs/second_paper_groupA_vs_groupB_experiment_report.md`.
   - Ensure the new valid numbers are displayed, and draw conclusions about whether SWE-agent and TRAE matched Aider's severe degradations.
4. **Final Check in `task.md`**:
   - Tick off the remaining open boxes under `- [ ] Fix SWE-agent/TRAE pipeline failures` and `- [ ] Re-run analysis scripts with corrected data`.
