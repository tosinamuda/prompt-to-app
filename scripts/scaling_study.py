"""RQ2 model-scaling study: does the value of induced structure shrink with model capability?

Runs the induction eval across multiple model tiers and prints a comparison table.
Uses Haiku as the frontier tier and Sonnet as an independent LLM judge (so Sonnet
never evaluates its own output).

Two metric axes:
  1. Gold-F1: field name matching (exact + semantic) against gold annotations
  2. Judge: Sonnet rates schema quality on a 4-dimension rubric (1-5 each)

Usage:
    uv run python scripts/scaling_study.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import dspy
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prompt2app.claude_lm import make_lm
from prompt2app.evaluation import CaseScore, mean, score_case
from prompt2app.induction import SignatureInducer
from prompt2app.llm_judge import SchemaJudge, format_schema, judge_score
from prompt2app.schemas import AppSpec

CASES_PATH = Path(__file__).resolve().parents[1] / "data" / "eval" / "induction_cases.jsonl"

MODELS = [
    ("8B",    "openrouter/meta-llama/llama-3.1-8b-instruct"),
    ("70B",   "openrouter/meta-llama/llama-3.3-70b-instruct"),
    ("120B",  "openrouter/openai/gpt-oss-120b"),
    ("front", "claude-cli/haiku"),
]


def load_cases() -> list[dict]:
    lines = CASES_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def run_tier(
    model_id: str, cases: list[dict], *, verbose: bool = False,
) -> tuple[list[CaseScore], list[AppSpec | None]]:
    if model_id.startswith("claude-cli/"):
        lm = make_lm(model_id, max_thinking_tokens=0)
    else:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        lm = dspy.LM(model_id, temperature=0, api_key=api_key or None, cache=False)
    dspy.configure(lm=lm)
    inducer = SignatureInducer()

    scores: list[CaseScore] = []
    apps: list[AppSpec | None] = []
    for case in cases:
        try:
            app: AppSpec = inducer(case["prompt"])
            sc = score_case(app, case["gold"])
            scores.append(sc)
            apps.append(app)
            if verbose:
                _print_case_detail(case, app, sc)
        except Exception as exc:
            print(f"  FAIL on {case['prompt'][:50]}… — {exc}")
            scores.append(CaseScore(
                inputs=_zero_prf(), outputs=_zero_prf(),
                input_type_accuracy=0.0, valid=False,
            ))
            apps.append(None)
    return scores, apps


def run_judge(
    judge: SchemaJudge, cases: list[dict], tier_apps: dict[str, list[AppSpec | None]],
) -> dict[str, dict]:
    """Run the Sonnet judge on all tiers' outputs, return tier→{mean, dims, per_case}."""
    tier_results: dict[str, dict] = {}
    dims = [
        "captures_variable_parts", "output_completeness",
        "type_precision", "field_naming", "right_granularity",
    ]
    for tier, apps in tier_apps.items():
        case_scores: list[float] = []
        dim_totals = {d: 0.0 for d in dims}
        n_scored = 0
        for case, app in zip(cases, apps):
            if app is None:
                case_scores.append(0.0)
                continue
            try:
                pred = judge(
                    original_prompt=case["prompt"],
                    predicted_schema=format_schema(app),
                )
                sc = judge_score(pred)
                case_scores.append(sc)
                v = pred.verdict
                for d in dims:
                    dim_totals[d] += getattr(v, d)
                n_scored += 1
                print(f"  {tier} | {case['prompt'][:45]:45s} | "
                      f"var={v.captures_variable_parts} out={v.output_completeness} "
                      f"typ={v.type_precision} nam={v.field_naming} "
                      f"grn={v.right_granularity} → {sc:.2f}")
            except Exception as exc:
                print(f"  Judge FAIL on tier={tier} {case['prompt'][:40]}… — {exc}")
                case_scores.append(0.0)
        dim_means = {d: dim_totals[d] / n_scored if n_scored else 0 for d in dims}
        tier_results[tier] = {"mean": mean(case_scores), "dims": dim_means}
    return tier_results


def _print_case_detail(case: dict, app: AppSpec, sc: CaseScore) -> None:
    gold = case["gold"]
    gold_in = sorted(f["name"] for f in gold.get("inputs", []))
    gold_out = sorted(f["name"] for f in gold.get("outputs", []))
    pred_in = sorted(f.name for f in app.inputs)
    pred_out = sorted(f.name for f in app.outputs)
    print(f"  prompt: {case['prompt'][:60]}…")
    print(f"    gold_in:  {gold_in}")
    print(f"    pred_in:  {pred_in}")
    print(f"    gold_out: {gold_out}")
    print(f"    pred_out: {pred_out}")
    print(f"    in_F1={sc.inputs.f1:.2f}  out_F1={sc.outputs.f1:.2f}  "
          f"type_acc={sc.input_type_accuracy}")


def _zero_prf():
    from prompt2app.evaluation import PRF
    return PRF(precision=0.0, recall=0.0, f1=0.0, tp=0, fp=0, fn=0)


def main() -> None:
    cases = load_cases()
    print(f"cases = {len(cases)}   models = {len(MODELS)}\n")

    results: list[dict] = []
    tier_apps: dict[str, list[AppSpec | None]] = {}

    for tier, model_id in MODELS:
        print(f"{'─' * 60}")
        print(f"Running tier={tier}  model={model_id}")
        t0 = time.time()
        scores, apps = run_tier(model_id, cases, verbose=(tier == "front"))
        elapsed = time.time() - t0
        tier_apps[tier] = apps

        in_f1 = mean([s.inputs.f1 for s in scores])
        out_f1 = mean([s.outputs.f1 for s in scores])
        type_acc = mean([s.input_type_accuracy for s in scores
                         if s.input_type_accuracy is not None])
        validity = mean([1.0 if s.valid else 0.0 for s in scores])

        results.append({
            "tier": tier,
            "model": model_id,
            "in_f1": in_f1,
            "out_f1": out_f1,
            "type_acc": type_acc,
            "validity": validity,
            "time_s": round(elapsed, 1),
        })
        print(f"  in_F1={in_f1:.2f}  out_F1={out_f1:.2f}  "
              f"type_acc={type_acc:.2f}  valid={validity:.2f}  "
              f"({elapsed:.1f}s)\n")

    print(f"\n{'─' * 60}")
    print("Running LLM judge (Sonnet via claude -p)…")
    t0 = time.time()
    judge_lm = make_lm("claude-cli/sonnet", max_thinking_tokens=0)
    judge = SchemaJudge(judge_lm)
    judge_results = run_judge(judge, cases, tier_apps)
    judge_elapsed = time.time() - t0
    print(f"\n  Judge done in {judge_elapsed:.1f}s")

    for r in results:
        jr = judge_results.get(r["tier"], {"mean": 0.0, "dims": {}})
        r["judge"] = round(jr["mean"], 3)
        r["judge_dims"] = {k: round(v, 2) for k, v in jr.get("dims", {}).items()}

    print(f"\n{'=' * 92}")
    print("MODEL-SCALING COMPARISON (RQ2)")
    print(f"{'=' * 92}")
    header = (f"{'tier':<8}{'in_F1':>8}{'out_F1':>8}{'type_acc':>10}"
              f"{'valid':>8}{'judge':>8}{'time':>8}  model")
    print(header)
    print("─" * len(header) + "─" * 30)
    for r in results:
        print(f"{r['tier']:<8}{r['in_f1']:>8.2f}{r['out_f1']:>8.2f}"
              f"{r['type_acc']:>10.2f}{r['validity']:>8.2f}"
              f"{r['judge']:>8.2f}"
              f"{r['time_s']:>7.1f}s  {r['model']}")

    dim_names = ["captures_variable_parts", "output_completeness",
                 "type_precision", "field_naming", "right_granularity"]
    dim_short = ["var_parts", "out_compl", "type_prec", "naming", "granular"]
    print(f"\nJudge dimension breakdown (mean per tier, 1-5 scale):")
    hdr2 = f"{'tier':<8}" + "".join(f"{s:>12}" for s in dim_short)
    print(hdr2)
    print("─" * len(hdr2))
    for r in results:
        dims = r.get("judge_dims", {})
        vals = "".join(f"{dims.get(d, 0):>12.1f}" for d in dim_names)
        print(f"{r['tier']:<8}{vals}")

    out_path = Path(__file__).resolve().parents[1] / "data" / "eval" / "scaling_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
