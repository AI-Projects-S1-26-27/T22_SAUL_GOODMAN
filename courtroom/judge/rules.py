"""Constants and exact numeric helpers of the rule engine.

Owner: Engineer 3 (Deterministic Judge).

All verdict-relevant arithmetic uses ``fractions.Fraction``. Floats appear only
in display fields. ``q()`` converts a float via its shortest ``repr``, so
``q(0.7) == Fraction(7, 10)`` exactly on every platform.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import TYPE_CHECKING

from courtroom.contracts import CaseType, ExamGround, StandardOfProof

if TYPE_CHECKING:
    from courtroom.contracts import CaseFile

ZERO = Fraction(0)
ONE = Fraction(1)

LLR_SCALE = Fraction(3)  # K: log-odds contributed by a unit-weight item
CORROBORATION_ALPHA = Fraction(1, 2)  # alpha: max corroboration bonus (+50 %)
CONTRADICTION_BETA = Fraction(4, 5)  # beta: pairwise contradiction pressure
MAX_CONTRADICTION_DISCOUNT = Fraction(9, 10)
IMPEACHMENT_FACTOR = Fraction(1, 2)  # credibility halves per successful impeachment
RELEVANCE_FLOOR = Fraction(1, 20)
# Proposal Sec. 6: "Fe is the four facts with the largest |v| per side, so splitting one fact into
# many cannot inflate the score." The cap applies per side of an element, i.e. separately to the
# facts that help the prosecution and the facts that help the defense. ``None`` removes it, which is
# how the earlier uncapped behaviour is reproduced (see tests/test_fact_cap.py).
MAX_FACTS_PER_SIDE: int | None = 4
DIRECTED_VERDICT_THRESHOLD = ZERO  # DV-1: any element with L_e < 0

# Witness examination (DEVIATIONS D13). Only reachable when ``CaseFile.rules.witnesses`` is on, so none of
# this touches a certified result. A real flaw exposed on cross multiplies the witness's credibility by
# the ground's factor; the factors compose with each other and with IMPEACHMENT_FACTOR.
EXAM_FACTORS: dict[ExamGround, Fraction] = {
    ExamGround.QUALIFICATIONS: Fraction(1, 3),  # the strongest attack: the opinion should not have been heard
    ExamGround.BIAS: Fraction(2, 3),  # the weakest: an interested witness can still be right
    ExamGround.INCONSISTENCY: Fraction(1, 2),  # as damaging as a successful impeachment
}
# Adverse events (DEVIATIONS D15). A witness who turns hostile keeps testifying but is worth a quarter as much;
# the testimony is not flipped, so a hostile defense witness can never help the prosecution beyond what an
# absent witness would.
HOSTILE_FACTOR = Fraction(1, 4)
EXAMINE_COST = 0.5
CROSS_COST = 1.0
SANCTION_FAILED_CROSS = 0.25  # attacking a flaw that is not there, like an overruled objection

PRIOR_LOG_ODDS: dict[CaseType, Fraction] = {
    CaseType.CRIMINAL: Fraction(-1),  # presumption of innocence (p ~= 0.27)
    CaseType.CIVIL: ZERO,
}

THRESHOLD_LOG_ODDS: dict[StandardOfProof, Fraction] = {
    StandardOfProof.BEYOND_REASONABLE_DOUBT: Fraction(11, 5),  # p ~= 0.90
    StandardOfProof.CLEAR_AND_CONVINCING: Fraction(11, 10),  # p ~= 0.75
    StandardOfProof.PREPONDERANCE: ZERO,  # strictly more likely than not
}

STRICT_STANDARDS = frozenset({StandardOfProof.PREPONDERANCE})

# Sanction points (utility penalties) and fines (budget units).
SANCTION_OVERRULED_OBJECTION = 0.25
SANCTION_BAD_FAITH_EVIDENCE = 2.0
SANCTION_VIOLATION = 1.0
FINE_VIOLATION = 1.0
OBJECTION_COST = 0.5
IMPEACHMENT_COST = 1.0
MOTION_COST = 0.5
CONTEMPT_VIOLATIONS = 3


def hostile_key(witness_id: str) -> str:
    """Key under which a witness's hostility rides in the impeachment ledger (``#`` cannot occur in an id)."""
    return f"{witness_id}#hostile"


def exposure_key(witness_id: str, ground: ExamGround) -> str:
    """Key under which an exposed flaw rides in the impeachment ledger.

    Witness ids match ``[A-Za-z0-9_-]+`` so ``#`` can never occur inside one.
    """
    return f"{witness_id}#{ground.value}"


def q(x: float | int | str | Fraction) -> Fraction:
    """Exact rational from a decimal-looking number."""
    if isinstance(x, Fraction):
        return x
    if isinstance(x, float):
        return Fraction(repr(x))
    return Fraction(x)


def fmt(x: Fraction) -> str:
    return f"{x.numerator}/{x.denominator}" if x.denominator != 1 else str(x.numerator)


def sigmoid(log_odds: float) -> float:
    """Display-only conversion; never used for a decision."""
    if log_odds >= 0:
        return 1.0 / (1.0 + math.exp(-log_odds))
    z = math.exp(log_odds)
    return z / (1.0 + z)


def threshold_for(case: CaseFile) -> Fraction:
    """The bar a case must clear, in log-odds.

    The standard's own bar unless the case carries an explicit ``bar_log_odds``. With no
    override this is exactly ``THRESHOLD_LOG_ODDS[case.standard]``, which is every library case
    and the whole certified analysis; ``tests/test_golden.py`` pins that digest for digest.
    """
    if case.bar_log_odds is not None:
        return Fraction(case.bar_log_odds)
    return THRESHOLD_LOG_ODDS[case.standard]


def threshold_met(log_odds: Fraction, standard: StandardOfProof, tau: Fraction | None = None) -> bool:
    """Whether ``log_odds`` clears the bar. The standard decides whether a tie passes."""
    tau = THRESHOLD_LOG_ODDS[standard] if tau is None else tau
    return log_odds > tau if standard in STRICT_STANDARDS else log_odds >= tau


def bar_log_odds_for(probability: float) -> str:
    """A probability as the exact, short rational string ``CaseFile.bar_log_odds`` expects."""
    text = f"{round(math.log(probability / (1.0 - probability)), 4):.4f}".rstrip("0").rstrip(".")
    return text or "0"


def override_for_bar(case: CaseFile, probability: float) -> str | None:
    """The ``bar_log_odds`` to use for a requested probability, or ``None`` for "the case's own".

    A bar within the same whole percent as the standard's own is treated as the standard
    itself. Without that, picking "90%" on a beyond-reasonable-doubt case would silently swap
    the exact 11/5 for a rounded 2.1972 and nudge borderline verdicts.
    """
    own = sigmoid(float(THRESHOLD_LOG_ODDS[case.standard]))
    if round(100 * probability) == round(100 * own):
        return None
    return bar_log_odds_for(probability)
