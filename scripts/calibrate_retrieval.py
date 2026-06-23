"""Calibrate the semantic-retrieval threshold (#5).

Embeds paraphrase pairs (should match) and unrelated pairs (should not), prints the
similarity for each, and recommends a cut-off in the gap between the two distributions.
Needs the local embedding model (no API cost); run manually, not in CI.

Usage:
    uv run python scripts/calibrate_retrieval.py
"""

from __future__ import annotations

from prompt2app.retrieval import SEMANTIC_MIN_SCORE, _cosine, _embed

PARAPHRASES = [
    ("Write an email to a supplier asking for a revised quote",
     "Draft a message to a vendor requesting updated pricing"),
    ("Create a weekly meal plan for a vegetarian family",
     "Plan a week of vegetarian meals for my household"),
    ("Draft a GitHub issue for a login bug",
     "File a bug report about the sign-in failing"),
    ("Summarize this research paper in bullet points",
     "Give me a bulleted summary of this academic article"),
]

UNRELATED = [
    ("Write a supplier email about a quote",
     "Generate a weekly meal plan with a budget"),
    ("Draft a GitHub issue for a bug",
     "Write a LinkedIn post announcing funding"),
    ("Summarize a research paper",
     "Create a Kubernetes deployment request"),
    ("Write a cover letter for an engineer",
     "Compare noise-cancelling headphones in a table"),
]


def _sims(pairs: list[tuple[str, str]]) -> list[float]:
    out = []
    for a, b in pairs:
        v = _embed([a, b])
        out.append(_cosine(v[0], v[1]))
    return out


def main() -> None:
    para = _sims(PARAPHRASES)
    unrel = _sims(UNRELATED)
    print("paraphrase pairs (should match):")
    for (a, _), s in zip(PARAPHRASES, para, strict=True):
        print(f"  {s:.3f}  {a[:50]}")
    print("unrelated pairs (should not match):")
    for (a, _), s in zip(UNRELATED, unrel, strict=True):
        print(f"  {s:.3f}  {a[:50]}")

    lo, hi = min(para), max(unrel)
    print(f"\nparaphrase min = {lo:.3f}   unrelated max = {hi:.3f}")
    if lo > hi:
        print(f"clean gap → recommended threshold ≈ {(lo + hi) / 2:.2f} "
              f"(current SEMANTIC_MIN_SCORE = {SEMANTIC_MIN_SCORE})")
    else:
        print("distributions overlap — no clean threshold; consider a stronger model")


if __name__ == "__main__":
    main()
