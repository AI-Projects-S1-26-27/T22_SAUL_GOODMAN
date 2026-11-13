"""The lookahead lawyer: information limits, determinism, and that alpha-beta gives the same choices as plain minimax."""

from __future__ import annotations

import ast
import inspect

import pytest

from courtroom.agents import describe_strategies, lookahead, make_agent
from courtroom.agents.lookahead import LookaheadAgent
from courtroom.cases import CASES, generate_case
from courtroom.contracts import EventKind
from courtroom.engine import run_trial, run_with_agents


def test_it_reads_only_the_party_view_and_the_public_oracle() -> None:
    tree = ast.parse(inspect.getsource(lookahead))
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not {m for m in imported if m and (m.startswith(("courtroom.cases", "courtroom.engine", "courtroom.llm", "courtroom.gametheory")))}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not attrs & {"case", "_cache", "_admitted", "_impeachments", "evidence", "witnesses"}  # no peeking behind the view or the oracle
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not names & {"CaseFile", "get_case", "generate_case"}


def test_it_is_selectable_but_not_one_of_the_certified_styles() -> None:
    names = {d["name"] for d in describe_strategies()}
    assert "lookahead" in names
    from courtroom.agents import STRATEGY_NAMES

    assert "lookahead" not in STRATEGY_NAMES
    assert isinstance(make_agent("lookahead", __import__("random").Random(0)), LookaheadAgent)


@pytest.mark.parametrize("cid", ["cookie-jar", "broken-bike", "kestrel-av", "helix-espionage", "gen-3", "gen-20"])
def test_trials_with_it_are_legal_and_reproducible(cid: str) -> None:
    case = generate_case(int(cid[4:])) if cid.startswith("gen-") else CASES[cid]
    a = run_trial(case, "lookahead", "adaptive", seed=2)
    b = run_trial(case, "lookahead", "adaptive", seed=2)
    assert a.digest == b.digest
    assert not any(e.kind is EventKind.VIOLATION for e in a.events)
    c = run_trial(case, "conservative", "lookahead", seed=2)
    assert not any(e.kind is EventKind.VIOLATION for e in c.events)


@pytest.mark.parametrize("cid", ["cookie-jar", "kestrel-av", "gen-20", "gen-44"])
def test_alphabeta_makes_the_same_choices_as_plain_minimax_with_fewer_nodes(cid: str) -> None:
    case = generate_case(int(cid[4:])) if cid.startswith("gen-") else CASES[cid]
    pruned, plain = LookaheadAgent(prune=True), LookaheadAgent(prune=False)
    a = run_with_agents(case, pruned, make_agent("adaptive", __import__("random").Random(0)), seed=1)
    b = run_with_agents(case, plain, make_agent("adaptive", __import__("random").Random(0)), seed=1)
    assert a.digest == b.digest  # every move identical
    assert pruned.nodes <= plain.nodes


def test_alphabeta_prunes_somewhere() -> None:
    case = CASES["cookie-jar"]
    pruned, plain = LookaheadAgent(prune=True), LookaheadAgent(prune=False)
    for agent in (pruned, plain):
        run_with_agents(case, agent, make_agent("adaptive", __import__("random").Random(0)), seed=0)
    assert pruned.nodes < plain.nodes


def test_the_oracle_extension_does_not_change_old_calls() -> None:
    """Adding the multi-impeachment what-if must leave every recorded trial exactly as it was (the pinned digests also check this)."""
    from courtroom.agents import Oracle, ScoreCache

    case = CASES["helix-espionage"]
    o = Oracle(ScoreCache(case), [], {})
    w = next(w for i in case.evidence for w in i.impeaches)
    assert o.log_odds(impeach=w) == o.log_odds(also_impeach=[w])
