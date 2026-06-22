"""Induction-quality eval harness.

Runs the inducer over a gold set and reports field P/R/F1, type accuracy, and signature
validity. This is the measurement apparatus for the research questions in docs/SPEC.md §8
(notably RQ1 parameterization-granularity and RQ2 scaling — swap LM_MODEL to compare tiers).

Usage:
    uv run python scripts/eval.py [path/to/cases.jsonl]

Caveat (see SPEC §8): a prompt has no single correct abstraction, so field-F1 measures
conformance to one annotation convention, not ground truth. Report inter-annotator
agreement on the gold set before over-interpreting these numbers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from prompt2app.evaluation import mean, score_case
from prompt2app.lm import configure_dspy_lm
from prompt2app.optimize import get_inducer
from prompt2app.settings import get_settings

DEFAULT_CASES = Path(__file__).resolve().parents[1] / "data" / "eval" / "induction_cases.jsonl"


def load_cases(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CASES
    settings = get_settings()
    configure_dspy_lm(settings)
    inducer = get_inducer()
    cases = load_cases(path)

    print(f"model = {settings.lm_model}   cases = {len(cases)}\n")
    header = f"{'task':<34}{'in_F1':>8}{'out_F1':>8}{'type_acc':>10}{'valid':>7}"
    print(header)
    print("-" * len(header))

    in_f1s, out_f1s, type_accs, valids = [], [], [], []
    for case in cases:
        app = inducer(case["prompt"])
        s = score_case(app, case["gold"])
        in_f1s.append(s.inputs.f1)
        out_f1s.append(s.outputs.f1)
        type_accs.append(s.input_type_accuracy)
        valids.append(1.0 if s.valid else 0.0)
        ta = "n/a" if s.input_type_accuracy is None else f"{s.input_type_accuracy:.2f}"
        print(
            f"{app.task_name[:33]:<34}{s.inputs.f1:>8.2f}{s.outputs.f1:>8.2f}"
            f"{ta:>10}{('yes' if s.valid else 'NO'):>7}"
        )

    print("-" * len(header))
    print(
        f"{'MEAN':<34}{mean(in_f1s):>8.2f}{mean(out_f1s):>8.2f}"
        f"{mean(type_accs):>10.2f}{mean(valids):>7.2f}"
    )


if __name__ == "__main__":
    main()
