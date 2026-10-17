"""Engineers 6 & 7: HTTP API contract and UI serving."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from courtroom.api.server import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"


def test_cases_and_case_file(client: TestClient) -> None:
    ids = [c["id"] for c in client.get("/api/cases").json()]
    assert "helix-espionage" in ids
    assert client.get("/api/cases/helix-espionage").json()["elements"]
    assert client.get("/api/cases/gen-7").status_code == 200
    assert client.get("/api/cases/nope").status_code == 404


def test_trial_round_trip_is_deterministic(client: TestClient) -> None:
    body = {"case_id": "helix-espionage", "prosecution": "aggressive", "defense": "adaptive", "seed": 3}
    a, b = client.post("/api/trial", json=body).json(), client.post("/api/trial", json=body).json()
    assert a["digest"] == b["digest"]
    assert a["events"][-1]["kind"] == "verdict"


@pytest.mark.parametrize(
    "body",
    [
        {"case_id": "helix-espionage", "prosecution": "bribery"},
        {"case_id": "helix-espionage", "seed": -1},
        {"case_id": "helix-espionage", "defense": "mixed:7"},
    ],
)
def test_bad_trial_requests_are_rejected(client: TestClient, body: dict) -> None:
    assert client.post("/api/trial", json=body).status_code == 422


def test_game_endpoint(client: TestClient) -> None:
    r = client.post("/api/game", json={"case_id": "edge-mutual-exclusion", "seeds": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["analysis"]["equilibria"] and body["dynamics"]


def test_game_limits(client: TestClient) -> None:
    assert client.post("/api/game", json={"case_id": "helix-espionage", "seeds": 10_000}).status_code == 422
    assert client.post("/api/game", json={"case_id": "helix-espionage", "strategies": ["chaos", "aggressive"]}).status_code == 422


def test_ui_is_served(client: TestClient) -> None:
    html = client.get("/").text
    assert "Courtroom" in html and "app.js" in html
    assert client.get("/app.js").status_code == 200


def test_validate_accepts_a_library_case(client: TestClient) -> None:
    payload = client.get("/api/cases/helix-espionage").json()
    r = client.post("/api/validate", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and body["case_id"] == "helix-espionage"
    assert body["elements"] == 3 and body["evidence"] == 17


def test_validate_names_the_failing_field(client: TestClient) -> None:
    r = client.post("/api/validate", json={"id": "broken"})
    assert r.status_code == 422
    body = r.json()
    assert body["ok"] is False
    assert body["errors"] and all({"field", "message"} <= set(e) for e in body["errors"])
    assert any(e["field"] == "title" for e in body["errors"])


def test_trial_accepts_an_inline_case_file(client: TestClient) -> None:
    payload = client.get("/api/cases/helix-espionage").json()
    inline = client.post("/api/trial", json={"case": payload, "seed": 0}).json()
    by_id = client.post("/api/trial", json={"case_id": "helix-espionage", "seed": 0}).json()
    assert inline["digest"] == by_id["digest"]  # same case, same seed, same trial


def test_trial_requires_a_case(client: TestClient) -> None:
    assert client.post("/api/trial", json={"seed": 0}).status_code == 422


def test_rules_endpoint_reports_thresholds_and_catch_probability(client: TestClient) -> None:
    body = client.get("/api/rules").json()
    assert body["standards"]["beyond_reasonable_doubt"]["log_odds"] == "11/5"
    assert body["priors"]["criminal"]["probability"] == pytest.approx(0.2689, abs=1e-4)
    assert body["prior_defect_rate"] == pytest.approx(0.15)
    rows = next(iter(body["catch_probability"].values()))
    observable = {r["ground"] for r in rows if r["observable"]}
    assert observable == {"relevance", "late_disclosure"}
    for r in rows:
        if r["observable"]:
            assert all(v == 1.0 for v in r["caught_by"].values())
