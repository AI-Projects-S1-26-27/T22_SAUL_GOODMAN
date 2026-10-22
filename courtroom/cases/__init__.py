"""Synthetic case library and procedural generator (Engineer 1)."""

from courtroom.cases.generator import generate_case
from courtroom.cases.library import CASES, get_case
from courtroom.cases.witness_cases import WITNESS_CASES

__all__ = ["CASES", "WITNESS_CASES", "generate_case", "get_case"]
