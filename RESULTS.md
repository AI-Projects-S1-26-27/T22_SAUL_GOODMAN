# Results

Reproducible from a clean checkout:

```bash
pip install -e ".[dev]"
python -m courtroom analysis --out results --workers 4
```

That writes `results/payoffs.json`, `results/bootstrap.json` and `results/sensitivity.json` in
about ten minutes on four workers. Every figure here comes from those three files and from
`python -m pytest`, `python -m courtroom stress` and `python -m courtroom verify`.

**These are the certified results.** They are exact rational arithmetic over seeded trials and
reproduce bit-for-bit. Nothing on this page involves a language model; the optional Gemini layer
is reported separately in [`LLM_EXHIBITION.md`](LLM_EXHIBITION.md) and is deliberately excluded
from every number below.

**Adverse events are on.** Since D19 the four library cases with real play (`helix-espionage`, `aurora-defi`,
`kestrel-av`, `edge-poisoned-tree`) ship with seeded adverse events: a witness fails to appear (10% of offers),
a digital record lacks its section 65B certificate (15%), a witness turns hostile (10% of admissions, credibility
x1/4). The three structural fixtures stay on the plain rulebook. The rates were chosen by a measured sweep
(`docs/CALIBRATION_SWEEP.md`). The earlier numbers, without events, are reproducible with `PLAIN_CASES`
(see `PROVENANCE.md`) and are what `docs/archive/` and the earlier sections of `DEVIATIONS.md` describe.

Configuration: the **4×4 game** over Aggressive, Conservative, Adaptive and Mixed(0.5), **200
common random seeds per cell** (the same seeds in every cell, so noise cancels between cells),
bootstrap **200 resamples**, sweep at **60 seeds** per cell. Chaos is a fuzzing agent and never
enters the matrix. Every equilibrium below passed the independent best-response verifier.

Measured against the current engine, in which **the two sides alternate turns** (deviation D5 in
[`DEVIATIONS.md`](DEVIATIONS.md)).

---

## 1. Verification

| Check | Command | Result |
|---|---|---|
| Test suite | `python -m pytest` | **1008 passed, 0 failed** |
| Fuzz | `python -m courtroom stress --cases 100` | 2,500 trials, **0 crashes, 0 invariant failures** |
| Replay determinism | `python -m courtroom verify` | 250/250 replays bit-identical; every case × pairing combination gives identical digests and valid hash chains |

The suite is 378 test functions across 25 files, which `@pytest.mark.parametrize` expands into the **1008 test
cases** pytest reports. 1008 is what the tool prints.

Fuzz verdict mix over 2,500 generated cases: 1,548 directed acquittal · 559 liable · 273 not
guilty · 78 guilty · 42 not liable. The generator produces weak cases — **61.9% end at the
directed-verdict review and only 3.1% reach a conviction** — so generated cases suit robustness
fuzzing but not payoff analysis. All analysis below uses the seven hand-written library cases.

---

## 2. Payoff matrices and equilibria

| Case | Type | Label | Equilibria | Dominance | Verified |
|---|---|---|---|---|---|
| `helix-espionage` | Criminal | **mixed** | 1 | none | ✓ |
| `aurora-defi` | Criminal | **dominance-solvable** | 1 | Conservative dominant, both sides | ✓ |
| `kestrel-av` | Civil | **dominance-solvable** | 1 | Conservative dominant (prosecution) | ✓ |
| `edge-empty-docket` | Criminal | pure | 16 | none (all profiles tie) | ✓ |
| `edge-mutual-exclusion` | Civil | pure | 4 | none | ✓ |
| `edge-poisoned-tree` | Criminal | pure | 4 | Conservative dominant (prosecution) | ✓ |
| `edge-defense-only` | Criminal | pure | 16 | none (all profiles tie) | ✓ |

**The flagship case still behaves as the proposal hoped, with adverse events on.** `helix-espionage` has **no pure
equilibrium and no dominant strategy for either side**: optimal play requires randomisation. The unique mixed
equilibrium, in exact rationals:

- prosecution: Conservative **837/1009** (≈83.0%), Adaptive **172/1009** (≈17.0%), Aggressive 0, Mixed 0
- defense: Conservative **5395/20224** (≈26.7%), Adaptive **14829/20224** (≈73.3%), Aggressive 0, Mixed 0

Turning adverse events on changed the mixture and narrowed the prosecution's win rate across cells from 0 to 100% down to
0 to 68.5%, but not the structure: the same two styles on each side, and the label held in 200/200 resamples.

**`aurora-defi` and `kestrel-av` are dominance-solvable with events on, and no case value fixes that.** In
`aurora-defi` Conservative is dominant for both sides; in `kestrel-av` it is dominant for the prosecution, and the unique
equilibrium is Conservative against Conservative. Without events they had a pure and a mixed equilibrium respectively (`docs/archive/`, D14). Re-running
the case calibration at the shipped event rates found **no** value of the kestrel `P-RECALL` strength (0 to 0.5) or the aurora
defense-evidence scale (0.6 to 1.8) that contests either case, so both were left as they were and are documented as
dominance-solvable rather than tuned (D19). The prosecution still wins about 11 to 23% (aurora) and 17.5 to 42% (kestrel) of
trials: the cases are contested in **outcome**, not in **strategy**. The two 16-equilibrium edge cases are those where every
profile ties, exactly as designed.

---

## 3. Bootstrap stability

Resampling the 200 seeds with replacement, 200 times, and re-solving each resampled game. **Label stability** is the share of
resamples with the same label; **support stability** is the share with the same set of equilibrium supports (which strategies each
side plays), which is stricter:

| Case | Label | Label stability | Support stability |
|---|---|---|---|
| `helix-espionage` | mixed | **100.0%** | 100.0% |
| `aurora-defi` | dominance-solvable | **100.0%** | 99.0% |
| `kestrel-av` | dominance-solvable | **99.5%** | 99.5% |
| `edge-empty-docket` | pure | **100.0%** | 100.0% |
| `edge-mutual-exclusion` | pure | **100.0%** | 100.0% |
| `edge-poisoned-tree` | pure | **100.0%** | 100.0% |
| `edge-defense-only` | pure | **100.0%** | 100.0% |

Both figures come from the same 200 seeds and 200 resamples. Label stability is `results/bootstrap.json`; support stability is
`results/calibration/events.jsonl`, taken from the measurement that matches how each case ships (the `default` setting for the four
cases with events on, `events-off` for the three plain fixtures). The two sources agree on label stability to the last digit for every
case (`test_shipped_stability_figures_agree_with_the_certified_bootstrap`). The lowest figure anywhere is `aurora-defi`'s support
stability, 99.0%.

Every label is stable under resampling, but only because the seed count is high. At 20 seeds `helix-espionage` reported **60%** stability
(before D19) and flipped between *mixed* and *dominance-solvable*. The proposal's 200-seed requirement is doing real work: a 20-seed matrix
would have supported a confident claim that is purely an artefact of the seeds.

---

## 4. Sensitivity sweep

Each parameter group perturbed by ±25%, plus the criminal standard swept across 80–95%.
"Breaks" means the equilibrium label moved. The adverse-event rates themselves are swept separately, in
`docs/CALIBRATION_SWEEP.md`.

| Case | Label survives | Breaks under |
|---|---|---|
| `helix-espionage` | 11 of 14 | `LLR_SCALE −25%`, `standards_of_proof +25%`, **BRD at 95%** |
| `aurora-defi` | 13 of 14 | `PRIOR_DEFECT_RATE −25%` |
| `kestrel-av` | 13 of 14 | `sanctions −25%` |
| `edge-empty-docket` | **every variation** | — |
| `edge-mutual-exclusion` | 13 of 14 | `PRIOR_DEFECT_RATE −25%` |
| `edge-poisoned-tree` | **every variation** | — |
| `edge-defense-only` | **every variation** | — |

**3 of seven cases are completely parameter-independent** (the structural edge fixtures: their outcomes follow from
the rules, not from any tuned constant). The others are parameter-dependent, and the table says exactly which constant each depends on.
No claim about them should be stated without that constant.

### The standard of proof, specifically

The headline question — *is the 90% bar justified, or just picked?* — has a measured answer, and it survived both a change to the trial's
turn order and the switch-on of adverse events:

| Beyond-reasonable-doubt bar | `helix-espionage` label | Prosecution win rate |
|---|---|---|
| 80% | mixed | 0.311 |
| 85% | mixed | 0.247 |
| **90% (the shipped value, 11/5)** | **mixed** | **0.200** |
| 95% | **collapses** | 0.008 |

The flagship case's mixed equilibrium is **stable anywhere from 80% to 90%** and collapses at 95%, where the prosecution can almost never win
(0.8%). The shipped value sits inside the stable band, not on its edge.

The bar itself remains a policy choice, not a measurement: 90% corresponds to the Blackstone 10:1
error-cost ratio (convict only when P(guilt) > 10/11 ≈ 91%), and the civil preponderance bar of
50% is the 1:1 ratio. The slider in the **Judge** tab lets an examiner move the bar and watch the
loaded trial be re-decided.

---

### The whole ladder, not just four points

The sweep above samples the criminal bar at 80, 85, 90 and 95%. The bundle also ships the full
game re-solved at seven bars from 50% to 95%, at the same 200 seeds per cell as the certified
analysis (the case's own bar reuses the certified matrix, so the two agree exactly). It is
produced by `python -m courtroom export`, and the web page reads it rather than recomputing it.

`helix-espionage`:

| Bar | Result | Prosecution plays | Defense plays | Prosecution wins at equilibrium |
|---|---|---|---|---|
| 50% | dominance-solvable | adaptive 100% | aggressive 100% | 27.5% |
| 60% | dominance-solvable | adaptive 100% | aggressive 100% | 26.0% |
| 70% | dominance-solvable | adaptive 100% | aggressive 100% | 11.5% |
| 80% | mixed | conservative 53%, adaptive 47% | adaptive 55%, aggressive 45% | 8.8% |
| 85% | mixed | conservative 84%, adaptive 16% | adaptive 90%, conservative 10% | 4.4% |
| 90% (own) | mixed | conservative 83%, adaptive 17% | adaptive 73%, conservative 27% | 4.9% |
| 95% | dominance-solvable | conservative 100% | conservative 100% | 0.0% |

Read it as a shape rather than a lookup. On this ladder the flagship's mixed equilibrium appears
only at 80%, 85% and 90%. At 50%, 60% and 70% and again at 95% the game has one clear best style
for each side, and at 95% the prosecution cannot win at all. The shipped 90% bar is inside the
mixed band. The ladder has seven rungs, so it cannot say where the band starts between 70% and
80% or where it ends between 90% and 95%; that would take a finer ladder. It also does not
explain *why* the structure changes, only that it does.

Cases whose label changes somewhere on the ladder: `helix-espionage`, `aurora-defi`.
Cases whose label never changes from 50% to 95%: `kestrel-av`, `edge-empty-docket`, `edge-mutual-exclusion`, `edge-poisoned-tree`, `edge-defense-only`.

---

## 5. Changes made before the parameters were frozen

All logged with reasons in [`DEVIATIONS.md`](DEVIATIONS.md): alternating turns and the
redefined directed-verdict trigger (D5), the generator fix for defense evidence that could help
the prosecution (D6), observable late disclosure (D1), and the relevance guard on presentation
(D2). D7 records a pre-existing gap that was **not** fixed: rebuttal can still add support,
contrary to the proposal, and the fix would require changing judge arithmetic.

One measurement is worth repeating here. Checking "does `L_e` ever rise after the directed-verdict
review" across 67 cases × 16 pairings (2,160 element checks):

| | Post-DV rises |
|---|---|
| Original code at `e5e97b2` | **21** |
| After D5 and D6 | **2**, both from rebuttal (D7) |

Alternating turns *reduced* the problem, because most defense evidence is now admitted before the
review rather than after it.

---

## 6. A bug found in the sweep itself

An early sweep reported **zero label changes and zero win-rate movement across every variation** —
a result that reads as "perfectly robust" and was in fact a defect. `estimate_payoffs` was being
given `workers=4`, and a `ProcessPoolExecutor` child re-imports `courtroom.*` from scratch, so the
constants patched in the parent never reached the trials. Every variation silently re-measured the
baseline.

The fix pins patched runs to a single process. `test_sweep_variations_actually_bite` now asserts
that at least one variation moves the win rate, so a sweep that stops biting fails the suite
rather than returning a reassuring table of zeros.

Worth stating in the report: *no movement anywhere* is indistinguishable from *a broken
measurement*, and should be treated as a red flag rather than a result.

---

## 7. What is still open

- **`aurora-defi` and `kestrel-av` are dominance-solvable with adverse events on, and the sweep found no case value that contests them (D19).**
  They were calibrated (D14) on the plain rulebook; re-running the calibration at the shipped event rates showed no value of either
  calibrated parameter that restores a mixed or pure structure with stable labels. They are left as they were and documented, not tuned.
  `docs/CALIBRATION_SWEEP.md` has the tables, and the strict reading in which no setting fully qualifies.
- **Rebuttal can still add support (D7).** Both available fixes are out of bounds: zeroing a
  rebuttal item's support changes judge arithmetic, and banning `PRESENT` in rebuttal changes the
  game again. `test_any_post_dv_rise_is_confined_to_rebuttal` pins the gap so it cannot spread.
- **Non-adaptive ranking is cost-blind.** Aggressive and Conservative rank by raw log-odds gain and
  ignore `presentation_cost`; only Adaptive weighs it. Fixing it means recalibrating `min_gain`,
  which would redefine the strategy profiles the proposal specifies.
- **A careful lawyer never objects on a guessed flaw at accuracy 0.65.** Its posterior after a red
  flag is 0.567, below its own 0.70 threshold, so in `helix-espionage` it only ever objects on the
  two observable grounds. Visible in the Judge tab's catch-probability table; a consequence of the
  published constants, not a bug, but it deserves a line in the report.
- **Replicator dynamics** are computed and plotted but not analysed here.
