# Pouya Dataset 2026 Workflow

The new dataset pipeline lives in:

- [`scripts/data/pouya_dataset_2026.py`](/home/22pf2/BenchmarkLLMAgent/scripts/data/pouya_dataset_2026.py)

It wraps the local `SWE-bench-Live-Collection/` assets for crawling, RepoLaunch setup, and validation, while explicitly skipping any issue-description quality filter.

## What It Produces

- `data/samples/pouya_dataset_2026/raw_candidates.jsonl`
- `data/samples/pouya_dataset_2026/launch_ready.jsonl`
- `data/samples/pouya_dataset_2026/validated_full.jsonl`
- `data/samples/pouya_dataset_2026/frozen_50.jsonl`
- `data/samples/pouya_dataset_2026/rejected_candidates.jsonl`

## End-to-End Commands

Prepare the workspace:

```bash
python scripts/data/pouya_dataset_2026.py init
```

1. Crawl and filter repositories with SWE-bench-Live criteria:

```bash
python scripts/data/pouya_dataset_2026.py crawl-repos \
  --token-file /path/to/tokens.txt

python scripts/data/pouya_dataset_2026.py filter-repos \
  --token-file /path/to/tokens.txt
```

2. Collect task candidates from the filtered repo set:

```bash
python scripts/data/pouya_dataset_2026.py collect-tasks \
  --token-file /path/to/tokens.txt \
  --start-date 2025-05-01
```

3. Build the mixed-quality raw candidate set:

```bash
python scripts/data/pouya_dataset_2026.py build-raw-candidates \
  --token-file /path/to/tokens.txt \
  --start-date 2025-05-01
```

4. Generate a RepoLaunch config:

```bash
python scripts/data/pouya_dataset_2026.py write-launch-config
```

Then run RepoLaunch using the generated config:

```bash
cd SWE-bench-Live-Collection/launch
python -m launch.run --config-path /home/22pf2/BenchmarkLLMAgent/data/samples/pouya_dataset_2026/launch/config.json
```

5. Merge RepoLaunch organize output back into the dataset:

```bash
python scripts/data/pouya_dataset_2026.py merge-launch-results \
  --organize-jsonl /home/22pf2/BenchmarkLLMAgent/data/samples/pouya_dataset_2026/launch/workspace/organize.jsonl
```

6. Run executable validation and gold-patch confirmation:

```bash
python scripts/data/pouya_dataset_2026.py run-validation --workers 4
```

7. Promote only stable executable instances:

```bash
python scripts/data/pouya_dataset_2026.py promote-validated \
  --launch-workspace /home/22pf2/BenchmarkLLMAgent/data/samples/pouya_dataset_2026/launch/workspace
```

8. Freeze the first official subset:

```bash
python scripts/data/pouya_dataset_2026.py freeze --count 50
```

## Notes

- Date filtering is based on the linked issue creation date, not issue text quality.
- Quality is recorded as metadata:
  - `quality_signals`
  - `quality_bucket`
- Validation uses the local SWE-bench-Live validation flow:
  - RepoLaunch environment setup
  - repeated post-patch execution in `evaluation.validation`
  - gold-patch confirmation in `evaluation.evaluation`
