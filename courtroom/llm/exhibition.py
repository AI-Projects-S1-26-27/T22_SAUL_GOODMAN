"""Head-to-head exhibition: a Gemini policy against the four deterministic strategies.

Owner: Engineer 5 (exhibition only).

**These are not equilibrium results and must never be presented as such.** The four
deterministic strategies form a closed, reproducible strategy set whose payoff matrix can be
solved exactly and checked by a best-response verifier. An LLM row cannot be: its payoffs are
not reproducible from a cold cache on another machine, so no equilibrium computed over them
could be certified. This module therefore writes its own file and never touches
``results/payoffs.json``, ``bootstrap.json`` or ``sensitivity.json``.

The harness injects the agent straight into ``Court`` rather than registering it, so
``courtroom.agents.registry`` — part of the certified core — never learns the LLM exists.
"""

from __future__ import annotations

import json
import random
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from courtroom.agents import make_agent
from courtroom.cases import get_case
from courtroom.contracts import Side
from courtroom.engine.trial import Court
from courtroom.llm.client import LLMClient, QuotaExhausted, SpendCeilingReached
from courtroom.llm.factory import make_client
from courtroom.llm.policy import LLMAgent

DETERMINISTIC = ("aggressive", "conservative", "adaptive", "mixed:0.5")


@dataclass
class Cell:
    llm_side: str
    opponent: str
    n: int = 0
    llm_wins: int = 0
    llm_payoff: list[float] = field(default_factory=list)
    opponent_payoff: list[float] = field(default_factory=list)
    llm_spent: list[float] = field(default_factory=list)
    llm_presented: list[int] = field(default_factory=list)
    llm_objections: list[int] = field(default_factory=list)
    llm_sustained: list[int] = field(default_factory=list)
    llm_admitted: list[int] = field(default_factory=list)
    decisions: int = 0
    llm_decisions: int = 0
    trivial_decisions: int = 0
    quota_decisions: int = 0
    reprompts: int = 0
    fallback_reasons: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        mean = lambda xs: round(statistics.fmean(xs), 4) if xs else 0.0  # noqa: E731
        return {
            "llm_side": self.llm_side,
            "opponent": self.opponent,
            "trials": self.n,
            "llm_win_rate": round(self.llm_wins / self.n, 4) if self.n else 0.0,
            "mean_llm_payoff": mean(self.llm_payoff),
            "mean_opponent_payoff": mean(self.opponent_payoff),
            "mean_llm_budget_spent": mean(self.llm_spent),
            "mean_exhibits_offered": mean(self.llm_presented),
            "mean_exhibits_admitted": mean(self.llm_admitted),
            "mean_objections_raised": mean(self.llm_objections),
            "mean_objections_sustained": mean(self.llm_sustained),
            "decisions": self.decisions,
            "trivial_decisions": self.trivial_decisions,
            "quota_decisions": self.quota_decisions,
            "choices": self.decisions - self.trivial_decisions - self.quota_decisions,
            "llm_chosen": self.llm_decisions,
            "fallback_rate": (
                round(1 - self.llm_decisions / (self.decisions - self.trivial_decisions - self.quota_decisions), 4)
                if self.decisions - self.trivial_decisions - self.quota_decisions else 0.0
            ),
            "reprompts": self.reprompts,
            "fallback_reasons": dict(self.fallback_reasons),
        }


def build_court(
    case,
    llm_side: Side,
    opponent: str,
    seed: int,
    client: LLMClient,
) -> tuple[Court, LLMAgent]:
    """The one place an exhibition trial is assembled.

    Used by the live harness and by the offline replay, so a replay from the committed cache
    cannot drift from the run that filled it: same agent seeds, same strategy names, same seed.
    """
    agent = LLMAgent(client=client, rng=random.Random(f"{seed}:llm"))
    other = make_agent(opponent, random.Random(f"{seed}:agent:{opponent}"))
    p, d = (agent, other) if llm_side is Side.PROSECUTION else (other, agent)
    names = ("llm", opponent) if llm_side is Side.PROSECUTION else (opponent, "llm")
    return Court(case, p, d, seed, *names), agent


def _deterministic_baseline(case, seeds, opponents) -> list[dict[str, object]]:
    """The same match-ups with a fixed strategy in the LLM's seat.

    Pure simulation, no API calls, so the comparison is free and exactly reproducible. Without
    it, "the LLM plays differently" is an impression; with it, it is a number.
    """
    from courtroom.engine import run_trial

    mean = lambda xs: round(statistics.fmean(xs), 4) if xs else 0.0  # noqa: E731
    rows: list[dict[str, object]] = []
    for side in (Side.PROSECUTION, Side.DEFENSE):
        for strategy in opponents:
            for opponent in opponents:
                wins, spent, offered, admitted, objections, sustained = 0, [], [], [], [], []
                for seed in seeds:
                    names = (strategy, opponent) if side is Side.PROSECUTION else (opponent, strategy)
                    result = run_trial(case, *names, seed=seed)
                    ledger = result.ledgers[side]
                    wins += int(result.verdict.outcome.favours is side)
                    spent.append(ledger.spent)
                    offered.append(ledger.presented)
                    admitted.append(ledger.admitted)
                    objections.append(ledger.objections)
                    sustained.append(ledger.sustained)
                rows.append({
                    "side": side.value, "strategy": strategy, "opponent": opponent,
                    "trials": len(seeds), "win_rate": round(wins / len(seeds), 4) if seeds else 0.0,
                    "mean_budget_spent": mean(spent),
                    "mean_exhibits_offered": mean(offered),
                    "mean_exhibits_admitted": mean(admitted),
                    "mean_objections_raised": mean(objections),
                    "mean_objections_sustained": mean(sustained),
                })
    return rows


def run_exhibition(
    case_id: str = "helix-espionage",
    seeds: Sequence[int] = (0, 1, 2, 3, 4),
    opponents: Sequence[str] = DETERMINISTIC,
    client: LLMClient | None = None,
    max_calls: int | None = None,
    out_path: Path | None = None,
    on_trial: object | None = None,
) -> dict[str, object]:
    """Play the LLM on both sides against every deterministic strategy.

    Aborts cleanly on the client's spend ceiling or ``max_calls``, reporting whatever
    completed rather than throwing the run away.
    """
    case = get_case(case_id)
    client = client or make_client()
    cells: list[Cell] = []
    aborted: str | None = None
    resumable = False
    completed: list[str] = []
    calls_at_start = client.usage.calls

    for llm_side in (Side.PROSECUTION, Side.DEFENSE):
        for opponent in opponents:
            cell = Cell(llm_side=llm_side.value, opponent=opponent)
            for seed in seeds:
                if max_calls is not None and client.usage.calls >= max_calls:
                    aborted = f"call ceiling of {max_calls} reached"
                    break
                court, agent = build_court(case, llm_side, opponent, seed, client)
                client.start_trial()
                try:
                    result = court.run()
                except QuotaExhausted as exc:
                    # Daily cap: stop cleanly. Everything already answered stays in the cache,
                    # so the next run replays it for free and carries on from here.
                    aborted = str(exc)
                    resumable = True
                    break
                except SpendCeilingReached as exc:
                    aborted = str(exc)
                    break
                completed.append(f"{llm_side.value}|{opponent}|{seed}")
                # Persist after every trial, not at the end: a kill, a crash or a quota stop
                # must never throw away calls that have already been paid for.
                client.save()

                cell.n += 1
                cell.llm_wins += int(result.verdict.outcome.favours is llm_side)
                cell.llm_payoff.append(result.utilities[llm_side])
                cell.opponent_payoff.append(result.utilities[llm_side.opponent])
                ledger = result.ledgers[llm_side]
                cell.llm_spent.append(ledger.spent)
                cell.llm_presented.append(ledger.presented)
                cell.llm_admitted.append(ledger.admitted)
                cell.llm_objections.append(ledger.objections)
                cell.llm_sustained.append(ledger.sustained)
                cell.decisions += agent.decisions
                cell.llm_decisions += agent.llm_decisions
                cell.trivial_decisions += agent.trivial_decisions
                cell.quota_decisions += agent.quota_decisions
                cell.reprompts += agent.reprompts
                for reason, count in agent.fallback_reasons.items():
                    cell.fallback_reasons[reason] = cell.fallback_reasons.get(reason, 0) + count
                if callable(on_trial):
                    on_trial(llm_side.value, opponent, seed, result, agent, client)
                if agent.quota_exhausted:
                    aborted = (
                        "Gemini daily quota exhausted. Progress is cached; rerun the same "
                        "command tomorrow to resume without re-spending calls."
                    )
                    resumable = True
                    break
            cells.append(cell)
            if aborted:
                break
        if aborted:
            break

    baseline = _deterministic_baseline(case, seeds, opponents)

    client.save()
    decisions = sum(c.decisions for c in cells)
    trivial = sum(c.trivial_decisions for c in cells)
    quota_hit = sum(c.quota_decisions for c in cells)
    choices = decisions - trivial - quota_hit
    chosen = sum(c.llm_decisions for c in cells)
    report: dict[str, object] = {
        "kind": "exhibition",
        "not_equilibrium_analysis": (
            "These are exhibition results. An LLM policy is not reproducible from a cold cache, "
            "so its payoffs cannot be certified by the best-response verifier and are deliberately "
            "excluded from the payoff matrices, the bootstrap and the sensitivity sweep."
        ),
        "case_id": case_id,
        "model": client.model,
        "provider": client.provider_tag,
        "temperature": client.temperature,
        "seeds": list(seeds),
        "opponents": list(opponents),
        "aborted": aborted,
        "resumable": resumable,
        "resume_hint": (
            "Rerun the identical command. Every answered prompt is in the committed cache, so "
            "finished work replays as cache hits at no cost and the run continues where it stopped."
            if resumable else None
        ),
        "completed_trials": completed,
        "api_calls_this_run": client.usage.calls - calls_at_start,
        # Each cache entry was paid for by exactly one real call at some point, so this is the
        # cumulative cost of producing these results, not just the cost of the latest run.
        "cached_responses_total": len(client._cache),
        "decisions": decisions,
        "trivial_decisions": trivial,
        "quota_decisions": quota_hit,
        "choices": choices,
        "llm_chosen": chosen,
        "overall_fallback_rate": round(1 - chosen / choices, 4) if choices else 0.0,
        "usage": client.usage.as_dict(),
        "cells": [c.as_dict() for c in cells],
        "deterministic_baseline": baseline,
    }
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
