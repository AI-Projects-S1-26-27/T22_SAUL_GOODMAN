"""Pydantic v2 data contracts shared by every subsystem.

Owner: Engineer 1 (Contracts & Case Library).

Rules for this module:
* Pure data. No behaviour beyond validation and trivial derived properties.
* Every model is frozen; mutation happens only by constructing new objects.
* Numbers that feed the judge are floats with <= 4 decimals so they convert
  exactly to rationals via ``Fraction(repr(x))``.
"""

from __future__ import annotations

from enum import StrEnum
from fractions import Fraction
from typing import Literal

__all__ = [
    "DEFAULT_COST",
    "Action",
    "ActionType",
    "AdversePush",
    "CaseFile",
    "CaseType",
    "Contribution",
    "ElementScore",
    "EventKind",
    "EvidenceGraph",
    "EvidenceItem",
    "EvidenceKind",
    "ExamGround",
    "Frozen",
    "GraphEdge",
    "GraphNode",
    "Injection",
    "Ledger",
    "LegalElement",
    "ObjectionGround",
    "PartyView",
    "PerceivedItem",
    "Phase",
    "RuleFiring",
    "RuleSet",
    "ScoreSnapshot",
    "Side",
    "StandardOfProof",
    "TrialEvent",
    "TrialResult",
    "Verdict",
    "VerdictOutcome",
    "Window",
    "Witness",
]

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --------------------------------------------------------------------------- enums


class Side(StrEnum):
    PROSECUTION = "prosecution"
    DEFENSE = "defense"

    @property
    def opponent(self) -> Side:
        return Side.DEFENSE if self is Side.PROSECUTION else Side.PROSECUTION


class CaseType(StrEnum):
    CRIMINAL = "criminal"
    CIVIL = "civil"


class StandardOfProof(StrEnum):
    BEYOND_REASONABLE_DOUBT = "beyond_reasonable_doubt"
    CLEAR_AND_CONVINCING = "clear_and_convincing"
    PREPONDERANCE = "preponderance"


class EvidenceKind(StrEnum):
    DOCUMENT = "document"
    DIGITAL_LOG = "digital_log"
    PHYSICAL = "physical"
    FINANCIAL_RECORD = "financial_record"
    TESTIMONY = "testimony"
    EXPERT = "expert"


class ObjectionGround(StrEnum):
    HEARSAY = "hearsay"
    RELEVANCE = "relevance"
    AUTHENTICATION = "authentication"
    ILLEGALLY_OBTAINED = "illegally_obtained"
    LATE_DISCLOSURE = "late_disclosure"
    SPECULATION = "speculation"


class ExamGround(StrEnum):
    """What a cross-examiner attacks. Deliberately NOT part of ``ObjectionGround``: the perception
    channel and the chaos fuzzer iterate that enum, so a new member there would change every digest."""

    QUALIFICATIONS = "qualifications"
    BIAS = "bias"
    INCONSISTENCY = "inconsistency"


class Phase(StrEnum):
    OPENING = "opening"
    # Both sides alternate here. The phase ends when the PROSECUTION can present no more,
    # which is what makes the directed-verdict review sound (see judge.directed_verdict_review).
    EVIDENCE = "evidence"
    DIRECTED_VERDICT_REVIEW = "directed_verdict_review"
    DEFENSE_CASE = "defense_case"  # defense alone, if it had not already rested
    REBUTTAL = "rebuttal"
    DELIBERATION = "deliberation"
    CLOSED = "closed"
    PROSECUTION_CASE = "prosecution_case"  # retired: kept so older exported bundles still parse


class ActionType(StrEnum):
    PRESENT_EVIDENCE = "present_evidence"
    OBJECT = "object"
    IMPEACH = "impeach"
    MOTION_DIRECTED_VERDICT = "motion_directed_verdict"
    PASS = "pass"
    REST = "rest"
    # Only legal under ``RuleSet.witnesses``; with the flag off the validator refuses them (V-WINDOW).
    EXAMINE = "examine"
    CROSS_EXAMINE = "cross_examine"


class EventKind(StrEnum):
    PHASE_CHANGE = "phase_change"
    ACTION = "action"
    RULING = "ruling"
    VIOLATION = "violation"
    DIRECTED_VERDICT = "directed_verdict"
    WATCHDOG = "watchdog"
    VERDICT = "verdict"
    INJECTION = "injection"  # evidence added to a party's hand mid-trial; see Injection
    EXAMINATION = "examination"  # a witness examined or cross-examined; only under RuleSet.witnesses
    ADVERSE = "adverse"  # a seeded adverse event; only under RuleSet.adverse_events


class VerdictOutcome(StrEnum):
    GUILTY = "guilty"
    NOT_GUILTY = "not_guilty"
    LIABLE = "liable"
    NOT_LIABLE = "not_liable"
    DIRECTED_ACQUITTAL = "directed_acquittal"

    @property
    def favours(self) -> Side:
        return Side.PROSECUTION if self in (VerdictOutcome.GUILTY, VerdictOutcome.LIABLE) else Side.DEFENSE


Window = Literal["primary", "response", "motion"]

# Canonical per-kind presentation cost (litigation budget units).
DEFAULT_COST: dict[EvidenceKind, float] = {
    EvidenceKind.DOCUMENT: 1.0,
    EvidenceKind.DIGITAL_LOG: 1.0,
    EvidenceKind.PHYSICAL: 1.0,
    EvidenceKind.FINANCIAL_RECORD: 1.0,
    EvidenceKind.TESTIMONY: 1.5,
    EvidenceKind.EXPERT: 2.0,
}


def _four_decimals(v: float) -> float:
    if round(v, 4) != v:
        raise ValueError(f"{v!r} has more than 4 decimals; judge inputs must be exact decimals")
    return v


# --------------------------------------------------------------------------- case file


class LegalElement(Frozen):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    description: str


class Witness(Frozen):
    id: str = Field(pattern=r"^[A-Za-z0-9_\-]+$")
    name: str
    role: str
    credibility: float = Field(ge=0.0, le=1.0)
    bias_note: str | None = None
    # Hidden flaws, the witness analogue of an exhibit's defect flags. They matter only under
    # ``RuleSet.witnesses``; the defaults make every existing witness flawless, so no existing case moves.
    qualified: bool = True  # False: the witness is not qualified to give the opinion offered
    impartial: bool = True  # False: undisclosed interest in the outcome
    consistent: bool = True  # False: a prior statement contradicts the testimony

    @field_validator("credibility")
    @classmethod
    def _exact_credibility(cls, v: float) -> float:
        return _four_decimals(v)


class EvidenceItem(Frozen):
    id: str = Field(pattern=r"^[A-Za-z0-9_\-]+$")
    title: str
    description: str
    kind: EvidenceKind
    owner: Side
    fact_id: str
    support: dict[str, float]
    reliability: float = Field(ge=0.0, le=1.0)
    witness_id: str | None = None
    hearsay: bool = False
    authenticated: bool = True
    lawfully_obtained: bool = True
    disclosed: bool = True
    personal_knowledge: bool = True
    contradicts: tuple[str, ...] = ()
    impeaches: tuple[str, ...] = ()
    cost: float | None = Field(default=None, ge=0.0)

    @field_validator("reliability")
    @classmethod
    def _exact_reliability(cls, v: float) -> float:
        return _four_decimals(v)

    @field_validator("support")
    @classmethod
    def _support_range(cls, v: dict[str, float]) -> dict[str, float]:
        for key, val in v.items():
            if not -1.0 <= val <= 1.0:
                raise ValueError(f"support[{key}]={val} outside [-1, 1]")
            _four_decimals(val)
        return v

    @model_validator(mode="after")
    def _testimony_needs_witness(self) -> EvidenceItem:
        if self.kind is EvidenceKind.TESTIMONY and self.witness_id is None:
            raise ValueError(f"testimony {self.id} must reference a witness")
        return self

    @property
    def presentation_cost(self) -> float:
        return self.cost if self.cost is not None else DEFAULT_COST[self.kind]


class RuleSet(Frozen):
    """Optional rule extensions. ``CaseFile.rules is None`` means the certified rulebook, bit for bit."""

    witnesses: bool = False  # direct and cross-examination of witnesses (DEVIATIONS D13)
    # Seeded adverse events (DEVIATIONS D15): a witness fails to appear, a digital record is excluded for a
    # missing section 65B certificate, a witness turns hostile. Each rate is a probability per opportunity.
    adverse_events: bool = False
    no_show: float = Field(default=0.10, ge=0.0, le=1.0)
    missing_certificate: float = Field(default=0.15, ge=0.0, le=1.0)
    hostile: float = Field(default=0.10, ge=0.0, le=1.0)
    # What a hostile witness's credibility is multiplied by, as an exact rational ("1/4"). A field, not a module
    # constant, so a sweep can vary it in worker processes without patching anything.
    hostile_credibility: str = Field(default="1/4", pattern=r"^\d{1,3}(/\d{1,3})?$")

    @field_validator("hostile_credibility")
    @classmethod
    def _factor_in_unit_interval(cls, v: str) -> str:
        try:
            f = Fraction(v)
        except (ValueError, ZeroDivisionError):
            raise ValueError(f"hostile_credibility {v!r} is not a rational number") from None
        if not Fraction(0) <= f <= Fraction(1):
            raise ValueError("hostile_credibility must lie between 0 and 1")
        return v


class CaseFile(Frozen):
    id: str = Field(pattern=r"^[a-z0-9_\-]+$")
    title: str
    synopsis: str
    case_type: CaseType
    standard: StandardOfProof
    charge: str
    elements: tuple[LegalElement, ...] = Field(min_length=1)
    witnesses: tuple[Witness, ...] = ()
    evidence: tuple[EvidenceItem, ...] = ()
    budget: float = Field(default=10.0, gt=0)
    max_primary_turns: int = Field(default=8, ge=1, le=64)
    rebuttal_turns: int = Field(default=2, ge=0, le=16)
    perception_accuracy: float = Field(default=0.8, ge=0.5, le=1.0)
    tags: tuple[str, ...] = ()
    # The proof standard's bar is a game parameter, not a constant of nature. ``None`` (every
    # library case, and the only path the certified analysis uses) means "the standard's own
    # bar". Otherwise an exact rational in log-odds, written "11/5" or "2.1972"; the standard
    # still decides whether a tie passes (strict for preponderance, inclusive otherwise).
    bar_log_odds: str | None = Field(default=None, pattern=r"^(\d{1,2}(\.\d{1,6})?|\d{1,4}/\d{1,4})$")
    rules: RuleSet | None = None

    @property
    def witness_examination(self) -> bool:
        return self.rules is not None and self.rules.witnesses

    @property
    def adverse_events(self) -> bool:
        return self.rules is not None and self.rules.adverse_events

    @field_validator("bar_log_odds")
    @classmethod
    def _bar_is_a_sane_rational(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            bar = Fraction(v)
        except (ValueError, ZeroDivisionError):
            raise ValueError(f"bar_log_odds {v!r} is not a rational number") from None
        # 0 is "more likely than not"; 7 is about 99.9%. Below 0 would let a case be proven
        # when it is less likely than not, and above 7 nothing could ever be proven.
        if not Fraction(0) <= bar <= Fraction(7):
            raise ValueError("bar_log_odds must lie between 0 (50%) and 7 (about 99.9%)")
        return v

    @model_validator(mode="after")
    def _referential_integrity(self) -> CaseFile:
        element_ids = {e.id for e in self.elements}
        witness_ids = {w.id for w in self.witnesses}
        evidence_ids = [e.id for e in self.evidence]
        if len(element_ids) != len(self.elements):
            raise ValueError("duplicate element ids")
        if len(witness_ids) != len(self.witnesses):
            raise ValueError("duplicate witness ids")
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("duplicate evidence ids")
        known = set(evidence_ids)
        for item in self.evidence:
            unknown_elements = set(item.support) - element_ids
            if unknown_elements:
                raise ValueError(f"{item.id} supports unknown elements {sorted(unknown_elements)}")
            if item.witness_id is not None and item.witness_id not in witness_ids:
                raise ValueError(f"{item.id} references unknown witness {item.witness_id}")
            for other in item.contradicts:
                if other == item.id or other not in known:
                    raise ValueError(f"{item.id} contradicts invalid item {other}")
            for w in item.impeaches:
                if w not in witness_ids:
                    raise ValueError(f"{item.id} impeaches unknown witness {w}")
        return self

    # Convenience lookups (pure).
    def item(self, evidence_id: str) -> EvidenceItem | None:
        return next((e for e in self.evidence if e.id == evidence_id), None)

    def witness(self, witness_id: str) -> Witness | None:
        return next((w for w in self.witnesses if w.id == witness_id), None)

    def contradiction_edges(self) -> list[tuple[str, str]]:
        """Undirected, deduplicated, sorted contradiction edges."""
        edges = {tuple(sorted((i.id, j))) for i in self.evidence for j in i.contradicts}
        return sorted((a, b) for a, b in edges)


class Injection(Frozen):
    """An exhibit added to its owner's hand once the trial has produced ``at_seq`` events.

    It lives on the trial *result*, not on the event: ``TrialEvent`` is hashed field by field, so a
    new event field would change every digest ever produced. The chain commits to the item instead
    through the content hash carried in the injection event's rule firing (``INJ-1``), which
    ``engine.verify_injections`` checks. Re-running with ``result.injections`` reproduces the trial.
    """

    at_seq: int = Field(ge=1, le=10_000)
    item: EvidenceItem


class AdversePush(Frozen):
    """An adverse event the examiner pushes into a trial once it has produced ``at_seq`` events.

    Like ``Injection`` it lives on the trial *result*, never on the hashed event, so no digest moves. It is
    forced, not drawn: ``no_show`` and ``missing_certificate`` name an exhibit that has not been offered yet and
    take effect when its owner offers it; ``hostile`` names a witness and takes effect now if the witness has
    already testified, or on admission otherwise. The announcement is a logged event in the hash chain, and
    both sides can see it.
    """

    at_seq: int = Field(ge=1, le=10_000)
    kind: Literal["no_show", "missing_certificate", "hostile"]
    target: str = Field(pattern=r"^[A-Za-z0-9_\-]+$")


# --------------------------------------------------------------------------- actions


class Action(Frozen):
    """An agent's requested move. Deliberately permissive: bad-faith or malformed
    actions must be *representable* so the procedure layer can reject and penalise
    them instead of crashing."""

    actor: Side
    type: ActionType
    evidence_id: str | None = None
    witness_id: str | None = None
    ground: ObjectionGround | ExamGround | None = None
    rationale: str = ""


# --------------------------------------------------------------------------- judge output


class RuleFiring(Frozen):
    rule_id: str
    detail: str


class Contribution(Frozen):
    evidence_id: str
    element_id: str
    support: float
    strength: float
    contradiction_discount: float
    corroboration_factor: float
    weight: float
    log_odds: float
    counted: bool  # False when superseded by a stronger item on the same fact


class ElementScore(Frozen):
    element_id: str
    log_odds: str  # exact rational, e.g. "11/5"
    log_odds_float: float
    probability: float
    threshold: str
    threshold_probability: float
    met: bool
    contributions: tuple[Contribution, ...]


class ScoreSnapshot(Frozen):
    elements: tuple[ElementScore, ...]
    burden_index: float  # probability of the weakest element
    weakest_element: str
    all_met: bool


class Verdict(Frozen):
    outcome: VerdictOutcome
    reason: str
    decisive_element: str | None
    snapshot: ScoreSnapshot
    rules: tuple[RuleFiring, ...]


# --------------------------------------------------------------------------- agent view


class PerceivedItem(Frozen):
    """An opponent item as seen through the noisy perception channel."""

    evidence_id: str
    title: str
    kind: EvidenceKind
    support: dict[str, float]
    defect_belief: dict[ObjectionGround, float]


class PartyView(Frozen):
    side: Side
    phase: Phase
    window: Window
    case_id: str
    case_type: CaseType
    standard: StandardOfProof
    element_ids: tuple[str, ...]
    own_evidence: tuple[EvidenceItem, ...]
    presented: tuple[str, ...]
    admitted: tuple[str, ...]
    excluded: tuple[str, ...]
    pending: PerceivedItem | None
    snapshot: ScoreSnapshot
    budget: float
    reserve_basis: float  # starting budget
    opponent_budget: float
    turns_left: int
    impeachment_options: tuple[tuple[str, str], ...]  # (own item id, opposing witness id), unused and testified
    rebuttal_targets: tuple[str, ...]
    opponent_objections: int
    opponent_response_windows: int
    # Witness examination (empty unless the case enables it). ``exam_options`` are (opposing witness,
    # ground) pairs still open; ``witness_beliefs`` is the noisy posterior that each flaw is real.
    examine_options: tuple[str, ...] = ()
    exam_options: tuple[tuple[str, str], ...] = ()
    witness_beliefs: dict[str, dict[str, float]] = Field(default_factory=dict)
    own_exposures: tuple[tuple[str, str], ...] = ()  # (own witness, ground of its latest exposure), public record
    adverse: dict[str, float] = Field(default_factory=dict)  # the case's published adverse-event rates; empty if off
    known_adverse: tuple[str, ...] = ()  # pushed events announced in court, "<kind>:<target>"; public to both sides


# --------------------------------------------------------------------------- trial record


class Ledger(Frozen):
    side: Side
    budget_start: float
    budget: float
    spent: float
    sanctions: float
    violations: int
    presented: int
    admitted: int
    excluded: int
    objections: int
    sustained: int
    overruled: int
    impeachments: int


class TrialEvent(Frozen):
    seq: int
    phase: Phase
    kind: EventKind
    actor: Side | None = None
    action: Action | None = None
    summary: str
    subject: str | None = None  # evidence id this event is about, if any
    status: Literal["offered", "admitted", "excluded", "impeached", "injected", "exposed", "unfounded", "rehabilitated", "no_show", "no_certificate", "hostile", "announced", "not_applied"] | None = None
    rules: tuple[RuleFiring, ...] = ()
    burden_index: float | None = None
    element_probabilities: dict[str, float] = Field(default_factory=dict)
    prev_hash: str = ""
    hash: str = ""


class GraphNode(Frozen):
    id: str
    label: str
    owner: Side
    kind: EvidenceKind
    status: Literal["unpresented", "admitted", "excluded"]
    weight: float


class GraphEdge(Frozen):
    source: str
    target: str
    relation: Literal["contradicts", "corroborates"]


class EvidenceGraph(Frozen):
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]


class TrialResult(Frozen):
    case_id: str
    case_title: str
    seed: int
    prosecution_strategy: str
    defense_strategy: str
    events: tuple[TrialEvent, ...]
    verdict: Verdict
    ledgers: dict[Side, Ledger]
    utilities: dict[Side, float]
    digest: str
    graph: EvidenceGraph
    injections: tuple[Injection, ...] = ()  # every injection requested, in order, applied or not
    adverse_pushes: tuple[AdversePush, ...] = ()  # every adverse push requested, in order, applied or not
