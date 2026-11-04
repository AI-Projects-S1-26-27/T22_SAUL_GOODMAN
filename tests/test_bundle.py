"""The static web bundle must ship the engine, analysis and exhibition that are in the repo.

The hosted demo is static files, so the bundle *is* the product there. Two earlier failures
motivate these tests: analysis results that described a turn order the code no longer played, and
no way to notice. Everything here recomputes from the engine and compares.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from courtroom.cases import CASES, get_plain_case
from courtroom.engine import run_trial
from courtroom.gametheory import estimate_payoffs
from courtroom.gametheory.bootstrap import equilibrium_label

WEB = Path(__file__).resolve().parent.parent / "courtroom" / "viz" / "web"
ROOT = WEB.parent.parent.parent


def _load(path: Path, var: str) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith(f"window.{var} = "), f"{path.name} is not the expected assignment"
    return json.loads(text[text.index("{") : text.rindex("}") + 1])


@pytest.fixture(scope="module")
def bundle() -> dict:
    return _load(WEB / "data" / "bundle.js", "COURTROOM_BUNDLE")


@pytest.fixture(scope="module")
def exhibition() -> dict:
    return _load(WEB / "data" / "exhibition.js", "COURTROOM_EXHIBITION")


# ----------------------------------------------------------------- certified bundle


def test_every_bundled_trial_is_what_the_engine_produces_now(bundle) -> None:
    assert len(bundle["trials"]) == 42
    for key, shipped in bundle["trials"].items():
        case_id, prosecution, defense, seed = key.split("|")
        fresh = run_trial(CASES[case_id], prosecution, defense, seed=int(seed))
        assert shipped["digest"] == fresh.digest, f"{key}: the bundle ships a different engine's trial"
        assert shipped["verdict"]["outcome"] == fresh.verdict.outcome.value


def test_the_bundle_ships_the_four_by_four_game_for_every_case(bundle) -> None:
    assert set(bundle["games"]) == set(CASES)
    for cid, game in bundle["games"].items():
        assert game["row_strategies"] == ["aggressive", "conservative", "adaptive", "mixed:0.5"], cid
        assert len(game["seeds"]) == 200, cid
        assert len(game["cells"]) == 16, cid
        assert game["dynamics"], f"{cid}: no replicator trajectory"


def test_a_bundled_game_reproduces_from_the_engine(bundle) -> None:
    """Cheap case, full 200 seeds: the shipped matrix is the engine's matrix, cell for cell."""
    cid = "edge-empty-docket"
    fresh = estimate_payoffs(CASES[cid], tuple(bundle["meta"]["strategies"]), seeds=range(200))
    shipped = {(c["row"], c["col"]): (c["mean_row"], c["mean_col"]) for c in bundle["games"][cid]["cells"]}
    assert {(c.row, c.col): (c.mean_row, c.mean_col) for c in fresh.cells} == shipped


def test_the_shipped_analysis_describes_the_shipped_games(bundle) -> None:
    """Bootstrap labels must agree with the equilibrium of the matrix next to them."""
    analysis = bundle["analysis"]
    assert analysis["order"] == list(CASES)
    for cid in CASES:
        b = analysis["bootstrap"][cid]
        game = bundle["games"][cid]
        assert b["n_seeds"] == 200 and b["n_resamples"] == 200
        assert b["row_strategies"] == game["row_strategies"]
        from courtroom.gametheory.nash import GameAnalysis

        label = equilibrium_label(GameAnalysis.model_validate(game["analysis"]))
        assert b["baseline_label"] == label, f"{cid}: bootstrap says {b['baseline_label']}, the matrix says {label}"


def test_the_sweep_is_labelled_with_what_it_perturbed(bundle) -> None:
    sweep = bundle["analysis"]["sensitivity"]
    parameters = {v["parameter"] for v in sweep["variations"]}
    assert {"sanctions", "costs", "LLR_SCALE", "PRIOR_DEFECT_RATE", "standards_of_proof", "beyond_reasonable_doubt"} <= parameters
    assert set(sweep["case_ids"]) == set(CASES)
    assert sweep["robust_cases"] or sweep["fragile_cases"]


def test_the_certified_bundle_contains_no_language_model_output(bundle) -> None:
    text = (WEB / "data" / "bundle.js").read_text(encoding="utf-8").lower()
    # The bundle states, in its meta note, that it holds no model output. That sentence is the
    # one permitted mention of the subject; strip it before looking for anything real.
    text = text.replace("contains no language-model output", "")
    for needle in ("gemini", "exhibition", '"llm"'):
        assert needle not in text, f"bundle.js mentions {needle!r}"
    assert "llm" not in bundle and "exhibition" not in bundle


def test_the_bundle_carries_the_judge_constants_it_displays(bundle) -> None:
    rules = bundle["rules"]
    assert rules["standards"]["beyond_reasonable_doubt"]["log_odds"] == "11/5"
    assert rules["standards"]["clear_and_convincing"]["log_odds"] == "11/10"
    assert rules["standards"]["preponderance"]["log_odds"] == "0"


# ----------------------------------------------------------------- exhibition bundle


def test_the_exhibition_is_a_separate_labelled_file(exhibition) -> None:
    meta = exhibition["meta"]
    assert "not equilibrium analysis" in meta["label"].lower()
    assert "best-response verifier" in meta["not_equilibrium"]
    assert meta["kind"] == "exhibition"
    assert meta["mismatches_vs_live_run"] == [], "the replay no longer matches the live run"


def test_the_exhibition_covers_every_seat_opponent_and_seed(exhibition) -> None:
    meta = exhibition["meta"]
    expected = {
        f"{meta['case_id']}|{'llm' if side == 'p' else opp}|{opp if side == 'p' else 'llm'}|{seed}"
        for side in ("p", "d")
        for opp in meta["opponents"]
        for seed in meta["seeds"]
    }
    assert set(exhibition["trials"]) == expected == set(exhibition["stats"])


def test_exhibition_trials_replay_from_the_cache_with_no_network(exhibition, monkeypatch) -> None:
    """Rebuild three shipped trials from the committed cache and compare digests.

    The client is built with the network off, the SDK is booby-trapped, and a key is set in the
    environment on purpose: if anything tried to call out, this would fail loudly.
    """
    from courtroom.contracts import Side
    from courtroom.llm.client import LLMClient
    from courtroom.llm.exhibition import build_court

    monkeypatch.setenv("GEMINI_API_KEY", "set-on-purpose-to-prove-it-is-not-used")

    def boom(self):
        raise AssertionError("the exhibition replay tried to reach the network")

    monkeypatch.setattr(LLMClient, "_sdk", boom)
    client = LLMClient(allow_network=False)
    meta = exhibition["meta"]
    case = get_plain_case(meta["case_id"])  # the exhibition was recorded on the plain rulebook
    for side, opponent, seed in ((Side.PROSECUTION, "aggressive", 0), (Side.DEFENSE, "conservative", 3), (Side.PROSECUTION, "mixed:0.5", 4)):
        court, _ = build_court(case, side, opponent, seed, client)
        result = court.run()
        key = f"{meta['case_id']}|{result.prosecution_strategy}|{result.defense_strategy}|{seed}"
        assert exhibition["trials"][key]["digest"] == result.digest, f"{key} does not replay from the cache"
    assert client.usage.calls == 0


def test_exhibition_decisions_are_fully_accounted_for(exhibition) -> None:
    for key, st in exhibition["stats"].items():
        assert st["llm_chosen"] + st["trivial"] + st["fallbacks"] == st["decisions"], key


# ----------------------------------------------------------------- the static site itself


def test_every_asset_the_page_references_exists_where_vercel_will_serve_it() -> None:
    """vercel.json serves courtroom/viz/web as-is, so every relative reference must resolve there."""
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert config["outputDirectory"] == "courtroom/viz/web"
    assert not config.get("buildCommand"), "the site is static; a build step would be a surprise"

    html = (WEB / "index.html").read_text(encoding="utf-8")
    refs = re.findall(r'(?:src|href)="([^"#:]+)"', html)
    assert refs, "found no local references; the pattern is wrong"
    for ref in refs:
        assert (WEB / ref).exists(), f"index.html references {ref}, which will 404 on the static host"

    css = (WEB / "styles.css").read_text(encoding="utf-8")
    for ref in re.findall(r"url\(['\"]?([^)'\"#:]+)['\"]?\)", css):
        assert (WEB / ref).exists(), f"styles.css references {ref}, which will 404 on the static host"


def test_the_page_stays_functional_without_an_api() -> None:
    """The hosted demo has no /api. The page must fall back to the bundle rather than break."""
    js = (WEB / "app.js").read_text(encoding="utf-8")
    assert 'S.mode = "offline"' in js and "COURTROOM_BUNDLE" in js


# ----------------------------------------------------------------- the precomputed proof-bar ladder


def test_every_case_ships_a_ladder_that_agrees_with_the_certified_analysis(bundle) -> None:
    analysis = bundle["analysis"]
    for cid in CASES:
        grid = analysis["threshold_grid"][cid]
        assert grid["seeds"] == 200 and len(grid["strategies"]) == 4
        bars = [r["bar"] for r in grid["bars"]]
        assert bars == sorted(bars) and len(bars) == 7
        own = [r for r in grid["bars"] if not r["overridden"]]
        assert len(own) == 1, f"{cid}: exactly one rung should be the case's own bar"
        assert own[0]["label"] == analysis["bootstrap"][cid]["baseline_label"], (
            f"{cid}: the ladder's own rung disagrees with the certified analysis"
        )


def test_a_ladder_rung_reproduces_from_the_engine(bundle) -> None:
    """Re-solve one cheap case at one off-standard bar and compare it with what shipped."""
    from courtroom.judge.rules import override_for_bar

    cid, bar = "edge-empty-docket", 0.7
    case = CASES[cid]
    override = override_for_bar(case, bar)
    assert override is not None
    fresh = estimate_payoffs(case.model_copy(update={"bar_log_odds": override}), tuple(bundle["meta"]["strategies"]), seeds=range(200))
    shipped = next(r for r in bundle["analysis"]["threshold_grid"][cid]["bars"] if r["bar"] == bar)
    assert shipped["label"] == equilibrium_label(fresh.analysis)
    assert shipped["equilibria"] == len(fresh.analysis.equilibria)
    assert shipped["overridden"] is True


def test_the_bundle_does_not_hard_code_a_different_standard_than_the_engine(bundle) -> None:
    """The page reads its standards from rules; they must be the engine's, to the digit."""
    from courtroom.judge.rules import THRESHOLD_LOG_ODDS, sigmoid

    for name, shipped in bundle["rules"]["standards"].items():
        standard = next(s for s in THRESHOLD_LOG_ODDS if s.value == name)
        assert shipped["probability"] == round(sigmoid(float(THRESHOLD_LOG_ODDS[standard])), 4)


def test_the_certified_page_does_not_download_the_exhibition() -> None:
    """The replay is 1.5 MB and only the exhibition needs it, so it must load on demand."""
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert "exhibition.js" not in html, "index.html loads the exhibition for every visitor"
    js = (WEB / "app.js").read_text(encoding="utf-8")
    assert js.count("data/exhibition.js") == 1, "the only reference should be the lazy loader"
    assert "function loadExhibitionData" in js


def test_the_exhibition_is_the_only_place_the_llm_strategy_appears_in_the_page_data(bundle) -> None:
    """The LLM seat exists in exhibition.js and nowhere in the certified bundle."""
    assert not any("llm" in key.split("|")[1:3] for key in bundle["trials"])
    assert "llm" not in {s["name"] for s in bundle["strategies"]}
