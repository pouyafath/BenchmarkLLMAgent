# Prompt For Next Agent

Continue from `/home/22pf2/BenchmarkLLMAgent/HANDOFF_SECONDPAPER_F2P_P2P_CONTINUATION_2026-03-24.md`.

Goal:
- Build a 10-issue dataset from second-paper issues where each issue has:
- `FAIL_TO_PASS_count > 0`
- `PASS_TO_PASS_count > 0`

Constraints:
- Reuse existing local artifacts first (avoid re-fetching GitHub API unless absolutely necessary).
- Prioritize completing scikit derivation from cached dataset/predictions/logs.
- Keep output deterministic and document all commands, paths, and failures.

Key inputs:
- `/home/22pf2/BenchmarkLLMAgent/data/samples/second_paper_sklearn_exact_f2p_p2p_v1/custom_instances_raw.jsonl`
- `/home/22pf2/BenchmarkLLMAgent/data/samples/second_paper_sklearn_exact_f2p_p2p_v1/predictions_baseline_empty_patch.jsonl`
- `/home/22pf2/BenchmarkLLMAgent/data/samples/second_paper_sklearn_exact_f2p_p2p_v1/predictions_gold_patch.jsonl`
- `/home/22pf2/BenchmarkLLMAgent/logs/run_evaluation/secondpaper_custom_baseline_probe_second_paper_sklearn_exact_f2p_p2p_v1/`

Important fix already applied:
- scikit live spec now uses Python 3.10 in:
- `/home/22pf2/BenchmarkLLMAgent/scripts/data/derive_exact_f2p_p2p_secondpaper_py10.py`
- `/home/22pf2/BenchmarkLLMAgent/bench_env/lib/python3.12/site-packages/swebench/harness/test_spec/test_spec.py`

Deliverables:
- Final 10-issue JSONL with non-zero F2P/P2P.
- Summary JSON/MD with counts and exact issue IDs.
- Clear note of any infra failures that remain unresolved.

