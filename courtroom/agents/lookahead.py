"""A lawyer that thinks ahead: depth-limited alpha-beta over its own next moves.

This is **not** one of the four certified styles and it is not in the recorded trials. It is an extra that can be picked live and is
compared with the four in a clearly labelled table. It uses only what any counsel is given: its own :class:`PartyView` and the public
scoring :class:`Oracle`. It never reads the case file, the opponent's unpresented evidence, or the opponent's code.

How it decides:

* **Its own turn.** It searches the next few things it could do (offer an exhibit, impeach a witness, rest), and after each offer the
  reply it fears most: the opponent either lets the exhibit in or objects on a ground that would be sustained. It knows its own
  exhibits' real flaws (any counsel does), so it assumes the opponent objects whenever that hurts it most. Alpha-beta skips the lines
  that cannot change the choice. The search ends after ``depth`` moves of its own or when it rests; the position is then scored by a
  smooth estimate of "would the Accuser's record clear the bar" and the record's log-odds potential (the unit the other styles value a move in), plus the money and sanctions spent so far.
* **When the opponent offers an exhibit.** It is told, through its noisy signal, how likely each ground is to be valid (its belief). The
  choice between letting the exhibit in and objecting on a ground is an expectation over that belief: with probability *b* the objection is
  sustained, otherwise it is overruled and costs a sanction. That is where hidden information enters.
* **Directed verdict.** The same rule as the Adaptive style.

Everything it assumes about the future is a simplification: it does not model the opponent's own future offers, and the leaf estimate is a
heuristic. The judge, as always, decides the verdict exactly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from courtroom.agents.base import COST_WEIGHT, LOGODDS_VALUE, SANCTION_WEIGHT, Oracle
from courtroom.agents.policies import ADAPTIVE, CounselAgent
from courtroom.contracts import Action, ActionType, EvidenceItem, ObjectionGround, PartyView, Phase, Side
from courtroom.judge.admissibility import BAD_FAITH_GROUNDS, valid_grounds
from courtroom.judge.rules import (
    IMPEACHMENT_COST,
    OBJECTION_COST,
    SANCTION_BAD_FAITH_EVIDENCE,
    SANCTION_OVERRULED_OBJECTION,
    THRESHOLD_LOG_ODDS,
)

WIN_VALUE = 10.0  # the winner's prize in the payoff (kept equal to courtroom.engine.utility.WIN_VALUE)
SLOPE = 2.0  # how sharply the leaf estimate turns from "losing" to "winning" as the weakest element crosses the bar
DEFAULT_DEPTH = 3


@dataclass(frozen=True, slots=True)
class _Plan:
    """What the lookahead has assumed so far: items offered and let in, witnesses impeached, and the money and sanctions each side bears."""

    added: frozenset[str] = frozenset()
    impeached: tuple[str, ...] = ()
    own_spent: float = 0.0
    opp_spent: float = 0.0
    own_sanctions: float = 0.0
    opp_sanctions: float = 0.0
    done: frozenset[str] = frozenset()  # items already offered in this plan


class LookaheadAgent:
    name = "lookahead"

    def __init__(self, depth: int = DEFAULT_DEPTH, prune: bool = True) -> None:
        self.depth = depth
        self.prune = prune  # False: plain minimax over the same moves (for the equality test and the node count)
        self.nodes = 0  # alpha-beta nodes visited so far, for reporting
        self._motion_helper = CounselAgent(ADAPTIVE)

    def opening_statement(self, side: Side) -> str:
        role = "The People" if side is Side.PROSECUTION else "The defense"
        return f"{role} proceed by thinking ahead: weighing the next few moves and the reply to each before acting. (Exhibition style, not certified.)"

    # ------------------------------------------------------------------ dispatch

    def act(self, view: PartyView, oracle: Oracle) -> Action:
        if view.window == "motion":
            return self._motion_helper.act(view, oracle)
        if view.window == "response":
            return self._respond(view, oracle)
        return self._primary(view, oracle)

    # ------------------------------------------------------------------ the estimate of a position

    def _value(self, view: PartyView, oracle: Oracle, p: _Plan) -> float:
        """The side's estimated advantage (its utility minus the opponent's) if the trial ended on the plan's record."""
        lo = oracle.log_odds(add=p.added, also_impeach=p.impeached)
        tau = float(THRESHOLD_LOG_ODDS[view.standard])
        margin = min(lo.values()) - tau
        p_acc = 1.0 / (1.0 + math.exp(-SLOPE * margin))
        p_own = p_acc if view.side is Side.PROSECUTION else 1.0 - p_acc
        own = (view.reserve_basis - view.budget) + p.own_spent
        opp = (view.reserve_basis - view.opponent_budget) + p.opp_spent
        # The log-odds potential is the same quantity, in the same units (LOGODDS_VALUE), that the hand-written styles use to value a move.
        # It matters here because a plan too short to clear the bar would otherwise look worthless, and the lawyer would give up.
        sign = 1.0 if view.side is Side.PROSECUTION else -1.0
        shaping = LOGODDS_VALUE * sign * oracle.potential(lo)
        return shaping + WIN_VALUE * (2 * p_own - 1) - COST_WEIGHT * (own - opp) - SANCTION_WEIGHT * (p.own_sanctions - p.opp_sanctions)

    # ------------------------------------------------------------------ the opponent's offer: an expectation over beliefs

    def _respond(self, view: PartyView, oracle: Oracle) -> Action:
        pending = view.pending
        if pending is None or view.budget < OBJECTION_COST:
            return Action(actor=view.side, type=ActionType.PASS, rationale="No objection.")
        let_in = self._value(view, oracle, _Plan(added=frozenset({pending.evidence_id})))
        best_value, best_ground = let_in, None
        for ground in ObjectionGround:
            belief = pending.defect_belief.get(ground, 0.0)
            if belief <= 0.0:
                continue
            sustained = self._value(
                view,
                oracle,
                _Plan(
                    opp_sanctions=SANCTION_BAD_FAITH_EVIDENCE if ground in BAD_FAITH_GROUNDS else 0.0,
                    own_spent=OBJECTION_COST,
                ),
            )
            overruled = self._value(
                view,
                oracle,
                _Plan(added=frozenset({pending.evidence_id}), own_spent=OBJECTION_COST, own_sanctions=SANCTION_OVERRULED_OBJECTION),
            )
            expected = belief * sustained + (1 - belief) * overruled
            if expected > best_value + 1e-9:
                best_value, best_ground = expected, ground
        if best_ground is None:
            return Action(actor=view.side, type=ActionType.PASS, rationale=f"Let it in: expected value {let_in:+.2f}, no objection beats it.")
        return Action(
            actor=view.side,
            type=ActionType.OBJECT,
            evidence_id=pending.evidence_id,
            ground=best_ground,
            rationale=f"Objection, {best_ground.value}: expected value {best_value:+.2f} against {let_in:+.2f} for letting it in.",
        )

    # ------------------------------------------------------------------ its own turn: alpha-beta over the next few moves

    def _options(self, view: PartyView, p: _Plan) -> list[tuple[str, str, str]]:
        """Moves available in the plan: ('offer', item id, ''), ('impeach', item id, witness id)."""
        spendable = view.budget - p.own_spent
        out: list[tuple[str, str, str]] = []
        for item in view.own_evidence:
            if item.id in view.presented or item.id in p.done or item.presentation_cost > spendable:
                continue
            if view.phase is Phase.REBUTTAL and item.id not in view.rebuttal_targets:
                continue
            out.append(("offer", item.id, ""))
        if spendable >= IMPEACHMENT_COST:
            own = {i.id: i for i in view.own_evidence}
            for item_id, witness in view.impeachment_options:
                it = own.get(item_id)
                if it is not None and witness in it.impeaches and witness not in p.impeached:
                    out.append(("impeach", item_id, witness))
        return out

    def _replies(self, view: PartyView, p: _Plan, item_id: str, items: dict[str, EvidenceItem]) -> list[_Plan]:
        """After this side offers an item: the opponent lets it in, or objects on a ground that would be sustained."""
        item = items[item_id]
        paid = p.own_spent + item.presentation_cost
        done = p.done | {item_id}
        out = [_Plan(added=p.added | {item_id}, impeached=p.impeached, own_spent=paid, opp_spent=p.opp_spent,
                     own_sanctions=p.own_sanctions, opp_sanctions=p.opp_sanctions, done=done)]
        for ground in valid_grounds(item, view.case_type):
            out.append(_Plan(
                added=p.added, impeached=p.impeached, own_spent=paid, opp_spent=p.opp_spent + OBJECTION_COST,
                own_sanctions=p.own_sanctions + (SANCTION_BAD_FAITH_EVIDENCE if ground in BAD_FAITH_GROUNDS else 0.0),
                opp_sanctions=p.opp_sanctions, done=done,
            ))
        return out

    def _impeached(self, p: _Plan, item_id: str, witness: str) -> _Plan:
        return _Plan(added=p.added, impeached=(*p.impeached, witness), own_spent=p.own_spent + IMPEACHMENT_COST,
                     opp_spent=p.opp_spent, own_sanctions=p.own_sanctions, opp_sanctions=p.opp_sanctions, done=p.done)

    def _ordered_options(self, view: PartyView, oracle: Oracle, p: _Plan, items: dict[str, EvidenceItem]) -> list[tuple[str, str, str]]:
        """Look first at the move that scores best if the opponent simply lets it in. Alpha-beta gives the same answer in any order."""
        def key(opt: tuple[str, str, str]) -> tuple[float, tuple[str, str, str]]:
            kind, item_id, witness = opt
            child = self._impeached(p, item_id, witness) if kind == "impeach" else self._replies(view, p, item_id, items)[0]
            return (-self._value(view, oracle, child), opt)
        return [o for _, o in sorted(key(o) for o in self._options(view, p))]

    def _max(self, view: PartyView, oracle: Oracle, p: _Plan, depth: int, alpha: float, beta: float, items: dict[str, EvidenceItem]) -> float:
        """This side to move: it may rest (score the plan as it stands) or make one more move."""
        self.nodes += 1
        best = self._value(view, oracle, p)
        if depth == 0:
            return best
        alpha = max(alpha, best)
        if self.prune and alpha >= beta:
            return best
        for kind, item_id, witness in self._ordered_options(view, oracle, p, items):
            v = (
                self._max(view, oracle, self._impeached(p, item_id, witness), depth - 1, alpha, beta, items)
                if kind == "impeach"
                else self._min(view, oracle, p, item_id, depth, alpha, beta, items)
            )
            best = max(best, v)
            alpha = max(alpha, best)
            if self.prune and alpha >= beta:
                break
        return best

    def _min(self, view: PartyView, oracle: Oracle, p: _Plan, item_id: str, depth: int, alpha: float, beta: float, items: dict[str, EvidenceItem]) -> float:
        """The opponent replies to an offer with whatever hurts this side most."""
        self.nodes += 1
        best = float("inf")
        replies = sorted(self._replies(view, p, item_id, items), key=lambda c: self._value(view, oracle, c))
        for child in replies:
            best = min(best, self._max(view, oracle, child, depth - 1, alpha, beta, items))
            beta = min(beta, best)
            if self.prune and alpha >= beta:
                break
        return best

    def _primary(self, view: PartyView, oracle: Oracle) -> Action:
        root = _Plan()
        items = {i.id: i for i in view.own_evidence}
        stop = self._value(view, oracle, root)
        best_v, best_opt = stop, None
        alpha = stop
        for opt in self._ordered_options(view, oracle, root, items):
            kind, item_id, witness = opt
            v = (
                self._max(view, oracle, self._impeached(root, item_id, witness), self.depth - 1, alpha, float("inf"), items)
                if kind == "impeach"
                else self._min(view, oracle, root, item_id, self.depth, alpha, float("inf"), items)
            )
            if v > best_v + 1e-9:
                best_v, best_opt = v, opt
                alpha = max(alpha, v)
        if best_opt is None:
            return Action(actor=view.side, type=ActionType.REST, rationale=f"Thinking ahead, nothing beats resting now ({stop:+.2f}).")
        kind, item_id, witness = best_opt
        if kind == "impeach":
            return Action(actor=view.side, type=ActionType.IMPEACH, evidence_id=item_id, witness_id=witness,
                          rationale=f"Thinking {self.depth} moves ahead: impeaching {witness} with {item_id} leads to {best_v:+.2f}, against {stop:+.2f} for resting.")
        return Action(actor=view.side, type=ActionType.PRESENT_EVIDENCE, evidence_id=item_id,
                      rationale=f"Thinking {self.depth} moves ahead: offering {item_id} leads to {best_v:+.2f}, against {stop:+.2f} for resting.")
