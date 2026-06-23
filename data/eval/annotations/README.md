# Annotations

Independent gold annotations, one JSONL file per annotator, used to measure
inter-annotator agreement (issue #4). See [docs/annotation_guidelines.md](../../../docs/annotation_guidelines.md)
for how to annotate.

## How to contribute an annotation set

1. Copy `_template.jsonl` to `<your-name>.jsonl` (files starting with `_` are ignored).
2. For each line (one per case), fill in `inputs` and `outputs` — each a list of
   `{"name": "snake_case", "type": "<one of the 8 types>"}`.
3. Do **not** look at other annotators' files or `../induction_cases.jsonl` first.
4. Run `uv run python scripts/annotator_agreement.py`.

## File format

Each line is one case:

```json
{"case_id": 1, "inputs": [{"name": "item", "type": "string"}], "outputs": [{"name": "email_body", "type": "text"}]}
```

`case_id` aligns annotators to the same prompt (see `_template.jsonl` for the prompts).
All annotator files must cover the same set of `case_id`s.

## Agreement

With 2 annotators the script reports Cohen's kappa; with 3+ it reports Fleiss' kappa, for
both field existence and field type. Target: substantial (κ > 0.6) on existence. If
agreement is low, the gold annotations should be revised toward consensus before the
F1-based metrics are trusted.
