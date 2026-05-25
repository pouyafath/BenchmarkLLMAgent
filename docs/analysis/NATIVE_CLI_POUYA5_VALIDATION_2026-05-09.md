# Native CLI Pouya-5 Validation - 2026-05-09

## Scope

This validation ran the five native CLI issue enhancers on the first 5 instances from the canonical Pouya-20 gold-validated dataset:

- `Flexget__Flexget-4986`
- `MDAnalysis__mdanalysis-5071`
- `MDAnalysis__mdanalysis-5113`
- `PennyLaneAI__pennylane-7474`
- `PennyLaneAI__pennylane-7668`

The run is enhancer-only. It verifies native enhancer execution, parsing, and output quality before launching expensive solver/evaluation runs. It does not run mini-SWE-agent solving or SWE-bench harness evaluation.

## Command

```bash
cd /home/22pf2/BenchmarkLLMAgent
bench_env/bin/python scripts/enhancers/run_native_cli_pouya5_validation.py \
  --limit 5 \
  --output-dir runs/native_cli_pouya5_20260509
```

The runner points all native enhancers at the local Ollama OpenAI-compatible endpoint:

```text
http://127.0.0.1:11434/v1
model: gpt-oss:120b
```

## Artifacts

| Artifact | Purpose |
|---|---|
| `runs/native_cli_pouya5_20260509/SUMMARY.json` | Aggregated validation result |
| `runs/native_cli_pouya5_20260509/raw_results/*.json` | Per-agent/per-issue raw result, metadata, timing, and quality checks |
| `runs/native_cli_pouya5_20260509_sweagent_retry2/` | Targeted SWE-agent rerun for `PennyLaneAI__pennylane-7474` after parser tightening |

## Corrected Result

| Agent | Real / Total | Failures | Weak Outputs | Parse Source | Total Seconds | Avg Seconds | Max Seconds |
|---|---:|---:|---:|---|---:|---:|---:|
| `aider` | 5/5 | 0 | 0 | `explicit_markers` x5 | 100.2 | 20.0 | 29.3 |
| `trae` | 5/5 | 0 | 0 | `trajectory` x5 | 574.6 | 114.9 | 225.4 |
| `openhands` | 5/5 | 0 | 0 | `strict_markers` x5 | 308.2 | 61.6 | 69.3 |
| `mini_swe_agent` | 5/5 | 0 | 0 | `strict_markers` x5 | 101.0 | 20.2 | 36.4 |
| `swe_agent` | 5/5 | 0 | 0 | `trajectory` x5 | 1683.0* | 336.6* | 817.1* |

The accepted 25/25 real outputs:

- returned `enhancer_type: real`
- had return code `0`, except the final SWE-agent retry for `PennyLaneAI__pennylane-7668`, which produced parseable trajectory output and then hit the wall-clock timeout before calling `submit`
- changed both title and body
- produced bodies longer than 300 characters
- included reproduction/steps content
- included expected and actual behavior content

*The SWE-agent timing row reflects the corrected merged artifact and the final focused retry. Earlier failed retries are preserved in separate retry directories but are not counted as accepted outputs.

## Bugs Found And Fixed

1. `swe_agent` accepted stdout log text as an enhanced issue.
   - Symptom: `PennyLaneAI__pennylane-7474` initially parsed from `stdout` with title text like shell-planning output and a body contaminated by SWE-agent command-timeout observations.
   - Fix: `src/enhancers/ready_to_use/sweagent_enhancer.py` now accepts only trajectory content for benchmark enhancement parsing.

2. `swe_agent` accepted weak trajectory bodies.
   - Symptom: the first trajectory-only retry returned a short body containing a command timeout message and missing expected/actual sections.
   - Fix: SWE-agent candidate acceptance now rejects timeout-contaminated bodies and requires summary, reproduction/steps, and expected/actual content.

3. Validation runner reported `returncode: null` for successful `0` return codes.
   - Cause: Python `or` treated `0` as false while selecting metadata fields.
   - Fix: `scripts/enhancers/run_native_cli_pouya5_validation.py` now selects the first non-`None` returncode field.

4. Validation summary missed timeout contamination.
   - Symptom: `swe_agent__MDAnalysis__mdanalysis-5071` and `swe_agent__PennyLaneAI__pennylane-7668` contained the phrase `was cancelled because it took more than 60 seconds`, but the earlier summary still reported `weak_count: 0`.
   - Fix: the validation runner now records `timeout_contaminated` and includes it in weak-output detection.

5. Two stale SWE-agent raw artifacts were corrected.
   - `MDAnalysis__mdanalysis-5071` was rerun cleanly and merged into `runs/native_cli_pouya5_20260509/raw_results/`.
   - `PennyLaneAI__pennylane-7668` was rerun with broader trajectory parsing. It produced a valid trajectory enhancement before timing out and is now recorded as a real trajectory-sourced enhancement with timeout metadata.

6. SWE-agent trajectory parsing missed valid output in `history`.
   - Symptom: `PennyLaneAI__pennylane-7668` contained valid `ENHANCED_TITLE` / `ENHANCED_BODY` text in the SWE-agent trajectory, but the parser did not scan that schema and discarded it.
   - Fix: SWE-agent parsing now scans `history`, `trajectory`, `messages`, and `info.submission` fields.

7. SWE-agent timeout handling discarded valid trajectory output.
   - Symptom: SWE-agent wrote the enhanced issue but did not call `submit`, so the process timed out and the wrapper returned an error.
   - Fix: if timeout occurs after parseable trajectory output exists, the wrapper preserves the native trajectory result and records `timed_out: true`.

## Remaining Risk

SWE-agent is now clean on the enhancer-only Pouya-5 validation, but it remains operationally slower and one accepted result required timeout recovery from trajectory output. Full 20-issue runs should keep timeout metadata and raw trajectories in the artifact.

This validation used Ollama because the Devstral endpoint on port `18000` was unavailable in prior smoke evidence. For the full pipeline, either keep the Ollama overrides or restart Devstral before launching runs that default to `127.0.0.1:18000`.
