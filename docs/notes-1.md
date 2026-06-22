Yes. There is research here, but the novelty is **not** “use an LLM to extract entities and make a form.” That alone is now too shallow. The research starts when you treat the prompt as a **latent application specification** and study whether an LLM system can compile that intent into a reusable, optimized, tool-bound interface.

A strong framing would be:

> **Can natural-language prompts be compiled into reusable, self-optimizing form applications that improve task completion, correctness, and user control compared with static forms or chat-only interfaces?**

## The core idea

Your old idea was:

> User prompt → LLM extracts entities → generated reusable form

The stronger 2026 version is:

> User prompt → infer task intent, entities, constraints, missing information, output schema, and tool affordances → generate an adaptive form/UI → bind it to tools or MCP apps → optimize the extraction and UI strategy from user corrections and downstream task success.

DSPy makes this more interesting because its signatures are declarative input/output behavior specifications, not just prompt strings, and its optimizers can tune program parameters against metrics you define. That gives you a path to move from “prompt engineering” to a measurable, optimizable pipeline. ([DSPy][1])

MCP makes it more interesting because it gives the system a protocol-level way to discover and call tools, resources, prompts, and user-elicitation flows. In other words, the generated form does not have to be cosmetic. It can become the safe interaction layer between natural language and executable actions. ([Model Context Protocol][2])

Generative UI also matters because current systems can connect model tool calls to rendered interface components, rather than only returning text. The Vercel AI SDK, for example, describes generative UI as connecting tool-call results to React components. ([AI SDK][3]) Recent research on “Generative Interfaces” also frames LLMs as systems that can proactively generate adaptive task-specific UIs instead of static chat responses. ([arXiv][4])

## Where the research is

The research is in **intent-to-interface compilation**.

You are not just extracting `name`, `date`, `location`, or `budget`. You are asking:

1. What task is the user trying to perform?
2. What entities are already present?
3. What fields are missing?
4. Which fields are required, optional, dependent, or inferred?
5. Which validation rules apply?
6. What output schema should the system produce?
7. Which tool, API, MCP server, or workflow should this connect to?
8. What UI is best for collecting the missing information?
9. How should the system learn from user corrections?
10. Can the generated app be reused for future similar prompts?

That is a legitimate research problem because it combines **information extraction, schema induction, program synthesis, HCI, tool-use safety, and optimization**.

## What could be novel

The strongest novelty would be one or more of these.

### 1. Dynamic signature induction

DSPy signatures normally specify the expected input/output behavior of an LM module. Your research could investigate whether the system can **infer those signatures automatically** from natural-language prompts, tool descriptions, previous user corrections, and domain context.

Example:

User says:

> “Help me create a vendor onboarding request for a Nigerian fintech supplier.”

The system infers a signature like:

```text
Input:
- user_request
- organization_policy_context
- available_tools

Output:
- vendor_onboarding_form_schema
- required_fields
- optional_fields
- validation_rules
- tool_binding
- missing_information_questions
```

The research question becomes:

> **How accurately can LLMs infer task-specific input/output signatures from natural-language intent and tool metadata?**

That is more novel than using a static schema.

### 2. Self-optimizing form generation

A basic generated form is not enough. The research gets stronger if the form improves over time.

For example, the system notices that users often correct “company size,” “region,” or “payment terms” fields. The optimizer then adjusts the extraction prompt, validation logic, field ordering, or clarification strategy.

DSPy is relevant because optimizers can tune prompts, examples, or LM weights against a metric. ([DSPy][5]) Your contribution could define metrics beyond extraction accuracy:

```text
Metric = 
  tool_call_validity
+ entity_extraction_accuracy
+ user_completion_rate
- correction_count
- hallucinated_fields
- unnecessary_questions
- time_to_completion
```

Research question:

> **Can downstream interaction metrics optimize prompt-to-form systems better than traditional extraction-only metrics such as entity F1?**

That is a strong angle.

### 3. Form as a safety boundary for tool use

This may be the most practical research contribution.

LLM agents often jump from prompt to tool call too quickly. A generated form can act as an intermediate verification layer.

Instead of:

```text
Prompt → tool call
```

You get:

```text
Prompt → extracted intent → generated form → user verification → validated tool call
```

With MCP, this becomes especially relevant because tools can expose executable capabilities, and MCP explicitly supports tools, resources, prompts, and elicitation. ([Model Context Protocol][2])

Research question:

> **Can generated forms reduce invalid, unsafe, or hallucinated tool calls in LLM-agent workflows?**

That is not just engineering. That is agent safety, UX, and systems research.

### 4. Reusable prompt-derived applications

Most generative UI work is transient: the model generates an interface for the current interaction. Your angle could be that the generated form becomes a **persistent reusable applet**.

For example:

```text
"Create a request for GPU access"
```

becomes a reusable internal tool:

```text
GPU Access Request App
- project name
- business justification
- cloud provider
- GPU type
- duration
- budget center
- approval chain
- generated ticket/tool call
```

The next time someone asks a similar thing, the system does not start from scratch. It retrieves, adapts, and optimizes the applet.

Research question:

> **Can natural-language prompts be compiled into reusable micro-applications that generalize across similar future tasks?**

That is a stronger claim than “dynamic form generation.”

### 5. Joint optimization of schema, UI, and tool binding

Most systems optimize only one layer:

```text
Extraction only
UI generation only
Tool calling only
```

Your research could optimize all three together:

```text
Natural language understanding
+ schema induction
+ generated UI
+ validation
+ tool execution
+ user feedback
```

This is where the work becomes novel.

Research question:

> **How can an LLM system jointly optimize extracted schemas, interface layouts, and tool bindings from user feedback and execution outcomes?**

This is a clean research direction.

## A good thesis-style framing

Use this framing:

> **Self-Optimizing Intent-to-Form Compilers for LLM Tool Use**

Or:

> **Prompt-to-Form: Compiling Natural Language Intent into Reusable, Tool-Bound User Interfaces**

Or:

> **Adaptive Form Synthesis from Natural Language for Safer LLM Tool Execution**

The strongest research question:

> **Can LLMs compile natural-language user intent into reusable, self-optimizing form applications that improve structured data capture and tool execution compared with chat-only, static-form, and one-shot generated-UI baselines?**

That question is measurable, comparative, and broad enough for research.

## Possible system architecture

A clean architecture could look like this:

```text
1. User prompt
   ↓
2. Intent and entity extractor
   - task type
   - entities
   - constraints
   - missing slots
   ↓
3. Signature synthesizer
   - input schema
   - output schema
   - validation rules
   - confidence scores
   ↓
4. Form compiler
   - JSON Schema / Zod schema
   - UI schema
   - field dependencies
   - default values
   - clarification prompts
   ↓
5. Generative UI renderer
   - React components
   - form layout
   - review screen
   ↓
6. MCP/tool binder
   - maps form output to tool/API calls
   - validates before execution
   ↓
7. Feedback loop
   - user corrections
   - failed tool calls
   - completion metrics
   ↓
8. DSPy optimizer
   - improves extraction
   - improves signatures
   - improves clarification strategy
```

The artifact is not just a form. It is a **compiler pipeline**.

## What to evaluate

You can compare four systems:

| System              | Description                                                                      |
| ------------------- | -------------------------------------------------------------------------------- |
| Chat-only assistant | User interacts only through conversation                                         |
| Static tool form    | Hand-designed form from a fixed schema                                           |
| One-shot LLM form   | LLM generates a form once with no optimization                                   |
| Your system         | Dynamic signature induction, generated form, tool binding, feedback optimization |

Measure:

| Metric                     | What it tells you                                       |
| -------------------------- | ------------------------------------------------------- |
| Entity extraction accuracy | Did the system identify the right fields?               |
| Schema validity            | Did it produce a usable input/output schema?            |
| Missing-field detection    | Did it ask for the right missing information?           |
| Tool-call validity         | Did the final action execute correctly?                 |
| User correction count      | How much fixing did the user need to do?                |
| Completion time            | Did the interface make the task faster?                 |
| Reuse success              | Does the generated app work for similar future prompts? |
| Hallucinated field rate    | Did the system invent fields that do not belong?        |
| User preference            | Do users prefer it over chat or static forms?           |

This gives you empirical substance.

## Best domains to test

Use domains with structured workflows and real consequences, but not too much regulatory overhead at first.

Good candidates:

| Domain                       | Why it works                                                 |
| ---------------------------- | ------------------------------------------------------------ |
| Internal enterprise requests | Access requests, procurement, onboarding, approvals          |
| Cloud operations             | Deployment requests, incident reports, resource provisioning |
| Developer workflows          | GitHub issue creation, PR review forms, bug reports          |
| CRM/business ops             | Lead capture, customer escalation, support triage            |
| Data collection              | Research intake forms, survey creation, annotation tasks     |
| AI agent tools               | Tool-call confirmation forms for MCP agents                  |

Given your background, **cloud/dev tooling** is probably the best area. Example:

> “From a developer’s natural-language request, generate an optimized form that captures the required fields for a cloud-native deployment workflow and binds the result to an MCP tool or API.”

That is concrete and aligned with your engineering profile.

## What not to claim as novel

Do not claim these as the main novelty:

```text
LLMs can extract entities.
LLMs can generate forms.
LLMs can generate React components.
LLMs can call tools.
LLMs can use schemas.
```

Those are known.

Claim novelty around:

```text
Automatic signature induction
Closed-loop optimization of form generation
Reusable prompt-derived applets
Tool-bound form compilation
Form-based safety layer for agent actions
Joint optimization of extraction, UI, and execution
Benchmarking prompt-to-form systems
```

That is defensible.

## A sharper research contribution statement

You could write it like this:

> This work proposes a self-optimizing prompt-to-form compiler that transforms natural-language user intent into reusable, validated, tool-bound form applications. Unlike static form builders or chat-only agents, the system induces task-specific input/output signatures, generates adaptive forms, binds form outputs to executable tools through protocols such as MCP, and optimizes extraction and clarification behavior using downstream task-success metrics.

That sounds like research.

## Possible paper abstract

> Large language models can interpret natural-language requests, but chat-based interfaces are inefficient for tasks requiring structured data capture, validation, and tool execution. We introduce Prompt-to-Form, a system that compiles natural-language intent into reusable, tool-bound form applications. The system induces input/output signatures, extracts entities and constraints, generates adaptive form schemas, binds validated outputs to external tools, and optimizes its behavior from user corrections and execution outcomes. We evaluate Prompt-to-Form against chat-only assistants, static forms, and one-shot generated interfaces across enterprise workflow tasks. Results assess schema accuracy, tool-call validity, user correction burden, completion time, and reuse performance. The work frames generated forms as an intermediate safety and control layer for LLM tool use.

## Strongest final research question

Use this:

> **How can LLM systems automatically induce, optimize, and reuse form-based interfaces from natural-language prompts to improve structured data capture and safe tool execution?**

Or the more empirical version:

> **Do self-optimizing prompt-to-form systems reduce user effort and invalid tool calls compared with chat-only agents, static forms, and one-shot generated UIs?**

The second one is better for a paper because it is testable.

## My read

There is real research here if you avoid building “another AI form generator.” The interesting contribution is a **self-improving interface compiler for LLM agents**.

The form is not the product. The form is the **control surface** between ambiguous human intent and deterministic tool execution.

[1]: https://dspy.ai/learn/programming/signatures/ "Signatures - DSPy"
[2]: https://modelcontextprotocol.io/specification/2025-06-18 "Specification - Model Context Protocol"
[3]: https://ai-sdk.dev/docs/ai-sdk-ui/generative-user-interfaces "AI SDK UI: Generative User Interfaces"
[4]: https://arxiv.org/html/2508.19227v3 "Generative Interfaces for Language Models"
[5]: https://dspy.ai/learn/optimization/optimizers/ "Optimizers - DSPy"
