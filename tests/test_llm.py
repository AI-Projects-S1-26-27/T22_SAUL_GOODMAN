"""W2: the language-model layer. Everything is stubbed. The point of the isolation tests is that the model cannot reach the core."""

from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from courtroom.agents import Oracle, ScoreCache, make_agent
from courtroom.cases import CASES
from courtroom.contracts import Side
from courtroom.engine import run_trial, run_with_agents
from courtroom.engine.trial import Court
from courtroom.judge.admissibility import ground_is_valid
from courtroom.llm import GeminiBackend, LLMClient, OllamaBackend, cache_key, configured_backends
from courtroom.llm.backends import BackendError
from courtroom.llm.policy import LLMAgent, build_prompt, legal_actions
from courtroom.procedure import validate
from tests.llm_stub import Stub, stub_client

CASE = CASES["helix-espionage"]
CORE = ("engine", "judge", "procedure", "gametheory", "agents", "cases", "contracts")


# ----------------------------------------------------------------- the core never imports the model layer


def test_core_modules_do_not_mention_the_llm_package():
    root = Path(__file__).resolve().parent.parent / "courtroom"
    offenders = [p.relative_to(root).as_posix() for sub in CORE for p in (root / sub).rglob("*.py") if "courtroom.llm" in p.read_text(encoding="utf-8")]
    assert not offenders, offenders


def test_loading_the_core_loads_no_model_code():
    code = "import courtroom.engine, courtroom.agents, courtroom.gametheory, courtroom.judge, courtroom.cases, sys; assert not [m for m in sys.modules if m.startswith('courtroom.llm')]"
    assert subprocess.run([sys.executable, "-c", code], capture_output=True).returncode == 0


def test_registering_the_ai_lawyer_changes_no_other_trial():
    before = run_trial(CASE, "adaptive", "aggressive", 4).digest
    import courtroom.llm.register  # noqa: F401  (registering is the whole point)

    assert run_trial(CASE, "adaptive", "aggressive", 4).digest == before


# ----------------------------------------------------------------- the AI lawyer


def _play(client: LLMClient, seed: int = 0, side: Side = Side.PROSECUTION):
    agent = LLMAgent(client, random.Random(f"{seed}:llm"))
    other = make_agent("conservative", random.Random(f"{seed}:o"))
    p, d = (agent, other) if side is Side.PROSECUTION else (other, agent)
    return agent, run_with_agents(CASE, p, d, seed, prosecution_name="llm", defense_name="conservative")


def test_the_ai_lawyer_plays_a_whole_trial_and_shows_a_reason_per_move(tmp_path):
    client, stub = stub_client(tmp_path)
    agent, result = _play(client)
    assert result.events[-1].kind.value == "verdict" and stub.chats
    reasons = [e.action.rationale for e in result.events if e.action and e.actor is Side.PROSECUTION and e.action.rationale.startswith("[ai] ")]
    assert reasons and all("It helps my side." in r for r in reasons)
    assert agent.report()["model_choices"] == agent.llm_decisions > 0


def test_a_model_that_answers_nonsense_falls_back_to_adaptive_and_counts_it(tmp_path):
    client, _ = stub_client(tmp_path, Stub(lambda body: "I would rather not say"))
    agent, result = _play(client)
    assert result.events[-1].kind.value == "verdict"  # the trial still finishes, legally
    assert agent.llm_decisions == 0 and agent.fallback_rate == 1.0 and agent.fallback_reasons["malformed"] > 0
    assert agent.reprompts > 0  # it was asked again before giving up


def test_an_out_of_range_index_is_malformed_not_a_silent_zero(tmp_path):
    client, _ = stub_client(tmp_path, Stub(lambda body: json.dumps({"choice": 99, "reason": "x"})))
    assert client.choose("s", "p", 3) is None and client.usage.malformed == 1


def test_no_backend_means_a_clean_fallback_and_the_trial_still_runs(tmp_path):
    client = LLMClient(backends=[], cache_path=tmp_path / "c.json")
    agent, result = _play(client)
    assert result.events[-1].kind.value == "verdict" and agent.fallback_rate == 1.0


def test_a_cached_run_replays_exactly_with_no_backend_at_all(tmp_path):
    live, _ = stub_client(tmp_path)
    _, first = _play(live)
    live.save()
    offline = LLMClient(backends=[], cache_path=tmp_path / "cache.json")  # a different machine: no key, no Ollama
    agent, second = _play(offline)
    assert second.digest == first.digest and agent.fallback_rate == 0.0 and offline.usage.calls == 0


def test_the_judge_decides_the_same_whatever_the_model_says(tmp_path):
    """The model picks moves; the verdict for a given record is the rulebook's. Same record, same verdict."""
    from courtroom.judge.tipping import prosecution_wins, record_of

    _, result = _play(stub_client(tmp_path)[0])
    assert prosecution_wins(CASE, record_of(result)) == (result.verdict.outcome.favours is Side.PROSECUTION)


# ----------------------------------------------------------------- the prompt sees no more than the view


def _views(side: Side) -> list:
    captured: list = []

    class Spy:
        name = "spy"

        def __init__(self, inner):
            self.inner = inner

        def opening_statement(self, s):
            return self.inner.opening_statement(s)

        def act(self, view, oracle):
            captured.append((view, oracle))
            return self.inner.act(view, oracle)

    spy = Spy(make_agent("adaptive", random.Random("0:spy")))
    other = make_agent("aggressive", random.Random("0:other"))
    p, d = (spy, other) if side is Side.PROSECUTION else (other, spy)
    Court(CASE, p, d, 0, "spy", "aggressive").run()
    assert captured and Oracle and ScoreCache
    return captured


def test_the_prompt_shows_the_noisy_posterior_never_the_truth():
    seen_pending = disagreed = False
    for side in Side:
        for view, oracle in _views(side):
            prompt = build_prompt(view, oracle, legal_actions(view))
            if view.pending is None:
                continue
            seen_pending = True
            item = CASE.item(view.pending.evidence_id)
            for ground, posterior in view.pending.defect_belief.items():
                if posterior <= 0:
                    continue
                assert f"{str(ground.value).replace('_', ' ')} {posterior:.0%}" in prompt
                if (posterior > 0.5) != ground_is_valid(item, ground, CASE.case_type):
                    disagreed = True
    assert seen_pending and disagreed, "this test would pass vacuously, or the channel is not noisy"


def test_the_prompt_names_no_exhibit_the_lawyer_cannot_see():
    for side in Side:
        for view, oracle in _views(side):
            prompt = build_prompt(view, oracle, legal_actions(view))
            allowed = {i.id for i in view.own_evidence} | set(view.presented) | set(view.admitted) | set(view.excluded)
            allowed |= {view.pending.evidence_id} if view.pending else set()
            assert {i.id for i in CASE.evidence if i.id in prompt} <= allowed


def test_the_ai_lawyer_is_only_ever_offered_legal_moves():
    checked = 0

    class Spy:
        name = "spy"

        def __init__(self, inner, box):
            self.inner, self.box = inner, box

        def opening_statement(self, s):
            return self.inner.opening_statement(s)

        def act(self, view, oracle):
            nonlocal checked
            for action in legal_actions(view):
                assert validate(action, self.box[0], view.side, view.window) is None
                checked += 1
            return self.inner.act(view, oracle)

    for a, b in (("aggressive", "conservative"), ("conservative", "adaptive")):
        box: list = [None]
        court = Court(CASE, Spy(make_agent(a, random.Random("0:a")), box), make_agent(b, random.Random("0:b")), 0, "spy", b)
        box[0] = court.state
        court.run()
    assert checked > 20


# ----------------------------------------------------------------- the client


def test_the_cache_key_covers_everything_that_changes_the_answer():
    base = cache_key("s", "p", "m", 0.0, 100, "")
    assert len({base, cache_key("S", "p", "m", 0.0, 100, ""), cache_key("s", "P", "m", 0.0, 100, ""), cache_key("s", "p", "M", 0.0, 100, ""),
                cache_key("s", "p", "m", 0.5, 100, ""), cache_key("s", "p", "m", 0.0, 101, ""), cache_key("s", "p", "m", 0.0, 100, "X")}) == 7


def test_a_second_identical_call_is_answered_from_the_cache(tmp_path):
    client, stub = stub_client(tmp_path)
    a, b = client.complete("sys", "prompt"), client.complete("sys", "prompt")
    assert a == b and len(stub.chats) == 1 and client.usage.cache_hits == 1


def test_backends_are_tried_cloud_then_local_then_gemini(tmp_path, monkeypatch):
    for k in ("OLLAMA_API_KEY", "GEMINI_API_KEY", "OLLAMA_LOCAL_MODEL"):
        monkeypatch.delenv(k, raising=False)
    assert [b.name for b in configured_backends()] == ["local"]
    monkeypatch.setenv("OLLAMA_API_KEY", "k1")
    monkeypatch.setenv("GEMINI_API_KEY", "k2")
    assert [b.name for b in configured_backends()] == ["cloud", "local", "gemini"]


def test_a_failing_backend_falls_through_to_the_next(tmp_path):
    calls: list[str] = []

    def transport(url, body, headers, timeout):
        calls.append(url)
        if "cloud.example" in url:
            raise BackendError("HTTP 500: down")
        if url.endswith("/api/tags"):
            return {"models": [{"name": "m"}]}
        return {"message": {"content": "hello"}}

    cloud = OllamaBackend("cloud", "http://cloud.example", "big", "KEY", transport)
    cloud.probe = lambda: True  # type: ignore[method-assign]  (it answers the probe, then fails the real call)
    local = OllamaBackend("local", "http://local.example", "m", None, transport)
    client = LLMClient(backends=[cloud, local], cache_path=tmp_path / "c.json")
    assert client.complete("s", "p") == "hello" and client.last_source == "local"


def test_gemini_request_shape_and_the_key_goes_only_in_a_header():
    sent: dict = {}

    def transport(url, body, headers, timeout):
        sent.update(url=url, body=body, headers=headers)
        return {"candidates": [{"content": {"parts": [{"text": "hi"}]}}]}

    g = GeminiBackend("SECRET-KEY", "gemini-x", transport=transport)
    assert g.chat("system", "prompt", temperature=0.0, max_tokens=50, schema=None) == "hi"
    assert "SECRET-KEY" not in sent["url"] and sent["headers"]["x-goog-api-key"] == "SECRET-KEY"
    assert sent["body"]["generationConfig"]["temperature"] == 0.0


def test_a_key_never_appears_in_a_backend_error(monkeypatch):
    import urllib.request

    def boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    cloud = OllamaBackend("cloud", "http://x", "m", "TOP-SECRET")
    with pytest.raises(BackendError) as exc:
        cloud.chat("s", "p", temperature=0.0, max_tokens=10, schema=None)
    assert "TOP-SECRET" not in str(exc.value)


def test_the_call_cap_per_run_is_enforced(tmp_path):
    client, _ = stub_client(tmp_path, max_calls_per_run=2)
    results = [client.complete("s", f"p{i}") for i in range(4)]
    assert results[:2] != [None, None] and results[2:] == [None, None] and client.usage.refusals == 2


def test_status_says_whether_a_backend_answers(tmp_path):
    client, _ = stub_client(tmp_path)
    assert client.status()["available"] is True and client.status()["backend"] == "local"
    assert LLMClient(backends=[], cache_path=tmp_path / "x.json").status()["available"] is False


def test_saving_the_cache_from_many_threads_at_once_is_safe(tmp_path):
    import threading

    client, _ = stub_client(tmp_path)
    for i in range(6):
        client.complete("s", f"p{i}")
    errors: list[Exception] = []

    def go():
        try:
            for _ in range(30):
                client._dirty = True
                client.save()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors and json.loads((tmp_path / "cache.json").read_text())["entries"]
    assert not list(tmp_path.glob("*.tmp"))


def test_a_cache_that_cannot_be_written_does_not_break_the_caller(tmp_path):
    client, _ = stub_client(tmp_path)
    client.complete("s", "p")
    client.cache_path = tmp_path / "missing" / "deeper" / "c.json"
    (tmp_path / "missing").write_text("a file where a folder should be")
    client.save()  # must not raise
    assert client.last_error and "could not save" in client.last_error
