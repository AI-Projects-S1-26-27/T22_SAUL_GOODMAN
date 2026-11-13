"""L1-L3 entry points: the classic-game, efficiency and security routes and commands, and the results they committed."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from courtroom.api.server import app
from courtroom.cli import main
from courtroom.gametheory.classic import LABELS

client = TestClient(app)
RESULTS = Path(__file__).resolve().parent.parent / "results"


def test_classic_route_labels_every_two_by_two_corner() -> None:
    r = client.post("/api/classic", json={"case_id": "helix-espionage", "seeds": 5, "resamples": 10}).json()
    assert len(r["subgames"]) == 36
    assert sum(r["label_counts"].values()) == 36 and set(r["label_counts"]) == set(LABELS)
    assert all(0 <= s["stability"] <= 1 for s in r["subgames"])


def test_classic_route_is_bounded() -> None:
    assert client.post("/api/classic", json={"case_id": "helix-espionage", "seeds": 500}).status_code == 422
    assert client.post("/api/classic/find", json={"count": 500}).status_code == 422
    assert client.post("/api/classic/find", json={"targets": ["not-a-game"]}).status_code == 422


def test_classic_find_reports_what_it_tried() -> None:
    r = client.post("/api/classic/find", json={"start": 0, "count": 2}).json()
    assert r["tried"] >= 1 and "Found by search" in r["note"]
    assert set(r["label_counts"]) == set(LABELS)


def test_efficiency_route_reports_pareto_security_and_the_theorem() -> None:
    r = client.post("/api/efficiency", json={"case_id": "kestrel-av", "seeds": 5}).json()
    assert r["efficiency"]["pareto_cells"] and r["efficiency"]["equilibria"]
    assert r["constant_sum"]["theorem_holds"] and r["constant_sum"]["maximin"] == r["constant_sum"]["minimax"]


def test_unknown_case_is_a_404() -> None:
    assert client.post("/api/classic", json={"case_id": "no-such-case"}).status_code == 404


def test_classic_command_runs(capsys) -> None:
    assert main(["classic", "--case", "cookie-jar", "--seeds", "5", "--resamples", "10"]) == 0
    assert "cookie-jar" in capsys.readouterr().out


def test_efficiency_command_runs(capsys) -> None:
    assert main(["efficiency", "--case", "cookie-jar", "--seeds", "5"]) == 0
    assert "theorem holds: True" in capsys.readouterr().out


def test_committed_results_agree_with_the_theorem_and_the_label_set() -> None:
    for name in ("efficiency", "efficiency_surprises"):
        d = json.loads((RESULTS / f"{name}.json").read_text())
        assert d["cases"], name
        for cid, c in d["cases"].items():
            assert c["constant_sum"]["theorem_holds"], f"{name} {cid}"
            assert c["constant_sum"]["maximin"] == c["constant_sum"]["minimax"], f"{name} {cid}"
    for name in ("classic", "classic_surprises"):
        d = json.loads((RESULTS / f"{name}.json").read_text())
        for cid, c in d["cases"].items():
            assert sum(c["label_counts"].values()) == 36, f"{name} {cid}"
            assert set(c["label_counts"]) == set(LABELS)
