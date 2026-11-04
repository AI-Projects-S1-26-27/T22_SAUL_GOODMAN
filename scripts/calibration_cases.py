"""Re-calibrate the two rebalanced cases with adverse events ON at given rates (DEVIATIONS D19, docs/CALIBRATION_SWEEP.md).

    python scripts/calibration_cases.py --no-show 0.1 --missing-certificate 0.15 --hostile 0.1 --out results/calibration/cases.jsonl

* ``kestrel-av``: strength of the one clean ``defect`` exhibit ``P-RECALL`` (reliability 0.70).
* ``aurora-defi``: a scale on the three defense intent exhibits (``D-BOUNTY``, ``D-RETURN``, ``D-ZHAO``); 1.0 is the shipped value.

One line per value, appended as it is measured; a value already in the file is skipped.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from courtroom.cases import PLAIN_CASES
from courtroom.gametheory.calibration import measure_case, run_cells, with_events

KESTREL = [0.0, 0.05, 0.075, 0.10, 0.125, 0.135, 0.15, 0.165, 0.175, 0.20, 0.225, 0.25, 0.275, 0.30, 0.35, 0.40, 0.50]
AURORA = [0.6, 0.7, 0.8, 0.9, 0.95, 0.96, 1.0, 1.05, 1.1, 1.15, 1.2, 1.3, 1.4, 1.6, 1.8]
#: The defense intent exhibits as first shipped (D14); a scale of 1.0 means these values.
AURORA_BASE = {"D-BOUNTY": -0.42, "D-RETURN": -0.45, "D-ZHAO": -0.45}


def kestrel_with(case, strength: float):
    items = [e for e in case.evidence if e.id != "P-RECALL"]
    if strength > 0:
        recall = next(e for e in case.evidence if e.id == "P-RECALL")
        items.append(recall.model_copy(update={"support": {"defect": round(strength, 4)}}))
    return case.model_copy(update={"evidence": tuple(items)})


def aurora_with(case, scale: float):
    items = [
        e.model_copy(update={"support": {"fraud_intent": round(AURORA_BASE[e.id] * scale, 4)}}) if e.id in AURORA_BASE else e
        for e in case.evidence
    ]
    return case.model_copy(update={"evidence": tuple(items)})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-show", type=float, required=True)
    ap.add_argument("--missing-certificate", type=float, required=True)
    ap.add_argument("--hostile", type=float, required=True)
    ap.add_argument("--hostile-credibility", default="1/4")
    ap.add_argument("--out", default="results/calibration/cases.jsonl")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seeds", type=int, default=200)
    ap.add_argument("--resamples", type=int, default=200)
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {(r["case"], r["value"]) for r in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    rates = (a.no_show, a.missing_certificate, a.hostile, a.hostile_credibility)
    for case_id, values, build in (("kestrel-av", KESTREL, kestrel_with), ("aurora-defi", AURORA, aurora_with)):
        for v in values:
            if (case_id, v) in done:
                continue
            case = with_events(build(PLAIN_CASES[case_id], v), *rates)
            cells = run_cells({case_id: case}, range(a.seeds), workers=a.workers)
            record = {"case": case_id, "value": v, "rates": list(rates), **measure_case(cells[case_id], n_resamples=a.resamples)}
            with out.open("a") as fh:
                fh.write(json.dumps(record) + "\n")
            print(f"{case_id} {v}: {record['label']} stab {record['label_stability']}/{record['support_stability']} win {record['win_min']}-{record['win_max']}", flush=True)


if __name__ == "__main__":
    main()
