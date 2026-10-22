# SUPERSEDED: the analysis as it stood before alternating turns

> **This is an archived copy, not current results.** It is the `RESULTS.md` written against the
> earlier trial order, in which the prosecution presented its whole case before the defense. The
> engine was then changed to alternating turns (deviation D5, requested separately from the LLM
> work), which made these figures describe a game the code no longer plays. The current analysis is
> [`RESULTS.md`](../../RESULTS.md).
>
> It is kept so the earlier numbers stay on record rather than silently disappearing. What it
> cannot do is be reproduced: `results/payoffs.json`, `bootstrap.json` and `sensitivity.json` are
> gitignored regenerable output and were overwritten when the analysis was rerun, and the engine
> that produced them was never committed on its own. Only this write-up survives, recovered from
> git history (commit `99c4439`).
>
> The LLM layer did not cause the change. Commit `e294bff`, which adds it, touches no analysis code
> and no analysis result file.

---

> **STALE — regenerate before use.** Every figure below was measured *before* the trial order
> changed from "prosecution presents in full, then the defense" to alternating turns
> (deviation D5 in [`DEVIATIONS.md`](DEVIATIONS.md)). The equilibria, bootstrap stabilities and
> sweep outcomes here describe the earlier game and no longer match the code. Regenerate with
> `python -m courtroom analysis --out results --workers 4` (about four minutes, no API calls)
> and rewrite this file from the output before quoting any of it in the report.
>
> The test and fuzz counts in section 1 are likewise from that run; the suite is now 544 tests.

Everything below is reproducible from a clean checkout:

```bash
pip install -e ".[dev]"
python -m courtroom analysis --out results --workers 4
```

That writes `results/payoffs.json`, `results/bootstrap.json` and `results/sensitivity.json`.
It takes about four minutes on four workers. Figures here come from those three files.

Configuration: **4×4 game** over Aggressive, Conservative, Adaptive and Mixed(0.5), **200 common
random seeds per cell** (the same seeds in every cell, so noise cancels between cells), bootstrap
**200 resamples**, sweep at **60 seeds** per cell. Chaos is a fuzzing agent and never enters the
matrix. Every equilibrium below passed the independent best-response verifier.

---

## 1. Verification

| Check | Command | Result |
|---|---|---|
| Test suite | `python -m pytest` | **495 passed, 0 failed** |
| Fuzz | `python -m courtroom stress --cases 100` | 2,500 trials, **0 crashes, 0 invariant failures** |
| Replay determinism | `python -m courtroom verify` | 250/250 replays bit-identical; **14/14** case × pairing combinations give identical digests and valid hash chains |

The suite contains **84 test functions**, which `@pytest.mark.parametrize` expands into the **495
test cases** pytest reports. Both numbers describe the same suite; 495 is what the tool prints.
(It was 483 before this round of work; 12 tests were added for the new analysis code.)

Fuzz verdict mix over 2,500 generated cases: 1,318 directed acquittal · 476 liable · 323 not guilty
· 303 not liable · 80 guilty. The generator produces weak cases — **52.7% end at the directed-verdict
review and only 3.2% reach a conviction** — so generated cases are suitable for robustness fuzzing
but not for payoff analysis. All analysis below uses the seven hand-written library cases.

---

## 2. Payoff matrices and equilibria

| Case | Type | Label | Equilibria | Dominance | Verified |
|---|---|---|---|---|---|
| `helix-espionage` | Criminal | **mixed** | 1 | none | ✓ |
| `aurora-defi` | Criminal | pure | 2 | Conservative strictly dominant (prosecution) | ✓ |
| `kestrel-av` | Civil | **dominance-solvable** | 1 | Conservative strictly dominant, both sides | ✓ |
| `edge-empty-docket` | Criminal | pure | 16 | none (all profiles tie) | ✓ |
| `edge-mutual-exclusion` | Civil | pure | 4 | none | ✓ |
| `edge-poisoned-tree` | Criminal | pure | 4 | Conservative strictly dominant (prosecution) | ✓ |
| `edge-defense-only` | Criminal | pure | 16 | none (all profiles tie) | ✓ |

**The flagship case behaves as the proposal hoped.** `helix-espionage` has **no pure equilibrium and
no dominant strategy for either side**: optimal play requires randomisation. The unique mixed
equilibrium, in exact rationals, is

- prosecution: Conservative **1413/3989** (≈35.4%), Adaptive **2576/3989** (≈64.6%), Aggressive 0, Mixed 0
- defense: Aggressive **12/257** (≈4.7%), Adaptive **245/257** (≈95.3%), Conservative 0, Mixed 0

**Reported plainly, not hidden:** `kestrel-av` is **trivial** — iterated elimination of strictly
dominated strategies leaves exactly one profile, so there is no strategic content. `aurora-defi`,
`edge-mutual-exclusion`, `edge-poisoned-tree`, `edge-empty-docket` and `edge-defense-only` are
**degenerate**: they return an even number of equilibria, which means ties and possibly a continuum.
The two 16-equilibrium cases are the ones where every profile ties, exactly as designed.

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

Every case's label is stable under resampling. Note this is honest only because the seed count is
high: at 20 seeds `helix-espionage` reports **60%** stability and flips between *mixed* and
*dominance-solvable*. The 200-seed requirement in the proposal is doing real work — a 20-seed
matrix would have supported a confident claim that is simply an artefact of the seeds.

---

## 4. Sensitivity sweep

Each parameter group perturbed by ±25%, plus the beyond-reasonable-doubt standard swept across
80–95% probability. "Changed" means the equilibrium label moved.

| Case | Label survives | Breaks under |
|---|---|---|
| `edge-empty-docket` | **every variation** | — |
| `edge-poisoned-tree` | **every variation** | — |
| `edge-defense-only` | **every variation** | — |
| `helix-espionage` | 11 of 14 | `LLR_SCALE −25%`, `standards +25%`, **BRD at 95%** |
| `aurora-defi` | 12 of 14 | `PRIOR_DEFECT_RATE −25%`, `costs +25%` |
| `kestrel-av` | 13 of 14 | `LLR_SCALE +25%` |
| `edge-mutual-exclusion` | 13 of 14 | `PRIOR_DEFECT_RATE −25%` |

**What survives:** the three structural edge fixtures are completely parameter-independent — their
outcomes follow from the rules (DV-2, waiver, exact cancellation), not from any tuned constant.
That is the strongest robustness claim in this project.

**What is parameter-dependent:** the four substantive cases. Each one's label depends on at least
one constant, and the report says which. No conclusion about them should be stated without the
parameter it rests on.

### The standard of proof, specifically

The headline question — *is the 90% bar justified, or just picked?* — has a measured answer:

| Beyond-reasonable-doubt bar | `helix-espionage` label | Prosecution win rate |
|---|---|---|
| 80% | mixed | 0.352 |
| 85% | mixed | 0.301 |
| **90% (the shipped value, 11/5)** | **mixed** | **0.289** |
| 95% | **collapses** | 0.000 |

The flagship case's mixed equilibrium is **stable anywhere from 80% to 90%** and collapses at 95%,
where the prosecution can no longer win at all. The shipped value sits inside the stable band, not
on its edge. The bar itself is a policy choice, not a measurement: 90% corresponds to the
Blackstone 10:1 error-cost ratio (convict only when P(guilt) > 10/11 ≈ 91%), and the civil
preponderance bar of 50% is the 1:1 ratio. The slider in the **Judge** tab lets an examiner move
the bar and watch the loaded trial be re-decided.

---

## 5. Two changes made before freezing

Both are logged with reasons in [`DEVIATIONS.md`](DEVIATIONS.md).

1. **Late disclosure is observed exactly**, not through the noisy channel. A party knows whether it
   received an exhibit before trial; that is a fact about the record, not an inference. The other
   four noisy grounds are unchanged.
2. **No profile offers evidence that is irrelevant as a matter of law.** Aggressive was presenting a
   `|support| = 0.02` exhibit (below the `1/20` relevance floor) in **28 of 40 trials**, costing 1.5
   budget for ~0.02 log-odds. Diagnosed to ranking, not the case file: `_value_presentation` returns
   raw gain for non-adaptive profiles and never subtracts `presentation_cost`, which is why only the
   EV profile correctly refused. No strategy profile constant was changed.

### Known consequence: `kestrel-av` lost its designed structure

Change 1 has a large, honest side effect, isolated by re-running the case under both perception
models:

| | Label | Plaintiff win rate (agg/agg, agg/cons, cons/agg, cons/cons) |
|---|---|---|
| Before (noisy late disclosure) | dominance-solvable, **Aggressive** dominant | 0.56, 1.00, 0.00, 0.00 |
| After (observable) | dominance-solvable, **Conservative** dominant | **0.00, 0.00, 0.00, 0.00** |

`P-BUGS` is the plaintiff's only support for the `defect` element and is undisclosed. Once late
disclosure is certain to be caught, it is always excluded, the element can never be proven, and the
conjunctive test means the plaintiff cannot win under any pairing. The README's old "arms race,
aggression strictly dominant for the plaintiff" description no longer holds and has been corrected.

**This was not retuned.** Editing a case file to restore a result after measuring it is
result-driven case design, and the proposal permits retuning only "within documented bounds" as a
team decision. The one-line change that would restore a contestable case, if the team wants it, is
setting `P-BUGS` to `disclosed=True` in `courtroom/cases/library.py`; a second disclosed exhibit
supporting `defect` would preserve the gamble instead of removing it. Either way the analysis must
be re-run and this file regenerated.

---

## 6. A bug found in the sweep itself

The first sweep run reported **zero label changes and zero win-rate movement across all 14
variations** — a result that reads as "perfectly robust" and was in fact a defect. `estimate_payoffs`
was being given `workers=4`, and a `ProcessPoolExecutor` child re-imports `courtroom.*` from
scratch, so the constants patched in the parent never reached the trials. Every variation silently
re-measured the baseline.

The fix pins the patched runs to a single process. `test_sweep_variations_actually_bite` now asserts
that at least one variation moves the win rate, so a sweep that stops biting fails the suite rather
than returning a reassuring table of zeros.

This is worth stating in the report: *no movement anywhere* is indistinguishable from *a broken
measurement*, and should be treated as a red flag rather than a result.

---

## 7. What is still open

- **`kestrel-av` needs a team decision** — publish as trivial, or retune within documented bounds (§5).
- **Non-adaptive ranking is cost-blind.** Aggressive and Conservative rank by raw log-odds gain and
  ignore `presentation_cost`; only Adaptive weighs it. Fixing it properly means recalibrating
  `min_gain`, which redefines the strategy profiles the proposal specifies, so it was left alone and
  flagged in `DEVIATIONS.md`.
- **A careful lawyer never objects on a guessed flaw at accuracy 0.65.** Its posterior after a red
  flag is 0.567, below its 0.70 objection threshold, so in `helix-espionage` it only ever objects on
  the two observable grounds. This is visible in the Judge tab's catch-probability table and
  explains much of the game's structure. It is a consequence of the published constants, not a bug,
  but it deserves a line in the report.
- **Replicator dynamics** are computed and plotted but not analysed here.
