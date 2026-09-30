"""Decomposition of a change in a product of factors into additive effects.

The identity used in this project:

    spend = customers x active_rate x txns_per_active x avg_ticket

All functions are pure and work on any number of factors, so they can be tested on
small hand-checked examples.
"""
from __future__ import annotations

import math
from itertools import permutations
from typing import Sequence

FACTORS = ("customers", "active_rate", "txns_per_active", "avg_ticket")


def log_mean(a: float, b: float) -> float:
    """Logarithmic mean of two positive numbers: (a - b) / (ln a - ln b).

    It always lies between a and b. When a equals b the formula is 0/0 and the limit
    is a itself.
    """
    if a <= 0 or b <= 0:
        raise ValueError("log_mean needs positive inputs")
    if a == b:
        return a
    return (a - b) / (math.log(a) - math.log(b))


def product(values: Sequence[float]) -> float:
    return math.prod(values)


def lmdi_effects(f0: Sequence[float], f1: Sequence[float]) -> list[float]:
    """Additive LMDI: effect_k = L(V1, V0) * ln(f1_k / f0_k), where V is the product.

    The logs of the factor ratios add up to ln(V1 / V0), and L(V1, V0) * ln(V1 / V0)
    is V1 - V0 by definition of the log mean. So the effects add up exactly.
    """
    if min(*f0, *f1) <= 0:
        raise ValueError("LMDI needs every factor to be positive in both periods")
    weight = log_mean(product(f1), product(f0))
    return [weight * math.log(b / a) for a, b in zip(f0, f1)]


def sequential_effects(
    f0: Sequence[float], f1: Sequence[float], order: Sequence[int] | None = None
) -> list[float]:
    """Sequential substitution: move one factor at a time from its old to its new value.

    `order` is the order in which factors are switched (indices into f0). The result
    depends on that order, which is the main weakness of the method. Effects are
    returned in the original factor positions and always add up to V1 - V0.
    """
    order = list(range(len(f0))) if order is None else list(order)
    current = list(f0)
    effects = [0.0] * len(f0)
    for k in order:
        before = product(current)
        current[k] = f1[k]
        effects[k] = product(current) - before
    return effects


def shapley_effects(f0: Sequence[float], f1: Sequence[float]) -> list[float]:
    """Average of sequential substitution over every possible factor order.

    Used only as a cross-check: it removes the order dependence by brute force and
    should land close to LMDI.
    """
    n = len(f0)
    totals = [0.0] * n
    orders = list(permutations(range(n)))
    for order in orders:
        for k, effect in enumerate(sequential_effects(f0, f1, order)):
            totals[k] += effect
    return [t / len(orders) for t in totals]


def decompose(f0: Sequence[float], f1: Sequence[float]) -> tuple[str, list[float]]:
    """LMDI where it is defined, otherwise sequential substitution in factor order."""
    if min(*f0, *f1) > 0:
        return "lmdi", lmdi_effects(f0, f1)
    return "sequential_fallback", sequential_effects(f0, f1)


def factors_from_totals(
    customers: float, active: float, txns: float, spend: float
) -> tuple[float, float, float, float]:
    """Turn the four raw totals into the four factors. A zero denominator gives 0."""
    active_rate = active / customers if customers > 0 else 0.0
    txns_per_active = txns / active if active > 0 else 0.0
    avg_ticket = spend / txns if txns > 0 else 0.0
    return float(customers), active_rate, txns_per_active, avg_ticket
