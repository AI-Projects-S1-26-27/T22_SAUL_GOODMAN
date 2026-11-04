"""Seeded adverse events (DEVIATIONS D15): no-show, missing 65B certificate, hostile witness.

What must hold: with the flag off nothing changes; with it on every event is drawn from a seeded stream,
logged in the hash chain, and replays bit for bit; the judge still reads only the record; and the events can
never raise the prosecution after the directed-verdict review.
"""

from __future__ import annotations

import ast
import itertools
import random
from fractions import Fraction
from pathlib import Path

import pytest

from courtroom.agents import ChaosAgent
from courtroom.cases import CASES, PLAIN_CASES
from courtroom.cases.events import EVENT_CASES, SHIPPED_RULES
from courtroom.contracts import EventKind, EvidenceKind, Phase, RuleSet
from courtroom.engine import Court, replay_trial, run_trial
from courtroom.engine.audit import verify_chain
from courtroom.judge.rules import HOSTILE_FACTOR, hostile_key
from courtroom.judge.scoring import score_record
from courtroom.llm.narrator import SPOKEN_KINDS, narrate

STRATEGIES = ("aggressive", "conservative", "adaptive")
# The cases that ship with events on, keyed by their ordinary ids.
ADVERSE_CASES = {cid: CASES[cid] for cid in sorted(EVENT_CASES)}
HELIX = ADVERSE_CASES["helix-espionage"]


def _adverse(trial) -> list:
    return [e for e in trial.events if e.kind is EventKind.ADVERSE]


# ----------------------------------------------------------------------- the fence


def test_the_plain_library_never_has_adverse_events_and_the_shipped_one_has_exactly_the_calibrated_ones() -> None:
    assert all(c.rules is None for c in PLAIN_CASES.values())
    assert {cid for cid, c in CASES.items() if c.adverse_events} == set(EVENT_CASES)
    assert all(CASES[cid].rules == SHIPPED_RULES for cid in EVENT_CASES)
    for case in PLAIN_CASES.values():
        for p, d in itertools.product(STRATEGIES, repeat=2):
            assert not _adverse(run_trial(case, p, d, seed=0))


def test_ruleset_defaults_to_no_adverse_events() -> None:
    rules = RuleSet()
    assert rules.adverse_events is False and rules.witnesses is False


def test_every_rate_at_zero_reproduces_the_plain_trial_exactly() -> None:
    """The adverse stream is separate: enabling the flag with nothing able to fire must not move a digest."""
    for cid, case in ADVERSE_CASES.items():
        base = PLAIN_CASES[cid]
        quiet = base.model_copy(update={"rules": RuleSet(adverse_events=True, no_show=0.0, missing_certificate=0.0, hostile=0.0)})
        for p, d in (("aggressive", "conservative"), ("adaptive", "adaptive")):
            assert run_trial(quiet, p, d, seed=3).digest == run_trial(base, p, d, seed=3).digest
        assert CASES[cid] is case


# ----------------------------------------------------------------------- determinism


@pytest.mark.parametrize("case_id", sorted(ADVERSE_CASES))
@pytest.mark.parametrize("pairing", list(itertools.product(STRATEGIES, STRATEGIES)))
def test_adverse_trials_replay_bit_for_bit(case_id: str, pairing: tuple[str, str]) -> None:
    case = ADVERSE_CASES[case_id]
    for seed in (0, 1, 2):
        first = run_trial(case, *pairing, seed=seed)
        second = replay_trial(first, case)
        assert first.digest == second.digest
        assert [e.hash for e in first.events] == [e.hash for e in second.events]
        assert verify_chain(first.events)


def test_different_seeds_give_different_adverse_histories() -> None:
    histories = {tuple((e.seq, e.status) for e in _adverse(run_trial(HELIX, "aggressive", "aggressive", seed=s))) for s in range(15)}
    assert len(histories) > 3


# ----------------------------------------------------------------------- the events themselves


def _collect(case, n: int = 40):
    out = []
    for p, d in itertools.product(STRATEGIES, repeat=2):
        for s in range(n // 9 + 1):
            out.append(run_trial(case, p, d, seed=s))
    return out


def test_every_kind_of_event_happens_and_is_logged_with_its_rule() -> None:
    seen: dict[str, str] = {}
    for case in ADVERSE_CASES.values():
        for trial in _collect(case):
            for e in _adverse(trial):
                assert e.rules, "an adverse event must carry its rule firing"
                seen[e.status] = e.rules[0].rule_id
    assert seen == {"no_show": "ADV-1", "no_certificate": "ADV-2", "hostile": "ADV-3"}


def test_a_failed_offer_is_excluded_not_pending_and_still_costs_the_turn() -> None:
    for trial in _collect(HELIX):
        for e in _adverse(trial):
            if e.status in ("no_show", "no_certificate"):
                assert e.action is not None and e.actor is not None and e.subject == e.action.evidence_id
                following = [x for x in trial.events if x.seq > e.seq]
                assert not any(x.status == "admitted" and x.subject == e.subject for x in following)
                ledger = trial.ledgers[e.actor]
                assert ledger.excluded >= 1 and ledger.spent > 0


def test_certificates_only_ever_fail_for_digital_records_and_no_shows_only_for_witnesses() -> None:
    for case in ADVERSE_CASES.values():
        for trial in _collect(case):
            for e in _adverse(trial):
                if e.status == "no_certificate":
                    assert case.item(e.subject).kind is EvidenceKind.DIGITAL_LOG
                if e.status == "no_show":
                    assert case.item(e.subject).witness_id is not None


def test_a_witness_turns_hostile_at_most_once_and_only_after_testifying() -> None:
    for case in ADVERSE_CASES.values():
        for trial in _collect(case):
            hostile = [e.subject for e in _adverse(trial) if e.status == "hostile"]
            assert len(hostile) == len(set(hostile))
            for e in _adverse(trial):
                if e.status == "hostile":
                    earlier = [x for x in trial.events if x.seq < e.seq and x.status == "admitted"]
                    assert any(case.item(x.subject).witness_id == e.subject for x in earlier)


def test_hostility_is_an_exact_quarter_of_credibility_and_changes_nothing_else() -> None:
    base = score_record(HELIX, ["P-NANDA"]).log_odds["intent"]
    hit = score_record(HELIX, ["P-NANDA"], {hostile_key("W-NANDA"): 1}).log_odds["intent"]
    prior = Fraction(-1)
    assert Fraction(1, 4) == HOSTILE_FACTOR
    assert (hit - prior) == (base - prior) * Fraction(1, 4)
    assert score_record(HELIX, ["P-NANDA"], {hostile_key("W-NANDA"): 0}).log_odds["intent"] == base


def test_observed_rates_match_the_published_ones() -> None:
    """500 offers of a testimony item: the no-show frequency should sit near 10%."""
    case = HELIX
    shows = offers = 0
    for seed in range(250):
        t = run_trial(case, "aggressive", "aggressive", seed=seed)
        for e in t.events:
            if e.action is not None and e.action.type.value == "present_evidence" and e.kind in (EventKind.ACTION, EventKind.ADVERSE):
                item = case.item(e.action.evidence_id)
                if item.witness_id is not None and e.status in ("offered", "no_show"):
                    offers += 1
                    shows += e.status == "no_show"
    assert offers > 150
    assert 0.04 < shows / offers < 0.18, (shows, offers)


@pytest.mark.parametrize("case_id", sorted(ADVERSE_CASES))
def test_no_adverse_event_can_raise_the_prosecution_after_the_directed_verdict_review(case_id: str) -> None:
    case = ADVERSE_CASES[case_id]
    for p, d in itertools.product(STRATEGIES, repeat=2):
        for seed in range(6):
            result = run_trial(case, p, d, seed=seed)
            dv = next((i for i, e in enumerate(result.events) if e.kind is EventKind.DIRECTED_VERDICT), None)
            if dv is None:
                continue
            for earlier, later in itertools.pairwise(result.events[dv:]):
                if later.phase is Phase.REBUTTAL or not earlier.element_probabilities or not later.element_probabilities:
                    continue
                for element, value in later.element_probabilities.items():
                    assert value <= earlier.element_probabilities[element] + 1e-9, (case_id, p, d, seed, later.seq)


def test_the_chaos_agent_survives_adverse_events() -> None:
    for case in ADVERSE_CASES.values():
        for seed in range(6):
            result = Court(case, ChaosAgent(random.Random(seed)), ChaosAgent(random.Random(seed + 7)), seed=seed).run()
            assert verify_chain(result.events) and result.events[-1].kind is EventKind.VERDICT


# ----------------------------------------------------------------------- agents


def test_only_the_adaptive_profile_discounts_for_the_published_risk() -> None:
    """With the same seed, Adaptive's choices differ between the adverse and plain versions of a case; the
    certified case gives it an empty ``adverse`` view, so its behaviour there is untouched (golden digests)."""
    differs = 0
    for cid, case in ADVERSE_CASES.items():
        base = PLAIN_CASES[cid]
        quiet = base.model_copy(update={"rules": RuleSet(adverse_events=True, no_show=0.0, missing_certificate=0.0, hostile=0.0)})
        a = run_trial(case, "adaptive", "adaptive", seed=0)
        b = run_trial(quiet, "adaptive", "adaptive", seed=0)
        differs += a.digest != b.digest
    assert differs >= 1


# ----------------------------------------------------------------------- language model boundary


def test_narration_of_adverse_events_never_changes_the_trial() -> None:
    from courtroom.llm.client import LLMClient

    class Says(LLMClient):
        def complete(self, system: str, prompt: str) -> str:
            self.usage.calls += 1
            return "Your Honour, we are disappointed."

    trial = next(t for t in _collect(HELIX) if _adverse(t))
    before = trial.digest
    lines = narrate(trial, HELIX, Says())
    assert EventKind.ADVERSE in SPOKEN_KINDS and lines
    assert run_trial(HELIX, trial.prosecution_strategy, trial.defense_strategy, trial.seed).digest == before


def test_no_core_package_imports_the_language_model_layer() -> None:
    root = Path(__file__).resolve().parents[1] / "courtroom"
    for package in ("contracts", "judge", "procedure", "agents", "engine", "cases", "gametheory"):
        for path in (root / package).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                assert not any(n == "courtroom.llm" or n.startswith("courtroom.llm.") for n in names), (path, names)


# ----------------------------------------------------------------------- the hostile credibility factor is a per-case parameter


def test_the_hostile_credibility_factor_is_read_from_the_case_and_stays_exact() -> None:
    marks = {hostile_key("W-NANDA"): 1}
    prior = Fraction(-1)
    base = score_record(HELIX, ["P-NANDA"]).log_odds["intent"]
    for text, factor in (("1/4", Fraction(1, 4)), ("1/2", Fraction(1, 2)), ("1/8", Fraction(1, 8)), ("0", Fraction(0))):
        case = HELIX.model_copy(update={"rules": RuleSet(adverse_events=True, hostile_credibility=text)})
        hit = score_record(case, ["P-NANDA"], marks).log_odds["intent"]
        assert (hit - prior) == (base - prior) * factor, text


@pytest.mark.parametrize("bad", ["2", "3/2", "x", "-1/2", "1/0"])
def test_a_factor_outside_zero_to_one_is_refused(bad: str) -> None:
    with pytest.raises(ValueError):
        RuleSet(adverse_events=True, hostile_credibility=bad)


def test_the_default_factor_leaves_every_events_trial_byte_identical_to_before() -> None:
    """1/4 is the value that was hard-coded; making it a field must not move a digest."""
    explicit = HELIX.model_copy(update={"rules": RuleSet(adverse_events=True, hostile_credibility="1/4")})
    for p, d in (("aggressive", "conservative"), ("adaptive", "adaptive")):
        assert run_trial(explicit, p, d, seed=2).digest == run_trial(HELIX, p, d, seed=2).digest


def test_adaptive_prices_a_harsher_hostile_witness_lower() -> None:
    mild = HELIX.model_copy(update={"rules": RuleSet(adverse_events=True, hostile=0.6, hostile_credibility="3/4")})
    harsh = HELIX.model_copy(update={"rules": RuleSet(adverse_events=True, hostile=0.6, hostile_credibility="0")})
    seen = {}
    for name, case in (("mild", mild), ("harsh", harsh)):
        t = run_trial(case, "adaptive", "adaptive", seed=0)
        seen[name] = [e.action.rationale for e in t.events if e.action and "expected survival" in e.action.rationale]
    assert seen["mild"] and seen["harsh"] and seen["mild"] != seen["harsh"]
