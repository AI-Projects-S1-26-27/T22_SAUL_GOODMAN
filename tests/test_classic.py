"""The 2x2 classifier against textbook matrices, with and without noise, and on a measured table."""

from __future__ import annotations

import pytest

from courtroom.gametheory.bootstrap import CellSamples
from courtroom.gametheory.classic import (
    BOS,
    CHICKEN,
    DOMINANCE,
    LABELS,
    OTHER,
    PD,
    PENNIES,
    STAG,
    classify_2x2,
    classify_case,
    classify_table,
)

# (row payoffs, column payoffs); row 0/1 and column 0/1 are the two plays of each side.
TEXTBOOK = {
    PD: ([[3, 0], [5, 1]], [[3, 5], [0, 1]]),  # cooperate, defect
    STAG: ([[4, 0], [3, 3]], [[4, 3], [0, 3]]),  # stag, hare
    BOS: ([[3, 0], [0, 2]], [[2, 0], [0, 3]]),  # Bach, Stravinsky
    CHICKEN: ([[0, -1], [1, -10]], [[0, 1], [-1, -10]]),  # swerve, straight
    PENNIES: ([[1, -1], [-1, 1]], [[-1, 1], [1, -1]]),
    DOMINANCE: ([[3, 2], [1, 0]], [[3, 1], [2, 0]]),
}


@pytest.mark.parametrize("label", list(TEXTBOOK))
def test_textbook_game_is_named_correctly(label: str) -> None:
    A, B = TEXTBOOK[label]
    assert classify_2x2(A, B).label == label


def test_relabelling_the_strategies_does_not_change_the_name() -> None:
    """The name depends on the order of the payoffs, not on which play is called 0 or 1."""
    for label, (A, B) in TEXTBOOK.items():
        swapped_a = [A[1], A[0]]
        swapped_b = [B[1], B[0]]
        assert classify_2x2(swapped_a, swapped_b).label == label
        col_a = [[r[1], r[0]] for r in A]
        col_b = [[r[1], r[0]] for r in B]
        assert classify_2x2(col_a, col_b).label == label


def test_scaling_and_shifting_payoffs_does_not_change_the_name() -> None:
    for label, (A, B) in TEXTBOOK.items():
        A2 = [[7 * v + 100 for v in r] for r in A]
        B2 = [[0.5 * v - 3 for v in r] for r in B]
        assert classify_2x2(A2, B2).label == label


def test_a_tie_where_a_strict_order_is_needed_gives_other() -> None:
    _, B = TEXTBOOK[PD]
    tied = [[3, 0], [3, 1]]  # temptation equals reward: no longer a dilemma
    assert classify_2x2(tied, B).label != PD


def test_noise_larger_than_the_gaps_gives_other_never_a_classic_game() -> None:
    A, B = TEXTBOOK[PD]
    big = [[5.0, 5.0], [5.0, 5.0]]
    assert classify_2x2(A, B, big, big).label == OTHER


def test_small_noise_keeps_the_classic_name() -> None:
    A, B = TEXTBOOK[BOS]
    small = [[0.01, 0.01], [0.01, 0.01]]
    assert classify_2x2(A, B, small, small).label == BOS


def test_prisoners_dilemma_reports_its_equilibrium() -> None:
    A, B = TEXTBOOK[PD]
    assert classify_2x2(A, B).pure_equilibria == [(1, 1)]


def test_bos_and_chicken_are_different_games() -> None:
    assert classify_2x2(*TEXTBOOK[BOS]).label != classify_2x2(*TEXTBOOK[CHICKEN]).label


def test_classify_table_covers_every_pair_of_styles_per_side() -> None:
    rows = ["a", "b", "c", "d"]
    A = [[float(i * 4 + j) for j in range(4)] for i in range(4)]
    B = [[float(-(i * 4 + j)) for j in range(4)] for i in range(4)]
    assert len(classify_table(rows, rows, A, B)) == 36


def _samples(table: dict[tuple[str, str], tuple[float, float]], n: int) -> dict[tuple[str, str], CellSamples]:
    out = {}
    for (r, c), (a, b) in table.items():
        wobble = [0.01 * ((k % 3) - 1) for k in range(n)]
        out[(r, c)] = CellSamples(row=r, col=c, row_utilities=[a + w for w in wobble], col_utilities=[b + w for w in wobble])
    return out


def test_classify_case_on_a_planted_prisoners_dilemma_is_stable_under_resampling() -> None:
    A, B = TEXTBOOK[PD]
    styles = ["x", "y"]
    table = {(styles[i], styles[j]): (A[i][j], B[i][j]) for i in range(2) for j in range(2)}
    res = classify_case("planted", _samples(table, 30), styles, styles, n_resamples=40)
    assert len(res.subgames) == 1
    assert res.subgames[0].label == PD and res.subgames[0].stability == 1.0
    assert set(res.label_counts) == set(LABELS)


def test_classify_case_is_deterministic() -> None:
    A, B = TEXTBOOK[CHICKEN]
    styles = ["x", "y"]
    table = {(styles[i], styles[j]): (A[i][j], B[i][j]) for i in range(2) for j in range(2)}
    s = _samples(table, 20)
    assert classify_case("p", s, styles, styles, 25).model_dump() == classify_case("p", s, styles, styles, 25).model_dump()
