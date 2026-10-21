"""Synthetic case library and procedural generator (Engineer 1)."""

from courtroom.cases.adverse_cases import ADVERSE_CASES
from courtroom.cases.generator import generate_case
from courtroom.cases.library import CASES, get_case
from courtroom.cases.witness_cases import WITNESS_CASES

__all__ = ["ADVERSE_CASES", "CASES", "WITNESS_CASES", "generate_case", "get_case"]
