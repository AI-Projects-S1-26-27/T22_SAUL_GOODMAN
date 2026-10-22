"""Procedural finite-state machine and party ledgers.

Owner: Engineer 2 (Procedure & Objection Arbiter).

The state object is the only mutable thing in a trial. It knows *whose turn it
is* and *what is legal*, but nothing about evidentiary weight (that belongs to
the judge).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from courtroom.contracts import CaseFile, EvidenceKind, ExamGround, Ledger, Phase, Side, Window

# Phases in which a party puts on evidence. EVIDENCE alternates between both sides;
# the other two are single-party continuations, so they name their one actor.
CASE_PHASES: dict[Phase, Side | None] = {
    Phase.EVIDENCE: None,  # alternating
    Phase.DEFENSE_CASE: Side.DEFENSE,
    Phase.REBUTTAL: Side.PROSECUTION,
}
EXAM_ACTIONS = frozenset({"examine", "cross_examine"})  # legal only under CaseFile.rules.witnesses
EXAM_PHASES = frozenset({Phase.EVIDENCE, Phase.DEFENSE_CASE})  # never rebuttal: it is scope-limited
PRIMARY_ACTIONS = frozenset({"present_evidence", "impeach", "pass", "rest"}) | EXAM_ACTIONS
RESPONSE_ACTIONS = frozenset({"object", "pass"})
MOTION_ACTIONS = frozenset({"motion_directed_verdict", "pass"})
ALLOWED: dict[Window, frozenset[str]] = {
    "primary": PRIMARY_ACTIONS,
    "response": RESPONSE_ACTIONS,
    "motion": MOTION_ACTIONS,
}
STALL_LIMIT = 2  # consecutive primary passes deemed a rest


@dataclass
class MutableLedger:
    side: Side
    budget_start: float
    budget: float
    spent: float = 0.0
    sanctions: float = 0.0
    violations: int = 0
    presented: int = 0
    admitted: int = 0
    excluded: int = 0
    objections: int = 0
    sustained: int = 0
    overruled: int = 0
    impeachments: int = 0
    response_windows: int = 0

    def charge(self, amount: float) -> float:
        """Spend up to ``amount``; returns what was actually charged (never negative budget)."""
        paid = min(amount, self.budget)
        self.budget = round(self.budget - paid, 6)
        self.spent = round(self.spent + paid, 6)
        return paid

    def freeze(self) -> Ledger:
        return Ledger(
            side=self.side,
            budget_start=self.budget_start,
            budget=self.budget,
            spent=self.spent,
            sanctions=self.sanctions,
            violations=self.violations,
            presented=self.presented,
            admitted=self.admitted,
            excluded=self.excluded,
            objections=self.objections,
            sustained=self.sustained,
            overruled=self.overruled,
            impeachments=self.impeachments,
        )


@dataclass
class ProcedureState:
    case: CaseFile
    phase: Phase = Phase.OPENING
    pending: str | None = None  # evidence id awaiting a response window
    presented: list[str] = field(default_factory=list)
    admitted: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    impeachments: dict[str, int] = field(default_factory=dict)
    used_impeachments: set[tuple[str, str]] = field(default_factory=set)
    exposures: list[tuple[str, ExamGround]] = field(default_factory=list)  # successful cross-examinations, in order
    used_crosses: set[tuple[str, ExamGround]] = field(default_factory=set)
    used_examines: set[str] = field(default_factory=set)
    hostile: set[str] = field(default_factory=set)  # witnesses who turned hostile (adverse events only)
    turns_used: dict[tuple[Phase, Side], int] = field(default_factory=dict)
    passes: dict[Side, int] = field(default_factory=dict)  # consecutive primary passes, per side
    rested: set[Side] = field(default_factory=set)
    last_primary: Side | None = None  # who took the last primary turn, so EVIDENCE can alternate
    motion_made: bool = False
    directed: tuple[bool, str | None] = (False, None)
    ledgers: dict[Side, MutableLedger] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.ledgers:
            self.ledgers = {s: MutableLedger(side=s, budget_start=self.case.budget, budget=self.case.budget) for s in Side}

    # ------------------------------------------------------------------ turn logic

    def pending_owner(self) -> Side | None:
        """Who offered the item awaiting a response (the validator guarantees owner == actor)."""
        item = self.case.item(self.pending) if self.pending else None
        return item.owner if item else None

    def expected(self) -> tuple[Side, Window] | None:
        """Who must act next and in which window, or ``None`` if the judge acts."""
        if self.phase in CASE_PHASES:
            if self.pending:
                owner = self.pending_owner()
                lead = CASE_PHASES[self.phase]
                # The non-offering side answers; fall back to the phase lead's opponent.
                return ((owner or (lead or Side.PROSECUTION)).opponent, "response")
            return (self.next_primary_side(), "primary")
        if self.phase is Phase.DIRECTED_VERDICT_REVIEW:
            return (Side.DEFENSE, "motion")
        return None

    def next_primary_side(self) -> Side:
        """Whose primary turn it is.

        EVIDENCE alternates: the side that did not take the last primary turn goes next,
        unless it has rested. Single-party phases always return their one actor.
        """
        lead = CASE_PHASES.get(self.phase)
        if lead is not None:
            return lead
        other = self.last_primary.opponent if self.last_primary else Side.PROSECUTION
        if other not in self.rested:
            return other
        return other.opponent

    def active_sides(self) -> set[Side]:
        """Sides that may still take a primary turn in this phase."""
        lead = CASE_PHASES.get(self.phase)
        sides = {lead} if lead is not None else set(Side)
        return {s for s in sides if s not in self.rested}

    def turn_cap(self, phase: Phase | None = None) -> int:
        phase = phase or self.phase
        return self.case.rebuttal_turns if phase is Phase.REBUTTAL else self.case.max_primary_turns

    def turns_left(self, side: Side | None = None) -> int:
        """Turns left for ``side`` in this phase. Caps are per side, not shared."""
        side = side or self.next_primary_side()
        return max(0, self.turn_cap() - self.turns_used.get((self.phase, side), 0))

    def consume_primary_turn(self, side: Side) -> None:
        key = (self.phase, side)
        self.turns_used[key] = self.turns_used.get(key, 0) + 1
        self.last_primary = side

    def rest(self, side: Side) -> None:
        self.rested.add(side)
        self.passes[side] = 0

    def next_phase_after_rest(self) -> Phase:
        """The phase to enter once the current one has no one left who can act."""
        match self.phase:
            case Phase.EVIDENCE:
                # The prosecution is finished, so nothing can raise L_e any further:
                # exactly the premise the directed-verdict review needs.
                return Phase.DIRECTED_VERDICT_REVIEW
            case Phase.DEFENSE_CASE:
                return Phase.REBUTTAL if self.case.rebuttal_turns > 0 else Phase.DELIBERATION
            case _:
                return Phase.DELIBERATION

    def phase_is_over(self) -> bool:
        """Whether the current evidence phase has run out of participants.

        EVIDENCE ends the moment the PROSECUTION is finished, even if the defense would
        still like to present: everything after this point can only lower L_e, which is
        precisely what makes the directed-verdict review sound.
        """
        if self.phase is Phase.EVIDENCE:
            return Side.PROSECUTION in self.rested
        return not self.active_sides()

    def enter(self, phase: Phase) -> None:
        self.phase = phase
        self.pending = None
        self.last_primary = None
        self.passes = {}
        # ``rested`` persists: a side that finished in EVIDENCE does not get another
        # primary turn later. Rebuttal is the one exception the proposal grants, a fresh
        # scope-limited opportunity for the prosecution.
        if phase is Phase.REBUTTAL:
            self.rested.discard(Side.PROSECUTION)

    # ------------------------------------------------------------------ record queries

    def testified_witnesses(self, side: Side) -> tuple[str, ...]:
        """Witnesses whose testimony for ``side`` has been admitted."""
        out: set[str] = set()
        for eid in self.admitted:
            item = self.case.item(eid)
            if item and item.owner is side and item.kind is EvidenceKind.TESTIMONY and item.witness_id:
                out.add(item.witness_id)
        return tuple(sorted(out))

    def exam_options(self, side: Side) -> tuple[tuple[str, ExamGround], ...]:
        """(opposing witness, ground) pairs ``side`` may still cross-examine on."""
        if not self.case.witness_examination or self.phase not in EXAM_PHASES:
            return ()
        return tuple(
            (w, g) for w in self.testified_witnesses(side.opponent) for g in ExamGround if (w, g) not in self.used_crosses
        )

    def examine_options(self, side: Side) -> tuple[str, ...]:
        """Own witnesses that may still be examined directly."""
        if not self.case.witness_examination or self.phase not in EXAM_PHASES:
            return ()
        return tuple(w for w in self.testified_witnesses(side) if w not in self.used_examines)

    def exposed_grounds(self, witness_id: str) -> tuple[ExamGround, ...]:
        return tuple(g for w, g in self.exposures if w == witness_id)

    def rebuttal_targets(self) -> tuple[str, ...]:
        """Prosecution items that may be offered in rebuttal: those contradicting admitted defense evidence."""
        admitted_defense = {eid for eid in self.admitted if (it := self.case.item(eid)) is not None and it.owner is Side.DEFENSE}
        targets = set()
        for a, b in self.case.contradiction_edges():
            for mine, theirs in ((a, b), (b, a)):
                item = self.case.item(mine)
                if item and item.owner is Side.PROSECUTION and theirs in admitted_defense and mine not in self.presented:
                    targets.add(mine)
        return tuple(sorted(targets))
