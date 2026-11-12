"""The AI lawyer: a language model choosing among the legal moves, as an opponent for the hand-written styles.

It is an exhibition only. Its trials are marked non-certified and it never enters a payoff matrix (see docs/LLM_ROLE.md).

It plays through exactly the interface every other agent uses: a ``PartyView`` and a read-only
``Oracle``. It therefore sees the same noisy defect posteriors as anyone else and cannot reach
an exhibit's true flags or the opponent's hand. ``test_llm_policy_prompt_sees_no_more_than_the_view``
enforces that.

Legality is structural. The policy enumerates the legal actions itself and asks the model for an
*index into that list*, with a JSON schema constraining the answer, so an illegal move cannot be
expressed. What can still go wrong is an out-of-range or unparseable index; that is re-prompted
up to ``MAX_REPROMPTS`` times and then falls back to the Adaptive policy. Every fallback is
counted, and the reason is kept.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field

from courtroom.agents.base import Oracle
from courtroom.agents.policies import ADAPTIVE, CounselAgent
from courtroom.contracts import Action, ActionType, ObjectionGround, PartyView, Phase, Side
from courtroom.llm.client import LLMClient

MAX_REPROMPTS = 2

SYSTEM = (
    "You are an attorney in a stylised courtroom game. You will be given the public record, "
    "your own budget and your own beliefs, and a numbered list of the moves available to you. "
    "Reply with JSON {\"choice\": <index>, \"reason\": \"<one short sentence>\"} naming the single move you judge best. "
    "Choose only from the list. The reason is one plain sentence about your strategy; do not state any fact about the "
    "case that is not in the record you were given."
)


def _describe(action: Action, view: PartyView, oracle: Oracle) -> str:
    match action.type:
        case ActionType.PRESENT_EVIDENCE:
            item = next(i for i in view.own_evidence if i.id == action.evidence_id)
            gain = oracle.gain(view.side, add=[item.id])
            return (
                f"Offer exhibit {item.id} ({item.kind.value}, costs {item.presentation_cost:g}): "
                f"{item.title}. Expected swing in your favour {gain:+.2f}."
            )
        case ActionType.OBJECT:
            ground = str(action.ground.value).replace("_", " ") if action.ground else "?"
            belief = view.pending.defect_belief.get(action.ground, 0.0) if view.pending and action.ground else 0.0
            return f"Object on the ground of {ground}. Your belief this flaw is real: {belief:.0%}. Costs 0.5."
        case ActionType.IMPEACH:
            gain = oracle.gain(view.side, impeach=action.witness_id)
            return (
                f"Challenge witness {action.witness_id} using {action.evidence_id} (costs 1.0). "
                f"Expected swing in your favour {gain:+.2f}."
            )
        case ActionType.MOTION_DIRECTED_VERDICT:
            return "Move for a directed verdict, asking the judge to end the trial now (costs 0.5)."
        case ActionType.REST:
            return "Rest: present nothing further."
        case ActionType.PASS:
            return "Do not object; let the exhibit in." if view.window == "response" else "Pass this turn."
    return action.type.value


def legal_actions(view: PartyView) -> list[Action]:
    """Every move the validator would accept right now, in a stable order."""
    side = view.side
    out: list[Action] = []
    if view.window == "response":
        for ground in ObjectionGround:
            if view.budget >= 0.5:
                out.append(Action(actor=side, type=ActionType.OBJECT, ground=ground, evidence_id=view.pending.evidence_id))
        out.append(Action(actor=side, type=ActionType.PASS))
        return out
    if view.window == "motion":
        if view.budget >= 0.5:
            out.append(Action(actor=side, type=ActionType.MOTION_DIRECTED_VERDICT))
        out.append(Action(actor=side, type=ActionType.PASS))
        return out

    for item in view.own_evidence:
        if item.id in view.presented or item.presentation_cost > view.budget:
            continue
        if view.phase is Phase.REBUTTAL and item.id not in view.rebuttal_targets:
            continue
        out.append(Action(actor=side, type=ActionType.PRESENT_EVIDENCE, evidence_id=item.id))
    if view.budget >= 1.0:
        for item_id, witness_id in view.impeachment_options:
            out.append(Action(actor=side, type=ActionType.IMPEACH, evidence_id=item_id, witness_id=witness_id))
    out.append(Action(actor=side, type=ActionType.REST))
    out.append(Action(actor=side, type=ActionType.PASS))
    return out


def build_prompt(view: PartyView, oracle: Oracle, options: list[Action], retry_note: str = "") -> str:
    role = "prosecution" if view.side is Side.PROSECUTION else "defense"
    lines = [
        f"You act for the {role}.",
        f"Stage: {view.phase.value.replace('_', ' ')}. Standard of proof: {view.standard.value.replace('_', ' ')}.",
        f"Your budget: {view.budget:.2f}. Opponent budget: {view.opponent_budget:.2f}. "
        f"Turns left this stage: {view.turns_left}.",
        "How sure the judge currently is of each point you must prove:",
    ]
    for element in view.snapshot.elements:
        lines.append(
            f"  - {element.element_id}: {element.probability:.0%} (needs {element.threshold_probability:.0%})"
        )
    lines.append(f"On the record: {len(view.admitted)} exhibits admitted, {len(view.excluded)} thrown out.")
    if view.pending is not None:
        beliefs = ", ".join(f"{g.value.replace('_', ' ')} {p:.0%}" for g, p in view.pending.defect_belief.items() if p > 0)
        lines.append(
            f"The other side has just offered {view.pending.evidence_id}: {view.pending.title}. "
            f"Your reading of its possible flaws: {beliefs or 'nothing stands out'}."
        )
    lines.append("")
    lines.append("Your available moves:")
    for index, action in enumerate(options):
        lines.append(f"  {index}. {_describe(action, view, oracle)}")
    if retry_note:
        lines.append("")
        lines.append(retry_note)
    lines.append("")
    lines.append(f'Reply with JSON {{"choice": <index between 0 and {len(options) - 1}>, "reason": "<one short sentence>"}}.')
    return "\n".join(lines)


@dataclass
class LLMAgent:
    """Chooses actions through a model call, falling back to Adaptive when it cannot."""

    client: LLMClient
    rng: random.Random = field(default_factory=random.Random)
    name: str = "llm"
    fallback_reasons: Counter[str] = field(default_factory=Counter)
    decisions: int = 0
    llm_decisions: int = 0
    trivial_decisions: int = 0  # only one legal move existed: no choice to make, not a fallback
    reprompts: int = 0
    _fallback: CounselAgent = field(init=False)

    def __post_init__(self) -> None:
        self._fallback = CounselAgent(ADAPTIVE, name="llm-fallback")

    def opening_statement(self, side: Side) -> str:
        return self._fallback.opening_statement(side)

    @property
    def choices(self) -> int:
        """Decisions where there was genuinely something to choose between."""
        return self.decisions - self.trivial_decisions

    @property
    def fallback_rate(self) -> float:
        """Share of real choices the model did not make.

        Measured over ``choices``, not ``decisions``. A turn with a single legal move is not a
        choice the model declined; counting those would have reported 27% where the true rate
        was 4%, and tripped a 30% alarm for a reason that has nothing to do with the model.
        """
        return round(1 - self.llm_decisions / self.choices, 4) if self.choices else 0.0

    def report(self) -> dict[str, object]:
        """What the page shows after the trial: how often the model actually chose."""
        return {
            "provider": self.client.last_source,
            "model": self.client.last_model,
            "decisions": self.decisions,
            "choices": self.choices,
            "model_choices": self.llm_decisions,
            "fallbacks": self.choices - self.llm_decisions,
            "fallback_rate": self.fallback_rate,
            "fallback_reasons": dict(self.fallback_reasons),
            "reprompts": self.reprompts,
        }

    def act(self, view: PartyView, oracle: Oracle) -> Action:
        self.decisions += 1
        options = legal_actions(view)
        if len(options) <= 1:
            # Nothing to decide, so no call is made and this is not counted as a fallback.
            self.trivial_decisions += 1
            return options[0] if options else Action(actor=view.side, type=ActionType.PASS)

        note = ""
        before = self._counters()
        for attempt in range(MAX_REPROMPTS + 1):
            answer = self.client.choose(SYSTEM, build_prompt(view, oracle, options, note), len(options))
            if answer is not None:
                index, reason = answer
                self.llm_decisions += 1
                chosen = options[index]
                # "[ai]" marks a line the UI shows as the lawyer's thinking. It is never spoken as a fact.
                return chosen.model_copy(update={"rationale": f"[ai] {reason or _describe(chosen, view, oracle)}"})
            if attempt < MAX_REPROMPTS:
                self.reprompts += 1
                note = (
                    f"Your previous reply was not a usable index. Answer with a single integer "
                    f"between 0 and {len(options) - 1}. Attempt {attempt + 2}."
                )

        self.fallback_reasons[self._reason_since(before)] += 1
        return self._adaptive(view, oracle, "fallback")

    def _adaptive(self, view: PartyView, oracle: Oracle, why: str) -> Action:
        action = self._fallback.act(view, oracle)
        return action.model_copy(update={"rationale": f"[{why}: adaptive] {action.rationale}"})

    _REASONS = ("blocked", "malformed", "errors", "refusals")

    def _counters(self) -> dict[str, int]:
        usage = self.client.usage
        return {name: getattr(usage, name) for name in self._REASONS}

    def _reason_since(self, before: dict[str, int]) -> str:
        """Why *this* decision fell back.

        Attribution is by the delta across this decision's attempts, not by scanning the
        client's running totals: once any malformed answer had occurred, a totals scan blamed
        every later fallback on "malformed" regardless of what actually happened.
        """
        after = self._counters()
        moved = {name: after[name] - before[name] for name in self._REASONS}
        worst = max(moved, key=lambda name: moved[name])
        if moved[worst] <= 0:
            return "unknown"
        return "unavailable" if worst == "refusals" else worst
