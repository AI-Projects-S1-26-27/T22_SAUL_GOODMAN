"""Golden digests: the certified engine must not drift.

``tests/golden/digests.json`` pins the event-chain digest and verdict of 42 deterministic
trials (7 cases x 3 pairings x 2 seeds), recorded from the engine as it stood before the
UI-completion work (threshold parameter, evidence injection, exhibition replay).

Anything that changes a digest here changes what "same case, same seed, same verdict" means,
so a failure is a stop-and-think event, not something to regenerate away. The file was
produced by hashing ``run_trial`` for every key; regenerate it only for a deliberate,
documented rule change, and record that in DEVIATIONS.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from courtroom.cases import CASES
from courtroom.engine import run_trial

GOLDEN = json.loads((Path(__file__).parent / "golden" / "digests.json").read_text(encoding="utf-8"))


def test_the_golden_set_is_the_size_we_think_it_is() -> None:
    assert len(GOLDEN) == 7 * 3 * 2


@pytest.mark.parametrize("key", sorted(GOLDEN))
def test_digest_and_verdict_are_unchanged(key: str) -> None:
    case_id, prosecution, defense, seed = key.split("|")
    result = run_trial(CASES[case_id], prosecution, defense, seed=int(seed))
    expected = GOLDEN[key]
    assert result.digest == expected["digest"], f"{key}: the event chain changed"
    assert result.verdict.outcome.value == expected["verdict"]
    assert len(result.events) == expected["events"]
