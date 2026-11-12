"""Recorded trials never change: re-run every trial in the web bundle and compare digests.

The voice clips were recorded from these exact trials, so a moved digest would mean re-recording.
"""
import json
from pathlib import Path

import pytest

from courtroom.cases import CASES
from courtroom.engine import run_trial

PINNED = json.loads((Path(__file__).parent / "golden" / "bundle_digests.json").read_text(encoding="utf-8"))


def test_pin_covers_every_case_and_pairing():
    assert len(PINNED) == len(CASES) * 16


@pytest.mark.parametrize("key", sorted(PINNED))
def test_recorded_trial_digest_is_unchanged(key):
    case_id, p, d, seed = key.split("|")
    assert run_trial(CASES[case_id], p, d, int(seed)).digest == PINNED[key]
