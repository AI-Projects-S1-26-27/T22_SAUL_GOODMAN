"""Review findings E2, E3, G4: shared cache copies, finite money fields, bootstrap guards."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from courtroom.agents.base import ScoreCache
from courtroom.cases import get_case
from courtroom.gametheory.bootstrap import bootstrap_case
from tests.conftest import item, make_case


def test_score_cache_hands_out_copies_so_an_agent_cannot_change_the_scores() -> None:  # E2
    cache = ScoreCache(make_case((item("P1"),)))
    first = cache.log_odds(["P1"], {})
    first["e1"] = 99.0
    assert cache.log_odds(["P1"], {})["e1"] != 99.0


@pytest.mark.parametrize("bad", [float("inf"), float("nan")])
def test_non_finite_budget_and_cost_are_rejected_at_the_door(bad: float) -> None:  # E3
    with pytest.raises(ValidationError):
        make_case((item("P1"),), budget=bad)
    with pytest.raises(ValidationError):
        item("P1", cost=bad)


def test_bootstrap_refuses_zero_resamples_and_no_seeds_with_a_clear_message() -> None:  # G4
    case = get_case("cookie-jar")
    with pytest.raises(ValueError, match="n_resamples"):
        bootstrap_case(case, seeds=(0, 1), n_resamples=0)
    with pytest.raises(ValueError, match="seeds"):
        bootstrap_case(case, seeds=(), n_resamples=5)
