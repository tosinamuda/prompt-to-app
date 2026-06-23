"""Render publication figures from the eval result JSON files in data/eval/.

Each figure is regenerated from its result file, so reruns stay in sync with the data.
Output goes to figures/ as both PDF and SVG (vector, thesis-ready). Colors come from the
Wong colorblind-safe palette.

Usage:
    uv run python scripts/plot_results.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt

DATA = Path(__file__).resolve().parents[1] / "data" / "eval"
FIGURES = Path(__file__).resolve().parents[1] / "figures"

# Wong palette — distinguishable under the common forms of color blindness.
BLUE, ORANGE, GREEN, VERMILLION, PURPLE = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7"

plt.rcParams.update({
    "figure.figsize": (6.5, 4.0),
    "font.size": 10,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "savefig.bbox": "tight",
})


def _save(fig, name: str) -> None:
    FIGURES.mkdir(exist_ok=True)
    for ext in ("pdf", "svg"):
        fig.savefig(FIGURES / f"{name}.{ext}")
    plt.close(fig)
    print(f"  wrote figures/{name}.pdf and .svg")


def plot_granularity_tradeoff() -> None:
    """RQ3: quality (judge, F1) vs reuse coverage across granularity levels."""
    path = DATA / "granularity_results.json"
    if not path.exists():
        print("  skip granularity — run scripts/granularity_study.py first")
        return
    data = json.loads(path.read_text())
    rows = data["by_level"]
    levels = [r["level"] for r in rows]
    xs = list(range(len(levels)))
    fields = [r["mean_field_count"] for r in rows]
    xtick_labels = [f"{lvl}\n({fc:.0f} fields)" for lvl, fc in zip(levels, fields, strict=True)]

    fig, ax = plt.subplots()
    ax.plot(xs, [r["judge"] for r in rows], "o-", color=BLUE, label="Judge score (quality)")
    ax.plot(xs, [r["field_f1"] for r in rows], "s--", color=GREEN, label="Field F1 (quality)")
    ax.plot(xs, [r["reuse_binary"] for r in rows], "^-", color=VERMILLION,
            label="Reuse coverage (binary)")
    ax.plot(xs, [r["reuse_graded"] for r in rows], "v--", color=ORANGE,
            label="Reuse coverage (graded)")

    peak = max(range(len(rows)), key=lambda i: rows[i]["judge"])
    ax.axvline(peak, color="grey", linewidth=1, linestyle=":")
    ax.annotate("peak quality", xy=(peak, rows[peak]["judge"]),
                xytext=(peak + 0.1, rows[peak]["judge"] - 0.12),
                fontsize=8, color="grey")

    ax.set_xticks(xs)
    ax.set_xticklabels(xtick_labels, fontsize=8)
    ax.set_xlabel("Parameterization granularity (coarse → fine)")
    ax.set_ylabel("Score (0–1)")
    ax.set_ylim(0, 1.05)
    ax.set_title("RQ3: Quality vs reuse across parameterization granularity")
    ax.legend(fontsize=8, loc="lower center", ncol=2)
    _save(fig, "granularity_tradeoff")


def plot_scaling() -> None:
    """RQ2: induction quality across model tiers."""
    path = DATA / "scaling_results.json"
    if not path.exists():
        print("  skip scaling — run scripts/scaling_study.py first")
        return
    rows = json.loads(path.read_text())
    tiers = [r["tier"] for r in rows]
    xs = list(range(len(tiers)))
    width = 0.35

    fig, ax = plt.subplots()
    ax.bar([x - width / 2 for x in xs], [r["judge"] for r in rows], width,
           color=BLUE, label="Judge score")
    ax.bar([x + width / 2 for x in xs], [r["in_f1"] for r in rows], width,
           color=GREEN, label="Input field F1")

    ax.set_xticks(xs)
    ax.set_xticklabels(tiers)
    ax.set_xlabel("Model tier (small → frontier)")
    ax.set_ylabel("Score (0–1)")
    ax.set_ylim(0, 1.05)
    ax.set_title("RQ2: Induction quality scales with model size")
    ax.legend(fontsize=8, loc="lower right")
    _save(fig, "scaling_quality")


def plot_loop_ablation() -> None:
    """RQ4: the four feedback-loop conditions across metrics."""
    path = DATA / "ablation_results.json"
    if not path.exists():
        print("  skip ablation — run scripts/loop_ablation.py first")
        return
    summary = json.loads(path.read_text())["summary"]
    conditions = [r["condition"] for r in summary]
    metrics = [("in_f1", "Input F1", BLUE), ("out_f1", "Output F1", GREEN),
               ("type_acc", "Type acc", ORANGE), ("judge", "Judge", VERMILLION)]
    xs = list(range(len(conditions)))
    width = 0.2

    fig, ax = plt.subplots()
    for i, (key, label, color) in enumerate(metrics):
        offset = (i - (len(metrics) - 1) / 2) * width
        ax.bar([x + offset for x in xs], [r[key] for r in summary], width,
               color=color, label=label)

    ax.set_xticks(xs)
    ax.set_xticklabels(conditions)
    ax.set_xlabel("Feedback-loop condition")
    ax.set_ylabel("Score (0–1)")
    ax.set_ylim(0, 1.05)
    ax.set_title("RQ4: Loop ablation — metrics by condition")
    ax.legend(fontsize=8, loc="lower right", ncol=2)
    _save(fig, "loop_ablation")


def main() -> None:
    print("Rendering figures…")
    plot_granularity_tradeoff()
    plot_scaling()
    plot_loop_ablation()


if __name__ == "__main__":
    main()
