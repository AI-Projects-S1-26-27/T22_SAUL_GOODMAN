"""What a pushed adverse event changed: each side's first decision that differs, and the belief behind it.

Everything here is read from two finished trials (the same inputs with and without the push). It computes
nothing about the case and runs no agent. The reason shown for a changed decision is the rationale the agent
itself recorded in the hash chain, which for the expected-value profile includes the survival probability it
believed, plus the public announcement that produced that belief. No narration is involved.
"""

from __future__ import annotations

from typing import Any

from courtroom.contracts import AdversePush, CaseFile, EventKind, Side, TrialEvent, TrialResult

_ANNOUNCING = {"announced", "hostile", "not_applied"}


def _push_event_index(after: TrialResult, push: AdversePush) -> int | None:
    for i, ev in enumerate(after.events):
        if ev.kind is EventKind.ADVERSE and ev.subject == push.target and ev.status in _ANNOUNCING and any(
            f"push at step {push.at_seq}: {push.kind} on {push.target}" in r.detail for r in ev.rules
        ):
            return i
    return None


def _decision(ev: TrialEvent) -> tuple[Any, ...]:
    a = ev.action
    assert a is not None
    return (a.type.value, a.evidence_id, a.witness_id, a.ground.value if a.ground else None)


def _own_decisions(trial: TrialResult, side: Side, start: int) -> list[TrialEvent]:
    """The side's own moves from ``start`` on, one per primary or response turn, in order."""
    return [e for e in trial.events[start:] if e.actor is side and e.action is not None]


def _describe(ev: TrialEvent | None) -> dict[str, Any] | None:
    if ev is None or ev.action is None:
        return None
    return {
        "step": ev.seq + 1,
        "type": ev.action.type.value,
        "evidence_id": ev.action.evidence_id,
        "witness_id": ev.action.witness_id,
        "rationale": ev.action.rationale,
    }


def push_reaction(before: TrialResult, after: TrialResult, push: AdversePush, case: CaseFile | None = None) -> dict[str, Any]:
    """Compare ``before`` (without ``push``) with ``after`` (with it), side by side."""
    at = _push_event_index(after, push)
    announcement = after.events[at] if at is not None else None
    # The announcement exists only in ``after``, so the same moment is one event earlier in ``before``.
    start_after = (at + 1) if at is not None else 0
    start_before = at if at is not None else 0
    sides = []
    for side in Side:
        strategy = after.prosecution_strategy if side is Side.PROSECUTION else after.defense_strategy
        mine_before = _own_decisions(before, side, start_before)
        mine_after = _own_decisions(after, side, start_after)
        first: tuple[TrialEvent | None, TrialEvent | None] = (None, None)
        for i in range(max(len(mine_before), len(mine_after))):
            b = mine_before[i] if i < len(mine_before) else None
            a = mine_after[i] if i < len(mine_after) else None
            if b is None or a is None or _decision(a) != _decision(b):
                first = (b, a)
                break
        b, a = first
        dropped = None
        if b is not None and b.action is not None and b.action.evidence_id == push.target and push.kind != "hostile":
            dropped = (
                f"Dropped {push.target}: the court was told it may fail, so its expected survival is 0.00 and "
                f"offering it is no longer worth the cost."
            )
        if b is not None and b.action is not None and push.kind == "hostile" and case is not None:
            item = case.item(b.action.evidence_id) if b.action.evidence_id else None
            if item is not None and item.witness_id == push.target:
                dropped = (
                    f"Dropped {b.action.evidence_id}: {push.target} may turn hostile, which would cut the testimony "
                    f"to a quarter of its weight, so its expected value falls below the next best exhibit."
                )
        sides.append(
            {
                "side": side.value,
                "strategy": strategy,
                "reacted": b is not None or a is not None,
                "before": _describe(b),
                "after": _describe(a),
                "belief": dropped,
            }
        )
    return {
        "push": push.model_dump(mode="json"),
        "announced_at_step": (at + 1) if at is not None else None,
        "announcement": announcement.summary if announcement else None,
        "applied": announcement is not None and announcement.status != "not_applied",
        "verdict_before": before.verdict.outcome.value,
        "verdict_after": after.verdict.outcome.value,
        "sides": sides,
    }
