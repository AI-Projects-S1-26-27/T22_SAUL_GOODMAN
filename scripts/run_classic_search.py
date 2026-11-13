"""Search generated cases for the classic games and save what was found under results/.

    python scripts/run_classic_search.py [--surprises] [--start 0] [--count 120]

The search spots a prisoner's dilemma, stag hunt or battle of the sexes on a few seeds, then re-measures it on a disjoint set of fresh
seeds and keeps it only if the same two-by-two game carries the same name there. Nothing is tuned; a case either shows the game or not.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from courtroom.contracts import Surprises
from courtroom.gametheory.finder import find_classic

RESULTS = Path(__file__).resolve().parent.parent / "results"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--surprises", action="store_true")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=120)
    a = ap.parse_args()
    t0 = time.time()
    rep = find_classic(start=a.start, count=a.count, surprises=Surprises() if a.surprises else None, per_label=5)
    path = RESULTS / f"classic_search{'_surprises' if a.surprises else ''}.json"
    out = json.loads(rep.model_dump_json())
    out["seconds"] = 0  # wall-clock time is not a result; keeping it out keeps the file reproducible
    path.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path} in {time.time() - t0:.0f}s; label counts {rep.label_counts}; found {len(rep.found)}")


if __name__ == "__main__":
    main()
