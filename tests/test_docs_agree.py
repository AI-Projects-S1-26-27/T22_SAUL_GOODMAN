"""RESULTS.md, HANDOFF.md and the sweep document quote the same figures, and those figures are the data's (DEVIATIONS D19)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = (ROOT / "RESULTS.md").read_text(encoding="utf-8")
HANDOFF = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
SWEEP = (ROOT / "docs" / "CALIBRATION_SWEEP.md").read_text(encoding="utf-8")
BOOT = {r["case_id"]: r for r in json.loads((ROOT / "results" / "bootstrap.json").read_text(encoding="utf-8"))}
PAYOFFS = {r["case_id"]: r for r in json.loads((ROOT / "results" / "payoffs.json").read_text(encoding="utf-8"))}
EVENTS = {json.loads(x)["name"]: json.loads(x) for x in (ROOT / "results" / "calibration" / "events.jsonl").read_text(encoding="utf-8").splitlines()}
SHIPS_WITH_EVENTS = {"helix-espionage", "aurora-defi", "kestrel-av", "edge-poisoned-tree"}


def _support(cid: str) -> float:
    return EVENTS["default" if cid in SHIPS_WITH_EVENTS else "events-off"]["cases"][cid]["support_stability"]


def test_the_results_table_quotes_the_stabilities_in_the_data() -> None:
    rows = re.findall(r"^\| `([a-z-]+)` \| ([a-z-]+) \| \*\*([\d.]+)%\*\* \| ([\d.]+)% \|$", RESULTS, flags=re.M)
    assert {r[0] for r in rows} == set(BOOT)
    for cid, label, label_pct, support_pct in rows:
        assert label == BOOT[cid]["baseline_label"], cid
        assert float(label_pct) == round(100 * BOOT[cid]["stability"], 1), cid
        assert float(support_pct) == round(100 * _support(cid), 1), cid


def test_handoff_quotes_the_same_stabilities_as_results() -> None:
    quoted = dict(re.findall(r"(helix|aurora|kestrel) ([\d.]+/[\d.]+)", HANDOFF.split("### 3.1")[1].split("### 3.2")[0]))
    expected = {
        "helix": "helix-espionage", "aurora": "aurora-defi", "kestrel": "kestrel-av",
    }
    assert set(quoted) == set(expected)
    for short, cid in expected.items():
        assert quoted[short] == f"{100 * BOOT[cid]['stability']:.1f}/{100 * _support(cid):.1f}", short
    assert "the other four cases 100.0/100.0" in HANDOFF


def test_handoff_says_every_calibrated_case_holds_99_percent_and_that_is_true() -> None:
    assert "Stability is 99% or better for every case" in HANDOFF
    for cid in ("aurora-defi", "kestrel-av", "helix-espionage"):
        assert min(BOOT[cid]["stability"], _support(cid)) >= 0.99, cid


def test_results_quotes_the_helix_mixture_in_the_data() -> None:
    eq = PAYOFFS["helix-espionage"]["analysis"]["equilibria"][0]
    for mix in (eq["row_mix_exact"], eq["col_mix_exact"]):
        for value in mix.values():
            if value not in ("0", "1"):
                assert value in RESULTS, value


def test_results_equilibrium_counts_match_the_data() -> None:
    for cid, row in PAYOFFS.items():
        line = next(x for x in RESULTS.splitlines() if x.startswith(f"| `{cid}` | ") and ("Criminal" in x or "Civil" in x))
        assert f" | {len(row['analysis']['equilibria'])} | " in line, cid


def test_the_sweep_document_quotes_the_shipped_figures() -> None:
    assert "0.990" in SWEEP and "11 of 20" in SWEEP
    for cid in ("aurora-defi", "kestrel-av"):
        label = EVENTS["default"]["cases"][cid]["label"]
        assert label == "dominance-solvable"
    assert f"{100 * EVENTS['default']['cases']['aurora-defi']['support_stability']:.1f}%" in HANDOFF + RESULTS


def test_handoff_separates_what_is_resolved_from_what_is_not_for_each_known_issue() -> None:
    for start, end in (("### 3.1", "### 3.2"), ("### 3.2", "### 3.3"), ("### 3.3", "### 3.4")):
        section = HANDOFF.split(start)[1].split(end)[0]
        assert "**Resolved.**" in section and "**Not resolved.**" in section, start
        assert section.index("**Resolved.**") < section.index("**Not resolved.**"), start


def test_the_counts_handoff_quotes_are_the_counts_in_the_data() -> None:
    events = (ROOT / "results" / "calibration" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    cases = (ROOT / "results" / "calibration" / "cases.jsonl").read_text(encoding="utf-8").splitlines()
    assert f"{len(events)} settings" in HANDOFF and f"{len(cases)} values" in HANDOFF
    assert "11 of 20 settings" in HANDOFF and "x1.5" in HANDOFF and "99% or better" in HANDOFF
    cases_json = [json.loads(line) for line in cases]
    assert all(r["label"] == "dominance-solvable" for r in cases_json)  # "all 32 are dominance-solvable"
