# Code review before the 21 Nov demo

Nine reviewers, one per area, each working from the repository at commit `0fd0261` and reporting only what it could reproduce or point to at
a file and line. Severity: **P0** wrong result or crash in the demo path, **P1** wrong or misleading elsewhere, **P2** robustness, **P3** cleanup.
Status: `open` until fixed, `fixed` (with the commit), `deferred` or `rejected`, each with its reason.

Areas and ids: E engine, procedure, judge · A agents · G game theory · API api and cli · W web and lab · S security · R reproducibility ·
D docs against code · T tests. The reviewers' full write-ups are not committed; each finding below carries its evidence in short.

Clean results worth knowing (checked and found sound): maximin and minimax agree on 3000 random matrices and the minimax theorem held on 1000
constant-sum ones; the 2x2 classifier gave no inconsistency in 20000 random games under relabelling, swapping and scaling; minimax and alpha-beta
agreed on every small tree; `lab-math.js` matches Python on non-degenerate games; 6500 trials of every pairing with surprises raised no crash, loop
or illegal move; trials are identical under three `PYTHONHASHSEED` values; the lookahead lawyer's choices did not change when every hidden field
of the opponent's unoffered exhibits was mutated (160 runs); no secret in any revision of the git history; no script ran on injected
`<img onerror>` / `</script>` payloads in any case, witness, exhibit or model-reply field; all eight certified results regenerate byte-identical in
a fresh clone.

## Findings

### P0

| Id | Area | Finding and evidence | Proposed fix | Status |
|---|---|---|---|---|
| D2 | docs | `DEMO_SCRIPT.md` sends the presenter to a docket group "lawyers move the verdict" that does not exist (tabs are Everyday, Serious, Tricky tests), and says an everyday case is decided by the evidence, but `broken-bike` is in Everyday and `results/matters.json` rates it "lawyers". | Name the cases and tabs. | fixed: DEMO_SCRIPT names the tabs and cases; the generated list shows each case's tab |

### P1

| Id | Area | Finding and evidence | Proposed fix | Status |
|---|---|---|---|---|
| E1 | engine | The validator never checks that an impeaching exhibit was offered or admitted: 29 of 70 impeachments in the seed-0 4x4 library runs used an exhibit never admitted. | Require admission, or document it. **Either changes recorded trials and pinned digests, so it needs a voice re-record and is your decision.** | fixed: you approved it. The validator, the view and the search now require an admitted exhibit; digests and line baseline re-pinned, results regenerated, DEVIATIONS D6. 9 new spoken lines still need recording |
| A1 | agents | README style table lists Chaotic and Mixed and omits Reckless (Wild). | Correct the table. | fixed: README style table corrected |
| A2 | agents | The Bold blurb says "Shows every piece of evidence", but Bold offered 194 of 391 own exhibits. | New blurb text in `app.js` (not in the pinned lines or digests; `profile.description` is in the digests and stays). | fixed: Bold blurb in app.js reworded (pinned lines unchanged) |
| API1 | api | No time cap on heavy endpoints: an inline case at the limit takes 12.7 s on `/api/tree` and 24 to 44 s on `/api/lookahead`; 33 concurrent heavy requests starved `/api/health` for up to 9.6 s. | Lower inline limits, wall-clock budget, semaphore with 503. | fixed in part: at most two heavy requests at once, the rest get 503 and `/api/health` stays responsive. No per-request time cap yet |
| API2 | api | `/api/find` and `/api/classic/find` give load-dependent answers (a 25 s budget counted in seconds). | Budget by candidates, or cache and label truncation. | deferred: not attempted in this round (listed for later) |
| W1 | web | At 375 px the home page is 488 px wide and the lab 509 px: the 16-cell grid, the case selects and the nav overflow. | Scroll the grid inside its box, cap widths. | fixed: test `test_no_horizontal_overflow_on_a_phone` |
| W2 | web | A failing `/api/trial` silently plays the recorded seed-0 trial ignoring seed, surprises and an edited case, and the badge says the server is not running. | Say so, and refuse when the request cannot be honoured. | fixed: a failed trial request is reported; the badge says SAVED TRIAL when seed 0 falls back |
| R1 | repro | `results/oracle/*.json` store wall-clock seconds, so re-running changes 4 of 5 files and `render_docs --check` then fails. | Keep timings out of the hashed files. | deferred: a fix changes the certified oracle files and their pinned hashes; documented in PROVENANCE instead |
| R2 | repro | `python -m courtroom export` does not reproduce the committed `bundle.js` (7 strategies, extra fields); all 160 digests identical. | Document it, or make export non-destructive by default. | deferred: needs your decision (regenerating the shipped bundle). The digests are identical either way |
| D1 | docs | README says 483 tests; the suite has 899. | Correct. | fixed |
| D3 | docs | README says six pairings per case in the hosted demo; the bundle has 16. | Correct. | fixed |
| D4 | docs | README "The web app" describes six tabs, a Technical-details switch and a theme switch that do not exist. | Rewrite to the real layout. | fixed |
| D5 | docs | README claims no network dependencies and self-hosted fonts; the pages load Google Fonts, cdnjs and jsdelivr. | Correct. | fixed |
| D6 | docs | Same style-table error as A1 (also `docs/DESIGN.md`). | Correct. | fixed |
| D7 | docs | README says the defense can move for a directed verdict when a point has no evidence; that is the judge's own DV-2, and the motion is granted only below log-odds 0. | Correct. | fixed |
| T1 | tests | Changing `RELEVANCE_FLOOR` from 1/20 to 1/10 survives the suite. | Boundary test. | fixed: tests/test_judge_boundaries.py |
| T2 | tests | Changing the directed-verdict check `lo < 0` to `<=` survives. | Boundary test. | fixed |
| T3 | tests | Forcing a civil win to read GUILTY instead of LIABLE survives. | Test the wording. | fixed |
| T4 | tests | Flipping the same-fact tie-break and the weakest-element order survives. | Tie-break tests. | fixed |
| T5 | tests | Dropping the column best-response check in `verify_equilibrium`, treating weak dominance as strict, and weak-dominance elimination in `iesds` all survive. | Targeted tests. | fixed: tests/test_nash_edges.py |

### P2

| Id | Area | Finding and evidence | Proposed fix | Status |
|---|---|---|---|---|
| E2 | engine | `Oracle.log_odds` returns the shared cache dict and agents see the global case supports: a hostile agent could change the library. Built-in agents do not. | Return copies. | fixed |
| E3 | engine | `budget=inf` passes validation, the trial runs, then JSON serialisation fails. | Reject non-finite floats. | fixed |
| A3 | agents | `/api/game` accepts `lookahead` with no "exhibition, not certified" label. | Label it or refuse. | fixed: 422, exhibition style cannot enter a payoff table |
| G1 | theory | `support_enumeration` tries equal-size supports only; degenerate games can lose equilibria (258 of 1500 random tie games; none of 800 generic). Certified results are not affected. | Document, or extend the enumeration. | deferred: certified results are not affected; needs a decision on a different enumeration |
| G2 | theory | The `degenerate` flag is "even number of equilibria", which is unreliable. | Detect ties directly (changes a serialised flag, so regenerate and log in DEVIATIONS). | deferred: changes a serialised flag in results/, so it needs a regeneration and a DEVIATIONS entry |
| G3 | theory | Python and `lab-math.js` differ on degenerate games. | Align them. | deferred: only differs on degenerate games |
| G4 | theory | Bootstrap crashes on `n_resamples=0` or no seeds; asymmetric interval below 40 resamples. | Guard. | fixed |
| API3 | api | Deeply nested JSON gives a 500 with a RecursionError. | Size cap plus catch. | fixed |
| API4 | api | No request body size limit (a 100 MB body was fully parsed). | 413 over a cap. | fixed |
| API5 | api | `/api/game` returns 500 for an unknown or malformed strategy name. | Same validator as `/api/trial`. | fixed |
| W3 | web | Arrow keys on the music slider also step the trial. | Ignore keys from inputs. | fixed |
| W4 | web | The courtroom is `aria-modal` with no focus trap (read from the code). | Make the page behind inert. | deferred: read from the code, not reproduced |
| S1 | security | Eight CDN scripts have no integrity check. | SRI or vendor. | deferred: needs hashes fetched from the CDNs; the page works without those scripts |
| S2 | security | No Host check on the API; paid LLM routes are open if the server is exposed or rebound. | Trusted-host middleware, refuse non-loopback with a key. | fixed: trusted-host middleware |
| S3 | security | No request body limit (same as API4). | See API4. | fixed: 413 over 1 MB |
| S4 | security | The narrator's "adds no facts" check is weaker than `docs/LLM_ROLE.md` says (digits inside larger numbers pass; lowercase facts pass). | Tighten, soften the doc. | deferred: output only decorates dialogue, never a verdict; the doc wording should be softened |
| R3 | repro | The 3D demo needs the internet for three.js, GSAP and fonts. | State it; vendor if time allows. | deferred: documented in README (CDN use); vendoring is not done |
| D8 | docs | README helix mix 40%/91% is the 30-seed bundle value; 100 seeds give 39%/87%. | Say which. | rejected: no doc at HEAD contains those shares |
| D9 | docs | `node --check courtroom/viz/web/*.js` checks only the first file. | Loop. | fixed |
| D10 | docs | PROVENANCE uses `--count 400`; the stored file has 395. | Correct. | fixed: wording explains 400 requested, 395 measured |
| D11 | docs | Lab hero "Everything is live / every number comes from real trials". | Reword. | fixed |
| T6 | tests | The alpha-beta ordering sign flip survives. | Node-count test. | deferred |
| T7 | tests | Pruning conditions in `lookahead.py` are not shown to prune. | Node-count test. | deferred |
| T8 | tests | `run`, `game`, `oracle`, `tournament`, `stress`, `export` have no test. | Smoke tests. | fixed: tests/test_cli_smoke.py (run, game, stress, tournament) |

### P3 (listed; fixed only where trivial)

| Id | Finding | Status |
|---|---|---|
| E4 | `verify_chain` accepts empty and truncated chains. | deferred: not attempted in this round (listed for later) |
| E5 | `docs/DESIGN.md` states the corroboration count wrongly. | deferred: not attempted in this round (listed for later) |
| E6 | `generate_case(n_elements=0)` raises a raw ValueError. | deferred: not attempted in this round (listed for later) |
| A4 | Smart's blurb is broader than the behaviour. | deferred: not attempted in this round (listed for later) |
| A5 | The unknown-strategy error omits lookahead and llm. | deferred: not attempted in this round (listed for later) |
| G5 | The alpha-beta "cutoffs" counter includes breaks that prune nothing (354 reported against 185 real for broken-bike); fixing it changes `results/tree_search.json`. | deferred: not attempted in this round (listed for later) |
| G6 | `find_classic` note range is wrong when a generated case has no evidence. | deferred: not attempted in this round (listed for later) |
| G7 | Pareto efficiency considers pure cells only; undocumented. | deferred: not attempted in this round (listed for later) |
| API6 | Odd case-id handling (`gen-1_0` resolves to `gen-10`). | deferred: not attempted in this round (listed for later) |
| API7 | Two CLI messages (`run --seed -1`, `game --seeds 0`). | deferred: not attempted in this round (listed for later) |
| W5 | The lab is blank with no message when `bundle.js` is missing. | deferred: not attempted in this round (listed for later) |
| W6 | Lab "Run fresh trials" has no timeout and concurrent runs share one status line. | deferred: not attempted in this round (listed for later) |
| S5 | `_backup/` and `FINAL_PLAN.md` are untracked but not ignored; no `.vercelignore`. | deferred: not attempted in this round (listed for later) |
| S6 | Personal e-mail addresses in commit metadata. | deferred: not attempted in this round (listed for later) |
| S7 | Unpinned dependencies, no lockfile. | deferred: not attempted in this round (listed for later) |
| R4 | A plain (non-editable) install omits voices and fonts. | deferred: not attempted in this round (listed for later) |
| R5 | The voice recording steps need external model files. | deferred: not attempted in this round (listed for later) |
| D12 | "Passes with no network" omits the Chromium install for the UI tests. | fixed (PROVENANCE) |
| D13 | DEVIATIONS D3 wording. | deferred: not attempted in this round (listed for later) |
| D14 | `docs/DESIGN.md` names modules that do not exist. | deferred: not attempted in this round (listed for later) |
| D15 | README layout and library tables are incomplete. | deferred: not attempted in this round (listed for later) |
| T9 | Some endpoints have no direct test. | deferred: not attempted in this round (listed for later) |
| T10 | Some assertions are weak. | deferred: not attempted in this round (listed for later) |
| T11 | `live_server` has a port race and hides a failed start. | fixed |
| T12 | Random-order and coverage tools were not run. | deferred: not attempted in this round (listed for later) |

## Counts

Found 70. Fixed 33, deferred 36, rejected 1. By severity (fixed / deferred / rejected): P0 1 / 0 / 0; P1 16 / 4 / 0; P2 14 / 9 / 1; P3 2 / 23 / 0. "Fixed" for API1 means a cap on concurrent heavy jobs, not a per-request time limit. Commits: one per fix or per closely related group, each naming its ids.

## Not confirmed by any reviewer (not counted)

Possible `libm` differences in `exp` flipping a sixth-decimal rounding in hashed events; an agent that never returns would hang a trial (no per-agent
timeout); very large hostile inline cases (100 + 100 items) ran for minutes; the first "Run fresh trials" sweep in the lab reported every trial
failed once and did not reproduce; the full demo flow to the verdict, a hung `/api` on the hosted site, and the lab tables at 375 px were not
examined by the web reviewer and are covered by the demo walkthrough in Phase 3.
