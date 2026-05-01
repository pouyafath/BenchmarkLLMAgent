# True Native Agents Approach Status (Verified-10)

## Scope
- Same solver stack as baseline: `mini-SWE-agent + Devstral-Small-2-24B-Instruct-2512`
- Same dataset/split/IDs: `SWE-bench/SWE-bench_Verified` (`test`) on the fixed 10 astropy instances from `/home/22pf2/SWE-Bench_Replication/selected_instances.txt`
- Same metrics path: SWE-bench harness + comparison summary (`RESOLVED`, `FAIL_TO_PASS`, `PASS_TO_PASS`)
- Strict native enforcement enabled: `--require-native-enhancer`

## Completed True-Native Run
- Enhancer: `trae`
- Run dir:
  - `/home/22pf2/BenchmarkLLMAgent/true_native_agents_approach/results/verified10_baseline_vs_enhanced/trae__true_native_full10_trae_devstral_20260323`
- Key outputs:
  - comparison json: `comparison_summary.json`
  - comparison markdown: `comparison_summary.md`
  - reproducibility manifest: `reproducibility_manifest.json`
- Final metrics vs baseline:
  - Baseline RESOLVED: `3/10 (30.0%)`
  - Enhanced RESOLVED: `3/10 (30.0%)`
  - Baseline FAIL_TO_PASS: `3/10 (30.0%)`
  - Enhanced FAIL_TO_PASS: `3/10 (30.0%)`
  - Baseline PASS_TO_PASS: `5/10 (50.0%)`
  - Enhanced PASS_TO_PASS: `6/10 (60.0%)`
  - Infra failures: `0`
  - Model/provider failures: `0`
  - Evaluation failures: `0`

## In-Progress True-Native Second-Paper Run (P2P-only 10)
- Goal: mirror the verified true-native setup on second-paper 10-issue dataset.
- Enhancer: `trae` (native only; strict enforcement enabled)
- Solver: `mini-SWE-agent + Devstral-Small-2-24B-Instruct-2512`
- Dataset:
  - `/home/22pf2/BenchmarkLLMAgent/data/samples/second_paper_final_10_p2p_only/final_10_instances_p2p_only.jsonl`
- Run dir:
  - `/home/22pf2/BenchmarkLLMAgent/true_native_agents_approach/results/secondpaper10_p2p_only_baseline_vs_enhanced/trae__true_native_p2p_only_full10_trae_devstral_w2_20260324`
- Run log:
  - `/home/22pf2/BenchmarkLLMAgent/true_native_agents_approach/results/secondpaper10_p2p_only_baseline_vs_enhanced/run_trae_true_native_p2p_only_full10_w2.log`
- Parallel settings:
  - `enhancer_parallel=2`
  - `solver_workers=2`
  - `eval_workers=2`
- Strict native flag:
  - `--require-native-enhancer`

## Native Enhancer Viability (Current Server Setup)
- `trae`: **usable** (fixed to pass required `--config-file`; produces `enhancer_type=real`)
- `openhands`: **blocked for this setup** (runtime path attempted local HF model load rather than intended OpenAI-compatible endpoint)
- `mini_swe_agent`: **blocked for this setup** (runtime path attempted local HF model load; not reliably using intended endpoint)
- `aider`: **not available as native CLI** in current environment

## Code Fixes Applied During Migration
- Fixed workflow root detection after moving scripts under `llm_proxy_approach`:
  - `/home/22pf2/BenchmarkLLMAgent/llm_proxy_approach/scripts/workflows/run_verified10_enhancement_vs_baseline.py`
- Fixed TRAE enhancer integration for current CLI version (`--config-file` required):
  - `/home/22pf2/BenchmarkLLMAgent/src/enhancers/ready_to_use/trae_enhancer.py`
- Fixed mini enhancer CLI option mismatch and strict error tagging:
  - `/home/22pf2/BenchmarkLLMAgent/src/enhancers/ready_to_use/mini_swe_agent_enhancer.py`
- Added stricter nonzero-return handling for aider/trae native adapters:
  - `/home/22pf2/BenchmarkLLMAgent/src/enhancers/ready_to_use/aider_enhancer.py`
  - `/home/22pf2/BenchmarkLLMAgent/src/enhancers/ready_to_use/trae_enhancer.py`
