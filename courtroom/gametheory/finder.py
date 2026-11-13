"""Contested-case finder: search generated cases for ones where the verdict really can move.

Nobody wrote these cases. ``generate_case(seed)`` builds a valid case from a seed; the finder tries a run of seeds,
scores each with the "does strategy matter" measure, then solves the 4x4 game for the best few and records whether it has a
dominant strategy. The answer is a list of case ids (``gen-<seed>``) the 3D courtroom can play.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from courtroom.cases import generate_case
from courtroom.contracts import Surprises
from courtroom.gametheory.bootstrap import STYLES as STYLES4
from courtroom.gametheory.bootstrap import collect_samples
from courtroom.gametheory.classic import BOS, LABELS, PD, STAG, classify_case, classify_table, table_stats
from courtroom.gametheory.matters import Mattering, measure
from courtroom.gametheory.payoff import estimate_payoffs

CONFIRM_STABILITY = 0.8  # a found game must keep its name on at least 80% of resamples of the fresh seeds
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


# --------------------------------------------------------------------------- classic-game search


class ClassicFound(BaseModel):
    """A generated case with a 2x2 sub-game that carries a classic name, confirmed on seeds that were not used to find it."""

    model_config = ConfigDict(frozen=True)
    case_id: str
    title: str
    label: str
    rows: tuple[str, str]
    cols: tuple[str, str]
    reason: str
    found_on: int  # seeds used to spot it
    confirmed_on: int  # fresh seeds used to confirm it
    confirmed_label: str
    stability: float  # share of resamples of the confirmation seeds that keep the label
    row_payoffs: list[list[float]]
    col_payoffs: list[list[float]]


class ClassicFindReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    targets: list[str]
    start: int
    tried: int
    seconds: float
    surprises: bool
    label_counts: dict[str, int]  # every label over all tried cases (all corners) with the standard-error tolerance, on the spotting seeds
    label_counts_no_tolerance: dict[str, int]  # the same count reading the means as exact (z = 0): the candidates the search then tried to confirm
    candidates: int  # corners that looked like a target game when read as exact
    found: list[ClassicFound]
    note: str


def find_classic(
    targets: Sequence[str] = (PD, STAG, BOS),
    start: int = 0,
    count: int = 40,
    seeds: Sequence[int] = tuple(range(12)),
    confirm_seeds: Sequence[int] = tuple(range(1000, 1040)),
    n_resamples: int = 100,
    surprises: Surprises | None = None,
    time_budget: float | None = None,
    per_label: int = 3,
) -> ClassicFindReport:
    """Search generated cases for one whose measured game contains a prisoner's dilemma, stag hunt or battle of the sexes.

    A case is spotted on ``seeds``, then re-measured on ``confirm_seeds`` (a disjoint set) and kept only if the same sub-game
    carries the same label there. Nothing is tuned: a case either shows the game or it does not.
    """
    t0 = time.perf_counter()
    seen: Counter[str] = Counter()
    raw: Counter[str] = Counter()
    tried = 0
    best: dict[str, list[ClassicFound]] = {t: [] for t in targets}
    for gseed in range(start, start + count):
        if time_budget is not None and time.perf_counter() - t0 > time_budget:
            break
        case = generate_case(gseed)
        if not case.evidence:
            continue
        tried += 1
        spot = collect_samples(case, STYLES4, seeds, surprises=surprises)
        A, B, SA, SB = table_stats(spot, STYLES4, STYLES4)
        # Spot loosely, confirm strictly: read the means as exact to find candidates, then demand the full tolerance on fresh seeds.
        hits = []
        for r, c, cl in classify_table(STYLES4, STYLES4, A, B, SA, SB, z=0.0):
            raw[cl.label] += 1
            if cl.label in targets:
                hits.append((r, c, cl))
        for _, _, cl in classify_table(STYLES4, STYLES4, A, B, SA, SB):
            seen[cl.label] += 1
        if not hits:
            continue
        confirm = collect_samples(case, STYLES4, confirm_seeds, surprises=surprises)
        result = classify_case(case.id, confirm, STYLES4, STYLES4, n_resamples=n_resamples, surprises=surprises is not None)
        index = {(s.rows, s.cols): s for s in result.subgames}
        ridx = {n: i for i, n in enumerate(STYLES4)}
        for r, c, cl in hits:
            sub = index[(r, c)]
            if sub.label != cl.label or sub.stability < CONFIRM_STABILITY:
                continue
            ri, ci = [ridx[x] for x in r], [ridx[x] for x in c]
            best[cl.label].append(
                ClassicFound(
                    case_id=case.id,
                    title=case.title,
                    label=cl.label,
                    rows=r,
                    cols=c,
                    reason=cl.reason,
                    found_on=len(seeds),
                    confirmed_on=len(confirm_seeds),
                    confirmed_label=sub.label,
                    stability=sub.stability,
                    row_payoffs=[[result.A[i][j] for j in ci] for i in ri],
                    col_payoffs=[[result.B[i][j] for j in ci] for i in ri],
                )
            )
    found: list[ClassicFound] = []
    for label in targets:
        ranked = sorted(best[label], key=lambda f: (-f.stability, f.case_id, f.rows, f.cols))
        seen_cases: set[str] = set()
        for f in ranked:
            if f.case_id not in seen_cases and len([x for x in found if x.label == label]) < per_label:
                seen_cases.add(f.case_id)
                found.append(f)
    return ClassicFindReport(
        targets=list(targets),
        start=start,
        tried=tried,
        seconds=round(time.perf_counter() - t0, 2),
        surprises=surprises is not None,
        label_counts={k: seen.get(k, 0) for k in LABELS},
        label_counts_no_tolerance={k: raw.get(k, 0) for k in LABELS},
        candidates=sum(raw.get(t, 0) for t in targets),
        found=found,
        note=(
            f"Found by search: tried gen-{start} to gen-{start + tried - 1}; a corner that looked like a target game on a few seeds is listed only if it "
            f"keeps the same name, under the full tolerance, on {len(confirm_seeds)} fresh seeds and on at least {int(CONFIRM_STABILITY * 100)}% of their resamples. Nothing was tuned."
        ),
    )
