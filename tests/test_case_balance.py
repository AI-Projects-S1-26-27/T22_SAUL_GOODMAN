"""The rebalanced cases must stay contested (DEVIATIONS D14); the fixtures must stay fixtures."""

from __future__ import annotations

import itertools

from courtroom.cases import CASES
from courtroom.contracts import Side
from courtroom.engine import run_trial
from courtroom.judge.scoring import score_record

STRATEGIES = ("aggressive", "conservative", "adaptive")


def _win_rates(case_id: str, seeds: int = 12) -> list[float]:
    return [
        sum(run_trial(CASES[case_id], p, d, seed=s).verdict.outcome.favours is Side.PROSECUTION for s in range(seeds)) / seeds
        for p, d in itertools.product(STRATEGIES, STRATEGIES)
    ]


def test_aurora_is_winnable_but_not_easy() -> None:
    rates = _win_rates("aurora-defi")
    assert max(rates) > 0.0, "the prosecution can never win: the case is unwinnable again"
    assert max(rates) < 0.5, "the prosecution wins too easily: the case is no longer defense-favoured"


def test_kestrel_is_contested_and_not_a_single_fact_away_from_certain() -> None:
    rates = _win_rates("kestrel-av")
    assert max(rates) > 0.0 and min(rates) < max(rates)
    assert sum(rates) / len(rates) < 0.5


def test_every_element_is_provable_by_the_prosecution_alone() -> None:
    """The earlier aurora flaw: an element whose ceiling sat below the bar whatever anyone did."""
    for case_id in ("aurora-defi", "kestrel-av"):
        case = CASES[case_id]
        tau = {"criminal": 2.2, "civil": 0.0}[case.case_type.value]
        mine = [e.id for e in case.evidence if e.owner is Side.PROSECUTION]
        for element, value in score_record(case, mine).log_odds.items():
            assert float(value) > tau, (case_id, element, float(value))


def test_the_fixtures_are_still_fixtures() -> None:
    for case_id in ("edge-empty-docket", "edge-defense-only", "edge-mutual-exclusion"):
        assert max(_win_rates(case_id, 3)) == 0.0, f"{case_id} is meant to be unwinnable"


def test_the_duplicate_exhibit_still_adds_nothing() -> None:
    case = CASES["aurora-defi"]
    one = score_record(case, ["P-TXS"]).log_odds["execution"]
    assert score_record(case, ["P-TXS", "P-TXS-DUP"]).log_odds["execution"] == one
