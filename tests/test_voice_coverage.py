"""Every spoken line of every recorded trial has a recorded clip (AGENTS.md section 4.4), and every clip in the manifest exists."""

from __future__ import annotations

import json

from tests.ui_support import WEB, page, static_server

COVERAGE_JS = """async () => {
  const man = await (await fetch("voices/manifest.json")).json();
  const missing = []; let lines = 0;
  for (const t of Object.values(COURTROOM_BUNDLE.trials)) {
    S.caseId = t.case_id; S.trial = t;
    for (const ev of t.events) for (const b of narrate(ev).beats) {
      lines++;
      const key = (b.who === "witness" ? "witness:" + b.name : b.who) + "|" + b.text;
      if (!man[key]) missing.push(key.slice(0, 120));
    }
  }
  return { lines, missing: [...new Set(missing)] };
}"""


def test_every_line_of_every_bundled_trial_has_a_clip() -> None:
    with static_server() as base, page() as (pg, errors):
        pg.goto(f"{base}/index.html")
        pg.wait_for_function("window.COURTROOM_BUNDLE && typeof narrate === 'function'")
        res = pg.evaluate(COVERAGE_JS)
        assert res["lines"] > 1000
        assert res["missing"] == [], res["missing"]
        assert errors == []


def test_every_manifest_entry_points_at_an_existing_clip() -> None:
    man = json.loads((WEB / "voices" / "manifest.json").read_text())
    gone = [k for k, f in man.items() if not (WEB / "voices" / f).exists()]
    assert gone == []
