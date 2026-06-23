# Evaluation data

The gold annotations, task variants, and result files behind the research experiments.

## Files

| File | Role |
|---|---|
| `induction_cases.jsonl` | The **validated** gold set (8 cases). Each line: `{prompt, gold: {inputs, outputs}}`. Backs RQ1/RQ2/RQ3/RQ4. |
| `induction_cases_candidates.jsonl` | **Draft** new cases (7) awaiting inter-annotator validation before promotion (issue #6). Each line also carries `task_name`/`title`/`description`. |
| `reuse_variants.jsonl` | Realistic rephrasings per case with `required_inputs`, for the RQ3 reuse-coverage metric. |
| `annotations/` | Independent per-annotator gold annotations for inter-annotator agreement (issue #4). See its README. |
| `scaling_results.json` | RQ2 output (model-scaling). |
| `ablation_results.json` | RQ4 output (loop ablation). |
| `granularity_results.json` | RQ3 output (parameterization granularity). |

## Promoting candidate cases (issue #6)

The 7 cases in `induction_cases_candidates.jsonl` are drafts. Before they join the
validated set:

1. Have ≥2 people annotate them independently (see `annotations/`) and confirm
   agreement with `scripts/annotator_agreement.py`.
2. Reconcile any disagreements into a consensus gold.
3. Append the reconciled `{prompt, gold}` lines to `induction_cases.jsonl` and add each
   `{task_name, title, description}` to `GOLD_META` in `scripts/loop_ablation.py`.
4. Re-run the affected experiments so results reflect the expanded set.

Keeping drafts separate means the published RQ results stay tied to the validated 8 cases
until the expansion is reviewed.
