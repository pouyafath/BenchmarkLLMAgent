# Second-Paper 10-Issue F2P/P2P Dataset - Final Report

## Goal
Produce a 10-issue dataset where every issue has `FAIL_TO_PASS_count > 0` AND `PASS_TO_PASS_count > 0`.

## Result: SUCCESS

All 10 selected issues meet the criteria.

## Final Dataset Files

| File | Path |
|------|------|
| **Final JSONL (10 issues)** | `data/samples/second_paper_final_10_f2p_p2p/final_10_instances_with_f2p_p2p.jsonl` |
| **Summary JSON** | `data/samples/second_paper_final_10_f2p_p2p/final_derivation_summary.json` |
| **Sklearn detail summary** | `data/samples/second_paper_final_10_f2p_p2p/sklearn_derivation_summary.json` |
| **Derivation script** | `scripts/data/derive_and_merge_final_dataset.py` |

## Final 10 Issues

| # | Instance ID | Repo | F2P | P2P | Total Tests |
|---|------------|------|-----|-----|-------------|
| 1 | `pallets__flask-5004` | pallets/flask | 2 | 53 | 56 |
| 2 | `pallets__flask-5391` | pallets/flask | 1 | 53 | 57 |
| 3 | `pallets__flask-5472` | pallets/flask | 1 | 125 | 130 |
| 4 | `pallets__flask-5553` | pallets/flask | 2 | 188 | 194 |
| 5 | `pallets__flask-5621` | pallets/flask | 1 | 126 | 131 |
| 6 | `psf__requests-6628` | psf/requests | 1 | 136 | 323 |
| 7 | `scikit-learn__scikit-learn-28901` | scikit-learn/scikit-learn | 11 | 359 | 370 |
| 8 | `scikit-learn__scikit-learn-29294` | scikit-learn/scikit-learn | 1 | 16 | 17 |
| 9 | `scikit-learn__scikit-learn-30056` | scikit-learn/scikit-learn | 1 | 19 | 20 |
| 10 | `scikit-learn__scikit-learn-30622` | scikit-learn/scikit-learn | 2 | 39 | 41 |

### Summary Statistics
- **Repos**: 3 (Flask: 5, Requests: 1, scikit-learn: 4)
- **Total F2P tests**: 23 (range: 1-11)
- **Total P2P tests**: 1,114 (range: 16-359)
- **PASS_TO_FAIL count**: 0 across all instances (clean)

## Additional Qualifying Issues (not selected, available as overflow)

| Instance ID | F2P | P2P |
|------------|-----|-----|
| `scikit-learn__scikit-learn-30625` | 1 | 6 |
| `scikit-learn__scikit-learn-30868` | 5 | 75 |

## Infra Failures (Unresolved)

2 sklearn instances consistently fail Docker image build (`setup_repo.sh` exit code 1):
- `scikit-learn__scikit-learn-30818`
- `scikit-learn__scikit-learn-30895`

These are repo-level build failures unrelated to Python version or spec configuration.

## Source Data Paths

### Flask/Requests v2 (stable, complete)
- Instances: `data/samples/second_paper_flask_requests_exact_f2p_p2p_v2/custom_instances_with_f2p_p2p.jsonl`
- Summary: `data/samples/second_paper_flask_requests_exact_f2p_p2p_v2/f2p_p2p_derivation_summary.json`

### Scikit-learn v1 (12/14 complete)
- Raw instances: `data/samples/second_paper_sklearn_exact_f2p_p2p_v1/custom_instances_raw.jsonl`
- Baseline predictions: `data/samples/second_paper_sklearn_exact_f2p_p2p_v1/predictions_baseline_empty_patch.jsonl`
- Gold predictions: `data/samples/second_paper_sklearn_exact_f2p_p2p_v1/predictions_gold_patch.jsonl`
- Baseline logs: `logs/run_evaluation/secondpaper_custom_baseline_probe_second_paper_sklearn_exact_f2p_p2p_v1/baseline_noop_patch_probe/`
- Gold logs: `logs/run_evaluation/secondpaper_custom_gold_probe_second_paper_sklearn_exact_f2p_p2p_v1/gold_patch_probe/`

## Methodology
1. Candidate issues identified from SWE-bench-Live second-paper repos (Python-only)
2. Each issue's PR diff split into fix patch + test patch
3. SWE-bench harness run twice per instance:
   - **Baseline**: noop patch (appends comment to README) - captures pre-fix test state
   - **Gold**: actual fix patch - captures post-fix test state
4. Test results compared:
   - **FAIL_TO_PASS**: tests that fail without fix, pass with fix (the bug-revealing tests)
   - **PASS_TO_PASS**: tests that pass both before and after fix (regression guard)
5. Qualifying issues: F2P > 0 AND P2P > 0

## Environment
- Python: 3.12 (bench_env)
- swebench: 4.1.0
- Docker env image: `sweb.env.py.x86_64.7198acc6807c84aa4561f4` (Python 3.9 for sklearn, Python 3.10 for Flask/Requests)
