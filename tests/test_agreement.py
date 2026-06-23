import pytest

from prompt2app.agreement import (
    cohens_kappa,
    field_existence_ratings,
    fleiss_kappa,
    interpret,
)


def test_cohens_kappa_perfect():
    assert cohens_kappa([True, False, True, False], [True, False, True, False]) == 1.0


def test_cohens_kappa_chance_level_is_zero():
    # 50% observed agreement with 50/50 marginals → exactly chance → kappa 0.
    assert cohens_kappa([True, True, False, False], [True, False, True, False]) == 0.0


def test_cohens_kappa_unanimous_same_side_is_one():
    assert cohens_kappa([True, True], [True, True]) == 1.0


def test_cohens_kappa_rejects_bad_input():
    with pytest.raises(ValueError):
        cohens_kappa([], [])
    with pytest.raises(ValueError):
        cohens_kappa([True], [True, False])


def test_fleiss_kappa_perfect():
    # 3 raters, 2 items, unanimous on opposite categories → kappa 1.
    assert fleiss_kappa([[3, 0], [0, 3]]) == 1.0


def test_fleiss_kappa_rejects_uneven_raters():
    with pytest.raises(ValueError):
        fleiss_kappa([[3, 0], [2, 0]])


def test_field_existence_ratings_counts_presence():
    annotations = [
        {"cases": [{"inputs": [{"name": "item"}]}]},
        {"cases": [{"inputs": [{"name": "item"}]}]},
        {"cases": [{"inputs": [{"name": "quantity"}]}]},
    ]
    rows = field_existence_ratings(annotations, "inputs")
    # candidates sorted: item (present 2/3), quantity (present 1/3)
    assert rows == [[2, 1], [1, 2]]


def test_interpret_bands():
    assert interpret(0.1) == "poor"
    assert interpret(0.5) == "moderate"
    assert interpret(0.7) == "substantial"
    assert interpret(0.95) == "almost perfect"
