"""Run the best-response search for the committed results: results/oracle/<case>[_surprises].json.

The three cases are the ones the "does strategy matter" measure found strategy to matter in (helix-espionage and kestrel-av,
decided by the lawyers; broken-bike, partly). Cases where the evidence alone decides have nothing for a better lawyer to move.
Nothing is tuned: whatever is found is written down.

    python scripts/run_oracle_results.py [--workers 4]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from courtroom.cases import CASES
from courtroom.contracts import Surprises
from courtroom.gametheory.oracle import run_oracle

OUT = Path(__file__).resolve().parent.parent / "results" / "oracle"
CASE_IDS = ("helix-espionage", "kestrel-av", "broken-bike")
BUDGET = 60
TRAIN = tuple(range(8))
HELDOUT = tuple(range(100, 124))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for cid in CASE_IDS:
        for sur in (False, True):
            t0 = time.time()
            r = run_oracle(CASES[cid], budget=BUDGET, surprises=Surprises() if sur else None, train=TRAIN, heldout=HELDOUT, workers=a.workers)
            path = OUT / f"{cid}{'_surprises' if sur else ''}.json"
            path.write_text(json.dumps(json.loads(r.model_dump_json()), indent=1, sort_keys=True) + "\n", encoding="utf-8")
            print(f"{path.name}: {r.headline} ({time.time() - t0:.0f}s, {r.trials} trials)", flush=True)


if __name__ == "__main__":
    main()
