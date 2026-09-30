"""Unit tests for the pure decomposition functions in src/decomposition.py."""
import math

import pytest

from src.decomposition import (
    decompose,
    factors_from_totals,
    lmdi_effects,
    log_mean,
    product,
    sequential_effects,
    shapley_effects,
)

# (customers, active rate, txns per active, avg ticket) in two periods
CASES = [
    ((1000, 0.80, 10.0, 50.0), (1100, 0.75, 12.0, 45.0)),
    ((10127, 1.0, 19.06, 66.0), (8500, 0.999, 14.38, 69.5)),
    ((50, 0.5, 2.0, 10.0), (500, 0.9, 1.0, 300.0)),
    ((3, 1.0, 1.0, 1.0), (1, 0.2, 7.5, 0.01)),
]


def total_change(f0, f1):
    return product(f1) - product(f0)


@pytest.mark.parametrize("f0, f1", CASES)
@pytest.mark.parametrize("method", [lmdi_effects, sequential_effects, shapley_effects])
def test_effects_sum_to_total_change(method, f0, f1):
    effects = method(f0, f1)
    assert len(effects) == 4
    assert math.isclose(sum(effects), total_change(f0, f1), rel_tol=1e-12, abs_tol=1e-9)


@pytest.mark.parametrize("method", [lmdi_effects, sequential_effects, shapley_effects])
def test_zero_change_gives_zero_effects(method):
    f = (1000, 0.8, 10.0, 50.0)
    assert method(f, f) == [0.0, 0.0, 0.0, 0.0]


@pytest.mark.parametrize("changed", [0, 1, 2, 3])
@pytest.mark.parametrize("method", [lmdi_effects, sequential_effects, shapley_effects])
def test_single_factor_change_is_fully_attributed_to_that_factor(method, changed):
    f0 = [1000, 0.8, 10.0, 50.0]
    f1 = list(f0)
    f1[changed] = f0[changed] * 0.7
    effects = method(f0, f1)
    for k, effect in enumerate(effects):
        if k == changed:
            assert math.isclose(effect, total_change(f0, f1), rel_tol=1e-12)
        else:
            assert abs(effect) < 1e-9


def test_offsetting_changes_give_effects_that_cancel():
    # customers double, ticket halves: spend is unchanged but the effects are not zero
    f0, f1 = (100, 1.0, 10.0, 40.0), (200, 1.0, 10.0, 20.0)
    effects = lmdi_effects(f0, f1)
    assert math.isclose(effects[0], -effects[3], rel_tol=1e-12)
    assert effects[0] > 0
    assert abs(sum(effects)) < 1e-9


def test_lmdi_does_not_depend_on_factor_order():
    f0, f1 = CASES[0]
    forward = lmdi_effects(f0, f1)
    backward = lmdi_effects(f0[::-1], f1[::-1])[::-1]
    assert forward == pytest.approx(backward, rel=1e-12)


def test_sequential_depends_on_factor_order_but_still_sums():
    f0, f1 = CASES[0]
    forward = sequential_effects(f0, f1, order=[0, 1, 2, 3])
    backward = sequential_effects(f0, f1, order=[3, 2, 1, 0])
    assert not math.isclose(forward[0], backward[0], rel_tol=1e-6)
    assert math.isclose(sum(forward), sum(backward), rel_tol=1e-12)


def test_lmdi_lies_between_the_two_extreme_sequential_orders():
    f0, f1 = CASES[1]
    lmdi = lmdi_effects(f0, f1)
    forward = sequential_effects(f0, f1, order=[0, 1, 2, 3])
    backward = sequential_effects(f0, f1, order=[3, 2, 1, 0])
    for k in (0, 2, 3):
        assert min(forward[k], backward[k]) <= lmdi[k] <= max(forward[k], backward[k])


def test_log_mean_properties():
    assert log_mean(5.0, 5.0) == 5.0
    assert log_mean(2.0, 8.0) == pytest.approx(log_mean(8.0, 2.0))
    assert 2.0 < log_mean(2.0, 8.0) < 8.0
    assert log_mean(2.0, 8.0) < (2.0 + 8.0) / 2  # below the arithmetic mean
    with pytest.raises(ValueError):
        log_mean(0.0, 1.0)


def test_lmdi_rejects_a_zero_factor():
    with pytest.raises(ValueError):
        lmdi_effects((100, 1.0, 10.0, 40.0), (0, 0.0, 0.0, 0.0))


def test_zero_factor_falls_back_to_sequential_and_still_sums():
    # every customer leaves: the whole change belongs to the customers factor
    f0 = (100, 0.9, 10.0, 40.0)
    f1 = factors_from_totals(customers=0, active=0, txns=0.0, spend=0.0)
    method, effects = decompose(f0, f1)
    assert method == "sequential_fallback"
    assert math.isclose(effects[0], -product(f0), rel_tol=1e-12)
    assert effects[1:] == [0.0, 0.0, 0.0]


def test_decompose_uses_lmdi_when_all_factors_are_positive():
    method, effects = decompose(*CASES[0])
    assert method == "lmdi"
    assert effects == lmdi_effects(*CASES[0])


def test_factors_multiply_back_to_spend():
    factors = factors_from_totals(customers=200, active=150, txns=3000.0, spend=180000.0)
    assert factors == (200.0, 0.75, 20.0, 60.0)
    assert math.isclose(product(factors), 180000.0, rel_tol=1e-12)


def test_worked_two_period_example():
    """A hand-checkable example: four factors, two periods, known answers."""
    f0 = (1000, 0.80, 10.0, 50.0)   # spend 400,000
    f1 = (1100, 0.75, 12.0, 45.0)   # spend 445,500
    assert product(f0) == pytest.approx(400_000)
    assert product(f1) == pytest.approx(445_500)
    weight = log_mean(445_500, 400_000)
    assert round(weight) == 422_342
    lmdi = [round(e) for e in lmdi_effects(f0, f1)]
    assert lmdi == [40_253, -27_257, 77_002, -44_498]
    assert sum(lmdi) == 45_500
    seq = [round(e) for e in sequential_effects(f0, f1)]
    assert seq == [40_000, -27_500, 82_500, -49_500]
