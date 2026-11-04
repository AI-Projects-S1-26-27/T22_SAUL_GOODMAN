"""Which library cases ship with adverse events on, and at what rates (DEVIATIONS D19).

The rates are the ones ``docs/CALIBRATION_SWEEP.md`` selected by measurement: no-show 10%, missing certificate 15%, hostile 10%,
a hostile witness's credibility multiplied by 1/4. Four cases ship with them on, the ones with real play (the two flagship cases,
the civil case and the poisoned-tree case). The three structural fixtures stay on the plain rulebook: each exists to show one
rule (a docket with nothing on it, a defense-only docket, an exact tie), and a random event would blur the thing they demonstrate.
"""

from __future__ import annotations

from courtroom.contracts import CaseFile, RuleSet

SHIPPED_RULES = RuleSet(adverse_events=True, no_show=0.10, missing_certificate=0.15, hostile=0.10, hostile_credibility="1/4")

#: Case ids that ship with ``SHIPPED_RULES``.
EVENT_CASES = frozenset({"helix-espionage", "aurora-defi", "kestrel-av", "edge-poisoned-tree"})


def ship(case: CaseFile) -> CaseFile:
    """The case as shipped: with the adverse-event rules if it is one of ``EVENT_CASES``, unchanged otherwise."""
    if case.id in EVENT_CASES:
        return case.model_copy(update={"rules": SHIPPED_RULES})
    return case
