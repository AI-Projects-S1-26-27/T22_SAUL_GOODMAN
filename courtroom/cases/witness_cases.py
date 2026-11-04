"""Library cases with the witness-examination rules switched on (DEVIATIONS D13).

They are derived from three certified cases by giving some witnesses a hidden flaw and setting
``rules=RuleSet(witnesses=True)``. They live in their own registry, not in ``CASES``: the certified
analysis, ``RESULTS.md`` and the pinned digests iterate ``CASES`` and must not move.

Each flaw is one a reader can see the reason for in the witness's own role, which is also what makes it
guessable through the noisy channel: a spouse is interested, an informant is inconsistent.
"""

from __future__ import annotations

from courtroom.cases.library import PLAIN_CASES
from courtroom.contracts import CaseFile, RuleSet

# case id -> {witness id: flaws to set to False}
_FLAWS: dict[str, dict[str, tuple[str, ...]]] = {
    "helix-espionage": {
        "W-NANDA": ("impartial",),  # prosecution's key witness has a grudge
        "W-OKAFOR": ("consistent",),  # the tipster's account has moved between interviews
        "W-VANCE-SPOUSE": ("impartial",),  # the defendant's spouse
        "W-HR": ("qualified",),  # an HR officer opining on exfiltration logs
    },
    "aurora-defi": {
        "W-DEV": ("impartial", "consistent"),
        "W-BOUNTY": ("qualified",),
    },
    "kestrel-av": {
        "W-ENG": ("qualified",),  # the engineer is not a metallurgist
        "W-EYE2": ("consistent",),
    },
}


def _with_witness_rules(case: CaseFile, flaws: dict[str, tuple[str, ...]]) -> CaseFile:
    witnesses = tuple(
        w.model_copy(update={flag: False for flag in flaws.get(w.id, ())}) for w in case.witnesses
    )
    return case.model_copy(
        update={
            "id": f"{case.id}-witnesses",
            "title": f"{case.title} (with witness examination)",
            "witnesses": witnesses,
            "rules": RuleSet(witnesses=True),
            "tags": (*case.tags, "witness-examination"),
        }
    )


WITNESS_CASES: dict[str, CaseFile] = {
    f"{cid}-witnesses": CaseFile.model_validate(_with_witness_rules(PLAIN_CASES[cid], flaws).model_dump(mode="json"))
    for cid, flaws in _FLAWS.items()
}
