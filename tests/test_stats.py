import pytest

from prompt2app.stats import (
    bootstrap_ci,
    compare_paired,
    paired_deltas,
    pearson,
    permutation_test_p,
    sign_test_p,
)


def test_paired_deltas_and_validation():
    assert paired_deltas([1.0, 2.0], [0.5, 2.5]) == [0.5, -0.5]
    with pytest.raises(ValueError):
        paired_deltas([1.0], [1.0, 2.0])
    with pytest.raises(ValueError):
        paired_deltas([], [])


def test_sign_test_exact_values_at_n8():
    # The arithmetic quoted in the methodology plan: 8/8 wins → p=2/256; 7/8 → p=18/256.
    assert sign_test_p([1.0] * 8) == pytest.approx(2 / 256)
    assert sign_test_p([1.0] * 7 + [-1.0]) == pytest.approx(18 / 256)


def test_sign_test_drops_zeros_and_handles_all_zero():
    assert sign_test_p([0.0, 0.0, 1.0, 1.0]) == pytest.approx(0.5)  # n=2, k=2 → 2*(1/4)
    assert sign_test_p([0.0, 0.0]) == 1.0


def test_permutation_test_detects_strong_effect_and_not_noise():
    strong = permutation_test_p([0.5] * 10, seed=1)
    assert strong < 0.01
    balanced = permutation_test_p([0.5, -0.5, 0.4, -0.4, 0.3, -0.3], seed=1)
    assert balanced > 0.3


def test_bootstrap_ci_constant_and_contains_mean():
    assert bootstrap_ci([2.0, 2.0, 2.0], seed=1) == (2.0, 2.0)
    lo, hi = bootstrap_ci([1.0, 2.0, 3.0, 4.0], seed=1)
    assert lo <= 2.5 <= hi


def test_pearson_known_values():
    assert pearson([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)
    assert pearson([1, 2, 3], [6, 4, 2]) == pytest.approx(-1.0)
    assert pearson([1, 1, 1], [2, 4, 6]) == 0.0
    assert pearson([1.0], [2.0]) == 0.0


def test_compare_paired_bundle():
    result = compare_paired([0.9] * 8, [0.8] * 8, seed=1)
    assert result.mean_delta == pytest.approx(0.1)
    assert result.n == 8
    assert result.sign_p == pytest.approx(2 / 256)
    assert result.ci_low <= result.mean_delta <= result.ci_high
