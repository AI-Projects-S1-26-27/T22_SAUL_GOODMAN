"""Draw the report's and the slides' charts from results/ (nothing typed by hand).

    python scripts/make_figures.py

Writes report/figures/*.pdf (vector, for LaTeX) and presentation/figures/*.png (for the slides). Needs matplotlib.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import render_docs as rd  # noqa: E402

REPORT_FIG = ROOT / "report" / "figures"
SLIDE_FIG = ROOT / "presentation" / "figures"
NAVY, BLUE, ORANGE, GREY, GREEN = "#1B2A49", "#2F6DB5", "#D9822B", "#8A94A6", "#3C8D5A"
SHORT = {
    "aurora-defi": "Aurora DeFi", "broken-bike": "Broken Bike", "cookie-jar": "Cookie Jar", "edge-defense-only": "Defense-only",
    "edge-empty-docket": "Empty Docket", "edge-mutual-exclusion": "Mutual Exclusion", "edge-poisoned-tree": "Poisoned Tree",
    "garden-dog": "Garden Dog", "helix-espionage": "Helix Espionage", "kestrel-av": "Kestrel AV-7",
}
STYLE = {"aggressive": "Bold", "conservative": "Careful", "adaptive": "Smart", "reckless": "Wild"}


def _setup(big: bool) -> None:
    plt.rcParams.update({
        "font.family": "sans-serif", "font.size": 15 if big else 9, "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": NAVY, "axes.labelcolor": NAVY, "xtick.color": NAVY, "ytick.color": NAVY, "text.color": NAVY,
        "axes.titleweight": "bold", "axes.titlesize": 17 if big else 10, "figure.dpi": 150,
    })


def _save(fig: plt.Figure, name: str, slide: bool) -> None:
    REPORT_FIG.mkdir(parents=True, exist_ok=True)
    SLIDE_FIG.mkdir(parents=True, exist_ok=True)
    if slide:  # the large-type version is for the projector (png); the small one is the report's vector figure
        fig.savefig(SLIDE_FIG / f"{name}.png", bbox_inches="tight", dpi=200)
    else:
        fig.savefig(REPORT_FIG / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def matters(big: bool = False) -> None:
    _setup(big)
    d = rd.load("matters")
    rows = sorted(d["cases"].items(), key=lambda kv: kv[1]["pairing_spread"])
    fig, ax = plt.subplots(figsize=(8.4 if big else 5.6, 4.4 if big else 3.1))
    y = np.arange(len(rows))
    ax.barh(y + 0.2, [r["pairing_spread"] * 100 for _, r in rows], 0.38, color=BLUE, label="Lawyers move it by")
    ax.barh(y - 0.2, [r["seed_noise"] * 100 for _, r in rows], 0.38, color=ORANGE, label="Seed coin-flip")
    ax.set_yticks(y, [SHORT[c] for c, _ in rows])
    ax.set_xlabel(f"percentage points of Accuser wins ({d['n_seeds']} seeds, 9 pairings)")
    ax.legend(frameon=False, loc="lower right")
    _save(fig, "fig_matters", big)


def bootstrap(big: bool = False) -> None:
    _setup(big)
    a, b = rd.load("bootstrap"), rd.load("bootstrap_surprises")
    order = sorted(a["cases"], key=lambda c: a["cases"][c]["stability"])
    fig, ax = plt.subplots(figsize=(8.4 if big else 5.6, 4.4 if big else 3.1))
    y = np.arange(len(order))
    ax.scatter([a["cases"][c]["stability"] * 100 for c in order], y, s=70 if big else 28, color=BLUE, label=f"plain rules ({a['n_seeds']} seeds)", zorder=3)
    ax.scatter([b["cases"][c]["stability"] * 100 for c in order], y, s=70 if big else 28, color=ORANGE, marker="D", label=f"surprises on ({b['n_seeds']} seeds)", zorder=3)
    ax.axvline(80, color=GREY, lw=1, ls="--")
    ax.set_yticks(y, [SHORT[c] for c in order])
    ax.set_xlim(0, 103)
    ax.set_xlabel(f"how often the equilibrium label survives resampling (%, {a['n_resamples']} resamples)")
    ax.legend(frameon=False, loc="lower left", fontsize=11 if big else 7)
    _save(fig, "fig_bootstrap", big)


def oracle(big: bool = False) -> None:
    _setup(big)
    res = sorted(rd.load_oracle().values(), key=lambda r: (r["case_id"], r["surprises"]))
    labels, gains, cols = [], [], []
    for r in res:
        best = max((r["exploitability"][s]["gain"] for s in ("prosecution", "defense") if r["exploitability"][s]["found_better"]), default=0.0)
        labels.append(f"{SHORT[r['case_id']]}\n{'surprises' if r['surprises'] else 'plain'}")
        gains.append(best)
        cols.append(GREEN if best else GREY)
    fig, ax = plt.subplots(figsize=(8.4 if big else 5.6, 4.0 if big else 2.9))
    ax.bar(range(len(res)), gains, color=cols)
    ax.set_xticks(range(len(res)), [lab.replace("\n", " ") for lab in labels], fontsize=11 if big else 7, rotation=30, ha="right")
    ax.set_ylabel("utility gained per trial\nover the old equilibrium")
    for i, g in enumerate(gains):
        ax.text(i, g + 0.03, f"+{g:.2f}" if g else "none found", ha="center", fontsize=12 if big else 7)
    _save(fig, "fig_oracle", big)


def tree(big: bool = False) -> None:
    _setup(big)
    d = rd.load("tree_search")["cases"]
    rows = [(c, r) for c, r in d.items() if r["minimax_nodes"] and r["alphabeta_nodes"] and r["alphabeta_ordered_nodes"]]
    rows.sort(key=lambda kv: kv[1]["minimax_nodes"])
    fig, ax = plt.subplots(figsize=(8.4 if big else 6.2, 3.6 if big else 3.0))
    x = np.arange(len(rows))
    for k, (key, lab, col) in enumerate((("minimax_nodes", "plain minimax", GREY), ("alphabeta_nodes", "alpha-beta", BLUE), ("alphabeta_ordered_nodes", "alpha-beta, best move first", ORANGE))):
        ax.bar(x + (k - 1) * 0.27, [r[key] for _, r in rows], 0.27, color=col, label=lab)
    ax.set_yscale("log")
    ax.set_xticks(x, [SHORT.get(c, c) for c, _ in rows], fontsize=7 if not big else 10, rotation=40, ha="right")
    ax.set_ylabel("nodes visited (log scale)")
    ax.legend(frameon=False, fontsize=8 if not big else 11)
    _save(fig, "fig_tree", big)


def payoff(big: bool = False) -> None:
    _setup(big)
    d = rd.load("efficiency")
    cid = "helix-espionage"
    r = d["cases"][cid]
    m = np.array(r["accuser_win_rate"]) * 100
    rows, cols = [STYLE.get(s, s) for s in r["row_strategies"]], [STYLE.get(s, s) for s in r["col_strategies"]]
    fig, ax = plt.subplots(figsize=(5.2 if big else 3.6, 4.0 if big else 2.9))
    im = ax.imshow(m, cmap="Blues", vmin=0, vmax=100)
    ax.set_xticks(range(4), cols)
    ax.set_yticks(range(4), rows)
    ax.set_xlabel("Defender style")
    ax.set_ylabel("Accuser style")
    for i in range(4):
        for j in range(4):
            ax.text(j, i, f"{m[i, j]:.0f}", ha="center", va="center", color="white" if m[i, j] > 55 else NAVY, fontsize=13 if big else 8)
    ax.set_title(f"{SHORT[cid]}: Accuser win rate (%)", fontsize=12 if big else 8)
    fig.colorbar(im, ax=ax, shrink=0.8)
    _save(fig, "fig_payoff", big)


def main() -> int:
    for fn in (matters, bootstrap, oracle, payoff, tree):
        fn(big=False)
        fn(big=True)
    print("figures written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
