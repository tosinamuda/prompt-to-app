"""Diagnose why GEPA underperformed the no-loop baseline in RQ4 (issue #2).

Reproduces the RQ4 GEPA condition per LOOCV fold (detailed seed, Sonnet-CLI reflection,
gpt-oss executor, Haiku-CLI judge) but captures what GEPA actually produced:

  H2 (overfitting): how many gold field names from the *training* folds appear verbatim
     in the evolved instruction — a memorization signal.
  H3 (instruction length): does a longer evolved instruction correlate with a lower
     held-out judge score? Pairs with the manual finding that a lean 253-char docstring
     already beats the detailed 1339-char one (scripts/signature_study.py).

Per fold it records the no-GEPA baseline and the GEPA result on the held-out case, plus
the evolved instruction text and length. Evolved instructions are dumped for inspection.

Usage:
    uv run python scripts/gepa_diagnosis.py
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import dspy
from dotenv import load_dotenv

from prompt2app.claude_lm import make_lm
from prompt2app.evaluation import field_prf, induction_metric_with_feedback, mean
from prompt2app.induction import InduceAppSignature, SignatureInducer, slug
from prompt2app.llm_judge import SchemaJudge, format_schema, judge_score
from prompt2app.schemas import AppSpec

load_dotenv()

DATA = Path(__file__).resolve().parents[1] / "data" / "eval"
CASES_PATH = DATA / "induction_cases.jsonl"
OUT_PATH = DATA / "gepa_diagnosis_results.json"
INSTR_DUMP = DATA / "gepa_evolved_instructions.txt"

BASE_MODEL = "openrouter/openai/gpt-oss-120b"
REFLECTION_MODEL = "claude-cli/sonnet"
JUDGE_MODEL = "claude-cli/haiku"
MAX_METRIC_CALLS = 50  # matches the RQ4 run being diagnosed


def load_cases() -> list[dict]:
    return [json.loads(line) for line in CASES_PATH.read_text().splitlines() if line.strip()]


def to_example(case: dict) -> dspy.Example:
    return dspy.Example(
        raw_prompt=case["prompt"],
        input_parameters=case["gold"]["inputs"],
        program_outputs=case["gold"]["outputs"],
    ).with_inputs("raw_prompt")


def configure_base() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    dspy.configure(lm=dspy.LM(BASE_MODEL, temperature=0, api_key=api_key or None, cache=False))


def evolved_instructions(compiled: SignatureInducer) -> str:
    try:
        return compiled.induce.predict.signature.instructions
    except AttributeError:
        return ""


def gold_field_names(cases: list[dict]) -> set[str]:
    names: set[str] = set()
    for c in cases:
        for grp in ("inputs", "outputs"):
            names.update(slug(f["name"]) for f in c["gold"][grp])
    return names


def in_f1(app: AppSpec | None, gold: dict) -> float:
    if app is None:
        return 0.0
    return field_prf([f.model_dump() for f in app.inputs], gold.get("inputs", [])).f1


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    vx = sum((x - mx) ** 2 for x in xs) ** 0.5
    vy = sum((y - my) ** 2 for y in ys) ** 0.5
    return cov / (vx * vy) if vx and vy else 0.0


def run_fold(i: int, cases: list[dict], judge: SchemaJudge) -> dict | None:
    test = cases[i]
    train_cases = [c for j, c in enumerate(cases) if j != i]
    train_examples = [to_example(c) for c in train_cases]
    split = max(1, len(train_examples) // 4)
    val, train = train_examples[:split], train_examples[split:]

    baseline_app = SignatureInducer()(test["prompt"])  # detailed seed, no GEPA

    optimizer = dspy.GEPA(
        metric=induction_metric_with_feedback,
        reflection_lm=make_lm(REFLECTION_MODEL, max_thinking_tokens=4000),
        max_metric_calls=MAX_METRIC_CALLS,
        num_threads=1,
        track_stats=True,
    )
    try:
        compiled = optimizer.compile(student=SignatureInducer(), trainset=train, valset=val)
        gepa_app = compiled(test["prompt"])
        instr = evolved_instructions(compiled)
    except Exception as exc:
        print(f"  fold {i + 1} GEPA FAIL: {exc}")
        return None

    train_names = gold_field_names(train_cases)
    leaked = sorted(n for n in train_names if n in instr)

    base_judge = judge_score(judge(original_prompt=test["prompt"],
                                   predicted_schema=format_schema(baseline_app)))
    gepa_judge = judge_score(judge(original_prompt=test["prompt"],
                                   predicted_schema=format_schema(gepa_app)))
    result = {
        "fold": i + 1,
        "seed_chars": len(InduceAppSignature.instructions),
        "evolved_chars": len(instr),
        "base_judge": round(base_judge, 3),
        "gepa_judge": round(gepa_judge, 3),
        "base_in_f1": round(in_f1(baseline_app, test["gold"]), 3),
        "gepa_in_f1": round(in_f1(gepa_app, test["gold"]), 3),
        "train_field_names_in_instruction": leaked,
        "instruction": instr,
    }
    print(f"  fold {i + 1}: evolved {result['evolved_chars']:>5} chars "
          f"(seed {result['seed_chars']}) | judge base={base_judge:.2f} gepa={gepa_judge:.2f} "
          f"| {len(leaked)} train field names leaked")
    return result


def report(folds: list[dict]) -> dict:
    lens = [f["evolved_chars"] for f in folds]
    gepa_j = [f["gepa_judge"] for f in folds]
    deltas = [f["gepa_judge"] - f["base_judge"] for f in folds]
    summary = {
        "n_folds": len(folds),
        "mean_seed_chars": round(mean([f["seed_chars"] for f in folds]), 1),
        "mean_evolved_chars": round(mean(lens), 1),
        "mean_base_judge": round(mean([f["base_judge"] for f in folds]), 3),
        "mean_gepa_judge": round(mean(gepa_j), 3),
        "mean_delta_judge": round(mean(deltas), 3),
        "corr_evolved_len_vs_judge": round(pearson(lens, gepa_j), 3),
        "mean_train_names_leaked": round(mean([len(f["train_field_names_in_instruction"])
                                               for f in folds]), 2),
    }
    print(f"\n{'=' * 70}\nGEPA DIAGNOSIS (RQ4 / #2)\n{'=' * 70}")
    print(f"seed instruction: {summary['mean_seed_chars']:.0f} chars")
    growth = summary["mean_evolved_chars"] / summary["mean_seed_chars"]
    print(f"evolved instruction: {summary['mean_evolved_chars']:.0f} chars "
          f"(mean) — GEPA grows the prompt {growth:.1f}×")
    print(f"judge: baseline {summary['mean_base_judge']:.3f} → GEPA "
          f"{summary['mean_gepa_judge']:.3f}  (Δ {summary['mean_delta_judge']:+.3f})")
    print(f"H3 — corr(evolved length, judge) = {summary['corr_evolved_len_vs_judge']:+.3f} "
          "(negative ⇒ longer instructions score worse)")
    print(f"H2 — {summary['mean_train_names_leaked']:.1f} training-fold field names appear "
          "verbatim in the evolved instruction (memorization signal)")
    return summary


def main() -> None:
    cases = load_cases()
    print(f"GEPA diagnosis — {len(cases)} LOOCV folds\nbase: {BASE_MODEL}  "
          f"reflection: {REFLECTION_MODEL}  judge: {JUDGE_MODEL}\n")
    configure_base()
    judge = SchemaJudge(make_lm(JUDGE_MODEL, max_thinking_tokens=0))

    t0 = time.time()
    folds = [r for i in range(len(cases)) if (r := run_fold(i, cases, judge)) is not None]
    summary = report(folds)

    INSTR_DUMP.write_text("\n\n".join(
        f"=== FOLD {f['fold']} ({f['evolved_chars']} chars, "
        f"judge {f['gepa_judge']}) ===\n{f['instruction']}" for f in folds
    ))
    OUT_PATH.write_text(json.dumps({
        "model": BASE_MODEL, "reflection_model": REFLECTION_MODEL, "judge_model": JUDGE_MODEL,
        "max_metric_calls": MAX_METRIC_CALLS, "summary": summary,
        "per_fold": [{k: v for k, v in f.items() if k != "instruction"} for f in folds],
    }, indent=2))
    print(f"\nResults → {OUT_PATH}\nEvolved instructions → {INSTR_DUMP}\n"
          f"Total: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
