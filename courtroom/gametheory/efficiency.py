"""Pareto efficiency and security (maximin) values of a measured game, in exact arithmetic.

Two lecture ideas, computed on the project's own tables:

* **Pareto optimality.** A cell is Pareto-efficient if no other cell is at least as good for both sides and better for one.
  An equilibrium whose payoffs some cell beats for *both* sides is Pareto-dominated: the prisoner's-dilemma lesson.
* **Minimax / maximin.** The *security value* of a side is the best payoff it can guarantee whatever the other side does,
  allowing it to randomise. In a constant-sum game (one side's gain is the other's loss) the two sides' security values
  meet at one number, the value of the game, and it equals the Nash value (the minimax theorem). The real courtroom game
  is not constant-sum, so there the security value is only a floor, and the gap to the equilibrium payoff is reported.

Everything is in ``fractions.Fraction``; the maximin is found by enumerating the vertices of its linear program, so it is
exact, not an approximation.
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
from itertools import combinations

from pydantic import BaseModel, ConfigDict

from courtroom.gametheory.nash import GameAnalysis, Matrix, as_fraction_matrix, solve


def _fs(x: Fraction) -> str:
    return f"{x.numerator}/{x.denominator}" if x.denominator != 1 else str(x.numerator)


# --------------------------------------------------------------------------- maximin (security values)


def maximin(A: Matrix) -> tuple[Fraction, list[Fraction]]:
    """The best payoff the row player can guarantee with a mixed strategy, and a strategy that guarantees it.

    Solves ``max v`` subject to ``sum_i x_i A[i][j] >= v`` for every column ``j``, ``x >= 0``, ``sum x = 1``. The optimum sits at
    a vertex of that polytope, so we try every choice of ``k`` rows to mix over and ``k`` columns that bind, solve the
    ``(k+1) x (k+1)`` system exactly, keep the feasible solutions and take the best ``v``.
    """
    m, n = len(A), len(A[0])
    best: tuple[Fraction, list[Fraction]] | None = None
    for k in range(1, min(m, n) + 1):
        for I in combinations(range(m), k):  # noqa: E741 - supports, standard notation
            for J in combinations(range(n), k):
                M = [[A[i][j] for i in I] + [Fraction(-1)] for j in J] + [[Fraction(1)] * k + [Fraction(0)]]
                sol = solve(M, [Fraction(0)] * k + [Fraction(1)])
                if sol is None:
                    continue
                x = [Fraction(0)] * m
                for idx, i in enumerate(I):
                    x[i] = sol[idx]
                v = sol[k]
                if any(p < 0 for p in x):
                    continue
                if any(sum((x[i] * A[i][j] for i in range(m)), Fraction(0)) < v for j in range(n)):
                    continue
                if best is None or v > best[0]:
                    best = (v, x)
    assert best is not None  # a pure maximin strategy is always a vertex
    return best


def _transpose_neg(M: Matrix) -> Matrix:
    return [[-M[i][j] for i in range(len(M))] for j in range(len(M[0]))]


def minimax_value(A: Matrix) -> tuple[Fraction, list[Fraction]]:
    """The least the column player can hold the row player to (the row player's payoff matrix is ``A``), and its strategy."""
    v, y = maximin(_transpose_neg(A))
    return -v, y


class Security(BaseModel):
    model_config = ConfigDict(frozen=True)
    pure_value: float
    pure_strategy: str
    mixed_value: float
    mixed_value_exact: str
    mixed_strategy: dict[str, str]  # exact weights, zero weights left out


class ConstantSum(BaseModel):
    """The win-probability game: the Accuser's chance of winning against the Defender's, which always sum to one."""

    model_config = ConfigDict(frozen=True)
    maximin: float  # what the Accuser can guarantee
    minimax: float  # what the Defender can hold the Accuser to
    nash_value: float | None  # the Accuser's win probability at a Nash equilibrium
    theorem_holds: bool
    saddle_point: bool  # True if pure strategies already meet (no randomising needed)


def _pure_maximin(A: Matrix, labels: Sequence[str]) -> tuple[Fraction, str]:
    mins = [min(r) for r in A]
    k = max(range(len(A)), key=lambda i: (mins[i], -i))
    return mins[k], labels[k]


def security_values(analysis: GameAnalysis) -> tuple[Security, Security]:
    """(Accuser, Defender) security values for the general-sum measured game."""
    A = as_fraction_matrix(analysis.A)
    B = as_fraction_matrix(analysis.B)
    out = []
    # Accuser: rows of A. Defender: the columns of B, so transpose to make the Defender the row player.
    Bt = [[B[i][j] for i in range(len(B))] for j in range(len(B[0]))]
    for M, labels in ((A, analysis.row_labels), (Bt, analysis.col_labels)):
        pv, ps = _pure_maximin(M, labels)
        v, x = maximin(M)
        out.append(
            Security(
                pure_value=float(pv),
                pure_strategy=ps,
                mixed_value=float(v),
                mixed_value_exact=_fs(v),
                mixed_strategy={labels[i]: _fs(p) for i, p in enumerate(x) if p != 0},
            )
        )
    return out[0], out[1]


def constant_sum_check(W: Sequence[Sequence[float | Fraction]]) -> ConstantSum:
    """Minimax theorem on a win-probability matrix ``W`` (the Accuser's win rate; the Defender's is ``1 - W``)."""
    from courtroom.gametheory.nash import support_enumeration

    Wf = as_fraction_matrix(W)
    lo, _ = maximin(Wf)
    hi, _ = minimax_value(Wf)
    neg = [[-v for v in row] for row in Wf]
    eqs = support_enumeration(Wf, neg)
    nash: Fraction | None = None
    if eqs:
        x, y = eqs[0]
        nash = sum((x[i] * Wf[i][j] * y[j] for i in range(len(x)) for j in range(len(y))), Fraction(0))
    saddle = any(
        Wf[i][j] == min(Wf[i]) and Wf[i][j] == max(Wf[r][j] for r in range(len(Wf))) for i in range(len(Wf)) for j in range(len(Wf[0]))
    )
    return ConstantSum(
        maximin=float(lo),
        minimax=float(hi),
        nash_value=float(nash) if nash is not None else None,
        theorem_holds=(lo == hi) and (nash is None or nash == lo),
        saddle_point=saddle,
    )


# --------------------------------------------------------------------------- Pareto


def pareto_cells(A: Matrix, B: Matrix) -> list[tuple[int, int]]:
    """Cells no other cell beats for both sides (at least as good for both, better for one)."""
    cells = [(i, j) for i in range(len(A)) for j in range(len(A[0]))]
    return [
        (i, j)
        for i, j in cells
        if not any(
            A[k][q] >= A[i][j] and B[k][q] >= B[i][j] and (A[k][q] > A[i][j] or B[k][q] > B[i][j]) for k, q in cells
        )
    ]


class Dominator(BaseModel):
    model_config = ConfigDict(frozen=True)
    row: str
    col: str
    row_gain: float
    col_gain: float


class EquilibriumEfficiency(BaseModel):
    model_config = ConfigDict(frozen=True)
    row_mix: dict[str, str]
    col_mix: dict[str, str]
    row_payoff: float
    col_payoff: float
    pure: bool
    pareto_efficient: bool
    strictly_dominated: bool  # some cell is better for BOTH sides: the prisoner's-dilemma situation
    dominated_by: list[Dominator]  # cells better for both sides, best joint gain first
    security_gap_row: float  # equilibrium payoff minus the side's mixed security value
    security_gap_col: float


class Efficiency(BaseModel):
    model_config = ConfigDict(frozen=True)
    row_labels: list[str]
    col_labels: list[str]
    pareto_cells: list[tuple[str, str]]
    equilibria: list[EquilibriumEfficiency]
    social_dilemma: bool  # some equilibrium is dominated for both sides by a cell
    all_equilibria_efficient: bool
    row_security: Security
    col_security: Security


def efficiency(analysis: GameAnalysis) -> Efficiency:
    A = as_fraction_matrix(analysis.A)
    B = as_fraction_matrix(analysis.B)
    rl, cl = analysis.row_labels, analysis.col_labels
    sec_r, sec_c = security_values(analysis)
    pc = pareto_cells(A, B)
    eqs: list[EquilibriumEfficiency] = []
    for e in analysis.equilibria:
        u, v = Fraction(repr(e.row_payoff)), Fraction(repr(e.col_payoff))
        better = [
            Dominator(row=rl[i], col=cl[j], row_gain=float(A[i][j] - u), col_gain=float(B[i][j] - v))
            for i in range(len(A))
            for j in range(len(A[0]))
            if A[i][j] >= u and B[i][j] >= v and (A[i][j] > u or B[i][j] > v)
        ]
        # "dominated" in the dilemma sense: strictly better for both
        strict = [d for d in better if d.row_gain > 0 and d.col_gain > 0]
        eqs.append(
            EquilibriumEfficiency(
                row_mix=e.row_mix_exact,
                col_mix=e.col_mix_exact,
                row_payoff=e.row_payoff,
                col_payoff=e.col_payoff,
                pure=e.pure,
                pareto_efficient=not better,
                strictly_dominated=bool(strict),
                dominated_by=sorted(strict or better, key=lambda d: -(d.row_gain + d.col_gain))[:3],
                security_gap_row=round(e.row_payoff - sec_r.mixed_value, 6),
                security_gap_col=round(e.col_payoff - sec_c.mixed_value, 6),
            )
        )
    return Efficiency(
        row_labels=list(rl),
        col_labels=list(cl),
        pareto_cells=[(rl[i], cl[j]) for i, j in pc],
        equilibria=eqs,
        social_dilemma=any(q.strictly_dominated for q in eqs),
        all_equilibria_efficient=all(q.pareto_efficient for q in eqs) if eqs else True,
        row_security=sec_r,
        col_security=sec_c,
    )
