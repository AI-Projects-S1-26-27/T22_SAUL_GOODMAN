"""The tree and lookahead entry points: bounded API routes, CLI commands, and the committed results."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from courtroom.api.server import app
from courtroom.cli import main

client = TestClient(app)
RESULTS = Path(__file__).resolve().parent.parent / "results"


def test_tree_route_solves_a_small_case_and_the_methods_agree() -> None:
    r = client.post("/api/tree", json={"case_id": "gen-51", "picture": True}).json()
    assert r["values_agree"] is True and r["value"] is not None
    assert r["alphabeta_ordered_nodes"] <= r["alphabeta_nodes"] <= r["minimax_nodes"]
    assert r["picture"]["kind"] in ("max", "min") and "open-file" in r["note"].lower()


def test_tree_route_is_bounded() -> None:
    assert client.post("/api/tree", json={"case_id": "gen-51", "max_nodes": 10**7}).status_code == 422
    big = client.post("/api/tree", json={"case_id": "helix-espionage", "max_nodes": 500}).json()
    assert big["value"] is None and big["minimax_nodes"] is None  # too big for the limit, reported as such


def test_lookahead_route_is_labelled_and_bounded() -> None:
    r = client.post("/api/lookahead", json={"case_id": "cookie-jar", "seeds": 4}).json()
    assert "not certified" in r["note"].lower() and r["seeds"] == 4
    assert client.post("/api/lookahead", json={"case_id": "cookie-jar", "seeds": 500}).status_code == 422


def test_lookahead_is_selectable_in_a_live_trial() -> None:
    r = client.post("/api/trial", json={"case_id": "cookie-jar", "prosecution": "lookahead", "defense": "adaptive", "seed": 1}).json()
    assert r["prosecution_strategy"] == "lookahead" and r["verdict"]["outcome"]


def test_tree_command(capsys) -> None:
    assert main(["tree", "--case", "gen-20"]) == 0
    out = capsys.readouterr().out
    assert "the three values agree: True" in out


def test_lookahead_command(capsys) -> None:
    assert main(["lookahead", "--case", "cookie-jar", "--seeds", "4"]) == 0
    assert "not certified" in capsys.readouterr().out


def test_committed_tree_results_are_self_consistent() -> None:
    d = json.loads((RESULTS / "tree_search.json").read_text())
    assert d["cases"]
    for cid, r in d["cases"].items():
        if r["values_agree"] is not None:
            assert r["values_agree"] is True, cid
        if r["minimax_nodes"] and r["alphabeta_nodes"] and r["alphabeta_ordered_nodes"]:
            assert r["alphabeta_nodes"] <= r["minimax_nodes"], cid


def test_committed_lookahead_results_are_labelled_exhibition() -> None:
    for name in ("lookahead", "lookahead_surprises"):
        d = json.loads((RESULTS / f"{name}.json").read_text())
        assert d["exhibition"] is True
        assert all("not certified" in c["note"].lower() for c in d["cases"].values())
