"""Exact evidentiary scoring (see docs/DESIGN.md section 3.3).

Owner: Engineer 3.

``score_record`` is a *pure function* of (case, admitted set, impeachment counts).
It never looks at presentation order, so permutation invariance holds by
construction. The tests verify it anyway.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction

from courtroom.contracts import (
    CaseFile,
    Contribution,
    ElementScore,
    EvidenceItem,
    ExamGround,
    ScoreSnapshot,
)
from courtroom.judge import rules as _rules
from courtroom.judge.rules import (
    CONTRADICTION_BETA,
    CORROBORATION_ALPHA,
    EXAM_FACTORS,
    HOSTILE_FACTOR,
    IMPEACHMENT_FACTOR,
    LLR_SCALE,
    MAX_CONTRADICTION_DISCOUNT,
    ONE,
    PRIOR_LOG_ODDS,
    ZERO,
    exposure_key,
    fmt,
    hostile_key,
    q,
    sigmoid,
    threshold_for,
    threshold_met,
)


@dataclass(frozen=True, slots=True)
class ExactScores:
    """Exact per-element log-odds plus the display snapshot built from them."""

    log_odds: dict[str, Fraction]
    snapshot: ScoreSnapshot


def _cap_facts_per_side(counted: set[str], weights: Mapping[str, Fraction], cap: int | None) -> set[str]:
    """Keep the ``cap`` strongest counted facts on each side of an element (proposal Sec. 6).

    A fact helps the prosecution when its weight is positive and the defense when it is negative,
    and the two sides are capped separately, so a large defense case cannot push out the
    prosecution's best facts or the other way round. Ranking is by ``|w|`` with the evidence id as
    the tie-break, so the result is still a pure function of the admitted set.
    """
    if cap is None:
        return counted
    kept: set[str] = set()
    for sign in (1, -1):
        side = sorted((i for i in counted if _sign(weights[i]) == sign), key=lambda i: (-abs(weights[i]), i))
        kept.update(side[:cap])
    return kept


def credibility(item: EvidenceItem, case: CaseFile, impeachments: Mapping[str, int]) -> Fraction:
    if item.witness_id is None:
        return ONE
    witness = case.witness(item.witness_id)
    base = q(witness.credibility) if witness is not None else ONE
    value = base * IMPEACHMENT_FACTOR ** impeachments.get(item.witness_id, 0)
    # Exposed flaws ride in the same ledger under ``exposure_key``; an absent key is a factor of one,
    # so a record with no cross-examination scores exactly as before.
    for ground in ExamGround:
        if impeachments.get(exposure_key(item.witness_id, ground), 0):
            value *= EXAM_FACTORS[ground]
    if impeachments.get(hostile_key(item.witness_id), 0):
        # The case's own published factor when it has one; the module default otherwise (and for every case without events).
        value *= Fraction(case.rules.hostile_credibility) if case.rules is not None else HOSTILE_FACTOR
    return value


def _sign(x: Fraction) -> int:
    return (x > 0) - (x < 0)


def score_record(
    case: CaseFile,
    admitted: Iterable[str],
    impeachments: Mapping[str, int] | None = None,
) -> ExactScores:
    impeachments = impeachments or {}
    items = sorted((i for i in case.evidence if i.id in set(admitted)), key=lambda i: i.id)
    admitted_ids = {i.id for i in items}

    # Symmetric contradiction adjacency restricted to admitted items.
    neighbours: dict[str, set[str]] = {i.id: set() for i in items}
    for a, b in case.contradiction_edges():
        if a in admitted_ids and b in admitted_ids:
            neighbours[a].add(b)
            neighbours[b].add(a)

    strength = {i.id: q(i.reliability) * credibility(i, case, impeachments) for i in items}

    discount: dict[str, Fraction] = {}
    for i in items:
        pressure = ZERO
        for j in sorted(neighbours[i.id]):
            denom = strength[i.id] + strength[j]
            if denom > 0:
                pressure += CONTRADICTION_BETA * strength[j] / denom
        discount[i.id] = min(MAX_CONTRADICTION_DISCOUNT, pressure)

    prior = PRIOR_LOG_ODDS[case.case_type]
    tau = threshold_for(case)
    exact: dict[str, Fraction] = {}
    element_scores: list[ElementScore] = []

    for element in case.elements:
        e = element.id
        weights: dict[str, Fraction] = {}
        corr: dict[str, Fraction] = {}
        for i in items:
            s = q(i.support.get(e, 0.0))
            if s == 0:
                continue
            corroborating_facts = {
                j.fact_id for j in items if j.fact_id != i.fact_id and _sign(q(j.support.get(e, 0.0))) == _sign(s)
            }
            corr[i.id] = ONE + CORROBORATION_ALPHA * (ONE - Fraction(1, 2) ** len(corroborating_facts))
            weights[i.id] = s * strength[i.id] * (ONE - discount[i.id]) * corr[i.id]

        # Cumulative-evidence rule: one counted item per underlying fact.
        best_per_fact: dict[str, str] = {}
        for item_id in sorted(weights):
            fact = case.item(item_id).fact_id  # type: ignore[union-attr]
            incumbent = best_per_fact.get(fact)
            if incumbent is None or abs(weights[item_id]) > abs(weights[incumbent]):
                best_per_fact[fact] = item_id
        counted = set(best_per_fact.values())
        counted = _cap_facts_per_side(counted, weights, _rules.MAX_FACTS_PER_SIDE)

        log_odds = prior + LLR_SCALE * sum((weights[i] for i in sorted(counted)), ZERO)
        exact[e] = log_odds
        contributions = tuple(
            Contribution(
                evidence_id=i,
                element_id=e,
                support=float(q(case.item(i).support[e])),  # type: ignore[union-attr]
                strength=float(strength[i]),
                contradiction_discount=float(discount[i]),
                corroboration_factor=float(corr[i]),
                weight=float(weights[i]),
                log_odds=float(LLR_SCALE * weights[i]),
                counted=i in counted,
            )
            for i in sorted(weights)
        )
        element_scores.append(
            ElementScore(
                element_id=e,
                log_odds=fmt(log_odds),
                log_odds_float=float(log_odds),
                probability=sigmoid(float(log_odds)),
                threshold=fmt(tau),
                threshold_probability=sigmoid(float(tau)),
                met=threshold_met(log_odds, case.standard, tau),
                contributions=contributions,
            )
        )

    # Weakest element: lowest exact log-odds; ties broken by element declaration order.
    weakest = min(case.elements, key=lambda el: exact[el.id]).id
    snapshot = ScoreSnapshot(
        elements=tuple(element_scores),
        burden_index=sigmoid(float(exact[weakest])),
        weakest_element=weakest,
        all_met=all(es.met for es in element_scores),
    )
    return ExactScores(log_odds=exact, snapshot=snapshot)
