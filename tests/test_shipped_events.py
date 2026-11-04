"""The shipped adverse-event configuration is the one the committed sweep selects (DEVIATIONS D19)."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

from courtroom.cases import CASES, PLAIN_CASES, get_plain_case
from courtroom.cases.events import EVENT_CASES, SHIPPED_RULES
from courtroom.gametheory.calibration import choose, exposed

ROOT = Path(__file__).resolve().parent.parent


def _lines(name: str) -> list[dict]:
    return [json.loads(x) for x in (ROOT / "results" / "calibration" / name).read_text(encoding="utf-8").splitlines()]


EVENTS = _lines("events.jsonl")
CASES_SWEEP = _lines("cases.jsonl")
BASELINE = next(r for r in EVENTS if r["name"] == "events-off")


def test_the_sweep_is_complete_and_run_at_the_certified_sample_sizes() -> None:
    names = {r["name"] for r in EVENTS}
    assert {"events-off", "default"} <= names and len(names) == len(EVENTS) == 21
    for r in EVENTS:
        assert set(r["cases"]) == set(PLAIN_CASES) and r["seeds"] == 200 and r["resamples"] == 200


def test_the_shipped_rates_are_exactly_the_setting_the_selection_rules_pick() -> None:
    chosen = choose(EVENTS, BASELINE, [c for c, k in PLAIN_CASES.items() if exposed(k)])
    record = next(r for r in EVENTS if r["name"] == chosen["setting"])
    assert (record["no_show"], record["missing_certificate"], record["hostile"], record["hostile_credibility"]) == (
        SHIPPED_RULES.no_show,
        SHIPPED_RULES.missing_certificate,
        SHIPPED_RULES.hostile,
        SHIPPED_RULES.hostile_credibility,
    )
    assert Fraction(SHIPPED_RULES.hostile_credibility) == Fraction(1, 4)


def test_the_documented_thin_spot_in_the_selection_is_real() -> None:
    """By the letter of the rules a band qualifies, but only helix of the three contested cases keeps a mixed equilibrium."""
    default = next(r for r in EVENTS if r["name"] == "default")["cases"]
    assert default["helix-espionage"]["label"] == "mixed"
    assert default["aurora-defi"]["label"] == "dominance-solvable" and default["kestrel-av"]["label"] == "dominance-solvable"
    assert BASELINE["cases"]["aurora-defi"]["label"] == "pure" and BASELINE["cases"]["kestrel-av"]["label"] == "mixed"


def test_no_value_of_either_calibrated_parameter_contests_its_case_with_events_on() -> None:
    """Why the case values were left as they were: the sweep found nothing better to move to."""
    for record in CASES_SWEEP:
        assert record["label"] == "dominance-solvable", (record["case"], record["value"])
        assert record["rates"] == [SHIPPED_RULES.no_show, SHIPPED_RULES.missing_certificate, SHIPPED_RULES.hostile, SHIPPED_RULES.hostile_credibility]
    kestrel = {r["value"] for r in CASES_SWEEP if r["case"] == "kestrel-av"}
    aurora = {r["value"] for r in CASES_SWEEP if r["case"] == "aurora-defi"}
    recall = next(i for i in PLAIN_CASES["kestrel-av"].evidence if i.id == "P-RECALL").support["defect"]
    assert recall in kestrel and 1.0 in aurora


def test_exactly_the_calibrated_cases_ship_with_events_and_the_fixtures_stay_plain() -> None:
    assert {cid for cid, c in CASES.items() if c.adverse_events} == set(EVENT_CASES) == {"helix-espionage", "aurora-defi", "kestrel-av", "edge-poisoned-tree"}
    for cid in ("edge-empty-docket", "edge-mutual-exclusion", "edge-defense-only"):
        assert CASES[cid] is PLAIN_CASES[cid] and CASES[cid].rules is None


def test_the_recorded_exhibition_is_replayed_on_the_plain_rulebook() -> None:
    assert get_plain_case("helix-espionage").rules is None and CASES["helix-espionage"].rules is not None


def test_no_setting_qualifies_when_only_the_cases_that_are_real_contests_are_counted() -> None:
    """The finding behind the thin spot: count the four cases with real play, not the three fixtures, and (b) and (c) never hold together."""
    from courtroom.gametheory.calibration import evaluate, real_play_cases

    real = real_play_cases(BASELINE)
    assert set(real) == {"helix-espionage", "aurora-defi", "kestrel-av", "edge-poisoned-tree"}
    exp = [c for c, k in PLAIN_CASES.items() if exposed(k)]
    for r in EVENTS:
        if r["events_on"]:
            e = evaluate(r, BASELINE, exp, scope=real)
            assert not (e["a"] and e["b"] and e["c"]), r["name"]


def test_shipped_stability_figures_agree_with_the_certified_bootstrap() -> None:
    """RESULTS.md quotes label stability from results/bootstrap.json and support stability from the sweep: they must be one measurement."""
    certified = {r["case_id"]: r for r in json.loads((ROOT / "results" / "bootstrap.json").read_text(encoding="utf-8"))}
    default = next(r for r in EVENTS if r["name"] == "default")["cases"]
    for cid in PLAIN_CASES:
        measured = default[cid] if cid in EVENT_CASES else BASELINE["cases"][cid]
        assert measured["label_stability"] == certified[cid]["stability"], cid
        assert measured["label"] == certified[cid]["baseline_label"], cid
