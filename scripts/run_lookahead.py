"""Compare the lookahead lawyer with the four hand-written styles on every library case and save results/lookahead*.json.

    python scripts/run_lookahead.py [--surprises] [--seeds 40] [--workers 4]

An exhibition: lookahead is labelled "not certified" wherever it appears. Nothing is tuned: it is one fixed lawyer, run once.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from courtroom.cases import CASES
from courtroom.contracts import Surprises
from courtroom.gametheory.lookahead_eval import compare_lookahead

RESULTS = Path(__file__).resolve().parent.parent / "results"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--surprises", action="store_true")
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    t0 = time.time()
    sur = Surprises() if a.surprises else None
    cases = {cid: json.loads(compare_lookahead(c, tuple(range(a.seeds)), sur, a.workers).model_dump_json()) for cid, c in CASES.items()}
    out = {"surprises": a.surprises, "n_seeds": a.seeds, "exhibition": True, "cases": cases}
    path = RESULTS / f"lookahead{'_surprises' if a.surprises else ''}.json"
    path.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
