"""Bootstrap stability of the equilibrium label (proposal Sec. 8).

Owner: Engineer 5.

``estimate_payoffs`` reports one matrix from a fixed seed set, so the equilibrium
it yields could be an artefact of those seeds. Here the per-seed utilities are
kept, the seed set is resampled with replacement, and the game is re-solved on
each resample. The fraction of resamples whose label matches the baseline is an
honest confidence statement about "this case is pure / mixed / dominance-solvable".

Deterministic: the same (case, strategies, seeds, n_resamples, rng_seed) gives
the same report on any machine.
"""

from __future__ import annotations

import random
import statistics
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor

from pydantic import BaseModel, ConfigDict

from courtroom.cases import get_case
from courtroom.contracts import CaseFile, Side, Surprises
from courtroom.engine import run_trial
from courtroom.gametheory.nash import GameAnalysis, analyze

STYLES = ("aggressive", "conservative", "adaptive", "reckless")  # the four styles the page offers

PURE = "pure"
MIXED = "mixed"
DOMINANCE_SOLVABLE = "dominance-solvable"
NONE = "no-equilibrium-found"


def equilibrium_label(analysis: GameAnalysis) -> str:
    """Classify a solved game as the proposal's three labels.

    Dominance-solvable is checked first: it is the strongest claim, since iterated
    elimination of strictly dominated strategies leaves exactly one profile.
    """
    if len(analysis.iesds_rows) == 1 and len(analysis.iesds_cols) == 1:
        return DOMINANCE_SOLVABLE
    if not analysis.equilibria:
        return NONE
    if any(eq.pure for eq in analysis.equilibria):
        return PURE
    return MIXED


class CellSamples(BaseModel):
    """Per-seed utilities for one (row, col) cell — the raw material for resampling."""

    model_config = ConfigDict(frozen=True)
    row: str
    col: str
    row_utilities: list[float]
    col_utilities: list[float]


class CellInterval(BaseModel):
    """The Accuser's mean payoff in one cell, with a bootstrap 95% interval over the seed set."""

    model_config = ConfigDict(frozen=True)
    row: str
    col: str
    mean: float
    low: float
    high: float


class LabelStability(BaseModel):
    model_config = ConfigDict(frozen=True)
    case_id: str
    row_strategies: list[str]
    col_strategies: list[str]
    n_seeds: int
    n_resamples: int
    baseline_label: str
    baseline_equilibria: int
    label_counts: dict[str, int]
    stability: float
    rng_seed: int
    surprises: bool = False
    accuser_payoff_intervals: list[CellInterval] = []


def _cell_samples(args: tuple[CaseFile, str, str, tuple[int, ...], Surprises | None]) -> CellSamples:
    case, row, col, seeds, surprises = args
    up: list[float] = []
    ud: list[float] = []
    for s in seeds:
        r = run_trial(case, row, col, seed=s, surprises=surprises)
        up.append(r.utilities[Side.PROSECUTION])
        ud.append(r.utilities[Side.DEFENSE])
    return CellSamples(row=row, col=col, row_utilities=up, col_utilities=ud)


def collect_samples(
    case: CaseFile,
    strategies: Sequence[str],
    seeds: Sequence[int],
    workers: int = 1,
    surprises: Surprises | None = None,
) -> dict[tuple[str, str], CellSamples]:
    """Run every cell on the common seed set, keeping each seed's utilities."""
    rows, cols = list(strategies), list(strategies)
    jobs = [(case, r, c, tuple(seeds), surprises) for r in rows for c in cols]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            cells = list(pool.map(_cell_samples, jobs))
    else:
        cells = [_cell_samples(j) for j in jobs]
    return {(c.row, c.col): c for c in cells}


def _matrices(
    samples: dict[tuple[str, str], CellSamples],
    rows: Sequence[str],
    cols: Sequence[str],
    index: Sequence[int] | None = None,
) -> tuple[list[list[float]], list[list[float]]]:
    """Mean payoff matrices over ``index`` (all seeds when None).

    Means are rounded to 6 dp so the exact-rational solver keeps small denominators,
    matching what ``estimate_payoffs`` stores in a ``Cell``.
    """

    def mean(xs: list[float]) -> float:
        picked = xs if index is None else [xs[i] for i in index]
        return round(statistics.fmean(picked), 6)

    A = [[mean(samples[(r, c)].row_utilities) for c in cols] for r in rows]
    B = [[mean(samples[(r, c)].col_utilities) for c in cols] for r in rows]
    return A, B


def bootstrap_case(
    case: CaseFile,
    strategies: Sequence[str] = STYLES,
    seeds: Sequence[int] = tuple(range(100)),
    n_resamples: int = 200,
    workers: int = 1,
    rng_seed: int = 0,
    surprises: Surprises | None = None,
) -> LabelStability:
    """Resample the seed set ``n_resamples`` times; report how often the label holds."""
    if n_resamples < 1:
        raise ValueError("n_resamples must be at least 1")
    if not seeds:
        raise ValueError("seeds must not be empty")
    rows, cols = list(strategies), list(strategies)
    samples = collect_samples(case, strategies, seeds, workers=workers, surprises=surprises)

    A, B = _matrices(samples, rows, cols)
    baseline = analyze(rows, cols, A, B)
    baseline_label = equilibrium_label(baseline)

    rng = random.Random(rng_seed)
    n = len(seeds)
    counts: Counter[str] = Counter()
    for _ in range(n_resamples):
        index = [rng.randrange(n) for _ in range(n)]
        Ab, Bb = _matrices(samples, rows, cols, index)
        counts[equilibrium_label(analyze(rows, cols, Ab, Bb))] += 1

    # Per-strategy payoff with a bootstrap 95% interval: how far the number could move with a different set of seeds.
    cell_stats = []
    for r in rows:
        for c in cols:
            cs = samples[(r, c)]
            means = sorted(
                statistics.fmean(cs.row_utilities[i] for i in idx)
                for idx in ([rng.randrange(n) for _ in range(n)] for _ in range(n_resamples))
            )
            cell_stats.append(
                CellInterval(
                    row=r, col=c, mean=round(statistics.fmean(cs.row_utilities), 4),
                    low=round(means[int(0.025 * n_resamples)], 4), high=round(means[int(0.975 * n_resamples) - 1], 4),
                )
            )
    return LabelStability(
        case_id=case.id,
        row_strategies=rows,
        col_strategies=cols,
        n_seeds=n,
        n_resamples=n_resamples,
        baseline_label=baseline_label,
        baseline_equilibria=len(baseline.equilibria),
        label_counts=dict(counts),
        stability=round(counts[baseline_label] / n_resamples, 6) if n_resamples else 0.0,
        rng_seed=rng_seed,
        surprises=surprises is not None,
        accuser_payoff_intervals=cell_stats,
    )


def bootstrap_library(
    case_ids: Sequence[str] | None = None,
    strategies: Sequence[str] = STYLES,
    seeds: Sequence[int] = tuple(range(100)),
    n_resamples: int = 200,
    workers: int = 1,
    rng_seed: int = 0,
    surprises: Surprises | None = None,
) -> list[LabelStability]:
    from courtroom.cases import CASES

    ids = list(case_ids or CASES)
    return [
        bootstrap_case(get_case(cid), strategies, seeds, n_resamples, workers=workers, rng_seed=rng_seed, surprises=surprises)
        for cid in ids
    ]
