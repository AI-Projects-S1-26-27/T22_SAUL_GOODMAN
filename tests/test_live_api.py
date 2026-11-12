"""W1: the live-control endpoints (verify, matters, find, explain, inline case, surprises)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from courtroom.api.server import app
from courtroom.cases import CASES
from courtroom.engine import run_trial
from courtroom.gametheory.finder import find_contested
from courtroom.gametheory.matters import measure
from courtroom.judge.tipping import prosecution_wins, record_of, tipping_points

client = TestClient(app)
BODY = {"case_id": "helix-espionage", "prosecution": "aggressive", "defense": "conservative", "seed": 0}


def test_verify_runs_twice_and_matches():
    r = client.post("/api/verify", json=BODY).json()
    assert r["identical"] and r["chain_valid"] and r["digest_first"] == r["digest_second"]


def test_a_recorded_trial_matches_what_the_server_computes():
    import json
    from pathlib import Path

    pinned = json.loads((Path(__file__).parent / "golden" / "bundle_digests.json").read_text())
    assert client.post("/api/trial", json=BODY).json()["digest"] == pinned["helix-espionage|aggressive|conservative|0"]


def test_surprises_toggle_changes_the_record_only_when_on():
    plain = client.post("/api/trial", json=BODY).json()
    on = client.post("/api/trial", json={**BODY, "seed": 1, "surprises": True}).json()
    assert plain["surprises"] is None and on["surprises"]["no_show"] == 0.1
    assert plain["digest"] == client.post("/api/trial", json={**BODY, "surprises": False}).json()["digest"]


def test_inline_case_is_used_and_validated():
    case = CASES["cookie-jar"].model_dump(mode="json")
    case["id"] = "my-case"
    r = client.post("/api/trial", json={"case": case, "prosecution": "adaptive", "defense": "adaptive"})
    assert r.status_code == 200 and r.json()["case_id"] == "my-case"
    bad = dict(case, budget=-1)
    assert client.post("/api/trial", json={"case": bad}).status_code == 422


def test_inline_case_is_size_bounded():
    case = CASES["cookie-jar"].model_dump(mode="json")
    case["evidence"] = [dict(case["evidence"][0], id=f"X-{i}") for i in range(31)]
    assert client.post("/api/trial", json={"case": case}).status_code == 422


def test_what_if_changing_an_exhibit_moves_the_verdict():
    case = CASES["helix-espionage"].model_dump(mode="json")
    base = client.post("/api/trial", json={"case": case, **{k: v for k, v in BODY.items() if k != "case_id"}}).json()
    assert base["verdict"]["outcome"] == "guilty"
    tip = client.post("/api/explain", json=BODY).json()["tipping"][0]
    for e in case["evidence"]:
        if e["id"] == tip["target"]:
            e["reliability"] = tip["to_value"]
    moved = client.post("/api/trial", json={"case": case, **{k: v for k, v in BODY.items() if k != "case_id"}}).json()
    assert moved["verdict"]["outcome"] != "guilty"


def test_matters_endpoint_rates_the_cases_honestly():
    cookie = client.post("/api/matters", json={"case_id": "cookie-jar"}).json()
    helix = client.post("/api/matters", json={"case_id": "helix-espionage", "seeds": 3}).json()
    assert cookie["verdict"] == "evidence" and cookie["pairing_spread"] == 0
    assert helix["verdict"] == "lawyers" and helix["pairing_spread"] >= 0.5


def test_matters_is_deterministic():
    assert measure(CASES["helix-espionage"], seeds=(0, 1)) == measure(CASES["helix-espionage"], seeds=(0, 1))


def test_finder_returns_playable_generated_cases():
    r = find_contested(start=0, count=8, top=2, game_seeds=(0, 1, 2))
    assert r.found and all(f.case_id.startswith("gen-") for f in r.found)
    assert client.get(f"/api/cases/{r.found[0].case_id}").status_code == 200
    again = find_contested(start=0, count=8, top=2, game_seeds=(0, 1, 2))
    assert [f.case_id for f in r.found] == [f.case_id for f in again.found]


def test_find_endpoint_is_bounded():
    assert client.post("/api/find", json={"count": 500}).status_code == 422


@pytest.mark.parametrize("cid,p,d", [("helix-espionage", "aggressive", "conservative"), ("kestrel-av", "adaptive", "adaptive")])
def test_tipping_points_really_flip_the_judges_verdict(cid, p, d):
    case = CASES[cid]
    result = run_trial(case, p, d, 0)
    rec = record_of(result)
    assert prosecution_wins(case, rec) == (result.verdict.outcome.favours.value == "prosecution")
    tips = tipping_points(case, result)
    assert tips
    for t in tips:
        from courtroom.judge.tipping import _with  # the same re-scoring the search uses

        flipped = _with(case, "exhibit" if t.kind == "exhibit" else "witness", t.target, t.to_value)
        step = 0.0001 if t.to_value > t.from_value else -0.0001
        before = _with(case, "exhibit" if t.kind == "exhibit" else "witness", t.target, round(t.to_value - step, 4))
        assert prosecution_wins(flipped, rec) != prosecution_wins(case, rec)
        assert prosecution_wins(before, rec) == prosecution_wins(case, rec)


def test_explain_text_uses_only_the_judges_figures():
    from courtroom.judge.explain import build_facts, check_text, template_text

    case = CASES["kestrel-av"]
    result = run_trial(case, "adaptive", "adaptive", 0)
    facts = build_facts(result, case)
    assert check_text(template_text(facts), facts) is None
