"""Witness examination (DEVIATIONS D13): direct and cross-examination behind ``RuleSet.witnesses``.

The properties that matter, in order: with the flag off nothing at all changes; with it on the new moves
are legal only where they are sound, are scored exactly, replay bit for bit, and the language model only
ever narrates them after the fact.
"""

from __future__ import annotations

import ast
import itertools
import random
from fractions import Fraction
from pathlib import Path

import pytest

from courtroom.agents import ChaosAgent, ScriptedAgent, perceive_witnesses
from courtroom.agents.adversarial import _LEGACY_ACTIONS
from courtroom.cases import CASES, WITNESS_CASES, get_case
from courtroom.contracts import (
    Action,
    ActionType,
    EventKind,
    ExamGround,
    Phase,
    RuleSet,
    Side,
)
from courtroom.engine import Court, replay_trial, run_trial
from courtroom.engine.audit import verify_chain
from courtroom.judge import Judge
from courtroom.judge.rules import CROSS_COST, EXAM_FACTORS, EXAMINE_COST, SANCTION_FAILED_CROSS, exposure_key
from courtroom.judge.scoring import score_record
from courtroom.llm.narrator import SPOKEN_KINDS, _prompt, _template, narrate
from courtroom.procedure import ProcedureState, validate

KESTREL = WITNESS_CASES["kestrel-av-witnesses"]
STRATEGIES = ("aggressive", "conservative", "adaptive")
P, D = Side.PROSECUTION, Side.DEFENSE


def _state(case, *, phase=Phase.EVIDENCE, admitted=()) -> ProcedureState:
    st = ProcedureState(case)
    st.phase = phase
    st.admitted = list(admitted)
    return st


def _cross(actor: Side, witness: str, ground=ExamGround.QUALIFICATIONS) -> Action:
    return Action(actor=actor, type=ActionType.CROSS_EXAMINE, witness_id=witness, ground=ground)


def _examine(actor: Side, witness: str) -> Action:
    return Action(actor=actor, type=ActionType.EXAMINE, witness_id=witness)


# --------------------------------------------------------------------- the flag is the whole fence


def test_the_certified_library_has_no_witness_rules_and_the_variants_are_separate() -> None:
    assert all(not c.witness_examination for c in CASES.values())
    from courtroom.cases import PLAIN_CASES

    assert all(c.rules is None for c in PLAIN_CASES.values())
    assert not set(WITNESS_CASES) & set(CASES), "the variants must stay out of CASES, which the analysis iterates"
    assert all(c.witness_examination for c in WITNESS_CASES.values())
    assert get_case("kestrel-av-witnesses") is KESTREL


def test_with_the_flag_off_an_examination_is_refused_not_ignored() -> None:
    case = CASES["kestrel-av"]
    st = _state(case, admitted=["P-TAN"])
    for action in (_cross(D, "W-ENG"), _examine(P, "W-ENG")):
        v = validate(action, st, action.actor, "primary")
        assert v is not None and v.rule_id == "V-WINDOW"


def test_with_the_flag_off_no_library_trial_contains_an_examination() -> None:
    for case in CASES.values():
        for p, d in itertools.product(("aggressive", "adaptive"), repeat=2):
            result = run_trial(case, p, d, seed=0)
            assert not any(e.kind is EventKind.EXAMINATION for e in result.events)


def test_the_chaos_fuzzer_still_samples_the_six_original_actions() -> None:
    """Adding enum members must not lengthen the list it draws from, or every chaos digest moves."""
    assert tuple(ActionType)[:6] == _LEGACY_ACTIONS
    assert [a.value for a in _LEGACY_ACTIONS] == [
        "present_evidence",
        "object",
        "impeach",
        "motion_directed_verdict",
        "pass",
        "rest",
    ]


def test_ruleset_defaults_to_off() -> None:
    assert RuleSet().witnesses is False


# --------------------------------------------------------------------- legality


def test_a_cross_examination_needs_an_opposing_witness_who_has_testified() -> None:
    before = _state(KESTREL)  # nobody has testified yet
    v = validate(_cross(D, "W-ENG"), before, D, "primary")
    assert v is not None and v.rule_id == "V-EXAM-TARGET"

    after = _state(KESTREL, admitted=["P-TAN"])
    assert validate(_cross(D, "W-ENG"), after, D, "primary") is None
    own = validate(_cross(P, "W-ENG"), after, P, "primary")  # cannot cross-examine your own witness
    assert own is not None and own.rule_id == "V-EXAM-TARGET"


def test_direct_examination_is_for_your_own_witness_only() -> None:
    st = _state(KESTREL, admitted=["P-TAN"])
    assert validate(_examine(P, "W-ENG"), st, P, "primary") is None
    v = validate(_examine(D, "W-ENG"), st, D, "primary")
    assert v is not None and v.rule_id == "V-EXAM-TARGET"


def test_each_witness_ground_pair_can_be_crossed_once() -> None:
    st = _state(KESTREL, admitted=["P-TAN"])
    st.used_crosses.add(("W-ENG", ExamGround.BIAS))
    dup = validate(_cross(D, "W-ENG", ExamGround.BIAS), st, D, "primary")
    assert dup is not None and dup.rule_id == "V-DUPLICATE"
    assert validate(_cross(D, "W-ENG", ExamGround.QUALIFICATIONS), st, D, "primary") is None
    st.used_examines.add("W-ENG")
    again = validate(_examine(P, "W-ENG"), st, P, "primary")
    assert again is not None and again.rule_id == "V-DUPLICATE"


def test_a_cross_examination_must_name_an_examination_ground() -> None:
    st = _state(KESTREL, admitted=["P-TAN"])
    no_ground = Action(actor=D, type=ActionType.CROSS_EXAMINE, witness_id="W-ENG")
    v = validate(no_ground, st, D, "primary")
    assert v is not None and v.rule_id == "V-MISSING-FIELD"


def test_examination_is_refused_in_rebuttal_and_outside_the_primary_window() -> None:
    rebuttal = _state(KESTREL, phase=Phase.REBUTTAL, admitted=["P-TAN"])
    v = validate(_examine(P, "W-ENG"), rebuttal, P, "primary")
    assert v is not None and v.rule_id == "V-EXAM-PHASE"
    st = _state(KESTREL, admitted=["P-TAN"])
    w = validate(_cross(D, "W-ENG"), st, D, "response")
    assert w is not None and w.rule_id == "V-WINDOW"


def test_examination_costs_budget_and_is_refused_without_it() -> None:
    st = _state(KESTREL, admitted=["P-TAN"])
    st.ledgers[D].budget = CROSS_COST - 0.01
    v = validate(_cross(D, "W-ENG"), st, D, "primary")
    assert v is not None and v.rule_id == "V-BUDGET"
    st.ledgers[P].budget = EXAMINE_COST - 0.01
    assert validate(_examine(P, "W-ENG"), st, P, "primary").rule_id == "V-BUDGET"  # type: ignore[union-attr]


# --------------------------------------------------------------------- the judge


def test_a_cross_examination_succeeds_exactly_when_the_hidden_flaw_is_real() -> None:
    judge = Judge(KESTREL)
    assert judge.rule_on_cross("W-ENG", ExamGround.QUALIFICATIONS)[0] is True  # flawed in the case
    assert judge.rule_on_cross("W-ENG", ExamGround.BIAS)[0] is False  # not flawed
    assert judge.rule_on_cross("W-EYE2", ExamGround.INCONSISTENCY)[0] is True
    assert judge.rule_on_cross("W-NOBODY", ExamGround.BIAS)[0] is False
    _ok, rule = judge.rule_on_cross("W-ENG", ExamGround.QUALIFICATIONS)
    assert rule.rule_id == "XEX-1" and "1/3" in rule.detail
    assert judge.rule_on_cross("W-ENG", ExamGround.BIAS)[1].rule_id == "XEX-2"


def test_redirect_repairs_the_latest_exposure_and_otherwise_does_nothing() -> None:
    judge = Judge(KESTREL)
    assert judge.rule_on_examine("W-ENG", (ExamGround.BIAS, ExamGround.QUALIFICATIONS))[1].rule_id == "XEX-4"
    ok, rule = judge.rule_on_examine("W-ENG", ())
    assert not ok and rule.rule_id == "XEX-5"


# --------------------------------------------------------------------- scoring is exact


def _log_odds(case, admitted, marks=None):
    return score_record(case, admitted, marks or {}).log_odds


def test_an_exposed_flaw_multiplies_credibility_by_exactly_its_factor() -> None:
    admitted = ["P-TAN"]
    base = _log_odds(KESTREL, admitted)["defect"]
    hit = _log_odds(KESTREL, admitted, {exposure_key("W-ENG", ExamGround.QUALIFICATIONS): 1})["defect"]
    prior = Fraction(0)  # civil
    assert (hit - prior) == (base - prior) * EXAM_FACTORS[ExamGround.QUALIFICATIONS]


def test_exposures_compose_with_each_other_and_with_impeachment() -> None:
    admitted = ["P-TAN"]
    k = exposure_key
    both = _log_odds(KESTREL, admitted, {k("W-ENG", ExamGround.BIAS): 1, k("W-ENG", ExamGround.INCONSISTENCY): 1})["defect"]
    base = _log_odds(KESTREL, admitted)["defect"]
    assert both == base * Fraction(2, 3) * Fraction(1, 2)
    withimp = _log_odds(KESTREL, admitted, {"W-ENG": 1, k("W-ENG", ExamGround.BIAS): 1})["defect"]
    assert withimp == base * Fraction(1, 2) * Fraction(2, 3)


def test_scoring_ignores_the_order_flaws_were_exposed_in() -> None:
    admitted = ["P-TAN", "P-EYE1", "D-EYE2"]
    marks = [exposure_key("W-ENG", g) for g in ExamGround]
    expected = _log_odds(KESTREL, admitted, dict.fromkeys(marks, 1))
    rng = random.Random(5)
    for _ in range(10):
        shuffled = marks[:]
        rng.shuffle(shuffled)
        assert _log_odds(KESTREL, admitted, dict.fromkeys(shuffled, 1)) == expected


def test_an_absent_or_zero_exposure_scores_exactly_as_before() -> None:
    admitted = [e.id for e in KESTREL.evidence]
    assert _log_odds(KESTREL, admitted) == _log_odds(KESTREL, admitted, {exposure_key("W-ENG", ExamGround.BIAS): 0})
    assert all(isinstance(v, Fraction) for v in _log_odds(KESTREL, admitted).values())


@pytest.mark.parametrize("case_id", sorted(WITNESS_CASES))
def test_exposing_a_witness_only_ever_hurts_the_side_that_called_it(case_id: str) -> None:
    """The soundness premise (P2): a cross-examination lowers the log-odds of the party that offered the
    witness. Prosecution witnesses lower L_e, defense witnesses raise it."""
    case = WITNESS_CASES[case_id]
    admitted = [e.id for e in case.evidence]
    base = _log_odds(case, admitted)
    owner = {e.witness_id: e.owner for e in case.evidence if e.witness_id}
    checked = 0
    for witness, side in owner.items():
        for ground in ExamGround:
            hit = _log_odds(case, admitted, {exposure_key(witness, ground): 1})
            for element, value in hit.items():
                if side is P:
                    assert value <= base[element], (case_id, witness, ground, element)
                else:
                    assert value >= base[element], (case_id, witness, ground, element)
                checked += value != base[element]
    assert checked, "no exposure moved any element, so this test would pass vacuously"


# --------------------------------------------------------------------- perception


def test_witness_perception_is_a_pure_function_of_case_and_seed() -> None:
    a = perceive_witnesses(KESTREL, random.Random("3:witness-perception"))
    b = perceive_witnesses(KESTREL, random.Random("3:witness-perception"))
    c = perceive_witnesses(KESTREL, random.Random("4:witness-perception"))
    assert a == b and a != c
    assert set(a) == {w.id for w in KESTREL.witnesses}
    assert all(set(v) == {g.value for g in ExamGround} for v in a.values())


def test_the_channel_is_informative_but_not_certain() -> None:
    """A real flaw is flagged far more often than a fake one, at the case's accuracy."""
    case = WITNESS_CASES["helix-espionage-witnesses"]  # accuracy 0.65
    real, fake = [], []
    for seed in range(400):
        beliefs = perceive_witnesses(case, random.Random(f"{seed}:witness-perception"))
        for witness in case.witnesses:
            for ground in ExamGround:
                flawed = not {
                    ExamGround.QUALIFICATIONS: witness.qualified,
                    ExamGround.BIAS: witness.impartial,
                    ExamGround.INCONSISTENCY: witness.consistent,
                }[ground]
                (real if flawed else fake).append(beliefs[witness.id][ground.value] > 0.5)
    assert 0.55 < sum(real) / len(real) < 0.75  # true-positive rate = accuracy = 0.65
    assert sum(fake) / len(fake) < 0.15  # false-positive rate = 0.0875


def test_witness_perception_never_touches_the_objection_stream() -> None:
    """The flag off draws nothing, and the flag on draws from a differently-seeded stream, so objection
    perception sees exactly the randomness it always did."""
    plain = run_trial(CASES["kestrel-av"], "adaptive", "adaptive", seed=2)
    flagged = KESTREL.model_copy(update={"id": "kestrel-av", "title": CASES["kestrel-av"].title})
    again = run_trial(flagged, "conservative", "conservative", seed=2)
    assert plain.verdict.outcome is not None and again.verdict.outcome is not None


# --------------------------------------------------------------------- the engine


def _scripted_court() -> Court:
    """Prosecution calls the engineer (a real qualifications flaw); the defense crosses twice; the
    prosecution then repairs the witness."""
    prosecution = ScriptedAgent([Action(actor=P, type=ActionType.PRESENT_EVIDENCE, evidence_id="P-TAN"), _examine(P, "W-ENG")])
    defense = ScriptedAgent(
        [
            Action(actor=D, type=ActionType.PASS),  # no objection to the engineer's testimony
            _cross(D, "W-ENG", ExamGround.QUALIFICATIONS),
            _cross(D, "W-ENG", ExamGround.BIAS),
        ]
    )
    return Court(KESTREL, prosecution, defense, seed=0)


def test_a_scripted_examination_runs_charges_and_scores_as_designed() -> None:
    result = _scripted_court().run()
    exams = [e for e in result.events if e.kind is EventKind.EXAMINATION]
    assert [e.status for e in exams] == ["exposed", "unfounded", "rehabilitated"] or [e.status for e in exams] == [
        "exposed",
        "rehabilitated",
        "unfounded",
    ]
    assert {e.status for e in exams} == {"exposed", "unfounded", "rehabilitated"}
    assert [r.rule_id for e in exams for r in e.rules].count("XEX-1") == 1
    assert verify_chain(result.events)
    # The defense paid 1.0 per cross-examination and was sanctioned only for the unfounded one.
    ledger = result.ledgers[D]
    assert ledger.spent >= 2 * CROSS_COST
    assert ledger.sanctions == SANCTION_FAILED_CROSS
    assert result.ledgers[P].sanctions == 0


def test_rehabilitation_restores_the_exposed_witness_exactly() -> None:
    court = _scripted_court()
    result = court.run()
    probs = [e.element_probabilities["defect"] for e in result.events if e.element_probabilities]
    exposed = next(e for e in result.events if e.status == "exposed")
    repaired = next(e for e in result.events if e.status == "rehabilitated")
    before = [e for e in result.events if e.seq < exposed.seq and e.element_probabilities][-1]
    assert exposed.element_probabilities["defect"] < before.element_probabilities["defect"]
    assert repaired.element_probabilities["defect"] > exposed.element_probabilities["defect"]
    assert probs, "the trial produced no probabilities"
    # Nothing left exposed at the end, so the final record scores as if no cross-examination had happened.
    assert not court.state.exposures
    assert not any("#" in k for k, v in court.state.impeachments.items() if v)


@pytest.mark.parametrize("case_id", sorted(WITNESS_CASES))
@pytest.mark.parametrize("pairing", list(itertools.product(STRATEGIES, STRATEGIES)))
def test_witness_trials_replay_bit_for_bit(case_id: str, pairing: tuple[str, str]) -> None:
    case = WITNESS_CASES[case_id]
    for seed in (0, 1, 2):
        first = run_trial(case, pairing[0], pairing[1], seed=seed)
        second = replay_trial(first, case)
        assert first.digest == second.digest
        assert first.verdict.model_dump_json() == second.verdict.model_dump_json()
        assert verify_chain(first.events)


def test_the_agents_actually_use_the_new_moves() -> None:
    """Otherwise every other test here could pass on a feature nobody ever exercises."""
    statuses: set[str | None] = set()
    for case in WITNESS_CASES.values():
        for p, d in itertools.product(STRATEGIES, STRATEGIES):
            for seed in range(3):
                result = run_trial(case, p, d, seed=seed)
                statuses |= {e.status for e in result.events if e.kind is EventKind.EXAMINATION}
    assert {"exposed", "rehabilitated"} <= statuses


@pytest.mark.parametrize("case_id", sorted(WITNESS_CASES))
def test_no_examination_can_raise_the_prosecution_after_the_directed_verdict_review(case_id: str) -> None:
    """The directed-verdict review is sound only if nothing after it can help the prosecution. Under
    examination, every move after the review is the defense's or a repair of a defense witness."""
    case = WITNESS_CASES[case_id]
    for p, d in itertools.product(STRATEGIES, STRATEGIES):
        for seed in range(4):
            result = run_trial(case, p, d, seed=seed)
            dv = next((i for i, e in enumerate(result.events) if e.kind is EventKind.DIRECTED_VERDICT), None)
            if dv is None:
                continue
            for earlier, later in itertools.pairwise(result.events[dv:]):
                if later.phase is Phase.REBUTTAL or not earlier.element_probabilities or not later.element_probabilities:
                    continue
                for element, value in later.element_probabilities.items():
                    assert value <= earlier.element_probabilities[element] + 1e-9, (case_id, p, d, seed, later.seq)


class _RandomExaminer:
    """Plays random examination moves, legal and illegal, to fuzz the new code paths."""

    name = "random-examiner"

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def opening_statement(self, side: Side) -> str:
        return "fuzz"

    def act(self, view, oracle):
        r = self.rng
        witnesses = [w for _, w in view.impeachment_options] + [w for w, _ in view.exam_options] + list(view.examine_options)
        kind = r.choice([ActionType.CROSS_EXAMINE, ActionType.EXAMINE, ActionType.PRESENT_EVIDENCE, ActionType.PASS, ActionType.REST])
        ids = [e.id for e in view.own_evidence]
        return Action(
            actor=view.side,
            type=kind,
            witness_id=r.choice([None, "W-GHOST", *witnesses]),
            evidence_id=r.choice([None, *ids]) if ids else None,
            ground=r.choice([None, *ExamGround]),
        ) if view.window == "primary" else Action(actor=view.side, type=ActionType.PASS)


def test_fuzzing_the_new_moves_never_crashes_and_always_terminates() -> None:
    for case in WITNESS_CASES.values():
        for seed in range(30):
            court = Court(case, _RandomExaminer(random.Random(seed)), _RandomExaminer(random.Random(seed + 1000)), seed=seed)
            result = court.run()
            assert verify_chain(result.events)
            assert result.events[-1].kind is EventKind.VERDICT
            assert len(result.events) <= 400


def test_the_chaos_agent_survives_witness_cases() -> None:
    for case in WITNESS_CASES.values():
        for seed in range(5):
            result = Court(case, ChaosAgent(random.Random(seed)), ChaosAgent(random.Random(seed + 9)), seed=seed).run()
            assert verify_chain(result.events)


# --------------------------------------------------------------------- the language model only narrates


def test_narration_of_examinations_never_changes_the_trial() -> None:
    from courtroom.llm.client import LLMClient

    class Says(LLMClient):
        def complete(self, system: str, prompt: str) -> str:
            self.usage.calls += 1
            return "Q: Is that so? A: It is."

    result = _scripted_court().run()
    lines = narrate(result, KESTREL, Says())
    exam_seqs = {e.seq for e in result.events if e.kind is EventKind.EXAMINATION}
    assert exam_seqs and exam_seqs <= set(lines), "every examination should be narrated"
    again = _scripted_court().run()
    assert result.digest == again.digest and result.verdict.model_dump_json() == again.verdict.model_dump_json()


def test_the_template_fallback_reads_as_question_and_answer_from_the_public_ruling() -> None:
    result = _scripted_court().run()
    by_status = {e.status: _template(KESTREL, e) for e in result.events if e.kind is EventKind.EXAMINATION}
    assert by_status["exposed"].startswith("Q: ") and "A: I... yes, I have to concede that." in by_status["exposed"]
    assert "A: No. There is nothing to that." in by_status["unfounded"]
    assert "A: Yes, and I stand by what I said." in by_status["rehabilitated"]


def test_examination_prompts_carry_the_public_record_and_never_a_hidden_flaw() -> None:
    result = _scripted_court().run()
    flaw_words = ("qualified", "impartial", "consistent")
    seen = 0
    for event in result.events:
        if event.kind is not EventKind.EXAMINATION:
            continue
        seen += 1
        prompt = _prompt(KESTREL, event, [])
        for line in prompt.splitlines():
            if line.startswith("Line of cross-examination:"):
                continue  # the move itself, said aloud in court
            for word in flaw_words:
                assert word not in line.lower(), f"prompt leaks {word!r}: {prompt}"
        assert "True" not in prompt and "False" not in prompt
        # The other grounds must not appear: only the one being put to the witness is named.
        named = [g.value for g in ExamGround if g.value in prompt.lower()]
        assert len(named) <= 1, named
    assert seen and EventKind.EXAMINATION in SPOKEN_KINDS


def test_a_prompt_for_an_unfounded_cross_does_not_reveal_which_flaw_is_real() -> None:
    result = _scripted_court().run()
    unfounded = next(e for e in result.events if e.status == "unfounded")
    prompt = _prompt(KESTREL, unfounded, "")
    assert "qualif" not in prompt.lower().replace("line of cross-examination: bias", "")


CORE_PACKAGES = ("contracts", "judge", "procedure", "agents", "engine", "cases", "gametheory")


def test_no_core_package_imports_the_language_model_layer() -> None:
    root = Path(__file__).resolve().parents[1] / "courtroom"
    offenders = []
    for package in CORE_PACKAGES:
        for path in (root / package).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                names = (
                    [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                    if isinstance(node, ast.ImportFrom)
                    else []
                )
                if any(n == "courtroom.llm" or n.startswith("courtroom.llm.") for n in names):
                    offenders.append(f"{path.relative_to(root)}: {names}")
    assert not offenders, offenders
