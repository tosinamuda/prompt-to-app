"""RQ4 loop-ablation study: does closing the feedback loop help?

Leave-one-out cross-validation over 8 gold cases. Each fold holds out 1 case
and uses the remaining 7 as human corrections (training data). Four conditions:

  - severed:   base inducer, no demonstrations — the loop is cut
  - fewshot:   gold corrections attached as LabeledFewShot demos
  - bootstrap: demos filtered through the induction metric (BootstrapFewShot)
  - gepa:      instructions rewritten by Sonnet reflection (GEPA)

Both gold-F1 metrics and the LLM judge (Sonnet) are reported per condition.

Usage:
    uv run python scripts/loop_ablation.py
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import dspy
from dotenv import load_dotenv

from prompt2app.claude_lm import make_lm
from prompt2app.evaluation import PRF, CaseScore, mean, score_case
from prompt2app.induction import SignatureInducer
from prompt2app.llm_judge import SchemaJudge, format_schema, judge_score
from prompt2app.schemas import AppSpec

load_dotenv()

CASES_PATH = Path(__file__).resolve().parents[1] / "data" / "eval" / "induction_cases.jsonl"

GOLD_META = [
    {"task_name": "generate_supplier_email", "title": "Supplier Quote Email",
     "description": "Generate a polite email to a supplier requesting a revised quote."},
    {"task_name": "draft_github_issue", "title": "GitHub Issue Draft",
     "description": "Draft a GitHub issue report for a software bug."},
    {"task_name": "create_deployment_request", "title": "K8s Deployment Request",
     "description": "Create a Kubernetes deployment request for a service."},
    {"task_name": "summarize_paper", "title": "Research Paper Summary",
     "description": "Summarize a research paper in bullet points for a target audience."},
    {"task_name": "generate_linkedin_post", "title": "LinkedIn Funding Post",
     "description": "Generate a professional LinkedIn post announcing a funding round."},
    {"task_name": "compare_products", "title": "Product Comparison Table",
     "description": "Create a comparison table for products across specified criteria."},
    {"task_name": "create_meal_plan", "title": "Weekly Meal Plan",
     "description": "Create a weekly meal plan with dietary constraints and budget."},
    {"task_name": "draft_cover_letter", "title": "Cover Letter Draft",
     "description": "Draft a cover letter tailored to a specific role and company."},
]

BASE_MODEL = "openrouter/openai/gpt-oss-120b"
REFLECTION_MODEL = "claude-cli/sonnet"
JUDGE_MODEL = "claude-cli/haiku"


def load_cases() -> list[dict]:
    lines = CASES_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def gold_to_example(case: dict, meta: dict) -> dspy.Example:
    return dspy.Example(
        raw_prompt=case["prompt"],
        task_name=meta["task_name"],
        title=meta["title"],
        description=meta["description"],
        input_parameters=case["gold"]["inputs"],
        program_outputs=case["gold"]["outputs"],
        constraints=[],
    ).with_inputs("raw_prompt")


def configure_lm() -> dspy.BaseLM:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    lm = dspy.LM(BASE_MODEL, temperature=0, api_key=api_key or None, cache=False)
    dspy.configure(lm=lm)
    return lm


def run_severed(test_case: dict) -> tuple[AppSpec | None, CaseScore | None]:
    inducer = SignatureInducer()
    try:
        app = inducer(test_case["prompt"])
        return app, score_case(app, test_case["gold"])
    except Exception as exc:
        print(f"    severed FAIL: {exc}")
        return None, None


def run_fewshot(
    train_examples: list[dspy.Example], test_case: dict,
) -> tuple[AppSpec | None, CaseScore | None]:
    optimizer = dspy.LabeledFewShot(k=len(train_examples))
    compiled = optimizer.compile(student=SignatureInducer(), trainset=train_examples)
    try:
        app = compiled(test_case["prompt"])
        return app, score_case(app, test_case["gold"])
    except Exception as exc:
        print(f"    fewshot FAIL: {exc}")
        return None, None


def run_bootstrap(
    train_examples: list[dspy.Example], test_case: dict,
) -> tuple[AppSpec | None, CaseScore | None]:
    from prompt2app.evaluation import induction_metric

    optimizer = dspy.BootstrapFewShot(
        metric=induction_metric,
        max_bootstrapped_demos=4,
        max_labeled_demos=4,
    )
    try:
        compiled = optimizer.compile(student=SignatureInducer(), trainset=train_examples)
    except Exception as exc:
        print(f"    bootstrap compile FAIL: {exc}")
        return None, None
    try:
        app = compiled(test_case["prompt"])
        return app, score_case(app, test_case["gold"])
    except Exception as exc:
        print(f"    bootstrap infer FAIL: {exc}")
        return None, None


def run_gepa(
    train_examples: list[dspy.Example], test_case: dict,
) -> tuple[AppSpec | None, CaseScore | None]:
    from prompt2app.evaluation import induction_metric_with_feedback

    n = len(train_examples)
    split = max(1, n // 4)
    val, train = train_examples[:split], train_examples[split:]

    reflection_lm = make_lm(REFLECTION_MODEL, max_thinking_tokens=4000)

    optimizer = dspy.GEPA(
        metric=induction_metric_with_feedback,
        reflection_lm=reflection_lm,
        max_metric_calls=50,
        num_threads=1,
        track_stats=True,
    )
    try:
        compiled = optimizer.compile(
            student=SignatureInducer(), trainset=train, valset=val,
        )
    except Exception as exc:
        print(f"    gepa compile FAIL: {exc}")
        return None, None
    try:
        app = compiled(test_case["prompt"])
        return app, score_case(app, test_case["gold"])
    except Exception as exc:
        print(f"    gepa infer FAIL: {exc}")
        return None, None


def zero_prf() -> PRF:
    return PRF(precision=0.0, recall=0.0, f1=0.0, tp=0, fp=0, fn=0)


def zero_score() -> CaseScore:
    return CaseScore(inputs=zero_prf(), outputs=zero_prf(), input_type_accuracy=0.0, valid=False)


def run_judge_batch(
    judge: SchemaJudge,
    cases: list[dict],
    condition_apps: dict[str, list[AppSpec | None]],
) -> dict[str, list[float]]:
    results: dict[str, list[float]] = {c: [] for c in condition_apps}
    for cond, apps in condition_apps.items():
        for case, app in zip(cases, apps, strict=True):
            if app is None:
                results[cond].append(0.0)
                continue
            try:
                pred = judge(
                    original_prompt=case["prompt"],
                    predicted_schema=format_schema(app),
                )
                sc = judge_score(pred)
                results[cond].append(sc)
                v = pred.verdict
                print(f"    {cond:10s} | {case['prompt'][:40]:40s} | "
                      f"var={v.captures_variable_parts} out={v.output_completeness} "
                      f"typ={v.type_precision} nam={v.field_naming} "
                      f"grn={v.right_granularity} -> {sc:.2f}")
            except Exception as exc:
                print(f"    judge FAIL {cond} {case['prompt'][:30]}… — {exc}")
                results[cond].append(0.0)
    return results


def main() -> None:
    cases = load_cases()
    n = len(cases)
    print(f"RQ4 loop-ablation — {n} cases, leave-one-out CV")
    print(f"base model: {BASE_MODEL}\n")

    configure_lm()

    conditions = ["severed", "fewshot", "bootstrap", "gepa"]
    fold_scores: dict[str, list[CaseScore]] = {c: [] for c in conditions}
    fold_apps: dict[str, list[AppSpec | None]] = {c: [] for c in conditions}

    t0 = time.time()
    for i in range(n):
        test_case = cases[i]
        train_cases = [c for j, c in enumerate(cases) if j != i]
        train_meta = [m for j, m in enumerate(GOLD_META) if j != i]
        train_examples = [
            gold_to_example(c, m) for c, m in zip(train_cases, train_meta, strict=True)
        ]

        prompt_short = test_case["prompt"][:55]
        print(f"{'─' * 70}")
        print(f"Fold {i + 1}/{n}  held-out: {prompt_short}…")

        # --- severed ---
        app_s, sc_s = run_severed(test_case)
        fold_scores["severed"].append(sc_s or zero_score())
        fold_apps["severed"].append(app_s)
        if sc_s:
            print(f"  severed    in_F1={sc_s.inputs.f1:.2f}  "
                  f"out_F1={sc_s.outputs.f1:.2f}  type={sc_s.input_type_accuracy}")

        # --- fewshot ---
        app_f, sc_f = run_fewshot(train_examples, test_case)
        fold_scores["fewshot"].append(sc_f or zero_score())
        fold_apps["fewshot"].append(app_f)
        if sc_f:
            print(f"  fewshot    in_F1={sc_f.inputs.f1:.2f}  "
                  f"out_F1={sc_f.outputs.f1:.2f}  type={sc_f.input_type_accuracy}")

        # --- bootstrap ---
        app_b, sc_b = run_bootstrap(train_examples, test_case)
        fold_scores["bootstrap"].append(sc_b or zero_score())
        fold_apps["bootstrap"].append(app_b)
        if sc_b:
            print(f"  bootstrap  in_F1={sc_b.inputs.f1:.2f}  "
                  f"out_F1={sc_b.outputs.f1:.2f}  type={sc_b.input_type_accuracy}")

        # --- gepa ---
        app_g, sc_g = run_gepa(train_examples, test_case)
        fold_scores["gepa"].append(sc_g or zero_score())
        fold_apps["gepa"].append(app_g)
        if sc_g:
            print(f"  gepa       in_F1={sc_g.inputs.f1:.2f}  "
                  f"out_F1={sc_g.outputs.f1:.2f}  type={sc_g.input_type_accuracy}")

    induction_elapsed = time.time() - t0
    print(f"\nInduction done in {induction_elapsed:.1f}s")

    # --- LLM judge ---
    print(f"\n{'─' * 70}")
    print(f"Running LLM judge ({JUDGE_MODEL})…")
    t1 = time.time()
    judge_lm = make_lm(JUDGE_MODEL, max_thinking_tokens=0)
    judge = SchemaJudge(judge_lm)
    judge_scores = run_judge_batch(judge, cases, fold_apps)
    judge_elapsed = time.time() - t1
    print(f"\nJudge done in {judge_elapsed:.1f}s")

    # --- summary table ---
    print(f"\n{'=' * 80}")
    print("LOOP-ABLATION RESULTS (RQ4)")
    print(f"{'=' * 80}")
    header = f"{'condition':<12}{'in_F1':>8}{'out_F1':>8}{'type_acc':>10}{'valid':>8}{'judge':>8}"
    print(header)
    print("─" * len(header))

    summary: list[dict] = []
    for cond in conditions:
        scores = fold_scores[cond]
        in_f1 = mean([s.inputs.f1 for s in scores])
        out_f1 = mean([s.outputs.f1 for s in scores])
        type_acc = mean([s.input_type_accuracy for s in scores
                         if s.input_type_accuracy is not None])
        validity = mean([1.0 if s.valid else 0.0 for s in scores])
        j_mean = mean(judge_scores[cond])

        print(f"{cond:<12}{in_f1:>8.2f}{out_f1:>8.2f}{type_acc:>10.2f}"
              f"{validity:>8.2f}{j_mean:>8.2f}")
        summary.append({
            "condition": cond, "in_f1": round(in_f1, 3), "out_f1": round(out_f1, 3),
            "type_acc": round(type_acc, 3), "validity": round(validity, 3),
            "judge": round(j_mean, 3),
        })

    # --- per-fold delta tables ---
    def _sign(x: float) -> str:
        return f"+{x:.2f}" if x >= 0 else f"{x:.2f}"

    for cond in ["fewshot", "bootstrap", "gepa"]:
        print(f"\nPer-fold Δ ({cond} − severed):")
        print(f"{'fold':<6}{'Δin_F1':>8}{'Δout_F1':>9}{'Δtype':>8}{'Δjudge':>8}")
        print("─" * 39)
        for i in range(n):
            s = fold_scores["severed"][i]
            c = fold_scores[cond][i]
            d_in = c.inputs.f1 - s.inputs.f1
            d_out = c.outputs.f1 - s.outputs.f1
            d_type = ((c.input_type_accuracy or 0) - (s.input_type_accuracy or 0))
            d_judge = judge_scores[cond][i] - judge_scores["severed"][i]
            print(f"{i + 1:<6}{_sign(d_in):>8}{_sign(d_out):>9}"
                  f"{_sign(d_type):>8}{_sign(d_judge):>8}")

    # --- save ---
    out_path = Path(__file__).resolve().parents[1] / "data" / "eval" / "ablation_results.json"
    out_data = {
        "model": BASE_MODEL,
        "n_cases": n,
        "cv": "leave-one-out",
        "summary": summary,
        "per_fold": {
            cond: [
                {
                    "in_f1": round(s.inputs.f1, 3),
                    "out_f1": round(s.outputs.f1, 3),
                    "type_acc": round(s.input_type_accuracy, 3)
                    if s.input_type_accuracy is not None else None,
                    "judge": round(judge_scores[cond][i], 3),
                }
                for i, s in enumerate(fold_scores[cond])
            ]
            for cond in conditions
        },
    }
    out_path.write_text(json.dumps(out_data, indent=2), encoding="utf-8")
    print(f"\nResults saved to {out_path}")
    print(f"Total time: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
