# Calibration sweep: adverse-event parameters, and the cases that depend on them

**Status:** measured, applied in DEVIATIONS D19. Every table below is generated from `results/calibration/*.jsonl` by
`scripts/render_calibration.py`, so the write-up cannot drift from the data, and `tests/test_shipped_events.py` fails if the shipped
configuration stops being the one these data select.

## 1. Summary

| Question | Answer |
|---|---|
| Chosen adverse-event parameters | no-show **10%**, missing certificate **15%**, hostile **10%**, hostile credibility **x1/4**. These are the values that had been guessed; the sweep shows them inside a plateau, and no other tested setting scored better under the rules (two tied on minimum stability) |
| Did a fully qualifying band exist? | **By the letter of rules (a) to (c): yes, 11 of 20 settings qualify.** Counting only the four cases that are real contests (not the three single-rule fixtures): **no setting qualifies**. That second reading is the one this document treats as the finding |
| What was the finding | Adverse events raise payoff variance where it was missing and the stability stays high, but they make `aurora-defi` and `kestrel-av` **dominance-solvable** (Conservative against Conservative). Only `helix-espionage` keeps a mixed equilibrium. Uncertainty flattens strategic depth; nothing tried restores it |
| Case values (`P-RECALL`, aurora defense scale) | **Left as they were.** With events on, no value of either parameter contests its case (every one of the 32 values measured is dominance-solvable). Rule: document, do not tune |
| What shipped | the four cases with real play carry the events at the chosen rates; the three fixtures and the recorded exhibition stay on the plain rulebook |

### A correction to how this was framed

The task and `HANDOFF.md` 3.1 said the library "ships with events on". Before D19 it did not: the certified library (`CASES`) was
on the plain rulebook, and events existed only in opt-in variants (`ADVERSE_CASES`, `results/adverse/`). So the certified results and the
calibration were consistent with each other, and the events-on results were a side analysis. D19 makes events-on the shipped
configuration, which is what this calibration was asked to support. The plain library remains available as `PLAIN_CASES`, and reproduces
all 42 pinned digests recorded before this change.

## 2. Method

* **Strategy space frozen:** Aggressive, Conservative, Adaptive, Mixed(0.5), 4x4, as certified.
* **Per setting, per case:** 16 cells x **200** common seeds, the same seeds and solver as the certified analysis, then **200** bootstrap
  resamples (rng seed 0). Recorded: equilibrium label (pure, mixed, dominance-solvable), the equilibria's supports, **label stability**
  (share of resamples with the same label), **support stability** (share with the same set of supports, which is stricter), each
  strategy's payoff standard deviation in each seat, and the prosecution's win rate per cell.
* **Settings (21):** events off; the default (10 / 15 / 10 / x1/4); each of the four parameters moved alone over 3 to 4 values;
  and all three rates scaled together by 0.5, 1.5, 2 and 3.
* **Cost:** about 55 to 65 seconds per setting on four workers, about 22 minutes for the sweep. Each setting is appended to the file as it is
  measured and a setting already present is skipped, so an interrupted run resumes.
* **Reproduce:** `python scripts/calibration_sweep.py --out /tmp/events.jsonl --workers 4`, then compare with `results/calibration/events.jsonl`.
  The case calibration of section 5 is `python scripts/calibration_cases.py --no-show 0.10 --missing-certificate 0.15 --hostile 0.10`.
* **Check on the method:** for the shipped configuration, the sweep's label stability equals the certified bootstrap's for all seven cases to
  the last digit (`test_shipped_stability_figures_agree_with_the_certified_bootstrap`), so these are one measurement, not two.

## 3. The sweep

Each cell reads: label (M mixed, P pure, D dominance-solvable), then label stability / support stability in percent.
(a), (b), (c) are the selection rules of section 4. "min stab." is the lowest of all 14 stability figures at that setting.

| Setting | helix | aurora | kestrel | empty | mutual | poison | defonly | (a) | (b) | (c) | min stab. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| events-off | M 100.0/94.0 | P 80.5/80.5 | M 98.0/76.5 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | - | - | - | - |
| default | M 100.0/100.0 | D 100.0/99.0 | D 99.5/99.5 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (5) | yes | 0.990 |
| no_show=0.0 | M 100.0/100.0 | D 100.0/99.0 | D 91.0/91.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (5) | no | 0.910 |
| no_show=0.05 | M 100.0/100.0 | D 100.0/99.0 | D 96.0/96.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (5) | yes | 0.960 |
| no_show=0.2 | M 100.0/100.0 | D 100.0/97.5 | D 99.0/99.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (5) | yes | 0.975 |
| no_show=0.3 | M 100.0/100.0 | D 100.0/96.0 | D 99.5/99.5 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (5) | yes | 0.960 |
| missing_certificate=0.0 | M 100.0/100.0 | P 82.5/81.0 | D 98.0/98.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (9/12) | yes (6) | no | 0.810 |
| missing_certificate=0.05 | M 100.0/100.0 | P 72.5/59.5 | D 99.0/99.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (6) | no | 0.595 |
| missing_certificate=0.25 | M 100.0/100.0 | D 100.0/95.0 | D 99.5/99.5 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (5) | yes | 0.950 |
| missing_certificate=0.35 | M 100.0/99.5 | D 100.0/69.0 | D 99.5/99.5 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (5) | no | 0.690 |
| hostile=0.0 | M 100.0/100.0 | D 100.0/99.0 | D 90.5/90.5 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (5) | no | 0.905 |
| hostile=0.05 | M 100.0/100.0 | D 100.0/99.0 | D 98.5/98.5 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (5) | yes | 0.985 |
| hostile=0.2 | M 100.0/100.0 | D 100.0/98.0 | D 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (5) | yes | 0.980 |
| hostile=0.3 | M 100.0/100.0 | D 100.0/98.5 | D 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (5) | yes | 0.985 |
| hostile_credibility=3/4 | M 100.0/100.0 | D 100.0/99.0 | D 97.0/97.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (5) | yes | 0.970 |
| hostile_credibility=1/2 | M 100.0/100.0 | D 100.0/99.0 | D 99.5/99.5 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (5) | yes | 0.990 |
| hostile_credibility=1/8 | M 100.0/100.0 | D 100.0/99.0 | D 99.5/99.5 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (5) | yes | 0.990 |
| scale x0.5 | M 100.0/98.5 | D 98.5/40.5 | D 71.0/71.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (5) | no | 0.405 |
| scale x1.5 | M 100.0/100.0 | D 100.0/94.5 | D 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (5) | no | 0.945 |
| scale x2.0 | M 100.0/98.5 | D 100.0/69.0 | D 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (5) | no | 0.690 |
| scale x3.0 | D 89.0/88.5 | D 100.0/46.0 | D 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | P 100.0/100.0 | yes (10/12) | yes (4) | no | 0.460 |

### Where each parameter's plateau lies

| Parameter | Fails below | Passes | Fails above | What fails |
|---|---|---|---|---|
| no-show | 0.0 | 0.05 to 0.30 | none tested | at 0 `kestrel-av` stability drops to 91%; at 0.05 it is 96% |
| missing certificate | 0.0 and 0.05 | 0.15 and 0.25 (0.25 is exactly 0.950) | 0.35 | below, `aurora-defi` flips to *pure* and is unstable (82% and 72% label); above, its support stability falls to 69% |
| hostile | 0.0 | 0.05 to 0.30 | none tested | at 0 `kestrel-av` stability drops to 90% |
| hostile credibility | none tested | 1/8, 1/4, 1/2, 3/4 | none tested | nothing: the factor barely matters across this range |
| all rates together | x0.5 | x1 only | x1.5 and above | `aurora-defi`'s support stability: 40% at x0.5, 94.5% at x1.5, 69% at x2, 46% at x3 |

The shipped setting is comfortably inside the single-parameter plateaus but **sits near the upper edge in the joint direction**: scaling every
rate by 1.5 already fails rule (c) by half a point. That is a real narrowness and is listed in section 7.

## 4. Choosing the setting

Rules, applied in order: **(a)** payoff variance rises where it was missing (at least half of the cells with sd below 0.5 with events off, in the
cases events can reach, gain at least 0.5 sd); **(b)** at least 3 of 7 cases are not dominance-solvable; **(c)** every case holds label **and** support
stability of 95% or better; **(d)** among qualifying settings take the highest minimum stability, ties toward more contested cases; **(e)** if none
qualifies, take the best-stability setting that still improves variance and say so.

**By the letter (seven cases):** 11 settings qualify (`default`, `no_show=0.05/0.2/0.3`, `missing_certificate=0.25`, `hostile=0.05/0.2/0.3`,
`hostile_credibility=3/4, 1/2, 1/8`). Rule (d) picks `default`, with minimum stability **0.990** (`aurora-defi`'s support stability), and
`hostile_credibility=1/2` and `1/8` tie it on minimum stability. Ties were broken by the number of contested cases (equal, five) and then by mean stability.

**Why that result should not be trusted at face value.** Rules (a) and (b) are satisfied largely by cases that no setting could have made
dull or interesting:

* Rule (a) passes at **10 of 12** flat cells, but **8 of those 12 are the `edge-mutual-exclusion` fixture**, where an event simply breaks an exact tie and so
  produces a large sd from nothing. Among the real cases, `helix-espionage` Conservative stays at sd 0.08 (it hardly ever offers an exposed exhibit) and
  `edge-poisoned-tree` Conservative stays at 0.00; only `aurora-defi` and `kestrel-av` Conservative really rise.
* Rule (b) counts five cases "contested", but three of them (`edge-empty-docket`, `edge-defense-only`, `edge-mutual-exclusion`) are single-rule fixtures that
  were never strategic, and a fourth (`edge-poisoned-tree`) is a pure game in which the prosecution wins at most 7.5% of any cell. Of the three flagship cases,
  only `helix-espionage` is not dominance-solvable.

**The strict reading** (rules applied to the four cases that are contests at all, meaning the prosecution can win a cell with events off; (b) then needs 3 of 4):

| Setting | (a) flat cells risen | (b) contested of 4 | (c) all stable | min stab. |
|---|---|---|---|---|
| default | yes (2/4) | no (2) | yes | 0.990 |
| no_show=0.0 | yes (2/4) | no (2) | no | 0.910 |
| no_show=0.05 | yes (2/4) | no (2) | yes | 0.960 |
| no_show=0.2 | yes (2/4) | no (2) | yes | 0.975 |
| no_show=0.3 | yes (2/4) | no (2) | yes | 0.960 |
| missing_certificate=0.0 | no (1/4) | yes (3) | no | 0.810 |
| missing_certificate=0.05 | yes (2/4) | yes (3) | no | 0.595 |
| missing_certificate=0.25 | yes (2/4) | no (2) | yes | 0.950 |
| missing_certificate=0.35 | yes (2/4) | no (2) | no | 0.690 |
| hostile=0.0 | yes (2/4) | no (2) | no | 0.905 |
| hostile=0.05 | yes (2/4) | no (2) | yes | 0.985 |
| hostile=0.2 | yes (2/4) | no (2) | yes | 0.980 |
| hostile=0.3 | yes (2/4) | no (2) | yes | 0.985 |
| hostile_credibility=3/4 | yes (2/4) | no (2) | yes | 0.970 |
| hostile_credibility=1/2 | yes (2/4) | no (2) | yes | 0.990 |
| hostile_credibility=1/8 | yes (2/4) | no (2) | yes | 0.990 |
| scale x0.5 | yes (2/4) | no (2) | no | 0.405 |
| scale x1.5 | yes (2/4) | no (2) | no | 0.945 |
| scale x2.0 | yes (2/4) | no (2) | no | 0.690 |
| scale x3.0 | yes (2/4) | no (1) | no | 0.460 |

On the strict reading **no setting satisfies (a), (b) and (c) together**. (b) holds only at missing certificate 0.0 and 0.05, where `aurora-defi` is a
*pure*-label game, and there (c) fails (label stability 82% and 72%). So by rule (e) the honest statement is: **no fully qualifying band exists**; the
setting with the best stability that still improves variance is the default; and the reason is structural, not a matter of tuning. `tests/test_shipped_events.py`
pins this finding. Both readings select the same setting, so nothing about what shipped depends on which one is right.

### Variance, where it was missing

Payoff standard deviation per strategy and seat (utility spans about -9 to +10). Cells that were flat with events off:

| Case, seat, strategy | events-off | default | scale x2.0 |
|---|---|---|---|
| helix pros aggressive | 5.79 | 5.24 | 4.66 |
| helix pros conservative | 0.00 | 0.08 | 0.11 |
| helix pros adaptive | 4.32 | 4.33 | 3.76 |
| helix pros mixed:0.5 | 3.94 | 3.67 | 3.38 |
| helix defe aggressive | 1.96 | 1.60 | 1.31 |
| helix defe conservative | 4.78 | 4.86 | 4.42 |
| helix defe adaptive | 3.20 | 3.00 | 2.58 |
| helix defe mixed:0.5 | 3.88 | 3.61 | 3.25 |
| aurora pros aggressive | 3.51 | 3.76 | 3.25 |
| aurora pros conservative | 0.31 | 3.34 | 3.03 |
| aurora pros adaptive | 3.28 | 4.04 | 3.50 |
| aurora pros mixed:0.5 | 2.44 | 3.88 | 3.68 |
| aurora defe aggressive | 1.80 | 3.40 | 3.20 |
| aurora defe conservative | 2.68 | 3.36 | 2.96 |
| aurora defe adaptive | 2.68 | 3.79 | 3.07 |
| aurora defe mixed:0.5 | 2.48 | 3.53 | 3.15 |
| kestrel pros aggressive | 4.15 | 4.80 | 5.29 |
| kestrel pros conservative | 0.00 | 3.85 | 4.88 |
| kestrel pros adaptive | 3.12 | 4.86 | 5.63 |
| kestrel pros mixed:0.5 | 2.79 | 4.44 | 5.29 |
| kestrel defe aggressive | 1.58 | 3.63 | 4.49 |
| kestrel defe conservative | 4.02 | 4.47 | 4.78 |
| kestrel defe adaptive | 2.16 | 3.79 | 4.61 |
| kestrel defe mixed:0.5 | 3.11 | 4.07 | 4.65 |
| mutual pros aggressive | 0.00 | 3.87 | 4.64 |
| mutual pros conservative | 0.15 | 3.81 | 4.59 |
| mutual pros adaptive | 0.15 | 3.81 | 4.59 |
| mutual pros mixed:0.5 | 0.20 | 3.83 | 4.61 |
| mutual defe aggressive | 0.00 | 3.82 | 4.63 |
| mutual defe conservative | 0.16 | 3.78 | 4.55 |
| mutual defe adaptive | 0.16 | 3.78 | 4.55 |
| mutual defe mixed:0.5 | 0.26 | 3.84 | 4.60 |
| poison pros aggressive | 3.75 | 3.69 | 3.39 |
| poison pros conservative | 0.00 | 0.00 | 0.00 |
| poison pros adaptive | 1.81 | 1.73 | 1.59 |
| poison pros mixed:0.5 | 3.74 | 3.64 | 3.53 |
| poison defe aggressive | 1.51 | 1.45 | 1.34 |
| poison defe conservative | 1.82 | 1.75 | 1.60 |
| poison defe adaptive | 1.82 | 1.75 | 1.61 |
| poison defe mixed:0.5 | 1.64 | 1.64 | 1.46 |

(`mutual` is shown because the sweep ran it with events on; it ships on the plain rulebook.) The events add risk exactly where a strategy
had none: `kestrel-av` Conservative prosecution 0.00 to 3.85, `aurora-defi` Conservative prosecution 0.31 to 3.34, and the defense seats in those two cases gain 1 to 2 points of sd.
`helix-espionage`, already volatile, barely moves, and Conservative there stays flat because it rarely offers anything an event can touch.

## 5. Re-running the case calibration with events on

At the chosen rates, each of the two calibrated values was swept across a wide range (`results/calibration/cases.jsonl`, 200 seeds, 200 resamples).
Bars show the prosecution's win-rate range across the 16 cells (`#` inside the range, `.` below it).

### `kestrel-av`: strength of the clean `defect` exhibit `P-RECALL` (shipped 0.15)

```
   0.0 |......#                                 | 13.5-17.5%   domi 100.0/100.0
  0.05 |.......                                 | 17.5-17.5%   domi 100.0/100.0
 0.075 |.......##########                       | 17.5-42.0%   domi 99.5/99.5
   0.1 |.......##########                       | 17.5-42.0%   domi 99.5/99.5
 0.125 |.......##########                       | 17.5-42.0%   domi 99.5/99.5
  0.15 |.......##########                       | 17.5-42.0%   domi 99.5/99.5
 0.175 |.......###########                      | 17.5-43.0%   domi 99.5/99.5
   0.2 |.......###########                      | 17.5-43.0%   domi 93.5/93.5
 0.225 |.......############                     | 17.5-45.5%   domi 89.5/89.5
  0.25 |.......############                     | 17.5-45.5%   domi 84.0/84.0
 0.275 |............................###         | 70.0-76.5%   domi 100.0/100.0
   0.3 |.............................###        | 71.5-78.5%   domi 100.0/100.0
  0.35 |.............................###        | 72.5-78.5%   domi 100.0/100.0
   0.4 |..............................###       | 73.0-82.0%   domi 100.0/100.0
   0.5 |...............................##       | 77.0-81.5%   domi 100.0/100.0
 0.135 |.......##########                       | 17.5-42.0%   domi 99.5/99.5
 0.165 |.......###########                      | 17.5-43.0%   domi 99.5/99.5
```

| Value | Label | Label stab. | Support stab. | Win rate (min to max) |
|---|---|---|---|---|
| 0.0 | dominance-solvable | 100.0% | 100.0% | 13.5% to 17.5% |
| 0.05 | dominance-solvable | 100.0% | 100.0% | 17.5% to 17.5% |
| 0.075 | dominance-solvable | 99.5% | 99.5% | 17.5% to 42.0% |
| 0.1 | dominance-solvable | 99.5% | 99.5% | 17.5% to 42.0% |
| 0.125 | dominance-solvable | 99.5% | 99.5% | 17.5% to 42.0% |
| 0.15 | dominance-solvable | 99.5% | 99.5% | 17.5% to 42.0% |
| 0.175 | dominance-solvable | 99.5% | 99.5% | 17.5% to 43.0% |
| 0.2 | dominance-solvable | 93.5% | 93.5% | 17.5% to 43.0% |
| 0.225 | dominance-solvable | 89.5% | 89.5% | 17.5% to 45.5% |
| 0.25 | dominance-solvable | 84.0% | 84.0% | 17.5% to 45.5% |
| 0.275 | dominance-solvable | 100.0% | 100.0% | 70.0% to 76.5% |
| 0.3 | dominance-solvable | 100.0% | 100.0% | 71.5% to 78.5% |
| 0.35 | dominance-solvable | 100.0% | 100.0% | 72.5% to 78.5% |
| 0.4 | dominance-solvable | 100.0% | 100.0% | 73.0% to 82.0% |
| 0.5 | dominance-solvable | 100.0% | 100.0% | 77.0% to 81.5% |
| 0.135 | dominance-solvable | 99.5% | 99.5% | 17.5% to 42.0% |
| 0.165 | dominance-solvable | 99.5% | 99.5% | 17.5% to 43.0% |

### `aurora-defi`: scale on the three defense intent exhibits (shipped 1.0)

```
   0.6 |...............#####                    | 36.0-49.0%   domi 93.0/65.5
   0.7 |............######                      | 29.5-45.0%   domi 100.0/99.5
   0.8 |.............####                       | 31.0-42.0%   domi 100.0/99.0
   0.9 |.............####                       | 31.0-42.0%   domi 100.0/99.0
  0.95 |.............#####                      | 31.0-43.0%   domi 100.0/99.0
  0.96 |.....####                               | 11.0-22.5%   domi 100.0/99.0
   1.0 |.....#####                              | 11.0-23.0%   domi 100.0/99.0
  1.05 |.....####                               | 10.5-22.5%   domi 100.0/99.0
   1.1 |.....####                               | 11.0-21.5%   domi 100.0/99.0
  1.15 |.....####                               | 11.0-22.0%   domi 100.0/99.0
   1.2 |.....####                               | 10.5-21.5%   domi 100.0/99.5
   1.3 |.....####                               | 11.0-21.0%   domi 100.0/99.5
   1.4 |...####                                 |  7.0-16.5%   domi 100.0/99.5
   1.6 |..####                                  |  3.5-14.0%   domi 100.0/99.0
   1.8 |..####                                  |  3.5-13.5%   domi 100.0/99.0
```

| Value | Label | Label stab. | Support stab. | Win rate (min to max) |
|---|---|---|---|---|
| 0.6 | dominance-solvable | 93.0% | 65.5% | 36.0% to 49.0% |
| 0.7 | dominance-solvable | 100.0% | 99.5% | 29.5% to 45.0% |
| 0.8 | dominance-solvable | 100.0% | 99.0% | 31.0% to 42.0% |
| 0.9 | dominance-solvable | 100.0% | 99.0% | 31.0% to 42.0% |
| 0.95 | dominance-solvable | 100.0% | 99.0% | 31.0% to 43.0% |
| 0.96 | dominance-solvable | 100.0% | 99.0% | 11.0% to 22.5% |
| 1.0 | dominance-solvable | 100.0% | 99.0% | 11.0% to 23.0% |
| 1.05 | dominance-solvable | 100.0% | 99.0% | 10.5% to 22.5% |
| 1.1 | dominance-solvable | 100.0% | 99.0% | 11.0% to 21.5% |
| 1.15 | dominance-solvable | 100.0% | 99.0% | 11.0% to 22.0% |
| 1.2 | dominance-solvable | 100.0% | 99.5% | 10.5% to 21.5% |
| 1.3 | dominance-solvable | 100.0% | 99.5% | 11.0% to 21.0% |
| 1.4 | dominance-solvable | 100.0% | 99.5% | 7.0% to 16.5% |
| 1.6 | dominance-solvable | 100.0% | 99.0% | 3.5% to 14.0% |
| 1.8 | dominance-solvable | 100.0% | 99.0% | 3.5% to 13.5% |

**No contested band exists.** Every one of the 32 values is **dominance-solvable**. The calibration rule was to choose from the middle of a contested
band and to leave a case as it is, documented as trivial, if none can be found without tuning to taste. None can, so both values were left unchanged.

**Rejected values (instability).** `kestrel-av` at 0.20, 0.225 and 0.25 (label stability 93.5%, 89.5%, 84.0%); `aurora-defi` at 0.6 (support stability 65.5%).

**The +/-10% check.** The rule rejects any value whose +/-10% neighbours flip the label. Both neighbours of each shipped value were measured exactly:
`P-RECALL` 0.135 and 0.165 (around 0.15) and aurora scale 0.9 and 1.1 (around 1.0) are all dominance-solvable, with stability 99.5/99.5% and 100/99% respectively, so
**no value is rejected for flipping a label**. Two **outcome** cliffs do sit near the shipped values, and
the label rule does not see them: `kestrel-av`'s win rate jumps from 17.5 to 45.5% up to 70 to 76.5% between 0.25 and 0.275 (the shipped 0.15 is 0.10 below it);
`aurora-defi`'s falls from 31 to 43% to 11 to 22.5% between 0.95 and 0.96, so the shipped 1.0 is **4% above a win-rate cliff**. Moving aurora to 1.15 would put it in
the middle of that plateau. It was not moved, because doing so is the tuning the rule forbids.

## 6. What this changed

* **Four library cases now ship with adverse events**, at the chosen rates; the three fixtures and the recorded exhibition stay plain.
* **Certified analysis regenerated once.** Labels: `helix-espionage` mixed (unchanged, new mixture), `aurora-defi` pure to **dominance-solvable**,
  `kestrel-av` mixed to **dominance-solvable**, all others unchanged. Prosecution win-rate range: helix 0 to 100% becomes 0 to 68.5%; aurora 0 to 16.5% becomes
  11 to 23%; kestrel 0 to 42% becomes 17.5 to 42%.
* **Exhibition baseline.** The recorded language-model exhibition was played on the plain rulebook, so its deterministic baseline (32 rows, 5 seeds) is kept on
  the plain rulebook too, and was re-derived from a fresh run of the fixed strategies on `PLAIN_CASES`: all 32 rows match
  (`test_the_exhibition_baseline_is_what_the_plain_rulebook_produces_now`). Mixing it with events-on figures would compare unlike games.
* **Strategy tab.** It reads the regenerated bundle; its helix mixture (837/1009, 172/1009) is checked against `results/payoffs.json` by the bundle tests.
* **Pinned digests:** 15 of 42 changed, all in the three cases whose trials events touched, and every one reproduces its old digest on the plain rulebook
  (`test_every_shipped_digest_that_moved_is_a_case_that_ships_with_events`). The plain rulebook still reproduces all 42 old digests.

## 7. Open uncertainties

1. **The rates are still chosen, not observed.** The sweep shows how sensitive the results are to them; it cannot say what they should be. Nothing in the evidence
   fixes 10%, 15% and 10% as realistic.
2. **The plateau is narrow in the joint direction.** All three rates scaled by 1.5 fail rule (c).
3. **Flat strategies stay flat.** Conservative in `helix-espionage` and `edge-poisoned-tree` hardly offers an exhibit an event can touch, so its sd does not move.
4. **`aurora-defi` sits 4% above an outcome cliff** (section 5), and `kestrel-av`'s `P-RECALL` has a second regime above 0.275. Neither affects the label.
5. **`aurora-defi`'s support stability is 99.0%, not 100%**; the margin to the 95% floor is small only in the joint direction above.
6. **Rule (b)'s wording lets fixtures carry it.** If the rule is meant to count genuine contests, no setting qualifies.
7. **The hostile credibility factor is exact but its effect is small** across 1/8 to 3/4; the sweep cannot distinguish them.
8. **Single-seed-set sample.** All figures use seeds 0 to 199; the bootstrap measures resampling noise on those seeds, not a fresh draw.
