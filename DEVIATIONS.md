# Deviations from the proposal

Where this project differs from `AIPP_Team22_SaulGoodman.pdf` (October 2026), and where it goes beyond it. Each row was checked against the
code, not remembered. The proposal's positioning is "a small formal game with no language model, an exact judge, and a game-theory layer whose
equilibria we can check"; the certified analysis keeps that positioning, and everything that departs from it is labelled.

## Differences in the certified game

| # | The proposal says | What the code does | Why, and what it affects |
|---|---|---|---|
| D1 | Sec. 7: the four strategic agents are Aggressive, Conservative, Adaptive and Mixed(p = 0.5). | The four styles in the payoff tables, the bundle and the lab are Aggressive (Bold), Conservative (Careful), Adaptive (Smart) and **Reckless (Wild)**. `mixed:<p>` still exists as a strategy name but is not in the four-by-four game. | The repository does not record why. It is flagged here so the report can say so. Every certified table, bootstrap, search and classic-game result uses these four. |
| D2 | Sec. 7: Mixed(p) "at each decision independently acts as Aggressive with probability p". | `MixedAgent` draws once per trial, from the seed, whether to play Aggressive or Conservative, and sticks with it. | Kept as built; it is not in the four-by-four game (D1), so no certified result depends on it. |
| D3 | Sec. 7: 200 common seeds per cell for the payoff matrices and 200 bootstrap resamples. | The payoff tables, the bootstrap and the classic-game labels use the proposal's 200 seeds per cell and 200 resamples (re-run on 17 Nov 2026, after the first certified runs had used 100 seeds). Sensitivity, the does-strategy-matter measurement and the lookahead comparison use fewer seeds (table below). | So that every result can be regenerated in minutes on a laptop. Standard errors and bootstrap stability are reported beside every result. |
| D4 | Sec. 5: the opponent receives one noisy signal per item and defect type. | Relevance is observed exactly (the support values are public once an exhibit is offered); the other five grounds go through the proposal's noisy channel (true-positive rate `a`, false-positive rate `(1 - a) / 4`, prior 0.15). | Relevance is a visible property of the exhibit, not a hidden flaw. The prior in code matches the proposal. |
| D5 | Sec. 6: directed verdict is granted "if any element is already at or below its standard (DV-1)" when the prosecution rests. | The defense must move for it (a costed action); the motion is granted only if some element's log-odds are below zero. A directed verdict is also entered on the judge's own initiative when no admitted evidence supports an element (DV-2, as proposed). | Zero is the point at which no reasonable fact-finder could find the element proven, which is the legal test; the standards of proof stay the bar for the final verdict. |
| D6 | Sec. 6 does not say when an exhibit may be used to impeach. | A party may impeach a witness only with an exhibit that has been offered and admitted (rule `V-IMPEACH-NOT-ADMITTED`, in the validator, the party's view and the tree search). Before 17 Nov 2026 the engine allowed an exhibit that was never admitted (finding E1 in `docs/CODE_REVIEW.md`). | A real impeachment needs a document in the record. The fix changed 37 of the 160 recorded trials (their digests, re-pinned) and two recorded verdicts: Helix Dynamics, Smart against Wild (guilty to not guilty) and Kestrel, Careful against Wild (not liable to liable). 9 spoken lines are new and 12 are gone, so those 9 need recording with `scripts/record_voices.py` (until then the browser's own voice reads them). Every analysis in `results/` except `matters` was re-run with the documented scripts; the numbers in `REPORT.md` are regenerated. |

The thresholds are **game parameters, not legal probabilities**, as the proposal says (Sec. 9). Section 6.3 of `REPORT.md` tests which
conclusions survive moving them.

Seeds per cell actually used, read from the result files:

<!-- BEGIN GENERATED:deviation_seeds -->
| Analysis | File | Seeds per cell |
|---|---|---|
| Bootstrap of the equilibrium label | `results/bootstrap.json` | 200 |
| Classic-game labels | `results/classic.json` | 200 |
| Pareto and security | `results/efficiency.json` | 200 |
| Rulebook sensitivity | `results/sensitivity.json` | 16 |
| Does strategy matter | `results/matters.json` | 8 |
| Lookahead comparison | `results/lookahead.json` | 40 |
<!-- END GENERATED:deviation_seeds -->

## Additions beyond the proposal

None of these changes a certified result. Each is off by default or clearly labelled where it appears.

| # | Addition | Status |
|---|---|---|
| A1 | **Courtroom surprises**: a witness who does not appear, a digital record without its certificate, a witness who turns hostile. | Behind a flag, off by default, never in the recorded trials. Analyses are reported with surprises off and, separately, on. |
| A2 | **A language-model layer** (an AI lawyer, case drafting from plain English, narration of unscripted cases, a model-worded verdict explanation, and the analyst chat). | Optional, off unless a backend answers, labelled "exhibition, not certified" wherever it appears, never imported by the core, never able to reach a verdict or a certified payoff. The instructor cleared the use of language models verbally on 4 November 2026; there is no written record. See `docs/LLM_ROLE.md`. |
| A3 | **The strategy lab and live controls** (seed box, LIVE/RECORDED badge, digest comparison, "does strategy matter here", contested-case finder, tipping point, what-if editor, verdict explainer). | Computed by the engine; the hosted site shows stored results and says so. |
| A4 | **Best-response search** (a double-oracle loop over the five parameters of a lawyer profile). | Certified analysis: deterministic styles and the exact judge only. |
| A5 | **Classic-game classification, Pareto efficiency, exact security values** (`gametheory/classic.py`, `efficiency.py`). | Certified analysis: it reads the same measured tables. |
| A6 | **The trial as a game tree** (`gametheory/search.py`): exact minimax and alpha-beta on an *open-file relaxation* (both sides see all evidence and flaws, no perception noise, zero-sum payoff). | A relaxation, labelled wherever it is shown. It is not the game the certified analysis solves, because the real game has hidden information and is general-sum. |
| A7 | **A lookahead lawyer** (`agents/lookahead.py`), the proposal's "stretch expectimax agent" in a simple form: depth-limited alpha-beta over its own next moves, an expectation over its belief when answering an offer. | An exhibition, selectable only when the local server is running, not one of the four certified styles, never in a certified table. It adds one multi-impeachment what-if method to the public oracle; existing calls are unchanged and the pinned digests do not move. |

## What was not changed

The documented game (phase order, actions, the noisy-perception channel, the four style definitions) and every recorded trial are as they were.
`tests/golden/bundle_digests.json` pins the digest of every recorded trial and `tests/golden/lines_baseline.json` every spoken line.
