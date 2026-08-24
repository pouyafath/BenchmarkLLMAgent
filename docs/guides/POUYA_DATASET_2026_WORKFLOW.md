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

## Current Full-Run Dataset Lineage

The live 2,900-instance RepoLaunch run does **not** read `raw_candidates.jsonl`
directly. The current full run uses a later operational subset:

- `/home/22pf2/paul-RepoLaunch/data/stage2_2026_viable.jsonl`

The lineage for the current full-run dataset is:

| Step | File | Rows | Why this step exists |
|---|---|---:|---|
| 1 | `data/samples/pouya_dataset_2026/raw_candidates.jsonl` | 7,714 | This is already post-cutoff candidate data. `collection_summary.json` shows `2,749` earlier rows were rejected as `issue_before_cutoff`, so `raw_candidates.jsonl` is the first file after the linked-issue date cutoff. |
| 2 | `data/samples/pouya_dataset_2026_stage1/dataset.jsonl` | 3,285 | Keep only rows with `PASS_TO_PASS_count > 0` using the static diff / test-structure derivation. Measured directly: `4,429` rows were dropped here, and all `4,429` had `PASS_TO_PASS_count = 0`. This file also adds LLM issue-type classification (`2,111 bug / 993 feature / 181 refactoring`). |
| 3 | `paul-RepoLaunch/data/stage2_2026_full.jsonl` | 3,229 | This is the Stage-0/0.5 working export that was copied into `paul-RepoLaunch` for the full run. Relative to the 3,285-stage file, `56` rows are missing (`35 bug / 16 feature / 5 refactoring`). The current repo documents the count but does **not** expose one single canonical producer script for this trim, so treat this as an operational export step, not a cleanly-scripted filter step. |
| 4 | `data/samples/pouya_dataset_2026_stage1/viable_for_paul.jsonl` | 2,950 | This is the explicit Paul pre-filter from `scripts/data/p2p_pipeline/filter_infra_incompatible.py`. It removes `335` rows that require external services or unsupported infra in a bare Paul container: PostgreSQL / PostGIS / MySQL / MongoDB / Redis / Celery / RabbitMQ / Kafka / Elasticsearch / OpenSearch / Docker-daemon style requirements / Kubernetes-related setup. |
| 5 | `paul-RepoLaunch/data/stage2_2026_viable.jsonl` | 2,900 | This is the dataset the live Stage 1 run actually uses. It is the intersection of the 3,229-row operational export and the 2,950-row infra-compatible set. Concretely: the 3,229-row file still contained `329` infra-incompatible rows, and all `329` are removed here. The final `2,900` file therefore equals `3,229 - 329`, and also `2,950 - 50`, where those `50` rows were already absent from the earlier 3,229 operational export. |

Current issue-type counts at each stage:

| File | Bug | Feature | Refactoring |
|---|---:|---:|---:|
| `pouya_dataset_2026_stage1/dataset.jsonl` | 2,111 | 993 | 181 |
| `paul-RepoLaunch/data/stage2_2026_full.jsonl` | 2,076 | 977 | 176 |
| `pouya_dataset_2026_stage1/viable_for_paul.jsonl` | 1,928 | 868 | 154 |
| `paul-RepoLaunch/data/stage2_2026_viable.jsonl` | 1,896 | 855 | 149 |

Important operational note:

- Your earlier slide matches the **3,285-row** classified Stage-1 file.
- The current live Paul run uses the later **2,900-row** operational viability subset.
- They are from the same lineage, but they are **not** the same stage artifact.

## The 7-Stage Enhancer+Solver Workflow
This process covers the following Agentic Pipeline stages:
- **Stage 0:** Raw collection and task derivation (`raw_candidates.jsonl`, 7,714 post-cutoff rows)
- **Stage 0.5:** P2P classification plus Paul viability pruning (`7,714 -> 3,285 -> 3,229 -> 2,950 -> 2,900`)
- **Stage 1:** RepoLaunch Setup (Docker building)
- **Stage 2:** RepoLaunch Organize (Test extraction)
- **Stage 3:** Gold Patch Validation (via `run-validation`)
- **Stage 4-6:** Enhancement and Solver comparison (executed after validation)

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
