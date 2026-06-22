# Prompt2App — Product & Research Spec

**Status:** working prototype (v0.2) · **Owner:** Tosin · **Last updated:** 2026-05-30

> One line: **Prompt2App turns a one-off natural-language prompt into a reusable, typed,
> optimizable mini-application with a generated UI — so a prompt becomes a tool, not a
> throwaway message.**

This document covers the problem, audience, the end-to-end user journey, scope, design
principles, success metrics, and the research the system is built to support. It reflects
what is actually implemented today and is explicit about what is aspirational.

---

## 1. Problem & pain points

A prompt is currently the unit of work for LLMs, but it is a *bad* unit for anything done
more than once:

| Pain point | Who feels it | Today's workaround | Why it's bad |
| --- | --- | --- | --- |
| **Prompts are ephemeral & re-typed.** The same task ("draft a deployment request", "write a supplier email") is re-written from scratch each time, with drift. | Anyone who repeats LLM tasks | Copy-paste from a notes file / prompt library | Inconsistent inputs → inconsistent outputs; no parameterization |
| **Chat is a poor interface for structured, repeated tasks.** No typed fields, no validation, easy to omit a required detail (budget, deadline, environment). | Practitioners & non-experts | Re-prompt when the model asks for missing info | Slow, error-prone, no guarantee the right fields were supplied |
| **Prompt engineering is unstructured.** Improving a prompt is manual trial-and-error with no schema to optimize against. | Prompt/AI engineers | Eyeballing outputs, ad-hoc edits | Not measurable, not reproducible, hard to optimize systematically |
| **Sharing a prompt with a non-author is hard.** The recipient doesn't know which parts are meant to vary. | Teams | A doc explaining "change X and Y" | High friction; the prompt's "interface" is implicit |
| **No structured channel for human feedback.** Corrections live in chat and are lost. | Evaluators, domain experts | Free-form comments | Feedback can't be folded back into the system |
| **Straight prompt→tool-call is ungrounded/unsafe.** Agents jump from intent to action with no verification surface. | Agent builders | Hope, or a Y/N confirm | No typed, inspectable boundary between intent and execution |

**Core insight:** the prompt is a *latent specification*. If we can recover that
specification (its inputs, outputs, constraints) we can compile it into something reusable,
inspectable, runnable, and improvable.

---

## 2. Target audience

**Primary persona — "Dayo", applied AI / prompt engineer.**
Runs the same families of LLM tasks repeatedly; wants reusable, typed, optimizable building
blocks instead of a prompt-notes file. Cares about output consistency and being able to
improve a task over time. Comfortable with DSPy / OpenRouter concepts.

**Secondary — internal-tooling / platform engineer.**
Wants to turn a colleague's good prompt into a shareable internal "applet" with a form and
guardrails, callable by non-experts or by other agents (over A2A/MCP).

**Tertiary — domain expert / non-engineer (the consumer of a compiled app).**
Doesn't write prompts; *fills a form*. The generated UI lowers the barrier to reusing an
expert-authored prompt safely.

**Fourth — researcher / evaluator.**
Uses the generated UI as a structured **prompt-evaluation workbench**: edit extracted
fields, run, label errors, submit corrections — producing structured feedback data instead
of messy chat transcripts.

Audience boundary: this is **not** a consumer no-code app builder and not a general
chatbot. It is a workbench for people who treat prompts as engineering artifacts.

---

## 3. What it is (concept)

Prompt2App is a **prompt compiler** with a closed optimization loop:

```
raw prompt
  → induced typed signature        inputs / outputs / constraints   ← "parameter abstraction"
  → compiled DSPy program          runnable
  → generated UI (MCP App)         approved, typed components
  → human fills, runs, corrects
  → corrections become training data → optimize the inducer
  → better signatures / outputs next time
```

The generated UI is delivered as a constrained **MCP App** (a validated layout of
pre-approved components), not arbitrary markup — so the interface is also a control surface,
not just cosmetics.

### Implemented architecture (today)

- **Induction (DSPy):** `InduceAppSignature` signature + `SignatureInducer` module turn a
  prompt into a typed spec (`{task_name, title, description, inputs[], outputs[], constraints[]}`).
- **Compiler:** builds a *dynamic* `dspy.Signature` + runnable program from the spec, and a
  generative-UI form schema.
- **MCP Apps server (FastMCP):** `compile_prompt` / `run_app` / `get_app` / `set_app_input`
  / `optimize_inducer` tools; the generated UI is served as the MCP UI resource
  `ui://prompt2app/app.html` (a validated layout of approved web components from a registry).
- **A2A agent (Google ADK):** an `LlmAgent` wired to the MCP tools, served over the A2A
  protocol; the browser talks to it with the official `@a2a-js/sdk` client.
- **Host SPA:** React + Vite + IBM Carbon (UI Shell). Deterministic `/api/compile` REST
  fallback guarantees the flow works even when the model can't tool-call.
- **Optimization:** human corrections persist as JSONL training data; `dspy.LabeledFewShot`
  recompiles the inducer.

Model: `openrouter/openai/gpt-oss-120b` via LiteLLM (configurable).

---

## 4. User journey (end-to-end)

The UI is **sequencing-led**: a progress indicator (`Describe → Compile → Fill & run →
Optimize`) gates the experience, with later steps dimmed until reachable. Details are
revealed progressively (accordions); exactly one primary action is shown at a time.

### Narrative

> Dayo keeps writing variations of "draft a GitHub issue for a bug". She pastes one such
> prompt into Prompt2App and hits **Compile**. The system induces a typed signature
> (`issue_title: string`, `issue_description: text`, `priority: enum[low|medium|high]` →
> `issue_title`, `issue_body`) and renders a form pre-filled from her prompt. She tweaks the
> priority, clicks **Run**, and gets a clean issue. The induced `priority` should have been
> an enum of her team's labels, so she edits the signature JSON and **saves the correction**.
> **Optimize** now appears; she folds the correction in. Next time she compiles a similar
> prompt, the signature is right. She shares the compiled app's URL with a teammate who just
> fills the form — no prompt-writing required.

### Steps

| # | UI step | User action | System action | Disclosure / state |
| --- | --- | --- | --- | --- |
| 0 | **Discover** | Opens the workbench (or picks an example) | Empty state; only "Describe" active | Fill & run + Optimize dimmed |
| 1 | **Describe** | Types/pastes a prompt (or selects an example) | Enables the single primary action | One primary button (Compile) |
| 2 | **Compile** | Clicks **Compile** | A2A agent calls `compile_prompt` → DSPy induces the signature → MCP UI resource returned (deterministic REST fallback if the model can't tool-call) | Stepper advances; Fill & run un-dims |
| 3 | **Review signature** | (Optional) expands the **Signature** accordion | Shows typed inputs/outputs + constraints | Collapsed by default (progressive disclosure) |
| 4 | **Fill** | Edits the generated form (text / number / currency / date / enum / checkbox), pre-filled from the prompt | Validates types | Generated app is the focus; "Run program" is now the sole primary |
| 5 | **Run** | Clicks **Run program** | Executes the compiled DSPy program; skeleton → typed outputs | Output rendered inline |
| 6 | **Inspect** | Reads outputs | — | — |
| 7 | **Correct** | (Optional) edits the signature JSON, **Save correction** | Persists a corrected spec as training data | Optimize step + header action appear (just-in-time) |
| 8 | **Optimize** | Clicks **Optimize inducer** | Recompiles the inducer from collected corrections (`LabeledFewShot`) | Closes the loop |
| 9 | **Reuse / share** | Re-uses the compiled app, or shares its URL / calls it via A2A or MCP | Same typed app serves humans and agents | — |

### Alternate / failure paths
- **Model can't tool-call:** A2A agent returns no UI → host falls back to `/api/compile`
  (deterministic). The generated app still appears; mechanism shown as a `via rest` tag.
- **Bad induction:** user corrects the signature (step 7) — the correction *is* the product
  feedback loop, not an error.
- **Run error:** inline error in the output region; inputs preserved.

---

## 5. Scope

### In scope (built)
- Prompt → typed signature induction (closed type system: string, text, integer, number,
  money, date, boolean, enum).
- Dynamic DSPy program compilation + execution.
- Generated UI via MCP Apps (approved-component registry + layout validation).
- A2A agent exposure (`@a2a-js/sdk` client) + deterministic REST path.
- Human correction capture + few-shot re-optimization of the inducer.
- Carbon UI Shell host with sequencing-led disclosure.
- **Prompt-to-applet reuse** — retrieval over prior apps (`/api/retrieve`, `find_similar_apps`
  MCP tool); the host offers "Reuse this app" before recompiling.
- **Eval harness** (`scripts/eval.py` + `evaluation.py`) + an offline **pytest** suite.

### Aspirational / next (not built)
- **Semantic retrieval:** reuse is currently *lexical* (token-cosine); embedding-based
  matching would catch paraphrases the lexical score misses.
- **Richer types:** lists, nested objects, file uploads.
- **Tool binding:** binding a compiled app's output to a real downstream tool/API/MCP action
  with a confirmation surface.
- **Metric-driven optimization** beyond few-shot demos (e.g., `MIPROv2`, reward functions).
- **Multi-user persistence / auth / sharing** (today: in-memory + JSONL).

### Non-goals
- A general chatbot. A consumer no-code site builder. A hosted multi-tenant SaaS (prototype
  is local/single-process).

---

## 6. Design principles (UX)

The interface is treated as a **control surface**, optimized against cognitive load:

- **Sequencing-led (staged disclosure):** the progress indicator gates the flow; unreachable
  steps are dimmed. The stepper reflects the real sequence, it isn't decoration.
- **Progressive disclosure:** signature details, JSON editor, and agent trace are collapsed
  by default and revealed on demand.
- **Just-in-time:** Optimize only appears once a correction exists.
- **Prioritization:** exactly one filled-primary action visible at any time; the primary
  "travels" with the active step (Compile → Run program).
- **Reduction:** routine status noise removed; the mechanism (`via agent`/`via rest`) is a
  small tag, not a banner.
- **Deliberate co-visibility exception:** the prompt and the generated app stay on screen
  together so re-compiling after a tweak is cheap.
- **Constrained generation:** generated UI is a validated layout of approved components, not
  arbitrary markup — safety + consistency (IBM Carbon).

---

## 7. Success metrics (product)

- **Reuse rate:** % of compiled apps run more than once / by someone other than the author.
- **Time-to-first-good-output** vs. raw chat for a repeated task.
- **Correction rate trend:** corrections per compile should fall as the inducer optimizes.
- **Field-completeness:** % of required fields supplied before first run (vs. chat omissions).
- **Share/handoff success:** a non-author completes a compiled app without help.
- **Agent-callability:** % of compiles that succeed via the A2A tool path (model-dependent).

---

## 8. Research opportunities

The system is also a **research instrument**. The honest framing (see `docs/notes-3.md`) is
that the *closed loop* is the contribution, and the sharpest open question is
**parameterization granularity** — not "LLM extracts entities and makes a form", which is
already known.

### Research questions
- **RQ1 — Parameterization granularity (primary).** Given a prompt, what governs the optimal
  level of parameterization when inducing a typed program, and can that level be *predicted*
  rather than hand-tuned? Lifting everything into inputs maximizes reuse but makes the user do
  the model's work; baking everything in maximizes one-shot quality but kills reuse. Where is
  the reuse-adjusted-quality peak, and what predicts it?
- **RQ2 — Scaling / model-tier (most tractable).** Does the value of explicit induced
  structure shrink as the base model improves at following raw instructions? Measure the
  structure-vs-raw gap across model tiers; a clean shrinking curve tells people *when* this
  tooling is worth building.
- **RQ3 — Feedback transfer (per unit time).** Do *field-level* corrections improve the
  program for future inputs more than *output ratings* do, **per unit of annotation time**?
  (Normalize by time, or the richest interface wins by construction.)
- **RQ4 — Does closing the loop help?** Ablation: full system vs. system-with-the-feedback-
  loop-severed, holding everything else constant. This isolates the headline claim.

### Hypotheses (testable)
- H1: parameterized abstractions yield more consistent outputs than raw prompts.
- H2: optimizing the *induced* signature matches or beats a hand-written one after K corrections.
- H3: generated forms reduce missing-field rate and correction time vs. chat.
- H4: structured field corrections give higher training utility per annotation-minute than
  free-form output ratings.
- H5: structure helps weaker models more than frontier models (the RQ2 curve).

### Evaluation design
- **Baselines:** chat-only · hand-built static form · one-shot generated UI · Prompt2App
  (full loop). Plus the **loop-severed ablation** for RQ4.
- **Metrics:** slot/field extraction quality, signature validity, output quality + format
  compliance, missing/hallucinated-field rate, human correction time, **annotation utility
  per minute**, reuse success on held-out similar prompts, optimization gain after K corrections.
- **Validity guardrails (from the critique):**
  - Report **inter-annotator agreement on the "gold" abstractions themselves** before trusting
    any field-F1 — the non-entity fields (`tone`, `audience`) that make this novel are the
    hardest to annotate reliably.
  - **Drop NER/slot-filling as competitors** (strawmen); use LLM structured extraction and a
    manual signature as the real baselines.
  - For any "form as safety boundary" claim, compare against a **human-confirmation baseline
    without the generated form** — otherwise you're measuring human-in-the-loop, not the form.
  - Make the optimization objective **operational** (a concrete optimizer per term) or report
    the axes as a **Pareto** analysis rather than a free-weighted sum.

### Likely venue split
- RQ1/RQ2 → ML/NLP (a finding/curve). RQ3 + the workbench → HCI/systems (a tool + user study).
  Pick a lane per paper; don't serve both in one.

---

## 9. Risks & open questions
- **No single correct abstraction** for a prompt → metrics need annotator-agreement framing.
- **Model tool-calling reliability** (A2A path) varies by model; mitigated by the REST fallback.
- **Reuse is lexical, not semantic** — retrieval now exists (token-cosine), but a heavy
  paraphrase scores low; embedding-based matching is the next step (§5).
- **Prototype persistence** (in-memory + JSONL) is not production-grade.

## 10. Roadmap (phases)
1. **P0 (done):** the closed loop end-to-end (induce → MCP-app UI → run → correct → optimize),
   A2A + MCP exposure, Carbon host.
2. **P1 (done):** prompt-to-applet reuse (lexical retrieval), an induction-quality eval harness,
   and an offline pytest suite.
3. **P2:** the loop-ablation (RQ4) + model-scaling (RQ2) studies on top of the eval harness;
   semantic (embedding) retrieval; richer types.
4. **P3:** tool binding with a confirmation surface; metric-driven optimizers.

---

### References
- Concept & framing: [`idea.md`](idea.md), [`notes-1.md`](notes-1.md), [`notes-2.md`](notes-2.md)
- Critique that shaped the research framing: [`notes-3.md`](notes-3.md)
- Implementation: [`../README.md`](../README.md)
