"""Robustness agents: Chaos (fuzzing), Reckless (wild but legal-ish) and Scripted (deterministic test fixtures).

Owner: Engineer 4.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

from courtroom.agents.base import Oracle
from courtroom.contracts import Action, ActionType, ObjectionGround, PartyView, Phase, Side
from courtroom.judge.rules import IMPEACHMENT_COST, MOTION_COST, OBJECTION_COST


class AgentCrash(RuntimeError):
    """Raised deliberately by the Chaos agent to test fault isolation."""


class ChaosAgent:
    """Emits random, frequently illegal actions, and occasionally raises.

    The engine must survive this agent with no uncaught exception, finite
    trial length, and a well-formed verdict.
    """

    name = "chaos"

    def __init__(self, rng: random.Random, crash_rate: float = 0.05) -> None:
        self.rng = rng
        self.crash_rate = crash_rate

    def opening_statement(self, side: Side) -> str:
        return "Counsel appears to have no strategy whatsoever."

    def act(self, view: PartyView, oracle: Oracle) -> Action:
        r = self.rng
        if r.random() < self.crash_rate:
            raise AgentCrash("chaos agent crashed on purpose")
        own_ids = [e.id for e in view.own_evidence]
        junk_ids = ["NOPE-404", *view.admitted, *own_ids]
        return Action(
            actor=r.choice([view.side, view.side, view.side, view.side.opponent]),
            type=r.choice(list(ActionType)),
            evidence_id=r.choice([None, *junk_ids]) if junk_ids else None,
            witness_id=r.choice([None, "W-GHOST", *[w for _, w in view.impeachment_options]]),
            ground=r.choice([None, *ObjectionGround]),
            rationale="¯\\_(ツ)_/¯",
        )


class RecklessAgent:
    """A wild but watchable lawyer: legal moves picked without thinking, plus the odd rule break.

    It throws in its evidence in random order (flaws and all), objects on a whim with a random
    ground, sometimes attacks a witness, and about one move in ten is out of turn. Unlike
    ``ChaosAgent`` it never crashes and mostly plays the game, so a trial with it still tells a story.
    """

    name = "reckless"

    def __init__(self, rng: random.Random, rule_break_rate: float = 0.1) -> None:
        self.rng = rng
        self.rule_break_rate = rule_break_rate

    def opening_statement(self, side: Side) -> str:
        return "Counsel will throw everything at the wall and see what sticks."

    def act(self, view: PartyView, oracle: Oracle) -> Action:
        r, side = self.rng, view.side
        if r.random() < self.rule_break_rate:
            return Action(actor=side, type=ActionType.MOTION_DIRECTED_VERDICT, rationale="Out of turn, on impulse.")
        if view.window == "motion":
            move = view.budget >= MOTION_COST and r.random() < 0.5
            return Action(actor=side, type=ActionType.MOTION_DIRECTED_VERDICT if move else ActionType.PASS, rationale="Gut feeling.")
        if view.window == "response":
            if view.pending is not None and view.budget >= OBJECTION_COST and r.random() < 0.5:
                return Action(actor=side, type=ActionType.OBJECT, ground=r.choice(list(ObjectionGround)), rationale="Object first, think later.")
            return Action(actor=side, type=ActionType.PASS, rationale="Let it go.")
        unshown = [
            e
            for e in view.own_evidence
            if e.id not in view.presented
            and e.presentation_cost <= view.budget
            and (view.phase is not Phase.REBUTTAL or e.id in view.rebuttal_targets)
        ]
        if view.impeachment_options and view.budget >= IMPEACHMENT_COST and r.random() < 0.3:
            ev_id, witness = r.choice(view.impeachment_options)
            return Action(actor=side, type=ActionType.IMPEACH, evidence_id=ev_id, witness_id=witness, rationale="Go after the witness.")
        if unshown:
            return Action(actor=side, type=ActionType.PRESENT_EVIDENCE, evidence_id=r.choice(unshown).id, rationale="Throw it in.")
        return Action(actor=side, type=ActionType.REST, rationale="Out of ammunition.")


class ScriptedAgent:
    """Replays a fixed list of actions (then rests/passes). Used by tests and demos."""

    def __init__(self, script: Sequence[Action], name: str = "scripted") -> None:
        self._script = list(script)
        self.name = name

    def opening_statement(self, side: Side) -> str:
        return "Scripted counsel."

    def act(self, view: PartyView, oracle: Oracle) -> Action:
        if self._script:
            return self._script.pop(0)
        kind = ActionType.REST if view.window == "primary" else ActionType.PASS
        return Action(actor=view.side, type=kind)
