"""RQ4 diagnosis: instruction evolution inside vs outside its operating envelope (#2).

Runs the GEPA condition per LOOCV fold while capturing what it actually produced, under
two arms (see issue #2 and docs/positioning.md):

  Arm A — budget-constrained, reproduces the RQ4 cell:   --budget 50  --valset tiny
  Arm B — documented envelope:                           --budget 300 --valset candidates

The ``candidates`` valset uses data/eval/induction_cases_candidates.jsonl (draft gold
cases, never used for reporting) as GEPA's Pareto-selection set. That fixes the RQ4
design flaw — selection starved on 1-2 examples — without touching the held-out test
case or shrinking the 7-case trainset. Comparing arms at matched budget isolates H2
(selection starvation); the instruction dump supports H3′ (train-specific content:
gold field names from training folds leaking verbatim into evolved instructions).

Per fold: no-loop baseline + GEPA on the held-out case (judge + gold-F1), evolved
instruction text/length, and the leak count. Models: gpt-oss-120b executor (paid API),
claude-cli/sonnet reflection, claude-cli/haiku judge (flat-fee CLI).

Usage:
    uv run python scripts/gepa_diagnosis.py --folds 1                # pilot, Arm B
    uv run python scripts/gepa_diagnosis.py --budget 50 --valset tiny  # Arm A replica
"""

from __future__ import annotations

import argparse
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
from prompt2app.stats import pearson

load_dotenv()

DATA = Path(__file__).resolve().parents[1] / "data" / "eval"
CASES_PATH = DATA / "induction_cases.jsonl"
CANDIDATES_PATH = DATA / "induction_cases_candidates.jsonl"

BASE_MODEL = "openrouter/openai/gpt-oss-120b"
REFLECTION_MODEL = "claude-cli/sonnet"
JUDGE_MODEL = "claude-cli/haiku"

# Lean seed from the signature study — the 253-char task statement that matched the
# detailed docstring on judge quality. Lets Arm B also ask "does evolution from a lean
# seed beat evolution from the detailed one?".
LEAN_INSTRUCTIONS = (
    "Compile a natural-language prompt into a reusable, typed program: identify the "
    "input fields a user can vary between runs, the typed outputs the program produces, "
    "and any fixed constraints. Ground every field in the prompt and use clear "
    "snake_case names."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=int, default=300,
                        help="GEPA max_metric_calls per fold (Arm A: 50, Arm B: 300+)")
    parser.add_argument("--valset", choices=["candidates", "tiny"], default="candidates",
                        help="'candidates' = draft gold cases as selection set; "
                             "'tiny' = split 1-2 examples off the trainset (RQ4 replica)")
    parser.add_argument("--folds", type=int, default=8,
                        help="run the first N LOOCV folds")
    parser.add_argument("--seed-instructions", choices=["detailed", "lean"],
                        default="detailed", help="docstring the evolution starts from")
    return parser.parse_args()


def load_cases(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


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


def run_fold(
    i: int,
    cases: list[dict],
    judge: SchemaJudge,
    *,
    budget: int,
    val_examples: list[dspy.Example] | None,
    instructions: str | None,
) -> dict | None:
    test = cases[i]
    train_cases = [c for j, c in enumerate(cases) if j != i]
    train_examples = [to_example(c) for c in train_cases]
    if val_examples is None:  # tiny: carve selection data out of the trainset (RQ4 replica)
        split = max(1, len(train_examples) // 4)
        val, train = train_examples[:split], train_examples[split:]
    else:
        val, train = val_examples, train_examples

    baseline_app = SignatureInducer(instructions=instructions)(test["prompt"])

    optimizer = dspy.GEPA(
        metric=induction_metric_with_feedback,
        reflection_lm=make_lm(REFLECTION_MODEL, max_thinking_tokens=4000),
        max_metric_calls=budget,
        num_threads=1,
        track_stats=True,
    )
    try:
        compiled = optimizer.compile(
            student=SignatureInducer(instructions=instructions), trainset=train, valset=val,
        )
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
        "seed_chars": len(instructions or InduceAppSignature.instructions),
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
    growth = summary["mean_evolved_chars"] / summary["mean_seed_chars"]
    print(f"seed instruction: {summary['mean_seed_chars']:.0f} chars")
    print(f"evolved instruction: {summary['mean_evolved_chars']:.0f} chars "
          f"(mean) — evolution grows the prompt {growth:.1f}×")
    print(f"judge: baseline {summary['mean_base_judge']:.3f} → GEPA "
          f"{summary['mean_gepa_judge']:.3f}  (Δ {summary['mean_delta_judge']:+.3f})")
    print(f"H3′ — corr(evolved length, judge) = {summary['corr_evolved_len_vs_judge']:+.3f}")
    print(f"H3′ — {summary['mean_train_names_leaked']:.1f} training-fold field names appear "
          "verbatim in the evolved instruction (memorization signal)")
    return summary


def main() -> None:
    args = parse_args()
    cases = load_cases(CASES_PATH)
    n_folds = min(args.folds, len(cases))
    val_examples = None
    if args.valset == "candidates":
        val_examples = [to_example(c) for c in load_cases(CANDIDATES_PATH)]
    instructions = LEAN_INSTRUCTIONS if args.seed_instructions == "lean" else None

    tag = f"{args.valset}_b{args.budget}_{args.seed_instructions}"
    out_path = DATA / f"gepa_diagnosis_{tag}.json"
    instr_dump = DATA / f"gepa_evolved_instructions_{tag}.txt"

    print(f"GEPA diagnosis — {n_folds} fold(s) | budget={args.budget} "
          f"valset={args.valset}({len(val_examples) if val_examples else '1-2 split'}) "
          f"seed={args.seed_instructions}")
    print(f"executor: {BASE_MODEL}  reflection: {REFLECTION_MODEL}  judge: {JUDGE_MODEL}\n")
    configure_base()
    judge = SchemaJudge(make_lm(JUDGE_MODEL, max_thinking_tokens=0))

    t0 = time.time()
    folds = []
    for i in range(n_folds):
        result = run_fold(i, cases, judge, budget=args.budget,
                          val_examples=val_examples, instructions=instructions)
        if result is not None:
            folds.append(result)
    if not folds:
        print("No fold completed — nothing to report.")
        return
    summary = report(folds)

    instr_dump.write_text("\n\n".join(
        f"=== FOLD {f['fold']} ({f['evolved_chars']} chars, "
        f"judge {f['gepa_judge']}) ===\n{f['instruction']}" for f in folds
    ))
    out_path.write_text(json.dumps({
        "config": {"budget": args.budget, "valset": args.valset,
                   "seed_instructions": args.seed_instructions, "n_folds": n_folds},
        "model": BASE_MODEL, "reflection_model": REFLECTION_MODEL, "judge_model": JUDGE_MODEL,
        "summary": summary,
        "per_fold": [{k: v for k, v in f.items() if k != "instruction"} for f in folds],
    }, indent=2))
    print(f"\nResults → {out_path}\nEvolved instructions → {instr_dump}\n"
          f"Total: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
