"""Measure how a case's game responds to a setting: structure, supports, stability and payoff variance.

Used to calibrate the adverse-event parameters and the case values that depend on them (DEVIATIONS D19). Nothing here is
part of the certified analysis: it re-runs the same trials, with the same seeds and the same solver, under a setting the
caller names, and reports what comes out. It adds no randomness of its own beyond the bootstrap's seeded resampling.

For one case and one setting it reports:

* the equilibrium **label** (pure, mixed, dominance-solvable) and the equilibria's **supports**;
* **label stability**: the share of bootstrap resamples that keep the label;
* **support stability**: the share that keep the exact set of equilibrium supports, which is stricter;
* each strategy's payoff **standard deviation** in each seat, pooled over opponents and seeds;
* the prosecution's win rate per cell (mean, minimum, maximum).
"""

from __future__ import annotations

import random
import statistics
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from typing import Any

from courtroom.contracts import CaseFile, RuleSet, Side
from courtroom.engine import run_trial
from courtroom.gametheory.bootstrap import equilibrium_label
from courtroom.gametheory.nash import analyze

STRATEGIES = ("aggressive", "conservative", "adaptive", "mixed:0.5")


def with_events(
    case: CaseFile,
    no_show: float,
    missing_certificate: float,
    hostile: float,
    hostile_credibility: str = "1/4",
) -> CaseFile:
    """The case with adverse events switched on at the given rates. All-zero rates is the events-off game."""
    rules = RuleSet(
        adverse_events=True,
        no_show=no_show,
        missing_certificate=missing_certificate,
        hostile=hostile,
        hostile_credibility=hostile_credibility,
    )
    return case.model_copy(update={"rules": rules})


def _cell(args: tuple[CaseFile, str, str, tuple[int, ...]]) -> tuple[str, str, list[float], list[float], list[int]]:
    case, row, col, seeds = args
    up: list[float] = []
    ud: list[float] = []
    wins: list[int] = []
    for s in seeds:
        r = run_trial(case, row, col, seed=s)
        up.append(r.utilities[Side.PROSECUTION])
        ud.append(r.utilities[Side.DEFENSE])
        wins.append(int(r.verdict.outcome.favours is Side.PROSECUTION))
    return row, col, up, ud, wins


def support_key(analysis: Any) -> tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]:
    """The set of equilibrium supports: which strategies each side puts weight on, per equilibrium."""
    return tuple(
        sorted(
            (
                tuple(k for k, v in eq.row_mix.items() if v > 1e-9),
                tuple(k for k, v in eq.col_mix.items() if v > 1e-9),
            )
            for eq in analysis.equilibria
        )
    )


def run_cells(
    cases: dict[str, CaseFile], seeds: Sequence[int], workers: int = 4, strategies: Sequence[str] = STRATEGIES
) -> dict[str, dict[tuple[str, str], tuple[list[float], list[float], list[int]]]]:
    """Every cell of every case, run on the same seeds, in one pool."""
    jobs = [(case, r, c, tuple(seeds)) for case in cases.values() for r in strategies for c in strategies]
    keys = [cid for cid in cases for _ in range(len(strategies) ** 2)]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            out = list(pool.map(_cell, jobs, chunksize=4))
    else:
        out = [_cell(j) for j in jobs]
    result: dict[str, dict[tuple[str, str], tuple[list[float], list[float], list[int]]]] = {cid: {} for cid in cases}
    for cid, (row, col, up, ud, wins) in zip(keys, out, strict=True):
        result[cid][(row, col)] = (up, ud, wins)
    return result


def _matrices(
    cells: dict[tuple[str, str], tuple[list[float], list[float], list[int]]],
    strategies: Sequence[str],
    index: Sequence[int] | None = None,
) -> tuple[list[list[float]], list[list[float]]]:
    def mean(xs: list[float]) -> float:
        picked = xs if index is None else [xs[i] for i in index]
        return round(statistics.fmean(picked), 6)

    A = [[mean(cells[(r, c)][0]) for c in strategies] for r in strategies]
    B = [[mean(cells[(r, c)][1]) for c in strategies] for r in strategies]
    return A, B


def measure_case(
    cells: dict[tuple[str, str], tuple[list[float], list[float], list[int]]],
    strategies: Sequence[str] = STRATEGIES,
    n_resamples: int = 200,
    rng_seed: int = 0,
) -> dict[str, Any]:
    """Structure, supports, both stabilities, variance and win rates from one case's cells."""
    rows = list(strategies)
    n = len(next(iter(cells.values()))[0])
    A, B = _matrices(cells, rows)
    base = analyze(rows, rows, A, B)
    label = equilibrium_label(base)
    base_support = support_key(base)

    rng = random.Random(rng_seed)
    labels: Counter[str] = Counter()
    same_support = 0
    for _ in range(n_resamples):
        index = [rng.randrange(n) for _ in range(n)]
        Ab, Bb = _matrices(cells, rows, index)
        a = analyze(rows, rows, Ab, Bb)
        labels[equilibrium_label(a)] += 1
        same_support += support_key(a) == base_support

    sd: dict[str, dict[str, float]] = {"prosecution": {}, "defense": {}}
    mean_payoff: dict[str, dict[str, float]] = {"prosecution": {}, "defense": {}}
    for s in rows:
        pros = [u for c in rows for u in cells[(s, c)][0]]
        defe = [u for r in rows for u in cells[(r, s)][1]]
        sd["prosecution"][s] = round(statistics.pstdev(pros), 4)
        sd["defense"][s] = round(statistics.pstdev(defe), 4)
        mean_payoff["prosecution"][s] = round(statistics.fmean(pros), 4)
        mean_payoff["defense"][s] = round(statistics.fmean(defe), 4)
    wins = [statistics.fmean(cells[(r, c)][2]) for r in rows for c in rows]
    return {
        "label": label,
        "n_equilibria": len(base.equilibria),
        "support": [[list(r), list(c)] for r, c in base_support],
        "label_stability": round(labels[label] / n_resamples, 4),
        "support_stability": round(same_support / n_resamples, 4),
        "labels": dict(labels),
        "sd": sd,
        "mean_payoff": mean_payoff,
        "win_mean": round(statistics.fmean(wins), 4),
        "win_min": round(min(wins), 4),
        "win_max": round(max(wins), 4),
        "dominant": [base.row_dominant, base.col_dominant],
    }


# --------------------------------------------------------------------------- choosing a setting

#: A strategy-in-a-seat whose payoff sd is below this with events off is "missing variance".
FLAT_SD = 0.5
#: Rule (a): the share of flat cells that must gain at least ``RISE`` sd for variance to count as risen.
FLAT_SHARE = 0.5
RISE = 0.5
#: Rule (c): bootstrap stability required of both label and support, for every case.
STABILITY_FLOOR = 0.95
#: Rule (b): at least this many cases must not be dominance-solvable.
MIN_CONTESTED = 3


def exposed(case: CaseFile) -> bool:
    """Whether an adverse event can touch this case at all: it has a witness's testimony or an electronic record."""
    return any(i.witness_id is not None or i.kind.value == "digital_log" for i in case.evidence)


def real_play_cases(baseline: dict[str, Any]) -> list[str]:
    """Cases in which the prosecution wins at least one cell with events off: the ones that are contests at all.

    The rules count seven cases, but three are single-rule fixtures that no setting can make contested (an empty docket, a
    defense-only docket, an exact tie). ``evaluate(..., scope=real_play_cases(baseline))`` applies rules (b) and (c) to the
    cases that can actually change strategically.
    """
    return [cid for cid, m in baseline["cases"].items() if m["win_max"] > 0]


def evaluate(
    record: dict[str, Any],
    baseline: dict[str, Any],
    exposed_cases: Sequence[str],
    scope: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Apply the selection rules to one measured setting. ``baseline`` is the events-off record.

    Rule (a) looks only at cells that were flat with events off *and* sit in a case events can reach; a strategy that
    never offers an exposed exhibit has nothing for an event to act on, and counting it would make the rule unsatisfiable.
    """
    flat, risen = [], []
    for cid in exposed_cases:
        if scope is not None and cid not in scope:
            continue
        for side in ("prosecution", "defense"):
            for strategy, sd0 in baseline["cases"][cid]["sd"][side].items():
                if sd0 < FLAT_SD:
                    flat.append((cid, side, strategy))
                    if record["cases"][cid]["sd"][side][strategy] - sd0 >= RISE:
                        risen.append((cid, side, strategy))
    a_share = len(risen) / len(flat) if flat else 1.0
    cases = {cid: m for cid, m in record["cases"].items() if scope is None or cid in scope}
    contested = [cid for cid, m in cases.items() if m["label"] != "dominance-solvable"]
    stabilities = {cid: min(m["label_stability"], m["support_stability"]) for cid, m in cases.items()}
    min_stab = min(stabilities.values())
    return {
        "a_share": round(a_share, 4),
        "a": a_share >= FLAT_SHARE,
        "flat_cells": len(flat),
        "risen_cells": len(risen),
        "contested": contested,
        "b": len(contested) >= MIN_CONTESTED,
        "unstable": sorted(cid for cid, s in stabilities.items() if s < STABILITY_FLOOR),
        "c": min_stab >= STABILITY_FLOOR,
        "min_stability": round(min_stab, 4),
        "mean_stability": round(statistics.fmean(stabilities.values()), 4),
    }


def choose(records: Sequence[dict[str, Any]], baseline: dict[str, Any], exposed_cases: Sequence[str]) -> dict[str, Any]:
    """Pick a shipping setting by the rules, in order, and say whether a fully qualifying band existed.

    (a) variance rises where it was missing; (b) at least three cases are not dominance-solvable; (c) every case holds
    both stabilities at 0.95 or better; (d) among qualifying settings, the highest minimum stability, ties toward more
    contested cases; (e) if none qualifies, the best-stability setting that still satisfies (a), recorded as such.
    """
    scored = [(r, evaluate(r, baseline, exposed_cases)) for r in records if r.get("events_on")]
    qualifying = [(r, e) for r, e in scored if e["a"] and e["b"] and e["c"]]
    if qualifying:
        r, e = max(qualifying, key=lambda t: (t[1]["min_stability"], len(t[1]["contested"]), t[1]["mean_stability"]))
        return {"band_exists": True, "setting": r["name"], "evaluation": e, "qualifying": [x["name"] for x, _ in qualifying]}
    improving = [(r, e) for r, e in scored if e["a"]]
    pool = improving or scored
    r, e = max(pool, key=lambda t: (t[1]["min_stability"], t[1]["mean_stability"], len(t[1]["contested"])))
    return {
        "band_exists": False,
        "setting": r["name"],
        "evaluation": e,
        "qualifying": [],
        "fallback": "rule (e): no setting satisfies (a), (b) and (c) together"
        + ("" if improving else "; none even satisfies (a), so the best-stability setting overall is used"),
    }
