# Experiment Status Report
**Last Updated**: 2026-05-10 20:39 UTC

## Current Experiment: Pouya-20 Native CLI Agent Comparison

**LLM**: gpt-5.4-mini (OpenAI API)
**Enhancers**: 5 native CLI agents (aider, trae, openhands, mini_swe_agent, swe_agent)
**Solver**: mini-SWE-agent (gpt-5.4-mini)
**Dataset**: Pouya-20 (20 curated issues from SWE-bench)
**Status**: Complete

### Enhancement Phase

All 5 agents run as native CLI subprocesses (no LLM proxy, no fallback, no llm_client.py).

| Agent | Success Rate | Enhancement Failures | Parse Method | Avg Time |
|-------|:-----------:|:---:|---|---|
| **aider** | 20/20 (100%) | 0 | explicit_markers (stdout) | ~10s |
| **trae** | 20/20 (100%) | 0 | trajectory | ~32s |
| **openhands** | 20/20 (100%) | 0 | strict/loose_markers (file) | ~45s |
| **mini_swe_agent** | 17/20 (85%) | 3 (template leak) | loose_markers (file) | ~12s |
| **swe_agent** | 19/20 (95%) | 1 (no markers) | trajectory | ~360s |

Enhancement failure details:
- **mini_swe_agent**: 3 issues produced unfilled template placeholders in stdout (body len=164); file was not written. Issues: PennyLaneAI__pennylane-7474, a2aproject__a2a-python-683, dgtlmoon__changedetection.io-3659
- **swe_agent**: 1 issue (astropy__astropy-18753) exited rc=0 but no ENHANCED_TITLE/ENHANCED_BODY markers found in trajectory

### Solver + Evaluation Phase

| Condition | Solver Inputs | Empty Patches | Resolved / 20 | Delta |
|-----------|:---:|:---:|:---:|:---:|
| **Baseline** | 20 | 0* | **3/20 (15%)** | -- |
| **aider** | 20 | 3 | **3/20 (15%)** | 0 |
| **trae** | 20 | 3 | **2/20 (10%)** | -1 |
| **openhands** | 20 | 3 | **2/20 (10%)** | -1 |
| **mini_swe_agent** | 17 | 2 | **2/20 (10%)** | -1 |
| **swe_agent** | 19 | 3 | **1/20 (5%)** | -2 |

*Baseline 0 empty patches because baseline eval was run when dlt-hub Docker images still existed. Enhanced runs correctly show 2-3 empty patches because those images are now missing.

Resolved IDs:
- Baseline/aider: a2aproject__a2a-python-683, ag2ai__faststream-2495, astropy__astropy-18753
- trae: a2aproject__a2a-python-683, ag2ai__faststream-2495
- openhands: ag2ai__faststream-2495, astropy__astropy-18753
- mini_swe_agent: ag2ai__faststream-2495, astropy__astropy-18753
- swe_agent: a2aproject__a2a-python-683

### Known Infrastructure Issues

1. **Missing Docker images**: `dlt-hub__dlt-2935` (pouya-replacements2/dev) and `dlt-hub__dlt-3048` (pouya-final20b/dev) images were deleted. Only `pouya20gpt-stage12/dev:*` images remain. The `validated_instances.jsonl` references stale image prefixes for these two issues.
2. **PennyLaneAI__pennylane-7474**: Solver hits `LimitsExceeded` across all enhanced conditions (too much compute). Baseline succeeded because it ran under different resource limits.

### Bug Fixes Applied (This Session)

| Bug | File | Fix |
|-----|------|-----|
| gpt-5.4-mini response_format 400 error | llm_client.py | Skip response_format for gpt-5 models |
| mini_swe_agent file-write failures | mini_swe_agent_enhancer.py | Explicit heredoc prompt + template placeholder rejection |
| swe_agent timeouts at 300s | .env | SWEAGENT_TIMEOUT=600 |
| Double provider prefix (openai/openai/...) | sweagent_enhancer.py, openhands_enhancer.py | Conditional prefix check |
| Quality gate over-strict | run_pouya5_solver_comparison.py | Removed title_changed and keyword hard blocks |
| Stale Ollama defaults in scripts | run_native_cli_pouya5_validation.py, run_solving_after_enhancement.py | Updated to OpenAI/gpt-5.4-mini |
| Duplicate .env entries | .env | Removed duplicate OPENHANDS_SOLVER lines |
| Hardcoded "/5" in report | run_pouya5_solver_comparison.py | Dynamic total_issues |
| Template placeholder leak in stdout | mini_swe_agent_enhancer.py | Added `<summary>`/`<steps>` sentinel check |

---

## Run Artifacts

| Run | Directory | Purpose |
|-----|-----------|---------|
| Enhancement (fixed, 20 issues) | `runs/native_cli_gpt54mini_20issues_merged/` | All 5 agents, 100 raw result files |
| Solver comparison (fixed) | `runs/pouya20_native_solver_comparison_fixed/` | Full solver+eval comparison |
| Enhancement (5-issue validation) | `runs/native_cli_gpt54mini_5issues_fixed/` | Post-fix verification run |
| Baseline solver | `runs/pouya_solver20_20260505_063614/` | 20-issue baseline (pre-existing) |

## Previous Experiments

| Experiment | Date | Dataset | Key Finding |
|-----------|------|---------|-------------|
| 3x3 groups | 2026-03-31 | 3x10 issues | Enhancement depends on agent + curation level |
| 50-issue SWE-bench-Live | 2026-04-03 | 50 issues | Enhancement never beneficial; aggressiveness = harm |
| 101-issue scale-up | 2026-03-30 | 2x101 issues | Aider: -35 to -46pp catastrophic degradation |
