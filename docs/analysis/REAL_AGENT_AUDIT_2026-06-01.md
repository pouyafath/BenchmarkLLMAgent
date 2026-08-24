# Real Agent Audit (2026-06-01)

This audit separates three different states that were getting mixed together:

1. **Real native agent integration**
   - the benchmark invokes an actual package / CLI / runtime
   - not a style-simulation prompt
2. **LLM proxy / simulated agent**
   - the benchmark uses a generic LLM prompt that imitates the agent
   - not acceptable for "real native agent" claims
3. **Not integrated / unavailable**
   - no runnable local integration exists in this repo + host setup

The classification below is based on current repo code and local host evidence on
`docjk-gpu-01`.

---

## 1) Current Category A Enhancer Inventory

Source of truth:

- `src/enhancers/ready_to_use/registry.py`
- `src/enhancers/dispatcher.py`

| Agent ID | Registry Type | Local Reality | Notes |
|---|---|---|---|
| `openhands` | `real` | **real native integration** | Runs `python -m openhands.core.main` from `bench_env` |
| `swe_agent` | `real` | **real native integration** | Dedicated native wrapper |
| `aider` | `real` | **real native integration** | Dedicated native wrapper |
| `mini_swe_agent` | `real` | **real native integration** | Dedicated native wrapper |
| `trae` | `real` | **real native integration** | Dedicated native wrapper |
| `cl_enhanced_gemma3` | `real` | **real native integration** | Wrapper into `LLMforGithubIssuesRefactor` |
| `github_copilot` | `llm_proxy` | **proxy only** | Not a native benchmark integration |
| `sweep` | `llm_proxy` | **proxy only** | Not a native benchmark integration |
| `cline` | `llm_proxy` | **proxy only** | Not a native benchmark integration |
| `magis` | `llm_proxy` | **proxy only** | Not a native benchmark integration |
| `copilot_workspace` | `llm_proxy` | **proxy only** | Not a native benchmark integration |
| `chatbr` | `llm_proxy` | **proxy only** | Not a native benchmark integration |
| `coderabbit` | `llm_proxy` | **proxy only** | Not a native benchmark integration |
| `live_swe_agent` | `llm_proxy` | **proxy only** | Explicitly routed through `llm_proxy_enhancer` |

Framework-built side:

| Agent ID | Local Reality | Notes |
|---|---|---|
| `simple_enhancer` | **not a native external agent** | real local enhancer implementation, but it is our own framework-built enhancer, not a third-party native agent |
| `code_context` | **not a native external agent** | deterministic local enhancer |
| `llm_append_analysis` / related append modes | **not a native external agent** | direct local LLM workflow |

---

## 2) OpenHands: Real or Fake?

**Conclusion: OpenHands is real in this benchmark.**

Why:

- Registry marks it as:
  - `enhancer_type = "real"`
  - `native_override = True`
- Dispatcher maps `openhands` directly to:
  - `src.enhancers.ready_to_use.openhands_enhancer.enhance_issue`
- The implementation runs the real package:
  - `bench_env/bin/python -m openhands.core.main`

Relevant files:

- `src/enhancers/ready_to_use/registry.py`
- `src/enhancers/dispatcher.py`
- `src/enhancers/ready_to_use/openhands_enhancer.py`
- `src/solvers/openhands/agent.py`

Important nuance:

- there is no standalone `openhands-cli` binary in `bench_env/bin`
- that does **not** make it fake
- the integration is module-based, not standalone-binary-based

Verified local host evidence:

- `bench_env` can import:
  - `openhands`
  - `openhands.core.main`
  - `openhands.llm.llm`

So OpenHands here is:

- a **real agent runtime**
- wrapped by our benchmark adapter
- backed by an LLM provider

It is **not** "just a prompt acting like OpenHands."

---

## 3) What API / Credentials OpenHands Needs

OpenHands itself is the agent runtime. It still needs an LLM backend.

### Enhancer path

`src/enhancers/ready_to_use/openhands_enhancer.py` uses:

- `OPENHANDS_MODEL` (default `gpt-5.4-mini`)
- `OPENHANDS_BASE_URL` (default `https://api.openai.com/v1`)
- `OPENHANDS_API_KEY` (default falls back to `OPENAI_API_KEY`)

### Solver path

`src/solvers/openhands/agent.py` uses:

- `OPENHANDS_SOLVER_MODEL` (default `gpt-5.4-mini`)
- `OPENHANDS_SOLVER_BASE_URL` (default `https://api.openai.com/v1`)
- `OPENHANDS_SOLVER_API_KEY` (default falls back to `OPENAI_API_KEY`)

### Practical meaning

To run **real OpenHands** here, the minimum requirement is:

- a valid `OPENAI_API_KEY`

or another **OpenAI-compatible** endpoint plus key:

- `OPENHANDS_BASE_URL`
- `OPENHANDS_API_KEY`

and similarly for the solver if separated:

- `OPENHANDS_SOLVER_BASE_URL`
- `OPENHANDS_SOLVER_API_KEY`

So if the question is:

> “Do we already have a real OpenHands agent here?”

Answer:

- **Yes**

If the question is:

> “Do we need some API to run it?”

Answer:

- **Yes, for the LLM backend**
- in the current benchmark setup that means an OpenAI-compatible API key

---

## 4) OpenClaw: Real or Fake?

**Conclusion: OpenClaw is not currently integrated here.**

Verified current repo + host state:

- no `openclaw_enhancer.py`
- no `openclaw` dispatcher entry
- no local `openclaw` binary
- no local `openclaw` Python module
- no local pip package detected on `docjk-gpu-01`

So OpenClaw is currently:

- **not available**
- **not native**
- **not acceptable to fake with an LLM proxy**

That is why Developer 04 correctly hard-stopped instead of pretending.

---

## 5) What Would Be Needed For Real OpenClaw

External docs indicate OpenClaw is a self-hosted local agent platform with:

- local install via:
  - `curl -fsSL https://openclaw.ai/install.sh | bash`
- GitHub releases for Linux / macOS / Windows
- its own local runtime / dashboard / gateway
- "your API keys" model-provider model

Operationally, for a **real OpenClaw integration** here we would need:

1. **A real local OpenClaw install**
   - official installer or GitHub release
   - not a placeholder wrapper
2. **A documented local entrypoint**
   - CLI, module, or RPC/API call path
3. **A model provider backend**
   - likely OpenAI / Anthropic / another supported provider
   - possibly local-model support, but that still needs verification after install
4. **A BenchmarkLLMAgent adapter**
   - new `src/enhancers/ready_to_use/openclaw_enhancer.py`
   - registry entry
   - dispatcher entry
   - smoke validation on a small canary

At the moment, the missing first step is:

- **actual OpenClaw installation/runtime on the host**

---

## 6) Safe Interpretation For Benchmark Reporting

When reporting results:

- `openhands` = **real native agent integration**
- `openclaw` = **not integrated / unavailable**
- `github_copilot`, `sweep`, `cline`, `magis`, `copilot_workspace`, `chatbr`,
  `coderabbit`, `live_swe_agent` = **LLM proxy simulations**, unless and until
  a real native integration is added

Do not mix:

- **real external agent**
- **our local enhancer**
- **LLM proxy simulation**

Those are three different classes.

---

## 7) Immediate Next Step If We Want Real OpenClaw

If we want to try a real OpenClaw integration next, the sequence should be:

1. install OpenClaw on `docjk-gpu-01`
2. verify it runs locally
3. determine exact model-provider requirements
4. write a real BenchmarkLLMAgent wrapper
5. run a 3-5 issue canary before any benchmark claim

Needed from the user for that path:

- one model-provider credential that OpenClaw can actually use after install
  - most likely OpenAI-compatible or Anthropic, depending on what the installed
    runtime supports on this host

