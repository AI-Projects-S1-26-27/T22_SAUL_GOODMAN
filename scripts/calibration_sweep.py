"""Sweep the four adverse-event parameters over every library case (DEVIATIONS D19, docs/CALIBRATION_SWEEP.md).

    python scripts/calibration_sweep.py --out results/calibration/events.jsonl --workers 4

One line is appended per setting as soon as it is measured, and a setting already in the file is skipped, so an interrupted run
resumes where it stopped. Takes about a minute per setting on four workers.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from courtroom.cases import CASES
from courtroom.gametheory.calibration import measure_case, run_cells, with_events

DEFAULT = {"no_show": 0.10, "missing_certificate": 0.15, "hostile": 0.10, "hostile_credibility": "1/4"}
GRID = {
    "no_show": [0.0, 0.05, 0.20, 0.30],
    "missing_certificate": [0.0, 0.05, 0.25, 0.35],
    "hostile": [0.0, 0.05, 0.20, 0.30],
    "hostile_credibility": ["3/4", "1/2", "1/8"],
}
SCALES = [0.5, 1.5, 2.0, 3.0]  # all three rates together, hostile credibility at its default


def settings() -> list[dict[str, object]]:
    out: list[dict[str, object]] = [{"name": "events-off", "off": True}, {"name": "default", **DEFAULT}]
    for key, values in GRID.items():
        for v in values:
            out.append({"name": f"{key}={v}", **{**DEFAULT, key: v}})
    for s in SCALES:
        out.append(
            {
                "name": f"scale x{s}",
                **{**DEFAULT, **{k: round(min(1.0, DEFAULT[k] * s), 4) for k in ("no_show", "missing_certificate", "hostile")}},
            }
        )
    return out


def case_set(setting: dict[str, object]) -> dict[str, object]:
    if setting.get("off"):
        return dict(CASES)
    return {
        cid: with_events(c, setting["no_show"], setting["missing_certificate"], setting["hostile"], setting["hostile_credibility"])  # type: ignore[arg-type]
        for cid, c in CASES.items()
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/calibration/events.jsonl")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seeds", type=int, default=200)
    ap.add_argument("--resamples", type=int, default=200)
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(line)["name"] for line in out.read_text().splitlines()} if out.exists() else set()
    for setting in settings():
        if setting["name"] in done:
            continue
        t0 = time.time()
        cases = case_set(setting)
        cells = run_cells(cases, range(a.seeds), workers=a.workers)  # type: ignore[arg-type]
        record = {
            **{k: v for k, v in setting.items() if k != "off"},
            "events_on": not setting.get("off"),
            "seeds": a.seeds,
            "resamples": a.resamples,
            "cases": {cid: measure_case(cells[cid], n_resamples=a.resamples) for cid in cases},
            "seconds": round(time.time() - t0, 1),
        }
        with out.open("a") as fh:
            fh.write(json.dumps(record) + "\n")
        print(f"{setting['name']}: {record['seconds']}s", flush=True)


if __name__ == "__main__":
    main()
