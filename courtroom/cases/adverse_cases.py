"""Library cases with seeded adverse events switched on (DEVIATIONS D15).

Same pattern as ``witness_cases``: derived from certified cases, kept in their own registry so the
certified analysis, ``RESULTS.md`` and the pinned digests never see them. Only the four cases with real play
are included; the three edge fixtures are rule tests and an adverse event would only add noise.
"""

from __future__ import annotations

from courtroom.cases.library import CASES
from courtroom.contracts import CaseFile, RuleSet

_BASES = ("helix-espionage", "aurora-defi", "kestrel-av", "edge-poisoned-tree")


def _with_adverse_events(case: CaseFile) -> CaseFile:
    return CaseFile.model_validate(
        case.model_copy(
            update={
                "id": f"{case.id}-adverse",
                "title": f"{case.title} (with adverse events)",
                "rules": RuleSet(adverse_events=True),
                "tags": (*case.tags, "adverse-events"),
            }
        ).model_dump(mode="json")
    )


ADVERSE_CASES: dict[str, CaseFile] = {f"{cid}-adverse": _with_adverse_events(CASES[cid]) for cid in _BASES}
