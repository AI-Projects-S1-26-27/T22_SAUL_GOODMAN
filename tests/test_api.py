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


def test_analyst_forwards_to_a_backend(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from courtroom.api import analyst

    seen: dict[str, object] = {}

    def fake_chat(base: str, model: str, key: str | None, messages: list[dict[str, str]]) -> str:
        seen.update(base=base, key=key, messages=messages)
        return "Careful wins here."

    monkeypatch.setattr(analyst, "load_env", lambda: None)
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")
    monkeypatch.setattr(analyst, "_chat", fake_chat)
    r = client.post("/api/analyst", json={"question": "Who wins?", "context": "A=[[1,2],[3,4]]"})
    assert r.status_code == 200
    assert r.json()["reply"] == "Careful wins here."
    assert r.json()["source"] == "cloud"
    assert seen["key"] == "test-key"
    assert "test-key" not in r.text
    messages = seen["messages"]
    assert isinstance(messages, list)
    assert "A=[[1,2],[3,4]]" in messages[0]["content"]
    assert messages[-1]["content"] == "Who wins?"


def test_analyst_reports_unavailable_and_bounds_input(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from courtroom.api import analyst

    def down(*_: object) -> str:
        raise RuntimeError("Add usage credits")

    monkeypatch.setattr(analyst, "load_env", lambda: None)
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")
    monkeypatch.setattr(analyst, "_chat", down)
    monkeypatch.setattr(analyst, "_local_model", lambda: None)
    r = client.post("/api/analyst", json={"question": "Who wins?"})
    assert r.status_code == 503
    assert any("Add usage credits" in x for x in r.json()["reasons"])
    assert "test-key" not in r.text
    assert client.post("/api/analyst", json={"question": "x" * 601}).status_code == 422
    assert client.post("/api/analyst", json={"question": ""}).status_code == 422
