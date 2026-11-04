"""Synthetic case library and procedural generator (Engineer 1)."""

from courtroom.cases.generator import generate_case
from courtroom.cases.library import CASES, PLAIN_CASES, get_case, get_plain_case
from courtroom.cases.witness_cases import WITNESS_CASES

__all__ = ["CASES", "PLAIN_CASES", "WITNESS_CASES", "generate_case", "get_case", "get_plain_case"]
