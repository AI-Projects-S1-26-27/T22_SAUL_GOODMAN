"""Build the 6-slide deck: presentation/Saul_Goodman_T22.pptx (and, with --pdf, the PDF drawn from the same layout by Chromium).

    python scripts/make_figures.py              # charts from results/
    python presentation/build_slides.py --pdf   # the deck, then presentation/Saul_Goodman_T22.pdf

Every number on a slide is read from results/ and git by scripts/submission_facts.py. Exactly six slides, in the order the course
brief fixes; speaker notes on each carry a target time. Needs python-pptx (and playwright's Chromium for --pdf, already a dev dependency).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import submission_facts as sf  # noqa: E402

OUT = ROOT / "presentation" / "Saul_Goodman_T22.pptx"
FIG = ROOT / "presentation" / "figures"
NAVY, BLUE, ORANGE, GREY, LIGHT, WHITE = (RGBColor.from_string(x) for x in ("1B2A49", "2F6DB5", "D9822B", "5B6577", "EEF2F8", "FFFFFF"))
FONT = "Arial"
REPO = "https://github.com/AI-Projects-S1-26-27/T22_SAUL_GOODMAN"
MEMBERS = ("Aditya Singh", "Divvij Y. Chichra", "Lakshya Sachdeva", "Mofasser A. Midda", "Pramit Khandelwal", "Rakshit Goel", "Rohan B. Pagire")


LOG: list[list[dict]] = []  # per slide, every shape added (geometry, fill, runs), so the PDF can be drawn from the same layout


def run(par, text: str, size: int, bold: bool = False, color: RGBColor = NAVY, italic: bool = False) -> None:
    r = par.add_run()
    r.text = text
    f = r.font
    f.name, f.size, f.bold, f.italic = FONT, Pt(size), bold, italic
    f.color.rgb = color


def box(slide, x, y, w, h, paras, fill: RGBColor | None = None, anchor=MSO_ANCHOR.TOP, shape=MSO_SHAPE.RECTANGLE, line: RGBColor | None = None, align=PP_ALIGN.LEFT, margin: float = 0.12):
    """paras: list of paragraphs; each is a list of (text, size, bold, color) runs or a single such tuple."""
    LOG[-1].append({"kind": "box", "x": x, "y": y, "w": w, "h": h, "paras": [p if isinstance(p, list) else [p] for p in paras], "fill": fill, "line": line, "anchor": anchor, "align": align, "shape": shape, "margin": margin})
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1.25)
    s.shadow.inherit = False
    tf = s.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(0.06)
    for i, p in enumerate(paras):
        par = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        par.alignment = align
        par.space_after = Pt(4)
        for t in (p if isinstance(p, list) else [p]):
            run(par, *t)
    return s


def new_slide(prs: Presentation):
    LOG.append([])
    return prs.slides.add_slide(prs.slide_layouts[6])


def frame(prs: Presentation, title: str, n: int):
    slide = new_slide(prs)
    box(slide, 0, 0, 13.333, 1.0, [[(title, 30, True, WHITE)]], fill=NAVY, anchor=MSO_ANCHOR.MIDDLE, margin=0.5)
    box(slide, 0, 7.12, 13.333, 0.38, [[(f"CS F407 Artificial Intelligence  |  Team 22, Saul Goodman  |  {n} / 6", 11, False, GREY)]], anchor=MSO_ANCHOR.MIDDLE, margin=0.5)
    return slide


def notes(slide, minutes: str, text: str) -> None:
    slide.notes_slide.notes_text_frame.text = f"[Target time {minutes}]\n{text}"


def pct(x: float) -> str:
    return f"{round(100 * x)}%"


def build() -> Presentation:
    facts = sf.collect()
    R, G = facts["results"], facts["git"]
    names = R["case_names"]
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)

    # ------------------------------------------------------------------ 1. title
    s = new_slide(prs)
    box(s, 0, 0, 13.333, 7.5, [[("", 10)]], fill=NAVY)
    box(s, 0.7, 0.55, 11.9, 0.5, [[("CS F407 ARTIFICIAL INTELLIGENCE  |  BITS PILANI, HYDERABAD CAMPUS", 14, True, RGBColor.from_string("9DB7E0"))]])
    box(s, 0.7, 1.25, 11.9, 1.9, [[("Strategic AI Agents in a Simulated Courtroom", 46, True, WHITE)], [("Evidence, objections and limited budgets, played as a game between two rational agents", 20, False, RGBColor.from_string("D6E0F2"))]])
    box(s, 0.7, 3.5, 6.2, 2.7, [
        [("Team 22: Saul Goodman", 26, True, WHITE)],
        [("Project type: Demo track", 20, False, WHITE)],
        [("Area: Agents & Game Theory", 20, False, WHITE)],
        [("(the exact judge draws on knowledge representation & reasoning)", 15, False, RGBColor.from_string("D6E0F2"))],
        [("GitHub: " + REPO, 14, False, ORANGE)],
    ])
    box(s, 7.3, 3.5, 5.3, 3.2, [[("Team", 16, True, ORANGE)]] + [[(m, 16, False, WHITE)] for m in MEMBERS])
    notes(s, "0:20", "Introduce the team and the project in one sentence: a courtroom played as a budgeted game, with an exact rule-based judge and a game-theory layer on top. Demo track; Agents and Game Theory.")

    # ------------------------------------------------------------------ 2. problem
    s = frame(prs, "Problem: a trial is a budgeted game with hidden flaws", 2)
    box(s, 0.6, 1.35, 6.3, 5.4, [
        [("Two lawyer agents, one fixed judge", 22, True, BLUE)],
        [("Each side has a limited budget and chooses: offer an exhibit, object, impeach a witness, rest.", 20)],
        [("A flawed exhibit helps only if the other side misses the flaw; a wrong objection is itself sanctioned.", 20)],
        [("Neither side can see which of the other's exhibits is really defective, only a noisy signal.", 20)],
        [("The same structure appears in audits, peer review and security inspections.", 20)],
    ], fill=LIGHT)
    box(s, 7.2, 1.35, 5.5, 3.4, [
        [("Project question", 20, True, ORANGE)],
        [("Against a fixed and fully transparent judge, how do budgets, penalties and noisy perception decide whether an aggressive or a conservative strategy wins, and when does the game have a dominant strategy rather than a mixed equilibrium?", 19, False, WHITE)],
    ], fill=NAVY)
    box(s, 7.2, 4.95, 5.5, 1.8, [
        [("Course concepts", 18, True, BLUE)],
        [("rational agents and utility, Bayes' rule, game formulation, Nash equilibrium, empirical game analysis, minimax and alpha-beta", 16)],
    ], line=BLUE)
    notes(s, "0:50", "Say the question out loud. Stress that nothing here is a model of real courts: the judge is a published rule system, and the thresholds are game parameters. The interesting object is the interaction between the two budgeted lawyers.")

    # ------------------------------------------------------------------ 3. related work
    s = frame(prs, "Related work: models argue, we solve a game", 3)
    cols = (
        ("AgentsCourt", "He et al., EMNLP 2024 Findings", "LLM agents simulate a court debate and a judge's decision, with legal-resource retrieval; evaluated on 420 Chinese judgment documents."),
        ("Strategic Courtroom Framework", "Siedler, arXiv 2026", "Trait-conditioned LLM teams argue 10 synthetic cases over 7,000+ simulated trials; a reinforcement-learning orchestrator picks defense traits."),
        ("Reflective multi-agent argument generation", "Zhang & Ashley, arXiv 2025", "Reflective multi-agent prompting to reduce manipulation and hallucination in generated legal arguments."),
    )
    for i, (t, a, d) in enumerate(cols):
        box(s, 0.6 + i * 4.15, 1.35, 3.95, 3.1, [[(t, 19, True, BLUE)], [(a, 14, False, GREY, True)], [(d, 16)]], fill=LIGHT)
    box(s, 0.6, 4.65, 12.05, 1.05, [[("Empirical game-theoretic analysis (Wellman, 2006): ", 17, True, NAVY), ("build a game from simulated play, then solve it. We use this method, with an exact judge in place of a learned one.", 17)]], line=BLUE, anchor=MSO_ANCHOR.MIDDLE)
    box(s, 0.6, 5.85, 12.05, 1.1, [[("Our contribution: ", 19, True, ORANGE), ("a small formal game with no language model in the core, an exact deterministic judge, and equilibria we can check, so every conclusion can be reproduced.", 19, False, WHITE)]], fill=NAVY, anchor=MSO_ANCHOR.MIDDLE)
    notes(s, "0:50", "These systems put the intelligence in language models. We take the opposite route. We claim no new algorithm and no accuracy on real cases; the contribution is an inspectable teaching demo. Descriptions of the three papers follow their abstracts; Wellman is cited for the method only.")

    # ------------------------------------------------------------------ 4. methods
    s = frame(prs, "Methods: one pipeline, an exact judge, a game on top", 4)
    stages = ("Case file\nevidence, elements", "Procedure\nturns, budgets, rules", "Agents\nfour styles", "Judge\nexact, with rule IDs", "Game layer\npayoffs, equilibria")
    for i, t in enumerate(stages):
        head, sub = t.split("\n")
        box(s, 0.5 + i * 2.5, 1.3, 2.25, 1.05, [[(head, 18, True, WHITE)], [(sub, 12, False, RGBColor.from_string("D6E0F2"))]], fill=BLUE if i != 3 else ORANGE, shape=MSO_SHAPE.PENTAGON, anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
    box(s, 0.5, 2.55, 6.1, 2.3, [
        [("The judge scores the record", 19, True, BLUE)],
        [("Per element e:  L_e = prior + 3 · Σ over facts ( strongest for − strongest against )", 15, True)],
        [("each item: support × reliability × credibility × (1 − contradiction) × corroboration", 14)],
        [("Accuser wins only if every L_e clears the standard of proof; all arithmetic is exact fractions.", 14)],
    ], fill=LIGHT)
    box(s, 0.5, 5.0, 6.1, 1.95, [
        [("Four lawyer styles", 19, True, BLUE)],
        [("Bold: offers flawed items, objects freely.  Careful: clean items only, keeps a reserve.  Smart: maximises expected utility, learns the other side.  Wild: random, sometimes illegal.", 14)],
    ], fill=LIGHT)
    methods = (
        ("Payoff Monte Carlo", "4×4 payoff table per case"),
        ("Exact Nash", "support enumeration in rationals"),
        ("Bootstrap", "how stable is the equilibrium label"),
        ("Sensitivity", "rulebook constants moved ±25%"),
        ("Best-response search", "can the styles be beaten?"),
        ("Classic-game classifier", "prisoner's dilemma, stag hunt, ..."),
        ("Minimax, alpha-beta", "the trial as a game tree"),
    )
    box(s, 6.85, 2.55, 5.95, 4.4, [[("Analysis methods", 19, True, ORANGE)]] + [[(f"{a}: ", 16, True), (b, 16)] for a, b in methods], line=BLUE)
    notes(s, "1:20", "Walk the pipeline left to right. The judge never imports the agents; agents see the judge only through a read-only oracle that answers what-if questions from the public record. Every analysis method is named once here and appears in the report with its relaxations.")

    # ------------------------------------------------------------------ 5. results
    s = frame(prs, "Results: strategy matters in some cases, and not in most", 5)
    m, b, o, c = R["matters"]["plain"], R["bootstrap"]["plain"], R["oracle"], R["classic"]
    worst = min(({**R["bootstrap"][k], "mode": "plain rules" if k == "plain" else "surprises on"} for k in ("plain", "surprises")), key=lambda x: x["worst"])
    big = (
        (f"{m['n_move']} of {m['n_cases']}", f"cases are moved by the lawyers; the other {m['n_evidence']} are decided by the evidence alone ({m['n_seeds']} seeds, all nine pairings)"),
        (f"{o['n_beaten']} of {o['n_searches']}", f"best-response searches beat the hand-written styles; most in {names[o['best']['case']]} (+{max(o['best']['gains'].values()):.2f} per trial, confirmed on fresh seeds)"),
        (pct(worst["worst"]), f"lowest stability of any equilibrium label ({names[worst['worst_case']]}, {worst['mode']}); {worst['n_seeds']} seeds, {worst['n_resamples']} resamples. With plain rules every label is at least {pct(b['worst'])}"),
        (f"0 of {c['corners']}", f"two-by-two corners are a prisoner's dilemma, stag hunt, battle of the sexes or chicken; {c['matching_pennies']} are matching pennies. Not found, reported as such"),
    )
    for i, (num, txt) in enumerate(big):
        y = 1.3 + i * 1.42
        box(s, 0.5, y, 2.7, 1.3, [[(num, 34, True, WHITE)]], fill=BLUE if i != 3 else GREY, anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
        box(s, 3.25, y, 4.35, 1.3, [[(txt, 14)]], fill=LIGHT, anchor=MSO_ANCHOR.MIDDLE)
    LOG[-1].append({"kind": "img", "src": FIG / "fig_matters.png", "x": 7.8, "y": 1.45, "w": 5.15})
    s.shapes.add_picture(str(FIG / "fig_matters.png"), Inches(7.8), Inches(1.45), width=Inches(5.15))
    box(s, 7.8, 5.2, 5.15, 1.7, [[("Read it honestly: ", 14, True, ORANGE), ("the legal model is stylised and the thresholds are game parameters, not legal probabilities. Several conclusions depend on the rulebook's constants (report, Discussion).", 14)]], line=ORANGE)
    notes(s, "1:20", "Four numbers only. All come from stored result files: a script reads results/ and writes them here. Lead with the finding that most cases are decided by the evidence, which we measured and did not expect. The not-found result for the classic games is deliberate: no case was retuned to make one appear.")

    # ------------------------------------------------------------------ 6. management
    s = frame(prs, "Project management and work division", 6)
    C = G["course"]
    ms = G["milestones"]
    rows = [(f"{g['gate']} planned {g['planned']}:", f"{g['what']}; first in git {g['first_in_git']} ({g['status']})") for g in G["gates"]]
    rows += [(d["date"], d["what"]) for d in ms]
    box(s, 0.5, 1.3, 7.2, 5.65, [[("Planned gates vs what git shows", 19, True, BLUE)]] + [[(f"{a}  ", 14, True, ORANGE), (b, 14)] for a, b in rows], fill=LIGHT)
    owners = (("Aditya", "contracts, cases"), ("Divvij", "procedure"), ("Lakshya", "judge"), ("Mofasser", "agents"), ("Rohan", "game theory"), ("Pramit", "engine, API, CLI"), ("Rakshit", "viz"))
    box(s, 7.95, 1.3, 4.9, 2.75, [[("Owners (proposal)", 18, True, BLUE)]] + [[(f"{a}: ", 15, True), (p, 15)] for a, p in owners], line=BLUE)
    box(s, 7.95, 4.2, 4.9, 2.75, [
        [("Deviations and cuts", 18, True, ORANGE)],
        [("Wild replaced Mixed(0.5) in the 4×4 game", 14)],
        [("Language-model layer: optional exhibition, never run live here", 14)],
        [("Impeachment needs an admitted exhibit (found in review)", 14)],
        [(f"Official repo: {C['commits']} commits, {len(C['by_author'])} authors. This branch: {G['non_merge_commits']} commits, {len(G['by_author'])} authors. How they relate: see the report", 14, True)],
    ], line=ORANGE)
    notes(s, "1:00", "Be plain about the history. There are two: the official course repository shows each member committing their own package from 2 October, and this integration branch starts with one commit on 27 September that already contains the core, with later work concentrated in one author. The report states both and leaves how they relate to the team to explain. Each member explains their own package in the viva.")
    return prs


def _css(c: RGBColor) -> str:
    return "#" + str(c)


def to_html() -> str:
    """The same shapes the .pptx holds, as absolutely positioned HTML (1280x720 px per slide)."""
    parts = ["<!doctype html><meta charset=utf-8><style>@page{size:13.333in 7.5in;margin:0}body{margin:0}.slide{position:relative;width:13.333in;height:7.5in;overflow:hidden;page-break-after:always;font-family:Arial,Helvetica,sans-serif}.b{position:absolute;box-sizing:border-box;display:flex;flex-direction:column}.b p{margin:0 0 4pt 0}</style>"]
    for shapes in LOG:
        parts.append("<section class=slide>")
        for sh in shapes:
            if sh["kind"] == "img":
                import base64

                b64 = base64.b64encode(Path(sh["src"]).read_bytes()).decode()
                parts.append(f'<img src="data:image/png;base64,{b64}" style="position:absolute;left:{sh["x"]}in;top:{sh["y"]}in;width:{sh["w"]}in">')
                continue
            st = [f"left:{sh['x']}in", f"top:{sh['y']}in", f"width:{sh['w']}in", f"height:{sh['h']}in", f"padding:0.06in {sh['margin']}in"]
            if sh["fill"] is not None:
                st.append(f"background:{_css(sh['fill'])}")
            if sh["line"] is not None:
                st.append(f"border:1.25pt solid {_css(sh['line'])}")
            if sh["shape"] == MSO_SHAPE.PENTAGON:
                st.append("clip-path:polygon(0 0,88% 0,100% 50%,88% 100%,0 100%)")
            st.append({MSO_ANCHOR.MIDDLE: "justify-content:center", MSO_ANCHOR.TOP: "justify-content:flex-start"}.get(sh["anchor"], "justify-content:flex-start"))
            st.append("text-align:" + {PP_ALIGN.CENTER: "center"}.get(sh["align"], "left"))
            ps = []
            for para in sh["paras"]:
                runs = "".join(f'<span style="font-size:{t[1]}pt;font-weight:{700 if len(t) > 2 and t[2] else 400};color:{_css(t[3]) if len(t) > 3 else _css(NAVY)};font-style:{"italic" if len(t) > 4 and t[4] else "normal"}">{t[0]}</span>'.replace("\n", "<br>") for t in para)
                ps.append(f"<p>{runs}</p>")
            parts.append(f'<div class=b style="{";".join(st)}">{"".join(ps)}</div>')
        parts.append("</section>")
    return "".join(parts)


def write_pdf(path: Path) -> None:
    from playwright.sync_api import sync_playwright

    html = to_html()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="load")
        page.pdf(path=str(path), width="13.333in", height="7.5in", print_background=True)
        browser.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", action="store_true")
    a = ap.parse_args()
    prs = build()
    assert len(prs.slides) == 6
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print("wrote", OUT.relative_to(ROOT))
    if a.pdf:
        write_pdf(OUT.with_suffix(".pdf"))
        print("wrote", OUT.with_suffix(".pdf").relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
