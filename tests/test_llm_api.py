"""W2 over HTTP, with a stub model: the AI lawyer, case drafting and narration."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from courtroom.api import server
from courtroom.cases import CASES
from courtroom.llm.draft import MAX_REPAIRS, draft_case, sanity
from courtroom.llm.narrator import check_line, narrate_case
from tests.llm_stub import Stub, stub_client

client = TestClient(server.app)
BODY = {"case_id": "helix-espionage", "prosecution": "llm", "defense": "conservative", "seed": 0}

GOOD = {
    "id": "x", "title": "Lee v. Park — The Borrowed Drone", "synopsis": "Lee lent a drone. It came back broken. Park denies it.",
    "case_type": "civil", "standard": "preponderance", "charge": "Park broke the drone.",
    "elements": [{"id": "damage", "name": "Damage", "description": "Park damaged the drone."}],
    "witnesses": [{"id": "W-SAM", "name": "Sam Ortiz", "role": "neighbour", "credibility": 0.8, "bias_note": None}],
    "evidence": [
        {"id": "P-PHOTO", "title": "Photo of the broken drone", "description": "A photo showing a cracked frame.", "kind": "physical", "owner": "prosecution", "fact_id": "f1", "support": {"damage": 0.8}, "reliability": 0.9},
        {"id": "P-SAM", "title": "Sam saw Park crash it", "description": "Sam says he watched Park crash it.", "kind": "testimony", "owner": "prosecution", "fact_id": "f2", "support": {"damage": 0.7}, "reliability": 0.7, "witness_id": "W-SAM"},
        {"id": "D-RECEIPT", "title": "Repair shop note", "description": "A shop note says the frame was already cracked.", "kind": "document", "owner": "defense", "fact_id": "f3", "support": {"damage": -0.6}, "reliability": 0.8},
    ],
}


@pytest.fixture
def stubbed(tmp_path, monkeypatch):
    c, stub = stub_client(tmp_path)
    monkeypatch.setattr(server, "default_client", lambda *a, **k: c)
    return c, stub


def test_ai_lawyer_trial_is_marked_not_certified_and_reports_its_fallbacks(stubbed):
    r = client.post("/api/trial", json=BODY).json()
    assert r["certified"] is False and r["ai"]["sides"]["prosecution"]["decisions"] > 0
    assert 0 <= r["ai"]["fallback_rate"] <= 1
    assert any(e["action"] and e["action"]["rationale"].startswith("[ai] ") for e in r["events"])


def test_ordinary_trials_stay_certified_and_have_no_ai_block():
    r = client.post("/api/trial", json={**BODY, "prosecution": "adaptive"}).json()
    assert r["certified"] is True and r["ai"] is None


def test_the_ai_lawyer_cannot_enter_a_payoff_table():
    assert client.post("/api/game", json={"case_id": "cookie-jar", "strategies": ["aggressive", "llm"]}).status_code == 422


def test_ai_trial_verifies_because_the_second_run_replays_from_cache(stubbed):
    r = client.post("/api/verify", json=BODY).json()
    assert r["identical"] and r["chain_valid"]


def test_ai_status_says_when_nothing_answers(tmp_path, monkeypatch):
    from courtroom.llm import LLMClient

    monkeypatch.setattr(server, "default_client", lambda *a, **k: LLMClient(backends=[], cache_path=tmp_path / "c.json"))
    assert client.get("/api/ai").json()["available"] is False
    assert client.post("/api/case/draft", json={"text": "my neighbour broke my drone"}).status_code == 503
    assert client.post("/api/narrate", json={"case_id": "cookie-jar"}).status_code == 503


# ----------------------------------------------------------------- drafting


def test_a_good_draft_validates_and_lands_as_a_custom_case(tmp_path):
    c, _ = stub_client(tmp_path, Stub(lambda body: json.dumps(GOOD)))
    d = draft_case("Lee lent Park a drone and it came back broken", c)
    assert d.case is not None and d.repairs == 0 and "custom" in d.case.tags and d.case.id.startswith("draft-")
    assert not sanity(d.case)


def test_a_bad_draft_is_repaired_with_the_validators_own_errors(tmp_path):
    replies = iter([json.dumps({**GOOD, "standard": "very_sure"}), json.dumps(GOOD)])
    seen: list[str] = []

    def reply(body):
        seen.append(body["messages"][1]["content"])
        return next(replies)

    c, _ = stub_client(tmp_path, Stub(reply))
    d = draft_case("Lee lent Park a drone and it came back broken", c)
    assert d.case is not None and d.repairs == 1
    assert "standard" in seen[1] and "not accepted" in seen[1]  # the error was fed back


def test_a_draft_that_never_validates_gives_up_after_the_repair_limit(tmp_path):
    c, stub = stub_client(tmp_path, Stub(lambda body: "not json at all"))
    d = draft_case("Lee lent Park a drone and it came back broken", c)
    assert d.case is None and d.repairs == MAX_REPAIRS and d.problems
    assert c.usage.calls + c.usage.cache_hits == MAX_REPAIRS + 1  # first ask plus each repair (identical repairs hit the cache)
    assert stub.chats


def test_a_valid_case_with_no_defense_evidence_is_sent_back(tmp_path):
    lopsided = {**GOOD, "evidence": [e for e in GOOD["evidence"] if e["owner"] == "prosecution"]}
    replies = iter([json.dumps(lopsided), json.dumps(GOOD)])
    c, _ = stub_client(tmp_path, Stub(lambda body: next(replies)))
    d = draft_case("Lee lent Park a drone and it came back broken", c)
    assert d.case is not None and d.repairs == 1


def test_numbers_with_too_many_decimals_are_rounded_not_rejected(tmp_path):
    messy = json.loads(json.dumps(GOOD))
    messy["evidence"][0]["reliability"] = 0.8500000001
    c, _ = stub_client(tmp_path, Stub(lambda body: json.dumps(messy)))
    d = draft_case("Lee lent Park a drone and it came back broken", c)
    assert d.case is not None and d.repairs == 0 and d.case.evidence[0].reliability == 0.85


def test_draft_endpoint_returns_the_case_for_the_editor(tmp_path, monkeypatch):
    c, _ = stub_client(tmp_path, Stub(lambda body: json.dumps(GOOD)))
    monkeypatch.setattr(server, "default_client", lambda *a, **k: c)
    r = client.post("/api/case/draft", json={"text": "Lee lent Park a drone and it came back broken"}).json()
    assert r["case"]["id"].startswith("draft-") and r["notes"]
    inline = client.post("/api/trial", json={"case": r["case"], "prosecution": "adaptive", "defense": "adaptive"})
    assert inline.status_code == 200  # the drafted case plays like any other


# ----------------------------------------------------------------- narration


def test_a_line_that_invents_a_number_or_a_name_is_refused():
    src = "Photo of the broken drone. A photo showing a cracked frame. Sam Ortiz neighbour"
    assert check_line("Your Honour, this photo shows a cracked frame.", src) is None
    assert "number" in check_line("Your Honour, this photo shows 3 cracks.", src)
    assert "Bruno" in check_line("Your Honour, Bruno took this photo.", src)


def test_narration_keeps_good_lines_and_refuses_ones_that_add_facts(tmp_path):
    case = CASES["cookie-jar"]
    item = case.evidence[0]

    def reply(body):
        text = body["messages"][1]["content"]
        if item.title in text:
            return json.dumps({"say": "Your Honour, I add the 99 cookies Zorg ate.", "wit": ""})
        return json.dumps({"say": f"Your Honour, here is {text.split('Exhibit title: ')[1].splitlines()[0]}.", "wit": "I saw it myself."})

    c, _ = stub_client(tmp_path, Stub(reply))
    out = narrate_case(case, c)
    assert item.id in out["refused"] and len(out["ev"]) == len(case.evidence) - 1


def test_narration_offline_is_empty_so_the_page_keeps_its_generic_lines(tmp_path):
    from courtroom.llm import LLMClient

    out = narrate_case(CASES["cookie-jar"], LLMClient(backends=[], cache_path=tmp_path / "c.json"))
    assert out["ev"] == {} and len(out["refused"]) == len(CASES["cookie-jar"].evidence)


def test_the_analyst_falls_back_to_gemini_as_a_third_backend(monkeypatch):
    from courtroom.api import analyst
    from courtroom.llm import backends

    monkeypatch.setattr(analyst, "load_env", lambda: None)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(analyst, "_local_model", lambda: None)
    monkeypatch.setattr(backends.GeminiBackend, "chat", lambda self, system, prompt, **kw: "Gemini says hi")
    r = client.post("/api/analyst", json={"question": "Who wins?"})
    assert r.status_code == 200 and r.json()["source"] == "gemini" and r.json()["reply"] == "Gemini says hi"
