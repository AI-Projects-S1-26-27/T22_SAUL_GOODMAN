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

from courtroom.cases import CASES, PLAIN_CASES
from courtroom.engine import run_trial

GOLDEN = json.loads((Path(__file__).parent / "golden" / "digests.json").read_text(encoding="utf-8"))
# The same 42 trials on the plain rulebook (no adverse events): recorded before D19 and never regenerated.
GOLDEN_PLAIN = json.loads((Path(__file__).parent / "golden" / "digests_plain.json").read_text(encoding="utf-8"))


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


def test_the_plain_golden_set_is_the_size_we_think_it_is() -> None:
    assert len(GOLDEN_PLAIN) == 7 * 3 * 2 and set(GOLDEN_PLAIN) == set(GOLDEN)


@pytest.mark.parametrize("key", sorted(GOLDEN_PLAIN))
def test_the_plain_rulebook_still_reproduces_every_digest_recorded_before_adverse_events_shipped(key: str) -> None:
    """The proof that D19 changed nothing but turning events on: with them off, all 42 old digests come back."""
    case_id, prosecution, defense, seed = key.split("|")
    result = run_trial(PLAIN_CASES[case_id], prosecution, defense, seed=int(seed))
    expected = GOLDEN_PLAIN[key]
    assert result.digest == expected["digest"], f"{key}: the plain rulebook changed"
    assert result.verdict.outcome.value == expected["verdict"] and len(result.events) == expected["events"]


def test_every_shipped_digest_that_moved_is_a_case_that_ships_with_events() -> None:
    moved = {k for k in GOLDEN if GOLDEN[k]["digest"] != GOLDEN_PLAIN[k]["digest"]}
    assert moved, "turning events on changed nothing, which would make this whole calibration moot"
    for key in moved:
        assert CASES[key.split("|")[0]].adverse_events, f"{key} changed but its case has no adverse events"
