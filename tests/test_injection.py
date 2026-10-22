"""Live evidence injection: logged in the hash chain, replay-identical, never mid-objection."""

from __future__ import annotations

import pytest

from courtroom.cases import CASES
from courtroom.contracts import EventKind, EvidenceItem, EvidenceKind, Injection, Side
from courtroom.engine import replay_trial, run_trial, verify_chain, verify_injections
from courtroom.engine.audit import chain, digest_item

HELIX = CASES["helix-espionage"]
PAIR = ("aggressive", "conservative")


def exhibit(case=HELIX, owner: Side = Side.PROSECUTION, ident: str = "X-NEW", support: float = 0.9, **kw) -> EvidenceItem:
    element = case.elements[0].id
    return EvidenceItem(
        id=ident,
        title="Newly recovered drive image",
        description="Found after the trial began.",
        kind=EvidenceKind.DOCUMENT,
        owner=owner,
        fact_id=f"fact-{ident}",
        support={element: support if owner is Side.PROSECUTION else -support},
        reliability=0.95,
        **kw,
    )


def inject(at_seq: int, item: EvidenceItem | None = None) -> Injection:
    return Injection(at_seq=at_seq, item=item or exhibit())


# ----------------------------------------------------------------- the default path is untouched


def test_a_trial_without_injections_records_none() -> None:
    result = run_trial(HELIX, *PAIR, seed=0)
    assert result.injections == ()
    assert not [e for e in result.events if e.kind is EventKind.INJECTION]
    assert verify_injections(result)


# ----------------------------------------------------------------- replay identity


def test_an_injected_trial_replays_to_the_same_verdict_and_digest() -> None:
    first = run_trial(HELIX, *PAIR, seed=3, injections=[inject(6)])
    again = run_trial(HELIX, *PAIR, seed=3, injections=[inject(6)])
    assert first.digest == again.digest
    assert first.verdict.model_dump_json() == again.verdict.model_dump_json()
    assert first.model_dump_json() == again.model_dump_json()


def test_a_finished_trial_replays_from_nothing_but_its_own_record() -> None:
    """The result carries what it needs: re-running from it reproduces verdict and digest."""
    original = run_trial(HELIX, *PAIR, seed=2, injections=[inject(8)])
    assert len(original.injections) == 1
    replayed = replay_trial(original, HELIX)
    assert replayed.digest == original.digest
    assert replayed.verdict.outcome == original.verdict.outcome
    assert replayed.verdict.model_dump_json() == original.verdict.model_dump_json()


def test_injecting_changes_the_trial_but_only_from_the_injection_onward() -> None:
    base = run_trial(HELIX, *PAIR, seed=0)
    hit = run_trial(HELIX, *PAIR, seed=0, injections=[inject(10)])
    at = next(e.seq for e in hit.events if e.kind is EventKind.INJECTION)
    assert [e.hash for e in hit.events[:at]] == [e.hash for e in base.events[:at]], "events before the injection changed"
    assert hit.digest != base.digest


# ----------------------------------------------------------------- the hash chain commits to it


def test_the_injection_is_one_event_in_the_chain_that_names_the_exhibit_by_hash() -> None:
    item = exhibit()
    result = run_trial(HELIX, *PAIR, seed=1, injections=[inject(6, item)])
    events = [e for e in result.events if e.kind is EventKind.INJECTION]
    assert len(events) == 1
    ev = events[0]
    assert ev.subject == "X-NEW" and ev.status == "injected" and ev.actor is None
    assert [r.rule_id for r in ev.rules] == ["INJ-1"]
    assert digest_item(item) in ev.rules[0].detail
    assert verify_chain(result.events)


def test_tampering_with_the_logged_injection_breaks_the_chain() -> None:
    result = run_trial(HELIX, *PAIR, seed=1, injections=[inject(6)])
    idx = next(i for i, e in enumerate(result.events) if e.kind is EventKind.INJECTION)
    forged = list(result.events)
    forged[idx] = forged[idx].model_copy(update={"summary": "New evidence enters the defense's hand."})
    assert not verify_chain(forged)


def test_editing_the_exhibit_after_the_fact_is_detected() -> None:
    """The exhibit is not in the event, only its hash is, so the check has to compare the two."""
    result = run_trial(HELIX, *PAIR, seed=1, injections=[inject(6)])
    assert verify_injections(result)
    doctored = Injection(at_seq=result.injections[0].at_seq, item=result.injections[0].item.model_copy(update={"reliability": 0.1}))
    assert not verify_injections(result.model_copy(update={"injections": (doctored,)}))
    assert not verify_injections(result.model_copy(update={"injections": ()}))


def test_a_rechained_forgery_still_fails_the_exhibit_check() -> None:
    """Rewriting the logged hash and re-chaining keeps verify_chain happy, but not the exhibit check."""
    result = run_trial(HELIX, *PAIR, seed=1, injections=[inject(6)])
    idx = next(i for i, e in enumerate(result.events) if e.kind is EventKind.INJECTION)
    rewritten = result.events[idx].model_copy(update={"rules": ()})
    events = list(result.events)
    prev = events[idx - 1].hash
    events[idx] = chain(rewritten, prev)
    for j in range(idx + 1, len(events)):
        events[j] = chain(events[j].model_copy(update={"prev_hash": "", "hash": ""}), events[j - 1].hash)
    assert verify_chain(events)
    assert not verify_injections(result.model_copy(update={"events": tuple(events)}))


# ----------------------------------------------------------------- it does something, safely


def test_the_owner_can_present_what_was_injected() -> None:
    result = run_trial(HELIX, *PAIR, seed=0, injections=[inject(1)])
    offered = [e for e in result.events if e.action and e.action.evidence_id == "X-NEW"]
    assert offered, "an aggressive prosecution never offered the new exhibit"
    assert any(n.id == "X-NEW" for n in result.graph.nodes)


def test_an_injection_never_lands_inside_a_response_window() -> None:
    base = run_trial(HELIX, *PAIR, seed=0)
    offered = next(e for e in base.events if e.status == "offered")
    result = run_trial(HELIX, *PAIR, seed=0, injections=[inject(offered.seq + 1)])
    at = next(i for i, e in enumerate(result.events) if e.kind is EventKind.INJECTION)
    assert result.events[at - 1].status != "offered", "the exhibit arrived while an objection was pending"
    assert at > offered.seq + 1, "it should have waited for the response to be ruled on"


def test_an_injection_point_after_the_evidence_phases_is_reported_not_dropped() -> None:
    result = run_trial(HELIX, *PAIR, seed=0, injections=[inject(9000)])
    assert not [e for e in result.events if e.kind is EventKind.INJECTION]
    missed = [e for e in result.events if any(r.rule_id == "INJ-2" for r in e.rules)]
    assert len(missed) == 1 and missed[0].subject == "X-NEW"
    assert verify_chain(result.events) and verify_injections(result)


def test_a_late_injection_is_still_an_input_so_the_replay_must_include_it() -> None:
    """It never landed, but it shaped the trial (an INJ-2 event), so the result must carry it.

    The first version of the engine recorded only applied injections, and replaying such a result
    silently dropped an input: the digests diverged on any trial that ended before the injection
    point. The empty-docket and defense-only cases found it.
    """
    late = run_trial(HELIX, *PAIR, seed=0, injections=[inject(9000)])
    assert len(late.injections) == 1
    assert replay_trial(late, HELIX).digest == late.digest
    base = run_trial(HELIX, *PAIR, seed=0)
    assert late.digest != base.digest, "the INJ-2 event is part of the chain, so it must change the digest"
    doctored = Injection(at_seq=9000, item=late.injections[0].item.model_copy(update={"reliability": 0.2}))
    assert not verify_injections(late.model_copy(update={"injections": (doctored,)}))


def test_injection_order_follows_the_point_not_the_argument_order() -> None:
    a, b = inject(4, exhibit(ident="X-A")), inject(9, exhibit(ident="X-B", support=0.4))
    assert run_trial(HELIX, *PAIR, seed=0, injections=[a, b]).digest == run_trial(HELIX, *PAIR, seed=0, injections=[b, a]).digest


# ----------------------------------------------------------------- bad exhibits are refused up front


def test_a_duplicate_exhibit_id_is_refused_before_the_trial_starts() -> None:
    with pytest.raises(ValueError, match="does not fit this case"):
        run_trial(HELIX, *PAIR, seed=0, injections=[inject(3, exhibit(ident="P-LAPTOP"))])


def test_an_exhibit_that_supports_an_unknown_point_is_refused() -> None:
    bad = exhibit().model_copy(update={"support": {"not-a-point": 0.5}})
    with pytest.raises(ValueError, match="does not fit this case"):
        run_trial(HELIX, *PAIR, seed=0, injections=[inject(3, bad)])


def test_an_exhibit_that_contradicts_something_absent_is_refused() -> None:
    bad = exhibit().model_copy(update={"contradicts": ("NOPE",)})
    with pytest.raises(ValueError, match="does not fit this case"):
        run_trial(HELIX, *PAIR, seed=0, injections=[inject(3, bad)])


def test_defense_evidence_that_helps_the_prosecution_cannot_be_injected() -> None:
    """Otherwise injection would reopen the hole the directed-verdict review depends on being shut."""
    bad = exhibit(owner=Side.DEFENSE).model_copy(update={"support": {HELIX.elements[0].id: 0.5}})
    with pytest.raises(ValueError, match="a defense exhibit may only help the defense"):
        run_trial(HELIX, *PAIR, seed=0, injections=[inject(3, bad)])
    # the mirror image is allowed: it is merely a foolish thing for the prosecution to introduce
    foolish = exhibit(owner=Side.PROSECUTION, support=-0.5)
    assert run_trial(HELIX, *PAIR, seed=0, injections=[inject(3, foolish)]).verdict is not None


def test_a_later_exhibit_may_contradict_an_earlier_injected_one() -> None:
    first = inject(3, exhibit(ident="X-A"))
    second = inject(7, exhibit(ident="X-B", owner=Side.DEFENSE).model_copy(update={"contradicts": ("X-A",)}))
    result = run_trial(HELIX, *PAIR, seed=0, injections=[first, second])
    assert {i.item.id for i in result.injections} <= {"X-A", "X-B"}
    assert verify_chain(result.events)


# ----------------------------------------------------------------- it cannot break the engine


@pytest.mark.parametrize("case_id", list(CASES))
def test_injection_keeps_every_invariant_across_the_library(case_id: str) -> None:
    case = CASES[case_id]
    for owner in Side:
        for seed in (0, 1, 2):
            for pair in (("aggressive", "conservative"), ("adaptive", "chaos")):
                injections = [inject(4, exhibit(case, owner))]
                result = run_trial(case, *pair, seed=seed, injections=injections)
                assert verify_chain(result.events)
                assert verify_injections(result)
                assert all(ledger.budget >= 0 for ledger in result.ledgers.values())
                assert result.verdict is not None
                assert replay_trial(result, case).digest == result.digest


# ----------------------------------------------------------------- the command line


def _write(tmp_path, injections: list[Injection]) -> str:
    path = tmp_path / "inject.json"
    path.write_text("[" + ",".join(i.model_dump_json() for i in injections) + "]", encoding="utf-8")
    return str(path)


def test_verify_proves_an_injected_trial_replays_bit_identically(tmp_path, capsys) -> None:
    from courtroom.cli import main

    code = main(["verify", "--case", "helix-espionage", "-p", "aggressive", "-d", "conservative", "--seed", "2", "--inject", _write(tmp_path, [inject(8)])])
    out = capsys.readouterr().out
    assert code == 0
    assert "bit-identical results: YES" in out
    assert "replays from its own record: YES" in out
    assert "exhibits match the chain: YES" in out


def test_verify_still_works_with_no_injection_file(capsys) -> None:
    from courtroom.cli import main

    assert main(["verify", "--case", "helix-espionage"]) == 0
    assert "replays from its own record" not in capsys.readouterr().out


def test_run_and_verify_refuse_an_exhibit_that_does_not_fit(tmp_path) -> None:
    from courtroom.cli import main

    bad = _write(tmp_path, [inject(3, exhibit(ident="P-LAPTOP"))])
    assert main(["verify", "--case", "helix-espionage", "--inject", bad]) == 2
    assert main(["run", "--case", "helix-espionage", "--inject", bad]) == 2
