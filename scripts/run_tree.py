"""Solve the open-file trial tree for several cases and save the result under results/tree_search.json.

    python scripts/run_tree.py [--workers 4]

For each case: plain minimax, alpha-beta, and alpha-beta with best-first move ordering, their node counts, and a check that the three
values are identical. Cases too big for a search are recorded as such, with the node limit that was hit. Also saves one small pruned tree
(gen-51) for the lab to draw. The open-file relaxation and its assumptions are stated in courtroom/gametheory/search.py.
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from courtroom.cases import CASES, generate_case
from courtroom.gametheory.search import solve_case, trace

RESULTS = Path(__file__).resolve().parent.parent / "results"

# (case id, node limit, also run plain minimax and unordered alpha-beta?)
JOBS: list[tuple[str, int, bool]] = [
    *((cid, 1_000_000, True) for cid in ("cookie-jar", "broken-bike", "garden-dog", "edge-empty-docket", "edge-mutual-exclusion", "edge-defense-only", "edge-poisoned-tree")),
    *((f"gen-{n}", 1_000_000, True) for n in (6, 20, 27, 39, 44, 51, 57, 62)),
    ("kestrel-av", 400_000, False),
    ("aurora-defi", 400_000, False),
    ("helix-espionage", 60_000, False),
]


def _case(cid: str):
    return generate_case(int(cid[4:])) if cid.startswith("gen-") else CASES[cid]


def _solve(job: tuple[str, int, bool]) -> dict[str, object]:
    cid, cap, everything = job
    rep = solve_case(_case(cid), max_nodes=cap, with_minimax=everything, with_unordered=everything, with_line=True)
    d = json.loads(rep.model_dump_json())
    d["node_limit"] = cap
    d["ran_all_three"] = everything  # False: only the ordered alpha-beta was run (the others would not finish)
    d["seconds"] = 0  # wall-clock time is not a result
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        rows = list(pool.map(_solve, JOBS))
    example = trace(generate_case(51))
    out = {
        "relaxation": "open file: both sides see every exhibit and flaw, no perception noise; zero-sum payoff (Accuser utility minus Defender utility)",
        "cases": {r["case_id"]: r for r in rows},
        "example": {"case_id": "gen-51", "tree": example},
    }
    path = RESULTS / "tree_search.json"
    path.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
