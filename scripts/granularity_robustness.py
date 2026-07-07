"""RQ3 robustness check: is the quality peak a gold-granularity artifact? (#1)

The gold schemas average ~4 input fields, and field-F1 rewards matching the gold field
set — so "quality peaks at ~4 fields" could be partly built into the metric. This
analysis, over the existing granularity_results.json (no LM calls):

  1. Reports the by-level curve on gold-INDEPENDENT axes only (judge, reuse coverage).
  2. Stratifies the per-level scores by each case's gold field count (small ≤3 vs
     large =5): if the F1-peak level tracks the stratum's gold size while the judge
     peak stays put, the F1 peak is an artifact and the judge/reuse peaks are robust.
  3. Quantifies entanglement: corr(|induced fields − gold fields|, in_F1) per axis.

Usage:
    uv run python scripts/granularity_robustness.py
"""

from __future__ import annotations

import json
from pathlib import Path

from prompt2app.evaluation import mean
from prompt2app.stats import pearson

DATA = Path(__file__).resolve().parents[1] / "data" / "eval"
RESULTS_PATH = DATA / "granularity_results.json"
CASES_PATH = DATA / "induction_cases.jsonl"
OUT_PATH = DATA / "granularity_robustness.json"

SMALL_GOLD_MAX = 3


def load() -> tuple[list[dict], dict[int, int]]:
    points = json.loads(RESULTS_PATH.read_text())["data_points"]
    gold_sizes = {
        i: len(json.loads(line)["gold"]["inputs"])
        for i, line in enumerate(
            (ln for ln in CASES_PATH.read_text().splitlines() if ln.strip()), start=1
        )
    }
    return points, gold_sizes


def by_level(points: list[dict], levels: list[str], key: str) -> dict[str, float]:
    return {
        level: round(mean([p[key] for p in points if p["level"] == level]), 3)
        for level in levels
    }


def peak(curve: dict[str, float]) -> str:
    return max(curve, key=curve.get)


def main() -> None:
    points, gold_sizes = load()
    levels = list(dict.fromkeys(p["level"] for p in points))

    print(f"Gold input-field counts per case: {gold_sizes}")
    print(f"Mean gold size: {mean(list(gold_sizes.values())):.2f} "
          "(the entanglement suspicion: F1 peak ≈ mean gold size)\n")

    # 1. Gold-independent curve
    judge = by_level(points, levels, "judge")
    reuse_b = by_level(points, levels, "reuse_binary")
    reuse_g = by_level(points, levels, "reuse_graded")
    f1 = by_level(points, levels, "field_f1")
    print(f"{'level':<14}{'judge*':>8}{'reuse_b*':>10}{'reuse_g*':>10}{'in_F1':>8}"
          "   (* = gold-independent)")
    print("─" * 52)
    for level in levels:
        print(f"{level:<14}{judge[level]:>8.2f}{reuse_b[level]:>10.2f}"
              f"{reuse_g[level]:>10.2f}{f1[level]:>8.2f}")
    print(f"\npeaks: judge→'{peak(judge)}'  reuse_b→'{peak(reuse_b)}'  "
          f"reuse_g→'{peak(reuse_g)}'  in_F1→'{peak(f1)}'")

    # 2. Stratified by gold size
    strata = {
        f"gold≤{SMALL_GOLD_MAX}": [p for p in points if gold_sizes[p["case_id"]] <= SMALL_GOLD_MAX],
        f"gold>{SMALL_GOLD_MAX}": [p for p in points if gold_sizes[p["case_id"]] > SMALL_GOLD_MAX],
    }
    strat_out: dict[str, dict] = {}
    for name, rows in strata.items():
        n_cases = len({p["case_id"] for p in rows})
        s_f1 = by_level(rows, levels, "field_f1")
        s_judge = by_level(rows, levels, "judge")
        s_fields = by_level(rows, levels, "field_count")
        strat_out[name] = {
            "n_cases": n_cases,
            "field_count_by_level": s_fields,
            "f1_by_level": s_f1,
            "judge_by_level": s_judge,
            "f1_peak": peak(s_f1),
            "judge_peak": peak(s_judge),
        }
        print(f"\nStratum {name} ({n_cases} cases):")
        print(f"{'level':<14}{'fields':>8}{'in_F1':>8}{'judge*':>8}")
        print("─" * 38)
        for level in levels:
            print(f"{level:<14}{s_fields[level]:>8.1f}{s_f1[level]:>8.2f}{s_judge[level]:>8.2f}")
        print(f"  F1 peak: '{peak(s_f1)}'   judge peak: '{peak(s_judge)}'")

    # 3. Entanglement correlations
    dist = [abs(p["field_count"] - gold_sizes[p["case_id"]]) for p in points]
    corr_f1 = pearson(dist, [p["field_f1"] for p in points])
    corr_judge = pearson(dist, [p["judge"] for p in points])
    corr_reuse = pearson(dist, [p["reuse_graded"] for p in points])
    print(f"\ncorr(|induced−gold| , metric) over all {len(points)} points:")
    print(f"  in_F1: {corr_f1:+.3f}   judge: {corr_judge:+.3f}   reuse_graded: {corr_reuse:+.3f}")
    print("  (strongly negative for F1 = the metric rewards matching gold size by "
        "construction; near-zero for judge/reuse = those axes are not size-entangled)")

    OUT_PATH.write_text(json.dumps({
        "gold_sizes": gold_sizes,
        "mean_gold_size": round(mean(list(gold_sizes.values())), 2),
        "gold_independent_curves": {
            "judge": judge, "reuse_binary": reuse_b, "reuse_graded": reuse_g,
        },
        "peaks": {"judge": peak(judge), "reuse_binary": peak(reuse_b),
                  "reuse_graded": peak(reuse_g), "field_f1": peak(f1)},
        "strata": strat_out,
        "entanglement_corr": {"field_f1": round(corr_f1, 3), "judge": round(corr_judge, 3),
                              "reuse_graded": round(corr_reuse, 3)},
    }, indent=2))
    print(f"\nSaved to {OUT_PATH}")


if __name__ == "__main__":
    main()
