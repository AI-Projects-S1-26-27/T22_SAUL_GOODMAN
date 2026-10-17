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


# ----------------------------------------------------------------- the bar as a parameter


def test_trial_accepts_a_bar_and_the_judge_applies_it(client: TestClient) -> None:
    body = client.post("/api/trial", json={"case_id": "helix-espionage", "bar": 0.95}).json()
    assert body["verdict"]["snapshot"]["elements"][0]["threshold_probability"] == pytest.approx(0.95, abs=1e-4)


def test_picking_the_standards_own_percent_is_the_certified_trial(client: TestClient) -> None:
    default = client.post("/api/trial", json={"case_id": "helix-espionage", "seed": 2}).json()
    same = client.post("/api/trial", json={"case_id": "helix-espionage", "seed": 2, "bar": 0.90}).json()
    assert same["digest"] == default["digest"], "90% must keep the exact 11/5, not a rounded value"


def test_a_bar_out_of_range_is_refused(client: TestClient) -> None:
    for bar in (0.2, 1.0, 1.5):
        assert client.post("/api/trial", json={"case_id": "helix-espionage", "bar": bar}).status_code == 422


def test_a_case_that_already_names_its_bar_cannot_also_be_given_one(client: TestClient) -> None:
    case = client.get("/api/cases/helix-espionage").json()
    case["bar_log_odds"] = "3"
    assert client.post("/api/trial", json={"case": case, "bar": 0.8}).status_code == 422
    assert client.post("/api/trial", json={"case": case}).status_code == 200


def test_game_recomputes_the_equilibrium_at_a_bar(client: TestClient) -> None:
    body = client.post(
        "/api/game", json={"case_id": "helix-espionage", "bar": 0.8, "seeds": 4, "strategies": ["aggressive", "conservative"]}
    ).json()
    assert body["bar"]["overridden"] is True
    assert body["bar"]["probability"] == pytest.approx(0.8, abs=1e-3)
    assert body["label"] in {"pure", "mixed", "dominance-solvable", "no-equilibrium-found"}
    assert body["analysis"]["equilibria"] is not None


def test_game_without_a_bar_reports_the_standards_own(client: TestClient) -> None:
    body = client.post("/api/game", json={"case_id": "helix-espionage", "seeds": 2}).json()
    assert body["bar"] == {"standard": "beyond_reasonable_doubt", "probability": 0.9002, "log_odds": "11/5", "overridden": False}


def test_game_analyses_a_pasted_case_and_refuses_a_broken_one(client: TestClient) -> None:
    case = client.get("/api/cases/edge-poisoned-tree").json()
    ok = client.post("/api/game", json={"case": case, "seeds": 2})
    assert ok.status_code == 200 and ok.json()["case_id"] == "edge-poisoned-tree"
    assert client.post("/api/game", json={"case": {"id": "broken"}, "seeds": 2}).status_code == 422
    assert client.post("/api/game", json={"seeds": 2}).status_code == 422


def test_an_oversized_pasted_case_is_refused(client: TestClient) -> None:
    case = client.get("/api/cases/helix-espionage").json()
    extra = [dict(case["evidence"][0], id=f"X{i}") for i in range(70)]
    case["evidence"] = case["evidence"] + extra
    assert client.post("/api/game", json={"case": case, "seeds": 1}).status_code == 422


def test_narration_and_trial_agree_on_which_game_was_played(client: TestClient) -> None:
    req = {"case_id": "helix-espionage", "seed": 1, "bar": 0.95}
    assert client.post("/api/narrate", json=req).json()["digest"] == client.post("/api/trial", json=req).json()["digest"]


# ----------------------------------------------------------------- live evidence injection


def _injection(at_seq: int = 6, **overrides) -> dict:
    item = {
        "id": "X-NEW", "title": "Newly recovered drive image", "description": "Found after the trial began.",
        "kind": "document", "owner": "prosecution", "fact_id": "fact-x-new",
        "support": {"access": 0.9}, "reliability": 0.95,
    }
    item.update(overrides)
    return {"at_seq": at_seq, "item": item}


def test_trial_accepts_an_injection_and_records_it(client: TestClient) -> None:
    body = client.post("/api/trial", json={"case_id": "helix-espionage", "seed": 1, "injections": [_injection()]}).json()
    assert [i["item"]["id"] for i in body["injections"]] == ["X-NEW"]
    assert [e["kind"] for e in body["events"]].count("injection") == 1


def test_an_injected_trial_over_http_matches_the_engine_digest(client: TestClient) -> None:
    from courtroom.cases import CASES
    from courtroom.contracts import Injection
    from courtroom.engine import run_trial

    http = client.post("/api/trial", json={"case_id": "helix-espionage", "seed": 1, "injections": [_injection()]}).json()
    direct = run_trial(CASES["helix-espionage"], "aggressive", "conservative", 1, [Injection.model_validate(_injection())])
    assert http["digest"] == direct.digest


def test_an_exhibit_that_does_not_fit_is_a_422_with_the_reason(client: TestClient) -> None:
    r = client.post("/api/trial", json={"case_id": "helix-espionage", "injections": [_injection(id="P-LAPTOP")]})
    assert r.status_code == 422
    assert "does not fit this case" in r.text


def test_a_malformed_exhibit_and_too_many_exhibits_are_refused(client: TestClient) -> None:
    assert client.post("/api/trial", json={"case_id": "helix-espionage", "injections": [_injection(reliability=2)]}).status_code == 422
    four = [_injection(at_seq=3 + i, id=f"X-{i}") for i in range(4)]
    assert client.post("/api/trial", json={"case_id": "helix-espionage", "injections": four}).status_code == 422


def test_narration_describes_the_same_injected_trial(client: TestClient) -> None:
    req = {"case_id": "helix-espionage", "seed": 1, "injections": [_injection()]}
    assert client.post("/api/narrate", json=req).json()["digest"] == client.post("/api/trial", json=req).json()["digest"]


def test_narration_never_reaches_the_network_even_when_a_key_is_set(client: TestClient, monkeypatch) -> None:
    """A page view must not be able to spend money. The server's key, if it has one, is unreachable."""
    from courtroom.llm.client import LLMClient

    monkeypatch.setenv("GEMINI_API_KEY", "set-on-purpose-to-prove-it-is-not-used")

    def boom(self):
        raise AssertionError("the narrate endpoint tried to reach the network")

    monkeypatch.setattr(LLMClient, "_sdk", boom)
    body = client.post("/api/narrate", json={"case_id": "helix-espionage", "seed": 0}).json()
    assert body["usage"]["calls"] == 0
    assert body["source"] == "template"
