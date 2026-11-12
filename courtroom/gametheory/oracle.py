"""Can the four hand-written lawyer styles be beaten?  A double-oracle (PSRO-style) search over lawyer profiles.

The four styles are not the only possible lawyers. Three of them are a few numbers in a ``StrategyProfile`` (how many known defects
to tolerate, how much gain a turn must bring, how readily to object ...), and the fourth plays at random. So we can *search*
for a profile that does better, instead of assuming the hand-written ones are good:

    start with the four styles on each side and solve the game exactly (``nash.analyze``)
    repeat, for at most ``MAX_ROUNDS`` rounds:
        for each side:
            take the other side's equilibrium mix
            search profiles (seeded random search, then local refinement) for one that earns the most against that mix
                on the TRAINING seeds
            re-check the best one on HELD-OUT seeds, against the current equilibrium mix, with a paired test
            keep it only if it wins by more than ``ACCEPT_SE`` standard errors
        if neither side kept anything: stop
        add what was kept to the strategy sets, fill in the new rows and columns, solve again

Everything is deterministic in (case, surprises flag, seeds, rng seed, budget). Payoffs come from real trials by the exact judge.
Nothing a language model produced is used. The result says how exploitable the hand-written styles were, what was found in plain
words, and what the final equilibrium is. It makes no claim beyond the family searched: failing to find a better profile in this
budget is evidence, not proof. See docs/LLM_ROLE.md for why the same check cannot certify a language model.
"""

from __future__ import annotations

import random
import statistics
import time
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from courtroom.agents import make_agent
from courtroom.agents.policies import ADAPTIVE, AGGRESSIVE, CONSERVATIVE, CounselAgent, StrategyProfile
from courtroom.contracts import CaseFile, Side, Surprises
from courtroom.engine import run_with_agents
from courtroom.gametheory.nash import analyze

MAX_ROUNDS = 4
ACCEPT_SE = 2.0  # a candidate must beat the current equilibrium mix by more than this many standard errors
START = ("aggressive", "conservative", "adaptive", "reckless")
PROFILES = {"aggressive": AGGRESSIVE, "conservative": CONSERVATIVE, "adaptive": ADAPTIVE}

# the five numbers the search may change (everything else about a profile is inherited from the one it was derived from)
SPACE: dict[str, tuple[float, float]] = {
    "max_known_defects": (0, 3),
    "min_gain": (0.0, 1.0),
    "objection_belief": (0.0, 1.0),
    "objection_min_impact": (0.0, 1.5),
    "reserve_fraction": (0.0, 0.6),
}


# --------------------------------------------------------------------------- strategies and one trial


@dataclass(frozen=True)
class Spec:
    """A lawyer: a named built-in style, or a searched profile."""

    name: str
    profile: tuple[tuple[str, Any], ...] | None = None  # sorted StrategyProfile fields, hashable; None for a named style

    def key(self) -> tuple[str, tuple[tuple[str, Any], ...] | None]:
        return (self.name, self.profile)

    def agent(self, seed: int, side: str):
        if self.profile is None:
            return make_agent(self.name, random.Random(f"{seed}:agent:{side}"))
        return CounselAgent(StrategyProfile(**dict(self.profile)), name=self.name)


def named(name: str) -> Spec:
    return Spec(name)


def from_profile(p: StrategyProfile, name: str) -> Spec:
    fields = p.model_dump()
    fields["name"] = name
    return Spec(name, tuple(sorted(fields.items())))


def _play(job: tuple[CaseFile, Spec, Spec, int, Surprises | None]) -> tuple[float, float]:
    case, p, d, seed, surprises = job
    r = run_with_agents(case, p.agent(seed, "prosecution"), d.agent(seed, "defense"), seed, surprises, p.name, d.name)
    return r.utilities[Side.PROSECUTION], r.utilities[Side.DEFENSE]


# --------------------------------------------------------------------------- plain words


def describe(spec: Spec) -> str:
    """A discovered profile in plain English."""
    if spec.profile is None:
        return spec.name
    f = dict(spec.profile)
    parts = []
    k = int(f["max_known_defects"])
    parts.append("shows only clean evidence" if k == 0 else f"shows evidence even with up to {k} known problem{'s' if k > 1 else ''}")
    parts.append("spends a turn on anything that helps" if f["min_gain"] < 0.05 else f"spends a turn only if it moves the judge by at least {f['min_gain']:.2f}")
    belief = f["objection_belief"]
    parts.append("objects on the slightest suspicion" if belief < 0.1 else f"objects only when it is {belief:.0%} sure of a flaw" if belief < 0.95 else "almost never objects")
    if f["objection_min_impact"] >= 0.05:
        parts.append(f"and only if the exhibit would matter by {f['objection_min_impact']:.2f} or more")
    parts.append("keeps nothing back for objections" if f["reserve_fraction"] < 0.02 else f"holds back {f['reserve_fraction']:.0%} of its budget for objections")
    basis = []
    if f.get("adaptive"):
        basis.append("reasons about the other lawyer")
    if f.get("always_move_dv"):
        basis.append("always asks for the trial to end early")
    if f.get("blanket_objection_impact") is not None:
        basis.append("objects to anything big whatever it suspects")
    return "; ".join(parts) + (f" ({', '.join(basis)})" if basis else "")


# --------------------------------------------------------------------------- the payoff cache


class Cache:
    """Every (row lawyer, column lawyer, seed) is played once, however many times a search asks for it."""

    def __init__(self, case: CaseFile, surprises: Surprises | None, workers: int) -> None:
        self.case, self.surprises, self.workers = case, surprises, workers
        self._u: dict[tuple, tuple[float, float]] = {}
        self.trials = 0
        self._pool: ProcessPoolExecutor | None = ProcessPoolExecutor(max_workers=workers) if workers > 1 else None

    def close(self) -> None:
        if self._pool:
            self._pool.shutdown()

    def fill(self, rows: Sequence[Spec], cols: Sequence[Spec], seeds: Sequence[int]) -> None:
        todo = [(r, c, s) for r in rows for c in cols for s in seeds if (r.key(), c.key(), s) not in self._u]
        jobs = [(self.case, r, c, s, self.surprises) for r, c, s in todo]
        out = list(self._pool.map(_play, jobs, chunksize=max(1, len(jobs) // (4 * self.workers)))) if self._pool and len(jobs) > 8 else [_play(j) for j in jobs]
        for (r, c, s), u in zip(todo, out, strict=True):
            self._u[(r.key(), c.key(), s)] = u
        self.trials += len(jobs)

    def u(self, r: Spec, c: Spec, seed: int) -> tuple[float, float]:
        return self._u[(r.key(), c.key(), seed)]

    def mean_matrix(self, rows: Sequence[Spec], cols: Sequence[Spec], seeds: Sequence[int]) -> tuple[list[list[float]], list[list[float]]]:
        self.fill(rows, cols, seeds)
        A = [[round(statistics.fmean(self.u(r, c, s)[0] for s in seeds), 6) for c in cols] for r in rows]
        B = [[round(statistics.fmean(self.u(r, c, s)[1] for s in seeds), 6) for c in cols] for r in rows]
        return A, B

    def vs_mix(self, side: str, me: Spec, others: Sequence[Spec], mix: Sequence[float], seeds: Sequence[int]) -> list[float]:
        """Per-seed payoff of ``me`` against the other side's mixture."""
        use = [(o, w) for o, w in zip(others, mix, strict=True) if w > 1e-9]
        if side == "prosecution":
            self.fill([me], [o for o, _ in use], seeds)
            return [sum(w * self.u(me, o, s)[0] for o, w in use) for s in seeds]
        self.fill([o for o, _ in use], [me], seeds)
        return [sum(w * self.u(o, me, s)[1] for o, w in use) for s in seeds]


# --------------------------------------------------------------------------- the search


def _clip(name: str, v: float) -> float:
    lo, hi = SPACE[name]
    v = min(hi, max(lo, v))
    return float(round(v)) if name == "max_known_defects" else round(v, 2)


def _derive(base: Spec | None, params: dict[str, float], name: str) -> Spec:
    """A new profile: the five searched numbers set, everything else inherited from ``base`` (or the conservative style)."""
    src = dict(base.profile) if base is not None and base.profile is not None else PROFILES.get(base.name if base else "conservative", CONSERVATIVE).model_dump()
    src.update({k: _clip(k, v) for k, v in params.items()})
    src["name"] = name
    src["label"] = name
    src["description"] = "found by the best-response search"
    p = StrategyProfile(**src)
    return from_profile(p, name)


def _params(spec: Spec) -> dict[str, float]:
    f = dict(spec.profile) if spec.profile else PROFILES[spec.name].model_dump()
    return {k: float(f[k]) for k in SPACE}


def search_best_response(
    cache: Cache,
    side: str,
    population: Sequence[Spec],
    opponents: Sequence[Spec],
    opp_mix: Sequence[float],
    train: Sequence[int],
    budget: int,
    rng: random.Random,
    name: str,
) -> tuple[Spec, float, int]:
    """Seeded random search then local refinement for the profile earning the most against ``opp_mix`` on the training seeds."""
    bases = [s for s in population if s.name != "reckless"]
    best: Spec | None = None
    best_val = float("-inf")
    tried = 0
    n_random = max(1, int(budget * 0.6))

    def score(spec: Spec) -> float:
        nonlocal tried
        tried += 1
        return statistics.fmean(cache.vs_mix(side, spec, opponents, opp_mix, train))

    for _ in range(n_random):
        base = rng.choice(bases)
        params = {k: rng.uniform(*SPACE[k]) for k in SPACE}
        cand = _derive(base, params, name)
        v = score(cand)
        if v > best_val:
            best, best_val = cand, v
    assert best is not None
    step = 0.25
    while tried < budget:
        improved = False
        for k in SPACE:
            if tried >= budget:
                break
            span = SPACE[k][1] - SPACE[k][0]
            for sign in (1, -1):
                if tried >= budget:
                    break
                trial = _params(best)
                trial[k] = trial[k] + sign * step * span
                cand = _derive(best, trial, name)
                if cand.profile == best.profile:
                    continue
                v = score(cand)
                if v > best_val + 1e-12:
                    best, best_val, improved = cand, v, True
        if not improved:
            step /= 2
            if step < 0.02:
                break
    return best, best_val, tried


# --------------------------------------------------------------------------- results


class Candidate(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    side: str
    plain: str
    params: dict[str, float]
    tried: int
    train_payoff: float
    heldout_candidate: float
    heldout_current: float
    difference: float
    standard_error: float
    z: float
    accepted: bool


class OracleReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    case_id: str
    surprises: bool
    train_seeds: list[int]
    heldout_seeds: list[int]
    budget: int
    rng_seed: int
    max_rounds: int
    rounds_run: int
    stopped: str
    start_strategies: list[str]
    start_equilibrium: dict[str, Any]
    candidates: list[Candidate]
    final_prosecution: list[dict[str, Any]]
    final_defense: list[dict[str, Any]]
    final_equilibrium: dict[str, Any]
    exploitability: dict[str, Any]
    trials: int
    seconds: float
    headline: str


def _pick(an) -> Any | None:  # type: ignore[no-untyped-def]
    """The equilibrium the lab shows first: a pure one if there is one, else the first found."""
    return next((e for e in an.equilibria if e.pure), an.equilibria[0] if an.equilibria else None)


def _mix(eq, labels: Sequence[str], which: str) -> list[float]:  # type: ignore[no-untyped-def]
    if eq is None:
        return [1.0 / len(labels)] * len(labels)
    m = eq.row_mix if which == "row" else eq.col_mix
    return [m.get(label, 0.0) for label in labels]


def _eq_summary(eq, rows: Sequence[Spec], cols: Sequence[Spec]) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    if eq is None:
        return {"found": False}
    return {
        "found": True,
        "pure": eq.pure,
        "prosecution_mix": {k: round(v, 4) for k, v in eq.row_mix.items() if v > 1e-9},
        "defense_mix": {k: round(v, 4) for k, v in eq.col_mix.items() if v > 1e-9},
        "prosecution_mix_exact": {k: v for k, v in eq.row_mix_exact.items() if eq.row_mix.get(k, 0) > 1e-9},
        "defense_mix_exact": {k: v for k, v in eq.col_mix_exact.items() if eq.col_mix.get(k, 0) > 1e-9},
        "prosecution_payoff": round(eq.row_payoff, 4),
        "defense_payoff": round(eq.col_payoff, 4),
        "verified": eq.verified,
    }


def run_oracle(
    case: CaseFile,
    budget: int = 40,
    surprises: Surprises | None = None,
    train: Sequence[int] = tuple(range(6)),
    heldout: Sequence[int] = tuple(range(100, 112)),
    rng_seed: int = 0,
    workers: int = 1,
    max_rounds: int = MAX_ROUNDS,
) -> OracleReport:
    t0 = time.perf_counter()
    cache = Cache(case, surprises, workers)
    rng = random.Random(f"oracle:{case.id}:{rng_seed}")
    all_seeds = [*train, *heldout]
    pop = {"prosecution": [named(n) for n in START], "defense": [named(n) for n in START]}
    candidates: list[Candidate] = []
    try:
        A, B = cache.mean_matrix(pop["prosecution"], pop["defense"], all_seeds)
        an = analyze([s.name for s in pop["prosecution"]], [s.name for s in pop["defense"]], A, B)
        eq = _pick(an)
        start_eq = _eq_summary(eq, pop["prosecution"], pop["defense"])
        start_x = _mix(eq, [s.name for s in pop["prosecution"]], "row")
        start_y = _mix(eq, [s.name for s in pop["defense"]], "col")
        start_rows, start_cols = list(pop["prosecution"]), list(pop["defense"])
        stopped = f"reached the limit of {max_rounds} rounds"
        rounds = 0
        for rnd in range(1, max_rounds + 1):
            rounds = rnd
            names_p, names_d = [s.name for s in pop["prosecution"]], [s.name for s in pop["defense"]]
            x, y = _mix(eq, names_p, "row"), _mix(eq, names_d, "col")
            kept: dict[str, Spec] = {}
            for side, mine, theirs, opp_mix, own_mix in (
                ("prosecution", pop["prosecution"], pop["defense"], y, x),
                ("defense", pop["defense"], pop["prosecution"], x, y),
            ):
                name = f"best-{side[:3]}-{rnd}"
                cand, train_val, tried = search_best_response(cache, side, mine, theirs, opp_mix, train, budget, rng, name)
                got = cache.vs_mix(side, cand, theirs, opp_mix, heldout)
                # the current equilibrium mix, played against the same opponent mix on the same held-out seeds
                cur = [0.0] * len(heldout)
                for spec, w in zip(mine, own_mix, strict=True):
                    if w > 1e-9:
                        per = cache.vs_mix(side, spec, theirs, opp_mix, heldout)
                        cur = [c + w * p for c, p in zip(cur, per, strict=True)]
                diffs = [g - c for g, c in zip(got, cur, strict=True)]
                mean_d = statistics.fmean(diffs)
                se = statistics.stdev(diffs) / len(diffs) ** 0.5 if len(diffs) > 1 else 0.0
                z = mean_d / se if se > 0 else (float("inf") if mean_d > 0 else 0.0)
                ok = mean_d > 0 and z > ACCEPT_SE
                candidates.append(
                    Candidate(
                        name=name, side=side, plain=describe(cand), params=_params(cand), tried=tried, train_payoff=round(train_val, 4),
                        heldout_candidate=round(statistics.fmean(got), 4), heldout_current=round(statistics.fmean(cur), 4),
                        difference=round(mean_d, 4), standard_error=round(se, 4), z=round(min(z, 99.0), 2), accepted=ok,
                    )
                )
                if ok:
                    kept[side] = cand
            if not kept:
                stopped = f"round {rnd}: neither side found a profile that beat the current equilibrium by more than {ACCEPT_SE:g} standard errors"
                break
            for side, spec in kept.items():
                pop[side].append(spec)
            A, B = cache.mean_matrix(pop["prosecution"], pop["defense"], all_seeds)
            an = analyze([s.name for s in pop["prosecution"]], [s.name for s in pop["defense"]], A, B)
            eq = _pick(an)

        # how exploitable was the first equilibrium? What do the best discovered profiles earn against its opponent mix?
        expl: dict[str, Any] = {}
        for side, mine, theirs, opp_mix, own_mix, base_pop in (
            ("prosecution", pop["prosecution"], start_cols, start_y, start_x, start_rows),
            ("defense", pop["defense"], start_rows, start_x, start_y, start_cols),
        ):
            def value(spec: Spec, side: str = side, theirs: list[Spec] = theirs, opp_mix: list[float] = opp_mix) -> float:
                return statistics.fmean(cache.vs_mix(side, spec, theirs, opp_mix, all_seeds))

            eq_value = sum(w * value(s) for s, w in zip(base_pop, own_mix, strict=True) if w > 1e-9)
            top = max(mine, key=value)
            expl[side] = {
                "equilibrium_payoff": round(eq_value, 4),
                "best_found": top.name,
                "best_found_payoff": round(value(top), 4),
                "gain": round(max(0.0, value(top) - eq_value), 4),
                "found_better": top.profile is not None and value(top) > eq_value + 1e-9,
            }
        final_eq = _eq_summary(eq, pop["prosecution"], pop["defense"])
        report = OracleReport(
            case_id=case.id, surprises=surprises is not None, train_seeds=list(train), heldout_seeds=list(heldout), budget=budget, rng_seed=rng_seed,
            max_rounds=max_rounds, rounds_run=rounds, stopped=stopped, start_strategies=list(START), start_equilibrium=start_eq,
            candidates=candidates,
            final_prosecution=[{"name": s.name, "plain": describe(s), "searched": s.profile is not None} for s in pop["prosecution"]],
            final_defense=[{"name": s.name, "plain": describe(s), "searched": s.profile is not None} for s in pop["defense"]],
            final_equilibrium=final_eq, exploitability=expl, trials=cache.trials, seconds=round(time.perf_counter() - t0, 1), headline="",
        )
    finally:
        cache.close()
    return report.model_copy(update={"headline": headline(report)})


def headline(r: OracleReport) -> str:
    """One generated sentence for the result, from its own numbers."""
    acc = [c for c in r.candidates if c.accepted]
    if not acc:
        return (f"No better lawyer was found: in {r.rounds_run} round(s) and {sum(c.tried for c in r.candidates)} candidate profiles, none beat the "
                f"current equilibrium by more than {ACCEPT_SE:g} standard errors on held-out seeds.")
    sides = sorted({c.side for c in acc})
    gains = {s: r.exploitability[s]["gain"] for s in sides}
    where = " and ".join(f"the {s} (gain {gains[s]:.2f} per trial)" for s in sides)
    return (f"The hand-written styles could be beaten: {len(acc)} better profile(s) were found for {where}, then the game was solved again "
            f"with them.")
