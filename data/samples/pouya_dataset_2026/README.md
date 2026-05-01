# `pouya_dataset_2026`

Mixed-quality, SWE-bench-Live-style dataset workspace.

This dataset is intended to:
- keep the SWE-bench/SWE-bench-Live task shape
- collect only Python bug-fix issue/PR pairs
- require issue creation date `>= 2025-05-01`
- avoid any description-quality filtering
- record quality metadata instead of using it as a gate

Primary generated artifacts:
- `raw_candidates.jsonl`
- `launch_ready.jsonl`
- `validated_full.jsonl`
- `frozen_50.jsonl`
- `rejected_candidates.jsonl`
- `collection_summary.json`

Pipeline entrypoint:
- [`scripts/data/pouya_dataset_2026.py`](/home/22pf2/BenchmarkLLMAgent/scripts/data/pouya_dataset_2026.py)
