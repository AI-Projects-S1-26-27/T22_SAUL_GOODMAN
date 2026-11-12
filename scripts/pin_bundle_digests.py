"""Write tests/golden/bundle_digests.json: the digest of every recorded trial in the web bundle.

Run once, before touching the engine. The test re-runs every trial and compares.
"""
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
raw = (root / "courtroom/viz/web/data/bundle.js").read_text(encoding="utf-8")
bundle = json.loads(re.sub(r"^window\.COURTROOM_BUNDLE = |;\s*$", "", raw))
out = {k: t["digest"] for k, t in sorted(bundle["trials"].items())}
(root / "tests/golden/bundle_digests.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
print(len(out), "trials pinned")
