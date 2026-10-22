"""Gemini transport behaviour, driven entirely by stubs.

No test in this file performs a network call. The SDK client is replaced with a fake, so every
branch — success, transient 429, daily quota, safety block, malformed structured output, cache
hit — is exercised deterministically and offline.
"""

from __future__ import annotations

import json

import pytest
from google.genai import errors

from courtroom.contracts import Side
from courtroom.llm.client import (
    ActionChoice,
    LLMClient,
    QuotaExhausted,
    cache_key,
)

# ----------------------------------------------------------------- fakes


class _Part:
    def __init__(self, text: str) -> None:
        self.text = text


class _Content:
    def __init__(self, text: str) -> None:
        self.parts = [_Part(text)]


class _Candidate:
    def __init__(self, text: str = "", finish_reason: str = "STOP") -> None:
        self.content = _Content(text)
        self.finish_reason = finish_reason


class _Usage:
    def __init__(self, prompt: int = 11, out: int = 7) -> None:
        self.prompt_token_count = prompt
        self.candidates_token_count = out
        self.thoughts_token_count = 0


class _Response:
    def __init__(self, text: str = "", finish_reason: str = "STOP") -> None:
        self.candidates = [_Candidate(text, finish_reason)]
        self.usage_metadata = _Usage()
        self.prompt_feedback = None
        self.text = text


class _Models:
    def __init__(self, outcomes: list) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0) if self.outcomes else _Response("fallthrough")
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _SDK:
    def __init__(self, outcomes: list) -> None:
        self.models = _Models(outcomes)


def _client(tmp_path, outcomes: list, **kw) -> LLMClient:
    client = LLMClient(cache_path=tmp_path / "responses.json", **kw)
    client._client = _SDK(outcomes)  # never constructs a real genai.Client
    return client


def _client_error(status: int, message: str) -> errors.ClientError:
    exc = errors.ClientError.__new__(errors.ClientError)
    Exception.__init__(exc, message)
    exc.code = status
    return exc


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "stub-key-never-used")
    monkeypatch.setattr("time.sleep", lambda _s: None)  # no real backoff waits


# ----------------------------------------------------------------- success and caching


def test_success_records_tokens_and_caches(tmp_path) -> None:
    client = _client(tmp_path, [_Response("Objection, hearsay.")])
    assert client.complete("sys", "prompt") == "Objection, hearsay."
    assert client.usage.calls == 1
    assert client.usage.input_tokens == 11 and client.usage.output_tokens == 7
    assert client.usage.fallbacks == 0

    # second identical request is served from memory, with no further SDK call
    assert client.complete("sys", "prompt") == "Objection, hearsay."
    assert client._client.models.calls == 1
    assert client.usage.cache_hits == 1


def test_cache_hit_from_disk_needs_no_sdk_at_all(tmp_path) -> None:
    path = tmp_path / "responses.json"
    probe = LLMClient(cache_path=path)
    key = cache_key("prompt", "sys", probe.model, probe.temperature, probe.max_tokens)
    path.write_text(json.dumps({key: "from disk"}), encoding="utf-8")

    client = LLMClient(cache_path=path)  # no _client injected: touching the SDK would fail
    assert client.complete("sys", "prompt") == "from disk"
    assert client.usage.cache_hits == 1 and client.usage.calls == 0


def test_save_round_trips_the_cache(tmp_path) -> None:
    client = _client(tmp_path, [_Response("line")])
    client.complete("sys", "prompt")
    client.save()
    assert LLMClient(cache_path=tmp_path / "responses.json").complete("sys", "prompt") == "line"


# ----------------------------------------------------------------- 429: transient vs daily


def test_transient_429_retries_then_succeeds(tmp_path) -> None:
    client = _client(tmp_path, [_client_error(429, "RESOURCE_EXHAUSTED per minute"), _Response("ok")])
    assert client.complete("sys", "prompt") == "ok"
    assert client._client.models.calls == 2
    assert client.usage.rate_limited == 0 and client.usage.calls == 1


def test_transient_429_gives_up_after_the_retry_cap_and_falls_back(tmp_path) -> None:
    outcomes = [_client_error(429, "RESOURCE_EXHAUSTED per minute")] * 10
    client = _client(tmp_path, outcomes)
    assert client.complete("sys", "prompt") is None
    assert client.usage.rate_limited == 1
    assert client.usage.fallbacks == 1
    assert client._client.models.calls == 4  # the initial attempt plus three retries, then stop


def test_daily_quota_raises_and_is_not_counted_as_a_fallback(tmp_path) -> None:
    """A daily cap is an outage, not a model failure, and must not be retried."""
    client = _client(
        tmp_path,
        [_client_error(429, "RESOURCE_EXHAUSTED: Quota exceeded for generate_requests_per_day")],
    )
    with pytest.raises(QuotaExhausted):
        client.complete("sys", "prompt")
    assert client.usage.quota_stops == 1
    assert client.usage.fallbacks == 0, "a quota stop must not be blamed on the model"
    assert client.usage.rate_limited == 0
    assert client._client.models.calls == 1, "a daily cap must not be retried"


@pytest.mark.parametrize(
    "message",
    ["Quota exceeded: requests per day", "limit: PerDay", "exceeded your daily limit", "generate_requests_per_day"],
)
def test_daily_quota_phrasings_are_recognised(tmp_path, message: str) -> None:
    client = _client(tmp_path, [_client_error(429, message)])
    with pytest.raises(QuotaExhausted):
        client.complete("sys", "prompt")


# ----------------------------------------------------------------- blocked and malformed


def test_safety_block_counts_as_a_fallback(tmp_path) -> None:
    client = _client(tmp_path, [_Response("", finish_reason="SAFETY")])
    assert client.complete("sys", "prompt") is None
    assert client.usage.blocked == 1 and client.usage.calls == 0


def test_empty_response_counts_as_blocked(tmp_path) -> None:
    client = _client(tmp_path, [_Response("")])
    assert client.complete("sys", "prompt") is None
    assert client.usage.blocked == 1


def test_server_error_retries_then_counts_as_an_error(tmp_path) -> None:
    boom = errors.ServerError.__new__(errors.ServerError)
    Exception.__init__(boom, "503 UNAVAILABLE")
    client = _client(tmp_path, [boom] * 10)
    assert client.complete("sys", "prompt") is None
    assert client.usage.errors == 1


def test_choose_rejects_an_out_of_range_index_as_malformed(tmp_path) -> None:
    client = _client(tmp_path, [_Response(json.dumps({"choice": 9}))])
    assert client.choose("sys", "prompt", n_options=3) is None
    assert client.usage.malformed == 1


def test_choose_rejects_unparseable_output_as_malformed(tmp_path) -> None:
    client = _client(tmp_path, [_Response("I would object, your Honour.")])
    assert client.choose("sys", "prompt", n_options=3) is None
    assert client.usage.malformed == 1


def test_choose_accepts_a_valid_structured_answer(tmp_path) -> None:
    client = _client(tmp_path, [_Response(json.dumps({"choice": 2}))])
    assert client.choose("sys", "prompt", n_options=3) == 2
    assert client.usage.malformed == 0


def test_action_choice_schema_round_trips() -> None:
    assert ActionChoice.model_validate_json('{"choice": 4}').choice == 4


# ----------------------------------------------------------------- caps and key handling


def test_no_key_means_no_sdk_call(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = _client(tmp_path, [_Response("never reached")])
    assert client.complete("sys", "prompt") is None
    assert client.usage.refusals == 1
    assert client._client.models.calls == 0


def test_per_run_call_ceiling_stops_further_calls(tmp_path) -> None:
    """The ceiling is an explicit instance setting, so a harness cannot hit it by accident."""
    client = _client(tmp_path, [_Response("one"), _Response("two")], max_calls_per_run=1)
    assert client.complete("sys", "a") == "one"
    assert client.complete("sys", "b") is None
    assert client.usage.refusals == 1


def test_the_api_key_is_never_written_to_the_cache(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-value")
    client = _client(tmp_path, [_Response("line")])
    client.complete("sys", "prompt")
    client.save()
    assert "super-secret-value" not in (tmp_path / "responses.json").read_text(encoding="utf-8")


def test_usage_separates_cache_hits_from_real_calls(tmp_path) -> None:
    """The report must never present a cached replay as fresh model output."""
    client = _client(tmp_path, [_Response("a"), _Response("b")])
    client.complete("sys", "one")
    client.complete("sys", "two")
    client.complete("sys", "one")
    snapshot = client.usage.as_dict()
    assert snapshot["calls"] == 2
    assert snapshot["cache_hits"] == 1
    assert snapshot["fallbacks"] == 0


# ----------------------------------------------------------------- the exhibition write-up


def _results_fixture(**overrides) -> dict:
    base = {
        "kind": "exhibition",
        "case_id": "helix-espionage",
        "model": "gemini-3.1-flash-lite",
        "temperature": 0.0,
        "seeds": [0, 1],
        "opponents": ["aggressive", "conservative"],
        "aborted": None,
        "resumable": False,
        "resume_hint": None,
        "completed_trials": ["prosecution|aggressive|0"],
        "api_calls_this_run": 1,
        "decisions": 10,
        "llm_chosen": 8,
        "overall_fallback_rate": 0.2,
        "usage": {
            "calls": 8, "cache_hits": 3, "fallbacks": 2, "unavailable": 0, "rate_limited": 1,
            "blocked": 0, "malformed": 1, "errors": 0, "fallback_rate": 0.2,
            "input_tokens": 1234, "output_tokens": 56, "quota_stops": 0, "estimated_cost": 0.0,
        },
        "cells": [{
            "llm_side": "prosecution", "opponent": "aggressive", "trials": 1, "llm_win_rate": 1.0,
            "mean_llm_payoff": 1.5, "mean_opponent_payoff": -1.5, "mean_llm_budget_spent": 3.0,
            "decisions": 10, "llm_chosen": 8, "fallback_rate": 0.2, "reprompts": 1,
            "fallback_reasons": {"malformed": 1},
        }],
    }
    base.update(overrides)
    return base


def _render(tmp_path, payload: dict) -> str:
    from courtroom.llm.report import render

    src = tmp_path / "r.json"
    src.write_text(json.dumps(payload), encoding="utf-8")
    return render(src, tmp_path / "OUT.md")


def test_the_writeup_cannot_invent_numbers(tmp_path) -> None:
    """Every figure in LLM_EXHIBITION.md is read from the results file, never typed in."""
    text = _render(tmp_path, _results_fixture())
    for expected in ("gemini-3.1-flash-lite", "1,234", "56", "20.0%", "+1.50", "-1.50"):
        assert expected in text, f"the write-up dropped {expected!r} from the results file"


def test_the_writeup_always_says_it_is_not_equilibrium_analysis(tmp_path) -> None:
    text = _render(tmp_path, _results_fixture())
    lowered = text.lower()
    assert "not equilibrium analysis" in lowered
    assert "best-response verifier" in lowered
    assert "cache miss" in lowered


def test_the_writeup_separates_cache_hits_from_real_calls(tmp_path) -> None:
    """And is explicit that a cache replay reporting 0 calls was not free to produce."""
    text = _render(tmp_path, _results_fixture(cached_responses_total=137))
    assert "Real API calls **in this run** | **8**" in text
    assert "Cache hits (no call made) | 3" in text
    assert "Distinct responses in the committed cache | 137" in text
    assert "Read the call count carefully" in text
    assert "cold-cache reproduction would cost about" in text


def test_the_writeup_reports_a_quota_stop_as_resumable_not_as_a_fallback(tmp_path) -> None:
    payload = _results_fixture(
        aborted="Gemini daily quota exhausted.",
        resumable=True,
        resume_hint="Rerun the identical command.",
    )
    payload["usage"] = {**payload["usage"], "quota_stops": 1}
    text = _render(tmp_path, payload)
    assert "Stopped early" in text and "Resumable" in text
    assert "Daily-quota stops | 1" in text
    assert "is **not** a fallback" in text


def test_the_writeup_explains_why_the_illegal_action_rate_is_structural(tmp_path) -> None:
    text = _render(tmp_path, _results_fixture())
    assert "Structurally impossible" in text
    assert "index into that list" in text


# ----------------------------------------------------------------- quota must not reach the engine


def test_quota_exhaustion_never_escapes_into_the_engine(tmp_path) -> None:
    """A daily cap must stop the run, not become a silent procedural violation.

    The engine wraps every ``agent.act()`` in ``except Exception`` and turns a raise into a
    V-AGENT-FAULT. When QuotaExhausted escaped into that barrier the run carried on, the outage
    was invisible, ``resumable`` stayed false, and the affected cells reported a fabricated
    100% fallback rate with no reasons recorded. This pins the fix.
    """
    import random

    from courtroom.agents import make_agent
    from courtroom.cases import CASES
    from courtroom.engine.trial import Court
    from courtroom.llm.policy import LLMAgent

    class AlwaysOutOfQuota(LLMClient):
        def choose(self, system: str, prompt: str, n_options: int) -> int | None:
            raise QuotaExhausted("daily cap gone")

    case = CASES["helix-espionage"]
    agent = LLMAgent(client=AlwaysOutOfQuota(cache_path=tmp_path / "c.json"), rng=random.Random("0"))
    result = Court(case, agent, make_agent("conservative", random.Random("0:d")), 0, "llm", "conservative").run()

    assert agent.quota_exhausted is True
    assert agent.quota_decisions > 0
    # the trial still completed legally rather than collapsing into violations
    assert result.verdict is not None
    assert result.ledgers[Side.PROSECUTION].violations == 0, "quota leaked into the engine as a violation"
    # and an outage is not counted against the model
    assert agent.fallback_rate == 0.0
    assert agent.choices + agent.quota_decisions + agent.trivial_decisions == agent.decisions


def test_every_decision_is_accounted_for(tmp_path, monkeypatch) -> None:
    """Counters must partition the decisions exactly; a gap means an outcome is going unrecorded."""
    import random

    from courtroom.agents import make_agent
    from courtroom.cases import CASES
    from courtroom.engine.trial import Court
    from courtroom.llm.policy import LLMAgent

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    case = CASES["helix-espionage"]
    for side in ("prosecution", "defense"):
        agent = LLMAgent(client=LLMClient(cache_path=tmp_path / "c.json"), rng=random.Random("0"))
        other = make_agent("conservative", random.Random("0:d"))
        p, d = (agent, other) if side == "prosecution" else (other, agent)
        Court(case, p, d, 0, "a", "b").run()
        accounted = (
            agent.llm_decisions
            + agent.trivial_decisions
            + agent.quota_decisions
            + sum(agent.fallback_reasons.values())
        )
        assert accounted == agent.decisions, (
            f"{side}: {agent.decisions} decisions but only {accounted} accounted for"
        )
