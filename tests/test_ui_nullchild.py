"""``Element.replaceChildren(null)`` writes the text "null" into the page (the ``el()`` helper skips nulls, the DOM method does not)."""

import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "courtroom" / "viz" / "web"


def test_no_replacechildren_call_is_handed_a_possibly_null_argument():
    for name in ("live.js", "lab-extra.js"):
        lines = (WEB / name).read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if re.search(r"replaceChildren\(\s*$", line):
                j = i + 1
                while j < len(lines) and not re.match(r"\s*\)", lines[j]):
                    # a top-level argument line (indent of 8) that ends in ': null,' would put the text "null" on screen
                    assert not re.match(r"^ {8}\S.*: null,$", lines[j]), f"{name}:{j + 1} passes null to replaceChildren"
                    j += 1
