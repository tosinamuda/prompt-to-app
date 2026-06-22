# Prompt2App

**Turn a natural-language prompt into a reusable, typed, optimizable LLM application with a generated UI.**

Prompt2App is a prompt compiler that treats free-form prompts as latent application specifications. Instead of throwing away a prompt after one use, it induces a typed signature (inputs, outputs, constraints), compiles it into an optimizable [DSPy](https://dspy.ai) program, and generates a form-based UI — so a prompt becomes a reusable tool, not a throwaway message.

```
"Write a polite email to supplier X asking for a revised quote on 20 laptops under $30k"
                                        ↓
                              Prompt Compiler (DSPy)
                                        ↓
              ┌─────────────────────────────────────────────┐
              │  Inputs:  supplier, item, quantity, budget  │
              │  Output:  email_subject, email_body         │
              │  Type:    string, string, integer, money    │
              └─────────────────────────────────────────────┘
                                        ↓
                        Generated Form UI + Runnable Program
                                        ↓
                    Human corrects fields → Optimizer improves
```

## Why

| Problem | What Prompt2App does |
|---|---|
| Prompts are ephemeral — the same task is retyped from scratch each time | Compiles the prompt into a parameterized app that can be reused |
| Chat is a poor interface for structured, repeated tasks | Generates a typed form with validation and defaults |
| Prompt engineering is trial-and-error | Exposes a DSPy signature that can be optimized against metrics |
| Sharing a prompt requires explaining "change X and Y" | The form **is** the interface — inputs are explicit |
| Human corrections are lost in chat | Field-level corrections feed back into the optimizer |

## Quickstart

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Node.js](https://nodejs.org/) 18+ and [pnpm](https://pnpm.io/)
- An [OpenRouter](https://openrouter.ai/) API key

### Setup

```bash
git clone https://github.com/tosinamuda/prompt-to-app.git
cd prompt-to-app

# Install Python dependencies
uv sync

# Configure your API key
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY
```

### Run (two processes)

```bash
# Terminal 1: Backend (FastAPI + MCP + A2A)
uv run app-start --port 8011

# Terminal 2: Frontend (Vite + React + Carbon)
cd web
pnpm install
pnpm dev
# Open http://127.0.0.1:5180
```

### Run tests

```bash
uv run pytest                          # unit tests (offline, no API key needed)
uv run ruff check src scripts tests    # lint
```

## Architecture

Prompt2App has three layers: a DSPy-based compiler backend, protocol servers (MCP + A2A), and a React frontend.

### Backend (`src/prompt2app/`)

| Module | Responsibility |
|---|---|
| `induction.py` | DSPy `ChainOfThought` signature inducer — prompt to typed spec |
| `compiler.py` | Builds a dynamic `dspy.Signature` + runnable program from the induced spec |
| `evaluation.py` | Field P/R/F1, type accuracy, signature validity metrics |
| `llm_judge.py` | LLM-based schema quality judge (5-dimension rubric) |
| `retrieval.py` | Prompt-to-app similarity search for reuse (cosine over embeddings) |
| `optimize.py` | Feeds human corrections back into `LabeledFewShot` / `BootstrapFewShot` / `GEPA` |
| `claude_lm.py` | DSPy LM backend that shells out to `claude -p` (flat-fee CLI) |
| `registry.py` | Approved UI component registry + layout validation |
| `mcp_server.py` | FastMCP tools: `compile_prompt`, `run_app`, `find_similar_apps`, etc. |
| `a2a_agent.py` | Google ADK agent served over A2A protocol |
| `api.py` | REST endpoints: `/api/compile`, `/api/retrieve`, `/api/apps/{id}/run` |

### Frontend (`web/`)

React + Vite + [Carbon Design System](https://carbondesignsystem.com/). Communicates with the backend via A2A protocol (with REST fallback). Features a 4-step progressive UI: Describe → Compile → Fill & Run → Optimize.

### Protocols

- **[MCP](https://modelcontextprotocol.io/)** — the generated app is served as an MCP UI resource with approved web components
- **[A2A](https://google.github.io/A2A/)** — the compiler agent is accessible via Google's Agent-to-Agent protocol

## Research

This prototype is an instrument for studying **prompt-to-program compilation**. The core research questions:

1. **Induction quality** — Can an LLM reliably induce typed signatures from raw prompts?
2. **Model scaling** — Does the value of induced structure shrink as the base model gets more capable?
3. **Parameterization granularity** — What governs the optimal number of fields to expose? (The novel question.)
4. **Feedback loop** — Does closing a human-correction loop improve induction quality over time?

### Experiments

```bash
# Induction eval over 8 gold-annotated cases
uv run python scripts/eval.py

# Model scaling study (8B → 70B → 120B → frontier)
uv run python scripts/scaling_study.py

# Loop ablation: severed vs fewshot vs bootstrap vs GEPA
uv run python scripts/loop_ablation.py
```

Results are saved to `data/eval/`. See [docs/](docs/) for the research framing and detailed notes.

### Key findings so far

**Scaling study (RQ2):** Induction quality scales monotonically with model size — 8B (judge: 0.67) → 70B (0.79) → 120B (0.93). Larger models induce better field names, types, and granularity.

**Loop ablation (RQ4):** Bootstrap filtering (judge: 0.88) beats the no-loop baseline (0.82). Raw few-shot demos and GEPA instruction evolution do not improve over the baseline with the current model pairing.

## Tech stack

- **[DSPy](https://dspy.ai)** — declarative LM programming framework (signatures, modules, optimizers)
- **[FastMCP](https://gofastmcp.com)** — Model Context Protocol server with generative UI (MCP Apps)
- **[Google ADK](https://google.github.io/adk-docs/)** — Agent Development Kit with A2A protocol support
- **[LiteLLM](https://litellm.ai)** + **[OpenRouter](https://openrouter.ai/)** — unified LLM access across providers
- **[Carbon Design System](https://carbondesignsystem.com/)** — IBM's open-source design system (React)
- **[FastAPI](https://fastapi.tiangolo.com/)** — async Python web framework
- **[fastembed](https://github.com/qdrant/fastembed)** — lightweight local embeddings for retrieval

## Project structure

```
prompt-to-app/
├── src/prompt2app/       # Python backend
│   ├── induction.py      # DSPy signature inducer
│   ├── compiler.py       # Signature → runnable program
│   ├── evaluation.py     # Metrics (field F1, type acc, validity)
│   ├── llm_judge.py      # LLM schema quality judge
│   ├── retrieval.py      # App reuse via similarity search
│   ├── optimize.py       # Human correction → optimizer
│   ├── mcp_server.py     # MCP tools + UI resource
│   ├── a2a_agent.py      # A2A agent (Google ADK)
│   ├── api.py            # REST API
│   └── main.py           # FastAPI app entry point
├── web/                  # React + Carbon frontend
├── scripts/              # Experiment runners
│   ├── eval.py           # Baseline induction eval
│   ├── scaling_study.py  # RQ2: model scaling
│   └── loop_ablation.py  # RQ4: feedback loop ablation
├── data/eval/            # Gold annotations + experiment results
├── tests/                # Pytest suite
└── docs/                 # Research notes and spec
```

## Configuration

Create a `.env` file in the project root:

```env
OPENROUTER_API_KEY=your-key-here
LM_MODEL=openrouter/openai/gpt-oss-120b
```

The experiment scripts also support `claude-cli/sonnet` and `claude-cli/haiku` model identifiers, which use the Claude CLI (`claude -p`) instead of an API key.

## License

MIT
