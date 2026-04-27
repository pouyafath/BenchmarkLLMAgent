# BenchmarkLLMAgent - Active Handoff Pointer

This root handoff file exists so contributors can always open:

`/home/22pf2/BenchmarkLLMAgent/HANDOFF_TO_NEXT_AGENT.md`

## Active Workflow (2026-03-19)

The canonical 10-issue workflow is now the SWE-bench Verified sample aligned with:

- `/home/22pf2/SWE-Bench_Replication/selected_instances.txt`
- `/home/22pf2/SWE-Bench_Replication/replication_report.md`

Use:

```bash
cd /home/22pf2/BenchmarkLLMAgent

/home/22pf2/SWE-Bench_Replication/.venv312/bin/python \
  scripts/data/prepare_verified_10_samples_from_replication.py

./bench_env/bin/python scripts/workflows/run_verified10_enhancement_vs_baseline.py \
  --enhancer-agent simple_enhancer \
  --output-tag run1
```

## Latest Run Snapshot (2026-03-19)

Completed bugfix runs:

- `results/verified10_baseline_vs_enhanced/simple_enhancer__bugfix_full10_simple_20260318/`
- `results/verified10_baseline_vs_enhanced/swe_agent__bugfix_full10_swe_agent_20260318/`
- Baseline (replication): RESOLVED `3/10`, F2P issue success `3/10`, P2P issue success `5/10`
- Enhanced (`simple_enhancer`): RESOLVED `3/10`, F2P issue success `3/10`, P2P issue success `6/10`
- Enhanced (`swe_agent`): RESOLVED `3/10`, F2P issue success `3/10`, P2P issue success `7/10`
- Both runs completed with `10/10` attempted and `0` evaluation failures.

Primary artifacts:

- per-run `comparison_summary.json`
- per-run `enhanced_metrics.json`
- aggregate:
  - `results/verified10_baseline_vs_enhanced/multi_enhancer_bugfix_full10_20260318.json`
  - `results/verified10_baseline_vs_enhanced/multi_enhancer_bugfix_full10_20260318.md`

## Canonical Handoff Document

Full handoff details live in:

- `docs/handoff/HANDOFF_TO_NEXT_AGENT.md`

The section **"2026-03-18 Update (Supersedes old default path)"** in that file is authoritative for current execution.
