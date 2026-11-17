"""Measure the proposal's evaluation plan (proposal section 8) and write report/generated/eval_plan.json.

    python scripts/eval_plan.py            # runs the stress fuzz (every trial replayed), the timing, the edge fixtures and the test groups

For each row of the plan it records the evidence the PDF report quotes: how many tests of a named group pass, the stress report, the
timing of every recorded pairing, the verdict and rule of each edge fixture. Nothing is typed by hand; the report reads the JSON.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "report" / "generated" / "eval_plan.json"
PY = sys.executable

GROUPS = {  # plan row -> test files that back it
    "correctness": ["tests/test_judge.py", "tests/test_judge_boundaries.py", "tests/test_gametheory.py", "tests/test_nash_edges.py"],
    "robustness": ["tests/test_engine.py", "tests/test_contracts_and_cases.py", "tests/test_procedure.py", "tests/test_review_robustness.py", "tests/test_agents.py"],
    "analysis": ["tests/test_analysis.py", "tests/test_classic.py", "tests/test_efficiency.py", "tests/test_search.py", "tests/test_lookahead.py"],
    "live_demo": ["tests/test_api.py", "tests/test_api_hardening.py", "tests/test_live_api.py", "tests/test_cli_smoke.py", "tests/test_ui_editor_absurd.py", "tests/test_voice_coverage.py", "tests/test_bundle_digests.py"],
}


def pytest_counts(files: list[str]) -> dict:
    import tempfile
    import xml.etree.ElementTree as ET

    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / "r.xml"
        p = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}", *files], cwd=ROOT, capture_output=True, text=True)
        suite = ET.parse(xml).getroot()
        suite = suite if suite.tag == "testsuite" else suite[0]
        total, bad, skipped = int(suite.get("tests", 0)), int(suite.get("failures", 0)) + int(suite.get("errors", 0)), int(suite.get("skipped", 0))
    return {"files": files, "passed": total - bad - skipped, "failed": bad, "skipped": skipped, "returncode": p.returncode}


def timing() -> dict:
    from courtroom.cases import CASES
    from courtroom.engine import run_trial

    styles = ("aggressive", "conservative", "adaptive", "reckless")
    ms = []
    for cid in CASES:
        for p in styles:
            for d in styles:
                t0 = time.perf_counter()
                run_trial(CASES[cid], p, d, 0)
                ms.append((time.perf_counter() - t0) * 1000)
    return {"trials": len(ms), "median_ms": round(statistics.median(ms), 1), "max_ms": round(max(ms), 1), "under_1s": max(ms) < 1000}


def replays() -> dict:
    """Every recorded trial run again: same digest as pinned, and the hash chain verifies."""
    from courtroom.cases import CASES
    from courtroom.engine import run_trial, verify_chain

    pinned = json.loads((ROOT / "tests/golden/bundle_digests.json").read_text())
    same = chain = 0
    for key, digest in pinned.items():
        cid, p, d, seed = key.split("|")
        r = run_trial(CASES[cid], p, d, int(seed))
        same += r.digest == digest
        chain += bool(verify_chain(r.events))
    return {"recorded_trials": len(pinned), "same_digest": same, "chain_valid": chain}


def edge_fixtures() -> list[dict]:
    from courtroom.cases import CASES
    from courtroom.engine import run_trial

    out = []
    for cid in sorted(c for c in CASES if c.startswith("edge-")):
        r = run_trial(CASES[cid], "aggressive", "conservative", 0)
        rules = sorted({x.rule_id for e in r.events for x in e.rules})
        spent = {side.value: round(led.budget_start - led.budget, 2) for side, led in r.ledgers.items()}
        out.append({"case": cid, "outcome": r.verdict.outcome, "reason": r.verdict.reason, "rules": rules, "budget_spent": spent})
    return out


def stress_full() -> dict:
    from courtroom.gametheory import stress

    t0 = time.time()
    rep = stress(n_cases=100, replay_every=1)
    return {"trials": rep.trials, "crashes": rep.crashes, "invariant_failures": rep.invariant_failures, "deterministic_replays": rep.deterministic_replays, "max_events": rep.max_events, "mean_ms": rep.mean_ms, "seconds": round(time.time() - t0)}


def main() -> int:
    ev = {"timing": timing(), "replays": replays(), "edge_fixtures": edge_fixtures(), "stress": stress_full(), "tests": {k: pytest_counts(v) for k, v in GROUPS.items()}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(ev, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: ev[k] for k in ("timing", "replays", "stress")}, indent=1))
    print({k: (v["passed"], v["failed"]) for k, v in ev["tests"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
