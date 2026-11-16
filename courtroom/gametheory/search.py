"""The trial as a game tree: exact minimax and alpha-beta on the open-file relaxation.

The trial is a *sequential* game: lawyers take turns offering evidence, the other side may object, and so on. The payoff-table
chapters flatten all of that into one choice of style. This module opens it up again and searches the tree.

It does **not** re-implement the rules. A node is a real :class:`~courtroom.engine.Court` (the same class that runs every trial);
the legal moves are found by asking the real ``validate`` and the real judge; a move is applied by the real ``_dispatch``; and the value
at the end is the real judge's verdict through the real utility function. Only the logging is switched off, so that a node is cheap.
A test replays a scripted trial through this tree and through the engine and checks that they agree.

**The open-file relaxation.** The real game has hidden information: a lawyer sees each opposing exhibit only through a noisy
signal, so it can misjudge whether an objection would be sustained. Here both sides see all the evidence and all its flaws, with no
perception noise. Then every move has a deterministic outcome, and the game is one of perfect information. To make minimax and
alpha-beta applicable the payoff is also made **zero-sum**: the value of a finished trial is the Accuser's utility minus the Defender's
(10 for winning, minus 0.3 per unit of budget spent, minus sanctions). The Accuser maximises it and the Defender minimises it.
This is a relaxation, not the game the certified analysis solves: that game has hidden information and is general-sum.

Two moves are left out because they are strictly worse than another move in every state, and a test checks the value is unchanged when
they are put back: passing a turn (acting or resting now is never worse, because only the leading side acts within a phase) and an
objection or impeachment that the judge would reject (it costs money and a sanction and changes nothing else).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction

from pydantic import BaseModel, ConfigDict

from courtroom.agents import make_agent
from courtroom.contracts import (
    Action,
    ActionType,
    CaseFile,
    ObjectionGround,
    Phase,
    RuleFiring,
    Side,
    Window,
)
from courtroom.engine import Court
from courtroom.engine.utility import utilities
from courtroom.procedure import ProcedureState, validate

MAX_NODES_DEFAULT = 2_000_000


class TooBig(Exception):
    """The search would visit more nodes than it was allowed."""


# --------------------------------------------------------------------------- a node of the tree


def _copy_state(st: ProcedureState) -> ProcedureState:
    return ProcedureState(
        case=st.case,
        phase=st.phase,
        pending=st.pending,
        presented=list(st.presented),
        admitted=list(st.admitted),
        excluded=list(st.excluded),
        impeachments=dict(st.impeachments),
        used_impeachments=set(st.used_impeachments),
        turns_used=dict(st.turns_used),
        consecutive_passes=st.consecutive_passes,
        motion_made=st.motion_made,
        directed=st.directed,
        ledgers={s: replace(led) for s, led in st.ledgers.items()},
    )


class Node(Court):
    """A trial in progress, searchable. The rules are the engine's own; only the event log is switched off."""

    def __init__(self, case: CaseFile) -> None:
        # Agents are never asked for a move here: the search supplies them. The names only fill the parent's bookkeeping.
        import random

        super().__init__(case, make_agent("aggressive", random.Random(0)), make_agent("conservative", random.Random(0)), seed=0)
        self.state.enter(Phase.PROSECUTION_CASE)  # the opening statements change nothing
        self.state.consecutive_passes = 0

    def _emit(self, *args: object, **kwargs: object) -> None:  # the search keeps no transcript
        return None

    def clone(self) -> Node:
        n = object.__new__(Node)
        n.__dict__.update(self.__dict__)
        n.state = _copy_state(self.state)
        n._hostile = set(self._hostile)
        return n

    # -- who moves ------------------------------------------------------------------

    def settle(self) -> tuple[Side, Window] | None:
        """Play out the moves nobody chooses (a side that has used up its turns is deemed to rest) and say who decides next."""
        st = self.state
        while st.phase not in (Phase.DELIBERATION, Phase.CLOSED):
            side, window = st.expected()  # type: ignore[misc]
            if window == "primary" and st.turns_left() == 0:
                self._rest(side, RuleFiring(rule_id="TURN-CAP", detail="turns exhausted"))
                continue
            return side, window
        return None

    def legal_actions(self, prune: bool = True) -> list[Action]:
        """Every move the procedure allows now. With ``prune`` the strictly worse moves described above are left out."""
        who = self.settle()
        if who is None:
            return []
        side, window = who
        st, case = self.state, self.case
        cands: list[Action] = []
        if window == "primary":
            for item in case.evidence:
                if item.owner is side:
                    cands.append(Action(actor=side, type=ActionType.PRESENT_EVIDENCE, evidence_id=item.id))
                    for w in st.testified_witnesses(side.opponent) if item.id in st.admitted else ():
                        if not prune or w in item.impeaches:
                            cands.append(Action(actor=side, type=ActionType.IMPEACH, evidence_id=item.id, witness_id=w))
            cands.append(Action(actor=side, type=ActionType.REST))
            if not prune:
                cands.append(Action(actor=side, type=ActionType.PASS))
        elif window == "response":
            pending = case.item(st.pending) if st.pending else None
            if pending is not None:
                for g in ObjectionGround:
                    if not prune or self.judge.rule_on_objection(pending, g)[0]:
                        cands.append(Action(actor=side, type=ActionType.OBJECT, evidence_id=pending.id, ground=g))
            cands.append(Action(actor=side, type=ActionType.PASS))
        else:
            cands.append(Action(actor=side, type=ActionType.MOTION_DIRECTED_VERDICT))
            cands.append(Action(actor=side, type=ActionType.PASS))
        return [a for a in cands if validate(a, st, side, window) is None]

    def apply(self, action: Action) -> None:
        """Make a move with the engine's own dispatcher."""
        side, window = self.settle()  # type: ignore[misc]
        if window == "response":
            self.state.ledgers[side].response_windows += 1
        self._dispatch(side, window, action)

    # -- value ------------------------------------------------------------------------

    def verdict_now(self):
        st = self.state
        return self.judge.deliberate(st.admitted, st.impeachments, st.directed)

    def utilities_now(self) -> dict[Side, float]:
        """What each side would get if the trial ended on the current record (the real judge and the real payoff)."""
        v = self.verdict_now()
        return utilities(v.outcome, {s: self.state.ledgers[s].freeze() for s in Side})

    def advantage_now(self) -> float:
        u = self.utilities_now()
        return round(u[Side.PROSECUTION] - u[Side.DEFENSE], 6)

    def finished(self) -> bool:
        return self.settle() is None


# --------------------------------------------------------------------------- minimax and alpha-beta


class Stats:
    def __init__(self, max_nodes: int) -> None:
        self.nodes = 0
        self.leaves = 0
        self.cutoffs = 0
        self.max_nodes = max_nodes

    def visit(self) -> None:
        self.nodes += 1
        if self.nodes > self.max_nodes:
            raise TooBig(f"more than {self.max_nodes} nodes")


def _children(node: Node, prune: bool) -> list[tuple[Action, Node]]:
    out = []
    for a in node.legal_actions(prune):
        c = node.clone()
        c.apply(a)
        out.append((a, c))
    return out


def minimax(node: Node, stats: Stats, prune: bool = True) -> float:
    """Plain minimax: look at every line of play."""
    stats.visit()
    who = node.settle()
    if who is None:
        stats.leaves += 1
        return node.advantage_now()
    kids = _children(node, prune)
    values = [minimax(c, stats, prune) for _, c in kids]
    return max(values) if who[0] is Side.PROSECUTION else min(values)


def order_best_first(kids: list[tuple[Action, Node]], maximising: bool) -> list[tuple[Action, Node]]:
    """Look first at the move that already looks best for the side choosing (the value if the trial ended right after it)."""
    return sorted(kids, key=lambda ac: ac[1].advantage_now() * (-1 if maximising else 1))


def alphabeta(
    node: Node,
    stats: Stats,
    alpha: float = float("-inf"),
    beta: float = float("inf"),
    ordering: Callable[[list[tuple[Action, Node]], bool], list[tuple[Action, Node]]] | None = None,
    prune: bool = True,
) -> float:
    """Minimax that skips lines that cannot change the answer: once one side already has a better option elsewhere, the rest of a branch is ignored."""
    stats.visit()
    who = node.settle()
    if who is None:
        stats.leaves += 1
        return node.advantage_now()
    maximising = who[0] is Side.PROSECUTION
    kids = _children(node, prune)
    if ordering is not None:
        kids = ordering(kids, maximising)
    best = float("-inf") if maximising else float("inf")
    for _, c in kids:
        v = alphabeta(c, stats, alpha, beta, ordering, prune)
        if maximising:
            best = max(best, v)
            alpha = max(alpha, best)
        else:
            best = min(best, v)
            beta = min(beta, best)
        if alpha >= beta:
            stats.cutoffs += 1
            break
    return best


def principal_variation(root: Node, value: float, prune: bool = True, limit: int = 60) -> list[str]:
    """One line of best play: at each node a move whose exact value equals the root's (found with alpha-beta)."""
    node, line = root, []
    while len(line) < limit:
        who = node.settle()
        if who is None:
            break
        maximising = who[0] is Side.PROSECUTION
        chosen = None
        for a, c in order_best_first(_children(node, prune), maximising):
            if abs(alphabeta(c, Stats(10**9), ordering=order_best_first, prune=prune) - value) < 1e-9:
                chosen = (a, c)
                break
        if chosen is None:
            break
        a, node = chosen
        line.append(describe(a))
    return line


def describe(a: Action) -> str:
    who = "Accuser" if a.actor is Side.PROSECUTION else "Defender"
    match a.type:
        case ActionType.PRESENT_EVIDENCE:
            return f"{who} offers {a.evidence_id}"
        case ActionType.OBJECT:
            return f"{who} objects to {a.evidence_id} ({a.ground.value if a.ground else '?'})"
        case ActionType.IMPEACH:
            return f"{who} impeaches {a.witness_id} with {a.evidence_id}"
        case ActionType.MOTION_DIRECTED_VERDICT:
            return f"{who} moves for a directed verdict"
        case ActionType.PASS:
            return f"{who} passes"
        case ActionType.REST:
            return f"{who} rests"
    return f"{who} {a.type.value}"


# --------------------------------------------------------------------------- the report


class TreeReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    case_id: str
    title: str
    evidence: tuple[int, int]  # Accuser items, Defender items
    value: float | None  # the Accuser's advantage with best play on both sides (None if the search was cut off)
    value_exact: str | None
    minimax_nodes: int | None  # None: more than the allowed number of nodes
    alphabeta_nodes: int | None
    alphabeta_ordered_nodes: int | None
    minimax_leaves: int | None
    alphabeta_ordered_cutoffs: int | None
    pruned_share: float | None  # 1 - ordered alpha-beta nodes / minimax nodes
    ordering_saving: float | None  # 1 - ordered / unordered alpha-beta nodes
    values_agree: bool | None
    best_play: list[str]
    seconds: float
    note: str


def solve_case(
    case: CaseFile,
    max_nodes: int = MAX_NODES_DEFAULT,
    with_minimax: bool = True,
    with_line: bool = True,
    with_unordered: bool = True,
) -> TreeReport:
    """Solve the open-file game for ``case`` three ways and compare. Plain minimax is skipped (and reported as too big) past ``max_nodes``."""
    t0 = time.perf_counter()
    root = Node(case)
    mm_nodes = mm_leaves = ab_nodes = abo_nodes = abo_cuts = None
    mm_val = ab_val = abo_val = None
    if with_minimax:
        s = Stats(max_nodes)
        try:
            mm_val = minimax(root.clone(), s)
            mm_nodes, mm_leaves = s.nodes, s.leaves
        except TooBig:
            pass
    if with_unordered:
        s = Stats(max_nodes)
        try:
            ab_val = alphabeta(root.clone(), s)
            ab_nodes = s.nodes
        except TooBig:
            pass
    s = Stats(max_nodes)
    try:
        abo_val = alphabeta(root.clone(), s, ordering=order_best_first)
        abo_nodes, abo_cuts = s.nodes, s.cutoffs
    except TooBig:
        pass
    vals = [v for v in (mm_val, ab_val, abo_val) if v is not None]
    value = abo_val if abo_val is not None else (ab_val if ab_val is not None else mm_val)
    agree = len({round(v, 6) for v in vals}) <= 1 if vals else None
    line = principal_variation(root, value) if (value is not None and with_line) else []
    own = [i for i in case.evidence if i.owner is Side.PROSECUTION]
    opp = [i for i in case.evidence if i.owner is Side.DEFENSE]
    return TreeReport(
        case_id=case.id,
        title=case.title,
        evidence=(len(own), len(opp)),
        value=value,
        value_exact=str(Fraction(repr(value))) if value is not None else None,
        minimax_nodes=mm_nodes,
        alphabeta_nodes=ab_nodes,
        alphabeta_ordered_nodes=abo_nodes,
        minimax_leaves=mm_leaves,
        alphabeta_ordered_cutoffs=abo_cuts,
        pruned_share=round(1 - abo_nodes / mm_nodes, 4) if mm_nodes and abo_nodes else None,
        ordering_saving=round(1 - abo_nodes / ab_nodes, 4) if ab_nodes and abo_nodes else None,
        values_agree=agree,
        best_play=line,
        seconds=round(time.perf_counter() - t0, 2),
        note=(
            "Open-file relaxation: both sides see every exhibit and flaw, no perception noise, and the payoff is zero-sum "
            "(the Accuser's utility minus the Defender's). Plain minimax, alpha-beta, and alpha-beta with best-first ordering "
            "must give the same value."
        ),
    )



# --------------------------------------------------------------------------- a picture of the search


def trace(case: CaseFile, ordering: bool = True, prune: bool = True, max_nodes: int = 5000) -> dict[str, object]:
    """Alpha-beta on ``case`` as a nested record of every node visited, with the moves it skipped, for drawing a small pruned tree."""
    stats = Stats(max_nodes)
    side_name = {Side.PROSECUTION: "Accuser", Side.DEFENSE: "Defender"}

    def walk(node: Node, move: str, alpha: float, beta: float) -> dict[str, object]:
        stats.visit()
        who = node.settle()
        if who is None:
            v = node.advantage_now()
            return {"move": move, "kind": "leaf", "value": v, "verdict": node.verdict_now().outcome.value}
        maximising = who[0] is Side.PROSECUTION
        kids = [(a, c) for a, c in _children(node, prune)]
        if ordering:
            kids = order_best_first(kids, maximising)
        best = float("-inf") if maximising else float("inf")
        out: list[dict[str, object]] = []
        skipped: list[str] = []
        cut = False
        for k, (a, c) in enumerate(kids):
            if cut:
                skipped.append(describe(a))
                continue
            child = walk(c, describe(a), alpha, beta)
            out.append(child)
            v = float(child["value"])  # type: ignore[arg-type]
            if maximising:
                best, alpha = max(best, v), max(alpha, max(best, v))
            else:
                best, beta = min(best, v), min(beta, min(best, v))
            if alpha >= beta and k < len(kids) - 1:
                cut = True
        return {
            "move": move,
            "kind": "max" if maximising else "min",
            "mover": side_name[who[0]],
            "window": who[1],
            "value": best,
            "alpha": None if alpha == float("-inf") else alpha,
            "beta": None if beta == float("inf") else beta,
            "children": out,
            "skipped": skipped,
        }

    return walk(Node(case), "the trial begins", float("-inf"), float("inf"))
