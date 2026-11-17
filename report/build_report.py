"""Build report/Saul_Goodman_T22_Report.pdf from results/, git and the evaluation measurements.

    python report/build_report.py            # facts, figures, generated tables and macros, then tectonic
    python report/build_report.py --no-pdf   # only the generated files
    python report/build_report.py --check    # fail if the committed generated files are stale (used by a test)

Nothing typed by hand reaches the PDF as a result: every number is a LaTeX macro or a table written here from results/*.json,
report/generated/eval_plan.json (scripts/eval_plan.py) and git (scripts/submission_facts.py). Needs tectonic (a self-contained LaTeX engine).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "report"
GEN = REPORT / "generated"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import render_docs as rd  # noqa: E402
import submission_facts as sf  # noqa: E402

ESC = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "\\": r"\textbackslash{}"}


def esc(s: str) -> str:
    return "".join(ESC.get(ch, ch) for ch in s)


def inline(s: str) -> str:
    """Markdown inline (code, bold) to LaTeX, escaping the rest."""
    out, i = [], 0
    for m in re.finditer(r"`([^`]+)`|\*\*([^*]+)\*\*", s):
        out.append(esc(s[i:m.start()]))
        out.append(r"\texttt{" + esc(m.group(1)) + "}" if m.group(1) else r"\textbf{" + esc(m.group(2)) + "}")
        i = m.end()
    out.append(esc(s[i:]))
    return "".join(out)


def md_rows(md: str) -> tuple[list[str], list[list[str]]]:
    lines = [ln for ln in md.strip().splitlines() if ln.startswith("|")]
    cells = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines]
    return cells[0], cells[2:]


def tex_table(head: list[str], rows: list[list[str]], spec: str, size: str = r"\small", raw: bool = False) -> str:
    spec = re.sub(r"p\{([^}]*)\}", r">{\\raggedright\\arraybackslash}p{\1}", spec)
    fmt = (lambda x: x) if raw else inline
    body = "\n".join(" & ".join(fmt(c) for c in r) + r" \\" for r in rows)
    return f"{{{size}\n\\begin{{tabularx}}{{\\textwidth}}{{{spec}}}\n\\toprule\n" + " & ".join(r"\textbf{" + inline(h) + "}" for h in head) + " \\\\\n\\midrule\n" + body + "\n\\bottomrule\n\\end{tabularx}}\n"


def pct(x: float, d: int = 0) -> str:
    return f"{100 * x:.{d}f}\\%"


def macros(facts: dict, ev: dict) -> dict[str, str]:
    R, G = facts["results"], facts["git"]
    names = R["case_names"]
    m, b, bs = R["matters"]["plain"], R["bootstrap"]["plain"], R["bootstrap"]["surprises"]
    o, c, e, t, la, s = R["oracle"], R["classic"], R["efficiency"], R["tree"], R["lookahead"], R["sensitivity"]
    worst = min(({**R["bootstrap"][k], "mode": "plain rules" if k == "plain" else "surprises on"} for k in ("plain", "surprises")), key=lambda x: x["worst"])
    best_gain = max(o["best"]["gains"].values())
    out = {
        "NCases": R["n_cases"], "NMove": m["n_move"], "NEvidence": m["n_evidence"], "MSeeds": m["n_seeds"],
        "NLawyers": len(m["lawyers"]), "NPartly": len(m["partly"]),
        "BootSeeds": b["n_seeds"], "BootResamples": b["n_resamples"], "BootWorstPlain": pct(b["worst"], 1), "BootWorstPlainCase": names[b["worst_case"]],
        "BootBelowPlain": b["n_below_80"], "BootBelowSurprises": bs["n_below_80"], "BootWorstSurprises": pct(bs["worst"], 1), "BootWorstSurprisesCase": names[bs["worst_case"]],
        "BootWorstAny": pct(worst["worst"], 1), "BootWorstAnyCase": names[worst["worst_case"]], "BootWorstAnyMode": worst["mode"],
        "NSearches": o["n_searches"], "NBeaten": o["n_beaten"], "BestGain": f"{best_gain:.2f}", "BestCase": names[o["best"]["case"]],
        "ClassicCorners": c["corners"], "ClassicFoundTotal": sum(c["found"].values()), "MatchingPennies": c["matching_pennies"], "SearchTried": c["search_tried"],
        "SearchLookedDilemma": c["search_looked_like"]["prisoners-dilemma"], "SearchLookedStag": c["search_looked_like"]["stag-hunt"], "SearchKept": c["search_kept"],
        "ClassicSeeds": c["n_seeds"], "EffSeeds": e["n_seeds"], "TheoremHolds": e["theorem_holds"], "TheoremTotal": e["theorem_total"],
        "TreeSolved": t["solved"], "TreeTotal": t["total"], "LookSeeds": la["n_seeds"], "LookBeats": len(la["beats_plain"]), "LookBeatsCase": names[la["beats_plain"][0]] if la["beats_plain"] else "none",
        "SensVariations": s["n_variations"], "SensSeeds": s["n_seeds"], "SensRobust": len(s["robust"]), "SensFragile": len(s["fragile"]),
        "NCommits": G["non_merge_commits"], "NAuthors": len(G["by_author"]), "NCommitDays": G["distinct_commit_days"], "FirstCommit": G["first_commit"], "LastCommit": G["last_commit"],
        "TrialMedianMs": ev["timing"]["median_ms"], "TrialMaxMs": ev["timing"]["max_ms"], "TimedTrials": ev["timing"]["trials"],
        "ReplaySame": ev["replays"]["same_digest"], "ReplayTotal": ev["replays"]["recorded_trials"], "ReplayChain": ev["replays"]["chain_valid"],
        "StressTrials": ev["stress"]["trials"], "StressCrashes": ev["stress"]["crashes"], "StressInvariant": ev["stress"]["invariant_failures"], "StressReplays": ev["stress"]["deterministic_replays"],
        "StressMeanMs": ev["stress"]["mean_ms"],
    }
    C = G.get("course", {})
    if C:
        cshort = {"Aditya": "Aditya", "Lakshya Sachdeva": "Lakshya", "Mofasser Arafat": "Mofasser", "rohanp-965": "Rohan", "RakshitGoel007": "Rakshit", "Divvij0202": "Divvij", "PramitKH26": "Pramit", "binarycoder3012": "Binary"}
        out.update({"CourseCommits": C["commits"], "CourseAuthors": len(C["by_author"]), "CourseFirst": C["first"], "CourseLast": C["last"], "CourseDays": C["days_with_commits"],
                    "CourseMinPerDay": C["min_per_day"], "CourseMaxPerDay": C["max_per_day"], "CourseSame": C["core_files_identical_to_lump"], "CourseDiffer": C["core_files_different_from_lump"],
                    "CourseCore": C["core_files_in_lump"], "LumpDate": C["lump_commit_date"]})
        for a, n in C["by_author"].items():
            out[f"Course{cshort[a]}"] = n
        for pk, d in C["package_first_in_official_history"].items():
            out["CourseFirst" + pk.capitalize()] = d
    do = next(x for x in ev["edge_fixtures"] if x["case"] == "edge-defense-only")
    out["DefenseOnlySpent"] = f"{do['budget_spent']['defense']:g}"
    e1 = G["e1"]
    out.update({"EOneDigests": e1["digests_changed"], "EOneTrials": e1["trials"], "EOneFlipped": e1["verdicts_flipped"]})
    cc = G["claude_coauthored"]
    short = {"Pramit Khandelwal": "Pramit", "binarycoder3012": "Binarycoder", "savage2006": "Savage", "Divvij0202": "Divvij"}
    for a, row in G["by_author"].items():
        k = short.get(a, "".join(ch for ch in a if ch.isalpha()))
        out[f"Commits{k}"] = row
        out[f"First{k}"], out[f"Last{k}"] = G["first_last"][a]
        out[f"Claude{k}"] = cc.get(a, {}).get("with_claude_trailer", 0)
        out[f"AllCommits{k}"] = cc.get(a, {}).get("commits", row)
    out["ClaudeTotal"] = sum(v["with_claude_trailer"] for v in cc.values())
    out["AllCommitsTotal"] = sum(v["commits"] for v in cc.values())
    out["FlagshipEvidence"] = ", ".join(names[c] for c in ("aurora-defi", "helix-espionage", "kestrel-av") if c in m["evidence"]) or "none"
    out["OracleBudget"] = next(iter(rd.load_oracle().values()))["budget"]
    cr = R["code_review"]
    tot = {k: sum(d.get(k, 0) for d in cr["by_severity"].values()) for k in ("fixed", "deferred", "rejected")}
    out.update({"ReviewTotal": cr["total"], "ReviewFixed": tot["fixed"], "ReviewDeferred": tot["deferred"], "ReviewRejected": tot["rejected"],
                "ReviewPZeroFixed": cr["by_severity"]["P0"].get("fixed", 0), "ReviewPOneFound": sum(cr["by_severity"]["P1"].values()), "ReviewPOneFixed": cr["by_severity"]["P1"].get("fixed", 0)})
    old = R["bootstrap_at_100_seeds"]["plain"]
    out.update({"BootOldSeeds": old["n_seeds"], "BootOldBelow": len(old["below_80"]), "BootOldWorst": pct(min(old["below_80"].values()), 1) if old["below_80"] else "none",
                "BootOldWorstCase": names[min(old["below_80"], key=old["below_80"].get)] if old["below_80"] else "none",
                "BootOldSecondCase": names[sorted(old["below_80"], key=old["below_80"].get)[1]] if len(old["below_80"]) > 1 else "none",
                "BootOldSecond": pct(sorted(old["below_80"].values())[1], 1) if len(old["below_80"]) > 1 else "none",
                "SensPriorChanges": R["sensitivity"]["parameter_impact"]["PRIOR_DEFECT_RATE"]})
    for k, v in ev["tests"].items():
        key = "".join(w.capitalize() for w in k.split("_"))
        out[f"Tests{key}"] = v["passed"]
        out[f"TestsFailed{key}"] = v["failed"]
    return {k: str(v) for k, v in out.items()}


def md(name: str) -> tuple[list[str], list[list[str]]]:
    return md_rows(getattr(rd, name)())


def tables(facts: dict, ev: dict) -> dict[str, str]:
    t: dict[str, str] = {}
    h, r = md("matters")
    t["tab_matters"] = tex_table(["Case", "Verdict (plain rules)", "Lawyers move it by", "Seed coin-flip", "Verdict (surprises on)"], [[x[0], x[1], x[2], x[3], x[4]] for x in r], "@{}p{4cm}p{2.9cm}rrp{2.9cm}@{}")
    h, r = md("bootstrap")
    t["tab_bootstrap"] = tex_table(h, r, "@{}p{5cm}lrlr@{}")
    h, r = md("sensitivity")
    t["tab_sensitivity"] = tex_table(h, r, "@{}lrr@{}")
    h, r = md("oracle")
    t["tab_oracle"] = tex_table(["Case", "Surprises", "Kept", "Confirmed on fresh seeds", "Gain per trial vs the old equilibrium"], [[x[0], x[1], x[4], x[5], x[6]] for x in r], "@{}p{4.9cm}lrrp{3.5cm}@{}")
    h, r = md("lectures")
    t["tab_lectures"] = tex_table(["Lecture concept", "What our data says", "Relaxation or limit"], [[x[0], x[2], x[3]] for x in r], "@{}p{2.8cm}p{5.2cm}p{6cm}@{}", r"\footnotesize")
    h, r = md("deviation_seeds")
    t["tab_seeds"] = tex_table(h, r, "@{}p{6cm}p{5cm}r@{}")
    edge = [[x["case"], x["outcome"].replace("_", " "), ", ".join(x["rules"][:6]), f"{x['budget_spent'].get('prosecution', 0):g} / {x['budget_spent'].get('defense', 0):g}"] for x in ev["edge_fixtures"]]
    t["tab_edge"] = tex_table(["Edge fixture", "Verdict (Bold vs Careful, seed 0)", "Rules fired", "Budget spent (Accuser / Defender)"], edge, "@{}p{3.7cm}p{3cm}p{4.6cm}p{2.6cm}@{}", r"\footnotesize")
    G = facts["git"]
    rows = []
    for a, n in G["by_author"].items():
        lo, hi = G["first_last"][a]
        touched = ", ".join(f"{k} {v}" for k, v in sorted(G["files_touched_by_author"].get(a, {}).items(), key=lambda kv: (-kv[1], kv[0]))[:6])
        rows.append([a, str(n), f"{lo} to {hi}", touched])
    t["tab_git"] = tex_table(["Git author name", "Commits", "First to last", "Files touched by area (count)"], rows, "@{}p{3.2cm}rp{3.6cm}p{6cm}@{}", r"\footnotesize")
    C = G.get("course", {})
    if C:
        crow = [[a, str(n), ", ".join(f"{k} {v}" for k, v in sorted(C["areas_by_author"].get(a, {}).items(), key=lambda kv: (-kv[1], kv[0]))[:4])] for a, n in sorted(C["by_author"].items(), key=lambda kv: (-kv[1], kv[0]))]
        t["tab_course"] = tex_table(["Author name in the official repository", "Commits", "Files touched by area (count)"], crow, "@{}p{5cm}rp{8cm}@{}", r"\footnotesize")
    ms = [[d["date"], d["what"]] for d in G["milestones"]]
    ms += [[g["planned"], f"Gate {g['gate']} planned ({g['what']}); first evidence in git {g['first_in_git']} ({g['evidence_path']}): {g['status']}"] for g in G["gates"]]
    t["tab_milestones"] = tex_table(["Date", "What (first appearance in git, or a planned gate)"], sorted(ms), "@{}p{2.4cm}X@{}", r"\small")
    return t


def write_all(dest: Path = GEN) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    facts = sf.collect()
    (dest / "facts.json").write_text(json.dumps(facts, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    ev = json.loads((GEN / "eval_plan.json").read_text(encoding="utf-8"))
    mac = macros(facts, ev)
    (dest / "numbers.tex").write_text("% generated by report/build_report.py: do not edit\n" + "".join(f"\\newcommand{{\\{k}}}{{{esc(v) if not v.endswith(chr(92) + '%') else v}}}\n" for k, v in mac.items()), encoding="utf-8")
    for name, body in tables(facts, ev).items():
        (dest / f"{name}.tex").write_text("% generated by report/build_report.py: do not edit\n" + body, encoding="utf-8")


GIT_DERIVED_FILES = {"tab_git.tex", "tab_milestones.tex"}
GIT_MACRO = re.compile(r"\\newcommand\{\\(NCommits|NAuthors|NCommitDays|FirstCommit|LastCommit|Commits|First|Last|Claude|AllCommits|EOne)\w*\}")


def _comparable(name: str, text: str) -> str:
    """Git-derived values change with every commit, so a freshness check compares only what comes from results/ and the eval measurements."""
    if name in GIT_DERIVED_FILES:
        return ""
    if name == "numbers.tex":
        return "\n".join(ln for ln in text.splitlines() if not GIT_MACRO.match(ln))
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            fresh = Path(tmp)
            (fresh / "eval_plan.json").write_text((GEN / "eval_plan.json").read_text(encoding="utf-8"), encoding="utf-8")
            write_all(fresh)
            stale = [n for n in sorted(p.name for p in fresh.glob("*.tex")) if _comparable(n, (fresh / n).read_text(encoding="utf-8")) != _comparable(n, (GEN / n).read_text(encoding="utf-8") if (GEN / n).exists() else "")]
        if stale:
            print("report/generated is stale (" + ", ".join(stale) + "): run python report/build_report.py --no-pdf")
            return 1
        print("report generated files up to date")
        return 0
    write_all()
    print("wrote report/generated")
    if a.no_pdf:
        return 0
    exe = shutil.which("tectonic")
    if not exe:
        print("tectonic is not installed (brew install tectonic); the generated tables were written")
        return 2
    p = subprocess.run([exe, "--keep-logs", "main.tex"], cwd=REPORT, capture_output=True, text=True)
    sys.stdout.write(p.stdout[-1500:] + p.stderr[-2500:])
    if p.returncode == 0:
        shutil.copy(REPORT / "main.pdf", REPORT / "Saul_Goodman_T22_Report.pdf")
        print("wrote report/Saul_Goodman_T22_Report.pdf")
    return p.returncode


if __name__ == "__main__":
    raise SystemExit(main())
