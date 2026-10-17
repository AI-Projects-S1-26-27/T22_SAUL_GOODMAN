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


def _smoke(app: Path | None = None) -> tuple[int, dict]:
    env = {**os.environ, **({"UI_SMOKE_APP": str(app)} if app else {})}
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


def test_the_net_catches_the_null_trial_crash(tmp_path) -> None:
    source = APP.read_text(encoding="utf-8")
    guard = "    if (S.trial) { buildTranscript(); updateTranscript(); }"
    assert guard in source, "the guard this mutation removes has moved; update the test"
    mutated = tmp_path / "app.js"
    mutated.write_text(source.replace(guard, "    buildTranscript(); updateTranscript();"), encoding="utf-8")
    code, report = _smoke(mutated)
    assert code == 1
    assert any("reading 'events'" in p for p in report["problems"])


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
