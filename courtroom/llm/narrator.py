"""Spoken argument text for a trial that has already finished.

Owner: Engineer 7 (presentation only).

The narrator runs **after** ``run_trial`` returns, over the finished, immutable event stream.
It cannot reach into the trial because by the time it exists the trial is over: every action
was chosen, ruled on and hashed before a single word of this text was written. That is the
whole design. Narration is returned as a separate ``{event_seq: text}`` map and is never
written back into ``TrialEvent``, so the digest, the hash chain and the verdict are untouched
by construction rather than by care.

What goes into a prompt: the public record (what was offered, what the judge ruled) and the
speaker's own case theory. Never the opponent's hand, and never any item's hidden defect flags
— ``test_narrator_prompt_never_leaks_hidden_flags`` enforces that.
"""

from __future__ import annotations

from courtroom.contracts import ActionType, CaseFile, EventKind, Side, TrialEvent, TrialResult
from courtroom.llm.client import LLMClient

SYSTEM = (
    "You are a trial lawyer in a stylised courtroom simulation. Speak one short line of "
    "courtroom argument, at most 30 words, in plain English. Address the judge. Do not invent "
    "facts, exhibits or witnesses beyond those given. Do not narrate; speak as counsel. No "
    "preamble, no quotation marks."
)

_ROLE = {Side.PROSECUTION: "counsel for the prosecution", Side.DEFENSE: "counsel for the defense"}

# Event kinds that represent a party speaking. RULING covers objections and impeachments,
# which are ruled on in the same event that records the move.
SPOKEN_KINDS = frozenset({EventKind.ACTION, EventKind.RULING})


def _public_item(case: CaseFile, evidence_id: str | None) -> str:
    """Public description of an exhibit. Hidden defect flags are deliberately excluded."""
    item = case.item(evidence_id) if evidence_id else None
    if item is None:
        return ""
    elements = ", ".join(f"{k} {v:+g}" for k, v in item.support.items())
    return f"{item.id} ({item.kind.value}, reliability {item.reliability:g}; bears on {elements})"


def _template(case: CaseFile, event: TrialEvent, awaiting_response: bool = False) -> str:
    """The fallback line. Always available, no network, no key."""
    action = event.action
    if action is None or event.actor is None:
        return ""
    who = "The People" if event.actor is Side.PROSECUTION else "The defense"
    item = case.item(action.evidence_id) if action.evidence_id else None
    match action.type:
        case ActionType.PRESENT_EVIDENCE:
            return f"{who} offers {item.title if item else action.evidence_id}, your Honour."
        case ActionType.OBJECT:
            ground = str(action.ground.value).replace("_", " ") if action.ground else "objection"
            return f"Objection, your Honour — {ground}."
        case ActionType.IMPEACH:
            return f"{who} challenges the credibility of {action.witness_id}."
        case ActionType.MOTION_DIRECTED_VERDICT:
            return f"{who} moves for a directed verdict, your Honour."
        case ActionType.REST:
            return f"{who} rests."
        case ActionType.PASS:
            return "No objection, your Honour." if awaiting_response else f"{who} has nothing further at this time."
    return ""


def _prompt(case: CaseFile, event: TrialEvent, history: list[str]) -> str:
    action = event.action
    assert action is not None and event.actor is not None
    lines = [
        f"Case: {case.title}",
        f"Charge: {case.charge}",
        f"You are {_ROLE[event.actor]}.",
        f"Stage of trial: {event.phase.value.replace('_', ' ')}.",
    ]
    if history:
        lines.append("What has just been said: " + " / ".join(history[-3:]))
    move = action.type.value.replace("_", " ")
    lines.append(f"You have ALREADY decided this move and it cannot change: {move}.")
    if action.evidence_id:
        lines.append(f"Exhibit: {_public_item(case, action.evidence_id)}")
    if action.ground is not None:
        lines.append(f"Ground of objection: {str(action.ground.value).replace('_', ' ')}")
    if action.witness_id:
        lines.append(f"Witness: {action.witness_id}")
    lines.append("Say the one line you would say in court to carry out that move.")
    return "\n".join(lines)


def narrate(
    result: TrialResult,
    case: CaseFile,
    client: LLMClient | None = None,
) -> dict[int, str]:
    """Argument text per event sequence number, for a trial that has already been decided.

    With no client, no key or no cache entry, every line falls back to a template, so the
    transcript always reads sensibly and the demo cannot be broken by a failed network call.
    """
    if client is not None:
        client.start_trial()
    out: dict[int, str] = {}
    history: list[str] = []
    awaiting_response = False
    for event in result.events:
        # Objections and impeachments arrive as RULING events that still carry the actor's
        # action, so filter on "someone did something", not on a single event kind.
        if event.action is None or event.actor is None or event.kind not in SPOKEN_KINDS:
            if event.status == "offered":
                awaiting_response = True
            continue
        text = None
        if client is not None:
            text = client.complete(SYSTEM, _prompt(case, event, history))
        line = (text or _template(case, event, awaiting_response)).strip()
        if line:
            out[event.seq] = line
            history.append(f"{event.actor.value}: {line}")
        awaiting_response = event.status == "offered"
    return out
