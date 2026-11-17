"""Every number the slides and the PDF report quote, read from results/ and git by code (never typed by hand).

    python scripts/submission_facts.py            # print the facts as JSON
    python scripts/submission_facts.py --write    # write report/generated/facts.json

The slides (presentation/build_slides.py) and the report (report/build_report.py) import ``collect()``. A test compares the committed
facts.json with a fresh run, so a stale file fails the suite. Nothing here reads the network.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import render_docs as rd  # noqa: E402  (the same loaders the generated docs use)

OUT = ROOT / "report" / "generated" / "facts.json"
PACKAGES = ("contracts", "cases", "procedure", "judge", "agents", "gametheory", "engine", "api", "cli", "viz")


FIRST_CERTIFIED_COMMIT = "6c5e33d"  # the last commit whose bootstrap.json was run at 100 seeds (before the 200-seed re-run)


def bootstrap_at_100_seeds() -> dict:
    """What the first certified bootstrap showed (100 seeds), kept in git: read from that commit, not typed."""
    out = {}
    for tag, name in (("plain", "bootstrap"), ("surprises", "bootstrap_surprises")):
        d = json.loads(subprocess.run(["git", "show", f"{FIRST_CERTIFIED_COMMIT}:results/{name}.json"], cwd=ROOT, capture_output=True, text=True, check=True).stdout)
        low = {c: r["stability"] for c, r in d["cases"].items() if r["stability"] < 0.8}
        out[tag] = {"n_seeds": d["n_seeds"], "below_80": dict(sorted(low.items(), key=lambda kv: kv[1]))}
    return out


def code_review() -> dict:
    """Counts from docs/CODE_REVIEW.md: findings by severity (the P0 to P3 headings) and by status (the first word of the status cell)."""
    sev, rows = "", []
    for ln in (ROOT / "docs" / "CODE_REVIEW.md").read_text(encoding="utf-8").splitlines():
        h = re.match(r"###\s+(P\d)", ln)
        if h:
            sev = h.group(1)
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if ln.startswith("|") and len(cells) >= 3 and re.fullmatch(r"[A-Z]+\d+", cells[0]) and sev:
            rows.append((cells[0], sev, re.split(r"[:\s]", cells[-1], maxsplit=1)[0].lower()))
    by_sev: dict[str, Counter] = defaultdict(Counter)
    for _, sv, st in rows:
        by_sev[sv][st] += 1
    return {"total": len(rows), "by_severity": {k: dict(v) for k, v in sorted(by_sev.items())}}


def _case_label(r: dict) -> str:
    return r["verdict"]


def results_facts() -> dict:
    names = rd.case_names()
    f: dict = {"n_cases": len(names)}

    for tag, name in (("plain", "matters"), ("surprises", "matters_surprises")):
        d = rd.load(name)
        cases = d["cases"]
        f.setdefault("matters", {})[tag] = {
            "n_seeds": d["n_seeds"],
            "n_cases": len(cases),
            "evidence": sorted(c for c, r in cases.items() if r["verdict"] == "evidence"),
            "lawyers": sorted(c for c, r in cases.items() if r["verdict"] == "lawyers"),
            "partly": sorted(c for c, r in cases.items() if r["verdict"] == "partly_lawyers"),
        }
        m = f["matters"][tag]
        m["n_evidence"], m["n_move"] = len(m["evidence"]), len(m["lawyers"]) + len(m["partly"])

    for tag, name in (("plain", "bootstrap"), ("surprises", "bootstrap_surprises")):
        d = rd.load(name)
        st = {c: r["stability"] for c, r in d["cases"].items()}
        low = sorted(c for c, v in st.items() if v < 0.8)
        worst = min(st, key=st.get)
        f.setdefault("bootstrap", {})[tag] = {"n_seeds": d["n_seeds"], "n_resamples": d["n_resamples"], "worst_case": worst, "worst": st[worst], "below_80": low, "n_below_80": len(low), "n_cases": len(st)}

    s = rd.load("sensitivity")
    f["sensitivity"] = {"n_variations": len(s["variations"]), "n_seeds": s["n_seeds"], "robust": sorted(s["robust_cases"]), "fragile": sorted(s["fragile_cases"])}

    res = rd.load_oracle()
    rows = []
    for r in res.values():
        beat = {side: round(r["exploitability"][side]["gain"], 2) for side in ("prosecution", "defense") if r["exploitability"][side]["found_better"]}
        kept = [c for c in r["candidates"] if c["accepted"]]
        rows.append({"case": r["case_id"], "surprises": r["surprises"], "beaten": bool(beat), "gains": beat, "kept": len(kept), "confirmed": sum(1 for c in kept if c.get("confirmed"))})
    best = max((g, r) for r in rows for g in r["gains"].values())[1] if any(r["gains"] for r in rows) else None
    f["oracle"] = {"searches": rows, "n_searches": len(rows), "n_beaten": sum(1 for r in rows if r["beaten"]), "best": None if best is None else {"case": best["case"], "surprises": best["surprises"], "gains": best["gains"]}}

    c, cs, sr, ssr = rd.load("classic"), rd.load("classic_surprises"), rd.load("classic_search"), rd.load("classic_search_surprises")
    corners = sum(sum(x["label_counts"].values()) for x in c["cases"].values())
    count = lambda d, label: sum(x["label_counts"].get(label, 0) for x in d["cases"].values())  # noqa: E731
    f["classic"] = {
        "n_seeds": c["n_seeds"], "n_resamples": c["n_resamples"], "corners": corners,
        "found": {k: count(c, k) + count(cs, k) for k in ("prisoners-dilemma", "stag-hunt", "battle-of-the-sexes", "chicken")},
        "matching_pennies": count(c, "matching-pennies"), "matching_pennies_surprises": count(cs, "matching-pennies"),
        "search_tried": sr["tried"], "search_kept": len(sr["found"]) + len(ssr["found"]),
        "search_looked_like": {k: sr["label_counts_no_tolerance"][k] for k in ("prisoners-dilemma", "stag-hunt", "battle-of-the-sexes")},
    }

    e, es = rd.load("efficiency"), rd.load("efficiency_surprises")
    f["efficiency"] = {
        "n_seeds": e["n_seeds"],
        "dilemma_cases": sorted(k for k, r in e["cases"].items() if r["efficiency"]["social_dilemma"]),
        "theorem_holds": sum(1 for d in (e, es) for r in d["cases"].values() if r["constant_sum"]["theorem_holds"]),
        "theorem_total": len(e["cases"]) + len(es["cases"]),
    }

    t = rd.load("tree_search")
    solved = [r for r in t["cases"].values() if r["value"] is not None]
    f["tree"] = {"solved": len(solved), "total": len(t["cases"]), "all_agree": all(r["values_agree"] for r in solved), "unsolved": sorted(k for k, r in t["cases"].items() if r["value"] is None)}

    la, las = rd.load("lookahead"), rd.load("lookahead_surprises")
    wins = lambda d: sorted(k for k, r in d["cases"].items() if r["prosecution"]["beats"] or r["defense"]["beats"])  # noqa: E731
    f["lookahead"] = {"n_seeds": la["n_seeds"], "beats_plain": wins(la), "beats_surprises": wins(las), "n_cases": len(la["cases"])}
    f["seeds_per_cell"] = {n: rd.load(n).get("n_seeds") for n in ("bootstrap", "classic", "efficiency", "sensitivity", "matters", "lookahead")}
    f["sensitivity"]["parameter_impact"] = dict(s["parameter_impact"])
    f["bootstrap_at_100_seeds"] = bootstrap_at_100_seeds()
    f["code_review"] = code_review()
    f["case_names"] = names
    return f


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


MILESTONES = (  # (what, a path whose first appearance on any local branch dates it)
    ("Core engine in one commit: contracts, cases, procedure, judge, agents, Nash solver, engine, API, CLI, web UI", "courtroom/engine/trial.py"),
    ("Bootstrap stability of the equilibrium label", "courtroom/gametheory/bootstrap.py"),
    ("First certified result file", "results/bootstrap.json"),
    ("Strategy lab page", "courtroom/viz/web/lab.html"),
    ("Pinned digests of the recorded trials", "tests/golden/bundle_digests.json"),
    ("Does-strategy-matter measurement", "results/matters.json"),
)
GATES = (  # (gate, planned date, what the proposal says, a path whose first appearance in git is the closest evidence of it)
    ("G1", "2026-10-16", "one case runs end to end", "courtroom/engine/trial.py"),
    ("G2", "2026-10-23", "integrated demo on all three cases", "courtroom/viz/web/data/bundle.js"),
    ("G3", "2026-11-06", "parameters frozen, results reproduced", "results/bootstrap.json"),
)


def _gate(g: str, planned: str, what: str, path: str) -> dict:
    from datetime import date

    first = _first_added(path)
    days = (date.fromisoformat(first) - date.fromisoformat(planned)).days
    return {"gate": g, "planned": planned, "what": what, "evidence_path": path, "first_in_git": first, "days_after_plan": days, "status": "before the gate" if days <= 0 else f"{days} days after the gate"}


def _first_added(path: str) -> str:
    out = _git("log", "--branches", "--diff-filter=A", "--format=%ad", "--date=short", "--", path).split()
    return out[-1] if out else ""


def git_facts() -> dict:
    """Commit counts and dates, from every local branch (no emails, no remotes)."""
    raw = _git("log", "--branches", "--no-merges", "--format=%H|%an|%ad|%s", "--date=short").strip().splitlines()
    commits = [x.split("|", 3) for x in raw]
    by_author = Counter(a for _, a, _, _ in commits)
    dates: dict[str, list[str]] = defaultdict(list)
    for _, a, d, _ in commits:
        dates[a].append(d)
    pkgs: dict[str, Counter] = defaultdict(Counter)
    for h, a, _, _ in commits:
        for path in _git("show", "--name-only", "--format=", h).split():
            parts = path.split("/")
            if parts[0] == "courtroom" and len(parts) > 2:
                key = "viz" if parts[1] == "viz" else parts[1]
            elif parts[0] == "courtroom":
                key = "cli" if parts[1] == "cli.py" else "courtroom (top level)"
            else:
                key = parts[0]
            pkgs[a][key] += 1
    all_dates = sorted(d for _, _, d, _ in commits)
    on_main = _git("log", "final-integration", "--no-merges", "--format=%ad", "--date=short").split()
    return {
        "non_merge_commits": len(commits),
        "by_author": dict(by_author.most_common()),
        "first_last": {a: [min(v), max(v)] for a, v in dates.items()},
        "files_touched_by_author": {a: dict(c.most_common()) for a, c in pkgs.items()},
        "first_commit": all_dates[0], "last_commit": all_dates[-1],
        "commits_by_date_final_integration": dict(sorted(Counter(on_main).items())),
        "distinct_commit_days": len(set(all_dates)),
        "milestones": [{"what": w, "path": p, "date": _first_added(p)} for w, p in MILESTONES],
        "gates": [_gate(g, d, w, p) for g, d, w, p in GATES],
        "merge_commits_by_github": int(_git("log", "--branches", "--merges", "--format=%an").split("\n").count("PramitKH26")),
    }


E1_COMMIT = "6c5e33d"  # the commit that fixed finding E1 (impeachment with an unadmitted exhibit)


def e1_effect() -> dict:
    """What fixing E1 did to the recorded trials, read from git: pinned digests and verdicts before and after that commit."""
    def bundle(rev: str) -> dict:
        raw = _git("show", f"{rev}:courtroom/viz/web/data/bundle.js")
        return json.loads(re.sub(r"^window\.COURTROOM_BUNDLE = |;\s*$", "", raw))["trials"]

    old, new = bundle(E1_COMMIT + "^"), bundle(E1_COMMIT)
    changed = [k for k in old if old[k]["digest"] != new[k]["digest"]]
    flipped = [k for k in changed if old[k]["verdict"]["outcome"] != new[k]["verdict"]["outcome"]]
    return {"trials": len(old), "digests_changed": len(changed), "verdicts_flipped": len(flipped), "flipped": flipped}


def collect() -> dict:
    g = git_facts()
    g["claude_coauthored"] = claude_coauthored()
    g["e1"] = e1_effect()
    return {"results": results_facts(), "git": g}


def claude_coauthored() -> dict:
    """Commits per author whose message carries a Co-Authored-By: Claude trailer (absence of a trailer proves nothing)."""
    out: dict[str, list[int]] = {}
    for ln in _git("log", "--branches", "--no-merges", "--format=%an|%(trailers:key=Co-Authored-By,valueonly,separator=;)").strip().splitlines():
        a, _, tr = ln.partition("|")
        row = out.setdefault(a, [0, 0])
        row[0] += 1
        row[1] += "Claude" in tr
    return {a: {"commits": r[0], "with_claude_trailer": r[1]} for a, r in out.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true", help="fail if the committed results part of facts.json is stale")
    a = ap.parse_args()
    facts = collect()
    text = json.dumps(facts, indent=1, sort_keys=True) + "\n"
    if a.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text, encoding="utf-8")
        print("wrote", OUT.relative_to(ROOT))
    elif a.check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
        if old.get("results") != json.loads(json.dumps(facts["results"])):
            print("report/generated/facts.json is stale: run python scripts/submission_facts.py --write")
            return 1
        print("facts up to date")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
