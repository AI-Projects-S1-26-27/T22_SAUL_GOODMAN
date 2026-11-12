"""Plain-language account of why a trial ended as it did, read from the record and nothing else.

``build_facts`` reads a *finished* ``TrialResult`` (its event log and the judge's own computed snapshot) and lays out what
the judge decided and why. It runs no agent and recomputes nothing: every number in it was produced by the judge and is
copied out. ``template_text`` turns those facts into plain sentences with no model involved, so the explanation always
exists, offline, with no key. The optional model layer (outside this package) may rephrase it but is checked against the same
facts, using ``allowed_numbers`` and ``check_text`` below.

It reads only the public record: exhibit titles and ids, the rulings and grounds argued, the credibility events and the
judge's numbers. Hidden exhibit flags and witness flaws are not read, so they cannot be disclosed.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from courtroom.contracts import CaseFile, EventKind, Side, TrialResult

_ID = re.compile(r"\b[PD]-[A-Z0-9][A-Z0-9-]*\b")
_NUM = re.compile(r"(?<![A-Za-z0-9-])-?\d+(?:\.\d+)?(?:/\d+)?%?")
_DIRECTED_WHY = {
    "no_support": "because no accepted exhibit supported it, so the defense was never asked to answer it.",
    "below_even": "because the accepted evidence left it below even odds, so no reasonable fact-finder could find it proven.",
}


class ElementFact(BaseModel):
    id: str
    name: str
    log_odds: str  # exact, as the judge reports it
    log_odds_float: float
    probability_pct: float
    bar_log_odds: str
    bar_pct: float
    met: bool
    for_prosecution: list[dict[str, Any]]  # strongest counted exhibits pushing toward the prosecution
    for_defense: list[dict[str, Any]]


class Facts(BaseModel):
    case_title: str
    outcome: str
    outcome_word: str
    winner: str
    reason: str
    decisive_element: str | None
    directed: str | None  # the point the judge ended the case on, if it ended early
    directed_why: str | None  # "no_support" (DV-2: nothing accepted bears on it) or "below_even" (DV-1: under 50%)
    elements: list[ElementFact]
    exclusions: list[dict[str, Any]]
    credibility: list[str]
    adverse: list[str]
    sanctions: dict[str, float]
    steps: int


# --------------------------------------------------------------------------- facts


def _title(case: CaseFile, evidence_id: str) -> str:
    item = case.item(evidence_id)
    return item.title if item else evidence_id


def _owner(case: CaseFile, evidence_id: str) -> str:
    item = case.item(evidence_id)
    return item.owner.value if item else "unknown"


def build_facts(result: TrialResult, case: CaseFile) -> Facts:
    verdict = result.verdict
    names = {e.id: e.name for e in case.elements}
    elements: list[ElementFact] = []
    for es in verdict.snapshot.elements:
        counted = [c for c in es.contributions if c.counted]
        pro = sorted((c for c in counted if c.log_odds > 0), key=lambda c: -c.log_odds)[:3]
        con = sorted((c for c in counted if c.log_odds < 0), key=lambda c: c.log_odds)[:3]

        def fact(c) -> dict[str, Any]:
            return {"id": c.evidence_id, "title": _title(case, c.evidence_id), "weight": round(c.log_odds, 2)}

        elements.append(
            ElementFact(
                id=es.element_id,
                name=names.get(es.element_id, es.element_id),
                log_odds=es.log_odds,
                log_odds_float=round(es.log_odds_float, 2),
                probability_pct=round(100 * es.probability, 1),
                bar_log_odds=es.threshold,
                bar_pct=round(100 * es.threshold_probability, 1),
                met=es.met,
                for_prosecution=[fact(c) for c in pro],
                for_defense=[fact(c) for c in con],
            )
        )

    exclusions: list[dict[str, Any]] = []
    credibility: list[str] = []
    adverse: list[str] = []
    directed: str | None = None
    directed_why: str | None = None
    for ev in result.events:
        if ev.kind is EventKind.RULING and ev.status == "excluded" and ev.subject:
            ground = ev.action.ground.value.replace("_", " ") if ev.action and ev.action.ground else "an objection"
            exclusions.append({"id": ev.subject, "title": _title(case, ev.subject), "by": ev.actor.value if ev.actor else None, "ground": ground})
        elif ev.kind is EventKind.DIRECTED_VERDICT and "GRANTED" in ev.summary:
            directed = ev.summary.split("GRANTED on", 1)[-1].strip(" .")
            directed_why = "no_support" if any(r.rule_id == "DV-2" and "sua sponte" in r.detail for r in ev.rules) else "below_even"
        elif ev.status == "impeached":
            credibility.append(ev.summary)
        elif ev.kind is EventKind.ADVERSE and ev.status in ("no_show", "no_certificate", "hostile"):
            adverse.append(ev.summary)
    ledgers = {s.value: round(result.ledgers[s].sanctions, 2) for s in Side}
    return Facts(
        case_title=case.title,
        outcome=verdict.outcome.value,
        outcome_word=verdict.outcome.value.replace("_", " "),
        winner=verdict.outcome.favours.value,
        reason=verdict.reason,
        decisive_element=verdict.decisive_element,
        directed=directed,
        directed_why=directed_why,
        elements=elements,
        exclusions=exclusions,
        credibility=credibility,
        adverse=adverse,
        sanctions=ledgers,
        steps=len(result.events),
    )


# --------------------------------------------------------------------------- allowed numbers


def _variants(x: float) -> set[str]:
    out = {f"{x:.0f}", f"{x:.1f}", f"{x:.2f}", f"{x:g}", f"{abs(x):.0f}", f"{abs(x):.1f}", f"{abs(x):.2f}", f"{abs(x):g}"}
    return out | {s.rstrip("0").rstrip(".") for s in out if "." in s}


def allowed_numbers(facts: Facts) -> set[str]:
    """Every number the text may legitimately mention: the ones in the facts, in the forms a writer would use."""
    ok: set[str] = {str(facts.steps), "1", "2", "3"}  # small counting words and "1 of 3" style lists are harmless
    for e in facts.elements:
        for x in (e.log_odds_float, e.probability_pct, e.bar_pct):
            ok |= _variants(x)
        ok |= {e.log_odds, e.bar_log_odds}
        for side in (e.for_prosecution, e.for_defense):
            for c in side:
                ok |= _variants(c["weight"])
    for v in facts.sanctions.values():
        ok |= _variants(v)
    ok |= {str(len(facts.exclusions)), str(len(facts.elements))}
    # Numbers that are part of an exhibit's own title (a time stamp, an amount) are quoted from the record, not new.
    titles = [facts.case_title, *(c["title"] for e in facts.elements for c in (*e.for_prosecution, *e.for_defense))]
    titles += [x["title"] for x in facts.exclusions]
    # So are numbers in the record's own event lines (the judge's reason, an impeachment, "section 65B" in an adverse event).
    titles += [facts.reason, *facts.credibility, *facts.adverse]
    for t in titles:
        ok |= {tok.rstrip("%") for tok in _NUM.findall(t)}
    return ok


def check_text(text: str, facts: Facts) -> str | None:
    """``None`` when the text only uses numbers and exhibit ids from the facts, else the reason it is refused."""
    known_ids = {c["id"] for e in facts.elements for c in (*e.for_prosecution, *e.for_defense)} | {x["id"] for x in facts.exclusions}
    # Exhibits named in the record's own event lines (an impeachment, an adverse event) are in the record too.
    known_ids |= set(_ID.findall(" ".join([facts.reason, *facts.credibility, *facts.adverse])))
    unknown_ids = sorted(set(_ID.findall(text)) - known_ids)
    if unknown_ids:
        return f"it named exhibits that are not in the record of this verdict: {', '.join(unknown_ids)}"
    ok = allowed_numbers(facts)
    for token in _NUM.findall(text):
        bare = token.rstrip("%")
        if bare in ok or bare.lstrip("-") in ok or bare.rstrip("0").rstrip(".") in ok:
            continue
        return f"it used a number that is not among the judge's figures: {token}"
    return None


# --------------------------------------------------------------------------- the template


def _list(items: list[str]) -> str:
    return ", ".join(items[:-1]) + (" and " if len(items) > 1 else "") + items[-1] if items else ""


def template_text(f: Facts) -> str:
    who = "the prosecution side" if f.winner == "prosecution" else "the defense"
    parts = [f"The judge decided for {who}: {f.outcome_word}. {f.reason.replace('_', ' ')}"]
    if f.directed:
        parts.append(f"The case was ended early on “{f.directed}” {_DIRECTED_WHY[f.directed_why or 'below_even']}")
    for e in f.elements:
        verdict = "met the bar" if e.met else "fell short of the bar"
        line = (
            f"On “{e.name}” the accepted evidence reached {e.probability_pct:g}% (log-odds {e.log_odds_float:g}) against a bar of "
            f"{e.bar_pct:g}%, so it {verdict}."
        )
        pro = [f"{c['title']} ({c['id']}, {c['weight']:+g})" for c in e.for_prosecution[:2]]
        con = [f"{c['title']} ({c['id']}, {c['weight']:+g})" for c in e.for_defense[:2]]
        if pro:
            line += f" What pushed toward the prosecution: {_list(pro)}."
        if con:
            line += f" What pushed toward the defense: {_list(con)}."
        parts.append(line)
    if f.decisive_element and not f.directed:
        name = next((e.name for e in f.elements if e.id == f.decisive_element), f.decisive_element)
        parts.append(f"The point that decided it was “{name}”.")
    if f.exclusions:
        shown = [f"{x['title']} ({x['id']}, objection on {x['ground']})" for x in f.exclusions[:3]]
        parts.append(f"The court kept out {len(f.exclusions)} exhibit(s): {_list(shown)}.")
    if f.credibility or f.adverse:
        parts.append("Along the way: " + " ".join((f.credibility + f.adverse)[:3]))
    return " ".join(parts)


