"""A plain-language brief of a case, generated from its structured data and the judge's own constants.

Owner: Engineer 3 (Deterministic Judge). Pure and stateless: the same case always gives the same brief.

The brief is the answer to "what is this trial about, and who has to prove what?" before any evidence is
offered. Every number in it is read from the case file or from ``judge.rules`` at the moment it is built
(the presumption, the bar, the tie rule, the credibility factors), and the issues are the case's own
elements in the case's own order, so it cannot drift from what the engine decides. It contains nothing
hidden: no exhibit flags, no witness flaws, no opponent hand.
"""

from __future__ import annotations

from pydantic import BaseModel

from courtroom.contracts import CaseFile, CaseType, Side, StandardOfProof
from courtroom.judge import rules as _rules
from courtroom.judge.rules import STRICT_STANDARDS, fmt, sigmoid, threshold_for


class Issue(BaseModel):
    id: str
    name: str
    question: str  # what the court must decide, from the element's own description
    burden: str  # who must prove it
    supporting_exhibits: dict[str, int]  # exhibits on file that push each way: {"prosecution": n, "defense": n}
    if_unsupported: str  # what happens if the proving side has nothing accepted on it


class Burden(BaseModel):
    bearer: str
    statement: str
    standard: str
    standard_plain: str
    bar_probability: float
    bar_log_odds: str  # exact rational
    presumption_probability: float
    presumption_log_odds: str
    shift_needed: str  # exact rational: bar minus presumption, the net weight each issue needs
    tie_rule: str
    conjunctive: str


class CaseBrief(BaseModel):
    case_id: str
    title: str
    kind: str
    story: str
    charge: str
    parties: dict[str, str]
    burden: Burden
    issues: list[Issue]
    each_side: dict[str, list[str]]
    docket: list[str]
    how_the_judge_weighs: list[str]
    procedure: list[str]
    published_risks: list[str]


_STANDARD_PLAIN = {
    StandardOfProof.BEYOND_REASONABLE_DOUBT: "The highest standard: the court must be sure, leaving no reasonable doubt.",
    StandardOfProof.CLEAR_AND_CONVINCING: "A high standard: the claim must be highly probable, well above a balance of probabilities.",
    StandardOfProof.PREPONDERANCE: "The lowest standard: the claim must be more likely true than not.",
}


def _pct(log_odds: float) -> float:
    return round(100 * sigmoid(log_odds), 1)


def build_brief(case: CaseFile) -> CaseBrief:
    criminal = case.case_type is CaseType.CRIMINAL
    claimant = "the prosecution" if criminal else "the plaintiff (shown as the prosecution side)"
    prior = _rules.PRIOR_LOG_ODDS[case.case_type]
    tau = threshold_for(case)
    tie = (
        "A point that lands exactly on the bar is not proved."
        if case.standard in STRICT_STANDARDS
        else "A point that lands exactly on the bar counts as proved."
    )
    burden = Burden(
        bearer=Side.PROSECUTION.value,
        statement=(
            f"{claimant.capitalize()} carries the burden on every issue and must prove each one. "
            "The defense does not have to prove anything."
        ),
        standard=case.standard.value.replace("_", " "),
        standard_plain=_STANDARD_PLAIN[case.standard],
        bar_probability=_pct(float(tau)),
        bar_log_odds=fmt(tau),
        presumption_probability=_pct(float(prior)),
        presumption_log_odds=fmt(prior),
        shift_needed=fmt(tau - prior),
        tie_rule=tie,
        conjunctive="Every issue is decided separately and every one must be proved. One unproved issue is enough to fail.",
    )

    issues: list[Issue] = []
    for element in case.elements:
        pushes = {"prosecution": 0, "defense": 0}
        for item in case.evidence:
            value = item.support.get(element.id, 0.0)
            if value > 0:
                pushes["prosecution"] += 1
            elif value < 0:
                pushes["defense"] += 1
        issues.append(
            Issue(
                id=element.id,
                name=element.name,
                question=element.description,
                burden=Side.PROSECUTION.value,
                supporting_exhibits=pushes,
                if_unsupported=(
                    "If no accepted exhibit supports it, the judge ends the case at once without hearing the defense "
                    f"({'directed acquittal' if criminal else 'judgment for the defense'})."
                ),
            )
        )

    names = ", ".join(f"“{e.name}”" for e in case.elements)
    each_side = {
        Side.PROSECUTION.value: [
            f"Prove every issue to the standard: {names}.",
            (
                f"Lift each from the starting presumption ({burden.presumption_probability:g}%) above the bar ({burden.bar_probability:g}%)."
                if tau != prior
                else f"Tip each issue past even odds ({burden.bar_probability:g}%): the starting presumption and the bar are the same."
            ),
            "Offer exhibits one at a time, spend a limited budget, and answer objections.",
        ],
        Side.DEFENSE.value: [
            "Prove nothing. It wins if any one issue is left unproved.",
            "Object to exhibits it believes should be kept out, at the moment they are offered.",
            "Offer its own exhibits to weaken a point, and challenge the credibility of the other side's witnesses.",
        ],
    }

    witnesses = "; ".join(
        f"{w.name} ({w.role}{', ' + w.bias_note.rstrip('.') if w.bias_note else ''})" for w in case.witnesses
    )
    owned = {side: sum(1 for i in case.evidence if i.owner is side) for side in Side}
    docket = [
        f"{len(case.evidence)} exhibits on file: {owned[Side.PROSECUTION]} held by the prosecution side, {owned[Side.DEFENSE]} by the defense.",
        f"Each side has a litigation budget of {case.budget:g} and up to {case.max_primary_turns} turns.",
    ]
    if case.witnesses:
        docket.append(f"Witnesses: {witnesses}.")
    if case.rebuttal_turns:
        docket.append(f"After the defense case, the prosecution gets up to {case.rebuttal_turns} rebuttal turns, limited to answering what the defense raised.")

    judge = [
        f"Each exhibit adds or subtracts weight from the issues it bears on, scaled by {fmt(_rules.LLR_SCALE)} per unit of strength.",
        f"Weight depends on how reliable the exhibit is and how credible its witness is; each successful impeachment multiplies credibility by {fmt(_rules.IMPEACHMENT_FACTOR)}.",
        f"Exhibits that contradict each other reduce one another (pressure up to {fmt(_rules.CONTRADICTION_BETA)} each); several exhibits proving the same fact count once.",
        (
            f"At most {_rules.MAX_FACTS_PER_SIDE} facts per side count on any one issue."
            if _rules.MAX_FACTS_PER_SIDE is not None
            else "There is no cap on the number of facts per side."
        ),
        "The judge is a rulebook, not a model: the same record always gives the same verdict.",
    ]
    procedure = [
        "Both sides offer exhibits turn and turn about; the other side may object to each one as it is offered.",
        "When the prosecution has nothing more, the defense may ask the judge to end the case early.",
        "The defense may then continue alone, the prosecution may rebut, and the judge decides.",
    ]
    risks: list[str] = []
    if case.witness_examination:
        risks.append("Witnesses can be examined and cross-examined; a cross-examination on a flaw that is not there is penalised.")
    if case.adverse_events and case.rules is not None:
        r = case.rules
        risks.append(
            f"Adverse events are in play: a witness fails to appear ({r.no_show:.0%} of offers), "
            f"a digital record lacks its section 65B certificate ({r.missing_certificate:.0%} of offers), "
            f"a witness turns hostile ({r.hostile:.0%} of admissions)."
        )

    return CaseBrief(
        case_id=case.id,
        title=case.title,
        kind="Criminal prosecution" if criminal else "Civil claim",
        story=case.synopsis,
        charge=case.charge,
        parties={"prosecution": "The prosecution" if criminal else "The plaintiff (prosecution side)", "defense": "The defense"},
        burden=burden,
        issues=issues,
        each_side=each_side,
        docket=docket,
        how_the_judge_weighs=judge,
        procedure=procedure,
        published_risks=risks,
    )


__all__ = ["Burden", "CaseBrief", "Issue", "build_brief"]
