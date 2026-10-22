"""Ollama behind the same client interface as Gemini. Everything here is stubbed: no test touches a network."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from courtroom.cases import CASES
from courtroom.contracts import Side
from courtroom.engine import run_trial
from courtroom.llm import ActionChoice, LLMClient, OllamaClient, cache_key, make_client, narrate, provider_name
from courtroom.llm.bundle import replay_exhibition
from courtroom.llm.client import CACHE_PATH
from courtroom.llm.exhibition import build_court, run_exhibition
from courtroom.llm.ollama import DEFAULT_OLLAMA_MODEL, OLLAMA_CACHE_PATH


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any attempt to open a real connection fails loudly as an unreachable server."""

    def blocked(*args: object, **kwargs: object) -> None:
        raise urllib.error.URLError("network blocked by the test suite")

    monkeypatch.setattr(urllib.request, "urlopen", blocked)


class Stub:
    """A fake Ollama server. Records every request; answers from ``reply``."""

    def __init__(self, models: tuple[str, ...] = ("qwen3:8b",), reply=None) -> None:
        self.models, self.requests, self.reply = models, [], reply or (lambda payload: {"choice": 0})

    def __call__(self, path: str, payload: dict | None, timeout: float) -> dict:
        self.requests.append((path, payload))
        if path == "/api/tags":
            return {"models": [{"name": m} for m in self.models]}
        out = self.reply(payload)
        content = out if isinstance(out, str) else json.dumps(out)
        return {"message": {"role": "assistant", "content": content}, "prompt_eval_count": 120, "eval_count": 9}

    @property
    def chats(self) -> list[dict]:
        return [p for path, p in self.requests if path == "/api/chat"]


def _client(tmp_path: Path, stub: Stub | None = None, **kw) -> tuple[OllamaClient, Stub]:
    stub = stub or Stub()
    return OllamaClient(cache_path=tmp_path / "ollama.json", transport=stub, **kw), stub


# ----------------------------------------------------------------------- identity and the cache


def test_the_two_providers_can_never_share_a_cache_entry(tmp_path: Path) -> None:
    ollama, _ = _client(tmp_path)
    gemini = LLMClient(cache_path=tmp_path / "g.json")
    args = ("p", "s", 0.0, 160)
    assert cache_key(args[0], args[1], ollama.cache_model, *args[2:]) != cache_key(args[0], args[1], gemini.cache_model, *args[2:])
    assert ollama.cache_model == f"ollama/{DEFAULT_OLLAMA_MODEL}" and gemini.cache_model == gemini.model


def test_the_committed_gemini_cache_and_its_keys_are_untouched() -> None:
    assert OLLAMA_CACHE_PATH != CACHE_PATH and OLLAMA_CACHE_PATH.name == "responses.ollama.json"
    c = LLMClient(allow_network=False)
    assert c.cache_model == c.model and c.provider_tag == "gemini"
    assert c.usage.provider == "Gemini" and not c.usage.free


def test_a_live_run_is_written_to_the_cache_and_replays_offline_with_no_calls(tmp_path: Path) -> None:
    live, stub = _client(tmp_path)
    assert live.complete("system", "prompt") == '{"choice": 0}'
    live.save()
    assert len(stub.chats) == 1 and live.usage.calls == 1

    def exploding(*a: object, **k: object) -> dict:
        raise AssertionError("a replay must not call the server")

    replay = OllamaClient(cache_path=tmp_path / "ollama.json", transport=exploding, allow_network=False)
    assert replay.complete("system", "prompt") == '{"choice": 0}'
    assert replay.usage.cache_hits == 1 and replay.usage.calls == 0 and replay.usage.fallbacks == 0


# ----------------------------------------------------------------------- the wire format


def test_the_request_follows_the_documented_chat_shape(tmp_path: Path) -> None:
    client, stub = _client(tmp_path, seed=7)
    client.complete("be brief", "hello")
    payload = stub.chats[0]
    assert payload["model"] == "qwen3:8b" and payload["stream"] is False and payload["think"] is False
    assert payload["messages"] == [{"role": "system", "content": "be brief"}, {"role": "user", "content": "hello"}]
    opts = payload["options"]
    assert opts["temperature"] == 0.0 and opts["seed"] == 7 and opts["num_predict"] == 160 and opts["num_ctx"] == 4096
    assert "format" not in payload


def test_a_choice_request_carries_the_json_schema_and_parses_the_index(tmp_path: Path) -> None:
    client, stub = _client(tmp_path, stub=Stub(reply=lambda p: {"choice": 2}))
    assert client.choose("s", "p", 3) == 2
    assert stub.chats[0]["format"] == ActionChoice.model_json_schema()


@pytest.mark.parametrize("answer", [{"choice": 9}, {"choice": -1}, "not json at all", {"nope": 1}])
def test_a_bad_answer_is_malformed_never_a_silent_zero(tmp_path: Path, answer: object) -> None:
    client, _ = _client(tmp_path, stub=Stub(reply=lambda p: answer))
    assert client.choose("s", "p", 3) is None and client.usage.malformed == 1


def test_a_model_that_rejects_think_is_retried_once_without_it(tmp_path: Path) -> None:
    seen: list[dict] = []

    def transport(path: str, payload: dict | None, timeout: float) -> dict:
        if path == "/api/tags":
            return {"models": [{"name": "qwen3:8b"}]}
        seen.append(payload)
        if "think" in payload:
            raise urllib.error.HTTPError("http://x", 400, "bad", {}, __import__("io").BytesIO(b'{"error":"model does not support think"}'))
        return {"message": {"content": "ok"}, "prompt_eval_count": 1, "eval_count": 1}

    client = OllamaClient(cache_path=tmp_path / "o.json", transport=transport)
    assert client.complete("s", "p") == "ok"
    assert "think" in seen[0] and "think" not in seen[1] and client._think_supported is False


# ----------------------------------------------------------------------- never fatal


def test_a_server_that_is_not_running_is_a_clean_fallback_with_the_fix_in_the_message(tmp_path: Path) -> None:
    client = OllamaClient(cache_path=tmp_path / "o.json")  # real transport, blocked by the autouse fixture
    assert client.available is False and "ollama serve" in client.last_error
    assert client.complete("s", "p") is None
    assert client.usage.refusals == 1 and client.usage.errors == 0


def test_a_model_that_is_not_pulled_says_how_to_pull_it(tmp_path: Path) -> None:
    client, _ = _client(tmp_path, stub=Stub(models=("llama3.2:3b",)))
    assert client.available is False and "ollama pull qwen3:8b" in client.last_error
    assert client.complete("s", "p") is None


def test_transport_failures_empty_answers_and_server_errors_are_counted_not_raised(tmp_path: Path) -> None:
    boom, _ = _client(tmp_path, stub=Stub(reply=lambda p: (_ for _ in ()).throw(TimeoutError("slow"))))
    assert boom.complete("s", "p") is None and boom.usage.errors == 1 and "TimeoutError" in boom.last_error
    empty, _ = _client(tmp_path, stub=Stub(reply=lambda p: "   "))
    assert empty.complete("s", "p2") is None and empty.usage.blocked == 1


def test_caps_still_apply(tmp_path: Path) -> None:
    client, stub = _client(tmp_path, max_calls_per_run=2)
    for i in range(4):
        client.complete("s", f"p{i}")
    assert client.usage.calls == 2 and client.usage.refusals == 2 and len(stub.chats) == 2


def test_it_is_free_and_says_so(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    client.complete("s", "p")
    assert client.usage.free and client.usage.cost_estimate() == 0.0
    text = client.usage.summary()
    assert text.startswith("Ollama calls: 1") and "free (runs locally)" in text
    assert client.usage.as_dict()["estimated_cost"] == 0.0 and client.usage.input_tokens == 120


# ----------------------------------------------------------------------- selection by config


def test_the_provider_is_chosen_by_environment_and_overridden_by_an_argument(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("COURTROOM_LLM_PROVIDER", raising=False)
    assert provider_name() == "gemini" and type(make_client(cache_path=tmp_path / "g.json")) is LLMClient
    monkeypatch.setenv("COURTROOM_LLM_PROVIDER", "ollama")
    assert provider_name() == "ollama" and isinstance(make_client(cache_path=tmp_path / "o.json"), OllamaClient)
    assert provider_name("gemini") == "gemini" and type(make_client("gemini", cache_path=tmp_path / "g.json")) is LLMClient
    monkeypatch.setenv("COURTROOM_LLM_PROVIDER", "carrier-pigeon")
    with pytest.raises(ValueError, match="unknown LLM provider"):
        provider_name()


def test_a_named_model_reaches_the_client(tmp_path: Path) -> None:
    c = make_client("ollama", model="qwen3:14b", cache_path=tmp_path / "o.json")
    assert c.model == "qwen3:14b" and c.cache_model == "ollama/qwen3:14b"
    assert make_client("ollama", model=None, cache_path=tmp_path / "o.json").model == DEFAULT_OLLAMA_MODEL


# ----------------------------------------------------------------------- it plays a trial, and replays it


def test_the_policy_agent_plays_a_whole_trial_on_ollama_and_replays_identically(tmp_path: Path) -> None:
    case = CASES["helix-espionage"]
    live, _stub = _client(tmp_path)
    court, agent = build_court(case, Side.PROSECUTION, "aggressive", 0, live)
    first = court.run()
    live.save()
    assert live.usage.calls > 0 and agent.llm_decisions > 0
    assert any("[ollama] chose option" in (e.action.rationale if e.action else "") for e in first.events)

    def exploding(*a: object, **k: object) -> dict:
        raise AssertionError("replay must be offline")

    replay = OllamaClient(cache_path=tmp_path / "ollama.json", transport=exploding, allow_network=False)
    court2, _ = build_court(case, Side.PROSECUTION, "aggressive", 0, replay)
    second = court2.run()
    assert first.digest == second.digest and replay.usage.calls == 0


def test_an_ollama_exhibition_reports_and_replays_with_its_label_and_provider(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    out = tmp_path / "ex.json"
    report = run_exhibition(seeds=(0,), opponents=("aggressive",), client=client, out_path=out)
    assert report["provider"] == "ollama" and report["model"] == "qwen3:8b" and out.exists()
    data = replay_exhibition(out, cache_path=tmp_path / "ollama.json")
    assert data["meta"]["provider"] == "ollama" and data["meta"]["label"].startswith("Exhibition")
    assert "not equilibrium" in data["meta"]["label"].lower() and data["trials"]


def test_the_shipped_gemini_exhibition_is_byte_for_byte_what_it_was() -> None:
    web = Path(__file__).resolve().parent.parent / "courtroom" / "viz" / "web" / "data" / "exhibition.js"
    text = web.read_text(encoding="utf-8")
    meta = json.loads(text[len("window.COURTROOM_EXHIBITION = ") :].rstrip().rstrip(";"))["meta"]
    assert "provider" not in meta and meta["model"].startswith("gemini")


def test_narration_on_ollama_never_changes_a_verdict(tmp_path: Path) -> None:
    client, _ = _client(tmp_path, stub=Stub(reply=lambda p: "Your Honour, the record speaks."))
    case = CASES["helix-espionage"]
    result = run_trial(case, "aggressive", "conservative", seed=0)
    lines = narrate(result, case, client)
    assert lines and run_trial(case, "aggressive", "conservative", seed=0).digest == result.digest


def test_exporting_an_ollama_exhibition_will_not_silently_replace_the_shipped_gemini_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil

    from courtroom import cli

    client, _ = _client(tmp_path)
    results = tmp_path / "ex.json"
    run_exhibition(seeds=(0,), opponents=("aggressive",), client=client, out_path=results)
    out = tmp_path / "data"
    out.mkdir()
    shipped = Path(__file__).resolve().parent.parent / "courtroom" / "viz" / "web" / "data" / "exhibition.js"
    shutil.copy(shipped, out / "exhibition.js")
    before = (out / "exhibition.js").read_bytes()
    # replay_exhibition reads the Ollama cache through the default path; point it at the test's cache
    monkeypatch.setattr("courtroom.llm.bundle.replay_exhibition", lambda p: replay_exhibition(p, cache_path=tmp_path / "ollama.json"))
    with pytest.raises(SystemExit, match="Pass --force"):
        cli.main(["export-exhibition", "--results", str(results), "--out", str(out)])
    assert (out / "exhibition.js").read_bytes() == before
    cli.main(["export-exhibition", "--results", str(results), "--out", str(out), "--force"])
    assert b'"provider":"ollama"' in (out / "exhibition.js").read_bytes()
