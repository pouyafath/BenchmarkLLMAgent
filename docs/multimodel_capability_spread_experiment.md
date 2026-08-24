# Multi-Model Capability Spread Experiment (completed 2026-08-17)

## Goal
Test whether the RQ1 null (issue enhancement does not improve fix correctness) and the
solver-dominance finding hold **across the full range of LLMs available to us**, by running the
paper's canonical cell — **enh:Aider → sol:OpenHands** — with every model on the server plus two
commercial references, on a fixed set of *provably-solvable* issues.

## Sample
- **20 issues**, drawn (seed 42) from the subset of the **279 gold-evaluable** issues that
  **GPT-5-mini resolves at baseline** — i.e., issues known to be solvable by a strong model.
- File: `.secrets/sample20_gpt5solved.txt` (gitignored).
- **Deliberate upward bias for GPT-5-mini** (baseline = 20/20 by construction); the point is to see
  how many *known-solvable* issues each weaker model can also close, and whether enhancement moves
  the needle within each model.

## Method
- Cell: baseline (OpenHands on original) + Aider enhance + OpenHands solve on enhanced text.
- **cap = 30 iterations**, workers 2–4, one open-weight model held per run.
- Metric: **P2P-resolved** on the gold-evaluable subset, same three-method (v2/v3/v1) gold-probe
  harness as the paper's Table 1 (`scripts/evaluate/run_stage6_combined_new182.py` logic;
  scored via `scratchpad/score_sample.py` with `data/stage6_all279_v{1,2,3}.jsonl`).
- Open models served via **Ollama**: private `:11435` (qwen3:32b) and shared `:11434` (multi-load).
- Commercial models via the OpenAI API (`scripts/workflows/run_openai_cell.py`).

## Results (resolved / 20, cap 30)

| Model | Baseline | enh:Aider | Δ |
|---|---|---|---|
| GPT-5-mini* (frontier) | 20/20 | 18/20 | −2 |
| Qwen3-32B | 6/20 | 5/20 | −1 |
| Llama-3.3-70B | 4/20 | 0/20 | −4 |
| Qwen2.5-32B | 2/20 | 3/20 | +1 |
| GPT-4.1-mini* | 1/20 | 2/20 | +1 |
| Qwen3.5-35B | 1/20 | 2/20 | +1 |
| DeepSeek-R1-70B | 1/20 | 1/20 | 0 |
| gpt-oss-120B (reasoning) | 1/20 | 1/20 | 0 |
| Llama-3-8B (fp16) | 1/20 | 0/20 | −1 |
| GLM-4.7-flash-30B | 0/20 | 2/20 | +2 |
| Qwen2.5-72B | 0/20 | 1/20 | +1 |
| Qwen2.5-Coder-32B | 0/20 | 1/20 | +1 |
| DeepSeek-Coder-33B | 0/20 | 0/20 | 0 |
| DeepSeek-Coder-v2-16B | 0/20 | 0/20 | 0 |
| DeepSeek-R1-8B | 0/20 | 0/20 | 0 |
| Granite-Code-34B | 0/20 | 0/20 | 0 |
| Llama-3-8B (q4) | 0/20 | 0/20 | 0 |
| Mixtral-8×22B | 0/20 | 0/20 | 0 |
| Mixtral-8×7B | 0/20 | 0/20 | 0 |
| gemma-3-12B | — | — | did not load |
| Qwen3-Coder-30B | — | — | did not load |

\* commercial reference (not on the local server). **19 models scored + 2 that would not load.**

## Findings
1. **Capability is a cliff, not a slope.** Only the frontier model (GPT-5-mini) reliably closes
   provably-solvable issues (20/20); the best open model (Qwen3-32B) manages 6/20; every other
   model — open or commercial — lands 0–4/20.
2. **Enhancement helps none of them.** Δ ranges −4…+2 across all 19 models — uniformly negligible or
   negative (it *removes* all four of Llama-3.3-70B's solves). Consistent with RQ1 across the whole
   capability range.
3. **Code-specialized models are no better** than general ones (Qwen2.5-Coder, DeepSeek-Coder,
   Granite-Code all ≈0). Agentic competence, not coding knowledge, is the bottleneck.
4. **gpt-oss-120B ≈ 0** patches, confirming earlier observations.

## Replication note (added 2026-08-24)

The Qwen3-32B row above (6/20 -> 5/20, delta -1) reused the full-279 run rather than a dedicated
g5s20 run. A clean 20-instance rerun of the identical cell gives **7/20 -> 9/20, delta +2** --
the sign of the delta flips between two runs of the same configuration. All 16 solves in the
rerun are genuine unified diffs (verified), so this is run-to-run non-determinism, not a scoring
artifact. Treat the per-model delta as noise; see
`docs/why_gpt5_outperforms_open_models_20260824.md`.

Also added: **GPT-5-mini on the unbiased random-20 = 11/20 -> 10/20 (delta -1)**, scored from the
existing 279-issue run at no API cost (both samples are subsets of it). Its 55% on an unbiased
draw matches its 56% on the full 279.

## Infrastructure notes
- **Pool orchestrator** (`scripts/workflows/pool_orchestrator.py`): keeps 3 models running in
  parallel on `:11434` (which multi-loads), VRAM-aware (holds a launch if free VRAM < model size +
  buffer), health-logs every 5 min, auto-advances a queue, skips models that fail to load.
- `:11434` confirmed to hold multiple models concurrently; `:11435` is `MAX_LOADED=1` + `KEEP_ALIVE=-1`
  (single pinned model).
- OpenHands leaks runtime containers; reaped periodically (age-based) — never affected results.
- **Two models could not load** on the available Ollama/driver (gemma-3, Qwen3-Coder-30B) — a
  driver/version limitation, not GPU capacity.
- Runtime: ~2 days at 3-parallel for ~17 local models; cost: only GPT-4.1-mini spent real money (~5 CAD),
  all local runs free.

## Reproduction
- Sample: `.secrets/sample20_gpt5solved.txt`
- Local cell: `scripts/workflows/run_ollama_cell.py --model <M> --base-url http://localhost:11434/v1 --instances-file <sample> --tag <t>`
- OpenAI cell: `scripts/workflows/run_openai_cell.py --instances-file <sample> --model <M>`
- Score: `scratchpad/score_sample.py <run_dir> <sample> <label>` → `runs/stage6_sample_<label>/result.json`
- Paper: `papers/drafts/TSE_BenchmarkLLMAgent_2026.tex` §7 "Capability spread across many models" (branch `paper-crossmodel`).
