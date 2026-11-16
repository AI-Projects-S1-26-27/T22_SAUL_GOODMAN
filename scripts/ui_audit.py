"""Walk every case through the home page and every lab chapter in a real browser and list suspicious numbers.

    python scripts/ui_audit.py                 # recorded mode (static files, as on the hosted site)
    python scripts/ui_audit.py --live          # with the local server running (live controls on)
    python scripts/ui_audit.py --json out.json

It flags, per case and section: text that says NaN / null / undefined / Infinity / [object, empty table cells, tables whose numbers are
all zero or all equal, and chapters whose text does not change at all when the case changes (stale state). A flag is a question, not a
verdict: someone has to decide from results/ whether it is a true value or a bug (that decision is recorded in docs/UI_AUDIT.md).
Needs playwright and its Chromium.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BAD = re.compile(r"\b(NaN|undefined|null|Infinity)\b|\[object|—NaN|NaN%")
NUM = re.compile(r"^[−+-]?\d+(\.\d+)?%?$")

JS_TABLES = """(root) => [...root.querySelectorAll('table')].map((t, k) => ({
  k, label: t.getAttribute('aria-label') || (t.closest('.chapter') ? t.closest('.chapter').id : '') ,
  cells: [...t.querySelectorAll('td')].map((c) => c.innerText.trim()),
  head: [...t.querySelectorAll('th')].map((c) => c.innerText.trim()).slice(0, 4).join(' | ')}))"""


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def numeric_tokens(cells: list[str]) -> list[str]:
    out = []
    for c in cells:
        for tok in re.findall(r"[−+-]?\d+(?:\.\d+)?%?", c):
            out.append(tok.replace("−", "-"))
    return out


def judge_table(cells: list[str]) -> str | None:
    if not cells:
        return "empty table"
    if any(c == "" for c in cells):
        return f"{sum(c == '' for c in cells)} blank cell(s)"
    toks = numeric_tokens(cells)
    if len(toks) >= 4:
        vals = {float(t.rstrip("%")) for t in toks}
        if vals == {0.0}:
            return "all zeros"
        if len(vals) == 1:
            return f"all equal ({toks[0]})"
    return None


def audit(base: str, live: bool) -> dict:
    from playwright.sync_api import sync_playwright

    findings: list[dict] = []
    fingerprints: dict[str, dict[str, str]] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1300, "height": 900})
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
        ctx.add_init_script("try { localStorage.setItem('courtroom-tour-home-v3', 'seen'); localStorage.setItem('courtroom-tour-lab-v3', 'seen'); } catch (e) {}")
        pg = ctx.new_page()
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append("console: " + m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)

        def flag(case: str, page: str, section: str, shown: str, why: str) -> None:
            findings.append({"case": case, "page": page, "section": section, "shown": shown[:160], "why": why, "mode": "live" if live else "recorded"})

        # ---------------------------------------------------------------- home page
        pg.goto(f"{base}/index.html")
        pg.wait_for_function("window.selectCase && document.querySelector('#strat-case option')")
        cases = pg.evaluate("B.cases.map((c) => c.id)")
        for cid in cases:
            pg.evaluate(f"selectCase('{cid}')")
            pg.wait_for_timeout(250)
            cells = pg.locator("#matrix .cell").all_inner_texts()
            tex = pg.inner_text("#strategy")
            if BAD.search(tex):
                flag(cid, "home", "which style wins", BAD.search(tex).group(0), "bad token")
            if len(cells) != 16:
                flag(cid, "home", "which style wins", f"{len(cells)} cells", "not a 4x4 grid")
            wins = [c.split("\n")[0] for c in cells]
            if len(set(wins)) == 1:
                note = pg.inner_text("#strat-flat") if pg.is_visible("#strat-flat") else ""
                flag(cid, "home", "which style wins", f"every cell {wins[0]}", "all equal; sentence shown: " + (note[:60] or "NONE"))
            if pg.input_value("#strat-case") != cid:
                flag(cid, "home", "which style wins", pg.input_value("#strat-case"), "dropdown out of sync with docket")
            fingerprints.setdefault("home:which-style-wins", {})[cid] = hashlib.md5(tex.encode()).hexdigest()
            for sel in ("#start-case", "#combo-note"):
                t = pg.inner_text(sel) if pg.locator(sel).count() else ""
                if BAD.search(t):
                    flag(cid, "home", sel, t, "bad token")

        # ---------------------------------------------------------------- lab
        pg.goto(f"{base}/lab.html")
        pg.wait_for_selector("#lab-case")
        pg.wait_for_selector(".chapter")
        for cid in cases:
            pg.select_option("#lab-case", cid)
            pg.wait_for_timeout(1200 if not live else 2500)
            kp = pg.inner_text("#lab-kpis")
            if BAD.search(kp):
                flag(cid, "lab", "kpis", kp, "bad token")
            fingerprints.setdefault("lab:kpis", {})[cid] = hashlib.md5(kp.encode()).hexdigest()
            for ch in pg.locator(".chapter").all():
                chid = ch.get_attribute("id") or "?"
                tex = ch.inner_text()
                m = BAD.search(tex)
                if m:
                    i = m.start()
                    flag(cid, "lab", chid, tex[max(0, i - 40) : i + 30].replace("\n", " "), "bad token")
                for t in pg.evaluate(JS_TABLES, ch.element_handle()):
                    why = judge_table(t["cells"])
                    if why:
                        flag(cid, "lab", chid, f"{t['label'] or t['head']}: {' '.join(t['cells'][:6])}", "table " + why)
                # svg charts: every number printed on a chart axis or label
                for k, sv in enumerate(ch.locator("svg").all()):
                    texts = [x.strip() for x in sv.locator("text").evaluate_all("els => els.map((e) => e.textContent || '')") if NUM.match(x.strip())]
                    if len(texts) >= 4 and len({t.rstrip("%") for t in texts}) == 1:
                        flag(cid, "lab", chid, f"chart {k}: all labels {texts[0]}", "chart all equal")
                fingerprints.setdefault(f"lab:{chid}", {})[cid] = hashlib.md5(tex.encode()).hexdigest()
        browser.close()
    unchanged = [k for k, v in fingerprints.items() if len(set(v.values())) == 1 and len(v) > 2]
    return {"live": live, "cases": cases, "findings": findings, "page_errors": sorted(set(errors)), "text_identical_for_every_case": unchanged}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    port = free_port()
    if a.live:
        proc = subprocess.Popen([sys.executable, "-m", "courtroom", "serve", "--port", str(port)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        proc = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=ROOT / "courtroom" / "viz" / "web", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                socket.create_connection(("127.0.0.1", port), 0.3).close()
                break
            except OSError:
                time.sleep(0.25)
        res = audit(f"http://127.0.0.1:{port}", a.live)
    finally:
        proc.terminate()
    out = json.dumps(res, indent=1)
    if a.json:
        Path(a.json).write_text(out)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
