# Provenance: how to check our claims yourself

Everything below is something you can re-run. Each command says what a correct result looks like. Where a number below
was measured on one machine, the machine is named. Where a claim cannot be reproduced from a clean checkout, it says so.

Measured on the `calibration-sweep` branch (after `afba8fc`), on an Apple M3 Pro (18 GB, Python 3.14.7,
4 worker processes). Needs Python 3.11 or newer.

```bash
git clone https://github.com/BinaryCoder3012/AI_Project.git && cd AI_Project
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

---

## 1. Checks that take a few minutes

| Claim | Command | A correct result |
|---|---|---|
| The same case, seeds and strategies always give the same verdict, event for event | `python -m courtroom verify` | Two identical digests, `bit-identical results: YES   hash chain valid: YES` |
| The test suite passes | `python -m pytest` | `1019 passed` (about 90 s) |
| 42 pinned trials still hash to the digests recorded before the later features were built | `python -m pytest tests/test_golden.py` | 42 digests plus one size check pass. The file is `tests/golden/digests.json`; only the aurora and kestrel entries were ever regenerated, and only for a documented case change (D14) |
| The engine survives random and illegal play | `python -m courtroom stress --cases 100` | `"trials": 2500`, `"crashes": 0`, `"invariant_failures": 0`, `"failures": []`, 250 deterministic replays |
| The judge and every core package import nothing from the language-model layer | `python -m pytest tests -k "language_model_layer or only_reachable or reaches_nothing or do_not_import_the_llm"` | 5 pass; each parses the source of the core packages (`contracts judge procedure agents engine cases gametheory`) for an import of `courtroom.llm` |
| No test touches the network | `grep -rn "allow_network\|urlopen" tests/ \| head` | tests stub the HTTP layer or pass `allow_network=False`; `tests/test_ollama.py` and `tests/test_explainer.py` also replace `urlopen` with a function that raises, so a real call would fail loudly |

## 2. Regenerate the certified results (about 14 minutes)

The matrices, bootstrap and sweep are exact-rational arithmetic over seeded trials, so a regeneration is **byte-identical**.

```bash
python -m courtroom analysis --out /tmp/prov/analysis --workers 4
for f in payoffs bootstrap sensitivity; do cmp results/$f.json /tmp/prov/analysis/$f.json && echo "$f identical"; done
```

The files are tracked in git (`results/payoffs.json`, `bootstrap.json`, `sensitivity.json`), so a fresh clone has them to compare against. Regenerating on the commit below gave byte-identical files. Their SHA-256 hashes at this commit:

```
91175dec19d4c5dd4530239270a27385d1c7250265a38caca2f7f6b325fb1608  results/payoffs.json
cf27c8909a13bfcd85244c0163afa7f6f9020af5ba38dacb5284b8f4a28b5642  results/bootstrap.json
b04b459d2f5b9265ee23dd0c1fc33a91424bfb9492aa064e34847aeb0cbec933  results/sensitivity.json
```

The calibration that chose the adverse-event rates is separate and also reproducible (about 22 minutes plus 8):

```bash
python scripts/calibration_sweep.py --out /tmp/events.jsonl --workers 4
python scripts/calibration_cases.py --no-show 0.10 --missing-certificate 0.15 --hostile 0.10 --out /tmp/cases.jsonl
python scripts/render_calibration.py          # the tables of docs/CALIBRATION_SWEEP.md
```

Compare each with `results/calibration/`; the figures are exact for the same seeds and code. `tests/test_shipped_events.py` checks that the shipped rates are the
ones that data select.

Then the static web bundle (about 6 minutes), which embeds the trials, games, proof-bar ladder, case briefs and verdict accounts:

```bash
python -m courtroom export --out /tmp/prov/export
cmp /tmp/prov/export/bundle.js courtroom/viz/web/data/bundle.js && echo identical
```

Byte-identical at this commit (`cd3f2642...011a`). A previous version of this file was **not** identical: it had been patched by
hand, and was missing a field added to the trial record. It was regenerated with the command above as part of writing this page.

## 3. Replay the language-model exhibition from the cache (seconds, no key, no network)

```bash
python -m courtroom export-exhibition --out /tmp/prov/exh
cmp /tmp/prov/exh/exhibition.js courtroom/viz/web/data/exhibition.js && echo identical
```

Expected output: `replayed 40 trials from the cache, 4 cache misses, 0 mismatches against the live run`. Byte-identical at this
commit (`3f727d3f...9f83`). This replays Gemini's committed responses (`courtroom/llm/cache/responses.json`, keyed by a SHA-256 of
prompt, system text, model, temperature and token limit) through the real engine with the network disabled.

**What this does and does not prove.** It proves the 40 trials are exactly what the engine produces from those recorded
answers. It does **not** prove Gemini would give the same answers again: a cold cache on another machine calls the provider, and
providers do not guarantee identical output over time. That is why exhibition results are excluded from every certified number.
The 4 cache misses were requests rate-limited when recorded; they were re-asked, none fell back to another policy.

Run counts, for the record (`LLM_EXHIBITION.md`): 191 real API calls in the recorded run, 464 cache hits, 363 distinct cached
responses, 0.0% fallback, estimated cost $0.2041 **for that run only** (a cold reproduction needs about 363 calls).

## 4. The evidence behind the headline claims

### 4.1 The test suite grew with the work

Counted by `pytest --collect-only` at each commit (a throwaway checkout per commit):

| Commit | What it added | Tests collected | Test functions | Deviations logged |
|---|---|---|---|---|
| `e5e97b2` | the project as first received | 483 | 84 | no `DEVIATIONS.md` |
| `02b00f6` | alternating turns, bootstrap, sensitivity sweep | 498 | 99 | D1 to D8 |
| `e294bff` | optional Gemini layer | 544 | 142 | D1 to D8 |
| `70b2cc5` | analysis and exhibition in the static bundle | 600 | 157 | D1 to D8 |
| `2ce9e17` | proof bar as a parameter | 649 | 186 | D1 to D9 |
| `e1a8ed3` | evidence injection | 686 | 217 | D1 to D10 |
| `16d2552` | cache-only LLM opponent mode | 693 | 224 | D1 to D11 |
| `df8f081` | top-4-facts cap | 705 | 236 | D1 to D12 |
| `05b8809` | witness examination | 768 | 269 | D1 to D13 |
| `1a4de55` | case rebalance | 773 | 274 | D1 to D14 |
| `b58b485` | seeded adverse events | 827 | 290 | D1 to D15 |
| `b2c1a70` | pushed adverse events | 855 | 307 | D1 to D15 |
| `c12a7ca` | case briefs | 892 | 318 | D1 to D16 |
| `9cfad25` | Ollama provider | 914 | 337 | D1 to D17 |
| `ff0ee71` | verdict explainer | 932 | 353 | D1 to D18 |
| `afba8fc` | this page and its hash test | 935 | 356 | D1 to D18 |
| this change | calibration sweep, events shipped on, instructor note | 1019 | 389 | D1 to D19 |

The 483 matches what the repository's own README claimed on first receipt. To redo a row: `git worktree add /tmp/wt <commit>`, then
`cd /tmp/wt && PYTHONPATH=. python -m pytest --collect-only -q`, and add up the per-file counts. Collected is not passed: the pass
count at each commit was recorded when it was made (e.g. 544 passed in `RESULTS.md` at `e294bff`).

### 4.2 Deviations from the proposal: 18, each with a reason

`DEVIATIONS.md` lists every intentional divergence from the submitted proposal, with the reason and, where one exists, the
measurement. In short:

D1 late disclosure observable · D2 relevance guard · D3 `kestrel-av` trivial after D1 (later superseded by D14) · D4 sweep is
single-process · D5 alternating turns · D6 generator fix · D7 rebuttal can still add support (**known, not fixed**) · D8 optional
Gemini layer · D9 proof bar as a parameter · D10 evidence injection · D11 cache-only exhibition mode · D12 top-4-facts cap ·
D13 witness examination · D14 case rebalance (**result-driven, said so**) · D15 adverse events (seeded and pushed) · D16 case
brief · D17 Ollama · D18 verdict explainer · D19 adverse events ship on at measured rates, aurora and kestrel left as they were.

### 4.3 The top-4-facts cap (D12)

The proposal (Sec. 6) says the score uses "the four facts with the largest |v| per side"; the code did not enforce it.

| Measurement | Result |
|---|---|
| 875 library trials (every library case, many pairings and seeds), cap on against cap off | **0** digest changes, **0** verdict changes |
| 1,500 generated cases | **16** digest changes, **0** verdict changes |
| One side's good exhibits, log-odds at 4 / 6 / 8 exhibits | before 10.04 / 16.10 / 21.98, after 10.04 / 10.40 / 10.49 |

Check: `python -m pytest tests/test_fact_cap.py`. It also pins that setting `rules.MAX_FACTS_PER_SIDE = None` restores the old
judge, and that no library trial changes either way.

### 4.4 The sensitivity sweeps and the proof-bar ladder

`results/sensitivity.json` perturbs each parameter group by 25% and the criminal bar over 80 to 95%; `RESULTS.md` section 4 tables
which case labels survive. Current figures (adverse events on, D19), reproduced by section 2 above:

| Case | Label | Survives | Breaks under |
|---|---|---|---|
| `helix-espionage` | mixed | 11 of 14 | `LLR_SCALE -25%`, `standards +25%`, bar 95% |
| `aurora-defi` | dominance-solvable | 13 of 14 | `PRIOR_DEFECT_RATE -25%` |
| `kestrel-av` | dominance-solvable | 13 of 14 | `sanctions -25%` |
| `edge-mutual-exclusion` | pure | 13 of 14 | `PRIOR_DEFECT_RATE -25%` |
| the other three | pure | 14 of 14 | none |

Bootstrap stability, label / support (200 resamples of 200 seeds): helix 100.0 / 100.0%, aurora 100.0 / 99.0%, kestrel 99.5 / 99.5%, the four others 100 / 100%.

The adverse-event rates themselves are swept in `docs/CALIBRATION_SWEEP.md` (21 settings x 7 cases, `results/calibration/events.jsonl`), and the two
case values that depend on them in `results/calibration/cases.jsonl` (32 values). The finding there: with events on, **no value** of either case parameter makes
`aurora-defi` or `kestrel-av` anything but dominance-solvable, so they were left as they were and documented, not tuned (D19). It also records that
the selection rules are satisfied by the letter but not when only the four real contests are counted. **Neither rebalanced case is a robust design**; D14 and D19 say so.

### 4.5 Measurement bugs we found and fixed (and one we did not)

Listing these is the point: a result that looks perfect is the most suspicious one.

| What was wrong | How it was found | Where it is recorded and pinned |
|---|---|---|
| The sensitivity sweep reported **zero** change under every perturbation: worker processes re-imported the constants, so every variation silently re-measured the baseline | the table of zeros looked too good to be true | `RESULTS.md` section 6; `test_sweep_variations_actually_bite` |
| The exhibition's fallback rate counted turns with a single legal move, reporting 27.1% instead of the true 4.4% | noticed when the rate looked too high | `trivial_decisions` in `courtroom/llm/exhibition.py` |
| A daily-quota error was swallowed by a broad `except` and recorded as a model failure | found while making the exhibition resumable after a daily-quota stop | `QuotaExhausted` is caught inside the agent and counted separately, never as a fallback |
| Replaying an injected trial diverged when the injection point was never reached | found by replaying recorded trials | D10: every requested injection is recorded, applied or not |
| Observable late disclosure made `kestrel-av` unwinnable and trivial | win rate 0.000 in every cell | D3, then D14 |
| The proposal's top-4 cap was never implemented | reading the submitted wording against the code | D12 |
| Adding action types would have changed the chaos agent's random stream and every chaos digest | the bundle freshness test failed | the fuzzer samples a fixed six-action tuple (D13) |
| A test of the hostile-witness factor compared the result to the very constant under test, so it could not fail | a deliberate mutation of the constant left it green | the test now pins `Fraction(1, 4)` literally (D15) |
| The verdict explainer's template said every early ending meant "no accepted exhibit supported it"; that is only one of two rules | a test that checks the rule that fired | D18 |
| The design document estimated regeneration at about 10 minutes; measured 13 min 56 s, and the estimate for a 6x6 space was low by about 3x | timing the real run | `docs/DESIGN_WITNESS_POINTS.md` section 6.3 |
| A string splice into `app.js` deleted three functions the page still called | the page broke | `tests/ui_smoke.cjs` runs the real JavaScript in Node, with mutation tests that must go red |
| The committed bundle files had been patched by hand and were missing a field | `cmp` against a fresh export while writing this page | regenerated (section 2 and 3) |
| The three certified `results/*.json` files were **gitignored**, so they had never been committed; "byte-identical to the committed results" in an earlier version of this page was true only of files on one machine, and two tests that read them would have failed on a clean clone | checking what `git status` did not show after regenerating | `.gitignore` no longer excludes them, they are committed, and the fresh-clone check below now passes |
| In the calibration tables, 99.5% printed as "100" (Python rounds half to even in `:.0f`), hiding a real half-point | a cross-check of the sweep against the certified bootstrap, which said 99.5 | tables print one decimal; `test_shipped_stability_figures_agree_with_the_certified_bootstrap` |
| `HANDOFF.md` said the library "ships with events on" when it did not: the certified library was on the plain rulebook | tracing why the pinned digests would or would not change | corrected in `HANDOFF.md` and `docs/CALIBRATION_SWEEP.md`; D19 makes the statement true |
| Selection rule (b) was satisfied by structural fixtures, so a "qualifying band" existed that said nothing about strategic depth | reading which five cases counted as contested | reported both ways in `docs/CALIBRATION_SWEEP.md`; pinned by `test_no_setting_qualifies_when_only_the_cases_that_are_real_contests_are_counted` |

**Still wrong or unsettled, stated plainly:**

* D7: rebuttal can still add support after the directed-verdict review. Pinned by `test_any_post_dv_rise_is_confined_to_rebuttal`, not fixed.
* `aurora-defi`'s equilibrium label survives only 80.5% of resamples.
* `$0.2041` in `LLM_EXHIBITION.md` is the cost of the 191-call run, not of the 363 responses in the cache.

## 5. What we do not claim

* **No equilibrium result involves a language model.** Gemini and Ollama output is exhibition only, labelled so in the page and in
  every file that carries it, and is excluded from the matrices, bootstrap and sweep.
* **Ollama has not been run against a real server.** The client follows the documented API and is tested against a stub
  (`tests/test_ollama.py`); see `docs/OLLAMA.md`.
* **Nothing here establishes legal accuracy.** `docs/LEGAL_AND_BALANCE_AUDIT.md` lists where the engine diverges from the Indian-procedure
  notes (for example, it excludes illegally obtained evidence, which the notes say Indian law does not).
* **The witness-examination variants have not been solved as games.** The adverse-event rules have: they are now the shipped configuration of four cases, and `results/calibration/` is the sweep over their rates.
* **The rebalanced cases were tuned after measuring**, which D3 had refused to do. D14 records that it was done and why.
