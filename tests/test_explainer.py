"""The verdict explainer reads the record and the judge's numbers, and can neither change nor invent either."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from courtroom.cases import CASES
from courtroom.contracts import TrialResult
from courtroom.engine import run_trial
from courtroom.llm import LLMClient, OllamaClient
from courtroom.llm.explainer import SYSTEM, _prompt, build_facts, check_text, explain, template_text

HELIX = CASES["helix-espionage"]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*a: object, **k: object) -> None:
        raise urllib.error.URLError("network blocked by the test suite")

    monkeypatch.setattr(urllib.request, "urlopen", blocked)


class Says(LLMClient):
    """A client that always returns the same text, so tests control what the 'model' says."""

    def __init__(self, text: str | None, tmp: Path) -> None:
        super().__init__(cache_path=tmp / "x.json")
        self._text = text

    @property
    def available(self) -> bool:
        return True

    def _request(self, system, prompt, schema):
        self.usage.calls += 1
        return self._text


def _trials():
    for case in CASES.values():
        for p, d in (("aggressive", "conservative"), ("adaptive", "adaptive"), ("conservative", "aggressive")):
            yield case, run_trial(case, p, d, seed=0)


# ----------------------------------------------------------------------- the facts are the judge's own


def test_the_facts_are_copied_from_the_judges_snapshot_not_recomputed() -> None:
    for case, result in _trials():
        facts = build_facts(result, case)
        snap = result.verdict.snapshot
        assert [e.id for e in facts.elements] == [es.element_id for es in snap.elements]
        for fe, es in zip(facts.elements, snap.elements, strict=True):
            assert (fe.log_odds, fe.bar_log_odds, fe.met) == (es.log_odds, es.threshold, es.met)
            assert fe.log_odds_float == round(es.log_odds_float, 2) and fe.probability_pct == round(100 * es.probability, 1)
        assert facts.outcome == result.verdict.outcome.value and facts.reason == result.verdict.reason


def test_explaining_changes_nothing_about_the_trial(tmp_path: Path) -> None:
    result = run_trial(HELIX, "aggressive", "conservative", seed=0)
    before = result.model_dump_json()
    explain(result, HELIX)
    explain(result, HELIX, Says("The defense should have won, by a mile.", tmp_path))
    assert result.model_dump_json() == before
    assert run_trial(HELIX, "aggressive", "conservative", seed=0).digest == result.digest


# ----------------------------------------------------------------------- the text is held to those facts


def test_the_template_passes_its_own_number_check_on_every_case() -> None:
    for case, result in _trials():
        facts = build_facts(result, case)
        text = template_text(facts)
        assert check_text(text, facts) is None, (case.id, check_text(text, facts))
        for e in facts.elements:
            assert f"{e.bar_pct:g}%" in text and f"{e.probability_pct:g}%" in text


def test_an_invented_number_or_exhibit_is_refused() -> None:
    facts = build_facts(run_trial(HELIX, "aggressive", "conservative", seed=0), HELIX)
    assert "12.34" in (check_text("It reached 12.34% on access.", facts) or "")
    assert "P-ZZZ" in (check_text("P-ZZZ settled it.", facts) or "")
    assert check_text("It was close, and the defense had two strong exhibits.", facts) is None
    e = facts.elements[0]
    assert check_text(f"It reached {e.probability_pct:g}% against a bar of {e.bar_pct:g}%.", facts) is None


def test_a_model_that_stays_inside_the_facts_is_used(tmp_path: Path) -> None:
    result = run_trial(HELIX, "aggressive", "conservative", seed=0)
    facts = build_facts(result, HELIX)
    e = facts.elements[0]
    good = f"The judge found for the prosecution. On {e.name} the evidence reached {e.probability_pct:g}%, over a bar of {e.bar_pct:g}%."
    out = explain(result, HELIX, Says(good, tmp_path))
    assert out.source == "model" and out.text == good and out.note is None


@pytest.mark.parametrize("bad", ["The prosecution reached 99.999% certainty.", "Exhibit D-FAKE-1 was decisive.", "It reached 7.77 log-odds."])
def test_a_model_that_adds_a_figure_is_discarded_for_the_template(bad: str, tmp_path: Path) -> None:
    result = run_trial(HELIX, "aggressive", "conservative", seed=0)
    out = explain(result, HELIX, Says(bad, tmp_path))
    assert out.source == "template" and bad not in out.text and out.note and "refused" in out.note
    assert out.text == template_text(out.facts)


def test_no_answer_falls_back_to_the_template_and_says_why(tmp_path: Path) -> None:
    result = run_trial(HELIX, "aggressive", "conservative", seed=0)
    out = explain(result, HELIX, Says(None, tmp_path))
    assert out.source == "template" and out.note
    assert explain(result, HELIX).source == "template"


def test_the_prompt_carries_the_public_record_and_nothing_hidden() -> None:
    for case, result in _trials():
        text = (SYSTEM + _prompt(build_facts(result, case))).lower()
        for word in ("lawfully_obtained", "personal_knowledge", "bias_note", "impartial", "authenticated=", "hostile_risk"):
            assert word not in text, (case.id, word)


# ----------------------------------------------------------------------- local model, offline


def test_it_works_with_ollama_and_replays_from_the_cache_with_the_server_gone(tmp_path: Path) -> None:
    result = run_trial(HELIX, "aggressive", "conservative", seed=0)
    facts = build_facts(result, HELIX)
    e = facts.elements[0]
    reply = f"The judge found for the prosecution: {e.name} reached {e.probability_pct:g}% against {e.bar_pct:g}%."

    def server(path: str, payload: dict | None, timeout: float) -> dict:
        if path == "/api/tags":
            return {"models": [{"name": "qwen3:8b"}]}
        return {"message": {"content": reply}, "prompt_eval_count": 50, "eval_count": 20}

    live = OllamaClient(cache_path=tmp_path / "o.json", transport=server)
    first = explain(result, HELIX, live)
    live.save()
    assert first.source == "model" and first.provider == "ollama" and first.model == "qwen3:8b"

    def gone(*a: object, **k: object) -> dict:
        raise AssertionError("the server is gone; a replay must come from the cache")

    again = explain(result, HELIX, OllamaClient(cache_path=tmp_path / "o.json", transport=gone, allow_network=False))
    assert again.source == "model" and again.text == first.text


def test_when_ollama_is_down_it_still_explains_from_the_template(tmp_path: Path) -> None:
    out = explain(run_trial(HELIX, "aggressive", "conservative", seed=0), HELIX, OllamaClient(cache_path=tmp_path / "o.json"))
    assert out.source == "template" and "ollama serve" in (out.note or "")


# ----------------------------------------------------------------------- the API and the bundle


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from courtroom.api.server import create_app

    return TestClient(create_app())


def test_the_api_explains_a_trial_without_ever_calling_gemini(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COURTROOM_LLM_PROVIDER", raising=False)
    monkeypatch.setattr(LLMClient, "_request", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Gemini must not be called")))
    r = client.post("/api/explain", json={"case_id": "helix-espionage", "prosecution": "aggressive", "defense": "conservative", "seed": 0})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "template" and body["facts"]["outcome"] in {"guilty", "not_guilty", "directed_acquittal"}


def test_the_api_uses_the_local_model_when_configured_and_falls_back_cleanly(client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("COURTROOM_LLM_PROVIDER", "ollama")
    monkeypatch.setattr("courtroom.llm.ollama.OLLAMA_CACHE_PATH", tmp_path / "o.json")
    r = client.post("/api/explain", json={"case_id": "kestrel-av", "seed": 0})
    assert r.status_code == 200 and r.json()["source"] == "template" and "ollama serve" in r.json()["note"]


def test_the_api_rejects_a_bad_request(client) -> None:
    assert client.post("/api/explain", json={"case_id": "no-such-case"}).status_code in (404, 422)


def test_the_bundle_holds_a_current_template_account_for_every_bundled_trial() -> None:
    text = (Path(__file__).resolve().parent.parent / "courtroom" / "viz" / "web" / "data" / "bundle.js").read_text(encoding="utf-8")
    data = json.loads(text[len("window.COURTROOM_BUNDLE = ") :].rstrip().rstrip(";"))
    assert set(data["explanations"]) == set(data["trials"])
    for key, trial in data["trials"].items():
        case = CASES[key.split("|")[0]]
        assert data["explanations"][key] == json.loads(explain(TrialResult.model_validate(trial), case).model_dump_json()), key


def test_the_explainer_is_only_reachable_from_outside_the_core() -> None:
    root = Path(__file__).resolve().parent.parent / "courtroom"
    for package in ("contracts", "judge", "procedure", "agents", "engine", "cases", "gametheory"):
        for path in (root / package).rglob("*.py"):
            assert "llm.explainer" not in path.read_text(encoding="utf-8"), path


def test_the_reason_for_ending_the_case_early_matches_the_rule_the_judge_fired() -> None:
    """DV-2 (nothing accepted bears on the point) and DV-1 (below even odds on motion) are different findings."""
    seen = set()
    for case, result in _trials():
        facts = build_facts(result, case)
        if not facts.directed:
            continue
        fired = next(r.rule_id for e in result.events if e.kind.value == "directed_verdict" for r in e.rules if "GRANTED" in r.detail or "sua sponte" in r.detail)
        text = template_text(facts)
        if fired == "DV-2":
            assert facts.directed_why == "no_support" and "no accepted exhibit supported it" in text
        else:
            assert facts.directed_why == "below_even" and "below even odds" in text and "no accepted exhibit supported it" not in text
        seen.add(fired)
    assert seen == {"DV-1", "DV-2"}, "the fixtures no longer exercise both kinds of early ending"
