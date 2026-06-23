"""Compute inter-annotator agreement over the gold annotations (#4).

Reads one JSONL file per annotator from data/eval/annotations/ (see the README there
for the format), then reports Cohen's (2 annotators) or Fleiss' (3+) kappa for:
  - field existence — do annotators agree which fields a prompt should have?
  - field type      — among fields everyone included, do they agree on the type?

Usage:
    uv run python scripts/annotator_agreement.py
"""

from __future__ import annotations

import json
from pathlib import Path

from prompt2app.agreement import (
    cohens_kappa,
    field_existence_ratings,
    fleiss_kappa,
    interpret,
)
from prompt2app.induction import slug

ANNOTATIONS = Path(__file__).resolve().parents[1] / "data" / "eval" / "annotations"


def load_annotations() -> list[dict]:
    """Each annotator file → {name, cases: [case-by-case dict sorted by case_id]}."""
    out: list[dict] = []
    for path in sorted(ANNOTATIONS.glob("*.jsonl")):
        if path.name.startswith("_"):
            continue
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        rows.sort(key=lambda r: r["case_id"])
        out.append({"name": path.stem, "cases": rows})
    return out


def existence_kappa(annotations: list[dict], group: str) -> float:
    if len(annotations) == 2:
        return _pairwise_existence_kappa(annotations, group)
    rows = field_existence_ratings(annotations, group)
    return fleiss_kappa(rows) if rows else 1.0


def _pairwise_existence_kappa(annotations: list[dict], group: str) -> float:
    a_labels: list[bool] = []
    b_labels: list[bool] = []
    a, b = annotations[0], annotations[1]
    for ci in range(len(a["cases"])):
        names_a = {slug(f["name"]) for f in a["cases"][ci].get(group, []) if f.get("name")}
        names_b = {slug(f["name"]) for f in b["cases"][ci].get(group, []) if f.get("name")}
        for name in sorted(names_a | names_b):
            a_labels.append(name in names_a)
            b_labels.append(name in names_b)
    return cohens_kappa(a_labels, b_labels)


def type_agreement(annotations: list[dict], group: str) -> tuple[float, int]:
    """Raw type agreement over fields every annotator included. Returns (fraction, n)."""
    agree = 0
    total = 0
    for ci in range(len(annotations[0]["cases"])):
        maps = [
            {slug(f["name"]): f.get("type")
             for f in ann["cases"][ci].get(group, []) if f.get("name")}
            for ann in annotations
        ]
        common = set.intersection(*[set(m) for m in maps]) if maps else set()
        for name in common:
            total += 1
            if len({m[name] for m in maps}) == 1:
                agree += 1
    return (agree / total if total else 1.0, total)


def main() -> None:
    annotations = load_annotations()
    if len(annotations) < 2:
        print(f"Found {len(annotations)} annotator file(s) in {ANNOTATIONS}.")
        print("Need at least 2 to compute agreement. See the README there for the format.")
        return

    names = ", ".join(a["name"] for a in annotations)
    method = "Cohen's" if len(annotations) == 2 else "Fleiss'"
    print(f"{len(annotations)} annotators ({names}) — {method} kappa\n")

    for group in ("inputs", "outputs"):
        k = existence_kappa(annotations, group)
        ta, n = type_agreement(annotations, group)
        print(f"{group}:")
        print(f"  field existence κ = {k:.3f}  ({interpret(k)})")
        print(f"  type agreement    = {ta:.3f}  over {n} commonly-included fields")


if __name__ == "__main__":
    main()
