"""Courtroom surprises: off by default, seeded, exact, and visible in the record."""
from collections import Counter

from courtroom.cases import CASES
from courtroom.contracts import EventKind, Surprises
from courtroom.engine import run_trial, verify_chain
from courtroom.judge.rules import HOSTILE_FACTOR, HOSTILE_PREFIX
from courtroom.judge.scoring import credibility

ON = Surprises()


def test_default_is_the_plain_rulebook():
    plain = run_trial(CASES["helix-espionage"], "aggressive", "conservative", 0)
    assert plain.surprises is None
    assert not any(e.kind is EventKind.ADVERSE for e in plain.events)


def test_zero_rates_change_nothing_in_the_record():
    zero = Surprises(no_show=0, missing_certificate=0, hostile=0)
    for cid in ("helix-espionage", "aurora-defi"):
        a = run_trial(CASES[cid], "adaptive", "adaptive", 3)
        b = run_trial(CASES[cid], "adaptive", "adaptive", 3, surprises=zero)
        assert a.digest == b.digest


def test_surprises_are_seeded_and_replay_exactly():
    a = run_trial(CASES["helix-espionage"], "adaptive", "aggressive", 7, surprises=ON)
    b = run_trial(CASES["helix-espionage"], "adaptive", "aggressive", 7, surprises=ON)
    assert a.digest == b.digest and verify_chain(a.events)


def test_all_three_surprises_happen_and_the_seed_moves_the_record():
    seen: Counter[str] = Counter()
    digests = set()
    heavy = Surprises(no_show=0.3, missing_certificate=0.3, hostile=0.3)
    for seed in range(40):
        r = run_trial(CASES["helix-espionage"], "adaptive", "adaptive", seed, surprises=heavy)
        digests.add(r.digest)
        assert verify_chain(r.events)
        for e in r.events:
            if e.kind is EventKind.ADVERSE:
                seen[e.status] += 1
    assert set(seen) == {"no_show", "no_certificate", "hostile"}
    assert len(digests) > 10


def test_a_failed_offer_is_excluded_and_never_scored():
    only_no_show = Surprises(no_show=1, missing_certificate=0, hostile=0)
    r = run_trial(CASES["helix-espionage"], "aggressive", "aggressive", 0, surprises=only_no_show)
    failed = [e for e in r.events if e.status == "no_show"]
    assert failed
    for e in failed:
        assert next(n for n in r.graph.nodes if n.id == e.subject).status == "excluded"
        counted = {c.evidence_id for el in r.verdict.snapshot.elements for c in el.contributions}
        assert e.subject not in counted


def test_hostile_witness_keeps_a_quarter_of_their_credibility_exactly():
    case = CASES["helix-espionage"]
    item = next(i for i in case.evidence if i.witness_id)
    base = credibility(item, case, {})
    assert credibility(item, case, {HOSTILE_PREFIX + item.witness_id: 1}) == base * HOSTILE_FACTOR
