"""RQ3 parameterization-granularity study: what governs the optimal field count?

For each gold case the inducer is run at five granularity levels — from "lift only
the 1-2 critical knobs" to "decompose every detail into its own field". Each induced
form is scored on two opposing axes:

  - quality:  gold-field F1, type accuracy, and the LLM judge's schema rating
  - reuse:    can the form serve realistic rephrasings of the task without recompiling
              (coverage over hand-written variants in data/eval/reuse_variants.jsonl)

More fields raise reuse coverage but eventually hurt the judge's granularity rating —
the trade the experiment is built to surface.

Usage:
    uv run python scripts/granularity_study.py
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import dspy
from dotenv import load_dotenv

from prompt2app.claude_lm import make_lm
from prompt2app.evaluation import field_prf, mean, reuse_coverage, type_accuracy
from prompt2app.induction import SignatureInducer
from prompt2app.llm_judge import SchemaJudge, format_schema, judge_score
from prompt2app.schemas import AppSpec

load_dotenv()

DATA = Path(__file__).resolve().parents[1] / "data" / "eval"
CASES_PATH = DATA / "induction_cases.jsonl"
VARIANTS_PATH = DATA / "reuse_variants.jsonl"
OUT_PATH = DATA / "granularity_results.json"

BASE_MODEL = "openrouter/openai/gpt-oss-120b"
JUDGE_MODEL = "claude-cli/sonnet"

# Each level is the same signature with a different granularity directive appended.
# Field names (the prompt tokens) are identical across levels — only field count varies.
LEVELS: list[tuple[str, str | None]] = [
    ("minimal",
     "Extract ONLY the 1-2 most critical parameters — the bare minimum a user must "
     "change between runs. Collapse related details into a single field. When in doubt, "
     "leave it out."),
    ("conservative",
     "Extract only the essential parameters a user must provide. Keep the form small; "
     "merge closely-related details into one field rather than splitting them."),
    ("baseline", None),
    ("thorough",
     "Extract every variable part of the prompt, including optional parameters. Give "
     "each distinct knob its own field and lift a default value wherever the prompt "
     "states one."),
    ("maximal",
     "Decompose the prompt maximally: turn every noun phrase, qualifier, or detail that "
     "could conceivably vary across uses into its own separate input field. Strongly "
     "favor more, finer fields over fewer, coarser ones."),
]


def load_cases() -> list[dict]:
    return [json.loads(line) for line in CASES_PATH.read_text().splitlines() if line.strip()]


def load_variants() -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for line in VARIANTS_PATH.read_text().splitlines():
        if line.strip():
            rec = json.loads(line)
            out[rec["case_id"]] = rec["variants"]
    return out


def configure_base() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    dspy.configure(lm=dspy.LM(BASE_MODEL, temperature=0, api_key=api_key or None, cache=False))


def induce(level_hint: str | None, prompt: str) -> AppSpec | None:
    try:
        return SignatureInducer(granularity_hint=level_hint)(prompt)
    except Exception as exc:
        print(f"    induce FAIL: {exc}")
        return None


def score_point(app: AppSpec, gold: dict, variants: list[dict]) -> dict:
    pred_inputs = [f.model_dump() for f in app.inputs]
    pred_outputs = [f.model_dump() for f in app.outputs]
    reuse = reuse_coverage(pred_inputs, variants)
    return {
        "field_count": len(app.inputs),
        "field_f1": round(field_prf(pred_inputs, gold.get("inputs", [])).f1, 3),
        "out_f1": round(field_prf(pred_outputs, gold.get("outputs", [])).f1, 3),
        "type_acc": (lambda t: round(t, 3) if t is not None else None)(
            type_accuracy(pred_inputs, gold.get("inputs", []))
        ),
        "reuse_binary": round(reuse.binary, 3),
        "reuse_graded": round(reuse.graded, 3),
    }


def run_grid(
    cases: list[dict], variants: dict[int, list[dict]],
) -> tuple[list[dict], list[AppSpec | None]]:
    points: list[dict] = []
    apps: list[AppSpec | None] = []
    for ci, case in enumerate(cases, start=1):
        print(f"{'─' * 70}\nCase {ci}: {case['prompt'][:60]}…")
        for level, hint in LEVELS:
            app = induce(hint, case["prompt"])
            apps.append(app)
            point = {"case_id": ci, "level": level, "prompt": case["prompt"]}
            if app is None:
                point.update(field_count=0, field_f1=0.0, out_f1=0.0, type_acc=None,
                             reuse_binary=0.0, reuse_graded=0.0, judge=0.0)
            else:
                point.update(score_point(app, case["gold"], variants.get(ci, [])))
                print(f"  {level:<13} fields={point['field_count']:<2} "
                      f"in_F1={point['field_f1']:.2f} reuse={point['reuse_binary']:.2f}")
            points.append(point)
    return points, apps


def run_judge(points: list[dict], apps: list[AppSpec | None]) -> None:
    judge = SchemaJudge(make_lm(JUDGE_MODEL, max_thinking_tokens=0))
    dims = ["captures_variable_parts", "output_completeness", "type_precision",
            "field_naming", "right_granularity"]
    for point, app in zip(points, apps, strict=True):
        if app is None:
            point["judge"] = 0.0
            point["judge_dims"] = {}
            continue
        try:
            pred = judge(original_prompt=point["prompt"], predicted_schema=format_schema(app))
            point["judge"] = round(judge_score(pred), 3)
            point["judge_dims"] = {d: getattr(pred.verdict, d) for d in dims}
            print(f"  {point['level']:<13} case {point['case_id']} → judge={point['judge']:.2f} "
                  f"(granularity={pred.verdict.right_granularity})")
        except Exception as exc:
            print(f"  judge FAIL case {point['case_id']} {point['level']}: {exc}")
            point["judge"] = 0.0
            point["judge_dims"] = {}


def summarize(points: list[dict]) -> list[dict]:
    by_level: list[dict] = []
    for level, _ in LEVELS:
        rows = [p for p in points if p["level"] == level]
        counts = sorted(p["field_count"] for p in rows)
        median_fields = counts[len(counts) // 2] if counts else 0
        by_level.append({
            "level": level,
            "median_field_count": median_fields,
            "mean_field_count": round(mean([p["field_count"] for p in rows]), 2),
            "field_f1": round(mean([p["field_f1"] for p in rows]), 3),
            "type_acc": round(mean([p["type_acc"] for p in rows if p["type_acc"] is not None]), 3),
            "reuse_binary": round(mean([p["reuse_binary"] for p in rows]), 3),
            "reuse_graded": round(mean([p["reuse_graded"] for p in rows]), 3),
            "judge": round(mean([p["judge"] for p in rows]), 3),
        })
    return by_level


def print_table(by_level: list[dict]) -> None:
    print(f"\n{'=' * 78}\nGRANULARITY TRADEOFF (RQ3)\n{'=' * 78}")
    hdr = (f"{'level':<14}{'fields':>8}{'in_F1':>8}{'type':>8}"
           f"{'reuse_b':>9}{'reuse_g':>9}{'judge':>8}")
    print(hdr + "\n" + "─" * len(hdr))
    for r in by_level:
        print(f"{r['level']:<14}{r['mean_field_count']:>8.1f}{r['field_f1']:>8.2f}"
              f"{r['type_acc']:>8.2f}{r['reuse_binary']:>9.2f}{r['reuse_graded']:>9.2f}"
              f"{r['judge']:>8.2f}")
    best = max(by_level, key=lambda r: r["judge"])
    peak_reuse = max(by_level, key=lambda r: r["reuse_binary"])
    reuse_seq = [r["reuse_binary"] for r in by_level]
    monotonic = all(b >= a for a, b in zip(reuse_seq, reuse_seq[1:], strict=True))
    if monotonic:
        trend = "rises with field count, so quality is what bounds the optimum"
    else:
        trend = (f"peaks at '{peak_reuse['level']}' ({peak_reuse['reuse_binary']:.2f}) rather "
                 "than the finest level — past the optimum, finer directives rename and split "
                 "the canonical knobs, costing coverage as well as quality")
    print(f"\nPeak judge score at level '{best['level']}' "
          f"(mean {best['mean_field_count']:.1f} fields). Reuse coverage {trend}.")


def main() -> None:
    cases = load_cases()
    variants = load_variants()
    print(f"RQ3 granularity — {len(cases)} cases × {len(LEVELS)} levels = "
          f"{len(cases) * len(LEVELS)} inductions\nbase: {BASE_MODEL}\n")

    configure_base()
    t0 = time.time()
    points, apps = run_grid(cases, variants)
    print(f"\nInduction done in {time.time() - t0:.1f}s")

    print(f"\n{'─' * 70}\nRunning LLM judge ({JUDGE_MODEL})…")
    t1 = time.time()
    run_judge(points, apps)
    print(f"Judge done in {time.time() - t1:.1f}s")

    by_level = summarize(points)
    print_table(by_level)

    OUT_PATH.write_text(json.dumps({
        "model": BASE_MODEL,
        "judge_model": JUDGE_MODEL,
        "n_cases": len(cases),
        "levels": [name for name, _ in LEVELS],
        "by_level": by_level,
        "data_points": points,
    }, indent=2))
    print(f"\nResults saved to {OUT_PATH}\nTotal time: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
