"""The proof standard's bar is a game parameter: overridable per case, unchanged by default."""

from __future__ import annotations

import math
from fractions import Fraction

import pytest
from pydantic import ValidationError

from courtroom.agents import Oracle, ScoreCache
from courtroom.cases import CASES
from courtroom.contracts import CaseFile, StandardOfProof
from courtroom.engine import run_trial
from courtroom.judge.rules import (
    THRESHOLD_LOG_ODDS,
    bar_log_odds_for,
    override_for_bar,
    sigmoid,
    threshold_for,
    threshold_met,
)

HELIX = CASES["helix-espionage"]


def _with_bar(case: CaseFile, probability: float) -> CaseFile:
    return case.model_copy(update={"bar_log_odds": bar_log_odds_for(probability)})


# ----------------------------------------------------------------- default path


@pytest.mark.parametrize("case", list(CASES.values()), ids=list(CASES))
def test_with_no_override_the_bar_is_exactly_the_standards_own(case: CaseFile) -> None:
    assert case.bar_log_odds is None
    assert threshold_for(case) == THRESHOLD_LOG_ODDS[case.standard]


def test_the_three_standards_are_still_the_proposals_constants() -> None:
    assert THRESHOLD_LOG_ODDS[StandardOfProof.BEYOND_REASONABLE_DOUBT] == Fraction(11, 5)
    assert THRESHOLD_LOG_ODDS[StandardOfProof.CLEAR_AND_CONVINCING] == Fraction(11, 10)
    assert THRESHOLD_LOG_ODDS[StandardOfProof.PREPONDERANCE] == 0


# ----------------------------------------------------------------- validation


@pytest.mark.parametrize("bad", ["abc", "-1", "8", "99", "1/0", "1e9", "2.12345678", "11/5/2", "", " 2"])
def test_a_nonsensical_bar_is_rejected_by_the_case_validator(bad: str) -> None:
    with pytest.raises(ValidationError):
        CaseFile.model_validate({**HELIX.model_dump(mode="json"), "bar_log_odds": bad})


@pytest.mark.parametrize("good", ["0", "11/5", "2.1972", "2.2", "6.9068", "7"])
def test_a_sane_bar_is_accepted(good: str) -> None:
    case = CaseFile.model_validate({**HELIX.model_dump(mode="json"), "bar_log_odds": good})
    assert threshold_for(case) == Fraction(good)


# ----------------------------------------------------------------- the bar bites


def test_threshold_met_keeps_the_standards_tie_rule() -> None:
    tau = Fraction(3, 2)
    assert threshold_met(tau, StandardOfProof.BEYOND_REASONABLE_DOUBT, tau)  # inclusive
    assert not threshold_met(tau, StandardOfProof.PREPONDERANCE, tau)  # strict
    assert threshold_met(tau + Fraction(1, 10**9), StandardOfProof.PREPONDERANCE, tau)


def test_the_judge_reports_the_overridden_bar() -> None:
    result = run_trial(_with_bar(HELIX, 0.95), "aggressive", "conservative", seed=0)
    shown = result.verdict.snapshot.elements[0].threshold_probability
    assert shown == pytest.approx(0.95, abs=1e-4)


def test_an_unreachable_bar_acquits_a_case_the_default_bar_convicts() -> None:
    default = run_trial(HELIX, "aggressive", "conservative", seed=0)
    assert default.verdict.outcome.value == "guilty"
    strict = run_trial(_with_bar(HELIX, 0.999), "aggressive", "conservative", seed=0)
    assert strict.verdict.outcome.value != "guilty"


def test_the_oracle_reasons_about_the_overridden_bar() -> None:
    """Agents must see the same bar the judge applies, or they would play the wrong game."""
    case = _with_bar(HELIX, 0.95)
    assert Oracle(ScoreCache(case), [], {})._tau == pytest.approx(float(Fraction(case.bar_log_odds)))
    assert Oracle(ScoreCache(HELIX), [], {})._tau == pytest.approx(2.2)


def test_the_same_bar_replays_to_the_same_digest() -> None:
    case = _with_bar(HELIX, 0.8)
    assert run_trial(case, "aggressive", "conservative", seed=3).digest == run_trial(case, "aggressive", "conservative", seed=3).digest


def test_a_different_bar_is_a_different_game() -> None:
    a = run_trial(HELIX, "adaptive", "adaptive", seed=2)
    b = run_trial(_with_bar(HELIX, 0.99), "adaptive", "adaptive", seed=2)
    assert a.digest != b.digest


# ----------------------------------------------------------------- slider helpers


def test_bar_to_log_odds_is_short_exact_and_monotone() -> None:
    assert bar_log_odds_for(0.5) == "0"
    assert bar_log_odds_for(0.95) == "2.9444"
    values = [Fraction(bar_log_odds_for(p)) for p in (0.5, 0.6, 0.75, 0.9, 0.99)]
    assert values == sorted(values)
    assert float(Fraction(bar_log_odds_for(0.9))) == pytest.approx(math.log(0.9 / 0.1), abs=1e-4)


def test_picking_the_standards_own_percent_means_no_override() -> None:
    """90% on a beyond-reasonable-doubt case must keep the exact 11/5, not a rounded 2.1972."""
    criminal = HELIX
    assert criminal.standard is StandardOfProof.BEYOND_REASONABLE_DOUBT
    assert override_for_bar(criminal, 0.90) is None
    assert override_for_bar(criminal, 0.95) == "2.9444"
    civil = CASES["edge-mutual-exclusion"]
    assert civil.standard is StandardOfProof.PREPONDERANCE
    assert override_for_bar(civil, 0.5) is None
    assert round(100 * sigmoid(float(Fraction(override_for_bar(civil, 0.8) or "0")))) == 80
