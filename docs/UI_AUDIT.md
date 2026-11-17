# UI audit: every number on screen

How it was done: `python scripts/ui_audit.py` (recorded mode, static files as on the hosted site) and `python scripts/ui_audit.py --live`
(with `python -m courtroom serve`) drive Chromium through every case in the docket (10 cases) on the home page and every lab chapter
(17 chapters). They flag text that says NaN, null, undefined, Infinity or `[object`, blank table cells, tables or charts whose numbers are all
zero or all equal, and chapters whose text does not change at all when the case changes. Each flag was then checked against `results/`.
Both modes produced the same flags. No page errors were thrown in either mode.

The audit was also run by hand for stale state: switching case, seed and the surprises box in live mode and checking what each section shows
(the "does strategy matter" box, the docket tags, the Which style wins grid and its source line).

## Findings

| # | Case | Section | Shown | True or bug | Fix |
|---|---|---|---|---|---|
| 1 | every case | Home, Which style wins | The docket choice did not move the section: it stayed on the first case, and its dropdown was never updated (`selectCase()` never called `renderStrategy`). | Bug | `selectCase()` now sets `#strat-case` and re-renders. Test `test_docket_choice_drives_which_style_wins_and_its_dropdown`. |
| 2 | every case | Home, Which style wins | A 2x2 of Bold and Careful, from `bundle.games`, while the page offers four styles. | Bug | Reads the certified four-by-four table in `data/analysis.js` (`results/efficiency.json`, win rates, both payoffs, equilibria). No script change was needed: the numbers were already in the file. |
| 3 | every case | Home, Which style wins | A missing cell was read as 0% (`?? 0`). | Bug | A missing or non-numeric cell now reads "no data" and the grid is never called flat when data is missing. Test `test_missing_cell_reads_no_data_never_zero`. |
| 4 | aurora-defi, edge-empty-docket, edge-defense-only | Home, Which style wins | Every box 0%. | True (`results/efficiency.json` `accuser_win_rate` is 0 in all 16 cells; `results/matters.json` rates them "Decided by the evidence") | Kept the numbers; added "The evidence decides this case: the Accuser wins 0% whatever either lawyer does", the "does strategy matter here" rating, and each side's payoff in every box. |
| 5 | cookie-jar, garden-dog, edge-mutual-exclusion | Home, Which style wins | Between 0% and 4% in the 16 boxes, rated "Decided by the evidence". | True (the four-style table has a few small non-zero cells under Wild; the three-style rating measures Bold, Careful and Smart) | The same sentence, worded with the range of the case ("only 0% to 2%" for cookie-jar). |
| 6 | every case | Home, Which style wins | The takeaway named only a pure equilibrium and said nothing when the game had several or a mixed one. | Bug | The takeaway now reads the equilibria in the same file: one pure, one mixed (with the exact shares), or several. |
| 7 | every case, live mode | Home, Which style wins | Ticking Courtroom surprises changed the "does strategy matter" box and the docket tags but not this section. | Bug (stale state) | The section follows `S.surprises` (the `efficiency_surprises` and `matters_surprises` results) and says which it shows. Test `test_surprises_toggle_updates_which_style_wins_in_live_mode`. |
| 8 | every case | Home, Which style wins | Nothing said the table is stored (the stored seeds, 200 per cell at the time of writing), so a reader could expect the seed box to move it. | Misleading | A one-line source note under the takeaway. |
| 9 | hosted site (any case) | Home, Brief your lawyers | "Surprise me" and the Lookahead style appeared although no server answers (`Live.ready()` ran whenever the page was served over http, even when `/api/health` failed). | Bug | `ready()` returns unless the server answered. Test `test_tour_skips_live_only_steps_on_the_hosted_site_and_keeps_them_when_live` checks it through the tour. |
| 10 | aurora-defi, edge-empty-docket, edge-defense-only | Lab, chapter 14 (guarantees) | The win-probability table is 0% in every box. | True (same data as finding 4) | One plain sentence above the table saying why, and that it is not missing data. |
| 11 | aurora-defi (and any case with equal-payoff equilibria) | Lab, chapter 14 | The same sentence twice: "Equilibrium paying (-1.68, 7.79): ..." (two different equilibria with the same payoffs). | Bug (reads as a duplicate) | Each line now names its pair of styles. |
| 12 | every case | Lab, chapters 1 to 8 against chapters 10 to 14 | The first chapters show one recorded trial per pairing (for example Careful vs Careful pays -1.60) and the later ones the certified 100-seed average (-1.68). | True (different seed counts) but unexplained | The source line under the case box now says the later chapters use stored results averaged over N seeds, with N read from the file. |
| 13 | every case | Lab, chapters 6 (change the rules), 16 (analyst), 17 (words) | The text is identical for every case. | True (these chapters explain controls and words; they hold no case data) | None needed. |
| 14 | every case | Lab, all other chapters | No NaN, null, undefined, blank cell or all-equal table beyond those above. | True | None needed. |

## Stale state checked in live mode

| Change | Sections that must follow | Result |
|---|---|---|
| Case (docket click) | Which style wins and its dropdown; the "does strategy matter" box; docket tags; start-case line | Follow (fixed for the first) |
| Case (lab dropdown) | KPIs and all 17 chapters | Follow |
| Seed | The next trial and its badge and digest | Follows; the stored tables do not depend on it, and now say so |
| Courtroom surprises | "does strategy matter" box, docket tags, Which style wins | Follow (fixed for the last) |
| Style | The brief, the trial that is played | Follow |

## Reproduce

```bash
python -m playwright install chromium
python scripts/ui_audit.py --json /tmp/audit.json
python scripts/ui_audit.py --live --json /tmp/audit_live.json
python -m pytest tests/test_ui_strategy.py tests/test_ui_tour.py
```
