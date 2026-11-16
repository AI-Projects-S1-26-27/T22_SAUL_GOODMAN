"""Review findings T1 to T4: the judge's edges. Each of these was a mutation (a changed constant, comparison or tie-break) that no test caught."""

from __future__ import annotations

from courtroom.contracts import CaseType, ObjectionGround, Side, StandardOfProof, VerdictOutcome
from courtroom.judge import Judge, valid_grounds
from tests.conftest import item, make_case


def test_relevance_floor_is_exactly_one_twentieth() -> None:  # T1
    ground = lambda s: ObjectionGround.RELEVANCE in valid_grounds(item("P1", support={"e1": s}), CaseType.CRIMINAL)  # noqa: E731
    assert ground(0.049) is True
    assert ground(0.05) is False  # at the floor it is still relevant
    assert ground(0.07) is False
    assert ground(-0.049) is True  # the sign does not matter, only the size


def _tied_case(delta: float):
    """Civil case, prior 0: +0.4 and -(0.4 + delta) of equal strength, so the element's log-odds are -3*delta exactly."""
    return make_case(
        (item("P1", support={"e1": 0.4}), item("D1", Side.DEFENSE, support={"e1": -(0.4 + delta)}, fact_id="other")),
        case_type=CaseType.CIVIL,
        standard=StandardOfProof.PREPONDERANCE,
    )


def test_directed_verdict_needs_log_odds_strictly_below_zero() -> None:  # T2
    exact_zero = Judge(_tied_case(0.0))
    granted, _, rules = exact_zero.directed_verdict_review(["P1", "D1"], {}, moved=True)
    assert granted is False and any(r.rule_id == "DV-1" and "DENIED" in r.detail for r in rules)
    just_below = Judge(_tied_case(0.0001))
    assert just_below.directed_verdict_review(["P1", "D1"], {}, moved=True)[0] is True


def test_civil_cases_end_liable_or_not_liable_never_guilty() -> None:  # T3
    win = make_case((item("P1", support={"e1": 0.5}),), case_type=CaseType.CIVIL, standard=StandardOfProof.PREPONDERANCE)
    assert Judge(win).deliberate(["P1"], {}).outcome is VerdictOutcome.LIABLE
    nothing = make_case((item("P1", support={"e1": -0.5}, owner=Side.DEFENSE),), case_type=CaseType.CIVIL, standard=StandardOfProof.PREPONDERANCE)
    assert Judge(nothing).deliberate(["P1"], {}).outcome is VerdictOutcome.NOT_LIABLE
    crim = make_case((item("P1", support={"e1": 1.0}), item("P2", support={"e1": 1.0})))
    assert Judge(crim).deliberate(["P1", "P2"], {}).outcome is VerdictOutcome.GUILTY


def test_two_items_on_one_fact_count_once_and_the_lower_id_wins_a_tie() -> None:  # T4
    case = make_case((item("P2", support={"e1": 0.5}, fact_id="same"), item("P1", support={"e1": 0.5}, fact_id="same")))
    contribs = Judge(case).score(["P1", "P2"], {}).snapshot.elements[0].contributions
    counted = {c.evidence_id: c.counted for c in contribs}
    assert counted == {"P1": True, "P2": False}


def test_the_weakest_element_is_the_first_declared_when_two_tie() -> None:  # T4
    case = make_case((item("P1", support={"e1": 0.5, "e2": 0.5}),), elements=("e1", "e2"))
    assert Judge(case).score(["P1"], {}).snapshot.weakest_element == "e1"
    flipped = make_case((item("P1", support={"e1": 0.5, "e2": 0.5}),), elements=("e2", "e1"))
    assert Judge(flipped).score(["P1"], {}).snapshot.weakest_element == "e2"
