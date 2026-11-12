"""Exhibition table: the AI counsel against the four hand-written styles. Not certified, never a payoff table.

For each case and each style, the AI lawyer plays both sides (as Accuser against that style as Defender, and as Defender against
that style as Accuser) over a few seeds. Every cell reports how often the AI lawyer won, what it earned, and how often its model
failed to give a usable move (so the table shows how much of it is the model and how much is the Smart style filling in). Beside
each cell sits the same arrangement played by the Smart style, the lawyer the AI falls back to, as a reference.

Every model answer is cached (see ``courtroom.llm.client``), so a table that was run once with a model replays offline and
exactly. This harness is built and tested against a stub; it is run for real only when a backend answers.
"""

from __future__ import annotations

import random
import statistics
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict

from courtroom.agents import make_agent
from courtroom.contracts import CaseFile, Side, Surprises
from courtroom.engine import run_with_agents
from courtroom.llm.client import LLMClient
from courtroom.llm.policy import LLMAgent

STYLES = ("aggressive", "conservative", "adaptive", "reckless")


class Cell(BaseModel):
    model_config = ConfigDict(frozen=True)
    case_id: str
    ai_side: str
    style: str
    seeds: list[int]
    ai_win_rate: float
    ai_mean_payoff: float
    style_mean_payoff: float
    smart_reference_win_rate: float  # the Smart style in the AI's seat, same opponent, same seeds
    smart_reference_payoff: float
    fallback_rate: float
    model_choices: int
    fallbacks: int


class Exhibition(BaseModel):
    model_config = ConfigDict(frozen=True)
    label: str = "exhibition, not certified"
    surprises: bool
    model: str | None
    provider: str | None
    cells: list[Cell]
    usage: dict[str, Any]


def _won(result, side: Side) -> bool:  # type: ignore[no-untyped-def]
    return result.verdict.outcome.favours is side


def run_exhibition(
    cases: Sequence[CaseFile], client: LLMClient, seeds: Sequence[int] = (0, 1, 2), styles: Sequence[str] = STYLES, surprises: Surprises | None = None
) -> Exhibition:
    cells: list[Cell] = []
    for case in cases:
        for ai_side in (Side.PROSECUTION, Side.DEFENSE):
            for style in styles:
                ai_wins = smart_wins = fb = mc = 0
                ai_u: list[float] = []
                style_u: list[float] = []
                smart_u: list[float] = []
                for s in seeds:
                    client.start_trial()
                    ai = LLMAgent(client, random.Random(f"{s}:agent:{ai_side.value}"))
                    other_side = ai_side.opponent
                    other = make_agent(style, random.Random(f"{s}:agent:{other_side.value}"))
                    ref = make_agent("adaptive", random.Random(f"{s}:agent:{ai_side.value}"))
                    other2 = make_agent(style, random.Random(f"{s}:agent:{other_side.value}"))
                    pair = (ai, other) if ai_side is Side.PROSECUTION else (other, ai)
                    pair_ref = (ref, other2) if ai_side is Side.PROSECUTION else (other2, ref)
                    names = ("llm", style) if ai_side is Side.PROSECUTION else (style, "llm")
                    r = run_with_agents(case, pair[0], pair[1], s, surprises, names[0], names[1])
                    rr = run_with_agents(case, pair_ref[0], pair_ref[1], s, surprises)
                    ai_wins += _won(r, ai_side)
                    smart_wins += _won(rr, ai_side)
                    ai_u.append(r.utilities[ai_side])
                    style_u.append(r.utilities[ai_side.opponent])
                    smart_u.append(rr.utilities[ai_side])
                    fb += ai.choices - ai.llm_decisions
                    mc += ai.llm_decisions
                n = len(seeds)
                cells.append(
                    Cell(
                        case_id=case.id, ai_side=ai_side.value, style=style, seeds=list(seeds), ai_win_rate=round(ai_wins / n, 4),
                        ai_mean_payoff=round(statistics.fmean(ai_u), 4), style_mean_payoff=round(statistics.fmean(style_u), 4),
                        smart_reference_win_rate=round(smart_wins / n, 4), smart_reference_payoff=round(statistics.fmean(smart_u), 4),
                        fallback_rate=round(fb / (fb + mc), 4) if fb + mc else 0.0, model_choices=mc, fallbacks=fb,
                    )
                )
    client.save()
    return Exhibition(surprises=surprises is not None, model=client.last_model, provider=client.last_source, cells=cells, usage=client.usage.as_dict())
