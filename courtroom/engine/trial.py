"""Trial orchestrator: drives agents through the procedure FSM and records everything.

Owner: Engineer 6.

Robustness guarantees (all covered by tests):
* No exception raised by an agent escapes; it becomes violation V-AGENT-FAULT.
* Every loop iteration either consumes a primary turn, closes a response or
  motion window, or changes phase, so the trial always terminates. A global
  event cap (WATCHDOG) backs this up.
* Identical (case, strategies, seed) inputs produce an identical event hash chain.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence

from courtroom.agents import Agent, Oracle, ScoreCache, make_agent, perceive, perceive_witnesses
from courtroom.contracts import (
    Action,
    ActionType,
    AdversePush,
    CaseFile,
    EventKind,
    EvidenceGraph,
    EvidenceItem,
    EvidenceKind,
    ExamGround,
    GraphEdge,
    GraphNode,
    Injection,
    PartyView,
    PerceivedItem,
    Phase,
    RuleFiring,
    Side,
    TrialEvent,
    TrialResult,
    Verdict,
    Window,
)
from courtroom.engine.audit import GENESIS, chain, digest_item
from courtroom.engine.utility import utilities
from courtroom.judge import Judge
from courtroom.judge.admissibility import BAD_FAITH_GROUNDS
from courtroom.judge.rules import (
    CONTEMPT_VIOLATIONS,
    CROSS_COST,
    EXAMINE_COST,
    FINE_VIOLATION,
    IMPEACHMENT_COST,
    MOTION_COST,
    OBJECTION_COST,
    SANCTION_BAD_FAITH_EVIDENCE,
    SANCTION_FAILED_CROSS,
    SANCTION_OVERRULED_OBJECTION,
    SANCTION_VIOLATION,
    exposure_key,
    hostile_key,
)
from courtroom.procedure import ProcedureState, Violation, validate
from courtroom.procedure.state import CASE_PHASES, STALL_LIMIT
from courtroom.procedure.validator import VIOLATION_RULES

MAX_EVENTS = 400


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x)) if x >= 0 else math.exp(x) / (1 + math.exp(x))


class Court:
    def __init__(
        self,
        case: CaseFile,
        prosecution: Agent,
        defense: Agent,
        seed: int = 0,
        prosecution_strategy: str | None = None,
        defense_strategy: str | None = None,
        *,
        injections: Sequence[Injection] = (),
        adverse_pushes: Sequence[AdversePush] = (),
    ) -> None:
        self.case = case
        self.agents: dict[Side, Agent] = {Side.PROSECUTION: prosecution, Side.DEFENSE: defense}
        self.strategy_names = {
            Side.PROSECUTION: prosecution_strategy or prosecution.name,
            Side.DEFENSE: defense_strategy or defense.name,
        }
        self.seed = seed
        self.judge = Judge(case)
        self.state = ProcedureState(case)
        self.cache = ScoreCache(case)
        self._perception_rng = random.Random(f"{seed}:perception")
        self._perceived: PerceivedItem | None = None
        # A separate stream, seeded apart from objection perception, and only drawn when the case enables
        # witness examination, so a case without the flag consumes exactly the randomness it always did.
        # Adverse events draw from their own seeded stream, created only when the case enables them. A case
        # without the flag never touches it, and one with every rate at zero consumes it without effect, so
        # neither can disturb the objection or witness-perception streams.
        self._adverse_rng = random.Random(f"{seed}:adverse")
        self._witness_beliefs: dict[str, dict[str, float]] = (
            perceive_witnesses(case, random.Random(f"{seed}:witness-perception")) if case.witness_examination else {}
        )
        self._events: list[TrialEvent] = []
        self._last_hash = GENESIS
        self._injections, self._cases_after = _plan_injections(case, injections)
        self._requested: tuple[Injection, ...] = tuple(self._injections)  # every input, applied or not
        self._pushes = _plan_pushes(case, adverse_pushes)
        self._requested_pushes: tuple[AdversePush, ...] = tuple(self._pushes)

    # ------------------------------------------------------------------ event plumbing

    def _probabilities(self) -> tuple[float, dict[str, float]]:
        lo = self.cache.log_odds(self.state.admitted, self.state.impeachments)
        probs = {k: round(_sigmoid(v), 6) for k, v in lo.items()}
        return min(probs.values()), probs

    def _emit(
        self,
        kind: EventKind,
        summary: str,
        actor: Side | None = None,
        action: Action | None = None,
        rules: tuple[RuleFiring, ...] | list[RuleFiring] = (),
        subject: str | None = None,
        status: str | None = None,
    ) -> None:
        burden, probs = self._probabilities()
        event = TrialEvent(
            seq=len(self._events),
            phase=self.state.phase,
            kind=kind,
            actor=actor,
            action=action,
            summary=summary,
            subject=subject,
            status=status,  # type: ignore[arg-type]
            rules=tuple(rules),
            burden_index=round(burden, 6),
            element_probabilities=probs,
        )
        event = chain(event, self._last_hash)
        self._last_hash = event.hash
        self._events.append(event)

    def _enter(self, phase: Phase, reason: str) -> None:
        self.state.enter(phase)
        self._emit(EventKind.PHASE_CHANGE, f"Phase -> {phase.value}. {reason}".strip())

    # ------------------------------------------------------------------ views

    def _view(self, side: Side, window: Window) -> PartyView:
        st = self.state
        opp = side.opponent
        own = tuple(i for i in self.case.evidence if i.owner is side)
        options = tuple(
            (item.id, w) for w in st.testified_witnesses(opp) for item in own if (item.id, w) not in st.used_impeachments
        )
        return PartyView(
            side=side,
            phase=st.phase,
            window=window,
            case_id=self.case.id,
            case_type=self.case.case_type,
            standard=self.case.standard,
            element_ids=tuple(e.id for e in self.case.elements),
            own_evidence=own,
            presented=tuple(st.presented),
            admitted=tuple(st.admitted),
            excluded=tuple(st.excluded),
            pending=self._perceived if window == "response" else None,
            snapshot=self.judge.score(st.admitted, st.impeachments).snapshot,
            budget=st.ledgers[side].budget,
            reserve_basis=st.ledgers[side].budget_start,
            opponent_budget=st.ledgers[opp].budget,
            turns_left=st.turns_left(side),
            impeachment_options=options,
            examine_options=st.examine_options(side),
            exam_options=tuple((w, g.value) for w, g in st.exam_options(side)),
            known_adverse=tuple(st.known_adverse),
            adverse=(
                {
                    "no_show": self.case.rules.no_show,  # type: ignore[union-attr]
                    "missing_certificate": self.case.rules.missing_certificate,  # type: ignore[union-attr]
                    "hostile": self.case.rules.hostile,  # type: ignore[union-attr]
                }
                if self.case.adverse_events
                else {}
            ),
            own_exposures=tuple(
                (w, st.exposed_grounds(w)[-1].value) for w in st.testified_witnesses(side) if st.exposed_grounds(w)
            )
            if st.case.witness_examination
            else (),
            witness_beliefs={w: dict(self._witness_beliefs[w]) for w in st.testified_witnesses(opp) if w in self._witness_beliefs}
            if st.exam_options(side)
            else {},
            rebuttal_targets=st.rebuttal_targets() if side is Side.PROSECUTION else (),
            opponent_objections=st.ledgers[opp].objections,
            opponent_response_windows=st.ledgers[opp].response_windows,
        )

    # ------------------------------------------------------------------ main loop

    def run(self) -> TrialResult:
        st = self.state
        opening = " | ".join(f"{s.value}: {self._opening(s)}" for s in Side)
        self._emit(EventKind.PHASE_CHANGE, f"Court is in session: {self.case.title}. {opening}")
        self._enter(Phase.EVIDENCE, "Both sides present, turn and turn about; the prosecution opens.")

        while st.phase not in (Phase.DELIBERATION, Phase.CLOSED):
            if len(self._events) >= MAX_EVENTS:
                self._emit(
                    EventKind.WATCHDOG,
                    "Event cap reached; the court proceeds directly to deliberation.",
                    rules=[RuleFiring(rule_id="WATCHDOG-1", detail=f"{MAX_EVENTS} events exceeded.")],
                )
                st.enter(Phase.DELIBERATION)
                break
            if st.phase in CASE_PHASES and st.pending is None and st.phase_is_over():
                self._enter(st.next_phase_after_rest(), "No one left to present.")
                continue
            self._apply_due_injections()
            self._apply_due_pushes()
            side, window = st.expected()  # type: ignore[misc]
            if window == "primary" and st.turns_left(side) == 0:
                self._rest(side, RuleFiring(rule_id="TURN-CAP", detail=f"{side.value} exhausted its {st.turn_cap()} turns."))
                continue
            if window == "response":
                st.ledgers[side].response_windows += 1
            action, violation = self._solicit(side, window)
            if violation is not None:
                self._penalise(side, window, violation, action)
            else:
                assert action is not None
                self._dispatch(side, window, action)

        return self._deliberate()

    def _rest_if_spent(self, side: Side) -> None:
        """End a side's participation after a fruitless primary turn.

        Two triggers, checked only once the side has actually had its turn so that an
        over-budget attempt is still caught by the validator (V-BUDGET) rather than
        silently excused: it can no longer afford any action, or it has passed twice.
        """
        st = self.state
        if not self._can_afford_a_primary_action(side):
            self._rest(
                side,
                RuleFiring(rule_id="BUDGET-1", detail=f"{side.value} can afford no further action; deemed rested."),
            )
        elif st.passes.get(side, 0) >= STALL_LIMIT:
            self._rest(side, RuleFiring(rule_id="STALL-1", detail="Consecutive passes deemed a rest."))

    def _can_afford_a_primary_action(self, side: Side) -> bool:
        """Whether ``side`` could still do anything but pass.

        Budget exhaustion is one of the two triggers (with two consecutive passes) that end a
        side's participation, so the directed-verdict review has a well-defined moment to fire.
        """
        st = self.state
        budget = st.ledgers[side].budget
        if budget >= IMPEACHMENT_COST and st.testified_witnesses(side.opponent):
            return True
        if (budget >= CROSS_COST and st.exam_options(side)) or (budget >= EXAMINE_COST and st.examine_options(side)):
            return True
        allowed = set(st.rebuttal_targets()) if st.phase is Phase.REBUTTAL else None
        return any(
            item.owner is side
            and item.id not in st.presented
            and item.presentation_cost <= budget
            and (allowed is None or item.id in allowed)
            for item in self.case.evidence
        )

    def _opening(self, side: Side) -> str:
        try:
            return str(self.agents[side].opening_statement(side))[:500]
        except Exception as exc:
            return f"(no opening statement: {type(exc).__name__})"

    def _solicit(self, side: Side, window: Window) -> tuple[Action | None, Violation | None]:
        view = self._view(side, window)
        oracle = Oracle(self.cache, self.state.admitted, self.state.impeachments)
        try:
            action = self.agents[side].act(view, oracle)
            if not isinstance(action, Action):
                raise TypeError(f"agent returned {type(action).__name__}, not Action")
        except Exception as exc:
            return None, Violation("V-AGENT-FAULT", f"{VIOLATION_RULES['V-AGENT-FAULT']} ({type(exc).__name__}: {exc})")
        return action, validate(action, self.state, side, window)

    # ------------------------------------------------------------------ injected evidence

    def _apply_due_injections(self) -> None:
        """Add due exhibits to their owners' hands, but only between turns.

        An injection never lands inside a response window: an objection must be ruled on against the
        case as it stood when the exhibit was offered. It waits for the next primary turn, which keeps
        every ruling a pure function of the record it was made on.
        """
        st = self.state
        while (
            self._injections
            and self._injections[0].at_seq <= len(self._events)
            and st.pending is None
            and st.phase in CASE_PHASES
        ):
            inj = self._injections.pop(0)
            self.case = self._cases_after.pop(0)
            self.judge = Judge(self.case)
            st.case = self.case
            self.cache = ScoreCache(self.case)
            item = inj.item
            self._emit(
                EventKind.INJECTION,
                f"New evidence enters {item.owner.value}'s hand: {item.id}, {item.title}.",
                subject=item.id,
                status="injected",
                rules=[
                    RuleFiring(
                        rule_id="INJ-1",
                        detail=f"Injected for {item.owner.value} at step {inj.at_seq}; exhibit sha256 {digest_item(item)}.",
                    )
                ],
            )

    def _report_unapplied_injections(self) -> None:
        for inj in self._injections:
            self._emit(
                EventKind.RULING,
                f"{inj.item.id} was not added: the trial had left the evidence phases before step {inj.at_seq}.",
                subject=inj.item.id,
                rules=[
                    RuleFiring(
                        rule_id="INJ-2",
                        detail=(
                            "Injection point not reached while evidence could still be offered; "
                            f"exhibit sha256 {digest_item(inj.item)}."
                        ),
                    )
                ],
            )
        self._injections = []

    # ------------------------------------------------------------------ penalties

    def _penalise(self, side: Side, window: Window, violation: Violation, action: Action | None) -> None:
        st = self.state
        ledger = st.ledgers[side]
        ledger.violations += 1
        ledger.sanctions += SANCTION_VIOLATION
        fine = ledger.charge(FINE_VIOLATION)
        self._emit(
            EventKind.VIOLATION,
            f"{side.value} committed a procedural violation; treated as PASS, fined {fine:g}.",
            actor=side,
            action=action,
            rules=[RuleFiring(rule_id=violation.rule_id, detail=violation.detail)],
        )
        if window == "response":
            self._admit_pending(waived=True)
        elif window == "motion":
            self._directed_verdict_review(moved=False)
        else:
            st.consume_primary_turn(side)
            st.passes[side] = st.passes.get(side, 0) + 1
            if ledger.violations >= CONTEMPT_VIOLATIONS:
                self._rest(
                    side,
                    RuleFiring(
                        rule_id="CONTEMPT-1",
                        detail=f"{ledger.violations} violations: counsel held in contempt; case deemed rested.",
                    ),
                )
            else:
                self._rest_if_spent(side)

    # ------------------------------------------------------------------ dispatch

    def _dispatch(self, side: Side, window: Window, action: Action) -> None:
        st = self.state
        ledger = st.ledgers[side]
        match action.type:
            case ActionType.PRESENT_EVIDENCE:
                item = self.case.item(action.evidence_id)  # type: ignore[arg-type]
                assert item is not None
                ledger.charge(item.presentation_cost)
                ledger.presented += 1
                st.presented.append(item.id)
                failure = self._roll_offer(item)
                if failure is not None:
                    st.consume_primary_turn(side)
                    st.passes[side] = 0
                    st.excluded.append(item.id)
                    ledger.excluded += 1
                    self._emit_offer_failure(side, action, item, failure)
                    return
                st.pending = item.id
                st.consume_primary_turn(side)
                st.passes[side] = 0
                self._perceived = perceive(item, self.case, self._perception_rng)
                self._emit(
                    EventKind.ACTION,
                    f"{side.value} offers {item.id}: {item.title}.",
                    side,
                    action,
                    subject=item.id,
                    status="offered",
                )

            case ActionType.OBJECT:
                self._rule_on_objection(side, action)

            case ActionType.IMPEACH:
                item = self.case.item(action.evidence_id)  # type: ignore[arg-type]
                witness = action.witness_id
                assert item is not None and witness is not None
                ledger.charge(IMPEACHMENT_COST)
                st.used_impeachments.add((item.id, witness))
                st.consume_primary_turn(side)
                st.passes[side] = 0
                ok, rule = self.judge.rule_on_impeachment(item, witness)
                if ok:
                    st.impeachments[witness] = st.impeachments.get(witness, 0) + 1
                    ledger.impeachments += 1
                else:
                    ledger.sanctions += SANCTION_OVERRULED_OBJECTION
                self._emit(
                    EventKind.RULING,
                    f"{side.value} impeaches {witness} with {item.id}: {'effective' if ok else 'improper'}.",
                    side,
                    action,
                    [rule],
                    subject=witness,
                    status="impeached" if ok else None,
                )

            case ActionType.CROSS_EXAMINE:
                self._cross_examine(side, action)

            case ActionType.EXAMINE:
                self._examine(side, action)

            case ActionType.MOTION_DIRECTED_VERDICT:
                ledger.charge(MOTION_COST)
                st.motion_made = True
                self._emit(EventKind.ACTION, f"{side.value} moves for a directed verdict.", side, action)
                self._directed_verdict_review(moved=True)

            case ActionType.PASS:
                if window == "response":
                    self._emit(EventKind.ACTION, f"{side.value} does not object.", side, action)
                    self._admit_pending(waived=False)
                elif window == "motion":
                    self._emit(EventKind.ACTION, f"{side.value} makes no motion.", side, action)
                    self._directed_verdict_review(moved=False)
                else:
                    st.consume_primary_turn(side)
                    st.passes[side] = st.passes.get(side, 0) + 1
                    self._emit(EventKind.ACTION, f"{side.value} passes.", side, action)
                    self._rest_if_spent(side)

            case ActionType.REST:
                self._emit(EventKind.ACTION, f"{side.value} rests.", side, action)
                self._rest(side, None)

    # ------------------------------------------------------------------ adverse events

    def _roll_offer(self, item: EvidenceItem) -> str | None:
        """Whether offering ``item`` fails outright. Draws only for the events the item is exposed to."""
        st = self.state
        # A pushed event is forced, so it consumes no randomness and works on any case, flag or not.
        if item.id in st.armed_no_show:
            return "no_show"
        if item.id in st.armed_certificate:
            return "no_certificate"
        if not self.case.adverse_events:
            return None
        rules = self.case.rules
        assert rules is not None
        if item.witness_id is not None and self._adverse_rng.random() < rules.no_show:
            return "no_show"
        if item.kind is EvidenceKind.DIGITAL_LOG and self._adverse_rng.random() < rules.missing_certificate:
            return "no_certificate"
        return None

    def _emit_offer_failure(self, side: Side, action: Action, item: EvidenceItem, failure: str) -> None:
        if failure == "no_show":
            witness = self.case.witness(item.witness_id) if item.witness_id else None
            who = witness.name if witness else str(item.witness_id)
            summary = f"{side.value} offers {item.id}, but the witness, {who}, does not appear. The testimony is lost."
            pushed = " (pushed by the examiner)" if item.id in self.state.armed_no_show else ""
            rule = RuleFiring(rule_id="ADV-1", detail=f"Witness no-show for {item.id}{pushed}; the exhibit is excluded and its cost is not refunded.")
        else:
            summary = f"{side.value} offers {item.id}, but it has no section 65B certificate. The court excludes it."
            pushed = " (pushed by the examiner)" if item.id in self.state.armed_certificate else ""
            rule = RuleFiring(rule_id="ADV-2", detail=f"Electronic record {item.id}{pushed} lacks a certificate of authenticity; excluded without objection, no bad-faith sanction.")
        self._emit(EventKind.ADVERSE, summary, side, action, [rule], subject=item.id, status=failure)  # type: ignore[arg-type]

    def _after_admission(self, item: EvidenceItem) -> None:
        """A witness whose testimony has just been admitted may turn hostile (once per witness)."""
        st = self.state
        if item.witness_id is None or item.witness_id in st.hostile:
            return
        pushed = item.witness_id in st.armed_hostile
        if not pushed:
            if not self.case.adverse_events:
                return
            rules = self.case.rules
            assert rules is not None
            if self._adverse_rng.random() >= rules.hostile:
                return
        self._turn_hostile(item, pushed)

    def _turn_hostile(self, item: EvidenceItem, pushed: bool) -> None:
        st = self.state
        assert item.witness_id is not None
        st.hostile.add(item.witness_id)
        st.impeachments[hostile_key(item.witness_id)] = 1
        witness = self.case.witness(item.witness_id)
        who = witness.name if witness else item.witness_id
        self._emit(
            EventKind.ADVERSE,
            f"{who} turns hostile on the stand; the testimony of {item.witness_id} now carries a quarter of its weight.",
            subject=item.witness_id,
            status="hostile",
            rules=[
                RuleFiring(
                    rule_id="ADV-3",
                    detail=f"Witness {item.witness_id} turned hostile after {item.id}{' (pushed by the examiner)' if pushed else ''}; credibility x1/4.",
                )
            ],
        )

    # ------------------------------------------------------------------ pushed adverse events

    def _apply_due_pushes(self) -> None:
        """Announce due pushes, between turns and never inside a response window (like injections)."""
        st = self.state
        while self._pushes and self._pushes[0].at_seq <= len(self._events) and st.pending is None and st.phase in CASE_PHASES:
            self._apply_push(self._pushes.pop(0))

    def _push_rule(self, push: AdversePush, rule_id: str, detail: str) -> RuleFiring:
        return RuleFiring(rule_id=rule_id, detail=f"{detail} [push at step {push.at_seq}: {push.kind} on {push.target}]")

    def _refuse_push(self, push: AdversePush, why: str) -> None:
        self._emit(
            EventKind.ADVERSE,
            f"The request to apply {push.kind.replace('_', ' ')} to {push.target} was refused: {why}.",
            subject=push.target,
            status="not_applied",
            rules=[self._push_rule(push, "ADV-5", why)],
        )

    def _apply_push(self, push: AdversePush) -> None:
        st = self.state
        known = f"{push.kind}:{push.target}"
        if push.kind in ("no_show", "missing_certificate"):
            if push.target in st.presented:
                return self._refuse_push(push, f"{push.target} has already been offered")
            (st.armed_no_show if push.kind == "no_show" else st.armed_certificate).add(push.target)
            what = (
                f"The witness for {push.target} has told the court they may not attend."
                if push.kind == "no_show"
                else f"The court is told {push.target} may lack its section 65B certificate."
            )
            st.known_adverse.append(known)
            self._emit(
                EventKind.ADVERSE, what, subject=push.target, status="announced",
                rules=[self._push_rule(push, "ADV-4", "Announced in court; both sides know")],
            )
            return
        testimony = next((self.case.item(i) for i in st.admitted if (it := self.case.item(i)) and it.witness_id == push.target), None)
        if push.target in st.hostile:
            return self._refuse_push(push, f"{push.target} is already hostile")
        if testimony is not None:
            if testimony.owner is Side.DEFENSE and st.phase is not Phase.EVIDENCE:
                # Down-weighting a defense witness after the directed-verdict review would raise the prosecution
                # after the point where the review is sound (DEVIATIONS D5, D15).
                return self._refuse_push(push, "that would help the prosecution after the directed-verdict review")
            st.known_adverse.append(known)
            self._turn_hostile(testimony, pushed=True)
            return
        st.armed_hostile.add(push.target)
        st.known_adverse.append(known)
        self._emit(
            EventKind.ADVERSE, f"The court is told {push.target} may turn hostile when called.", subject=push.target,
            status="announced", rules=[self._push_rule(push, "ADV-4", "Announced in court; both sides know")],
        )

    def _report_unapplied_pushes(self) -> None:
        for push in self._pushes:
            self._refuse_push(push, "the trial had left the evidence phases before that step")
        self._pushes = []

    def _cross_examine(self, side: Side, action: Action) -> None:
        st = self.state
        ledger = st.ledgers[side]
        witness = action.witness_id
        ground = action.ground
        assert witness is not None and isinstance(ground, ExamGround)
        ledger.charge(CROSS_COST)
        st.used_crosses.add((witness, ground))
        st.consume_primary_turn(side)
        st.passes[side] = 0
        ok, rule = self.judge.rule_on_cross(witness, ground)
        if ok:
            st.exposures.append((witness, ground))
            st.impeachments[exposure_key(witness, ground)] = 1
        else:
            ledger.sanctions += SANCTION_FAILED_CROSS
        self._emit(
            EventKind.EXAMINATION,
            f"{side.value} cross-examines {witness} on {ground.value}: {'a real flaw is exposed' if ok else 'nothing found'}.",
            side,
            action,
            [rule],
            subject=witness,
            status="exposed" if ok else "unfounded",
        )

    def _examine(self, side: Side, action: Action) -> None:
        st = self.state
        ledger = st.ledgers[side]
        witness = action.witness_id
        assert witness is not None
        ledger.charge(EXAMINE_COST)
        st.used_examines.add(witness)
        st.consume_primary_turn(side)
        st.passes[side] = 0
        ok, rule = self.judge.rule_on_examine(witness, st.exposed_grounds(witness))
        if ok:
            _, ground = next((w, g) for w, g in reversed(st.exposures) if w == witness)
            st.exposures.remove((witness, ground))
            st.impeachments.pop(exposure_key(witness, ground), None)
        self._emit(
            EventKind.EXAMINATION,
            f"{side.value} examines its own witness {witness}: {'rehabilitated' if ok else 'nothing to repair'}.",
            side,
            action,
            [rule],
            subject=witness,
            status="rehabilitated" if ok else None,
        )

    def _rule_on_objection(self, side: Side, action: Action) -> None:
        st = self.state
        item = self.case.item(st.pending)  # type: ignore[arg-type]
        assert item is not None and action.ground is not None
        objector = st.ledgers[side]
        presenter = st.ledgers[item.owner]
        objector.charge(OBJECTION_COST)
        objector.objections += 1
        sustained, rule = self.judge.rule_on_objection(item, action.ground)
        rules = [rule]
        if sustained:
            st.excluded.append(item.id)
            presenter.excluded += 1
            objector.sustained += 1
            if action.ground in BAD_FAITH_GROUNDS:
                presenter.sanctions += SANCTION_BAD_FAITH_EVIDENCE
                rules.append(
                    RuleFiring(
                        rule_id="SANCTION-BF", detail=f"{item.owner.value} sanctioned for offering {item.id} in bad faith."
                    )
                )
        else:
            st.admitted.append(item.id)
            presenter.admitted += 1
            objector.overruled += 1
            objector.sanctions += SANCTION_OVERRULED_OBJECTION
            rules.append(
                RuleFiring(
                    rule_id="SANCTION-OVR",
                    detail=f"Overruled objection costs {side.value} {SANCTION_OVERRULED_OBJECTION} sanction points.",
                )
            )
        st.pending = None
        self._perceived = None
        self._emit(
            EventKind.RULING,
            f"Objection ({action.ground.value}) by {side.value}: {'SUSTAINED, ' + item.id + ' excluded' if sustained else 'OVERRULED, ' + item.id + ' admitted'}.",
            side,
            action,
            rules,
            subject=item.id,
            status="excluded" if sustained else "admitted",
        )
        if not sustained:
            self._after_admission(item)

    def _admit_pending(self, waived: bool) -> None:
        st = self.state
        if st.pending is None:
            return
        item = self.case.item(st.pending)
        assert item is not None
        st.admitted.append(item.id)
        st.ledgers[item.owner].admitted += 1
        st.pending = None
        self._perceived = None
        self._emit(
            EventKind.RULING,
            f"{item.id} admitted without objection.",
            rules=[RuleFiring(rule_id="ADM-WAIVER", detail=f"No (valid) objection to {item.id}; any defect is waived.")],
            subject=item.id,
            status="admitted",
        )
        self._after_admission(item)

    def _rest(self, side: Side, forced: RuleFiring | None) -> None:
        st = self.state
        if st.pending is not None:  # defensive: never strand a pending item
            self._admit_pending(waived=True)
        if forced is not None:
            self._emit(EventKind.RULING, f"{side.value} is deemed to have rested.", side, rules=[forced])
        st.rest(side)
        if st.phase_is_over():
            self._enter(st.next_phase_after_rest(), f"{side.value} rested.")
        else:
            # The other side is still going, so the phase continues without this one.
            self._emit(EventKind.RULING, f"{side.value} has finished presenting; {side.opponent.value} continues.", side)

    def _directed_verdict_review(self, moved: bool) -> None:
        st = self.state
        granted, element, rules = self.judge.directed_verdict_review(st.admitted, st.impeachments, moved)
        st.directed = (granted, element)
        self._emit(
            EventKind.DIRECTED_VERDICT,
            f"Directed verdict {'GRANTED on ' + str(element) if granted else 'denied'}.",
            rules=rules,
        )
        self._enter(Phase.DELIBERATION if granted else Phase.DEFENSE_CASE, "")

    # ------------------------------------------------------------------ verdict

    def _deliberate(self) -> TrialResult:
        st = self.state
        if st.phase is not Phase.DELIBERATION:
            st.enter(Phase.DELIBERATION)
        self._report_unapplied_injections()
        self._report_unapplied_pushes()
        verdict: Verdict = self.judge.deliberate(st.admitted, st.impeachments, st.directed)
        self._emit(
            EventKind.VERDICT,
            f"VERDICT: {verdict.outcome.value.upper().replace('_', ' ')}. {verdict.reason}",
            rules=verdict.rules,
        )
        st.enter(Phase.CLOSED)
        ledgers = {s: st.ledgers[s].freeze() for s in Side}
        return TrialResult(
            case_id=self.case.id,
            case_title=self.case.title,
            seed=self.seed,
            prosecution_strategy=self.strategy_names[Side.PROSECUTION],
            defense_strategy=self.strategy_names[Side.DEFENSE],
            events=tuple(self._events),
            verdict=verdict,
            ledgers=ledgers,
            utilities=utilities(verdict.outcome, ledgers),
            digest=self._last_hash,
            graph=self._graph(verdict),
            injections=self._requested,
            adverse_pushes=self._requested_pushes,
        )

    def _graph(self, verdict: Verdict) -> EvidenceGraph:
        st = self.state
        weight: dict[str, float] = {}
        for es in verdict.snapshot.elements:
            for c in es.contributions:
                if c.counted:
                    weight[c.evidence_id] = round(weight.get(c.evidence_id, 0.0) + abs(c.log_odds), 4)
        nodes = tuple(
            GraphNode(
                id=i.id,
                label=i.title,
                owner=i.owner,
                kind=i.kind,
                status="admitted" if i.id in st.admitted else "excluded" if i.id in st.excluded else "unpresented",
                weight=weight.get(i.id, 0.0),
            )
            for i in self.case.evidence
        )
        edges = [GraphEdge(source=a, target=b, relation="contradicts") for a, b in self.case.contradiction_edges()]
        admitted = [i for i in self.case.evidence if i.id in st.admitted]
        for x_idx, x in enumerate(admitted):
            for y in admitted[x_idx + 1 :]:
                if x.fact_id == y.fact_id:
                    continue
                if any(
                    x.support.get(e, 0) * y.support.get(e, 0) > 0 and min(abs(x.support[e]), abs(y.support[e])) >= 0.5
                    for e in x.support
                ):
                    edges.append(GraphEdge(source=x.id, target=y.id, relation="corroborates"))
        return EvidenceGraph(nodes=nodes, edges=tuple(edges))


def _plan_injections(case: CaseFile, injections: Sequence[Injection]) -> tuple[list[Injection], list[CaseFile]]:
    """Order the injections and validate each cumulative case up front.

    Doing it before the trial starts means a bad exhibit (duplicate id, unknown element, a
    contradiction with something that does not exist) is refused with a clear message instead of
    failing halfway through a trial, and the case after each injection is ready to swap in.
    """
    ordered = sorted(injections, key=lambda i: (i.at_seq, i.item.id))
    cases: list[CaseFile] = []
    current = case
    for inj in ordered:
        helps_prosecution = [k for k, v in inj.item.support.items() if v > 0]
        if inj.item.owner is Side.DEFENSE and helps_prosecution:
            # The directed-verdict review is sound only because defense evidence can never raise an
            # element's log-odds (see DEVIATIONS D5/D6). An injected exhibit must not reopen that.
            raise ValueError(
                f"injected exhibit {inj.item.id!r} is defense evidence with positive support for "
                f"{helps_prosecution}; a defense exhibit may only help the defense"
            )
        try:
            current = CaseFile.model_validate(
                {**current.model_dump(mode="json"), "evidence": [*(e.model_dump(mode="json") for e in current.evidence), inj.item.model_dump(mode="json")]}
            )
        except ValueError as exc:
            raise ValueError(f"injected exhibit {inj.item.id!r} does not fit this case: {exc}") from exc
        cases.append(current)
    return list(ordered), cases


def _plan_pushes(case: CaseFile, pushes: Sequence[AdversePush]) -> list[AdversePush]:
    """Order the pushes and refuse any that name something that cannot be affected, before the trial starts."""
    ordered = sorted(pushes, key=lambda p: (p.at_seq, p.kind, p.target))
    for push in ordered:
        if push.kind == "hostile":
            if case.witness(push.target) is None:
                raise ValueError(f"adverse push: {push.target!r} is not a witness in this case")
            continue
        item = case.item(push.target)
        if item is None:
            raise ValueError(f"adverse push: {push.target!r} is not an exhibit in this case")
        if push.kind == "no_show" and item.witness_id is None:
            raise ValueError(f"adverse push: {push.target!r} has no witness, so there is no one to fail to appear")
        if push.kind == "missing_certificate" and item.kind is not EvidenceKind.DIGITAL_LOG:
            raise ValueError(f"adverse push: {push.target!r} is not a digital record, so it needs no section 65B certificate")
    return ordered


def run_trial(
    case: CaseFile,
    prosecution: str,
    defense: str,
    seed: int = 0,
    injections: Sequence[Injection] = (),
    adverse_pushes: Sequence[AdversePush] = (),
) -> TrialResult:
    """Convenience entry point used by the CLI, API, and tournament."""
    p_agent = make_agent(prosecution, random.Random(f"{seed}:agent:prosecution"))
    d_agent = make_agent(defense, random.Random(f"{seed}:agent:defense"))
    return Court(case, p_agent, d_agent, seed, prosecution, defense, injections=injections, adverse_pushes=adverse_pushes).run()


def replay_trial(result: TrialResult, case: CaseFile) -> TrialResult:
    """Re-run a finished trial from nothing but its recorded inputs, injections included."""
    return run_trial(
        case, result.prosecution_strategy, result.defense_strategy, result.seed, result.injections, result.adverse_pushes
    )


def verify_injections(result: TrialResult) -> bool:
    """Whether every injection recorded in ``result`` is the exhibit the hash chain committed to.

    ``result.injections`` is every injection that was *requested*, applied or not, because a replay
    needs all of its inputs: an injection that arrived too late still shaped the trial by producing
    an INJ-2 event. The chain hashes events, and both INJ-1 (applied) and INJ-2 (not reached) carry
    the exhibit's SHA-256. Editing an exhibit afterwards leaves the chain valid but fails this check,
    and editing the event itself fails ``verify_chain``.
    """
    committed = {
        ev.subject: ru.detail
        for ev in result.events
        for ru in ev.rules
        if ru.rule_id in {"INJ-1", "INJ-2"}
    }
    if set(committed) != {i.item.id for i in result.injections}:
        return False
    return all(digest_item(i.item) in committed[i.item.id] for i in result.injections)
