"""Review findings API3, API4, API5, A3, S2, S3: bad input gets a clean answer, never a 500 or an unbounded read."""

from __future__ import annotations

from fastapi.testclient import TestClient

from courtroom.api.server import create_app

client = TestClient(create_app())


def test_game_rejects_unknown_and_malformed_strategy_names_with_422() -> None:  # API5
    for bad in ("nope", "mixed:abc"):
        r = client.post("/api/game", json={"case_id": "cookie-jar", "strategies": ["aggressive", bad], "seeds": 1})
        assert r.status_code == 422, (bad, r.status_code)


def test_game_refuses_the_lookahead_exhibition_style() -> None:  # A3
    r = client.post("/api/game", json={"case_id": "cookie-jar", "strategies": ["aggressive", "lookahead"], "seeds": 1})
    assert r.status_code == 422 and "exhibition" in r.text


def test_oversized_body_is_refused_before_it_is_read() -> None:  # API4, S3
    r = client.post("/api/trial", content=b"{" + b" " * 2_000_000 + b"}", headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_deeply_nested_json_is_a_422_not_a_500() -> None:  # API3
    r = client.post("/api/trial", content=b"[" * 50_000 + b"]" * 50_000, headers={"Content-Type": "application/json"})
    assert r.status_code in (400, 413, 422)  # newer FastAPI answers 400 for JSON it cannot parse


def test_a_foreign_host_header_is_refused() -> None:  # S2
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
    assert client.get("/api/health", headers={"Host": "127.0.0.1:8000"}).status_code == 200
    assert client.get("/api/health", headers={"Host": "localhost:8000"}).status_code == 200


def test_a_third_heavy_request_gets_503_instead_of_starving_the_server() -> None:  # API1
    from courtroom.api import server

    held = [server._HEAVY.acquire(blocking=False) for _ in range(server.MAX_HEAVY_JOBS)]
    try:
        assert all(held)
        r = client.post("/api/tree", json={"case_id": "cookie-jar"})
        assert r.status_code == 503
        assert client.get("/api/health").status_code == 200  # light endpoints are unaffected
    finally:
        for _ in held:
            server._HEAVY.release()
    assert client.post("/api/tree", json={"case_id": "cookie-jar"}).status_code == 200  # and it recovers


def test_a_deployment_can_name_its_own_host_but_a_wildcard_is_ignored(monkeypatch) -> None:  # hosting config
    monkeypatch.setenv("COURTROOM_ALLOWED_HOSTS", "demo.example.org, *")
    c = TestClient(create_app())
    assert c.get("/api/health", headers={"Host": "demo.example.org"}).status_code == 200
    assert c.get("/api/health", headers={"Host": "evil.example"}).status_code == 400  # "*" does not open the door to every host
    monkeypatch.delenv("COURTROOM_ALLOWED_HOSTS")
    assert TestClient(create_app()).get("/api/health", headers={"Host": "demo.example.org"}).status_code == 400
