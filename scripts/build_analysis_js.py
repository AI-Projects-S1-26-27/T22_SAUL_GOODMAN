"""Write courtroom/viz/web/data/analysis.js from the certified files in results/.

The hosted site has no server, so the lab reads its confidence intervals, sensitivity table and best-response results from this
generated file. It is never edited by hand: re-run this after any change under results/. A test fails if it is out of date.

    python scripts/build_analysis_js.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
OUT = ROOT / "courtroom" / "viz" / "web" / "data" / "analysis.js"


def build() -> str:
    data: dict[str, object] = {}
    for path in sorted(RESULTS.glob("*.json")):
        data[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    oracle = RESULTS / "oracle"
    if oracle.is_dir():
        data["oracle"] = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(oracle.glob("*.json"))}
    return "window.COURTROOM_ANALYSIS = " + json.dumps(data, separators=(",", ":"), sort_keys=True) + ";\n"


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KiB)")
