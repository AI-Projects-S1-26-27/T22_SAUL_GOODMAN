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
| Test suite | `python -m pytest` | **544 passed, 0 failed** |
| Fuzz | `python -m courtroom stress --cases 100` | 2,500 trials, **0 crashes, 0 invariant failures** |
| Replay determinism | `python -m courtroom verify` | 250/250 replays bit-identical; every case × pairing combination gives identical digests and valid hash chains |

The suite is **142 test functions** across 9 files, which `@pytest.mark.parametrize` expands into
the **544 test cases** pytest reports. Both numbers describe the same suite; 544 is what the tool
prints.

Fuzz verdict mix over 2,500 generated cases: 1,548 directed acquittal · 559 liable · 273 not
guilty · 78 guilty · 42 not liable. The generator produces weak cases — **61.9% end at the
directed-verdict review and only 3.1% reach a conviction** — so generated cases suit robustness
fuzzing but not payoff analysis. All analysis below uses the seven hand-written library cases.

---

## 2. Payoff matrices and equilibria

| Case | Type | Label | Equilibria | Dominance | Verified |
|---|---|---|---|---|---|
| `helix-espionage` | Criminal | **mixed** | 1 | none | ✓ |
| `aurora-defi` | Criminal | pure | 2 | Conservative dominant (prosecution) | ✓ |
| `kestrel-av` | Civil | **dominance-solvable** | 1 | Conservative dominant, both sides | ✓ |
| `edge-empty-docket` | Criminal | pure | 16 | none (all profiles tie) | ✓ |
| `edge-mutual-exclusion` | Civil | pure | 4 | none | ✓ |
| `edge-poisoned-tree` | Criminal | pure | 4 | Conservative dominant (prosecution) | ✓ |
| `edge-defense-only` | Criminal | pure | 16 | none (all profiles tie) | ✓ |

**The flagship case still behaves as the proposal hoped.** `helix-espionage` has **no pure
equilibrium and no dominant strategy for either side**: optimal play requires randomisation. The
unique mixed equilibrium, in exact rationals:

- prosecution: Conservative **711/821** (≈86.6%), Adaptive **110/821** (≈13.4%), Aggressive 0, Mixed 0
- defense: Adaptive **7870/8447** (≈93.2%), Conservative **577/8447** (≈6.8%), Aggressive 0, Mixed 0

Alternating turns changed *which* mixture is optimal but not the structure: the case still
requires randomisation, and the label held in 200/200 resamples.

**Reported plainly, not hidden:** `kestrel-av` is **trivial** — iterated elimination of strictly
dominated strategies leaves exactly one profile, so there is no strategic content. Its cause is
documented as D3 in `DEVIATIONS.md` and was not retuned to make it look better. The two
16-equilibrium edge cases are those where every profile ties, exactly as designed.

---

## 3. Bootstrap stability

Resampling the 200 seeds with replacement, 200 times, and re-solving each resampled game:

| Case | Label | Stability |
|---|---|---|
| `helix-espionage` | mixed | **100.0%** (200/200) |
| `aurora-defi` | pure | **100.0%** |
| `kestrel-av` | dominance-solvable | **100.0%** |
| `edge-empty-docket` | pure | **100.0%** |
| `edge-mutual-exclusion` | pure | **100.0%** |
| `edge-poisoned-tree` | pure | **100.0%** |
| `edge-defense-only` | pure | **100.0%** |

Every label is stable under resampling — but only because the seed count is high. At 20 seeds
`helix-espionage` reports **60%** stability and flips between *mixed* and *dominance-solvable*.
The proposal's 200-seed requirement is doing real work: a 20-seed matrix would have supported a
confident claim that is purely an artefact of the seeds.

---

## 4. Sensitivity sweep

Each parameter group perturbed by ±25%, plus the criminal standard swept across 80–95%.
"Breaks" means the equilibrium label moved.

| Case | Label survives | Breaks under |
|---|---|---|
| `kestrel-av` | **every variation** | — |
| `edge-empty-docket` | **every variation** | — |
| `edge-poisoned-tree` | **every variation** | — |
| `edge-defense-only` | **every variation** | — |
| `aurora-defi` | 13 of 14 | `PRIOR_DEFECT_RATE −25%` |
| `edge-mutual-exclusion` | 13 of 14 | `PRIOR_DEFECT_RATE −25%` |
| `helix-espionage` | 11 of 14 | `LLR_SCALE −25%`, `standards +25%`, **BRD at 95%** |

**Four of seven cases are now completely parameter-independent**, up from three before the turn
order changed. The three structural edge fixtures were always robust — their outcomes follow from
the rules (DV-2, waiver, exact cancellation) rather than from any tuned constant — and
`kestrel-av` joined them.

Three cases remain parameter-dependent, and the table says exactly which constant each depends on.
No claim about them should be stated without that constant.

### The standard of proof, specifically

The headline question — *is the 90% bar justified, or just picked?* — has a measured answer, and
it is the same answer as before the turn order changed:

| Beyond-reasonable-doubt bar | `helix-espionage` label | Prosecution win rate |
|---|---|---|
| 80% | mixed | 0.357 |
| 85% | mixed | 0.296 |
| **90% (the shipped value, 11/5)** | **mixed** | **0.255** |
| 95% | **collapses** | 0.000 |

The flagship case's mixed equilibrium is **stable anywhere from 80% to 90%** and collapses at 95%,
where the prosecution can no longer win at all. The shipped value sits inside the stable band, not
on its edge. **This result survived a change to the trial's turn order**, which is stronger
evidence than a single measurement.

The bar itself remains a policy choice, not a measurement: 90% corresponds to the Blackstone 10:1
error-cost ratio (convict only when P(guilt) > 10/11 ≈ 91%), and the civil preponderance bar of
50% is the 1:1 ratio. The slider in the **Judge** tab lets an examiner move the bar and watch the
loaded trial be re-decided.

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

- **`kestrel-av` needs a team decision** — publish as trivial, or retune within documented bounds
  (D3). It was deliberately not retuned after the fact.
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
