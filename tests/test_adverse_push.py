"""Adverse events pushed in by the examiner mid-trial (DEVIATIONS D15).

The behaviour that matters: a push is forced, not drawn; it is announced in the hash chain and so known to
both sides; the Adaptive profile changes its later choices because of that announcement and the other
profiles do not; and a replay from the recorded inputs is bit-identical.
"""

from __future__ import annotations

import itertools

import pytest

from courtroom.cases import ADVERSE_CASES, CASES
from courtroom.contracts import AdversePush, EventKind
from courtroom.engine import push_reaction, replay_trial, run_trial
from courtroom.engine.audit import verify_chain

HELIX = CASES["helix-espionage"]


def _offers(trial, item_id: str) -> bool:
    return any(e.action and e.action.type.value == "present_evidence" and e.action.evidence_id == item_id for e in trial.events)


# ----------------------------------------------------------------------- validation and fences


def test_no_push_leaves_every_trial_exactly_as_it_was() -> None:
    for p, d in itertools.product(("aggressive", "adaptive"), repeat=2):
        assert run_trial(HELIX, p, d, seed=1).digest == run_trial(HELIX, p, d, seed=1, adverse_pushes=[]).digest


@pytest.mark.parametrize(
    "push",
    [
        AdversePush(at_seq=1, kind="no_show", target="NOPE"),
        AdversePush(at_seq=1, kind="no_show", target="P-VPN"),  # a log has no witness to fail to appear
        AdversePush(at_seq=1, kind="missing_certificate", target="P-NANDA"),  # testimony is not an electronic record
        AdversePush(at_seq=1, kind="hostile", target="P-VPN"),  # an exhibit id, not a witness id
    ],
)
def test_a_push_naming_something_that_cannot_be_affected_is_refused_up_front(push: AdversePush) -> None:
    with pytest.raises(ValueError, match="adverse push"):
        run_trial(HELIX, "aggressive", "conservative", adverse_pushes=[push])


# ----------------------------------------------------------------------- what a push does


def test_a_pushed_certificate_failure_is_announced_then_excludes_the_exhibit_when_offered() -> None:
    push = AdversePush(at_seq=1, kind="missing_certificate", target="P-VPN")
    t = run_trial(HELIX, "aggressive", "aggressive", seed=0, adverse_pushes=[push])
    kinds = [(e.status, e.rules[0].rule_id) for e in t.events if e.kind is EventKind.ADVERSE]
    assert ("announced", "ADV-4") in kinds and ("no_certificate", "ADV-2") in kinds
    assert next(e for e in t.events if e.status == "no_certificate").rules[0].detail.count("pushed by the examiner") == 1
    assert not any(e.status == "admitted" and e.subject == "P-VPN" for e in t.events)
    assert verify_chain(t.events) and t.adverse_pushes == (push,)


def test_pushes_work_on_a_certified_case_with_no_flag_and_draw_no_randomness() -> None:
    assert not HELIX.adverse_events
    plain = run_trial(HELIX, "adaptive", "adaptive", seed=4)
    pushed = run_trial(HELIX, "adaptive", "adaptive", seed=4, adverse_pushes=[AdversePush(at_seq=3, kind="no_show", target="P-NANDA")])
    assert pushed.digest != plain.digest
    assert any(e.status == "announced" for e in pushed.events)


def test_a_push_on_an_exhibit_already_offered_is_refused_not_ignored() -> None:
    t = run_trial(HELIX, "aggressive", "aggressive", seed=0, adverse_pushes=[AdversePush(at_seq=12, kind="missing_certificate", target="P-VPN")])
    refused = [e for e in t.events if e.status == "not_applied"]
    assert refused and refused[0].rules[0].rule_id == "ADV-5" and "already been offered" in refused[0].rules[0].detail


def test_a_push_the_trial_never_reaches_is_recorded_and_reported() -> None:
    push = AdversePush(at_seq=9000, kind="hostile", target="W-NANDA")
    t = run_trial(HELIX, "aggressive", "aggressive", seed=0, adverse_pushes=[push])
    assert t.adverse_pushes == (push,)
    assert any(e.status == "not_applied" and "left the evidence phases" in e.rules[0].detail for e in t.events)


def test_a_witness_who_has_testified_turns_hostile_at_once_and_it_costs_the_side_that_called_them() -> None:
    base = run_trial(HELIX, "aggressive", "aggressive", seed=0)
    first = next(e for e in base.events if e.status == "admitted" and HELIX.item(e.subject).witness_id == "W-NANDA")
    push = AdversePush(at_seq=first.seq + 2, kind="hostile", target="W-NANDA")
    t = run_trial(HELIX, "aggressive", "aggressive", seed=0, adverse_pushes=[push])
    hostile = next(e for e in t.events if e.status == "hostile")
    assert hostile.rules[0].rule_id == "ADV-3" and "pushed by the examiner" in hostile.rules[0].detail
    before = [e for e in t.events if e.seq < hostile.seq and e.element_probabilities][-1]
    assert hostile.element_probabilities["intent"] < before.element_probabilities["intent"]


def test_a_defense_witness_cannot_be_made_hostile_after_the_directed_verdict_review() -> None:
    """It would raise the prosecution after the point where the review is sound, so the engine refuses it."""
    base = run_trial(HELIX, "aggressive", "aggressive", seed=0)
    dv = next(e.seq for e in base.events if e.kind is EventKind.DIRECTED_VERDICT)
    assert any(e.seq < dv and e.status == "admitted" and e.subject == "D-SPOUSE" for e in base.events), "fixture drifted"
    t = run_trial(HELIX, "aggressive", "aggressive", seed=0, adverse_pushes=[AdversePush(at_seq=dv + 2, kind="hostile", target="W-VANCE-SPOUSE")])
    assert not any(e.status == "hostile" for e in t.events)
    refused = next(e for e in t.events if e.status == "not_applied")
    assert "directed-verdict review" in refused.rules[0].detail
    # The same push before the review is allowed: it only hurts the defense.
    early = run_trial(HELIX, "aggressive", "aggressive", seed=0, adverse_pushes=[AdversePush(at_seq=dv - 4, kind="hostile", target="W-VANCE-SPOUSE")])
    assert any(e.status in ("hostile", "announced") for e in early.events)


# ----------------------------------------------------------------------- strategies react, from beliefs


def test_adaptive_drops_an_announced_failure_and_aggressive_walks_into_it() -> None:
    push = AdversePush(at_seq=1, kind="missing_certificate", target="P-VPN")
    base = {s: run_trial(HELIX, s, s, seed=0) for s in ("adaptive", "aggressive")}
    pushed = {s: run_trial(HELIX, s, s, seed=0, adverse_pushes=[push]) for s in ("adaptive", "aggressive")}
    assert _offers(base["adaptive"], "P-VPN") and _offers(base["aggressive"], "P-VPN")
    assert not _offers(pushed["adaptive"], "P-VPN"), "Adaptive should not pay to offer an exhibit it was told will fail"
    assert _offers(pushed["aggressive"], "P-VPN") and any(e.status == "no_certificate" for e in pushed["aggressive"].events)


def test_the_reaction_report_names_the_changed_decision_and_the_belief_behind_it() -> None:
    push = AdversePush(at_seq=1, kind="missing_certificate", target="P-VPN")
    before = run_trial(HELIX, "adaptive", "adaptive", seed=0)
    after = run_trial(HELIX, "adaptive", "adaptive", seed=0, adverse_pushes=[push])
    r = push_reaction(before, after, push, HELIX)
    pros = r["sides"][0]
    assert r["applied"] and r["announced_at_step"] == 3
    assert pros["reacted"] and pros["before"]["evidence_id"] == "P-VPN" and pros["after"]["evidence_id"] != "P-VPN"
    assert "expected survival is 0.00" in pros["belief"]
    # The sides that do not change are reported as unchanged, not invented.
    aggressive = push_reaction(
        run_trial(HELIX, "aggressive", "aggressive", seed=0),
        run_trial(HELIX, "aggressive", "aggressive", seed=0, adverse_pushes=[push]),
        push,
        HELIX,
    )
    assert aggressive["sides"][0]["belief"] is None


def test_adaptive_records_the_survival_it_believed_in_its_own_rationale() -> None:
    """With published rates the expected-value lawyer logs the survival it priced in, so the belief is on the record."""
    seen = []
    for seed in range(3):
        t = run_trial(ADVERSE_CASES["helix-espionage-adverse"], "adaptive", "adaptive", seed=seed)
        seen += [e.action.rationale for e in t.events if e.action and "expected survival" in e.action.rationale]
    assert seen
    for r in seen:
        value = float(r.split("expected survival ")[1].split(",")[0].split(" ")[0])
        assert 0.0 < value < 1.0, r


def test_a_hostile_announcement_makes_adaptive_stop_offering_that_witness() -> None:
    """Told a witness may turn hostile, the expected-value lawyer prices testimony at a quarter and drops it."""
    base = run_trial(HELIX, "adaptive", "adaptive", seed=0)
    pushed = run_trial(HELIX, "adaptive", "adaptive", seed=0, adverse_pushes=[AdversePush(at_seq=1, kind="hostile", target="W-NANDA")])
    assert _offers(base, "P-NANDA") and not _offers(pushed, "P-NANDA")
    aggressive = run_trial(HELIX, "aggressive", "aggressive", seed=0, adverse_pushes=[AdversePush(at_seq=1, kind="hostile", target="W-NANDA")])
    assert _offers(aggressive, "P-NANDA")


def test_the_agents_only_see_the_public_announcement() -> None:
    """Armed state stays in the court; agents get ``known_adverse`` strings and nothing else."""
    from courtroom.contracts import PartyView

    assert "known_adverse" in PartyView.model_fields
    assert not any(f in PartyView.model_fields for f in ("armed_no_show", "armed_certificate", "armed_hostile"))


# ----------------------------------------------------------------------- determinism


@pytest.mark.parametrize("pairing", list(itertools.product(("aggressive", "conservative", "adaptive"), repeat=2)))
def test_pushed_trials_replay_bit_for_bit(pairing: tuple[str, str]) -> None:
    pushes = [
        AdversePush(at_seq=2, kind="no_show", target="P-NANDA"),
        AdversePush(at_seq=5, kind="missing_certificate", target="P-DLP"),
        AdversePush(at_seq=9, kind="hostile", target="W-HR"),
    ]
    for case in (HELIX, ADVERSE_CASES["helix-espionage-adverse"]):
        for seed in (0, 1):
            first = run_trial(case, *pairing, seed=seed, adverse_pushes=pushes)
            again = replay_trial(first, case)
            assert first.digest == again.digest and [e.hash for e in first.events] == [e.hash for e in again.events]
            assert first.adverse_pushes == tuple(sorted(pushes, key=lambda p: (p.at_seq, p.kind, p.target)))
            assert verify_chain(first.events)


def test_a_push_never_raises_the_prosecution_after_the_directed_verdict_review() -> None:
    for p, d in itertools.product(("aggressive", "conservative", "adaptive"), repeat=2):
        for target, kind in (("W-HR", "hostile"), ("W-VANCE-SPOUSE", "hostile"), ("P-DLP", "missing_certificate")):
            t = run_trial(HELIX, p, d, seed=3, adverse_pushes=[AdversePush(at_seq=4, kind=kind, target=target)])
            dv = next((i for i, e in enumerate(t.events) if e.kind is EventKind.DIRECTED_VERDICT), None)
            if dv is None:
                continue
            for a, b in itertools.pairwise(t.events[dv:]):
                if b.phase.value == "rebuttal" or not a.element_probabilities or not b.element_probabilities:
                    continue
                for element, value in b.element_probabilities.items():
                    assert value <= a.element_probabilities[element] + 1e-9


# ----------------------------------------------------------------------- the API


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from courtroom.api.server import create_app

    return TestClient(create_app())


def test_the_api_returns_the_trial_and_what_changed(client) -> None:
    body = {"case_id": "helix-espionage", "prosecution": "adaptive", "defense": "adaptive", "seed": 0,
            "adverse_pushes": [{"at_seq": 1, "kind": "missing_certificate", "target": "P-VPN"}]}
    r = client.post("/api/adverse", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["trial"]["adverse_pushes"] == body["adverse_pushes"]
    assert data["reaction"]["sides"][0]["reacted"] and "P-VPN" in data["reaction"]["sides"][0]["belief"]


def test_the_api_refuses_an_empty_push_and_a_bad_target(client) -> None:
    assert client.post("/api/adverse", json={"case_id": "helix-espionage"}).status_code == 422
    bad = {"case_id": "helix-espionage", "adverse_pushes": [{"at_seq": 1, "kind": "no_show", "target": "P-VPN"}]}
    assert client.post("/api/adverse", json=bad).status_code == 422
    assert client.post("/api/trial", json={**bad, "adverse_pushes": [{"at_seq": 1, "kind": "bogus", "target": "x"}]}).status_code == 422
