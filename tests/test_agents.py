"""Engineer 4: agents, perception channel, policies."""

from __future__ import annotations

import random

import pytest

from courtroom.agents import ADAPTIVE, AGGRESSIVE, CONSERVATIVE, CounselAgent, MixedAgent, make_agent, perceive
from courtroom.agents.base import defect_posteriors
from courtroom.cases import CASES
from courtroom.contracts import ActionType, ObjectionGround, Side
from courtroom.engine import run_trial
from courtroom.judge import valid_grounds
from tests.conftest import item, make_case


def test_posteriors_are_calibrated() -> None:
    pos, neg = defect_posteriors(0.8)
    assert pos == pytest.approx(0.8 * 0.15 / (0.8 * 0.15 + 0.05 * 0.85))
    assert 0 < neg < 0.15 < pos < 1
    assert defect_posteriors(1.0) == (1.0, 0.0)


def test_perfect_perception_reveals_truth() -> None:
    case = make_case((item("P1", hearsay=True),), perception_accuracy=1.0)
    seen = perceive(case.evidence[0], case, random.Random(0))
    assert seen.defect_belief[ObjectionGround.HEARSAY] == 1.0
    assert seen.defect_belief[ObjectionGround.AUTHENTICATION] == 0.0


def test_perception_hit_rate_matches_accuracy() -> None:
    case = make_case((item("P1", hearsay=True),), perception_accuracy=0.8)
    rng = random.Random(1)
    pos, _ = defect_posteriors(0.8)
    hits = sum(perceive(case.evidence[0], case, rng).defect_belief[ObjectionGround.HEARSAY] == round(pos, 6) for _ in range(4000))
    assert 0.77 < hits / 4000 < 0.83


def _offered(result, side: Side) -> list[str]:
    return [e.action.evidence_id for e in result.events if e.status == "offered" and e.actor is side]  # type: ignore[union-attr]


@pytest.mark.parametrize("case_id", ["helix-espionage", "aurora-defi", "kestrel-av", "edge-poisoned-tree"])
def test_conservative_never_offers_known_defective_evidence(case_id: str) -> None:
    case = CASES[case_id]
    for seed in range(5):
        r = run_trial(case, "conservative", "conservative", seed)
        for eid in _offered(r, Side.PROSECUTION) + _offered(r, Side.DEFENSE):
            assert valid_grounds(case.item(eid), case.case_type) == ()  # type: ignore[arg-type]


def test_aggressive_offers_defective_evidence_on_poisoned_tree() -> None:
    r = run_trial(CASES["edge-poisoned-tree"], "aggressive", "conservative", 0)
    assert _offered(r, Side.PROSECUTION)


def test_aggressive_objects_more_than_conservative() -> None:
    case = CASES["helix-espionage"]
    agg = sum(run_trial(case, "aggressive", "aggressive", s).ledgers[Side.DEFENSE].objections for s in range(10))
    con = sum(run_trial(case, "aggressive", "conservative", s).ledgers[Side.DEFENSE].objections for s in range(10))
    assert agg > con


def test_profiles_differ_only_in_parameters() -> None:
    assert type(CounselAgent(AGGRESSIVE)) is type(CounselAgent(CONSERVATIVE)) is type(CounselAgent(ADAPTIVE))


def test_mixed_agent_realisation_is_seeded() -> None:
    real = [MixedAgent(0.5, random.Random(f"{s}:agent:prosecution")).realised for s in range(200)]
    again = [MixedAgent(0.5, random.Random(f"{s}:agent:prosecution")).realised for s in range(200)]
    assert real == again
    assert 70 < real.count("aggressive") < 130
    assert all(MixedAgent(1.0, random.Random(s)).realised == "aggressive" for s in range(20))


def test_registry_rejects_unknown_strategy() -> None:
    with pytest.raises(ValueError):
        make_agent("bribe-the-judge", random.Random(0))
    with pytest.raises(ValueError):
        make_agent("mixed:1.5", random.Random(0))


def test_agents_emit_rationales() -> None:
    r = run_trial(CASES["helix-espionage"], "adaptive", "aggressive", 0)
    acts = [e.action for e in r.events if e.action is not None and e.action.type is not ActionType.REST]
    assert acts and all(a.rationale for a in acts)


@pytest.mark.parametrize("case_id", [c for c in CASES if CASES[c].evidence])
def test_reckless_agent_plays_the_game(case_id: str) -> None:
    """Unlike chaos, the reckless agent mostly makes legal moves, so its evidence reaches the court."""
    for side in ("prosecution", "defense"):
        p, d = ("reckless", "aggressive") if side == "prosecution" else ("aggressive", "reckless")
        r = run_trial(CASES[case_id], p, d, seed=0)
        own = [e for e in CASES[case_id].evidence if e.owner.value == side]
        shown = [e for e in r.events if e.action and e.action.actor.value == side and e.action.type is ActionType.PRESENT_EVIDENCE]
        violations = [e for e in r.events if e.kind.value == "violation" and e.actor and e.actor.value == side]
        had_turn = side == "prosecution" or any(e.phase.value == "defense_case" for e in r.events)
        if own and had_turn:  # a directed acquittal can end the trial before the defense ever plays
            assert shown, f"reckless {side} never showed evidence in {case_id}"
        assert len(violations) <= max(3, len(shown))
