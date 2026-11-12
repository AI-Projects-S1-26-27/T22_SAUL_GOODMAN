"""Fill the generated regions of the docs from the certified files in results/. No number in those docs is typed by hand.

    python scripts/render_docs.py            # rewrite REPORT.md, PROVENANCE.md and DEMO_SCRIPT.md in place
    python scripts/render_docs.py --check    # exit 1 if any of them is out of date (a test runs this)

A generated region sits between ``<!-- BEGIN GENERATED:name -->`` and ``<!-- END GENERATED:name -->``. Everything outside the
markers is prose and contains no result numbers; ``tests/test_docs_generated.py`` checks that too.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DOCS = ("REPORT.md", "PROVENANCE.md", "DEMO_SCRIPT.md")
RESULTS = ROOT / "results"
NAMES = {"aggressive": "Bold", "conservative": "Careful", "adaptive": "Smart", "reckless": "Wild"}


def load(name: str) -> dict:
    path = RESULTS / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def pct(x: float, digits: int = 0) -> str:
    return f"{100 * x:.{digits}f}%"


def nm(n: str) -> str:
    if n in NAMES:
        return NAMES[n]
    m = re.match(r"best-(pro|def)-(\d+)", n)
    return f"Found {'Accuser' if m.group(1) == 'pro' else 'Defender'} {m.group(2)}" if m else n


def mix(m: dict) -> str:
    return ", ".join(f"{pct(v)} {nm(k)}" if v < 0.995 else nm(k) for k, v in sorted(m.items(), key=lambda kv: -kv[1])) or "none"


def table(head: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def case_names() -> dict[str, str]:
    from courtroom.cases import CASES

    return {cid: c.title.split(" — ")[-1] for cid, c in CASES.items()}


# --------------------------------------------------------------------------- blocks


def constants() -> str:
    from courtroom.judge import rules

    rows = [
        ["LLR_SCALE (K)", str(rules.LLR_SCALE), "log-odds an item of weight 1 contributes"],
        ["CORROBORATION_ALPHA (α)", str(rules.CORROBORATION_ALPHA), "most a corroborating fact can add to a weight"],
        ["CONTRADICTION_BETA (β)", str(rules.CONTRADICTION_BETA), "pairwise contradiction pressure"],
        ["MAX_CONTRADICTION_DISCOUNT", str(rules.MAX_CONTRADICTION_DISCOUNT), "cap on the discount from contradictions"],
        ["IMPEACHMENT_FACTOR", str(rules.IMPEACHMENT_FACTOR), "credibility multiplier per successful impeachment"],
        ["HOSTILE_FACTOR", str(rules.HOSTILE_FACTOR), "credibility multiplier for a witness who turned hostile (surprises only)"],
        ["Prior log-odds, criminal / civil", f"{rules.PRIOR_LOG_ODDS[next(iter(rules.PRIOR_LOG_ODDS))]} / {list(rules.PRIOR_LOG_ODDS.values())[1]}", "presumption of innocence / even odds"],
    ]
    for std, tau in rules.THRESHOLD_LOG_ODDS.items():
        rows.append([f"Bar: {std.value.replace('_', ' ')}", str(tau), "log-odds an element must reach"])
    rows += [
        ["OBJECTION_COST / IMPEACHMENT_COST / MOTION_COST", f"{rules.OBJECTION_COST} / {rules.IMPEACHMENT_COST} / {rules.MOTION_COST}", "budget a move costs"],
        ["SANCTION_OVERRULED_OBJECTION / BAD_FAITH / VIOLATION", f"{rules.SANCTION_OVERRULED_OBJECTION} / {rules.SANCTION_BAD_FAITH_EVIDENCE} / {rules.SANCTION_VIOLATION}", "sanction points"],
    ]
    return table(["Constant", "Value", "Meaning"], rows)


def matters() -> str:
    names = case_names()
    off, on = load("matters").get("cases", {}), load("matters_surprises").get("cases", {})
    if not off:
        return "_No stored measurement._"
    rows = []
    for cid in off:
        a, b = off[cid], on.get(cid, {})
        rows.append([names[cid], a["label"], pct(a["pairing_spread"]), pct(a["seed_noise"]), b.get("label", "–"), pct(b["pairing_spread"]) if b else "–", pct(b["seed_noise"]) if b else "–"])
    return table(["Case", "Verdict (plain rules)", "Lawyers move it by", "Seed coin-flip", "Verdict (surprises on)", "Lawyers move it by", "Seed coin-flip"], rows)


def matters_findings() -> str:
    names = case_names()
    meta = load("matters")
    off, on = meta.get("cases", {}), load("matters_surprises").get("cases", {})
    if not off:
        return ""
    flat = [names[c] for c, r in off.items() if r["verdict"] == "evidence"]
    moves = [names[c] for c, r in off.items() if r["verdict"] in ("lawyers", "partly_lawyers")]
    flat_on = [names[c] for c, r in on.items() if r["verdict"] == "evidence"]
    return (
        f"- Measured over {meta['n_seeds']} seeds and all nine pairings of Bold, Careful and Smart: **{len(flat)} of {len(off)} cases are decided by the evidence alone** "
        f"({', '.join(flat)}). In those, no style and no seed changes the verdict, so a strategy comparison has nothing to find.\n"
        f"- The lawyers move the verdict in {len(moves)} cases: {', '.join(moves)}.\n"
        f"- With courtroom surprises on, {len(flat_on)} of {len(on)} cases are still decided by the evidence alone ({', '.join(flat_on)})."
    )


def bootstrap() -> str:
    names = case_names()
    off, on = load("bootstrap"), load("bootstrap_surprises")
    if not off:
        return "_No stored bootstrap._"
    rows = []
    for cid, a in off["cases"].items():
        b = on.get("cases", {}).get(cid)
        rows.append([names[cid], a["baseline_label"], pct(a["stability"], 1), b["baseline_label"] if b else "–", pct(b["stability"], 1) if b else "–"])
    return table(["Case", "Label (plain)", "Stability", "Label (surprises on)", "Stability"], rows)


def bootstrap_findings() -> str:
    names = case_names()
    off, on = load("bootstrap"), load("bootstrap_surprises")
    if not off:
        return ""
    low = [f"{names[c]} ({pct(r['stability'])})" for c, r in off["cases"].items() if r["stability"] < 0.8]
    low_on = [f"{names[c]} ({pct(r['stability'])})" for c, r in on.get("cases", {}).items() if r["stability"] < 0.8]
    return (
        f"- Each game was re-solved on {off['n_resamples']} resamples of {off['n_seeds']} seeds. "
        f"Conclusions that came back less than 80% of the time with the plain rules: {', '.join(low) or 'none'}.\n"
        f"- With surprises on: {', '.join(low_on) or 'none'}."
    )


def sensitivity() -> str:
    off, on = load("sensitivity"), load("sensitivity_surprises")
    if not off:
        return "_No stored sensitivity run._"
    keys = sorted(set(off["parameter_impact"]) | set(on.get("parameter_impact", {})))
    rows = [[k.replace("_", " "), off["parameter_impact"].get(k, 0), on.get("parameter_impact", {}).get(k, 0)] for k in keys]
    return table(["Constant moved", "Label changes (plain)", "Label changes (surprises on)"], rows)


def sensitivity_findings() -> str:
    names = case_names()
    off, on = load("sensitivity"), load("sensitivity_surprises")
    if not off:
        return ""
    n = len(off["variations"])
    return (
        f"- The library was re-solved under {n} settings of the rulebook's constants (costs, sanctions, evidence weight, the prior defect rate and the standards of proof, "
        f"each moved by 25% either way, and the \"almost certain\" bar set from 80% to 95%), on {off['n_seeds']} seeds per cell.\n"
        f"- Cases whose label never changed (plain rules): {', '.join(names[c] for c in off['robust_cases']) or 'none'}. "
        f"Cases whose label changed under at least one setting: {', '.join(names[c] for c in off['fragile_cases']) or 'none'}.\n"
        f"- With surprises on, never changed: {', '.join(names[c] for c in on.get('robust_cases', [])) or 'none'}."
    )


def oracle() -> str:
    names = case_names()
    rows = []
    for _, r in sorted(load_oracle().items()):
        kept = [c for c in r["candidates"] if c["accepted"]]
        conf = sum(1 for c in kept if c.get("confirmed"))
        gains = ", ".join(f"{s}: +{r['exploitability'][s]['gain']:.2f}" for s in ("prosecution", "defense") if r["exploitability"][s]["found_better"]) or "none"
        rows.append([names[r["case_id"]], "on" if r["surprises"] else "off", r["rounds_run"], len(r["candidates"]), len(kept), f"{conf} of {len(kept)}", gains, mix(r["final_equilibrium"].get("prosecution_mix", {})), mix(r["final_equilibrium"].get("defense_mix", {}))])
    return table(["Case", "Surprises", "Rounds", "Profiles tried (best per round)", "Kept", "Confirmed on fresh seeds", "Gain per trial vs old equilibrium", "Final Accuser mix", "Final Defender mix"], rows) if rows else "_No stored search._"


def load_oracle() -> dict[str, dict]:
    d = RESULTS / "oracle"
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))} if d.is_dir() else {}


def oracle_findings() -> str:
    res = load_oracle()
    if not res:
        return ""
    names = case_names()
    lines = []
    for _, r in sorted(res.items()):
        lines.append(f"- **{names[r['case_id']]}**, surprises {'on' if r['surprises'] else 'off'}: {r['headline']}")
        for c in r["candidates"]:
            if c["accepted"]:
                lines.append(f"  - {'Accuser' if c['side'] == 'prosecution' else 'Defender'} {c['name']}: {c['plain']}. Beats the old equilibrium by {c['difference']:.2f} per trial (z {c['z']}); on fresh seeds z {c['confirm_z']}.")
    first = next(iter(res.values()))
    lines.append(f"- Search settings: {first['budget']} candidate profiles per side per round, searched on {len(first['train_seeds'])} seeds, accepted on {len(first['heldout_seeds'])} held-out seeds, confirmed on {len(first['confirm_seeds'])} more; at most {first['max_rounds']} rounds; a profile is kept only above 2 standard errors.")
    return "\n".join(lines)


def exhibition() -> str:
    ex = load("exhibition")
    if not ex:
        return ("_Not run._ The harness is built and tested against a stub, but no language-model backend answered while this project was assembled, "
                "so there is no table. With a backend available, `python -m courtroom exhibition --json results/exhibition.json` produces one, and this section fills itself in.")
    rows = [[c["case_id"], "Accuser" if c["ai_side"] == "prosecution" else "Defender", nm(c["style"]), pct(c["ai_win_rate"]), pct(c["smart_reference_win_rate"]), pct(c["fallback_rate"])] for c in ex["cells"]]
    return f"Model: {ex.get('model')} via {ex.get('provider')}. {ex['label'].capitalize()}.\n\n" + table(["Case", "AI plays", "Against", "AI wins", "Smart in its seat", "Model fell back"], rows)


def files() -> str:
    rows = []
    for p in sorted([*RESULTS.glob("*.json"), *(RESULTS / "oracle").glob("*.json")]):
        rows.append([f"`{p.relative_to(ROOT).as_posix()}`", f"`{hashlib.sha256(p.read_bytes()).hexdigest()[:12]}`", f"{p.stat().st_size // 1024 or 1} KiB"])
    pinned = json.loads((ROOT / "tests/golden/bundle_digests.json").read_text(encoding="utf-8"))
    lines = json.loads((ROOT / "tests/golden/lines_baseline.json").read_text(encoding="utf-8"))
    return table(["Result file", "sha256 (first 12)", "Size"], rows) + f"\n\n{len(pinned)} recorded trials are pinned in `tests/golden/bundle_digests.json`; {len(lines)} spoken lines in `tests/golden/lines_baseline.json`."


def demo_cases() -> str:
    off = load("matters").get("cases", {})
    if not off:
        return ""
    moves = [f"`{c}`" for c, r in off.items() if r["verdict"] == "lawyers"]
    some = [f"`{c}`" for c, r in off.items() if r["verdict"] == "partly_lawyers"]
    flat = [f"`{c}`" for c, r in off.items() if r["verdict"] == "evidence"]
    return (f"- Cases where changing the styles flips the verdict (use these to show strategy mattering): {', '.join(moves)}.\n"
            f"- Cases where it moves a little: {', '.join(some) or 'none'}.\n"
            f"- Cases where the evidence alone decides (show these as everyday trials, **not** as examples of strategy mattering): {', '.join(flat)}.")


BLOCKS = {
    "constants": constants, "matters": matters, "matters_findings": matters_findings, "bootstrap": bootstrap, "bootstrap_findings": bootstrap_findings,
    "sensitivity": sensitivity, "sensitivity_findings": sensitivity_findings, "oracle": oracle, "oracle_findings": oracle_findings,
    "exhibition": exhibition, "files": files, "demo_cases": demo_cases,
}
PATTERN = re.compile(r"(<!-- BEGIN GENERATED:(\w+) -->)\n(.*?)\n?(<!-- END GENERATED:\2 -->)", re.S)


def render(text: str) -> str:
    return PATTERN.sub(lambda m: m.group(1) + "\n" + BLOCKS[m.group(2)]() + "\n" + m.group(4), text)


def main() -> int:
    check = "--check" in sys.argv
    stale = []
    for name in DOCS:
        path = ROOT / name
        if not path.exists():
            continue
        old = path.read_text(encoding="utf-8")
        new = render(old)
        if new != old:
            stale.append(name)
            if not check:
                path.write_text(new, encoding="utf-8")
    if check and stale:
        print("out of date:", ", ".join(stale), "- run python scripts/render_docs.py")
        return 1
    print("docs up to date" if check else f"rendered {', '.join(DOCS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
