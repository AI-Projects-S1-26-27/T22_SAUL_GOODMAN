"""Tipping point: the smallest change to one number that would have flipped this verdict.

The judge scores a *record* (which exhibits were admitted, which witnesses were impeached) with exact arithmetic. So we can
ask a counterfactual honestly: keep the record, change one exhibit's reliability or one witness's credibility, and let the
judge decide again. A coarse scan finds where the verdict first flips; bisection then pins the exact 0.0001 step. This reuses
the judge itself, so every answer is the rulebook's, not an estimate.

What it does *not* do: it does not replay the lawyers. Agents might play differently if the numbers were different, so
"apply" in the UI re-runs the whole trial and shows what really happens.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from courtroom.contracts import ActionType, CaseFile, EventKind, Side, TrialResult, VerdictOutcome
from courtroom.judge.judge import Judge
from courtroom.judge.rules import HOSTILE_PREFIX

GRID = 10_000  # reliability and credibility are exact to four decimals
COARSE = 500  # first scan in steps of 5 points, then bisect inside the step that flips


class Tip(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: str  # "exhibit" | "witness"
    target: str  # evidence id or witness id
    name: str
    field: str  # "reliability" | "credibility"
    from_value: float
    to_value: float
    change_points: float  # absolute change, in percentage points
    direction: str  # "less" | "more"
    flips_to: str  # "prosecution" | "defense"
    sentence: str


class Record(BaseModel):
    model_config = ConfigDict(frozen=True)
    admitted: list[str]
    impeachments: dict[str, int]
    directed: bool
    moved: bool


def record_of(result: TrialResult) -> Record:
    """The record the judge scored, read back from the event log."""
    imp: dict[str, int] = {}
    moved = False
    for e in result.events:
        if e.status == "impeached" and e.subject:
            imp[e.subject] = imp.get(e.subject, 0) + 1
        elif e.status == "hostile" and e.subject:
            imp[HOSTILE_PREFIX + e.subject] = 1
        if e.kind is EventKind.ACTION and e.action is not None and e.action.type is ActionType.MOTION_DIRECTED_VERDICT:
            moved = True
    return Record(
        admitted=sorted(n.id for n in result.graph.nodes if n.status == "admitted"),
        impeachments=imp,
        directed=result.verdict.outcome is VerdictOutcome.DIRECTED_ACQUITTAL,
        moved=moved,
    )


def prosecution_wins(case: CaseFile, rec: Record) -> bool:
    judge = Judge(case)
    if rec.directed:
        granted, _, _ = judge.directed_verdict_review(rec.admitted, rec.impeachments, rec.moved)
        if granted:
            return False
    return judge.deliberate(rec.admitted, rec.impeachments).outcome.favours is Side.PROSECUTION


def _with(case: CaseFile, kind: str, target: str, value: float) -> CaseFile:
    value = round(value, 4)
    if kind == "exhibit":
        items = tuple(i.model_copy(update={"reliability": value}) if i.id == target else i for i in case.evidence)
        return case.model_copy(update={"evidence": items})
    ws = tuple(w.model_copy(update={"credibility": value}) if w.id == target else w for w in case.witnesses)
    return case.model_copy(update={"witnesses": ws})


def _flip_point(case: CaseFile, rec: Record, kind: str, target: str, k0: int, original: bool, toward: int) -> int | None:
    """Smallest-step value (in 1/10000) toward ``toward`` at which the outcome differs from ``original``, or None."""
    step = COARSE if toward > k0 else -COARSE
    prev = k0
    k = k0
    flipped_at: int | None = None
    while True:
        k = max(0, min(GRID, k + step)) if (k + step - toward) * step < 0 else toward
        if prosecution_wins(_with(case, kind, target, k / GRID), rec) != original:
            flipped_at = k
            break
        if k == toward:
            return None
        prev = k
    lo, hi = prev, flipped_at  # outcome == original at lo, differs at hi
    while abs(hi - lo) > 1:
        mid = (lo + hi) // 2
        if prosecution_wins(_with(case, kind, target, mid / GRID), rec) == original:
            lo = mid
        else:
            hi = mid
    return hi


def tipping_points(case: CaseFile, result: TrialResult, top: int = 5) -> list[Tip]:
    """Single-number changes that flip the verdict, smallest first. Empty if none exists."""
    rec = record_of(result)
    original = prosecution_wins(case, rec)
    tips: list[Tip] = []
    admitted = set(rec.admitted)
    witnesses = {i.witness_id for i in case.evidence if i.id in admitted and i.witness_id}
    levers: list[tuple[str, str, str, float, str]] = []
    for item in case.evidence:
        if item.id in admitted:
            levers.append(("exhibit", item.id, "reliability", item.reliability, item.title))
    for w in case.witnesses:
        if w.id in witnesses:
            levers.append(("witness", w.id, "credibility", w.credibility, w.name))
    flips_to = "defense" if original else "prosecution"
    for kind, target, field, value, name in levers:
        k0 = round(value * GRID)
        best: tuple[int, int] | None = None
        for toward in (0, GRID):
            if toward == k0:
                continue
            k = _flip_point(case, rec, kind, target, k0, original, toward)
            if k is not None and (best is None or abs(k - k0) < abs(best[0] - k0)):
                best = (k, toward)
        if best is None:
            continue
        k, toward = best
        pts = abs(k - k0) / 100
        direction = "more" if k > k0 else "less"
        noun = "reliable" if kind == "exhibit" else "believable"
        subject = f"“{name}”" if kind == "exhibit" else name
        tips.append(
            Tip(
                kind=kind,
                target=target,
                name=name,
                field=field,
                from_value=round(k0 / GRID, 4),
                to_value=round(k / GRID, 4),
                change_points=round(pts, 2),
                direction=direction,
                flips_to=flips_to,
                sentence=f"If {subject} were {pts:g} points {direction} {noun}, the verdict flips to the {flips_to}.",
            )
        )
    tips.sort(key=lambda t: (t.change_points, t.target))
    return tips[:top]
