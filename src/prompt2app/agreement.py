"""Inter-annotator agreement — validity check on the gold annotations.

Field-level chance-corrected agreement so a reviewer can tell whether the gold
abstractions reflect a stable ground truth or one annotator's convention. Cohen's
kappa for two annotators, Fleiss' kappa for three or more. Pure functions, unit-tested
offline; the loading/CLI layer lives in scripts/annotator_agreement.py.
"""

from __future__ import annotations

from prompt2app.induction import slug

# Landis & Koch interpretation bands for kappa.
_BANDS = [
    (0.20, "poor"), (0.40, "fair"), (0.60, "moderate"),
    (0.80, "substantial"), (1.01, "almost perfect"),
]


def interpret(kappa: float) -> str:
    for upper, label in _BANDS:
        if kappa < upper:
            return label
    return "almost perfect"


def cohens_kappa(labels_a: list[bool], labels_b: list[bool]) -> float:
    """Chance-corrected agreement between two annotators over binary decisions."""
    n = len(labels_a)
    if n == 0 or n != len(labels_b):
        raise ValueError("annotator label lists must be non-empty and equal length")
    observed = sum(1 for a, b in zip(labels_a, labels_b, strict=True) if a == b) / n
    pa_true, pb_true = sum(labels_a) / n, sum(labels_b) / n
    expected = pa_true * pb_true + (1 - pa_true) * (1 - pb_true)
    if expected >= 1.0:
        return 1.0  # both annotators unanimous on the same side — perfect by convention
    return (observed - expected) / (1 - expected)


def fleiss_kappa(item_category_counts: list[list[int]]) -> float:
    """Fleiss' kappa for >=3 raters. Each row is one item's per-category rater counts.

    Every item must have the same total number of raters.
    """
    if not item_category_counts:
        raise ValueError("need at least one item")
    n_raters = sum(item_category_counts[0])
    if n_raters < 2:
        raise ValueError("need at least two raters per item")
    if any(sum(row) != n_raters for row in item_category_counts):
        raise ValueError("every item must have the same number of raters")

    n_items = len(item_category_counts)
    p_item = [
        (sum(c * c for c in row) - n_raters) / (n_raters * (n_raters - 1))
        for row in item_category_counts
    ]
    p_bar = sum(p_item) / n_items

    n_categories = len(item_category_counts[0])
    totals = [sum(row[j] for row in item_category_counts) for j in range(n_categories)]
    p_cat = [t / (n_items * n_raters) for t in totals]
    p_expected = sum(p * p for p in p_cat)

    if p_expected >= 1.0:
        return 1.0
    return (p_bar - p_expected) / (1 - p_expected)


def field_existence_ratings(
    annotations: list[dict], group: str,
) -> list[list[int]]:
    """Build per-(case, candidate-field) [present, absent] rater counts for Fleiss.

    ``annotations`` is one record per annotator: ``{cases: [{inputs: [...], outputs: [...]}]}``.
    ``group`` is "inputs" or "outputs". A candidate field is any name some annotator used
    for that case; each annotator either included it (present) or not (absent).
    """
    n_raters = len(annotations)
    n_cases = len(annotations[0]["cases"])
    rows: list[list[int]] = []
    for ci in range(n_cases):
        per_annotator_names = [
            {slug(f["name"]) for f in ann["cases"][ci].get(group, []) if f.get("name")}
            for ann in annotations
        ]
        candidates = set().union(*per_annotator_names) if per_annotator_names else set()
        for name in sorted(candidates):
            present = sum(1 for names in per_annotator_names if name in names)
            rows.append([present, n_raters - present])
    return rows
