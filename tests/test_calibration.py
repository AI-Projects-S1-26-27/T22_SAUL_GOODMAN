"""The calibration measurements and the rules that choose a setting from them (DEVIATIONS D19)."""

from __future__ import annotations

from courtroom.cases import PLAIN_CASES
from courtroom.engine import run_trial
from courtroom.gametheory.calibration import (
    STABILITY_FLOOR,
    choose,
    evaluate,
    exposed,
    measure_case,
    run_cells,
    support_key,
    with_events,
)

HELIX = PLAIN_CASES["helix-espionage"]


def _quick(case, seeds=6, resamples=10):
    cells = run_cells({"c": case}, range(seeds), workers=1)
    return measure_case(cells["c"], n_resamples=resamples)


def test_zero_rates_are_exactly_the_events_off_game() -> None:
    off = _quick(HELIX)
    zero = _quick(with_events(HELIX, 0.0, 0.0, 0.0))
    assert off == zero
    for p, d in (("aggressive", "conservative"), ("adaptive", "adaptive")):
        assert run_trial(with_events(HELIX, 0.0, 0.0, 0.0), p, d, seed=3).digest == run_trial(HELIX, p, d, seed=3).digest


def test_a_measurement_is_deterministic_and_has_every_field() -> None:
    a, b = _quick(HELIX), _quick(HELIX)
    assert a == b
    assert set(a) >= {"label", "support", "label_stability", "support_stability", "sd", "win_mean", "win_min", "win_max"}
    assert 0.0 <= a["support_stability"] <= 1.0 and set(a["sd"]) == {"prosecution", "defense"}


def test_events_raise_the_payoff_spread_of_a_strategy_that_was_flat() -> None:
    off = _quick(PLAIN_CASES["kestrel-av"], seeds=30)
    on = _quick(with_events(PLAIN_CASES["kestrel-av"], 0.1, 0.15, 0.1), seeds=30)
    assert off["sd"]["prosecution"]["conservative"] < 0.5 <= on["sd"]["prosecution"]["conservative"]


def test_only_cases_events_can_reach_count_as_exposed() -> None:
    assert exposed(HELIX) and exposed(PLAIN_CASES["kestrel-av"])
    assert not exposed(PLAIN_CASES["edge-empty-docket"]) and not exposed(PLAIN_CASES["edge-defense-only"])


def _rec(name, labels, stab, sd_rise, on=True):
    return {
        "name": name,
        "events_on": on,
        "cases": {
            cid: {
                "label": lab,
                "label_stability": s,
                "support_stability": s,
                "sd": {"prosecution": {"conservative": 0.0 + sd_rise}, "defense": {"conservative": 0.0 + sd_rise}},
            }
            for cid, lab, s in zip("xyzw", labels, stab, strict=True)
        },
    }


def test_the_rules_pick_by_stability_among_qualifying_settings_and_record_the_band() -> None:
    base = _rec("off", ["pure"] * 4, [1.0] * 4, 0.0, on=False)
    good = _rec("good", ["mixed", "pure", "pure", "dominance-solvable"], [0.97, 1, 1, 1], 1.0)
    better = _rec("better", ["mixed", "pure", "pure", "dominance-solvable"], [0.99, 1, 1, 1], 1.0)
    flat = _rec("flat", ["mixed", "pure", "pure", "pure"], [1, 1, 1, 1], 0.0)
    out = choose([base, good, better, flat], base, list("xyzw"))
    assert out["band_exists"] and out["setting"] == "better" and set(out["qualifying"]) == {"good", "better"}


def test_when_no_setting_qualifies_it_says_so_and_still_picks_the_most_stable_that_improves_variance() -> None:
    base = _rec("off", ["pure"] * 4, [1.0] * 4, 0.0, on=False)
    a = _rec("a", ["dominance-solvable"] * 4, [1, 1, 1, 1], 1.0)  # stable, risen, but nothing contested (fails b)
    b = _rec("b", ["mixed", "pure", "pure", "pure"], [0.6, 1, 1, 1], 1.0)  # contested, but unstable (fails c)
    out = choose([base, a, b], base, list("xyzw"))
    assert out["band_exists"] is False and out["setting"] == "a" and "rule (e)" in out["fallback"]
    assert evaluate(b, base, list("xyzw"))["unstable"] == ["x"] and STABILITY_FLOOR == 0.95


def test_support_key_is_order_free() -> None:
    cells = run_cells({"c": HELIX}, range(4), workers=1)["c"]
    from courtroom.gametheory.calibration import STRATEGIES, _matrices
    from courtroom.gametheory.nash import analyze

    A, B = _matrices(cells, STRATEGIES)
    assert support_key(analyze(list(STRATEGIES), list(STRATEGIES), A, B)) == support_key(analyze(list(STRATEGIES), list(STRATEGIES), A, B))
