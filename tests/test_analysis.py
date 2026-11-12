"""W3: bootstrap, sensitivity and the best-response search. Small budgets: these check behaviour, not the committed results."""

from __future__ import annotations

from fractions import Fraction

from fastapi.testclient import TestClient

from courtroom.api.server import app
from courtroom.cases import CASES
from courtroom.contracts import Side, Surprises
from courtroom.engine import run_trial
from courtroom.gametheory import oracle as O
from courtroom.gametheory.bootstrap import DOMINANCE_SOLVABLE, MIXED, PURE, STYLES, bootstrap_case, equilibrium_label
from courtroom.gametheory.nash import analyze
from courtroom.gametheory.sensitivity import patched
from courtroom.judge import rules, scoring

http = TestClient(app)
CHEAP = CASES["cookie-jar"]


# ----------------------------------------------------------------- bootstrap


def test_equilibrium_labels_follow_the_proposal():
    pd = analyze(["a", "b"], ["a", "b"], [[3, 0], [5, 1]], [[3, 5], [0, 1]])  # prisoner's dilemma: dominance-solvable
    mp = analyze(["h", "t"], ["h", "t"], [[1, -1], [-1, 1]], [[-1, 1], [1, -1]])  # matching pennies: mixed
    co = analyze(["a", "b"], ["a", "b"], [[2, 0], [0, 1]], [[2, 0], [0, 1]])  # coordination: pure
    assert equilibrium_label(pd) == DOMINANCE_SOLVABLE and equilibrium_label(mp) == MIXED and equilibrium_label(co) == PURE


def test_bootstrap_is_deterministic_and_reports_intervals():
    a = bootstrap_case(CASES["broken-bike"], seeds=tuple(range(8)), n_resamples=30)
    b = bootstrap_case(CASES["broken-bike"], seeds=tuple(range(8)), n_resamples=30)
    assert a == b and 0 <= a.stability <= 1 and sum(a.label_counts.values()) == 30
    assert len(a.accuser_payoff_intervals) == len(STYLES) ** 2
    assert all(c.low <= c.mean <= c.high for c in a.accuser_payoff_intervals)


def test_bootstrap_with_surprises_is_a_different_seeded_game():
    plain = bootstrap_case(CASES["helix-espionage"], strategies=("aggressive", "conservative"), seeds=tuple(range(6)), n_resamples=10)
    sur = bootstrap_case(CASES["helix-espionage"], strategies=("aggressive", "conservative"), seeds=tuple(range(6)), n_resamples=10, surprises=Surprises())
    assert sur.surprises and not plain.surprises


# ----------------------------------------------------------------- sensitivity patching


def test_patching_a_rulebook_constant_reaches_the_judge_and_is_restored():
    case = CASES["helix-espionage"]
    admitted = [i.id for i in case.evidence if i.owner is Side.PROSECUTION]
    before = scoring.score_record(case, admitted).log_odds
    with patched({"LLR_SCALE": Fraction(1)}):
        during = scoring.score_record(case, admitted).log_odds
        assert during != before
    assert scoring.score_record(case, admitted).log_odds == before and Fraction(3) == rules.LLR_SCALE


def test_patching_restores_the_standards_of_proof():
    from courtroom.contracts import StandardOfProof

    was = dict(rules.THRESHOLD_LOG_ODDS)
    with patched(thresholds={StandardOfProof.BEYOND_REASONABLE_DOUBT: Fraction(1)}):
        assert rules.THRESHOLD_LOG_ODDS[StandardOfProof.BEYOND_REASONABLE_DOUBT] == 1
    assert dict(rules.THRESHOLD_LOG_ODDS) == was


# ----------------------------------------------------------------- the best-response search


def test_a_named_style_played_through_the_search_matches_run_trial():
    spec_p, spec_d = O.named("aggressive"), O.named("conservative")
    up, ud = O._play((CASES["helix-espionage"], spec_p, spec_d, 3, None))
    r = run_trial(CASES["helix-espionage"], "aggressive", "conservative", 3)
    assert (up, ud) == (r.utilities[Side.PROSECUTION], r.utilities[Side.DEFENSE])


def test_a_profile_equal_to_a_style_plays_exactly_like_it():
    prof = O.from_profile(O.PROFILES["conservative"], "conservative")
    case = CASES["helix-espionage"]
    assert O._play((case, prof, O.named("aggressive"), 2, None)) == O._play((case, O.named("conservative"), O.named("aggressive"), 2, None))


def test_the_search_is_deterministic():
    kw = dict(budget=4, train=(0, 1), heldout=(100, 101, 102, 103), max_rounds=1)
    a = O.run_oracle(CHEAP, **kw).model_copy(update={"seconds": 0})
    b = O.run_oracle(CHEAP, **kw).model_copy(update={"seconds": 0})
    assert a == b


def test_the_search_only_keeps_a_profile_that_beats_the_equilibrium_by_the_stated_margin():
    r = O.run_oracle(CASES["kestrel-av"], budget=6, train=(0, 1, 2), heldout=tuple(range(100, 108)), max_rounds=2)
    assert r.candidates
    for c in r.candidates:
        assert c.accepted == (c.difference > 0 and c.z > O.ACCEPT_SE)
    assert r.start_equilibrium["verified"] and r.final_equilibrium["verified"]  # exact check: no profitable deviation in the final game
    assert {s["name"] for s in r.final_prosecution} >= set(O.START)  # the hand-written styles stay in the game
    assert r.headline and r.trials > 0 and r.rounds_run <= 2


def test_searched_profiles_stay_inside_the_search_space_and_are_described_in_words():
    r = O.run_oracle(CASES["kestrel-av"], budget=6, train=(0, 1), heldout=(100, 101, 102, 103), max_rounds=1)
    for c in r.candidates:
        for k, (lo, hi) in O.SPACE.items():
            assert lo <= c.params[k] <= hi
        assert c.plain and "objects" in c.plain


def test_surprises_flag_is_recorded_on_the_result():
    r = O.run_oracle(CHEAP, budget=2, train=(0,), heldout=(100, 101, 102), max_rounds=1, surprises=Surprises())
    assert r.surprises is True


def test_oracle_endpoint_is_bounded_and_returns_a_report():
    assert http.post("/api/oracle", json={"case_id": "cookie-jar", "budget": 500}).status_code == 422
    r = http.post("/api/oracle", json={"case_id": "cookie-jar", "budget": 2, "rounds": 1}).json()
    assert r["case_id"] == "cookie-jar" and r["candidates"]


def test_bootstrap_endpoint_and_results_listing():
    r = http.post("/api/bootstrap", json={"case_id": "cookie-jar", "seeds": 5, "resamples": 20}).json()
    assert r["n_seeds"] == 5 and r["baseline_label"]
    assert http.post("/api/bootstrap", json={"case_id": "cookie-jar", "seeds": 5000}).status_code == 422
    assert isinstance(http.get("/api/results").json(), dict)


def test_every_kept_profile_is_checked_again_on_seeds_nobody_looked_at():
    r = O.run_oracle(CASES["kestrel-av"], budget=6, train=(0, 1, 2), heldout=tuple(range(100, 108)), max_rounds=2)
    assert not set(r.confirm_seeds) & (set(r.train_seeds) | set(r.heldout_seeds))
    for c in r.candidates:
        assert (c.confirmed is not None) == c.accepted


def test_the_lab_data_file_is_generated_from_results_and_up_to_date():
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("build_analysis_js", root / "scripts" / "build_analysis_js.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert (root / "courtroom/viz/web/data/analysis.js").read_text(encoding="utf-8") == mod.build(), "run scripts/build_analysis_js.py"
