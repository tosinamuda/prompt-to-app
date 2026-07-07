"""Paired statistics for experiment claims (#15).

Every ordering the thesis reports ("bootstrap > severed") must survive a paired test
over cases, not a comparison of two single-run means. Pure functions, deterministic
given a seed, unit-tested offline. Norms: Show Your Work (EMNLP 2019); Adding Error
Bars to Evals (arXiv:2411.00640).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


def paired_deltas(a: list[float], b: list[float]) -> list[float]:
    """Per-case differences a_i - b_i for two conditions measured on the same cases."""
    if len(a) != len(b) or not a:
        raise ValueError("conditions must be non-empty and measured on the same cases")
    return [x - y for x, y in zip(a, b, strict=True)]


def sign_test_p(deltas: list[float]) -> float:
    """Exact two-sided sign test on paired deltas (zeros dropped, binomial p=0.5).

    With n=8 informative cases, 8/8 wins gives p=0.0078 and 7/8 gives p=0.070 —
    the arithmetic behind "orderings on 8 cases are rarely significant".
    """
    signs = [d for d in deltas if d != 0]
    n = len(signs)
    if n == 0:
        return 1.0
    k = sum(1 for d in signs if d > 0)
    tail = min(k, n - k)
    cdf = sum(math.comb(n, i) for i in range(tail + 1)) / 2**n
    return min(1.0, 2 * cdf)


def permutation_test_p(
    deltas: list[float], *, n_permutations: int = 10_000, seed: int = 0,
) -> float:
    """Two-sided sign-flip permutation test on the mean of paired deltas."""
    if not deltas:
        raise ValueError("need at least one delta")
    observed = abs(sum(deltas) / len(deltas))
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_permutations):
        flipped = [d if rng.random() < 0.5 else -d for d in deltas]
        if abs(sum(flipped) / len(flipped)) >= observed:
            hits += 1
    return (hits + 1) / (n_permutations + 1)


def bootstrap_ci(
    values: list[float], *, n_boot: int = 10_000, alpha: float = 0.05, seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap CI for the mean of `values` (resampling cases)."""
    if not values:
        raise ValueError("need at least one value")
    rng = random.Random(seed)
    n = len(values)
    means = sorted(
        sum(rng.choice(values) for _ in range(n)) / n for _ in range(n_boot)
    )
    lo = means[int((alpha / 2) * n_boot)]
    hi = means[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return lo, hi


def pearson(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation; 0.0 when either side is constant or n < 2."""
    n = len(xs)
    if n != len(ys) or n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    vx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    vy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return cov / (vx * vy) if vx and vy else 0.0


@dataclass
class PairedComparison:
    mean_delta: float
    ci_low: float
    ci_high: float
    sign_p: float
    permutation_p: float
    n: int


def compare_paired(a: list[float], b: list[float], *, seed: int = 0) -> PairedComparison:
    """Full paired comparison of condition a vs b measured on the same cases."""
    deltas = paired_deltas(a, b)
    lo, hi = bootstrap_ci(deltas, seed=seed)
    return PairedComparison(
        mean_delta=sum(deltas) / len(deltas),
        ci_low=lo,
        ci_high=hi,
        sign_p=sign_test_p(deltas),
        permutation_p=permutation_test_p(deltas, seed=seed),
        n=len(deltas),
    )
