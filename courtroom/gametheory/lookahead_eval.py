"""Does the lookahead lawyer beat the four hand-written styles?  A labelled extra, never part of the certified analysis.

The question is the one the best-response search asks of its candidates: against the equilibrium the four styles settle into, does the
newcomer earn more, by more than two standard errors, on the same seeds? It is a paired comparison per seed, so luck of the draw cancels.
The lookahead style is a fixed, deterministic lawyer (no searching of parameters), so there is nothing here to tune and no held-out set
is needed; the same seeds are used for the four-style equilibrium and for the newcomer.

The five-by-five table (the four styles plus lookahead) is also solved, to show whether lookahead enters the equilibrium.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from courtroom.contracts import CaseFile, Surprises
from courtroom.gametheory.nash import analyze
from courtroom.gametheory.oracle import ACCEPT_SE, START, Cache, _mix, _pick, named

LOOKAHEAD = "lookahead"


class SideResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    side: str
    equilibrium_payoff: float  # the four styles' equilibrium mix, against the other side's equilibrium mix
    lookahead_payoff: float  # lookahead in that seat, against the same opponent mix
    difference: float
    standard_error: float
    z: float
    beats: bool  # more than 2 standard errors better
    worse: bool  # more than 2 standard errors worse
    pure_payoffs: dict[str, float]  # each of the five against the same opponent mix


class LookaheadReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    case_id: str
    surprises: bool
    seeds: int
    prosecution: SideResult
    defense: SideResult
    equilibrium_of_four: dict[str, dict[str, float]]
    five_by_five_equilibrium: dict[str, dict[str, float]]
    lookahead_in_equilibrium: dict[str, float]  # the weight lookahead gets in the five-by-five equilibrium, per side
    verdict: str
    note: str


def _side(cache: Cache, side: str, four: Sequence, look, opp_mix: Sequence[float], own_mix: Sequence[float], seeds: Sequence[int], label: str) -> SideResult:
    per = [cache.vs_mix(side, s, four, opp_mix, seeds) for s in four]
    eq = [sum(own_mix[i] * per[i][k] for i in range(len(four))) for k in range(len(seeds))]
    la = cache.vs_mix(side, look, four, opp_mix, seeds)
    d = [la[k] - eq[k] for k in range(len(seeds))]
    se = statistics.stdev(d) / math.sqrt(len(d)) if len(d) > 1 else 0.0
    mean = statistics.fmean(d)
    z = mean / se if se > 1e-12 else (math.copysign(math.inf, mean) if abs(mean) > 1e-12 else 0.0)
    z_out = max(-99.0, min(99.0, z))
    return SideResult(
        side=label,
        equilibrium_payoff=round(statistics.fmean(eq), 4),
        lookahead_payoff=round(statistics.fmean(la), 4),
        difference=round(mean, 4),
        standard_error=round(se, 4),
        z=round(z_out, 2),
        beats=z_out > ACCEPT_SE,
        worse=z_out < -ACCEPT_SE,
        pure_payoffs={**{s.name: round(statistics.fmean(per[i]), 4) for i, s in enumerate(four)}, LOOKAHEAD: round(statistics.fmean(la), 4)},
    )


def compare_lookahead(case: CaseFile, seeds: Sequence[int] = tuple(range(40)), surprises: Surprises | None = None, workers: int = 1) -> LookaheadReport:
    cache = Cache(case, surprises, workers)
    try:
        four = [named(s) for s in START]
        look = named(LOOKAHEAD)
        A, B = cache.mean_matrix(four, four, seeds)
        eq = _pick(analyze(list(START), list(START), A, B))
        x, y = _mix(eq, START, "row"), _mix(eq, START, "col")
        pro = _side(cache, "prosecution", four, look, y, x, seeds, "Accuser")
        dfn = _side(cache, "defense", four, look, x, y, seeds, "Defender")
        five = [*four, look]
        labels = [*START, LOOKAHEAD]
        A5, B5 = cache.mean_matrix(five, five, seeds)
        eq5 = _pick(analyze(labels, labels, A5, B5))
        mix5 = {
            "prosecution": {k: round(v, 4) for k, v in (eq5.row_mix if eq5 else {}).items() if v > 1e-9},
            "defense": {k: round(v, 4) for k, v in (eq5.col_mix if eq5 else {}).items() if v > 1e-9},
        }
    finally:
        cache.close()
    beats = [r.side for r in (pro, dfn) if r.beats]
    worse = [r.side for r in (pro, dfn) if r.worse]
    if beats:
        verdict = f"Lookahead beat the four-style equilibrium as the {' and '.join(beats)} by more than 2 standard errors."
    elif worse and len(worse) == 2:
        verdict = "Lookahead did clearly worse than the four-style equilibrium in both seats."
    elif worse:
        verdict = f"Lookahead did clearly worse as the {' and '.join(worse)}, and no better in the other seat."
    else:
        verdict = "Lookahead was not distinguishable from the four-style equilibrium in either seat."
    return LookaheadReport(
        case_id=case.id,
        surprises=surprises is not None,
        seeds=len(seeds),
        prosecution=pro,
        defense=dfn,
        equilibrium_of_four={"prosecution": {k: round(v, 4) for k, v in (eq.row_mix if eq else {}).items() if v > 1e-9}, "defense": {k: round(v, 4) for k, v in (eq.col_mix if eq else {}).items() if v > 1e-9}},
        five_by_five_equilibrium=mix5,
        lookahead_in_equilibrium={"prosecution": mix5["prosecution"].get(LOOKAHEAD, 0.0), "defense": mix5["defense"].get(LOOKAHEAD, 0.0)},
        verdict=verdict,
        note="Exhibition, not certified: lookahead is an extra style outside the four certified ones and is never in a payoff table used for the certified analysis.",
    )
