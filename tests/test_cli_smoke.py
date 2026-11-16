"""Review finding T8: the commands that had no test at all run, exit 0 and write what they promise."""

from __future__ import annotations

import json
from pathlib import Path

from courtroom.cli import main


def test_run_writes_the_trial_json(tmp_path: Path) -> None:
    out = tmp_path / "t.json"
    assert main(["run", "--case", "cookie-jar", "--seed", "3", "--json", str(out)]) == 0
    body = json.loads(out.read_text())
    assert body["digest"] and body["seed"] == 3


def test_game_writes_a_payoff_table_with_equilibria(tmp_path: Path) -> None:
    out = tmp_path / "g.json"
    assert main(["game", "--case", "cookie-jar", "--seeds", "2", "--json", str(out)]) == 0
    body = json.loads(out.read_text())
    assert body["analysis"]["equilibria"]


def test_stress_exits_zero_when_nothing_breaks() -> None:
    assert main(["stress", "--cases", "3"]) == 0


def test_tournament_runs() -> None:
    assert main(["tournament", "--seeds", "1", "--workers", "1"]) == 0


def test_unknown_case_is_a_clean_error_not_a_traceback() -> None:
    assert main(["run", "--case", "no-such-case"]) != 0
