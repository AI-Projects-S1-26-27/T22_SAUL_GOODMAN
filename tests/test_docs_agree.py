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


# ----------------------------------------------------------------------- DEVIATIONS D19 and the rewritten RESULTS tables, against the data

DEVIATIONS = (ROOT / "DEVIATIONS.md").read_text(encoding="utf-8")
D19 = DEVIATIONS.split("## D19 ")[1].split("## Corrections to claims made about the repo")[0]
BUNDLE = json.loads(
    (ROOT / "courtroom" / "viz" / "web" / "data" / "bundle.js").read_text(encoding="utf-8")[len("window.COURTROOM_BUNDLE = ") :].rstrip().rstrip(";")
)


def test_d19_quotes_figures_that_are_in_the_data() -> None:
    from courtroom.cases import CASES, PLAIN_CASES
    from courtroom.engine import run_trial

    events = (ROOT / "results" / "calibration" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    cases = (ROOT / "results" / "calibration" / "cases.jsonl").read_text(encoding="utf-8").splitlines()
    assert f"{len(events)} settings" in D19 and f"{len(cases)} values" in D19 and f"({len(cases)} of {len(cases)} values)" in D19
    assert "11 of 20 settings" in D19
    old = json.loads((ROOT / "tests" / "golden" / "digests_plain.json").read_text(encoding="utf-8"))
    new = json.loads((ROOT / "tests" / "golden" / "digests.json").read_text(encoding="utf-8"))
    moved = sum(1 for k in old if old[k]["digest"] != new[k]["digest"])
    assert f"{moved} of 42 changed" in D19, moved
    helix = PAYOFFS["helix-espionage"]["analysis"]["equilibria"][0]["row_mix_exact"]
    assert f"({helix['conservative']} and {helix['adaptive']} for the prosecution)" in D19
    for cid in ("aurora-defi", "kestrel-av"):
        assert BOOT[cid]["baseline_label"] == "dominance-solvable"
    assert "stability 80.5% becomes 100.0% label, 99.0% support" in D19 and BOOT["aurora-defi"]["stability"] == 1.0
    assert "98.0% becomes 99.5%" in D19 and BOOT["kestrel-av"]["stability"] == 0.995
    assert {cid for cid, c in CASES.items() if c.adverse_events} == {"helix-espionage", "aurora-defi", "kestrel-av", "edge-poisoned-tree"}
    assert run_trial(CASES["edge-mutual-exclusion"], "aggressive", "aggressive", seed=0).digest == run_trial(PLAIN_CASES["edge-mutual-exclusion"], "aggressive", "aggressive", seed=0).digest


def test_d14_is_still_there_and_still_says_what_it_said() -> None:
    d14 = DEVIATIONS.split("## D14 ")[1].split("## D15 ")[0]
    assert "this IS result-driven case design" in DEVIATIONS.split("## D14")[1].split("\n")[0]
    assert "Superseded by D19" in d14 and "the values were chosen by measuring, after D3 had refused to" in d14
    assert "about 20 configurations" in d14 and "narrow band, not a robust design" in d14


def test_results_ladder_is_the_ladder_in_the_bundle_built_from_the_certified_run() -> None:
    rows = re.findall(r"^\| (\d+)%(?: \(own\))? \| ([a-z-]+) \| .*? \| ([\d.]+)% \|$", RESULTS.split("`helix-espionage`:")[1].split("Read it as a shape")[0], flags=re.M)
    bars = BUNDLE["analysis"]["threshold_grid"]["helix-espionage"]["bars"]
    assert len(rows) == len(bars) == 7
    for (pct, label, win), bar in zip(rows, bars, strict=True):
        assert int(pct) == round(100 * bar["bar"]) and label == bar["label"], pct
        assert float(win) == round(100 * bar["prosecution_win_rate_at_equilibrium"], 1), pct


def test_results_sensitivity_table_is_the_one_in_the_data() -> None:
    sens = json.loads((ROOT / "results" / "sensitivity.json").read_text(encoding="utf-8"))
    base = sens["baseline"]
    for cid in sens["case_ids"]:
        survives = sum(1 for v in sens["variations"] if v["labels"][cid] == base[cid])
        line = next(x for x in RESULTS.splitlines() if x.startswith(f"| `{cid}` | ") and ("of 14" in x or "every variation" in x))
        assert ("**every variation**" in line) == (survives == 14), cid
        if survives != 14:
            assert f"| {survives} of 14 |" in line, cid


def test_results_standard_of_proof_table_is_the_one_in_the_data() -> None:
    sens = json.loads((ROOT / "results" / "sensitivity.json").read_text(encoding="utf-8"))
    for v in sens["variations"]:
        if v["parameter"] == "beyond_reasonable_doubt":
            pct = round(100 * float(v["setting"].split("=")[1]))
            win = f"{v['prosecution_win_rate']['helix-espionage']:.3f}"
            assert re.search(rf"^\| (?:\*\*)?{pct}%.*\| \*?\*?{win}\*?\*? \|$", RESULTS, flags=re.M), (pct, win)
