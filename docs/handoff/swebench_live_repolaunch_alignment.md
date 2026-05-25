# SWE-bench-Live RepoLaunch Alignment

Snapshot reviewed: `7fa4dab4e`.

## SWE-bench-Live Pipeline Stages

1. Repository and issue/PR collection
   - Upstream crawls popular Python repositories, then filters by activity, forks, Python language share, and license-like suitability. Our wrapper delegates repository crawling/filtering to the local SWE-bench-Live curation scripts with the same default thresholds: stars >= 1000, total issues+PRs >= 200, forks >= 200, Python share >= 60% (`scripts/data/pouya_dataset_2026.py:79-84`, `scripts/data/pouya_dataset_2026.py:735-760`).
   - Task extraction follows the SWE-bench/SWE-bench-Live shape: PR must be merged, linked to at least one resolved issue, have a non-empty source patch, and include test patch content. Upstream `build_dataset.py` creates `repo`, `pull_number`, `instance_id`, `issue_numbers`, `base_commit`, `patch`, `test_patch`, `problem_statement`, hints, commit URLs, and PR `created_at`.
   - Upstream closed-issue crawling discovers issue closure events whose closer is a pull request (`SWE-bench-Live-Collection/curation/swe_task_crawling/fetch_pulls.py:83-138`) and applies its coarse cutoff to the close event time (`SWE-bench-Live-Collection/curation/swe_task_crawling/fetch_pulls.py:140-179`).
   - Our final raw-candidate gate intentionally uses linked issue creation time >= 2025-05-01 (`scripts/data/pouya_dataset_2026.py:291-292`, `scripts/data/pouya_dataset_2026.py:945-966`).

2. RepoLaunch setup and organize
   - `launch.run` loads the dataset, runs setup, collects `setup.jsonl`, then runs organize on successful setup rows and collects `organize.jsonl` (`SWE-bench-Live-Collection/launch/launch/run.py:323-337`).
   - Setup flow: locate relevant files, select base image, start a bash session, run the setup agent, verify, and either retry setup or save the result (`SWE-bench-Live-Collection/launch/launch/core/workflow.py:16-53`).
   - Verification explicitly requires detailed per-test status output and accepts small pre-existing failures when most tests pass (`SWE-bench-Live-Collection/launch/launch/agent/setup/verify.py:14-40`, `SWE-bench-Live-Collection/launch/launch/agent/setup/verify.py:43-54`).
   - Organize flow: reload the successful setup container, rebuild, find an all-tests command, generate/refine a log parser, create per-test command support, and save an organized image/result (`SWE-bench-Live-Collection/launch/launch/core/workflow.py:65-124`).
   - The upstream collector emits launch-ready fields from successful result files: `setup_cmds`, `test_cmds`, `print_cmds`, `log_parser`, `docker_image`, and optionally `rebuild_cmds` and per-test metadata (`SWE-bench-Live-Collection/launch/launch/scripts/collect.py:40-57`). Our merge step preserves these fields on the raw candidate (`scripts/data/pouya_dataset_2026.py:1127-1136`).

3. Validation and evaluation
   - Validation runs in the RepoLaunch image. It applies `test_patch`, rebuilds, runs tests, parses pre-patch status, then starts a fresh container, applies both `test_patch` and gold `patch`, rebuilds, and runs post-patch tests three times (`SWE-bench-Live-Collection/evaluation/validation.py:49-73`).
   - Post-patch stability is conservative: any `fail` in the three post runs makes that test fail; otherwise any `skip` makes it skip; only all-pass is pass (`SWE-bench-Live-Collection/evaluation/validation.py:74-89`).
   - The local upstream code defines `PASS_TO_PASS = pre_pass & post_pass` and `FAIL_TO_PASS = post_pass - pre_pass` (`SWE-bench-Live-Collection/evaluation/validation.py:21-35`). This means F2P is "not passing before, passing after" in code, not strictly "failed before, passed after" as some prose docs say.
   - Validation keeps only rows with at least one `FAIL_TO_PASS` test (`SWE-bench-Live-Collection/evaluation/validation.py:171-176`).
   - Evaluation applies `test_patch` plus a candidate `pred_patch`, rebuilds, runs tests, parses status, and compares parsed pass/fail sets with the instance labels (`SWE-bench-Live-Collection/evaluation/evaluation.py:97-132`, `SWE-bench-Live-Collection/evaluation/evaluation.py:153-182`).
   - On Linux, current local upstream `resolved` requires no labeled P2P failure, no labeled F2P failure, and at least one labeled F2P success. Windows requires all labeled F2P successes (`SWE-bench-Live-Collection/evaluation/evaluation.py:179-183`).

## RepoLaunch Setup/Organize Flow in This Repo

The wrapper creates a config matching the upstream example structure: setup and organize enabled, OpenAI model config, workspace root, dataset path, parallelism, retry/step limits, command timeout, Linux platform, and image prefix (`scripts/data/pouya_dataset_2026.py:995-1019`; upstream example at `SWE-bench-Live-Collection/launch/data/examples/config.json`).

`cmd_run_launch` calls `python -m launch.run --config-path ...` inside `SWE-bench-Live-Collection/launch`, while monitoring setup/organize progress from upstream `result.json` files (`scripts/data/pouya_dataset_2026.py:1025-1073`). After upstream writes `organize.jsonl`, `cmd_merge_launch_results` joins organize output back to our raw candidates by `instance_id` and creates `launch_ready.jsonl` (`scripts/data/pouya_dataset_2026.py:1078-1160`).

`cmd_run_validation` then delegates to upstream `evaluation.validation`, followed by upstream `evaluation.evaluation --patch_dir gold` as a gold-patch confirmation pass (`scripts/data/pouya_dataset_2026.py:1163-1223`). `cmd_promote_validated` promotes only instances that are launch-ready, validation-kept, and gold-confirmed (`scripts/data/pouya_dataset_2026.py:1230-1248`, `scripts/data/pouya_dataset_2026.py:1251-1362`).

## Mismatch Inventory

Intentional collection differences:

- Custom repo pool: our dataset workspace owns the selected repo list and generated artifacts under `data/samples/pouya_dataset_2026/`; the wrapper still uses upstream crawl/filter logic when building that pool.
- Issue date cutoff >= 2025-05-01: `DEFAULT_START_DATE` is `2025-05-01` (`scripts/data/pouya_dataset_2026.py:79`), and the final candidate gate checks linked issue `created_at` (`scripts/data/pouya_dataset_2026.py:945-966`).
- No description-quality filter: quality signals and buckets are recorded (`scripts/data/pouya_dataset_2026.py:295-342`, `scripts/data/pouya_dataset_2026.py:960-970`) but are not used as rejection criteria. The inherited non-empty problem statement requirement is task-shape validity, not a quality filter.

Unintentional behavior mismatches found:

- None against the local SWE-bench-Live launch/validation/evaluation code paths. The wrapper delegates launch and validation/evaluation rather than reimplementing them, and the merge/promotion steps preserve upstream fields needed by the evaluator.

Documentation/prose differences to keep in mind:

- The methodology docs describe F2P as failed-to-passed, but the local upstream validation code computes `post_pass - pre_pass`, so skipped/error/missing-before to pass are included (`SWE-bench-Live-Collection/evaluation/validation.py:21-35`).
- The methodology docs describe resolved as all F2P and all P2P tests passing. The local upstream Linux evaluator uses no labeled failures plus at least one F2P success (`SWE-bench-Live-Collection/evaluation/evaluation.py:179-183`). This note treats code as authoritative for launch/validation alignment.
- The upstream crawler's coarse cutoff is based on issue closed event time (`SWE-bench-Live-Collection/curation/swe_task_crawling/fetch_pulls.py:169-179`), while our final intended cutoff is linked issue creation time (`scripts/data/pouya_dataset_2026.py:945-966`). This can admit extra intermediate rows that are later rejected as `issue_before_cutoff`; it should not exclude valid post-cutoff-created issues because they cannot close before creation.

## Changes Made

- Added this handoff note to pin the current interpretation of SWE-bench-Live collection, RepoLaunch, validation, and evaluation behavior.
- No functional code changes were made. Changing the F2P/resolved semantics to match prose would diverge from the local upstream code, so it was intentionally left unchanged.

## Paul RepoLaunch Smoke Addendum

The separate Paul fork at `/home/22pf2/paul-RepoLaunch` is intentionally outside this repository so the benchmark collection pipeline remains unchanged. For local server smoke runs, Paul now adds runtime guardrails in `paul/patches/patch_state.py`:

- It respects an explicit single `test_cmds` command before synthesizing one from `FAIL_TO_PASS` and `PASS_TO_PASS` (`/home/22pf2/paul-RepoLaunch/paul/patches/patch_state.py:54-66`, `/home/22pf2/paul-RepoLaunch/paul/patches/patch_state.py:180-211`).
- It rewrites broad pytest invocations such as `pytest`, `pytest -v -rA`, or `pytest <package>` to the row's targeted command during setup/verify (`/home/22pf2/paul-RepoLaunch/paul/patches/patch_state.py:85-143`, `/home/22pf2/paul-RepoLaunch/paul/patches/patch_state.py:374-385`).
- It can apply a row-local benchmark `test_patch` when `paul_apply_test_patch` is set, matching the evaluation assumption that benchmark test targets are available only after the test patch is applied (`/home/22pf2/paul-RepoLaunch/paul/patches/patch_state.py:146-177`, `/home/22pf2/paul-RepoLaunch/paul/patches/patch_state.py:358-367`).
- It marks verify successful if the enforced targeted command has already passed but the LLM fails to emit the final `<issue>None</issue>` action (`/home/22pf2/paul-RepoLaunch/paul/patches/patch_state.py:329-335`, `/home/22pf2/paul-RepoLaunch/paul/patches/patch_state.py:387-405`).

These changes are smoke/launch guardrails only. They do not change the Pouya collection policy, upstream validation/evaluation semantics, or the F2P/P2P labels stored in the dataset rows. For base-checkout launch smoke, the temporary experiment rows used P2P-targeted `test_cmds`; F2P fields remained intact for benchmark evaluation.

## Verification Commands

Run:

```bash
python -m py_compile scripts/data/pouya_dataset_2026.py
python scripts/data/pouya_dataset_2026.py write-launch-config --max-workers 1 --image-prefix repolaunch/alignment-check
python - <<'PY'
import json
from pathlib import Path

cfg = json.loads(Path("data/samples/pouya_dataset_2026/launch/config.json").read_text())
assert cfg["mode"] == {"setup": True, "organize": True}
assert cfg["dataset"].endswith("data/samples/pouya_dataset_2026/raw_candidates.jsonl")
assert cfg["os"] == "linux"
assert cfg["max_trials"] == 2
assert cfg["max_steps_setup"] == 60
assert cfg["max_steps_verify"] == 20
assert cfg["max_steps_organize"] == 40
print("launch config alignment ok")
PY
```
