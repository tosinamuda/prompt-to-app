# Research positioning

Validated against the literature on 2026-07-07 (web survey of the PBE/synthesis, HCI
prompt-interface, and prompt-optimization traditions, including 2025–2026 venues). This
document is the thesis's north star: what the contribution is, what it is not, and how
each research question sits against prior work.

## Contribution statement

> **Latent specification recovery:** a one-off natural-language prompt implicitly
> specifies a reusable task — inputs the author would vary between runs, typed outputs,
> and fixed constraints. We formalize recovering that specification as a measurable
> induction task, show it is *itself an optimization task* that human field-level
> corrections can iteratively improve, and characterize the central design choice —
> how finely to parameterize — as a dual-axis tradeoff with an interior optimum.

The generated form UI, the MCP/A2A serving stack, and the retrieval-based reuse are the
**instrument**, not the contribution. They exist so the loop is real rather than
simulated: a correction is a concrete edit to a rendered field, and an induced signature
is accepted only if it compiles to a runnable program.

## Instrument vs object — why this is research, not engineering

The workflow (induce → compile → render → correct → optimize) is engineering. The
science is four falsifiable questions **about the induction problem**, each answered by
measurement on the instrument:

| RQ | Question about the problem | Falsifiable claim tested |
|---|---|---|
| RQ1 | Is the latent specification recoverable at all? | Induced signatures match human-annotated gold above chance (field P/R/F1, type accuracy, validity) |
| RQ2 | Is recovery a capability that scales? | Quality rises monotonically with model tier; structure's value vs raw prompting shrinks or persists |
| RQ3 | What governs how finely to parameterize? | Quality and reuse are **not** monotone in field count — both have an interior optimum |
| RQ4 | Is induction an *improvable* task? | A metric + human corrections form a training signal that lifts held-out induction quality at realistic correction budgets |

Anything in the repo not needed to answer these four questions is explicitly out of the
thesis claims (Carbon host, A2A agent wiring, app store, retrieval reuse).

## The seam, against prior work

Every ingredient exists in isolation; the combination — *typed* signature induction with
reuse-across-runs semantics, compiled into an optimizable program, with corrections as
supervision — is unclaimed as of this survey.

| Cluster | Representative work | What it does | What it lacks |
|---|---|---|---|
| Prompt → widgets (in-situ) | [Malleable Prompting, UIST 2026](https://arxiv.org/abs/2604.10925); [Dynamic Prompt Middleware, CHIWORK 2025](https://doi.org/10.1145/3729176.3729203); [PromptCanvas](https://arxiv.org/abs/2506.03741); [BISCUIT, VL/HCC 2024](https://arxiv.org/abs/2404.07387); [AI-Instruments, CHI 2025](https://dl.acm.org/doi/10.1145/3706598.3714259) | Reify prompt spans / preferences as GUI controls for one generation | Style knobs, not run-varying I/O; ephemeral; untyped outputs; no compiled program; no learning loop |
| Prompt → deployable artifact | [Prompt2Model, EMNLP 2023](https://arxiv.org/abs/2308.12261); Google Opal (2025) | Prompt to trained model / step workflow with generic UI | No typed field induction; artifact is a model or step graph, not a parameterized prompt program; no correction loop |
| Prompt → task-driven UI | [Jelly — Generative & Malleable UIs, CHI 2025](https://arxiv.org/abs/2503.04084) | Parses a task description into a data model and generates malleable UIs | UI is the artifact; no typed outputs/constraints; no optimizer; no granularity experiment |
| Schema-first LLM programming | [TypeChat](https://github.com/microsoft/TypeChat), instructor, BAML, DSPy signatures | Validate LLM output against a **hand-written** schema | Inverse direction — the schema is authored, never induced |
| Spec extraction from prompts | [PromptPex, 2025](https://arxiv.org/abs/2503.05070) | Extracts checkable I/O rules from a prompt to generate tests | Rules for testing, not a reusable typed parameterization; no UI/loop |
| Template corpora | [From Prompts to Templates, FSE 2025](https://arxiv.org/abs/2504.02052) | Mines placeholder taxonomies from 2,163 real LLM-app templates | Descriptive; templates are hand-parameterized |

Differentiating axes to state explicitly: (1) parameters are defined *counterfactually*
(what a user would vary across future runs), not stylistically; (2) a domain type system
(`money/date/enum/…`) with typed **outputs** and constraints, not categorical/numeric
style attributes; (3) the induced signature compiles to an optimizable DSPy program;
(4) field-level corrections are supervision, not just edits.

## RQ3 — granularity (the headline)

The tension is old; the measurement is new. Prior traditions each see one axis:

- **PBE generalization ranking** — [Singh & Gulwani, CAV 2015](https://people.csail.mit.edu/rishabh/papers/cav15-ranking.pdf);
  [FlashProfile, OOPSLA 2018](https://arxiv.org/pdf/1709.05725): "how general should the
  induced program be?", collapsed into held-out accuracy or a fixed cost function.
- **Library-level LLM abstraction induction** — [TroVE, ICML 2024](https://arxiv.org/abs/2401.12869);
  [ReGAL, ICML 2024](https://arxiv.org/pdf/2401.16467); [LILO, ICLR 2024](https://arxiv.org/abs/2310.19791):
  accuracy + toolbox size/reuse, but granularity is emergent, never a controlled knob,
  and never per-template parameter count.
- **Slot-schema induction** (NAACL 2022) and **email template mining** (WWW 2017):
  quality vs gold only.
- **Form/API usability** (NN/g field-count studies; Stylos & Myers API parameters):
  monotone "fewer is better" pressure on a single axis.

**RQ3's novel cell:** treat parameter count of an LLM-induced template as a controlled
experimental variable and measure BOTH schema quality AND reuse coverage over realistic
rephrasings. Measured result (8 tasks × 5 levels, gpt-oss-120b): both axes peak
interiorly at ~4 fields; over-decomposition *renames and splits canonical knobs*, so
reuse falls too — the naive "more fields → more flexibility" intuition fails.

**Lead with the reuse interior optimum.** The quality peak is partly entangled with
gold schemas averaging ~4 fields (a slot-induction-style metric artifact); the judge and
reuse axes are gold-independent. A robustness check (report the curve excluding gold-F1;
per-case gold-size stratification) is required before the quality-peak claim is made.

## RQ4 — reframed: induction as an optimization task

**Not an optimizer bake-off.** GEPA and MIPROv2 are interchangeable policies; the claim
being tested is that *signature induction admits iterative improvement*: a decomposable
metric (field F1 + type accuracy + validity, with textual feedback) plus field-level
human corrections form a supervision signal, and the question is how much held-out
induction quality each additional correction buys, under which supervision regime.

What the current data supports (consistent with published results):

- At a realistic tiny correction budget (7 corrections/fold, ~50 metric calls),
  **metric-validated demonstrations** (BootstrapFewShot 0.88) beat both no-loop (0.82)
  and instruction evolution (GEPA 0.79) — reproducing the
  [MIPROv2 ablations](https://arxiv.org/abs/2406.11695) (demos > instructions on most
  tasks) and official DSPy guidance (~10 examples → BootstrapFewShot).
- The GEPA cell ran far outside its documented envelope
  ([GEPA, ICLR 2026](https://arxiv.org/abs/2507.19457): 150 train / 300 val,
  2,270–6,926 rollouts; ours: 5–6 train, 1–2 val, 50 calls — and the DSPy docs warn a
  tiny valset "makes GEPA overfit prompts to the provided trainset"). So the honest
  claim is a **budget-regime** finding, not "instruction evolution fails".

Revised hypothesis ranking for the diagnosis (was H1 > H2 > H3):

1. **H2 — selection starvation / overfitting (strongest).** No meaningful valset for
   Pareto selection; supported by DSPy's own docs and
   [non-vacuous generalization bounds for prompt optimization](https://arxiv.org/abs/2510.08413)
   (unregularized instruction search on scarce data overfits).
2. **H3′ — train-specific content, not raw length.** Rescoped:
   [IFScale](https://arxiv.org/abs/2507.11538) shows reasoning-class executors tolerate
   100+ instructions, so length alone is unlikely; the harmful thing is fold-specific
   memorized content (measurable: gold field names leaking into evolved instructions).
3. **H1 — reflection-executor gap (weakest as stated).** Strong-reflector/weak-executor
   is the *recommended* GEPA configuration; candidates are scored on the executor, so
   unfollowable instructions are filtered — given enough budget. H1 survives only as
   "capability gap × tiny-budget selection noise". Prompt-transfer evidence:
   [Rethinking Prompt Optimizers, 2025](https://arxiv.org/html/2505.09930v1).

Revised protocol (issue #2): arm A = budget-constrained loop (existing result); arm B =
proper-config GEPA (feedback-returning metric, explicit valset, several hundred calls);
arm C = bootstrap at matched budgets. Deliverable: **improvement-per-correction curves**
per regime, plus the H2/H3′ instrumentation (valset ablation; leak analysis). Result
either way is publishable: "corrections buy improvement cheaply via demos; instruction
evolution needs ≥N-correction budgets to pay off".

## Signature-level findings (supporting, consistent with literature)

- Lean 253-char docstring ≈/> detailed 1339-char on judge (0.86 vs 0.81) — consistent
  with MIPROv2's "detailed instructions pay off only for non-obvious conditional rules".
- Predict ≈ ChainOfThought for induction — consistent with
  [To CoT or not to CoT, ICLR 2025](https://arxiv.org/abs/2409.12183) (gains concentrate
  in math/symbolic tasks). CoT conditions are low-value future spend.
- The gold-F1 vs judge **ordering flip** (detailed wins F1, lean wins judge) is a metric
  red flag → resolved by human adjudication (issue #4) before either metric backs a claim.

## Methodology hardening (reviewer risks → fixes)

| # | Risk | Norm | Fix (issue) |
|---|---|---|---|
| 1 | Single run, no variance; n=8 paired sign test needs 8/8 for p<.05 | [Show Your Work, EMNLP 2019](https://aclanthology.org/D19-1224/); [Adding Error Bars to Evals](https://arxiv.org/abs/2411.00640) | ≥5 seeds/condition, paired per-case deltas, permutation/sign tests, 95% CIs |
| 2 | GEPA outside operating envelope | GEPA paper budgets/valsets | Proper-config arm (issue #2 revised) |
| 3 | 8 gold cases vs field norms 24–300 | Instruction Induction (ACL 2023) uses 24 tasks | Expand to ≥15 now, ≥24 target (issue #6 → critical path) |
| 4 | Same-family judge (sonnet reflector, claude judge) | [Preference leakage, ICML 2025](https://arxiv.org/abs/2502.01534); [self-preference, NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/hash/7f1f0218e45f5414c79c0679633e47bc-Abstract-Conference.html) | Cross-family judge panel ([PoLL](https://arxiv.org/abs/2404.18796)) + human calibration on disagreements. Note: bias direction *favors* GEPA, strengthening the RQ4 direction |
| 5 | Metric divergence (F1 vs judge) | [State of What Art?, TACL 2024](https://aclanthology.org/2024.tacl-1.52/): rankings flip across paraphrases | Human adjudication; report both metrics + agreement; ≥3 docstring paraphrases per condition |
| 6 | Dev-set reuse (iterating on the same 8 cases) | Held-out final test is standard | Freeze new gold cases (issue #6) as a never-touched test slice |

## One-paragraph defense against "it's just engineering"

The system is to this thesis what a telescope is to astronomy: necessary, non-trivial to
build, and not the discovery. The discoveries are measurements the instrument makes
possible — that latent specifications are recoverable (RQ1), that recovery scales with
capability but structure retains value (RQ2), that parameterization granularity has a
measurable dual-axis interior optimum (RQ3, headline), and that induction quality is
iteratively improvable from human corrections, with the supervision regime that pays off
depending on correction budget (RQ4). Each is falsifiable, none is a pipeline feature,
and all four survive against the four literatures they respectively touch.
