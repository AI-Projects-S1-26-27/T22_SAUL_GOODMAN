"""The trial as a game tree: the real engine's rules, exact minimax, alpha-beta and move ordering."""

from __future__ import annotations

import pytest

from courtroom.cases import CASES, generate_case
from courtroom.contracts import ActionType, EventKind, Side
from courtroom.engine import run_trial
from courtroom.gametheory.search import (
    Node,
    Stats,
    TooBig,
    alphabeta,
    minimax,
    order_best_first,
    solve_case,
)

SMALL = ["edge-mutual-exclusion", "edge-defense-only", "gen-20", "gen-44", "gen-51", "gen-62", "gen-6"]


def _case(cid: str):
    return generate_case(int(cid[4:])) if cid.startswith("gen-") else CASES[cid]


@pytest.mark.parametrize("cid", SMALL)
def test_minimax_alphabeta_and_ordered_alphabeta_agree_exactly(cid: str) -> None:
    root = Node(_case(cid))
    s1, s2, s3 = Stats(10**7), Stats(10**7), Stats(10**7)
    v1 = minimax(root.clone(), s1)
    v2 = alphabeta(root.clone(), s2)
    v3 = alphabeta(root.clone(), s3, ordering=order_best_first)
    assert v1 == v2 == v3
    assert s2.nodes <= s1.nodes and s3.nodes <= s1.nodes


def test_alphabeta_prunes_on_a_case_with_choices() -> None:
    root = Node(CASES["cookie-jar"])
    a, b = Stats(10**7), Stats(10**7)
    assert minimax(root.clone(), a) == alphabeta(root.clone(), b, ordering=order_best_first)
    assert b.nodes < a.nodes / 10  # ordered alpha-beta needs a small fraction of the nodes


@pytest.mark.parametrize("cid", ["edge-mutual-exclusion", "gen-20", "gen-51"])
def test_dropping_dominated_moves_does_not_change_the_value(cid: str) -> None:
    """Passing a turn, and objections or impeachments the judge would reject, are never better than the alternatives."""
    root = Node(_case(cid))
    pruned = minimax(root.clone(), Stats(10**7), prune=True)
    full = minimax(root.clone(), Stats(10**7), prune=False)
    assert pruned == full


def test_the_node_cap_stops_a_search_that_is_too_big() -> None:
    with pytest.raises(TooBig):
        minimax(Node(CASES["cookie-jar"]).clone(), Stats(100))


@pytest.mark.parametrize(("cid", "p", "d", "seed"), [("cookie-jar", "aggressive", "conservative", 0), ("broken-bike", "conservative", "adaptive", 1), ("kestrel-av", "adaptive", "aggressive", 2)])
def test_the_tree_applies_the_engines_own_rules(cid: str, p: str, d: str, seed: int) -> None:
    """Replay a real trial's moves through the tree: same verdict and same utilities as the engine."""
    r = run_trial(CASES[cid], p, d, seed=seed)
    assert not any(e.kind is EventKind.VIOLATION for e in r.events)
    node = Node(CASES[cid])
    for e in r.events:
        if e.action is None or e.kind is EventKind.VIOLATION:
            continue
        who = node.settle()
        assert who is not None and who[0] is e.action.actor
        node.apply(e.action)
    assert node.settle() is None
    assert node.verdict_now().outcome == r.verdict.outcome
    assert node.utilities_now() == r.utilities


def test_every_legal_move_the_tree_offers_is_accepted_by_the_procedure() -> None:
    node = Node(CASES["cookie-jar"])
    acts = node.legal_actions()
    assert acts and all(a.actor is Side.PROSECUTION for a in acts)
    assert any(a.type is ActionType.REST for a in acts)


def test_a_clone_is_independent() -> None:
    root = Node(CASES["cookie-jar"])
    kid = root.clone()
    kid.apply(next(a for a in kid.legal_actions() if a.type is ActionType.PRESENT_EVIDENCE))
    assert root.state.presented == [] and kid.state.presented


def test_solve_case_reports_equal_values_and_savings() -> None:
    rep = solve_case(CASES["cookie-jar"])
    assert rep.values_agree and rep.minimax_nodes and rep.alphabeta_ordered_nodes
    assert rep.alphabeta_ordered_nodes < rep.alphabeta_nodes < rep.minimax_nodes
    assert rep.best_play  # a line of best play is reported
