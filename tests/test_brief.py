"""The case brief is generated from the case file and the judge's constants, so it cannot drift from the engine."""

from __future__ import annotations

import ast
import json
from fractions import Fraction
from pathlib import Path

import pytest

from courtroom.cases import ADVERSE_CASES, CASES, WITNESS_CASES
from courtroom.contracts import Side
from courtroom.judge import rules
from courtroom.judge.brief import build_brief
from courtroom.judge.rules import PRIOR_LOG_ODDS, fmt, sigmoid, threshold_for

ALL = {**CASES, **WITNESS_CASES, **ADVERSE_CASES}


@pytest.mark.parametrize("case_id", sorted(ALL))
def test_the_burden_numbers_are_the_ones_the_judge_uses(case_id: str) -> None:
    case = ALL[case_id]
    b = build_brief(case).burden
    tau, prior = threshold_for(case), PRIOR_LOG_ODDS[case.case_type]
    assert b.bar_log_odds == fmt(tau) and b.presumption_log_odds == fmt(prior)
    assert b.shift_needed == fmt(tau - prior) and Fraction(b.shift_needed) == tau - prior
    assert b.bar_probability == round(100 * sigmoid(float(tau)), 1)
    assert b.presumption_probability == round(100 * sigmoid(float(prior)), 1)
    assert b.bearer == Side.PROSECUTION.value


@pytest.mark.parametrize("case_id", sorted(ALL))
def test_the_issues_are_the_cases_own_elements_in_order(case_id: str) -> None:
    case = ALL[case_id]
    brief = build_brief(case)
    assert [i.id for i in brief.issues] == [e.id for e in case.elements]
    assert [i.name for i in brief.issues] == [e.name for e in case.elements]
    assert [i.question for i in brief.issues] == [e.description for e in case.elements]
    for issue in brief.issues:
        pro = sum(1 for x in case.evidence if x.support.get(issue.id, 0) > 0)
        con = sum(1 for x in case.evidence if x.support.get(issue.id, 0) < 0)
        assert issue.supporting_exhibits == {"prosecution": pro, "defense": con}


def test_the_burden_is_stated_before_any_evidence_for_both_kinds_of_case() -> None:
    criminal = build_brief(CASES["helix-espionage"])
    civil = build_brief(CASES["kestrel-av"])
    assert "carries the burden" in criminal.burden.statement and "does not have to prove anything" in criminal.burden.statement
    assert criminal.kind == "Criminal prosecution" and civil.kind == "Civil claim"
    assert criminal.burden.bar_probability > 85 and civil.burden.bar_probability == 50.0
    assert "not proved" in civil.burden.tie_rule and "counts as proved" in criminal.burden.tie_rule


def test_moving_the_bar_moves_the_brief() -> None:
    case = CASES["helix-espionage"].model_copy(update={"bar_log_odds": "11/10"})
    assert build_brief(case).burden.bar_probability == 75.0 and build_brief(CASES["helix-espionage"]).burden.bar_probability == 90.0


def test_the_brief_follows_the_judges_constants_when_they_change(monkeypatch: pytest.MonkeyPatch) -> None:
    before = " ".join(build_brief(CASES["helix-espionage"]).how_the_judge_weighs)
    assert "At most 4 facts per side" in before
    monkeypatch.setattr(rules, "MAX_FACTS_PER_SIDE", None)
    monkeypatch.setattr(rules, "IMPEACHMENT_FACTOR", Fraction(1, 3))
    after = " ".join(build_brief(CASES["helix-espionage"]).how_the_judge_weighs)
    assert "no cap" in after and "1/3" in after and after != before


def test_it_is_deterministic_and_carries_nothing_hidden() -> None:
    for case in ALL.values():
        a, b = build_brief(case), build_brief(case)
        assert a == b
        text = json.dumps(a.model_dump()).lower()
        for word in ("hearsay", "authenticated", "lawfully", "disclosed", "personal_knowledge", "impartial", "consistent"):
            assert word not in text, (case.id, word)
        for item in case.evidence:
            assert item.id.lower() not in text and item.title.lower() not in text


def test_published_risks_appear_only_when_the_case_has_them() -> None:
    assert build_brief(CASES["helix-espionage"]).published_risks == []
    risks = " ".join(build_brief(ADVERSE_CASES["helix-espionage-adverse"]).published_risks)
    assert "10%" in risks and "15%" in risks and "65B" in risks
    assert build_brief(WITNESS_CASES["kestrel-av-witnesses"]).published_risks


def test_the_shipped_bundle_holds_the_brief_the_engine_builds_now() -> None:
    text = (Path(__file__).resolve().parent.parent / "courtroom" / "viz" / "web" / "data" / "bundle.js").read_text(encoding="utf-8")
    data = json.loads(text[len("window.COURTROOM_BUNDLE = ") :].rstrip().rstrip(";"))
    assert set(data["briefs"]) == set(CASES)
    for cid, case in CASES.items():
        assert data["briefs"][cid] == json.loads(build_brief(case).model_dump_json()), f"{cid}: the bundled brief is stale"


def test_the_brief_module_reaches_nothing_but_the_core() -> None:
    path = Path(__file__).resolve().parent.parent / "courtroom" / "judge" / "brief.py"
    imported = {
        n.module for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.ImportFrom) and n.module
    }
    assert not any(m.startswith("courtroom.llm") or m.startswith("courtroom.api") for m in imported)


# ----------------------------------------------------------------------- the API


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from courtroom.api.server import create_app

    return TestClient(create_app())


def test_the_api_serves_the_same_brief(client) -> None:
    r = client.get("/api/brief/aurora-defi")
    assert r.status_code == 200 and r.json() == json.loads(build_brief(CASES["aurora-defi"]).model_dump_json())
    assert client.get("/api/brief/no-such-case").status_code in (404, 422)


def test_a_custom_case_gets_a_brief_at_the_bar_it_asks_for(client) -> None:
    case = json.loads(CASES["edge-mutual-exclusion"].model_dump_json())
    r = client.post("/api/brief", json={"case": case, "bar": 0.8})
    assert r.status_code == 200
    assert r.json()["burden"]["bar_probability"] == 80.0
