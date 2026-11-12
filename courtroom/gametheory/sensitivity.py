"""Sensitivity sweep over the game parameters (proposal Sec. 8).

Owner: Engineer 5.

Costs, sanctions, the log-odds scale and the standards of proof are *game
parameters*, not measured quantities. A conclusion that only holds at one
setting is not a result. This module re-estimates every case's game under
perturbed parameters and reports which equilibrium labels survive.

The judge's *arithmetic* is untouched; only the named constants move, and they
are restored afterwards. Each constant is rebound in every module that imported
it by name, because ``from ... import X`` copies the binding.
"""

from __future__ import annotations

import importlib
import math
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from fractions import Fraction

from pydantic import BaseModel, ConfigDict

from courtroom.cases import CASES, get_case
from courtroom.contracts import CaseType, StandardOfProof, Surprises
from courtroom.gametheory.bootstrap import STYLES, equilibrium_label
from courtroom.gametheory.payoff import estimate_payoffs

DEFAULT_STRATEGIES = STYLES

# Every module holding a by-name binding of each constant. Dicts are shared
# objects and are mutated in place instead.
_SCALAR_BINDINGS: dict[str, tuple[str, ...]] = {
    "LLR_SCALE": ("courtroom.judge.rules", "courtroom.judge.scoring"),
    "CORROBORATION_ALPHA": ("courtroom.judge.rules", "courtroom.judge.scoring"),
    "CONTRADICTION_BETA": ("courtroom.judge.rules", "courtroom.judge.scoring"),
    "SANCTION_OVERRULED_OBJECTION": ("courtroom.judge.rules", "courtroom.agents.policies", "courtroom.engine.trial"),
    "SANCTION_BAD_FAITH_EVIDENCE": ("courtroom.judge.rules", "courtroom.agents.policies", "courtroom.engine.trial"),
    "SANCTION_VIOLATION": ("courtroom.judge.rules", "courtroom.engine.trial"),
    "FINE_VIOLATION": ("courtroom.judge.rules", "courtroom.engine.trial"),
    "OBJECTION_COST": (
        "courtroom.judge.rules",
        "courtroom.agents.policies",
        "courtroom.procedure.validator",
        "courtroom.engine.trial",
    ),
    "IMPEACHMENT_COST": (
        "courtroom.judge.rules",
        "courtroom.agents.policies",
        "courtroom.procedure.validator",
        "courtroom.engine.trial",
    ),
    "MOTION_COST": (
        "courtroom.judge.rules",
        "courtroom.agents.policies",
        "courtroom.procedure.validator",
        "courtroom.engine.trial",
    ),
    "PRIOR_DEFECT_RATE": ("courtroom.agents.base",),
}

SANCTION_KEYS = (
    "SANCTION_OVERRULED_OBJECTION",
    "SANCTION_BAD_FAITH_EVIDENCE",
    "SANCTION_VIOLATION",
    "FINE_VIOLATION",
)
COST_KEYS = ("OBJECTION_COST", "IMPEACHMENT_COST", "MOTION_COST")


@contextmanager
def patched(scalars: dict[str, object] | None = None, thresholds: dict[StandardOfProof, Fraction] | None = None) -> Iterator[None]:
    """Temporarily rebind named constants everywhere they were imported."""
    scalars = scalars or {}
    saved: list[tuple[object, str, object]] = []
    rules = importlib.import_module("courtroom.judge.rules")
    saved_thresholds = dict(rules.THRESHOLD_LOG_ODDS)
    try:
        for name, value in scalars.items():
            for mod_name in _SCALAR_BINDINGS[name]:
                mod = importlib.import_module(mod_name)
                saved.append((mod, name, getattr(mod, name)))
                setattr(mod, name, value)
        if thresholds:
            # Shared dict object: mutating it reaches every importing module.
            rules.THRESHOLD_LOG_ODDS.update(thresholds)
        yield
    finally:
        for mod, name, value in reversed(saved):
            setattr(mod, name, value)
        rules.THRESHOLD_LOG_ODDS.clear()
        rules.THRESHOLD_LOG_ODDS.update(saved_thresholds)


def log_odds_for(p: float) -> Fraction:
    """Exact rational log-odds for a probability, rounded to 4 dp to stay small."""
    return Fraction(repr(round(math.log(p / (1.0 - p)), 4)))


class Variation(BaseModel):
    model_config = ConfigDict(frozen=True)
    parameter: str
    setting: str
    labels: dict[str, str]
    prosecution_win_rate: dict[str, float]
    changed: list[str]


class SensitivityReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    strategies: list[str]
    n_seeds: int
    case_ids: list[str]
    baseline: dict[str, str]
    baseline_win_rate: dict[str, float]
    variations: list[Variation]
    robust_cases: list[str]
    fragile_cases: list[str]
    parameter_impact: dict[str, int]
    surprises: bool = False


def _labels(
    case_ids: Sequence[str], strategies: Sequence[str], seeds: Sequence[int], surprises: Surprises | None = None
) -> tuple[dict[str, str], dict[str, float]]:
    """Solve every case in-process.

    ``workers`` is deliberately not plumbed through: a ``ProcessPoolExecutor``
    child re-imports ``courtroom.*`` from scratch, so the constants ``patched``
    rebinds in this process would never reach the trials and every variation
    would silently return the baseline.
    """
    labels: dict[str, str] = {}
    win: dict[str, float] = {}
    for cid in case_ids:
        table = estimate_payoffs(get_case(cid), strategies, seeds=seeds, workers=1, surprises=surprises)
        labels[cid] = equilibrium_label(table.analysis)
        win[cid] = round(sum(c.prosecution_win_rate for c in table.cells) / len(table.cells), 6)
    return labels, win


def sweep(
    case_ids: Sequence[str] | None = None,
    strategies: Sequence[str] = DEFAULT_STRATEGIES,
    seeds: Sequence[int] = tuple(range(16)),
    delta: float = 0.25,
    brd_probabilities: Sequence[float] = (0.80, 0.85, 0.90, 0.95),
    surprises: Surprises | None = None,
) -> SensitivityReport:
    """Re-solve every case under perturbed parameters and report what survives."""
    ids = list(case_ids or CASES)
    rules = importlib.import_module("courtroom.judge.rules")
    base_scalars = {
        name: getattr(importlib.import_module(mods[0]), name) for name, mods in _SCALAR_BINDINGS.items()
    }
    base_thresholds = dict(rules.THRESHOLD_LOG_ODDS)

    baseline, baseline_win = _labels(ids, strategies, seeds, surprises)
    variations: list[Variation] = []

    def record(parameter: str, setting: str, scalars=None, thresholds=None) -> None:
        with patched(scalars, thresholds):
            labels, win = _labels(ids, strategies, seeds, surprises)
        variations.append(
            Variation(
                parameter=parameter,
                setting=setting,
                labels=labels,
                prosecution_win_rate=win,
                changed=sorted(c for c in ids if labels[c] != baseline[c]),
            )
        )

    def scaled(keys: Sequence[str], factor: float) -> dict[str, object]:
        out: dict[str, object] = {}
        for k in keys:
            v = base_scalars[k]
            out[k] = v * Fraction(repr(factor)) if isinstance(v, Fraction) else round(float(v) * factor, 10)
        return out

    for factor, tag in ((1 - delta, f"-{delta:.0%}"), (1 + delta, f"+{delta:.0%}")):
        record("sanctions", tag, scalars=scaled(SANCTION_KEYS, factor))
        record("costs", tag, scalars=scaled(COST_KEYS, factor))
        record("LLR_SCALE", tag, scalars=scaled(("LLR_SCALE",), factor))
        record("PRIOR_DEFECT_RATE", tag, scalars=scaled(("PRIOR_DEFECT_RATE",), factor))
        record(
            "standards_of_proof",
            tag,
            thresholds={s: v * Fraction(repr(factor)) for s, v in base_thresholds.items()},
        )

    for p in brd_probabilities:
        record(
            "beyond_reasonable_doubt",
            f"p={p:.2f}",
            thresholds={StandardOfProof.BEYOND_REASONABLE_DOUBT: log_odds_for(p)},
        )

    impact: dict[str, int] = {}
    for v in variations:
        impact[v.parameter] = impact.get(v.parameter, 0) + len(v.changed)
    fragile = sorted({c for v in variations for c in v.changed})
    return SensitivityReport(
        strategies=list(strategies),
        n_seeds=len(seeds),
        case_ids=ids,
        baseline=baseline,
        baseline_win_rate=baseline_win,
        variations=variations,
        robust_cases=[c for c in ids if c not in fragile],
        fragile_cases=fragile,
        parameter_impact=impact,
        surprises=surprises is not None,
    )


__all__ = ["CaseType", "SensitivityReport", "Variation", "log_odds_for", "patched", "sweep"]
