"""Run a certified analysis and save it under results/. Every number in the docs is read back from these files.

    python scripts/run_analysis.py bootstrap [--surprises] [--workers 4]
    python scripts/run_analysis.py sensitivity [--surprises]
    python scripts/run_analysis.py matters [--surprises]
    python scripts/run_analysis.py classic [--surprises] [--workers 4]
    python scripts/run_analysis.py efficiency [--surprises] [--workers 4]

Only the deterministic styles and the exact judge are used here; no language model is involved.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from courtroom.cases import CASES, get_case
from courtroom.contracts import Surprises
from courtroom.gametheory.bootstrap import STYLES, bootstrap_library, collect_samples
from courtroom.gametheory.classic import classify_case
from courtroom.gametheory.efficiency import constant_sum_check, efficiency
from courtroom.gametheory.matters import measure
from courtroom.gametheory.payoff import estimate_payoffs
from courtroom.gametheory.sensitivity import sweep

RESULTS = Path(__file__).resolve().parent.parent / "results"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=("bootstrap", "sensitivity", "matters", "classic", "efficiency"))
    ap.add_argument("--surprises", action="store_true")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--seeds", type=int, default=0, help="seeds per cell (default: 100 bootstrap, 16 sensitivity)")
    ap.add_argument("--resamples", type=int, default=200)
    a = ap.parse_args()
    sur = Surprises() if a.surprises else None
    tag = "_surprises" if a.surprises else ""
    RESULTS.mkdir(exist_ok=True)
    t0 = time.time()
    if a.what == "bootstrap":
        seeds = tuple(range(a.seeds or 100))
        rows = bootstrap_library(list(CASES), seeds=seeds, n_resamples=a.resamples, workers=a.workers, surprises=sur)
        out = {"surprises": a.surprises, "n_seeds": len(seeds), "n_resamples": a.resamples, "cases": {r.case_id: json.loads(r.model_dump_json()) for r in rows}}
    elif a.what == "classic":
        seeds = tuple(range(a.seeds or 100))
        cases = {}
        for cid in CASES:
            samples = collect_samples(get_case(cid), STYLES, seeds, workers=a.workers, surprises=sur)
            cases[cid] = json.loads(classify_case(cid, samples, STYLES, STYLES, n_resamples=a.resamples, surprises=a.surprises).model_dump_json())
        out = {"surprises": a.surprises, "n_seeds": len(seeds), "n_resamples": a.resamples, "cases": cases}
    elif a.what == "efficiency":
        seeds = tuple(range(a.seeds or 100))
        cases = {}
        for cid in CASES:
            t = estimate_payoffs(get_case(cid), STYLES, seeds=seeds, workers=a.workers, surprises=sur)
            win = {(c.row, c.col): c.prosecution_win_rate for c in t.cells}
            W = [[win[(r, c)] for c in t.col_strategies] for r in t.row_strategies]
            cases[cid] = {
                "row_strategies": t.row_strategies,
                "col_strategies": t.col_strategies,
                "A": t.analysis.A,
                "B": t.analysis.B,
                "accuser_win_rate": W,
                "efficiency": json.loads(efficiency(t.analysis).model_dump_json()),
                "constant_sum": json.loads(constant_sum_check(W).model_dump_json()),
            }
        out = {"surprises": a.surprises, "n_seeds": len(seeds), "cases": cases}
    elif a.what == "matters":
        seeds = tuple(range(a.seeds or 8))
        out = {"surprises": a.surprises, "n_seeds": len(seeds), "cases": {cid: json.loads(measure(c, seeds=seeds, surprises=sur).model_dump_json()) for cid, c in CASES.items()}}
    else:
        seeds = tuple(range(a.seeds or 16))
        out = json.loads(sweep(list(CASES), seeds=seeds, surprises=sur).model_dump_json())
    path = RESULTS / f"{a.what}{tag}.json"
    path.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
