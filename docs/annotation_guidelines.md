# Gold annotation guidelines

These guidelines define how to annotate a prompt for Prompt2App's evaluation set, so
that independent annotators produce comparable abstractions. Agreement between annotators
is then measured with `scripts/annotator_agreement.py` (issue #4).

## The task

Given a raw natural-language prompt, decide what a **reusable, parameterized program**
built from it should expose:

- **Input fields** — the values a user would change between runs (the knobs).
- **Output fields** — what the program produces.

You are recovering the prompt's *latent specification*, not tagging every noun. Ask: "if
someone ran this task repeatedly, what would they vary, and what would they get back?"

## Field types

Assign each field exactly one type from this closed set:

| Type | Use for | Example |
|---|---|---|
| `string` | short free text | a name, a title |
| `text` | long free text | an email body, an article |
| `integer` | whole number | quantity, number of replicas |
| `number` | decimal number | a rating, a ratio |
| `money` | a currency amount | a budget, a price |
| `date` | a calendar date | a deadline |
| `boolean` | yes/no | autoscaling on/off |
| `enum` | one of a fixed set of choices | tone, priority, environment |

Pick the **narrowest** type that fits: a budget is `money`, not `string`; a deadline is
`date`, not `string`; a priority with fixed levels is `enum`, not `string`.

## Conventions

- **Names** are `snake_case`, descriptive, and conventional (`max_budget`, not `mb` or
  `theMaximumBudgetAllowed`).
- **Inputs vs constraints.** A value the user varies is an input. A fixed task rule
  ("use a polite tone", "keep it under 200 words") is a *constraint*, not a field —
  unless the prompt clearly makes it a knob (e.g. tone is selectable). When unsure, prefer
  making something an input only if you can imagine a user changing it.
- **Granularity.** Prefer a few meaningful knobs over one-knob-per-word. Don't split a
  single concept (`recipient_first_name` + `recipient_last_name`) unless the task needs it.
- **Outputs** describe deliverables, not intermediate reasoning. An email task outputs
  `email_subject` and `email_body`, not `draft` and `final`.
- **Independence.** Annotate without looking at other annotators' work or the existing
  gold file. Disagreement is the signal we are measuring.

## Worked example

Prompt: *"Write a polite email to a supplier asking for a revised quote for 20 laptops,
under $30k, by Friday."*

```json
{
  "case_id": 1,
  "inputs": [
    {"name": "item", "type": "string"},
    {"name": "quantity", "type": "integer"},
    {"name": "max_budget", "type": "money"},
    {"name": "deadline", "type": "date"},
    {"name": "tone", "type": "enum"}
  ],
  "outputs": [
    {"name": "email_subject", "type": "string"},
    {"name": "email_body", "type": "text"}
  ]
}
```

## Submitting

Copy `data/eval/annotations/_template.jsonl` to `data/eval/annotations/<your-name>.jsonl`
and fill in the `inputs` and `outputs` for every case. Then run
`uv run python scripts/annotator_agreement.py` to see the agreement report. See the
[annotations README](../data/eval/annotations/README.md) for the file format.
