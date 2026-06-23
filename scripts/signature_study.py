"""Manual signature optimization for induction (#2 prep, per the dspy skill).

Before handing the signature to GEPA, hand-tune the prompt surface and measure. This
crosses two levers:
  - docstring: the detailed 6-step seed vs a lean task statement (the skill warns a
    bloated seed gets in the optimizer's way; this also probes the instruction-length
    hypothesis for GEPA)
  - module: ChainOfThought (reasoning) vs Predict (direct)

Field names and the typed InducedField outputs are held constant — only the prompt
surface changes. Reports gold-F1, the LLM judge, and the rendered instruction length.

Usage:
    uv run python scripts/signature_study.py
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import dspy
from dotenv import load_dotenv

from prompt2app.claude_lm import make_lm
from prompt2app.evaluation import field_prf, mean, type_accuracy
from prompt2app.induction import InduceAppSignature, SignatureInducer
from prompt2app.llm_judge import SchemaJudge, format_schema, judge_score
from prompt2app.schemas import AppSpec

load_dotenv()

DATA = Path(__file__).resolve().parents[1] / "data" / "eval"
CASES_PATH = DATA / "induction_cases.jsonl"
OUT_PATH = DATA / "signature_results.json"

BASE_MODEL = "openrouter/openai/gpt-oss-120b"
JUDGE_MODEL = "claude-cli/haiku"

# A lean task statement. The type vocabulary lives in the field descriptions, so the
# model still sees the closed type set without the 6-step procedure in the docstring.
LEAN_INSTRUCTIONS = (
    "Compile a natural-language prompt into a reusable, typed program: identify the "
    "input fields a user can vary between runs, the typed outputs the program produces, "
    "and any fixed constraints. Ground every field in the prompt and use clear "
    "snake_case names."
)

VARIANTS = [
    {"name": "detailed+cot", "instructions": None, "use_cot": True},
    {"name": "detailed+predict", "instructions": None, "use_cot": False},
    {"name": "lean+cot", "instructions": LEAN_INSTRUCTIONS, "use_cot": True},
    {"name": "lean+predict", "instructions": LEAN_INSTRUCTIONS, "use_cot": False},
]


def load_cases() -> list[dict]:
    return [json.loads(line) for line in CASES_PATH.read_text().splitlines() if line.strip()]


def configure_base() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    dspy.configure(lm=dspy.LM(BASE_MODEL, temperature=0, api_key=api_key or None, cache=False))


def induce(variant: dict, prompt: str) -> AppSpec | None:
    inducer = SignatureInducer(instructions=variant["instructions"], use_cot=variant["use_cot"])
    try:
        return inducer(prompt)
    except Exception as exc:
        print(f"    {variant['name']} induce FAIL: {exc}")
        return None


def score(app: AppSpec, gold: dict) -> dict:
    pred_in = [f.model_dump() for f in app.inputs]
    pred_out = [f.model_dump() for f in app.outputs]
    t = type_accuracy(pred_in, gold.get("inputs", []))
    return {
        "in_f1": round(field_prf(pred_in, gold.get("inputs", [])).f1, 3),
        "out_f1": round(field_prf(pred_out, gold.get("outputs", [])).f1, 3),
        "type_acc": round(t, 3) if t is not None else None,
        "n_inputs": len(app.inputs),
    }


def instruction_len(variant: dict) -> int:
    instr = variant["instructions"] or InduceAppSignature.instructions
    return len(instr)


def run_grid(cases: list[dict]) -> tuple[list[dict], dict[str, list[AppSpec | None]]]:
    points: list[dict] = []
    apps: dict[str, list[AppSpec | None]] = {v["name"]: [] for v in VARIANTS}
    for ci, case in enumerate(cases, start=1):
        print(f"{'─' * 70}\nCase {ci}: {case['prompt'][:55]}…")
        for variant in VARIANTS:
            app = induce(variant, case["prompt"])
            apps[variant["name"]].append(app)
            point = {"case_id": ci, "variant": variant["name"], "prompt": case["prompt"]}
            if app is None:
                point.update(in_f1=0.0, out_f1=0.0, type_acc=None, n_inputs=0, judge=0.0)
            else:
                point.update(score(app, case["gold"]))
                print(f"  {variant['name']:<18} in_F1={point['in_f1']:.2f} "
                      f"out_F1={point['out_f1']:.2f} fields={point['n_inputs']}")
            points.append(point)
    return points, apps


def run_judge(points: list[dict], apps: dict[str, list[AppSpec | None]], cases: list[dict]) -> None:
    judge = SchemaJudge(make_lm(JUDGE_MODEL, max_thinking_tokens=0))
    by_key = {(p["case_id"], p["variant"]): p for p in points}
    for name, app_list in apps.items():
        for ci, (case, app) in enumerate(zip(cases, app_list, strict=True), start=1):
            point = by_key[(ci, name)]
            if app is None:
                point["judge"] = 0.0
                continue
            try:
                pred = judge(original_prompt=case["prompt"], predicted_schema=format_schema(app))
                point["judge"] = round(judge_score(pred), 3)
            except Exception as exc:
                print(f"    judge FAIL {name} case {ci}: {exc}")
                point["judge"] = 0.0


def summarize(points: list[dict]) -> list[dict]:
    out: list[dict] = []
    for variant in VARIANTS:
        rows = [p for p in points if p["variant"] == variant["name"]]
        out.append({
            "variant": variant["name"],
            "instruction_chars": instruction_len(variant),
            "in_f1": round(mean([p["in_f1"] for p in rows]), 3),
            "out_f1": round(mean([p["out_f1"] for p in rows]), 3),
            "type_acc": round(mean([p["type_acc"] for p in rows if p["type_acc"] is not None]), 3),
            "judge": round(mean([p["judge"] for p in rows]), 3),
        })
    return out


def main() -> None:
    cases = load_cases()
    print(f"Signature study — {len(VARIANTS)} variants × {len(cases)} cases\nbase: {BASE_MODEL}\n")
    configure_base()

    t0 = time.time()
    points, apps = run_grid(cases)
    print(f"\nInduction done in {time.time() - t0:.1f}s")

    print(f"\nRunning judge ({JUDGE_MODEL})…")
    run_judge(points, apps, cases)

    summary = summarize(points)
    print(f"\n{'=' * 70}\nSIGNATURE COMPARISON (#2 prep)\n{'=' * 70}")
    hdr = f"{'variant':<18}{'instr_chars':>12}{'in_F1':>8}{'out_F1':>8}{'type':>7}{'judge':>8}"
    print(hdr + "\n" + "─" * len(hdr))
    for r in summary:
        print(f"{r['variant']:<18}{r['instruction_chars']:>12}{r['in_f1']:>8.2f}"
              f"{r['out_f1']:>8.2f}{r['type_acc']:>7.2f}{r['judge']:>8.2f}")
    best = max(summary, key=lambda r: (r["judge"], r["in_f1"]))
    print(f"\nBest: {best['variant']} (judge {best['judge']:.2f}, in_F1 {best['in_f1']:.2f})")

    OUT_PATH.write_text(json.dumps(
        {"model": BASE_MODEL, "judge_model": JUDGE_MODEL,
         "summary": summary, "data_points": points},
        indent=2,
    ))
    print(f"Saved to {OUT_PATH}\nTotal: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
