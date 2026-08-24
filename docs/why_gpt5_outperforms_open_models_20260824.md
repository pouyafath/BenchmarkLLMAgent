# Why GPT-5-mini Outperforms Every Other Model (forensic analysis, 2026-08-24)

## Question
The capability-spread experiment found a **cliff, not a slope**: GPT-5-mini resolves 20/20
provably-solvable issues, the best open model manages 6/20, and everything else lands 0–4/20.
This analysis opens the agent trajectories to answer *why*.

## Method
For every model we replayed the **same 20 issues** (`.secrets/sample20_gpt5solved.txt`), same
cell (baseline, OpenHands solver, cap 30), and extracted per instance:

- terminal agent state and failure type from `openhands.log`
  (`AgentStuckInLoopError`, `reached maximum iteration`, `AgentState.FINISHED`);
- what was actually **submitted for scoring** — `model_patch` in `preds.json`, the authoritative
  artifact — classified as empty / well-formed git diff / non-git text / >1 MB dump.

The `config.toml` files are byte-identical across models except the model name (same
`temperature = 0.3`, `max_output_tokens = 16384`, same container image), so nothing here is a
configuration artifact.

## Results (baseline arm, 20 GPT-5-mini-solvable issues, cap 30)

| Model | Solved | Empty patch | Clean diff | non-git | >1 MB | FINISHED | Stuck in loop | Hit cap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **GPT-5-mini** (frontier) | **20** | **0** | **20** | 0 | 0 | **18** | **0** | 2 |
| GPT-4.1-mini (commercial) | 1 | 19 | 0 | 1 | 0 | 4 | 0 | 10 |
| Llama-3.3-70B | 4* | 13 | 0 | 4 | 3 | 14 | 1 | 2 |
| Qwen2.5-32B | 2 | 17 | 3 | 0 | 0 | 3 | 3 | 10 |
| DeepSeek-R1-70B | 1 | 19 | 1 | 0 | 0 | 13 | 7 | 0 |
| gpt-oss-120B | 1 | 19 | 0 | 1 | 0 | 2 | 11 | 1 |
| Llama-3-8B (fp16) | 1 | 18 | 1 | 1 | 0 | 8 | 5 | 6 |
| Qwen2.5-72B | 0 | 19 | 0 | 1 | 0 | 1 | 0 | 11 |
| Qwen2.5-Coder-32B | 0 | 18 | 0 | 2 | 0 | 3 | 1 | 14 |
| GLM-4.7-flash | 0 | 20 | 0 | 0 | 0 | 0 | 7 | 13 |
| DeepSeek-Coder-33B | 0 | 20 | 0 | 0 | 0 | 0 | 14 | 1 |
| Granite-Code-34B | 0 | 20 | 0 | 0 | 0 | 0 | 1 | 9 |
| Mixtral-8×22B | 0 | 20 | 0 | 0 | 0 | 0 | 16 | 1 |
| Mixtral-8×7B | 0 | 20 | 0 | 0 | 0 | 2 | 11 | 7 |
| DeepSeek-Coder-v2-16B | 0 | 20 | 0 | 0 | 0 | 0 | 17 | 3 |

\* see "Validity finding" below — Llama-3.3-70B's four solves are spurious.

Qwen3-32B (the best open model, 6/20) is **absent**: its g5s20 run is fragmented across three
partial dirs (4+5+4 of 20) and its reported score reuses the full-279 run. Re-running it is the
obvious next step.

## Three mechanisms

### 1. The gap is *submission*, not *fix quality*
The decisive column is **Empty patch**. GPT-5-mini submits a well-formed diff on **20/20**
instances. Every other model submits **nothing at all** on 13–20 of 20. There is essentially no
model that writes a clean patch which then fails to fix the bug — that failure mode barely exists
in the data. The open models are not losing a code-correctness contest; **they never reach the
point of proposing a fix.**

GPT-5-mini's median submission is **1.2 KB touching 1 file** — a minimal, targeted edit.

### 2. They die in the agent loop, in one of two ways
- **Stuck in a loop** (`AgentStuckInLoopError`, repeating an identical action):
  DeepSeek-Coder-v2-16B 17/20, Mixtral-8×22B 16/20, DeepSeek-Coder-33B 14/20, gpt-oss-120B and
  Mixtral-8×7B 11/20.
- **Burned all 30 iterations** navigating without converging: Qwen2.5-Coder-32B 14/20,
  GLM-4.7-flash 13/20, Qwen2.5-72B 11/20, Qwen2.5-32B 10/20.

GPT-5-mini hits neither: 0 loops, 2 cap-outs, 18 clean `FINISHED`. It is also the **fastest**
(~2 min median vs 3–25 min), because it converges instead of thrashing.

### 3. It is not tool-calling support, and not coding knowledge
**GPT-4.1-mini is the control that settles this.** It is commercial and natively tool-calling —
the same API surface as GPT-5-mini — yet it submits **19/20 empty patches**, finishes only 4, and
caps out 10 times. It behaves like the open models, not like GPT-5-mini. So the differentiator is
not tool-calling capability.

Nor is it code specialisation: Qwen2.5-Coder, DeepSeek-Coder (both sizes) and Granite-Code submit
**zero** clean patches between them. The bottleneck is sustained *agentic* competence — keeping a
long multi-step task coherent and knowing when to stop — which is exactly what the weaker models
lack regardless of provider or coding tuning.

### Failure signature: workspace destruction
Llama-3.3-70B is the pathological case. Its submissions are `diff -ruN /testbed /workspace`
output, up to **98 MB / 2.9 M lines**, in which the **entire repository appears as deleted**
(`@@ -1,2642 +0,0 @@`, target side timestamped 1970). The agent wrecked its own workspace and the
patch-extraction fallback serialised the whole deletion. Median non-empty submission: 22 KB, with
runaway cases touching a median of 244 files.

## Validity finding — the P2P-only metric credits patches that never applied

`report_p2p_pass()` in [scripts/evaluate/run_stage6_combined_new182.py](../scripts/evaluate/run_stage6_combined_new182.py#L32-L36)
scores an instance resolved on **PASS_TO_PASS alone**:

```python
p = json.load(open(report)).get("PASS_TO_PASS", {})
return len(p.get("failure", [])) == 0 and len(p.get("success", [])) > 0
```

There is no FAIL_TO_PASS requirement. A patch that **fails to apply** leaves the repo untouched,
so the pass-to-pass suite stays green and the instance is counted as solved.

All four of Llama-3.3-70B's baseline "solves" are of this kind:

| Instance | Submitted `model_patch` | Harness `report.json` |
|---|---|---|
| `ansible__ansible-85385` | 60 chars of **English prose**: `"added fix to allow access to underscore-prefixed attributes"` | `"resolved": false` |
| `IDSIA__sacred-941` | a **raw Python source file**, not a diff | `"resolved": false` |
| `conan-io__conan-18832` | 10.7 MB whole-repo deletion dump | — |
| `huggingface__lighteval-755` | 2.9 MB dump | — |

In each case `FAIL_TO_PASS` is **empty** (no bug-fixing tests ran) and the harness's own verdict is
`"resolved": false` — which the project's P2P-only criterion overrides.

This matters directly for the paper. The Discussion currently leans on
*"it removes all four of Llama-3.3-70B's solves"* as the vivid illustration of the Δ = −4. Those
four solves are artifacts of non-applying garbage, not fixes that enhancement destroyed. The
sentence should be dropped or reframed.

Note this is a *known design decision*, not an oversight: these SWE-bench-Live-style instances
often have no usable F2P tests, which is why the v1/v2/v3 gold-probe machinery exists. But the
consequence — non-applying submissions scoring as solves — should be stated as a threat to validity,
and it argues for **requiring a non-empty, cleanly-applying patch** as a precondition for counting
a solve.

## Implications for the paper
1. **Sharpen the cliff claim.** The right statement is not "weaker models write worse fixes" but
   "weaker models never produce a fix to evaluate." That is a stronger and more interesting result.
2. **Tool-calling is ruled out** as the explanation, on the GPT-4.1-mini control. Worth one
   sentence — it is the obvious reviewer objection.
3. **Drop the Llama-3.3-70B Δ=−4 anecdote**, and add the P2P-only criterion to Threats to Validity.
4. The RQ1 null is *unaffected* — if models never submit patches, enhancement has nothing to act
   on, which is entirely consistent with a directionless Δ. If anything it explains *why* the Δ is
   noise at the bottom of the capability range.

## Reproduction
- `scratchpad/agent_forensics.py`, `taxonomy2.py` (analysis scripts, session scratchpad)
- Trajectories: `runs/ollama_pool*_g5s20_*/<model>/baseline__solver_openhands/{work,preds.json}`
- GPT-5-mini: `runs/oai_aider_oh_279eval_20260805_203247/gpt-5-mini/baseline__solver_openhands/`
- Sample: `.secrets/sample20_gpt5solved.txt`
