"""Which classic game is this?  A classifier for 2x2 games, and its use on the measured 4x4 tables.

The lecture games (prisoner's dilemma, stag hunt, battle of the sexes, chicken, matching pennies) are defined by the *order*
of the payoffs, not their size. This module reads that order off a 2x2 game and names it, so the project's own measured
games can be compared with the textbook ones. Nothing here changes a case, a payoff or a rule: it only reads results.

Payoffs measured from trials are noisy, so every comparison is made through a tolerance tied to the standard errors:
cell x is "better than" cell y only if the gap is more than ``z`` standard errors of the difference. A gap inside that
tolerance is a tie, and a game that needs a strict order where the data has a tie is called ``other``. That is deliberate:
the classifier would rather say "not sure" than invent a textbook game.

Everything is a deterministic function of its inputs.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Sequence
from itertools import combinations

from pydantic import BaseModel, ConfigDict

from courtroom.gametheory.bootstrap import CellSamples

PD = "prisoners-dilemma"
STAG = "stag-hunt"
BOS = "battle-of-the-sexes"
CHICKEN = "chicken"
PENNIES = "matching-pennies"
DOMINANCE = "dominance-solvable"
OTHER = "other"

LABELS = (PD, STAG, BOS, CHICKEN, PENNIES, DOMINANCE, OTHER)

PLAIN = {
    PD: "Prisoner's dilemma",
    STAG: "Stag hunt",
    BOS: "Battle of the sexes",
    CHICKEN: "Chicken",
    PENNIES: "Matching pennies",
    DOMINANCE: "Dominance-solvable (one clear best play)",
    OTHER: "None of the classic games",
}

Z = 2.0  # a gap counts only above two standard errors of the difference
FLOOR = 1e-9  # so that exact (zero-error) payoffs still need a real gap, not rounding dust

Grid = Sequence[Sequence[float]]


class Classic(BaseModel):
    """The name of one 2x2 game and the evidence for it."""

    model_config = ConfigDict(frozen=True)
    label: str
    reason: str
    pure_equilibria: list[tuple[int, int]]
    ties: int  # pairs of payoffs (per player) the data cannot tell apart; 0 means every order was decided


def _zeros() -> list[list[float]]:
    return [[0.0, 0.0], [0.0, 0.0]]


class _G:
    """A 2x2 game with significance-aware comparisons."""

    def __init__(self, A: Grid, B: Grid, SA: Grid | None, SB: Grid | None, z: float) -> None:
        self.A, self.B = A, B
        self.SA = SA if SA is not None else _zeros()
        self.SB = SB if SB is not None else _zeros()
        self.z = z

    def _gt(self, M: Grid, S: Grid, p: tuple[int, int], q: tuple[int, int]) -> bool:
        return M[p[0]][p[1]] - M[q[0]][q[1]] > self.z * math.hypot(S[p[0]][p[1]], S[q[0]][q[1]]) + FLOOR

    def ga(self, p: tuple[int, int], q: tuple[int, int]) -> bool:
        """The row player strictly prefers cell p to cell q."""
        return self._gt(self.A, self.SA, p, q)

    def gb(self, p: tuple[int, int], q: tuple[int, int]) -> bool:
        """The column player strictly prefers cell p to cell q."""
        return self._gt(self.B, self.SB, p, q)

    def pure_nash(self) -> list[tuple[int, int]]:
        """Cells where neither player has a *significant* gain from switching."""
        return [
            (i, j)
            for i in (0, 1)
            for j in (0, 1)
            if not self.ga((1 - i, j), (i, j)) and not self.gb((i, 1 - j), (i, j))
        ]

    def row_dominant(self) -> int | None:
        return next((i for i in (0, 1) if self.ga((i, 0), (1 - i, 0)) and self.ga((i, 1), (1 - i, 1))), None)

    def col_dominant(self) -> int | None:
        return next((j for j in (0, 1) if self.gb((0, j), (0, 1 - j)) and self.gb((1, j), (1, 1 - j))), None)

    def ties(self) -> int:
        cells = [(i, j) for i in (0, 1) for j in (0, 1)]
        n = 0
        for p, q in combinations(cells, 2):
            if not self.ga(p, q) and not self.ga(q, p):
                n += 1
            if not self.gb(p, q) and not self.gb(q, p):
                n += 1
        return n

    def security(self, M: Grid, S: Grid, strategy: int, row: bool) -> tuple[int, int]:
        """The cell where this strategy pays least (its worst case)."""
        cells = [(strategy, j) for j in (0, 1)] if row else [(i, strategy) for i in (0, 1)]
        return min(cells, key=lambda c: (M[c[0]][c[1]], c))


def classify_2x2(
    A: Grid,
    B: Grid,
    SA: Grid | None = None,
    SB: Grid | None = None,
    z: float = Z,
    names: tuple[tuple[str, str], tuple[str, str]] | None = None,
) -> Classic:
    """Name a 2x2 game by the order of its payoffs.

    ``A[i][j]`` is the row player's payoff and ``B[i][j]`` the column player's when row plays ``i`` and column plays ``j``.
    ``SA``/``SB`` are the standard errors of those payoffs (zero for an exact game such as a textbook matrix).
    """
    g = _G(A, B, SA, SB, z)
    rn, cn = names if names else (("row 0", "row 1"), ("col 0", "col 1"))
    ties = g.ties()
    ne = g.pure_nash()

    def done(label: str, reason: str) -> Classic:
        return Classic(label=label, reason=reason, pure_equilibria=ne, ties=ties)

    rd, cd = g.row_dominant(), g.col_dominant()

    # Prisoner's dilemma: both sides have a dominant play, and the outcome they land on is worse for both than the other corner.
    if rd is not None and cd is not None:
        cr, cc = 1 - rd, 1 - cd  # the "cooperative" strategies
        row_order = [(rd, cc), (cr, cc), (rd, cd), (cr, cd)]  # temptation > reward > punishment > sucker
        col_order = [(cr, cd), (cr, cc), (rd, cd), (rd, cc)]
        if all(g.ga(row_order[k], row_order[k + 1]) for k in range(3)) and all(
            g.gb(col_order[k], col_order[k + 1]) for k in range(3)
        ):
            return done(
                PD,
                f"Each side does best by playing {rn[rd]} / {cn[cd]} whatever the other does, yet both would be better off if both "
                f"played {rn[cr]} / {cn[cc]}.",
            )
        return done(DOMINANCE, f"Each side has one best play ({rn[rd]}, {cn[cd]}) and there is no dilemma: nobody is worse off for it.")

    # Dominance-solvable: one side has a dominant play and the other has a clear best reply to it.
    if rd is not None and (g.gb((rd, 0), (rd, 1)) or g.gb((rd, 1), (rd, 0))):
        return done(DOMINANCE, f"The row side has a dominant play ({rn[rd]}); the other side's best reply to it is clear.")
    if cd is not None and (g.ga((0, cd), (1, cd)) or g.ga((1, cd), (0, cd))):
        return done(DOMINANCE, f"The column side has a dominant play ({cn[cd]}); the other side's best reply to it is clear.")

    if not ne:
        return done(PENNIES, "Neither side has a stable pure choice: whatever one does, the other wants to switch, and round again.")

    if len(ne) == 2 and ne[1] == (1 - ne[0][0], 1 - ne[0][1]):
        n1, n2 = ne
        m1, m2 = (n1[0], n2[1]), (n2[0], n1[1])  # the two corners that are not equilibria
        row_pref = n1 if g.ga(n1, n2) else n2 if g.ga(n2, n1) else None
        col_pref = n1 if g.gb(n1, n2) else n2 if g.gb(n2, n1) else None

        if row_pref is not None and row_pref == col_pref:
            # Both sides agree which equilibrium is better. A stag hunt if the better one is also the riskier one for both.
            other = n2 if row_pref == n1 else n1
            risky = True
            for M, S, idx, is_row in ((A, g.SA, 0, True), (B, g.SB, 1, False)):
                mine = row_pref[idx]
                safe = other[idx]
                c_mine = g.security(M, S, mine, is_row)
                c_safe = g.security(M, S, safe, is_row)
                better = g.ga if is_row else g.gb
                risky = risky and better(c_safe, c_mine)
            if risky:
                return done(
                    STAG,
                    "Two stable outcomes, and both sides prefer the same one, but it only works if both go for it: "
                    "the safer play pays less when it succeeds and more when it fails.",
                )
            return done(OTHER, "Two stable outcomes and both sides prefer the same one, with no safety trade-off: a plain coordination game.")

        if row_pref is not None and col_pref is not None and row_pref != col_pref:
            both_below = all(g.ga(n, m) for n in (n1, n2) for m in (m1, m2)) and all(
                g.gb(n, m) for n in (n1, n2) for m in (m1, m2)
            )
            if both_below:
                return done(
                    BOS,
                    "Two stable outcomes and each side prefers a different one; failing to agree is worse for both than giving way.",
                )
            chicken = True
            for better, cells in ((g.ga, (row_pref, n1 if row_pref == n2 else n2)), (g.gb, (col_pref, n1 if col_pref == n2 else n2))):
                n_best, n_worst = cells
                hi, lo = (m1, m2) if better(m1, n_worst) else (m2, m1)
                chicken = chicken and better(n_best, hi) and better(hi, n_worst) and better(n_worst, lo)
            if chicken:
                return done(
                    CHICKEN,
                    "Two stable outcomes in which one side gives way, each side prefers to be the one who does not, and both pushing on is the worst of all.",
                )
    return done(OTHER, "The payoffs do not have the order of any classic game, or the data cannot separate them.")


# --------------------------------------------------------------------------- the measured 4x4 tables


class SubGame(BaseModel):
    """One 2x2 corner of a measured 4x4 table: two styles for the Accuser against two for the Defender."""

    model_config = ConfigDict(frozen=True)
    rows: tuple[str, str]
    cols: tuple[str, str]
    label: str
    reason: str
    stability: float  # share of seed resamples that give the same label
    label_counts: dict[str, int]
    ties: int


class CaseClassic(BaseModel):
    model_config = ConfigDict(frozen=True)
    case_id: str
    n_seeds: int
    n_resamples: int
    z: float
    surprises: bool
    row_strategies: list[str]
    col_strategies: list[str]
    A: list[list[float]]
    B: list[list[float]]
    SA: list[list[float]]
    SB: list[list[float]]
    subgames: list[SubGame]
    label_counts: dict[str, int]  # how many of the 36 sub-games carry each label (baseline seeds)
    mean_stability: float


def _stats(xs: Sequence[float], index: Sequence[int] | None) -> tuple[float, float]:
    picked = xs if index is None else [xs[i] for i in index]
    n = len(picked)
    mean = sum(picked) / n
    if n < 2:
        return mean, 0.0
    var = sum((x - mean) ** 2 for x in picked) / (n - 1)
    return mean, math.sqrt(var / n)


def table_stats(
    samples: dict[tuple[str, str], CellSamples],
    rows: Sequence[str],
    cols: Sequence[str],
    index: Sequence[int] | None = None,
) -> tuple[list[list[float]], list[list[float]], list[list[float]], list[list[float]]]:
    """Mean payoffs and their standard errors for both players over the chosen seeds."""
    A, B, SA, SB = [], [], [], []
    for r in rows:
        a_row, b_row, sa_row, sb_row = [], [], [], []
        for c in cols:
            cell = samples[(r, c)]
            ma, sa = _stats(cell.row_utilities, index)
            mb, sb = _stats(cell.col_utilities, index)
            a_row.append(ma)
            b_row.append(mb)
            sa_row.append(sa)
            sb_row.append(sb)
        A.append(a_row)
        B.append(b_row)
        SA.append(sa_row)
        SB.append(sb_row)
    return A, B, SA, SB


def _pick(M: Sequence[Sequence[float]], ri: tuple[int, int], ci: tuple[int, int]) -> list[list[float]]:
    return [[M[i][j] for j in ci] for i in ri]


def classify_table(
    rows: Sequence[str],
    cols: Sequence[str],
    A: Grid,
    B: Grid,
    SA: Grid | None = None,
    SB: Grid | None = None,
    z: float = Z,
) -> list[tuple[tuple[str, str], tuple[str, str], Classic]]:
    """Classify every 2x2 sub-game of a table (every pair of styles per side)."""
    SA = SA if SA is not None else [[0.0] * len(cols) for _ in rows]
    SB = SB if SB is not None else [[0.0] * len(cols) for _ in rows]
    out = []
    for ri in combinations(range(len(rows)), 2):
        for ci in combinations(range(len(cols)), 2):
            c = classify_2x2(
                _pick(A, ri, ci),
                _pick(B, ri, ci),
                _pick(SA, ri, ci),
                _pick(SB, ri, ci),
                z,
                names=((rows[ri[0]], rows[ri[1]]), (cols[ci[0]], cols[ci[1]])),
            )
            out.append(((rows[ri[0]], rows[ri[1]]), (cols[ci[0]], cols[ci[1]]), c))
    return out


def classify_case(
    case_id: str,
    samples: dict[tuple[str, str], CellSamples],
    rows: Sequence[str],
    cols: Sequence[str],
    n_resamples: int = 200,
    rng_seed: int = 0,
    z: float = Z,
    surprises: bool = False,
) -> CaseClassic:
    """Label every 2x2 sub-game of the case's measured table and test how often each label survives resampling the seeds."""
    n = len(next(iter(samples.values())).row_utilities)
    A, B, SA, SB = table_stats(samples, rows, cols)
    base = classify_table(rows, cols, A, B, SA, SB, z)
    rng = random.Random(rng_seed)
    counts: list[Counter[str]] = [Counter() for _ in base]
    for _ in range(n_resamples):
        index = [rng.randrange(n) for _ in range(n)]
        Ab, Bb, SAb, SBb = table_stats(samples, rows, cols, index)
        for k, (_, _, c) in enumerate(classify_table(rows, cols, Ab, Bb, SAb, SBb, z)):
            counts[k][c.label] += 1
    subgames = [
        SubGame(
            rows=r,
            cols=c,
            label=cl.label,
            reason=cl.reason,
            stability=round(counts[k][cl.label] / n_resamples, 4) if n_resamples else 0.0,
            label_counts=dict(counts[k]),
            ties=cl.ties,
        )
        for k, (r, c, cl) in enumerate(base)
    ]
    label_counts = Counter(s.label for s in subgames)
    return CaseClassic(
        case_id=case_id,
        n_seeds=n,
        n_resamples=n_resamples,
        z=z,
        surprises=surprises,
        row_strategies=list(rows),
        col_strategies=list(cols),
        A=[[round(v, 6) for v in r] for r in A],
        B=[[round(v, 6) for v in r] for r in B],
        SA=[[round(v, 6) for v in r] for r in SA],
        SB=[[round(v, 6) for v in r] for r in SB],
        subgames=subgames,
        label_counts={k: label_counts.get(k, 0) for k in LABELS},
        mean_stability=round(sum(s.stability for s in subgames) / len(subgames), 4),
    )
