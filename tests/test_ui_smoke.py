"""Run the web UI's real JavaScript in Node against the real bundle, and test the net itself.

``tests/ui_smoke.cjs`` boots ``app.js`` with a stub DOM and the shipped ``bundle.js``, fires every
registered listener, and visits every tab. It exists because two regressions got past the Python
suite: a splice that deleted functions ``init()`` still called, and a guard that missed a null
trial. Neither could be seen without running the JavaScript.

The mutation tests below are what keep the net honest. A smoke test that passes proves nothing
until you know it fails when it should, so each one reintroduces a real bug and demands a red.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "courtroom" / "viz" / "web" / "app.js"
HARNESS = ROOT / "tests" / "ui_smoke.cjs"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _smoke(app: Path | None = None, **extra: str) -> tuple[int, dict]:
    env = {**os.environ, **({"UI_SMOKE_APP": str(app)} if app else {}), **extra}
    done = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True, timeout=120, env=env, check=False)
    try:
        return done.returncode, json.loads(done.stdout)
    except ValueError:
        pytest.fail(f"the harness produced no JSON:\n{done.stdout}\n{done.stderr}")


def _without_function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    end = source.index("\n}\n", start) + 3
    return source[:start] + source[end:]


def test_the_real_ui_runs_clean_against_the_real_bundle() -> None:
    code, report = _smoke()
    assert report["problems"] == [], report["problems"]
    assert code == 0
    # a case really loaded and rendered: hundreds of handlers exist only once a trial is built
    assert report["listeners"] > 100, "no trial rendered, so this run proved very little"


def test_the_net_catches_a_deleted_function_that_init_calls(tmp_path) -> None:
    mutated = tmp_path / "app.js"
    mutated.write_text(_without_function(APP.read_text(encoding="utf-8"), "initModeBar"), encoding="utf-8")
    code, report = _smoke(mutated)
    assert code == 1
    assert any("initModeBar is not defined" in p for p in report["problems"])


def test_the_net_catches_a_render_that_assumes_a_trial_exists_before_one_has_loaded(tmp_path) -> None:
    """The class of bug that crashed the mode bar: init renders before any trial is loaded."""
    source = APP.read_text(encoding="utf-8")
    guard = '  if (!S.trial) {\n    box.replaceChildren(el("p", { class: "empty-note" }, "Load a trial in the courtroom first'
    assert guard in source, "the guard this mutation removes has moved; update the test"
    mutated = tmp_path / "app.js"
    mutated.write_text(source.replace(guard, '  if (false) {\n    box.replaceChildren(el("p", { class: "empty-note" }, "Load a trial in the courtroom first', 1), encoding="utf-8")
    code, report = _smoke(mutated)
    assert code == 1
    assert any("Cannot read properties of null" in p for p in report["problems"])
    assert report["stateAfterInit"]["caseId"] is None, "init should have aborted before selecting a case"


def test_the_net_catches_an_error_the_app_catches_and_shows_the_user(tmp_path) -> None:
    """A render error that loadTrial turns into 'The trial couldn't run' must still fail the build."""
    mutated = tmp_path / "app.js"
    mutated.write_text(_without_function(APP.read_text(encoding="utf-8"), "renderEvidenceMap"), encoding="utf-8")
    code, report = _smoke(mutated)
    assert code == 1
    assert any("renderEvidenceMap is not defined" in p for p in report["problems"])


def test_the_net_catches_a_tab_that_cannot_render(tmp_path) -> None:
    mutated = tmp_path / "app.js"
    mutated.write_text(_without_function(APP.read_text(encoding="utf-8"), "renderThreshold"), encoding="utf-8")
    code, report = _smoke(mutated)
    assert code == 1
    assert any("renderThreshold" in p for p in report["problems"])


# ----------------------------------------------------------------- live mode: the code a local user runs


@pytest.fixture(scope="module")
def live_fixtures(tmp_path_factory) -> Path:
    """Genuine engine output served by a fake API, so live-only code runs against real shapes."""
    from courtroom.agents import describe_strategies
    from courtroom.cases import CASES
    from courtroom.contracts import EvidenceItem, EvidenceKind, Injection, Side
    from courtroom.engine import run_trial
    from courtroom.gametheory import estimate_payoffs
    from courtroom.gametheory.bootstrap import equilibrium_label
    from courtroom.judge.rules import THRESHOLD_LOG_ODDS, sigmoid

    case = CASES["helix-espionage"]
    item = EvidenceItem(
        id="INJ-1", title="Newly recovered drive image", description="x", kind=EvidenceKind.DOCUMENT, owner=Side.PROSECUTION,
        fact_id="fact-inj-1", support={case.elements[0].id: 0.8}, reliability=0.9,
    )
    strategies = ("aggressive", "conservative", "adaptive", "mixed:0.5")
    table = estimate_payoffs(case, strategies, seeds=range(2))
    game = json.loads(table.model_dump_json())
    game["dynamics"] = []
    game["label"] = equilibrium_label(table.analysis)
    game["bar"] = {"standard": case.standard.value, "probability": 0.9002, "log_odds": "11/5", "overridden": False}
    bundle_rules = json.loads((ROOT / "courtroom" / "viz" / "web" / "data" / "bundle.js").read_text("utf-8").split("= ", 1)[1].rsplit(";", 1)[0])["rules"]
    fx = {
        "cases": [json.loads(c.model_dump_json()) for c in CASES.values()],
        "strategies": describe_strategies(),
        "rules": bundle_rules,
        "baseline": json.loads(run_trial(case, "aggressive", "conservative", 0).model_dump_json()),
        "injected": json.loads(run_trial(case, "aggressive", "conservative", 0, [Injection(at_seq=4, item=item)]).model_dump_json()),
        "game": game,
    }
    assert sigmoid(float(THRESHOLD_LOG_ODDS[case.standard])) == pytest.approx(0.9002, abs=1e-4)
    path = tmp_path_factory.mktemp("live") / "fixtures.json"
    path.write_text(json.dumps(fx), encoding="utf-8")
    return path


def _smoke_live(fixtures: Path, app: Path | None = None, **extra: str) -> tuple[int, dict]:
    env = {**os.environ, "UI_SMOKE_LIVE": str(fixtures), **({"UI_SMOKE_APP": str(app)} if app else {}), **extra}
    done = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True, timeout=120, env=env, check=False)
    try:
        return done.returncode, json.loads(done.stdout)
    except ValueError:
        pytest.fail(f"the harness produced no JSON:\n{done.stdout}\n{done.stderr}")


def test_the_live_ui_runs_clean_and_really_uses_the_live_controls(live_fixtures) -> None:
    code, report = _smoke_live(live_fixtures)
    assert report["problems"] == [], report["problems"]
    assert code == 0
    calls = report["calls"]
    paths = {c["path"] for c in calls}
    assert {"/health", "/cases", "/rules", "/trial", "/game"} <= paths
    assert any(c["path"] == "/trial" and c["injections"] == 1 for c in calls), "the injection button never fired a request"
    assert any(c["path"] == "/trial" and c["bar"] is not None for c in calls), "the replay-at-a-bar button never fired"
    assert any(c["path"] == "/game" and c["bar"] is not None for c in calls), "the recompute-at-a-bar button never fired"
    assert any(c["path"] == "/game" and c["inlineCase"] for c in calls), "the editor's Analyse button never fired"


def test_an_injected_exhibit_reaches_the_evidence_board(live_fixtures) -> None:
    """The trial used the exhibit, so the page has to list it. The board is built outside setupTrial,
    and an earlier version of the injection UI forgot to rebuild it: no exception, just a wrong page."""
    _, report = _smoke_live(live_fixtures)
    assert "ev-item|INJ-1" in report["dataIds"], f"the board never listed the injected exhibit: {report['dataIds']}"


def test_the_net_catches_an_injection_that_forgets_the_board(live_fixtures, tmp_path) -> None:
    source = APP.read_text(encoding="utf-8")
    needle = "    S.caseFile = withInjected(S.baseCaseFile, S.injections);\n    buildEvidenceBoard();\n"
    assert needle in source, "the line this mutation removes has moved; update the test"
    mutated = tmp_path / "app.js"
    mutated.write_text(source.replace(needle, "    S.caseFile = withInjected(S.baseCaseFile, S.injections);\n", 1), encoding="utf-8")
    _, report = _smoke_live(live_fixtures, mutated)
    assert "ev-item|INJ-1" not in report["dataIds"], "this mutation should have left the board without the exhibit"


def test_the_net_catches_a_broken_injection_path(live_fixtures, tmp_path) -> None:
    """Break only code that runs after the injection response arrives, and demand a red."""
    source = APP.read_text(encoding="utf-8")
    mutated = tmp_path / "app.js"
    mutated.write_text(source.replace("const withInjected = ", "const withInjectedGone = ", 1), encoding="utf-8")
    code, report = _smoke_live(live_fixtures, mutated)
    assert code == 1
    assert any("withInjected is not defined" in p for p in report["problems"])


# ----------------------------------------------------------------- the LLM exhibition mode


def test_the_page_always_opens_in_the_certified_mode() -> None:
    """Shared links and screenshots must never open in the exhibition by accident."""
    _, report = _smoke()
    assert report["stateAfterInit"]["exhibitionOn"] is False


def test_the_exhibition_opens_the_models_trial_from_the_replay_offline() -> None:
    code, report = _smoke(UI_SMOKE_START="exhibition")
    assert report["problems"] == [], report["problems"]
    assert code == 0
    assert report["stateAfterEnter"]["exhibitionOn"] is True
    assert report["stateAfterEnter"]["key"] == "helix-espionage|llm|conservative|0"
    assert report["stateAtEnd"]["exhibitionOn"] is True
    assert "ev-item|P-LAPTOP" in report["dataIds"], "the model's trial rendered no evidence board"


def test_in_the_exhibition_no_request_ever_names_the_llm_strategy(live_fixtures) -> None:
    """The server has no "llm" strategy to run, and the page must not try to send one.

    Live mode is where a stray request could actually go out, so this runs the exhibition there.
    """
    _, report = _smoke_live(live_fixtures, UI_SMOKE_START="exhibition")
    assert report["problems"] == [], report["problems"]
    assert report["stateAfterEnter"]["key"] == "helix-espionage|llm|conservative|0"
    # (the run goes on to fire the editor's "Try it in the courtroom", which leaves the exhibition by design)
    for call in report["calls"]:
        assert "llm" not in call["strategies"], f"the page sent the LLM strategy to the server: {call}"


def test_the_net_catches_an_exhibition_that_asks_the_server_for_the_model(live_fixtures, tmp_path) -> None:
    source = APP.read_text(encoding="utf-8")
    needle = "    const trial = S.exhibitionOn\n      ? S.exhibition.trials[key]\n      : S.mode === \"live\""
    assert needle in source, "the line this mutation changes has moved; update the test"
    mutated = tmp_path / "app.js"
    mutated.write_text(source.replace(needle, "    const trial = false\n      ? S.exhibition.trials[key]\n      : S.mode === \"live\"", 1), encoding="utf-8")
    _, report = _smoke_live(live_fixtures, mutated, UI_SMOKE_START="exhibition")
    assert any("llm" in c["strategies"] for c in report["calls"]), "the mutation should have sent the LLM strategy to the server"
