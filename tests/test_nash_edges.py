"""Review finding T5: edges of the Nash code that mutations got past (a missing column check, weak read as strict dominance)."""

from __future__ import annotations

from fractions import Fraction as F

from courtroom.gametheory.nash import as_fraction_matrix, dominant_strategy, iesds, verify_equilibrium


def M(rows):
    return as_fraction_matrix(rows)


def test_verify_equilibrium_checks_the_column_player_too() -> None:
    # the row player is happy (it is indifferent), but the column player would switch to column 1
    A = M([[1, 1], [1, 1]])
    B = M([[0, 5], [0, 5]])
    assert verify_equilibrium(A, B, [F(1), F(0)], [F(1), F(0)]) is False
    assert verify_equilibrium(A, B, [F(1), F(0)], [F(0), F(1)]) is True


def test_verify_equilibrium_checks_the_row_player_too() -> None:
    A = M([[0, 0], [5, 5]])
    B = M([[1, 1], [1, 1]])
    assert verify_equilibrium(A, B, [F(1), F(0)], [F(1), F(0)]) is False


def test_matching_pennies_equilibrium_is_exactly_one_half() -> None:
    A = M([[1, -1], [-1, 1]])
    B = M([[-1, 1], [1, -1]])
    half = [F(1, 2), F(1, 2)]
    assert verify_equilibrium(A, B, half, half) is True
    assert verify_equilibrium(A, B, [F(1, 3), F(2, 3)], half) is False


def test_weak_dominance_is_not_reported_as_strict() -> None:
    # row 0 is at least as good as row 1 everywhere and strictly better in one column only
    A = M([[3, 1], [3, 0]])
    idx, kind = dominant_strategy(A, "row")
    assert idx == 0 and kind == "weak"


def test_iesds_never_removes_a_weakly_dominated_strategy() -> None:
    A = M([[3, 1], [3, 0]])
    B = M([[1, 1], [1, 1]])
    rows, cols = iesds(A, B)
    assert rows == [0, 1] and cols == [0, 1]
    strict = M([[3, 1], [2, 0]])
    assert iesds(strict, B)[0] == [0]
