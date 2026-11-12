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


def test_spoken_lines_are_unchanged():
    """The 540 lines the recorded voices were made for must stay exactly as they are."""
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    root = Path(__file__).parent.parent
    out = subprocess.run([node, str(root / "scripts" / "collect_lines.cjs")], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == json.loads((Path(__file__).parent / "golden" / "lines_baseline.json").read_text(encoding="utf-8"))
