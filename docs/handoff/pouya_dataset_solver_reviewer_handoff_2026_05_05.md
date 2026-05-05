# Pouya Dataset + Solver Experiment Handoff

Date: 2026-05-05
Workspace: `/home/22pf2/BenchmarkLLMAgent`

## Current Objective

The project is trying to create a Pouya SWE-bench-style dataset from
`data/samples/pouya_dataset_2026_swebench_style_f2p_p2p/dataset.jsonl`, validate
it through the SWE-bench-Live-style pipeline, and then compare a mini-SWE-agent
baseline solver against an enhanced-problem-statement solver.

The desired production flow is:

1. RepoLaunch setup + organize with GPT only.
2. Gold evaluation to confirm the gold patch resolves F2P/P2P tests.
3. mini-SWE-agent baseline solver.
4. mini-SWE-agent enhanced solver.
5. Evaluation of both solver outputs.
6. Final summary comparing baseline vs enhanced.

## Important Policy Decisions

- Use GPT for this step. Do not use local open-source models.
- Do not expose API keys in commands, logs, docs, or prompts. Load the key via
  `OPENAI_API_KEY_FILE=$PWD/.claude/settings.local.json`.
- Use Python >=3.10. Prefer `bench_env/bin/python` or the server Python 3.12.
- Do not rerun expensive RepoLaunch work when cached artifacts are valid.
- Do not add local environment artifacts such as `bench_env/`, `.vendor/`, or
  `runs/` to commits.

## Main Workflow Script

The active workflow script is:

`scripts/workflows/run_pouya20_gpt54mini.py`

Recent fixes applied there:

- Uses `get_enhancer`, not `get_agent`, for the enhancer workflow.
- Fails fast on Python <3.10.
- Uses `uv run python -m pytest` rather than `uv run pytest`.
- Adds `-m ''` to evaluation test commands so repo marker filters do not
  deselect explicit F2P/P2P test node IDs.
- Preserves already-repaired parametrized F2P/P2P labels.
- Reuses cached `repolaunch_passed.jsonl` rows when reseeding runs.
- Adds default pilot exclusions for rows already proven unsuitable for the
  lightweight Stage 1+2 pilot.
- Adds `--repolaunch-timeout` to stop per-instance RepoLaunch wrapper stalls.

Verification run:

```bash
bench_env/bin/python -m py_compile scripts/workflows/run_pouya20_gpt54mini.py
```

This passed.

## 3-Sample Solver Experiment

Source 3-sample run:

`runs/pouya_3_gpt54mini_final3_20260504_224702`

Solver-only run performed by Developer Agent 1:

`runs/pouya_3_gpt54mini_solver_only_20260505_021023`

Reported final result:

- `baseline_resolved`: 0
- `baseline_total`: 3
- `baseline_resolved_ids`: []
- `enhanced_resolved`: 0
- `enhanced_total`: 3
- `enhanced_resolved_ids`: []

Evaluation artifacts were produced for both:

- `solver_baseline_eval`
- `solver_enhanced_eval`

Per-instance diagnosis reported by Developer Agent 1:

| Instance | Baseline patch | Enhanced patch | Stop reason | Evaluation result |
| --- | ---: | ---: | --- | --- |
| `MDAnalysis__mdanalysis-5113` | 0 chars | 0 chars | `CalledProcessError` / `CalledProcessError` | Empty patch in both |
| `Flexget__Flexget-4986` | 0 chars | 0 chars | `CalledProcessError` / `CalledProcessError` | Empty patch in both |
| `MDAnalysis__mdanalysis-5071` | 1,131 chars | 1,119 chars | Submitted / Submitted | 1 F2P failure in both |

Interpretation:

- The solver/evaluation pipeline ran, but the comparison is only partially
  meaningful.
- Two of three samples crashed before producing a patch. Those should be
  treated as runner/solver execution failures until the actual exception is
  inspected.
- One sample produced patches in both baseline and enhanced modes, and both
  failed the same F2P test. That sample is a valid solver-quality comparison,
  but the current enhancer did not help.
- The enhancer did materially change the prompts by appending about 1.7k-2.0k
  characters of analysis, but that analysis was not sufficient.

Next debugging target for the 3-sample experiment:

- Inspect the exact mini-SWE-agent crash logs for `MDAnalysis__mdanalysis-5113`
  and `Flexget__Flexget-4986`.
- Do not score those two as normal model failures until the crash cause is
  known.
- For `MDAnalysis__mdanalysis-5071`, compare the generated patch with the
  failing F2P log and decide whether the enhancer needs more targeted content.

## 20-Issue Stage 1+2 Dataset Attempt

Latest run:

`runs/pouya_20_gpt54mini_complete_20260505_020000`

This run executed only:

- `=== STAGE 1: Paul/RepoLaunch (GPT-5.4-mini) ===`
- `=== STAGE 2: Gold evaluation ===`

Final summary:

- Selected: 20
- RepoLaunch passed: 19/20
- RepoLaunch failed: 1/20
- Gold validated: 18/19 RepoLaunch survivors
- Solver baseline/enhanced: not run in this 20-issue attempt

RepoLaunch failure:

- `aws-powertools__powertools-lambda-python-7940`
- Classification: `setup_failed`
- Observed behavior: Poetry install path hung with no useful log progress.
- This row was added to the default pilot exclusion list.

Gold validation failure:

- `dgtlmoon__changedetection.io-3465`
- `report.json` shows both target tests failed:
  - F2P failure:
    `changedetectionio/tests/test_xpath_selector.py::test_rss_xpath`
  - P2P failure:
    `changedetectionio/tests/test_history_consistency.py::test_consistent_history`

Validated 18 rows:

- `Flexget__Flexget-4986`
- `MDAnalysis__mdanalysis-5071`
- `MDAnalysis__mdanalysis-5113`
- `PennyLaneAI__pennylane-7474`
- `PennyLaneAI__pennylane-7668`
- `SQLMesh__sqlmesh-5077`
- `SQLMesh__sqlmesh-5081`
- `a2aproject__a2a-python-564`
- `a2aproject__a2a-python-683`
- `ag2ai__faststream-2495`
- `ag2ai__faststream-2544`
- `amazon-science__chronos-forecasting-407`
- `anthropics__anthropic-sdk-python-1264`
- `astropy__astropy-18105`
- `astropy__astropy-18753`
- `aws-powertools__powertools-lambda-python-7026`
- `beeware__toga-3665`
- `dgtlmoon__changedetection.io-3659`

The 20-issue dataset is not complete yet. It needs two more validated
replacement rows because:

1. `aws-powertools__powertools-lambda-python-7940` failed RepoLaunch.
2. `dgtlmoon__changedetection.io-3465` failed gold evaluation.

## Current Process State

Checked with:

```bash
ps -eo pid,ppid,stat,etime,cmd | rg 'run_pouya20_gpt54mini|mini_sweagent|evaluation\.py|llm_append|paul\.run' || true
docker ps --format 'table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Names}}' | rg 'git-launch|sweb|pouya' || true
```

No active workflow, mini-SWE-agent, evaluation, Paul/RepoLaunch, or relevant
Docker containers were found at handoff time.

## Recommended Next Steps

1. Review Developer Agent 1's 3-sample solver run.
   - Confirm the exact crash causes for the two `CalledProcessError` cases.
   - Decide whether those are runner bugs, mini-SWE-agent config bugs, or valid
     model failures.

2. Improve solver/enhancer comparison before scaling.
   - The current `llm_append_analysis` enhancer changes the prompt but may be too
     generic.
   - A better enhancer should add exact F2P/P2P targets, relevant files, observed
     failing behavior, and a concise repair hypothesis.

3. Complete the 20-row validated dataset.
   - Keep the 18 validated rows from
     `runs/pouya_20_gpt54mini_complete_20260505_020000/validated_instances.jsonl`.
   - Exclude `aws-powertools__powertools-lambda-python-7940` and
     `dgtlmoon__changedetection.io-3465`.
   - Select and run replacements until there are 20 gold-validated rows.
   - Reuse cached RepoLaunch artifacts where possible.

4. Only after the 20-row dataset is complete, run baseline/enhanced solver
   comparison on those 20 rows.

## Prompt for Reviewer Agent

Copy/paste this to the reviewer agent:

```text
You are continuing work in /home/22pf2/BenchmarkLLMAgent.

Your role is reviewer + continuation agent. Review the work done by the other
developer agents and continue the project from the current state. Be strict:
separate valid benchmark results from infrastructure failures, and do not
overclaim enhancer performance.

Read this handoff first:
docs/handoff/pouya_dataset_solver_reviewer_handoff_2026_05_05.md

Context:
- We are building a Pouya SWE-bench-style dataset from
  data/samples/pouya_dataset_2026_swebench_style_f2p_p2p/dataset.jsonl.
- We use GPT only for this phase.
- Do not print or expose API keys. Use:
  OPENAI_API_KEY_FILE=$PWD/.claude/settings.local.json
- Use Python >=3.10, preferably bench_env/bin/python or the server Python 3.12.
- Do not commit local artifacts like bench_env/, .vendor/, runs/, or workspace
  runtime directories.

Review targets:
1. Review the 3-sample solver-only experiment:
   runs/pouya_3_gpt54mini_solver_only_20260505_021023

   Report whether the baseline vs enhanced comparison is valid. Specifically:
   - Inspect logs/trajectories for MDAnalysis__mdanalysis-5113 and
     Flexget__Flexget-4986, where both baseline and enhanced produced empty
     patches due to CalledProcessError.
   - Find the exact exception/command failure, not only the summary label.
   - Decide whether these two should be counted as solver failures or
     infrastructure/runner failures.
   - For MDAnalysis__mdanalysis-5071, inspect the generated patches and eval
     failure logs. Explain why both baseline and enhanced failed the same F2P
     test.
   - Confirm whether the enhanced prompt changed materially and whether it added
     useful targeted information or only generic analysis.

2. Review the 20-issue Stage 1+2 attempt:
   runs/pouya_20_gpt54mini_complete_20260505_020000

   Current known result:
   - RepoLaunch passed 19/20.
   - Gold validation passed 18/19 RepoLaunch survivors.
   - Failed RepoLaunch row: aws-powertools__powertools-lambda-python-7940.
   - Failed gold row: dgtlmoon__changedetection.io-3465.

   Verify this from summary.json, progress.json, report.json files, and logs.

Continuation task:
3. Complete the 20-row validated dataset.
   - Preserve the 18 validated rows from
     runs/pouya_20_gpt54mini_complete_20260505_020000/validated_instances.jsonl.
   - Exclude rows already proven unsuitable in this pilot, including
     aws-powertools__powertools-lambda-python-7940 and
     dgtlmoon__changedetection.io-3465.
   - Select replacement rows from
     data/samples/pouya_dataset_2026_swebench_style_f2p_p2p/dataset.jsonl.
   - Reuse cached RepoLaunch artifacts where valid.
   - Run only RepoLaunch setup+organize and gold evaluation for replacements.
   - Stop when there are 20 gold-validated rows.

Useful commands:

python -m json.tool runs/pouya_20_gpt54mini_complete_20260505_020000/summary.json
python -m json.tool runs/pouya_20_gpt54mini_complete_20260505_020000/progress.json
tail -f <new_run_dir>/progress.log

Before and after running, check for stale processes:

ps -eo pid,ppid,stat,etime,cmd | rg 'run_pouya20_gpt54mini|mini_sweagent|evaluation\.py|llm_append|paul\.run' || true
docker ps --format 'table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Names}}' | rg 'git-launch|sweb|pouya' || true

Deliverables:
- A short review of the 3-sample solver experiment: valid parts, invalid parts,
  exact crash causes, and whether enhancer performance can be concluded.
- A completed 20-row gold-validated dataset or a precise blocker if 20 cannot
  be reached.
- Exact run directory paths and summary numbers.
- List of any code changes made.
- Verification commands and key outputs.
```

