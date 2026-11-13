"""Pareto efficiency and security values: exact, and the minimax theorem on constant-sum games."""

from __future__ import annotations

import random
from fractions import Fraction as F

from courtroom.gametheory import analyze
from courtroom.gametheory.efficiency import (
    constant_sum_check,
    efficiency,
    maximin,
    minimax_value,
    pareto_cells,
    security_values,
)
from courtroom.gametheory.nash import as_fraction_matrix


def fm(rows):
    return as_fraction_matrix(rows)


def test_matching_pennies_has_value_zero_and_half_half() -> None:
    v, x = maximin(fm([[1, -1], [-1, 1]]))
    assert v == 0 and x == [F(1, 2), F(1, 2)]


def test_rock_paper_scissors_value_zero() -> None:
    v, x = maximin(fm([[0, -1, 1], [1, 0, -1], [-1, 1, 0]]))
    assert v == 0 and x == [F(1, 3)] * 3


def test_a_saddle_point_needs_no_randomising() -> None:
    v, x = maximin(fm([[3, 2], [1, 0]]))
    assert v == 2 and x == [1, 0]


def test_maximin_is_at_least_the_pure_maximin() -> None:
    rng = random.Random(7)
    for _ in range(40):
        m, n = rng.randint(2, 4), rng.randint(2, 4)
        A = fm([[rng.randint(-5, 5) for _ in range(n)] for _ in range(m)])
        v, x = maximin(A)
        assert v >= max(min(r) for r in A)
        assert sum(x) == 1 and all(p >= 0 for p in x)
        # the strategy really guarantees v
        assert all(sum(x[i] * A[i][j] for i in range(m)) >= v for j in range(n))


def test_minimax_theorem_on_random_zero_sum_matrices() -> None:
    """maximin = minimax = the Nash value, in exact arithmetic."""
    rng = random.Random(11)
    for _ in range(60):
        m, n = rng.randint(2, 4), rng.randint(2, 4)
        W = [[F(rng.randint(0, 20), 20) for _ in range(n)] for _ in range(m)]
        lo, _ = maximin(W)
        hi, _ = minimax_value(W)
        assert lo == hi
        res = constant_sum_check(W)
        assert res.theorem_holds
        assert res.maximin == res.minimax
        if res.nash_value is not None:
            assert res.nash_value == res.maximin


def test_minimax_theorem_on_the_projects_own_win_probability_game() -> None:
    from courtroom.cases import get_case
    from courtroom.gametheory import estimate_payoffs

    t = estimate_payoffs(get_case("helix-espionage"), ("aggressive", "conservative", "adaptive"), seeds=tuple(range(6)))
    W = [[next(c for c in t.cells if c.row == r and c.col == k).prosecution_win_rate for k in t.col_strategies] for r in t.row_strategies]
    res = constant_sum_check(W)
    assert res.theorem_holds and res.maximin == res.minimax


def test_pareto_cells_of_a_prisoners_dilemma() -> None:
    A = fm([[3, 0], [5, 1]])
    B = fm([[3, 5], [0, 1]])
    assert sorted(pareto_cells(A, B)) == [(0, 0), (0, 1), (1, 0)]  # everything but mutual defection


def test_prisoners_dilemma_equilibrium_is_dominated_and_flagged() -> None:
    a = analyze(["C", "D"], ["C", "D"], [[3, 0], [5, 1]], [[3, 5], [0, 1]])
    e = efficiency(a)
    assert e.social_dilemma and not e.all_equilibria_efficient
    q = e.equilibria[0]
    assert not q.pareto_efficient
    assert (q.dominated_by[0].row, q.dominated_by[0].col) == ("C", "C")
    assert ("D", "D") not in e.pareto_cells


def test_battle_of_the_sexes_equilibria_are_efficient() -> None:
    a = analyze(["O", "F"], ["O", "F"], [[2, 0], [0, 1]], [[1, 0], [0, 2]])
    e = efficiency(a)
    pure = [q for q in e.equilibria if q.pure]
    assert len(pure) == 2 and all(q.pareto_efficient for q in pure)
    mixed = [q for q in e.equilibria if not q.pure]
    assert mixed and not mixed[0].pareto_efficient  # the mixed equilibrium wastes the gains from agreeing


def test_security_gap_is_the_equilibrium_payoff_minus_the_guaranteed_floor() -> None:
    a = analyze(["C", "D"], ["C", "D"], [[3, 0], [5, 1]], [[3, 5], [0, 1]])
    sr, sc = security_values(a)
    assert sr.mixed_value == 1.0 and sc.mixed_value == 1.0  # defecting guarantees 1
    e = efficiency(a)
    assert e.equilibria[0].security_gap_row == 0.0
