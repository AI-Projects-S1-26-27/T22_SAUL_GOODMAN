"""Numbers in the docs come from results/, never from a hand."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ("REPORT.md", "PROVENANCE.md", "DEMO_SCRIPT.md", "docs/LLM_ROLE.md")
BLOCK = re.compile(r"<!-- BEGIN GENERATED:(\w+) -->.*?<!-- END GENERATED:\1 -->", re.S)


def _renderer():
    spec = importlib.util.spec_from_file_location("render_docs", ROOT / "scripts" / "render_docs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_generated_regions_are_up_to_date():
    mod = _renderer()
    for name in mod.DOCS:
        text = (ROOT / name).read_text(encoding="utf-8")
        assert mod.render(text) == text, f"{name} is stale: run python scripts/render_docs.py"


def test_every_marker_pair_is_known_and_closed():
    mod = _renderer()
    for name in mod.DOCS:
        text = (ROOT / name).read_text(encoding="utf-8")
        begins = re.findall(r"<!-- BEGIN GENERATED:(\w+) -->", text)
        ends = re.findall(r"<!-- END GENERATED:(\w+) -->", text)
        assert begins == ends and set(begins) <= set(mod.BLOCKS), name


def test_prose_outside_generated_regions_carries_no_result_numbers():
    """A percentage or a z-score written by hand would be a number nobody can regenerate."""
    for name in DOCS:
        prose = BLOCK.sub("", (ROOT / name).read_text(encoding="utf-8"))
        prose = re.sub(r"`[^`]*`", "", prose)  # code spans hold commands and constants, not results
        found = re.findall(r"\d+(?:\.\d+)?\s?%|\bz\s*[=≈]\s*\d", prose)
        assert not found, f"{name} has hand-typed result numbers outside a generated region: {found}"


def test_the_demo_script_never_offers_a_flat_case_as_a_strategy_example():
    """The generated lists decide which cases are named where; the prose must not contradict them."""
    text = (ROOT / "DEMO_SCRIPT.md").read_text(encoding="utf-8")
    assert "not** as examples of strategy mattering" in text or "not as examples of strategy mattering" in text.replace("**", "")
    assert "cookie-jar" in text and "garden-dog" in text  # they are listed, in the group where the evidence alone decides
    flat_line = next(line for line in text.splitlines() if "evidence alone decides" in line)
    assert "cookie-jar" in flat_line and "garden-dog" in flat_line
