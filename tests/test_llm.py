"""The optional LLM layer: isolation from the judge, caching, caps and fallback.

The point of every test here is the same: prove the LLM cannot reach the certified core.
"""

from __future__ import annotations

import json

import pytest

from courtroom.cases import CASES
from courtroom.contracts import Side
from courtroom.engine import run_trial
from courtroom.llm import LLMClient, cache_key, narrate
from courtroom.llm.narrator import SPOKEN_KINDS, _prompt, _public_item, _template

CASE = CASES["helix-espionage"]

# Fields of an exhibit the opponent is only ever allowed to *guess* at.
HIDDEN_FLAGS = ("hearsay", "authenticated", "lawfully_obtained", "disclosed", "personal_knowledge")


class AlwaysAnswers(LLMClient):
    """A client that always returns text, so tests exercise the with-LLM path without a key."""

    def complete(self, system: str, prompt: str) -> str:
        self.usage.calls += 1
        return "Your Honour, the record speaks for itself on this point."


# ----------------------------------------------------------------- isolation from the judge


def test_verdict_is_byte_identical_with_and_without_argument_text() -> None:
    """The hard constraint: generated text cannot move a verdict.

    Narration runs over a finished TrialResult, so this holds by construction. The test exists
    so that if anyone ever threads the narrator into the trial loop, the suite stops them.
    """
    plain = run_trial(CASE, "aggressive", "conservative", seed=0)
    lines = narrate(plain, CASE, AlwaysAnswers())
    after = run_trial(CASE, "aggressive", "conservative", seed=0)

    assert lines, "the narrator produced nothing, so this test would pass vacuously"
    assert plain.verdict.model_dump_json() == after.verdict.model_dump_json()
    assert plain.digest == after.digest
    assert plain.model_dump_json() == after.model_dump_json()


def test_narration_is_not_stored_on_the_trial_record() -> None:
    """Narration is returned beside the result, never written into it."""
    result = run_trial(CASE, "aggressive", "conservative", seed=0)
    before = result.model_dump_json()
    narrate(result, CASE, AlwaysAnswers())
    assert result.model_dump_json() == before


def test_engine_and_judge_do_not_import_the_llm_package() -> None:
    """The dependency arrow only ever points one way."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent / "courtroom"
    offenders = [
        path.relative_to(root).as_posix()
        for sub in ("engine", "judge", "procedure", "gametheory", "agents", "cases", "contracts")
        for path in (root / sub).rglob("*.py")
        if "courtroom.llm" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, f"the certified core must not import the LLM layer: {offenders}"


# ----------------------------------------------------------------- information isolation


def test_public_item_description_carries_no_latent_defect() -> None:
    """The exhibit projection a prompt may see is public attributes only."""
    for item in CASE.evidence:
        described = _public_item(CASE, item.id).lower()
        assert described
        for flag in HIDDEN_FLAGS:
            assert flag not in described, f"{item.id}: public description leaks {flag!r} -> {described}"
        for value in ("true", "false"):
            assert value not in described


def test_narrator_prompt_leaks_no_latent_defect() -> None:
    """A prompt may carry the public record and nothing more.

    One subtlety this test has to respect: an objection *ground* is spoken aloud in court, so
    a prompt for a decided OBJECT move legitimately contains e.g. "hearsay". That is the move
    being performed, not a disclosure of the exhibit's hidden flags. So the check is that a
    defect word appears nowhere except on the line naming the decided ground.
    """
    result = run_trial(CASE, "aggressive", "conservative", seed=0)
    prompts = [
        _prompt(CASE, ev, [])
        for ev in result.events
        if ev.action is not None and ev.actor is not None and ev.kind in SPOKEN_KINDS
    ]
    assert prompts
    for prompt in prompts:
        for line in prompt.splitlines():
            if line.startswith("Ground of objection:"):
                continue  # the move itself, said out loud in court
            lowered = line.lower()
            for flag in HIDDEN_FLAGS:
                assert flag not in lowered, f"prompt leaks the hidden flag {flag!r}:\n{prompt}"


def test_narrator_prompt_never_names_an_unoffered_exhibit() -> None:
    """The speaker may discuss what is on the record and the exhibit in its own hand, nothing else."""
    result = run_trial(CASE, "aggressive", "conservative", seed=0)
    offered: set[str] = set()
    for event in result.events:
        if event.action is None or event.actor is None or event.kind not in SPOKEN_KINDS:
            continue
        prompt = _prompt(CASE, event, [])
        allowed = offered | ({event.action.evidence_id} if event.action.evidence_id else set())
        named = {item.id for item in CASE.evidence if item.id in prompt}
        assert named <= allowed, f"prompt names exhibits not yet on the record: {named - allowed}"
        if event.status == "offered" and event.action.evidence_id:
            offered.add(event.action.evidence_id)


# ----------------------------------------------------------------- cache, caps, fallback


def test_cache_key_covers_every_input_that_changes_the_output() -> None:
    base = dict(prompt="p", system="s", model="m", temperature=0.0, max_tokens=10)
    key = cache_key(**base)
    assert key == cache_key(**base)  # stable
    for field, other in (
        ("prompt", "p2"), ("system", "s2"), ("model", "m2"), ("temperature", 0.7), ("max_tokens", 11)
    ):
        assert cache_key(**{**base, field: other}) != key, f"{field} must change the cache key"


def test_a_cache_hit_needs_no_key_and_no_network(tmp_path) -> None:
    path = tmp_path / "responses.json"
    client = LLMClient(cache_path=path, allow_network=False)
    key = cache_key("prompt", "system", client.model, client.temperature, client.max_tokens)
    path.write_text(json.dumps({key: "cached line"}), encoding="utf-8")

    client = LLMClient(cache_path=path, allow_network=False)
    assert client.complete("system", "prompt") == "cached line"
    assert client.usage.cache_hits == 1
    assert client.usage.calls == 0


def test_without_a_key_complete_returns_none_so_the_caller_falls_back(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = LLMClient(cache_path=tmp_path / "none.json")
    assert client.complete("system", "unseen prompt") is None
    assert client.usage.refusals == 1


def test_narration_falls_back_to_templates_and_still_reads_as_argument(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = run_trial(CASE, "aggressive", "conservative", seed=0)
    lines = narrate(result, CASE, LLMClient(cache_path=tmp_path / "none.json"))
    assert len(lines) > 10
    assert all(line and line[0].isupper() and line.endswith((".", "!", "?")) for line in lines.values())
    assert any("Objection" in line for line in lines.values())


def test_narration_works_with_no_client_at_all() -> None:
    result = run_trial(CASE, "aggressive", "conservative", seed=0)
    assert len(narrate(result, CASE, None)) > 10


def test_per_trial_call_ceiling_is_enforced(tmp_path, monkeypatch) -> None:
    from courtroom.llm import client as client_module

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-real-key")
    monkeypatch.setattr(client_module, "MAX_CALLS_PER_TRIAL", 0)
    client = LLMClient(cache_path=tmp_path / "none.json")
    client.start_trial()
    assert client.complete("system", "prompt") is None
    assert client.usage.calls == 0
    assert client.usage.refusals == 1


def test_cost_estimate_uses_the_configured_rate(monkeypatch) -> None:
    monkeypatch.setenv("COURTROOM_LLM_RATES", "2.0,10.0")
    client = LLMClient()
    client.usage.input_tokens = 1_000_000
    client.usage.output_tokens = 1_000_000
    assert client.usage.cost_estimate() == pytest.approx(12.0)


def test_every_action_type_has_a_template() -> None:
    """No move may fall through to an empty line in front of an examiner."""
    seen = set()
    for strategies in (("aggressive", "conservative"), ("chaos", "adaptive")):
        for seed in range(6):
            result = run_trial(CASE, *strategies, seed=seed)
            for event in result.events:
                if event.action is None or event.actor is None or event.kind not in SPOKEN_KINDS:
                    continue
                seen.add(event.action.type)
                assert _template(CASE, event).strip(), f"no template for {event.action.type}"
    assert len(seen) >= 4, f"too few action types exercised to be meaningful: {seen}"


def test_narration_covers_both_sides() -> None:
    result = run_trial(CASE, "aggressive", "conservative", seed=0)
    lines = narrate(result, CASE, None)
    actors = {result.events[seq].actor for seq in lines}
    assert actors == set(Side)


# ----------------------------------------------------------------- policy information isolation


def _views_from_a_trial(side: Side) -> list:
    """Every PartyView the given side was actually asked to act on, with its Oracle."""
    import random

    from courtroom.agents import Oracle, ScoreCache, make_agent
    from courtroom.engine.trial import Court

    captured: list = []

    class Spy:
        name = "spy"

        def __init__(self, inner) -> None:
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
    assert captured, "the spy never got a turn"
    assert Oracle and ScoreCache  # imported for the same surface the policy uses
    return captured


def test_llm_policy_reads_the_noisy_posterior_not_the_truth() -> None:
    """The policy must see an exhibit's flaws only through the same noisy channel as everyone else.

    A ground's *name* legitimately appears in a prompt twice over: as an available objection
    move, and as a belief percentage. Neither is a leak. The leak would be reading the true
    boolean off the case file, so this asserts the number shown is exactly the view's posterior
    and that those posteriors are genuinely uncertain rather than the ground truth in disguise.
    """
    from courtroom.judge.admissibility import ground_is_valid
    from courtroom.llm.policy import build_prompt, legal_actions

    saw_a_pending_item = False
    disagreed_with_truth = False
    for side in Side:
        for view, oracle in _views_from_a_trial(side):
            prompt = build_prompt(view, oracle, legal_actions(view))
            if view.pending is None:
                continue
            saw_a_pending_item = True
            item = CASE.item(view.pending.evidence_id)
            for ground, posterior in view.pending.defect_belief.items():
                if posterior <= 0:
                    continue
                shown = f"{str(ground.value).replace('_', ' ')} {posterior:.0%}"
                assert shown in prompt, f"prompt shows a belief that is not the view's posterior: {shown}"
                truth = ground_is_valid(item, ground, CASE.case_type)
                if (posterior > 0.5) != truth:
                    disagreed_with_truth = True
            assert "true" not in prompt.lower().split("available moves")[0]
    assert saw_a_pending_item, "no response window occurred, so this test would pass vacuously"
    assert disagreed_with_truth, "every posterior matched the truth: the channel is not actually noisy"


def test_llm_policy_prompt_names_no_exhibit_it_cannot_see() -> None:
    """The opponent's unplayed hand must never reach a prompt."""
    from courtroom.llm.policy import build_prompt, legal_actions

    for side in Side:
        for view, oracle in _views_from_a_trial(side):
            prompt = build_prompt(view, oracle, legal_actions(view))
            own = {item.id for item in view.own_evidence}
            public = set(view.presented) | set(view.admitted) | set(view.excluded)
            pending = {view.pending.evidence_id} if view.pending else set()
            named = {item.id for item in CASE.evidence if item.id in prompt}
            assert named <= own | public | pending, f"prompt names exhibits it cannot see: {named - (own | public | pending)}"


def test_llm_policy_only_ever_offers_legal_actions() -> None:
    """Legality is structural: the model picks an index into a list the validator accepts."""
    import random

    from courtroom.agents import Oracle, ScoreCache, make_agent
    from courtroom.engine.trial import Court
    from courtroom.llm.policy import legal_actions
    from courtroom.procedure import ProcedureState, validate

    checked = 0

    class Spy:
        name = "spy"

        def __init__(self, inner, state_box) -> None:
            self.inner = inner
            self.state_box = state_box

        def opening_statement(self, s):
            return self.inner.opening_statement(s)

        def act(self, view, oracle):
            nonlocal checked
            state = self.state_box[0]
            for action in legal_actions(view):
                assert validate(action, state, view.side, view.window) is None, (
                    f"policy offered an action the validator rejects: {action.type} in {view.window}"
                )
                checked += 1
            return self.inner.act(view, oracle)

    for strategies in (("aggressive", "conservative"), ("conservative", "adaptive")):
        box: list[ProcedureState] = [None]  # type: ignore[list-item]
        spy = Spy(make_agent(strategies[0], random.Random("0:a")), box)
        court = Court(CASE, spy, make_agent(strategies[1], random.Random("0:b")), 0, "spy", strategies[1])
        box[0] = court.state
        court.run()
    assert checked > 20, f"too few actions checked to be meaningful: {checked}"
    assert Oracle and ScoreCache
