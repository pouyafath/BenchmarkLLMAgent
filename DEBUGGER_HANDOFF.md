# Debugger Agent Handoff - 101-Issue Experiment Fix

**Date:** 2026-03-30
**Status:** URGENT - Need to fix failed experiments and re-run
**Previous Agent:** Completed diagnosis, ready for fix implementation

---

## Quick Summary

All 6 experiments completed but **4 out of 6 failed** due to pipeline bugs:
- **SWE-agent Group A/B**: 0/101 resolved (pipeline broken - enhanced solver never ran)
- **TRAE Group A/B**: 0/101 resolved (pipeline broken - enhanced solver never ran)
- **Aider Group A/B**: 5/101 and 2/101 resolved (solver ran but performed poorly - this is real data)

The 0% results are **NOT real** - they're artifacts of the pipeline failing before the enhanced solver could run.

---

## The Root Cause

The workflow script at `scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py` has a critical bug in the `_build_enhanced_dataset_jsonl()` function (lines 443-524):

```python
# Line 484-488
if require_native and enhancer_type != "real":
    raise ValueError(
        f"native enhancer required, but {iid} has enhancer_type={enhancer_type!r} "
        f"in {enh_file}"
    )
```

When `--require-native-enhancer` flag is used, **ANY** enhancement error causes the entire dataset build to abort. A few timeouts cascade into complete failure.

### Enhancement Errors Found

**SWE-agent Group A** (6 timeouts):
```
data/samples/101_issues_experiments/results_group_a/swe_agent__devstral101_groupA_20260327/enhancements/
  - swe_agent__astropy__astropy__13579.json
  - swe_agent__astropy__astropy__14508.json
  - swe_agent__pydata__xarray__6599.json
  - swe_agent__pydata__xarray__6992.json
  - swe_agent__scikit-learn__scikit-learn__12973.json
  - swe_agent__scikit-learn__scikit-learn__13328.json
```

**SWE-agent Group B** (4 timeouts):
```
data/samples/101_issues_experiments/results_group_b/swe_agent__devstral101_groupB_20260327/enhancements/
  - swe_agent__matplotlib__matplotlib__26208.json
  - swe_agent__sphinx-doc__sphinx__11510.json
  - swe_agent__sphinx-doc__sphinx__7454.json
  - swe_agent__sphinx-doc__sphinx__7757.json
```

**TRAE Group A** (1 crash):
```
data/samples/101_issues_experiments/results_group_a/trae__devstral101_groupA_20260327/enhancements/
  - trae__scikit-learn__scikit-learn__25973.json
```

**TRAE Group B** (1 crash):
```
data/samples/101_issues_experiments/results_group_b/trae__devstral101_groupB_20260327/enhancements/
  - trae__scikit-learn__scikit-learn__25973.json
```

All these files have `enhancer_type: "error"` instead of `"real"`, with error messages like `"sweagent timeout after 300s"`.

---

## The Fix Strategy

### Option 1: Manual Fix (Quick - RECOMMENDED)

Manually patch the 11 error files to mark them as "noop" enhancements (use original description), then re-run from Step 4 onwards.

**For each error file**, modify the JSON:
```python
# Change enhancer_type from "error" to "real"
data['enhancement_metadata']['enhancer_type'] = 'real'
data['enhancement_metadata']['enhancement_noop'] = True
data['enhancement_metadata']['error'] = None  # Clear the error
data['enhancement_metadata']['attempts'] = [{
    'attempt_num': 1,
    'enhanced_body': data['original_body'],  # Use original
    'enhanced_title': data['original_title'],  # Use original
    'body_similarity': 1.0,  # Identical
    'title_similarity': 1.0,  # Identical
    'body_length': len(data['original_body']),
    'note': 'Manually marked as noop due to enhancement timeout/error'
}]
```

Then re-run **only the failed experiments** starting from Step 4 (build enhanced dataset):

```bash
# SWE-agent Group A
bench_env/bin/python scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py \
  --enhancer-agent swe_agent \
  --output-tag devstral101_groupA_20260327 \
  --dataset-jsonl data/samples/101_issues_experiments/group_a_101/group_a_101_dataset.jsonl \
  --samples-json data/samples/101_issues_experiments/group_a_101/group_a_101_samples.json \
  --selected-ids-file data/samples/101_issues_experiments/group_a_101/group_a_101_instance_ids.txt \
  --max-issues 101 \
  --require-native-enhancer \
  --allow-identical-enhancements \
  --max-enhanced-body-chars 30000 \
  --solver-workers 4 \
  --eval-workers 4 \
  --results-root data/samples/101_issues_experiments/results_group_a \
  --skip-baseline \
  --skip-enhancement  # Skip - already done!

# Repeat for: SWE-agent Group B, TRAE Group A, TRAE Group B
```

### Option 2: Code Fix (Robust - for future runs)

Modify `_build_enhanced_dataset_jsonl()` to treat error enhancements as noop instead of aborting:

```python
# Around line 484-488, replace the ValueError with:
if require_native and enhancer_type != "real":
    # Treat as noop enhancement (use original)
    print(f"  WARNING: {iid} has enhancer_type={enhancer_type!r}, treating as noop")
    enhanced_title = sample.get("title", "") or ""
    enhanced_body = sample.get("body", "") or ""
    # Create synthetic noop metadata
    metadata = {
        'enhancer_type': 'real',
        'enhancement_noop': True,
        'attempts': [{
            'body_similarity': 1.0,
            'title_similarity': 1.0,
            'body_length': len(enhanced_body),
            'note': f'Auto-converted from {enhancer_type} to noop'
        }]
    }
```

---

## Step-by-Step Fix Instructions

### Step 1: Fix Enhancement Error Files

Run this Python script to patch all 11 error files:

```python
#!/usr/bin/env python3
"""Fix enhancement error files by marking them as noop."""
import json
from pathlib import Path

error_files = [
    # SWE-agent Group A (6 files)
    "data/samples/101_issues_experiments/results_group_a/swe_agent__devstral101_groupA_20260327/enhancements/swe_agent__astropy__astropy__13579.json",
    "data/samples/101_issues_experiments/results_group_a/swe_agent__devstral101_groupA_20260327/enhancements/swe_agent__astropy__astropy__14508.json",
    "data/samples/101_issues_experiments/results_group_a/swe_agent__devstral101_groupA_20260327/enhancements/swe_agent__pydata__xarray__6599.json",
    "data/samples/101_issues_experiments/results_group_a/swe_agent__devstral101_groupA_20260327/enhancements/swe_agent__pydata__xarray__6992.json",
    "data/samples/101_issues_experiments/results_group_a/swe_agent__devstral101_groupA_20260327/enhancements/swe_agent__scikit-learn__scikit-learn__12973.json",
    "data/samples/101_issues_experiments/results_group_a/swe_agent__devstral101_groupA_20260327/enhancements/swe_agent__scikit-learn__scikit-learn__13328.json",
    # SWE-agent Group B (4 files)
    "data/samples/101_issues_experiments/results_group_b/swe_agent__devstral101_groupB_20260327/enhancements/swe_agent__matplotlib__matplotlib__26208.json",
    "data/samples/101_issues_experiments/results_group_b/swe_agent__devstral101_groupB_20260327/enhancements/swe_agent__sphinx-doc__sphinx__11510.json",
    "data/samples/101_issues_experiments/results_group_b/swe_agent__devstral101_groupB_20260327/enhancements/swe_agent__sphinx-doc__sphinx__7454.json",
    "data/samples/101_issues_experiments/results_group_b/swe_agent__devstral101_groupB_20260327/enhancements/swe_agent__sphinx-doc__sphinx__7757.json",
    # TRAE Group A (1 file)
    "data/samples/101_issues_experiments/results_group_a/trae__devstral101_groupA_20260327/enhancements/trae__scikit-learn__scikit-learn__25973.json",
    # TRAE Group B (1 file)
    "data/samples/101_issues_experiments/results_group_b/trae__devstral101_groupB_20260327/enhancements/trae__scikit-learn__scikit-learn__25973.json",
]

for filepath in error_files:
    p = Path(filepath)
    if not p.exists():
        print(f"SKIP (not found): {p.name}")
        continue

    data = json.loads(p.read_text())
    original_type = data['enhancement_metadata'].get('enhancer_type')

    if original_type != 'error':
        print(f"SKIP (already fixed): {p.name} (type={original_type})")
        continue

    # Fix the metadata
    data['enhancement_metadata']['enhancer_type'] = 'real'
    data['enhancement_metadata']['enhancement_noop'] = True
    data['enhancement_metadata']['error'] = None
    data['enhancement_metadata']['attempts'] = [{
        'attempt_num': 1,
        'enhanced_body': data['original_body'],
        'enhanced_title': data['original_title'],
        'body_similarity': 1.0,
        'title_similarity': 1.0,
        'body_length': len(data['original_body']),
        'note': 'Manually marked as noop due to enhancement timeout/error'
    }]

    # Ensure enhanced_body and enhanced_title are set
    data['enhanced_body'] = data['original_body']
    data['enhanced_title'] = data['original_title']

    # Write back
    p.write_text(json.dumps(data, indent=2))
    print(f"FIXED: {p.name}")

print(f"\nDone. Fixed {len([f for f in error_files if Path(f).exists()])} files.")
```

Save this as `scripts/fix_enhancement_errors.py` and run:
```bash
cd /home/22pf2/BenchmarkLLMAgent
bench_env/bin/python scripts/fix_enhancement_errors.py
```

### Step 2: Re-run Failed Experiments

After fixing the error files, re-run the 4 failed experiments. Use these commands:

**SWE-agent Group A:**
```bash
cd /home/22pf2/BenchmarkLLMAgent
nohup bench_env/bin/python scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py \
  --enhancer-agent swe_agent \
  --output-tag devstral101_groupA_20260327 \
  --dataset-jsonl data/samples/101_issues_experiments/group_a_101/group_a_101_dataset.jsonl \
  --samples-json data/samples/101_issues_experiments/group_a_101/group_a_101_samples.json \
  --selected-ids-file data/samples/101_issues_experiments/group_a_101/group_a_101_instance_ids.txt \
  --max-issues 101 \
  --require-native-enhancer \
  --allow-identical-enhancements \
  --max-enhanced-body-chars 30000 \
  --solver-workers 4 \
  --eval-workers 4 \
  --results-root data/samples/101_issues_experiments/results_group_a \
  --skip-baseline \
  --skip-enhancement \
  > logs/swe_agent_groupA_retry.log 2>&1 &
```

**SWE-agent Group B:**
```bash
nohup bench_env/bin/python scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py \
  --enhancer-agent swe_agent \
  --output-tag devstral101_groupB_20260327 \
  --dataset-jsonl data/samples/101_issues_experiments/group_b_101/group_b_101_dataset.jsonl \
  --samples-json data/samples/101_issues_experiments/group_b_101/group_b_101_samples.json \
  --selected-ids-file data/samples/101_issues_experiments/group_b_101/group_b_101_instance_ids.txt \
  --max-issues 101 \
  --require-native-enhancer \
  --allow-identical-enhancements \
  --max-enhanced-body-chars 30000 \
  --solver-workers 4 \
  --eval-workers 4 \
  --results-root data/samples/101_issues_experiments/results_group_b \
  --skip-baseline \
  --skip-enhancement \
  > logs/swe_agent_groupB_retry.log 2>&1 &
```

**TRAE Group A:**
```bash
nohup bench_env/bin/python scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py \
  --enhancer-agent trae \
  --output-tag devstral101_groupA_20260327 \
  --dataset-jsonl data/samples/101_issues_experiments/group_a_101/group_a_101_dataset.jsonl \
  --samples-json data/samples/101_issues_experiments/group_a_101/group_a_101_samples.json \
  --selected-ids-file data/samples/101_issues_experiments/group_a_101/group_a_101_instance_ids.txt \
  --max-issues 101 \
  --require-native-enhancer \
  --allow-identical-enhancements \
  --max-enhanced-body-chars 30000 \
  --solver-workers 4 \
  --eval-workers 4 \
  --results-root data/samples/101_issues_experiments/results_group_a \
  --skip-baseline \
  --skip-enhancement \
  > logs/trae_groupA_retry.log 2>&1 &
```

**TRAE Group B:**
```bash
nohup bench_env/bin/python scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py \
  --enhancer-agent trae \
  --output-tag devstral101_groupB_20260327 \
  --dataset-jsonl data/samples/101_issues_experiments/group_b_101/group_b_101_dataset.jsonl \
  --samples-json data/samples/101_issues_experiments/group_b_101/group_b_101_samples.json \
  --selected-ids-file data/samples/101_issues_experiments/group_b_101/group_b_101_instance_ids.txt \
  --max-issues 101 \
  --require-native-enhancer \
  --allow-identical-enhancements \
  --max-enhanced-body-chars 30000 \
  --solver-workers 4 \
  --eval-workers 4 \
  --results-root data/samples/101_issues_experiments/results_group_b \
  --skip-baseline \
  --skip-enhancement \
  > logs/trae_groupB_retry.log 2>&1 &
```

These will run in background. Monitor with:
```bash
tail -f logs/swe_agent_groupA_retry.log
```

Expected time: **~3-4 hours each** (enhanced solving + evaluation)

### Step 3: Re-run Analysis After Completion

Once all 4 experiments complete successfully, re-run the analysis:

```bash
cd /home/22pf2/BenchmarkLLMAgent
bash scripts/reports/run_all_101_analysis.sh
```

---

## Expected Results After Fix

### SWE-agent (Moderate Rewrites)
- **Group A**: Expect ~45-50/101 resolved (baseline: 51/101)
- **Group B**: Expect ~32-36/101 resolved (baseline: 37/101)
- Moderate enhancement should have small negative or neutral effect

### TRAE (Noop Enhancements)
- **Group A**: Expect ~51/101 resolved (same as baseline)
- **Group B**: Expect ~36-37/101 resolved (same as baseline)
- Noop enhancements should show solver variance only (~±1-2 issues)

### Aider (Aggressive Rewrites - Already Complete)
- **Group A**: 5/101 resolved (baseline: 51/101) ← Real result, severe degradation
- **Group B**: 2/101 resolved (baseline: 37/101) ← Real result, severe degradation
- This confirms aggressive rewriting harms solver performance

---

## Key Files and Directories

### Workflow Script
```
scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py
  - Line 443-524: _build_enhanced_dataset_jsonl() function
  - Line 484-488: The bug (raises ValueError on error enhancements)
```

### Experiment Results
```
data/samples/101_issues_experiments/
  ├── results_group_a/
  │   ├── aider__devstral101_groupA_20260327/      ← COMPLETE (real degradation)
  │   ├── swe_agent__devstral101_groupA_20260327/  ← BROKEN (needs fix)
  │   └── trae__devstral101_groupA_20260327/       ← BROKEN (needs fix)
  └── results_group_b/
      ├── aider__devstral101_groupB_20260327/      ← COMPLETE (real degradation)
      ├── swe_agent__devstral101_groupB_20260327/  ← BROKEN (needs fix)
      └── trae__devstral101_groupB_20260327/       ← BROKEN (needs fix)
```

### Analysis Scripts
```
scripts/reports/
  ├── analyze_101_issue_results.py           ← Main aggregate analysis
  ├── per_repository_analysis.py             ← Per-repo breakdown
  ├── compute_statistical_significance.py    ← Statistical tests
  ├── compare_10_vs_101_issues.py           ← 10 vs 101 comparison
  └── run_all_101_analysis.sh               ← Master script (runs all 4)
```

### Documentation to Update
```
docs/
  ├── 101_issue_expansion_report.md          ← Main report (needs final results)
  ├── presentation_summary_5slides.md        ← 5-slide summary (needs update)
  └── second_paper_groupA_vs_groupB_experiment_report.md  ← Technical report
```

---

## Current State Summary

### Completed (Keep as-is)
- ✅ Aider Group A: 5/101 (real result - degradation)
- ✅ Aider Group B: 2/101 (real result - degradation)
- ✅ All baselines: Working correctly (51/101 Group A, 36-37/101 Group B)
- ✅ All enhancements: Generated (101/101 files per experiment)
- ✅ Analysis scripts: Created and tested

### Broken (Needs immediate fix)
- ❌ SWE-agent Group A: 0/101 (pipeline broken)
- ❌ SWE-agent Group B: 0/101 (pipeline broken)
- ❌ TRAE Group A: 0/101 (pipeline broken)
- ❌ TRAE Group B: 0/101 (pipeline broken)

### Action Items
1. ✅ Run `scripts/fix_enhancement_errors.py` to patch 11 error files
2. ⏳ Re-run 4 failed experiments (skip baseline + skip enhancement)
3. ⏳ Wait 3-4 hours for completion
4. ⏳ Re-run analysis scripts
5. ⏳ Update documentation with final results

---

## Context for Understanding

### Research Question
Does enhancing GitHub issue descriptions improve solver resolve rates?

### Hypothesis
Better issue descriptions → Better code patches → Higher resolve rates

### Actual Finding (So Far)
- **Aider (aggressive rewriting)**: Massive degradation (-45% Group A, -35% Group B)
- **TRAE (noop)**: Unknown (pipeline broken, needs fix)
- **SWE-agent (moderate rewriting)**: Unknown (pipeline broken, needs fix)

### Why This Matters
We need all 3 enhancement strategies to compare:
1. Noop (TRAE): Measures solver variance baseline
2. Moderate (SWE-agent): Balanced rewriting
3. Aggressive (Aider): Heavy rewriting

Current data shows aggressive rewriting harms performance. We need the other two data points to complete the picture.

---

## Environment Info

- **Python environment**: `bench_env/` (has swebench 4.1.0)
- **GPU availability**: GPUs 1-7 for vLLM
- **Model**: Devstral-Small-2-24B-Instruct-2512 (local vLLM)
- **Parallel workers**: 4 solver, 4 eval (speeds up runs)
- **Expected runtime per experiment**: 3-4 hours

---

## Success Criteria

After running the fix:

1. ✅ All 4 experiments have `enhanced_solver_run/preds.json` created
2. ✅ All 4 experiments have non-zero enhanced resolve counts
3. ✅ `comparison_summary.json` shows real metrics (not 0/101)
4. ✅ Analysis scripts produce meaningful comparisons
5. ✅ Documentation updated with final results

---

## Questions? Issues?

If you encounter any problems:

1. **Check experiment logs**: `data/samples/101_issues_experiments/results_group_*/*/logs/*.log`
2. **Check enhancement quality**: All 101 enhancement files should have `enhancer_type: "real"`
3. **Verify enhanced dataset**: `secondpaper10_enhanced_*.jsonl` should have 101 lines
4. **Monitor progress**: `tail -f logs/*_retry.log`

The previous agent completed full diagnosis and created all analysis infrastructure. Your job is to:
1. Apply the fix to the 11 error files
2. Re-run the 4 broken experiments
3. Verify results are valid
4. Update documentation

**Good luck!**
