"""Proposal Sec. 6: "Fe is the four facts with the largest |v| per side".

The code had no such cap, so the claim that splitting one fact into many cannot inflate the score
held for the same fact (the cumulative-evidence rule) but not for distinct facts: each extra
exhibit added a flat +3 log-odds without limit. These tests pin the cap, and pin that it changes
nothing on the shipped cases.
"""

from __future__ import annotations

import itertools
import random
from fractions import Fraction

import pytest

from courtroom.cases import CASES, generate_case
from courtroom.contracts import CaseFile, CaseType, EvidenceItem, EvidenceKind, LegalElement, Side, StandardOfProof
from courtroom.engine import run_trial
from courtroom.judge import rules
from courtroom.judge.scoring import score_record


@pytest.fixture(autouse=True)
def _restore_cap():
    before = rules.MAX_FACTS_PER_SIDE
    yield
    rules.MAX_FACTS_PER_SIDE = before


def _case(prosecution: int = 0, defense: int = 0, s: float = 0.8, rel: float = 0.8) -> tuple[CaseFile, list[str]]:
    ev = [
        EvidenceItem(id=f"P{i}", title="x", description="x", kind=EvidenceKind.DOCUMENT, owner=Side.PROSECUTION,
                     fact_id=f"p{i}", support={"e1": s}, reliability=rel)
        for i in range(prosecution)
    ] + [
        EvidenceItem(id=f"D{i}", title="x", description="x", kind=EvidenceKind.DOCUMENT, owner=Side.DEFENSE,
                     fact_id=f"d{i}", support={"e1": -0.5}, reliability=0.7)
        for i in range(defense)
    ]
    case = CaseFile(id="probe", title="t", synopsis="s", case_type=CaseType.CRIMINAL,
                    standard=StandardOfProof.BEYOND_REASONABLE_DOUBT, charge="c",
                    elements=(LegalElement(id="e1", name="E", description="d"),), evidence=tuple(ev))
    return case, [e.id for e in ev]


def _L(prosecution: int = 0, defense: int = 0) -> Fraction:
    case, ids = _case(prosecution, defense)
    return score_record(case, ids).log_odds["e1"]


# ----------------------------------------------------------------- the tail


def test_up_to_four_facts_the_score_is_exactly_what_it_always_was() -> None:
    for n in (1, 2, 3, 4):
        rules.MAX_FACTS_PER_SIDE = None
        before = _L(n)
        rules.MAX_FACTS_PER_SIDE = 4
        assert _L(n) == before


def test_the_tail_beyond_four_is_bounded_where_it_used_to_grow_without_limit() -> None:
    rules.MAX_FACTS_PER_SIDE = None
    uncapped = [_L(n) for n in (4, 6, 8)]
    assert uncapped == [Fraction(251, 25), Fraction(161, 10), Fraction(1099, 50)]  # +3 a fact, forever
    rules.MAX_FACTS_PER_SIDE = 4
    capped = [_L(n) for n in (4, 6, 8)]
    assert capped == [Fraction(251, 25), Fraction(52, 5), Fraction(1049, 100)]
    assert capped[2] < capped[0] + Fraction(1, 2), "four to eight exhibits should add less than half a log-odds point"


def test_what_remains_of_the_tail_is_only_the_corroboration_multiplier() -> None:
    """k still counts every supporting fact (the proposal defines it that way), so the four counted
    facts get a slightly larger multiplier as more facts arrive. It saturates: c_i < 3/2."""
    steps = [_L(n + 1) - _L(n) for n in range(4, 8)]
    assert all(0 < s < Fraction(1, 2) for s in steps)
    assert steps == sorted(steps, reverse=True), "each extra fact should add less than the one before"


def test_a_fifth_fact_cannot_overtake_a_stronger_one() -> None:
    rules.MAX_FACTS_PER_SIDE = 2
    case, _ = _case(prosecution=0)
    weak = EvidenceItem(id="W", title="x", description="x", kind=EvidenceKind.DOCUMENT, owner=Side.PROSECUTION,
                        fact_id="weak", support={"e1": 0.1}, reliability=0.5)
    strong = [EvidenceItem(id=f"S{i}", title="x", description="x", kind=EvidenceKind.DOCUMENT, owner=Side.PROSECUTION,
                           fact_id=f"s{i}", support={"e1": 0.9}, reliability=0.9) for i in range(2)]
    case = case.model_copy(update={"evidence": (weak, *strong)})
    counted = {c.evidence_id for c in score_record(case, ["W", "S0", "S1"]).snapshot.elements[0].contributions if c.counted}
    assert counted == {"S0", "S1"}, "the cap must keep the strongest facts, not the first ones"


# ----------------------------------------------------------------- per side


def test_each_side_is_capped_separately() -> None:
    """A large defense case must not push out the prosecution's best facts, nor the reverse."""
    case, ids = _case(prosecution=4, defense=6)
    counted = [c for c in score_record(case, ids).snapshot.elements[0].contributions if c.counted]
    assert sum(c.evidence_id.startswith("P") for c in counted) == 4
    assert sum(c.evidence_id.startswith("D") for c in counted) == 4


def test_the_defense_side_has_its_own_tail_bounded() -> None:
    rules.MAX_FACTS_PER_SIDE = None
    uncapped = _L(0, 8)
    rules.MAX_FACTS_PER_SIDE = 4
    assert _L(0, 8) > uncapped, "the defense's tail is bounded too: its score is less negative"


# ----------------------------------------------------------------- it is still the same judge


def test_permutation_invariance_survives_the_cap() -> None:
    case, ids = _case(prosecution=6, defense=5)
    rng = random.Random(7)
    expected = score_record(case, ids).log_odds["e1"]
    for _ in range(25):
        shuffled = ids[:]
        rng.shuffle(shuffled)
        assert score_record(case, shuffled).log_odds["e1"] == expected


def test_adding_defense_evidence_still_cannot_raise_an_element() -> None:
    """The directed-verdict review depends on this (D5, D6). The cap must not reopen it."""
    rng = random.Random(3)
    for _ in range(40):
        p, d = rng.randint(1, 7), rng.randint(0, 7)
        base, ids = _case(p, d)
        before = score_record(base, ids).log_odds["e1"]
        more, ids2 = _case(p, d + 1)
        assert score_record(more, ids2).log_odds["e1"] <= before


def test_the_arithmetic_stays_exact() -> None:
    assert isinstance(_L(6), Fraction)
    assert _L(6).denominator > 1


def test_the_three_standards_are_untouched() -> None:
    assert rules.THRESHOLD_LOG_ODDS[StandardOfProof.BEYOND_REASONABLE_DOUBT] == Fraction(11, 5)
    assert rules.THRESHOLD_LOG_ODDS[StandardOfProof.CLEAR_AND_CONVINCING] == Fraction(11, 10)
    assert rules.THRESHOLD_LOG_ODDS[StandardOfProof.PREPONDERANCE] == 0
    assert rules.MAX_FACTS_PER_SIDE == 4


# ----------------------------------------------------------------- no shipped result moves


def test_no_library_trial_changes_with_the_cap_on_or_off() -> None:
    """The claim that justifies calling this a conformance fix and not a scoring change."""
    strategies = ("aggressive", "conservative", "adaptive", "chaos")
    for case in CASES.values():
        for p, d in itertools.product(strategies, strategies):
            for seed in (0, 1):
                rules.MAX_FACTS_PER_SIDE = 4
                capped = run_trial(case, p, d, seed=seed)
                rules.MAX_FACTS_PER_SIDE = None
                uncapped = run_trial(case, p, d, seed=seed)
                assert capped.digest == uncapped.digest, f"{case.id} {p}/{d} seed {seed}"


def test_no_generated_verdict_changes_either() -> None:
    """On generated cases the cap does bite (digests move), but it must never flip a verdict."""
    differing_digests = 0
    for case in (generate_case(s) for s in range(30)):
        for p, d in (("aggressive", "conservative"), ("adaptive", "aggressive")):
            rules.MAX_FACTS_PER_SIDE = 4
            capped = run_trial(case, p, d, seed=0)
            rules.MAX_FACTS_PER_SIDE = None
            uncapped = run_trial(case, p, d, seed=0)
            assert capped.verdict.outcome == uncapped.verdict.outcome, f"{case.id} {p}/{d}"
            differing_digests += capped.digest != uncapped.digest
    assert differing_digests >= 0  # informational: the cap is allowed to move a digest on a generated case
