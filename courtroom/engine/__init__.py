"""Simulation engine: trial orchestration, audit chain, utilities (Engineer 6)."""

from courtroom.engine.audit import verify_chain
from courtroom.engine.trial import MAX_EVENTS, Court, run_trial, run_with_agents
from courtroom.engine.utility import WIN_VALUE, utilities

__all__ = ["MAX_EVENTS", "WIN_VALUE", "Court", "run_trial", "run_with_agents", "utilities", "verify_chain"]
