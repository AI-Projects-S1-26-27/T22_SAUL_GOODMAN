"""Contested-case finder: search generated cases for ones where the verdict really can move.

Nobody wrote these cases. ``generate_case(seed)`` builds a valid case from a seed; the finder tries a run of seeds,
scores each with the "does strategy matter" measure, then solves the 4x4 game for the best few and records whether it has a
dominant strategy. The answer is a list of case ids (``gen-<seed>``) the 3D courtroom can play.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from courtroom.cases import generate_case
from courtroom.contracts import Surprises
from courtroom.gametheory.matters import Mattering, measure
from courtroom.gametheory.payoff import estimate_payoffs

GAME_STRATEGIES = ("aggressive", "conservative", "adaptive", "reckless")


class Found(BaseModel):
    model_config = ConfigDict(frozen=True)
    case_id: str
    title: str
    score: float
    mattering: Mattering
    no_dominant_strategy: bool | None = None  # None when the 4x4 game was not solved for this one
    equilibrium_kind: str | None = None  # pure | mixed | dominance-solvable


class FindReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    start: int
    tried: int
    seconds: float
    surprises: bool
    found: list[Found]
    note: str


def score(m: Mattering) -> float:
    """Higher means more contested: lawyers change the verdict, and luck does too."""
    return round(m.pairing_spread + 0.5 * m.seed_noise, 4)


def _kind(analysis) -> str:  # type: ignore[no-untyped-def]
    if analysis.trivial:
        return "dominance-solvable"
    return "pure" if all(e.pure for e in analysis.equilibria) else "mixed"


def find_contested(
    start: int = 0,
    count: int = 30,
    top: int = 5,
    seeds: Sequence[int] = (0, 1, 2),
    game_seeds: Sequence[int] = tuple(range(8)),
    surprises: Surprises | None = None,
    time_budget: float | None = None,
) -> FindReport:
    """Try ``count`` generated cases from seed ``start``; solve the game for the ``top`` most contested."""
    t0 = time.perf_counter()
    scored: list[tuple[float, int, Mattering]] = []
    tried = 0
    for gseed in range(start, start + count):
        if time_budget is not None and time.perf_counter() - t0 > time_budget * 0.6:
            break
        tried += 1
        case = generate_case(gseed)
        if not case.evidence:
            continue
        m = measure(case, seeds=seeds, surprises=surprises)
        scored.append((score(m), gseed, m))
    scored.sort(key=lambda t: (-t[0], t[1]))
    found: list[Found] = []
    for sc, gseed, m in scored[:top]:
        case = generate_case(gseed)
        dominant: bool | None = None
        kind: str | None = None
        if time_budget is None or time.perf_counter() - t0 < time_budget:
            table = estimate_payoffs(case, GAME_STRATEGIES, seeds=game_seeds, surprises=surprises)
            a = table.analysis
            dominant = a.row_dominance != "strict" and a.col_dominance != "strict" and not a.trivial
            kind = _kind(a)
        found.append(Found(case_id=case.id, title=case.title, score=sc, mattering=m, no_dominant_strategy=dominant, equilibrium_kind=kind))
    # Cases whose game has no dominant strategy come first, then by score.
    found.sort(key=lambda f: (f.no_dominant_strategy is not True, -f.score, f.case_id))
    return FindReport(
        start=start,
        tried=tried,
        seconds=round(time.perf_counter() - t0, 2),
        surprises=surprises is not None,
        found=found,
        note=f"Found by search: tried gen-{start} to gen-{start + tried - 1}, scored each by how far the lawyers and the seed move the verdict.",
    )
