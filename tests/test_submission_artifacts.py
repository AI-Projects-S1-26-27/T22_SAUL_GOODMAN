"""The submission artefacts (slides, report) are generated from results/ and stay in step with them."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MEMBERS = ("Aditya Singh", "Divvij", "Lakshya Sachdeva", "Mofasser", "Rohan", "Pramit Khandelwal", "Rakshit Goel")


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)


def test_submission_facts_match_the_results() -> None:
    p = _run("scripts/submission_facts.py", "--check")
    assert p.returncode == 0, p.stdout + p.stderr


def test_report_generated_files_match_the_results() -> None:
    p = _run("report/build_report.py", "--check")
    assert p.returncode == 0, p.stdout + p.stderr


def test_report_prose_types_no_measured_percentages() -> None:
    """A measured percentage with a decimal (87.0\\%) must come from a macro or a generated table, never from the prose."""
    bad = []
    for f in sorted((ROOT / "report" / "sections").glob("*.tex")):
        for n, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\d\.\d+\s*\\%", ln):
                bad.append(f"{f.name}:{n}")
    assert bad == []


def test_report_has_every_section_the_brief_requires_and_every_member() -> None:
    text = "".join(f.read_text(encoding="utf-8") for f in sorted((ROOT / "report" / "sections").glob("*.tex")))
    for head in ("Introduction", "Background and related work", "Method", "Results and evaluation", "Discussion and limitations", "Individual contributions", "AI usage", "Deviations from the proposal", "thebibliography"):
        assert head in text, head
    for m in MEMBERS:
        assert m in text, m
    assert "MEMBER ADDS OWN AI USE" not in text  # every member has an AI-use line


def test_the_committed_pdfs_exist() -> None:
    assert (ROOT / "report" / "Saul_Goodman_T22_Report.pdf").stat().st_size > 50_000
    assert (ROOT / "presentation" / "Saul_Goodman_T22.pdf").stat().st_size > 20_000


def test_deck_has_exactly_six_slides_in_the_required_order_with_timed_notes() -> None:
    pptx = pytest.importorskip("pptx")
    prs = pptx.Presentation(ROOT / "presentation" / "Saul_Goodman_T22.pptx")
    slides = list(prs.slides)
    assert len(slides) == 6
    minutes = 0.0
    for s in slides:
        notes = s.notes_slide.notes_text_frame.text
        m = re.match(r"\[Target time (\d+):(\d+)\]", notes)
        assert m, notes[:40]
        minutes += int(m.group(1)) + int(m.group(2)) / 60
    assert minutes <= 6.5  # leaves the rest of the slot for the live demo
    titles = [" ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)[:400].lower() for s in slides]
    for i, words in enumerate((("saul goodman", "22", "github.com/ai-projects-s1-26-27/t22_saul_goodman", "demo"), ("problem",), ("related work",), ("methods",), ("results",), ("project management",))):
        for w in words:
            assert w in titles[i] or (i == 0 and w in " ".join(sh.text_frame.text for sh in slides[0].shapes if sh.has_text_frame).lower()), (i, w)
