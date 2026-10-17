"""Game-theoretic analysis: payoffs, exact Nash equilibria, dynamics, stress (Engineer 5)."""

from courtroom.gametheory.bootstrap import (
    LabelStability,
    bootstrap_case,
    bootstrap_library,
    equilibrium_label,
)
from courtroom.gametheory.dynamics import replicator
from courtroom.gametheory.nash import GameAnalysis, analyze, support_enumeration, verify_equilibrium
from courtroom.gametheory.payoff import PayoffTable, StressReport, estimate_payoffs, stress, tournament
from courtroom.gametheory.sensitivity import SensitivityReport, sweep

__all__ = [
    "GameAnalysis",
    "LabelStability",
    "PayoffTable",
    "SensitivityReport",
    "StressReport",
    "analyze",
    "bootstrap_case",
    "bootstrap_library",
    "equilibrium_label",
    "estimate_payoffs",
    "replicator",
    "stress",
    "support_enumeration",
    "sweep",
    "tournament",
    "verify_equilibrium",
]
