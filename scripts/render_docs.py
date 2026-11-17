"""Fill the generated regions of the docs from the certified files in results/. No number in those docs is typed by hand.

    python scripts/render_docs.py            # rewrite REPORT.md and PROVENANCE.md in place
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

DOCS = ("REPORT.md", "PROVENANCE.md", "DEVIATIONS.md")
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


def docket_tab(case_id: str) -> str:
    """Which docket tab a library case sits in (the same rule as category() in app.js)."""
    from courtroom.cases import get_case

    tags = get_case(case_id).tags
    return "Everyday" if "everyday" in tags else "Tricky tests" if "edge-case" in tags else "Serious"


def demo_cases() -> str:
    off = load("matters").get("cases", {})
    if not off:
        return ""

    def show(ids: list[str]) -> str:
        return ", ".join(f"`{c}` ({docket_tab(c)} tab)" for c in ids)

    moves = [c for c, r in off.items() if r["verdict"] == "lawyers"]
    some = [c for c, r in off.items() if r["verdict"] == "partly_lawyers"]
    flat = [c for c, r in off.items() if r["verdict"] == "evidence"]
    return (f"- Cases whose card is tagged \"Decided by the lawyers\" (use these to show strategy mattering): {show(moves)}.\n"
            f"- Cases tagged \"Partly the lawyers\": {show(some) or 'none'}.\n"
            f"- Cases where the evidence alone decides (tagged \"Decided by the evidence\"; show these as plain trials, **not** as examples of strategy mattering): {show(flat)}.")


# --------------------------------------------------------------------------- the lecture concepts (classic games, Pareto, minimax, alpha-beta)

CLASSIC_WORDS = {
    "prisoners-dilemma": "prisoner's dilemma", "stag-hunt": "stag hunt", "battle-of-the-sexes": "battle of the sexes", "chicken": "chicken",
    "matching-pennies": "matching pennies", "dominance-solvable": "dominance-solvable", "other": "none of the classic games",
}


def _classic_line(d: dict, label: str) -> str:
    names = case_names()
    per = {cid: c["label_counts"].get(label, 0) for cid, c in d.get("cases", {}).items()}
    total = sum(per.values())
    where = [f"{names[c]} ({n})" for c, n in per.items() if n]
    return f"{total} ({'; '.join(where)})" if total else "0"


def classic_findings() -> str:
    out = []
    for name, tag in (("classic", "Plain rules"), ("classic_surprises", "Courtroom surprises on")):
        d = load(name)
        if not d:
            continue
        corners = sum(sum(c["label_counts"].values()) for c in d["cases"].values())
        out.append(f"- **{tag}.** {len(d['cases'])} cases, {corners} two-by-two corners (every pair of the four styles for each side), measured over {d['n_seeds']} seeds, "
                   f"labels re-tested on {d['n_resamples']} resamples of the seeds.")
        for k in ("prisoners-dilemma", "stag-hunt", "battle-of-the-sexes", "chicken", "matching-pennies", "dominance-solvable", "other"):
            out.append(f"  - {CLASSIC_WORDS[k].capitalize()}: {_classic_line(d, k)}.")
        stab = [(sg["label"], sg["stability"]) for c in d["cases"].values() for sg in c["subgames"]]
        mp = [v for k, v in stab if k == "matching-pennies"]
        if mp:
            out.append(f"  - The matching-pennies corners kept their label on {pct(sum(mp) / len(mp))} of resamples on average.")
    for name, tag in (("classic_search", "plain rules"), ("classic_search_surprises", "surprises on")):
        d = load(name)
        if not d:
            continue
        n = sum(d["label_counts"].values())
        raw = d["label_counts_no_tolerance"]
        cand = d["candidates"]
        out.append(f"- **Search over generated cases ({tag}).** {d['tried']} generated cases ({d['note'].split(';')[0].replace('Found by search: ', '')}), {n} corners. "
                   f"Read as exact numbers, {cand} corners looked like a prisoner's dilemma, stag hunt or battle of the sexes "
                   f"({raw['prisoners-dilemma']} dilemma, {raw['stag-hunt']} stag hunt, {raw['battle-of-the-sexes']} battle of the sexes); "
                   f"**{len(d['found'])} kept** their name under the full tolerance on fresh seeds.")
    return "\n".join(out)


def efficiency_findings() -> str:
    names = case_names()
    out = []
    for name, tag in (("efficiency", "Plain rules"), ("efficiency_surprises", "Courtroom surprises on")):
        d = load(name)
        if not d:
            continue
        cases = d["cases"]
        dil = [names[c] for c, r in cases.items() if r["efficiency"]["social_dilemma"]]
        weak = [names[c] for c, r in cases.items() if not r["efficiency"]["social_dilemma"] and not r["efficiency"]["all_equilibria_efficient"]]
        eff = [names[c] for c, r in cases.items() if r["efficiency"]["all_equilibria_efficient"]]
        out.append(f"- **{tag}** ({d['n_seeds']} seeds): an equilibrium dominated for **both** sides by some cell (the prisoner's-dilemma pattern) in {len(dil)} of {len(cases)} cases"
                   f"{' (' + ', '.join(dil) + ')' if dil else ''}; only weakly dominated (a cell helps one side and hurts nobody) in {len(weak)}"
                   f"{' (' + ', '.join(weak) + ')' if weak else ''}; every equilibrium Pareto-efficient in {len(eff)}{' (' + ', '.join(eff) + ')' if eff else ''}.")
    return "\n".join(out)


def security_findings() -> str:
    names = case_names()
    out = []
    for name, tag in (("efficiency", "Plain rules"), ("efficiency_surprises", "Courtroom surprises on")):
        d = load(name)
        if not d:
            continue
        cases = d["cases"]
        ok = sum(1 for r in cases.values() if r["constant_sum"]["theorem_holds"])
        vals = {names[c]: r["constant_sum"]["maximin"] for c, r in cases.items()}
        saddle = sum(1 for r in cases.values() if r["constant_sum"]["saddle_point"])
        gaps_r = [q["security_gap_row"] for r in cases.values() for q in r["efficiency"]["equilibria"]]
        gaps_c = [q["security_gap_col"] for r in cases.values() for q in r["efficiency"]["equilibria"]]
        out.append(f"- **{tag}.** In the win-probability game (constant-sum) maximin equals minimax equals the Nash value in {ok} of {len(cases)} cases, as the minimax theorem says; "
                   f"a pure saddle point (nobody needs to randomise) in {saddle}. The Accuser's guaranteed win rate runs from {pct(min(vals.values()))} ({min(vals, key=vals.get)}) to {pct(max(vals.values()))} ({max(vals, key=vals.get)}). "
                   f"In the full general-sum game, an equilibrium pays the Accuser between {min(gaps_r):.2f} and {max(gaps_r):.2f} above its security value and the Defender between {min(gaps_c):.2f} and {max(gaps_c):.2f} above its own.")
    return "\n".join(out)


def tree_table() -> str:
    d = load("tree_search")
    if not d:
        return "_No stored search._"
    rows = []
    for cid, r in d["cases"].items():
        ran = r.get("ran_all_three", True)
        limit = r["node_limit"]

        def cell(n: int | None, ran: bool = True, limit: int = limit) -> str:
            return "not run" if not ran else (f"more than {limit:,}" if n is None else f"{n:,}")

        rows.append([cid, f"{r['evidence'][0]}, {r['evidence'][1]}", "not solved" if r["value"] is None else f"{r['value']:g}", cell(r["minimax_nodes"], ran), cell(r["alphabeta_nodes"], ran), cell(r["alphabeta_ordered_nodes"]),
                     "–" if r["values_agree"] is None else ("yes" if r["values_agree"] else "NO")])
    return table(["Case", "Exhibits (Accuser, Defender)", "Best-play value", "Plain minimax nodes", "Alpha-beta nodes", "Alpha-beta with ordering", "Same value?"], rows)


def tree_findings() -> str:
    d = load("tree_search")
    if not d:
        return ""
    rs = list(d["cases"].values())
    solved = [r for r in rs if r["value"] is not None]
    full = [r for r in rs if r["minimax_nodes"] and r["alphabeta_nodes"] and r["alphabeta_ordered_nodes"]]
    agree = all(r["values_agree"] for r in solved)
    shares = sorted(r["pruned_share"] for r in full)
    big = max(full, key=lambda r: r["minimax_nodes"])
    ord_better = sum(1 for r in full if r["alphabeta_ordered_nodes"] < r["alphabeta_nodes"])
    ord_worse = [r["case_id"] for r in full if r["alphabeta_ordered_nodes"] > r["alphabeta_nodes"]]
    unsolved = [r["case_id"] for r in rs if r["value"] is None]
    only_ordered = [r["case_id"] for r in rs if r.get("ran_all_three") is False and r["value"] is not None]
    wins = sum(1 for r in solved if r["value"] > 0)
    out = [
        f"- {len(solved)} of {len(rs)} cases were solved exactly; {'plain minimax, alpha-beta and alpha-beta with move ordering returned **the same value in every one**' if agree else '**the methods disagreed somewhere: see the table**'}.",
        f"- On the {len(full)} cases where plain minimax also finished, alpha-beta with move ordering visited between {pct(1 - shares[-1])} and {pct(1 - shares[0])} of minimax's nodes; the most expensive was {big['case_id']}: "
        f"{big['minimax_nodes']:,} nodes for plain minimax, {big['alphabeta_nodes']:,} for alpha-beta, {big['alphabeta_ordered_nodes']:,} with ordering.",
        f"- Move ordering helped in {ord_better} of the {len(full)} cases" + (f" and made no difference or cost slightly more in {len(ord_worse)} ({', '.join(ord_worse)})" if ord_worse else "") + ".",
        f"- Larger cases ({', '.join(only_ordered) or 'none'}) were solved with the ordered search alone, because plain minimax would not finish; {', '.join(unsolved) or 'none'} could not be solved within the node limit.",
        f"- With both sides seeing everything, the Accuser can win in {wins} of the {len(solved)} solved cases; in the others the Defender wins whatever the Accuser does.",
    ]
    return "\n".join(out)


def lookahead_findings() -> str:
    names = case_names()
    out = []
    for name, tag in (("lookahead", "Plain rules"), ("lookahead_surprises", "Courtroom surprises on")):
        d = load(name)
        if not d:
            continue
        beats, worse, same = [], [], []
        for cid, r in d["cases"].items():
            seats = [s for s in ("prosecution", "defense") if r[s]["beats"]]
            bad = [s for s in ("prosecution", "defense") if r[s]["worse"]]
            lab = {"prosecution": "as Accuser", "defense": "as Defender"}
            if seats:
                beats.append(f"{names[cid]} ({' and '.join(lab[x] for x in seats)})")
            if bad:
                worse.append(f"{names[cid]} ({' and '.join(lab[x] for x in bad)})")
            if not seats and not bad:
                same.append(names[cid])
        out.append(f"- **{tag}** ({d['n_seeds']} seeds, paired by seed, against the four-style equilibrium): lookahead beat it by more than two standard errors in {len(beats)} of {len(d['cases'])} cases"
                   f"{': ' + '; '.join(beats) if beats else ''}; did clearly worse in {len(worse)}{': ' + '; '.join(worse) if worse else ''}; was not distinguishable in {len(same)}{': ' + ', '.join(same) if same else ''}.")
    return "\n".join(out)


def lectures() -> str:
    """The lecture concepts, where each is computed and what our data says (every figure read from results/)."""
    c = load("classic")
    cs = load("classic_surprises")
    search = load("classic_search")
    ssearch = load("classic_search_surprises")

    def n(d: dict, label: str) -> int:
        return sum(x["label_counts"].get(label, 0) for x in d.get("cases", {}).values())

    def found(label: str) -> str:
        a, b = n(c, label), n(cs, label)
        if a == 0 and b == 0:
            sf = len([f for f in search.get("found", []) if f["label"] == label]) + len([f for f in ssearch.get("found", []) if f["label"] == label])
            return f"**Not found.** 0 of {sum(sum(x['label_counts'].values()) for x in c['cases'].values())} corners in the library, and {sf} kept after searching {search.get('tried', 0)} generated cases."
        return f"{a} corners (plain), {b} (surprises on)."

    eff, effs = load("efficiency"), load("efficiency_surprises")
    dil = sum(1 for r in eff.get("cases", {}).values() if r["efficiency"]["social_dilemma"])
    dils = sum(1 for r in effs.get("cases", {}).values() if r["efficiency"]["social_dilemma"])
    ok = sum(1 for r in eff.get("cases", {}).values() if r["constant_sum"]["theorem_holds"]) + sum(1 for r in effs.get("cases", {}).values() if r["constant_sum"]["theorem_holds"])
    tot = len(eff.get("cases", {})) + len(effs.get("cases", {}))
    tr = load("tree_search")
    solved = [r for r in tr.get("cases", {}).values() if r["value"] is not None]
    full = [r for r in solved if r["minimax_nodes"] and r["alphabeta_ordered_nodes"]]
    la = load("lookahead")
    las = load("lookahead_surprises")

    def lab(d: dict) -> int:
        return sum(1 for r in d.get("cases", {}).values() if r["prosecution"]["beats"] or r["defense"]["beats"])

    rows = [
        ["Prisoner's dilemma", "`gametheory/classic.py`; `python -m courtroom classic`; `results/classic*.json`", found("prisoners-dilemma"), "Only pairs of styles (2×2 corners of the 4×4 table). A gap under two standard errors is a tie, and a game needing a strict order where there is a tie is called none of the classic games."],
        ["Stag hunt", "same", found("stag-hunt"), "Risk is read from each play's worst case (a security-level notion), not from risk dominance."],
        ["Battle of the sexes (Bach or Stravinsky)", "same", found("battle-of-the-sexes"), "Needs two pure equilibria that the sides rank differently."],
        ["Chicken", "same", found("chicken"), "The same two-equilibria shape with a full strict order of four outcomes."],
        ["Matching pennies", "same", f"{n(c, 'matching-pennies')} corners (plain), {n(cs, 'matching-pennies')} (surprises on)", "Named when no pure equilibrium survives the tolerance; the sides need not be zero-sum."],
        ["Pareto optimality", "`gametheory/efficiency.py`; `python -m courtroom efficiency`; `results/efficiency*.json`", f"Some equilibrium dominated for both sides in {dil} of {len(eff.get('cases', {}))} cases (plain), {dils} (surprises on).", "Compared on mean payoffs over pure pairs of styles; a mixed equilibrium is compared by its expected payoffs, and mixing across cells together is not considered."],
        ["Minimax and the minimax theorem", "`gametheory/efficiency.py` (exact maximin by vertex enumeration); `tests/test_efficiency.py`", f"Maximin = minimax = Nash value in {ok} of {tot} win-probability games.", "Holds only for the constant-sum win-probability game. The real game is general-sum, so there the security value is only a floor."],
        ["Minimax on the trial tree", "`gametheory/search.py`; `python -m courtroom tree`; `results/tree_search.json`", f"{len(solved)} of {len(tr.get('cases', {}))} cases solved exactly.", "An open-file relaxation: both sides see all exhibits and flaws, no perception noise, and a zero-sum payoff (Accuser utility minus Defender utility). The real game has hidden information and is not zero-sum."],
        ["Alpha-beta pruning", "same", f"Same value as plain minimax in all {len(full)} cases where both finished, with move ordering cutting the nodes visited as shown in the table.", "Pruning is exact; the saving depends on the case and on the ordering heuristic."],
        ["Thinking ahead (depth-limited alpha-beta)", "`agents/lookahead.py`; `python -m courtroom lookahead`; `results/lookahead*.json`", f"Beat the four-style equilibrium in {lab(la)} of {len(la.get('cases', {}))} cases (plain) and {lab(las)} (surprises on).", "Exhibition, not certified. It uses only its own view and the public oracle, assumes the worst reply, and scores positions with a heuristic."],
    ]
    return table(["Lecture concept", "Where it is computed", "What our data says", "Limits"], rows)


def deviation_seeds() -> str:
    rows = []
    for name, what in (("bootstrap", "Bootstrap of the equilibrium label"), ("classic", "Classic-game labels"), ("efficiency", "Pareto and security"), ("sensitivity", "Rulebook sensitivity"), ("matters", "Does strategy matter"), ("lookahead", "Lookahead comparison")):
        d = load(name)
        if d:
            rows.append([what, f"`results/{name}.json`", str(d.get("n_seeds", d.get("seeds", "–")))])
    return table(["Analysis", "File", "Seeds per cell"], rows)


BLOCKS = {
    "constants": constants, "matters": matters, "matters_findings": matters_findings, "bootstrap": bootstrap, "bootstrap_findings": bootstrap_findings,
    "sensitivity": sensitivity, "sensitivity_findings": sensitivity_findings, "oracle": oracle, "oracle_findings": oracle_findings,
    "exhibition": exhibition, "files": files, "demo_cases": demo_cases,
    "classic_findings": classic_findings, "efficiency_findings": efficiency_findings, "security_findings": security_findings, "tree_table": tree_table,
    "tree_findings": tree_findings, "lookahead_findings": lookahead_findings, "lectures": lectures, "deviation_seeds": deviation_seeds,
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
