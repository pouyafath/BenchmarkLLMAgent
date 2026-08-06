# Solver Response-Handling & LLM Findings — 2026-06-15

Investigation triggered by low Stage-5 patch rates (smoke-2: baseline 5/10, enhanced 3/10).
All facts below were reproduced live against the dedicated Ollama on `:11435`.

## TL;DR
`qwen3:32b` is a **general reasoning model**, not an agentic/coder model. Two structural
mismatches with OpenHands depress its patch rate:
1. It emits **reasoning-only turns with empty `content`**, which the solver can't act on.
2. OpenHands does **not** grant it **native function-calling** (only `qwen3-coder*` qualifies),
   so it falls back to prompt-based FC that parses the (sometimes empty) `content`.

Neither is a bug in our code — it's a model/framework fit problem.

## Evidence

### 1. qwen3 splits reasoning into a separate field
Live probe of `:11435/v1/chat/completions` with `qwen3:32b`:
- `message keys: ['role', 'content', 'reasoning']`
- Simple prompt → `content`=19 chars ("2 + 2 equals **4**."), `reasoning`=561 chars.

### 2. Empty-content turns are frequent
Per-instance count of `content=''` completions (from `openhands.log`):
| Instance | result | empty-content turns |
|---|---|---|
| HKUDS__nanobot-3575 | PATCH | 17 |
| Diaoul__subliminal-1327 | PATCH | 9 |
| Azure-Samples__azure-search-openai-demo-2752 | empty | 15 |
| DLR-RM__stable-baselines3-2211 | empty | 16 |

**Caveat:** empty-turn count does *not* cleanly separate pass/fail (successful nanobot had 17,
failed azure had 15). So reasoning-only turns are an **efficiency / iteration-budget drag**, not
a proven sole cause of failures. They waste turns against `max_iter=30` and add latency.

### 3. qwen3:32b does NOT get native function-calling in OpenHands 1.4.0
`openhands/llm/model_features.py` → `FUNCTION_CALLING_PATTERNS` includes `qwen3-coder*` but
**not** plain `qwen3`. Verified:
```
get_features('openai/qwen3:32b').supports_function_calling == False
get_features('qwen3-coder').supports_function_calling      == True
```
→ OpenHands uses the **prompt-based FC converter** (`fn_call_converter.py`), parsing the agent's
action out of text `content`. Empty `content` ⇒ no action that turn.

### 4. Active solver path
`src/solvers/openhands_solver.py: solve_instance()` spawns
`python -m openhands.core.main -i {max_iter} --config-file config.toml` (real CodeAct in Docker),
configured as **`model = "openai/qwen3:32b"`** against Ollama's `/v1`. Patch is read from the
`oh_solution.patch` file the agent writes via a tool (stdout `_extract_patch` is a fallback).

### 5. How to disable thinking (and the catch)
| Method | content | reasoning | works? |
|---|---|---|---|
| default (thinking on) | 92 | 1856 | content present |
| `/no_think` prompt token | **0** | 2037 | ❌ forces empty content |
| `/v1` + `chat_template_kwargs:{enable_thinking:false}` | **0** | 2014 | ❌ ignored by Ollama OpenAI shim |
| **native `/api/chat` + `think:false`** | **287** | 0 | ✅ clean |

The solver uses the **`/v1` (openai) endpoint**, which ignores `enable_thinking`. To disable
thinking in the solver you must switch litellm to the **`ollama_chat/` provider** (native base_url,
no `/v1`) and pass `think:false`, or set a server-side no-think default.

## Minor (non-active) code issues
- `openhands_solver.py:127` — health-check `_ensure_model_healthy` reads only `.content`. Harmless
  today, but a reasoning-only "Say OK" reply would false-trigger an unload/reload that **evicts the
  model from VRAM**. Harden to `content + reasoning`.
- `src/solvers/openhands/agent.py:184` — `.content or ""`; this single-shot path is **unused**
  (the CodeAct subprocess path is active). No impact.

## Which LLMs are best with OpenHands?

OpenHands 1.4.0 grants **native function-calling** only to these families
(`FUNCTION_CALLING_PATTERNS`): Claude 3.5/3.7/4 (Sonnet/Opus/Haiku), GPT-4o/4.1/5, o3/o4-mini,
Gemini 2.5-pro/3, `groq/*`, Kimi-K2, **`qwen3-coder*`**, **`deepseek-chat`**, `grok-code-fast-1`.

### Open-weight, self-hostable options that get native FC AND fit the hardware
| Model | Ollama tag | Size | Why |
|---|---|---|---|
| **Qwen3-Coder-30B-A3B-Instruct** | `qwen3-coder:30b` | ~18-20 GB (Q4) | MoE 30B/3B-active, matches `qwen3-coder*` ⇒ native FC, **no thinking overhead**, agentic-coding optimized. Best drop-in (same family/size as qwen3:32b). |
| **Devstral-Small-2507** | `devstral` | ~14 GB (24B Q4) | Apache-2.0, **co-built by Mistral + All Hands AI specifically for OpenHands**, native tool calling, strong SWE-bench. |
| Qwen3-Coder-480B | — | ~250 GB+ | Native FC but needs many GPUs; overkill vs 30B. |
| DeepSeek-V3 (`deepseek-chat`) | — | ~400 GB (671B) | Native FC but too large to self-host reasonably. |

**Currently pulled on `:11435`:** none match native-FC patterns (we have qwen2.5-coder, qwen3.5,
glm-4.7, deepseek-coder/-r1, llama3.x, mixtral — none of which are in `FUNCTION_CALLING_PATTERNS`).
Would need to `ollama pull qwen3-coder:30b` and/or `ollama pull devstral`.

### Is switching wise?
**Yes, and now is the ideal time** — only the smoke + a 60-instance batch have run; sunk cost is
low. qwen3:32b is a general reasoning model fighting the agentic loop on two fronts (thinking
overhead + no native FC). Qwen3-Coder-30B and Devstral are *purpose-built* for exactly this and
fix both issues. **But validate first**, don't switch blind:

**Recommended experiment:** 10-instance A/B on the smoke set comparing
`qwen3:32b` (current) vs `qwen3-coder:30b` vs `devstral` — measure patch rate **and** wall-time.
Pick the winner before launching the full 383.

## A/B attempt #1 (2026-06-15) — qwen3-coder:30b via Ollama native-FC → ABORTED, invalid

Ran qwen3-coder:30b on a dedicated Ollama (`:11436`, GPU 0) over smoke-2's 10 baseline issues
with `native_tool_calling=true`. **Result: 0/10 patches** — but this is NOT a fair model verdict.
Per-instance log analysis:
- **9/10 ended in `AgentState.ERROR`** — `AgentStuckInLoopError` or `RuntimeError: reached maximum
  iteration (30)`. The model WAS tool-calling (`finish_reason='tool_calls'`, content like
  "Let me check…", tools `execute_bash`/`str_replace_editor`) but looped.
- **0/10 ran the patch-export step** (`git diff > /workspace/oh_solution.patch`) → no patch captured
  even where edits were made.

**Two root causes uncovered (both bigger than the model choice):**
1. **Ollama's OpenAI-compat function-calling is flaky** → native-FC agents loop / get stuck. A
   reliable tool-calling stack (e.g. **vLLM**) is likely needed to use native FC at all.
2. **Patch capture is fragile by design.** `solve_instance` only gets a patch if the agent itself
   runs `cd /testbed && git diff > /workspace/oh_solution.patch` (the shared-volume bridge), or
   types a diff into stdout. Native-FC agents edit via tools and skip the export → solved work is
   lost. This also means **absolute patch rates undercount across ALL runs** (any solved-but-not-
   exported instance). The robust fix: have the **harness** run `git diff` in the container before
   teardown, independent of agent behavior.

**Revised recommendation:** Switching to qwen3-coder is NOT a drop-in win *via Ollama*. Keep
qwen3:32b for the full 383 (it works in this harness; batch60 is valid). Before any model switch:
(a) add harness-side `git diff` patch capture, and (b) serve the coder model via vLLM (not Ollama)
for reliable native function-calling. Then re-run the A/B. Pulled models kept at
`/home/22pf2/ollama_ab_models` for the retry.

### Impact on the paper
The baseline-vs-enhanced comparison stays valid (identical model/config on both arms), so the
**relative** RQ results hold regardless of model choice. But **absolute** patch rates are
suppressed by qwen3's thinking overhead + prompt-based FC — note in threats-to-validity, and
ideally report the model that wins the A/B.
