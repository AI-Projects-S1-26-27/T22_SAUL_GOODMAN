# Saul Goodman Courtroom: report

CS F407 Agents & Game Theory, demo track. Every number in this report that comes from an experiment sits inside a *generated region*
(between `GENERATED` markers). `scripts/render_docs.py` fills those regions from the certified files in `results/`, and a test fails if
one is stale. Prose outside the regions contains no result numbers.

## 1. The problem

The project simulates a trial. Two lawyer agents (the Accuser and the Defender) each hold a budget and a set of exhibits, and play
moves in turn: offer an exhibit, object to one, challenge a witness, move to end the trial, rest. A **rulebook judge**, not a model,
rules on each objection with a named rule, weighs the exhibits that were accepted, and decides. The game-theory question is the one
every lawyer faces: *attack or play it safe?* Which style is best depends on the style the other side chooses.

The obvious criticism of a project like this is that it is hard-coded: the trials are pre-run, the lawyer styles are four hand-picked
ones, the lines are hand-written and the cases were written by hand to make the point. This report is about answering that with
measurements the examiner can reproduce and, in the running system, drive.

The first thing measured was uncomfortable. In most of the hand-written cases the verdict does not depend on the lawyers at all
(section 6.1). So a seed box alone would not convince anyone: the examiner has to be able to make a verdict *move* and see why.

## 2. The model

**The judge scores a record.** A record is the set of accepted exhibits plus how many times each witness was impeached (and whether a
witness turned hostile). It never depends on the order in which exhibits were offered. All verdict arithmetic uses exact rationals
(`fractions.Fraction`); floats appear only in display fields.

For an accepted exhibit *i*:

- strength: `s_i = reliability_i × credibility_i`, where credibility is the witness's base credibility times `IMPEACHMENT_FACTOR` once
  per successful impeachment, and times `HOSTILE_FACTOR` if the witness turned hostile (exhibits with no witness have credibility 1).
- contradiction discount: `d_i = min(MAX_CONTRADICTION_DISCOUNT, Σ_j β · s_j / (s_i + s_j))` over accepted exhibits *j* that contradict *i*.
- for each legal element *e* that the Accuser must prove, with `support_{i,e}` in [−1, 1]: corroboration factor
  `c_{i,e} = 1 + α · (1 − ½^n)`, where *n* is the number of *other facts* whose accepted exhibits point the same way on *e*.
- weight: `w_{i,e} = support_{i,e} · s_i · (1 − d_i) · c_{i,e}`. Only the strongest accepted exhibit per underlying fact counts.
- element log-odds: `L_e = prior + K · Σ_{counted i} w_{i,e}`.

The verdict is **conjunctive**: the Accuser wins only if *every* element's log-odds reaches the bar for the case's standard of proof
(at the bar for "preponderance", strictly above it). If no accepted exhibit supports an element at all, the case is dismissed early;
if the Defender moves for a directed verdict and some element is below even odds, it is granted.

A lawyer's payoff in one trial is `u = V · [win] − c · budget spent − μ · sanction points`, with the constants `V`, `c`, `μ` shared
by every agent and by the game-theory layer.

The constants of the rulebook (read from `courtroom/judge/rules.py` when this report was generated):

<!-- BEGIN GENERATED:constants -->
| Constant | Value | Meaning |
|---|---|---|
| LLR_SCALE (K) | 3 | log-odds an item of weight 1 contributes |
| CORROBORATION_ALPHA (α) | 1/2 | most a corroborating fact can add to a weight |
| CONTRADICTION_BETA (β) | 4/5 | pairwise contradiction pressure |
| MAX_CONTRADICTION_DISCOUNT | 9/10 | cap on the discount from contradictions |
| IMPEACHMENT_FACTOR | 1/2 | credibility multiplier per successful impeachment |
| HOSTILE_FACTOR | 1/4 | credibility multiplier for a witness who turned hostile (surprises only) |
| Prior log-odds, criminal / civil | -1 / 0 | presumption of innocence / even odds |
| Bar: beyond reasonable doubt | 11/5 | log-odds an element must reach |
| Bar: clear and convincing | 11/10 | log-odds an element must reach |
| Bar: preponderance | 0 | log-odds an element must reach |
| OBJECTION_COST / IMPEACHMENT_COST / MOTION_COST | 0.5 / 1.0 / 0.5 | budget a move costs |
| SANCTION_OVERRULED_OBJECTION / BAD_FAITH / VIOLATION | 0.25 / 2.0 / 1.0 | sanction points |
<!-- END GENERATED:constants -->

**Courtroom surprises** (optional, off by default, and off for every recorded trial) add three random events, each drawn from its own
seeded stream so a trial without them consumes exactly the randomness it always did: a witness may not appear when called, a digital
record may lack its authenticity certificate (both exclude the exhibit and refund nothing), and a witness whose testimony was accepted
may turn hostile (their credibility is multiplied by `HOSTILE_FACTOR`). The chances are `no_show`, `missing_certificate` and `hostile`
in `courtroom/contracts/models.py`. They were chosen for being plausible, not measured; section 8 says so.

## 3. The agents

A lawyer is a `StrategyProfile`: a few numbers read by one shared decision procedure, so the styles differ only in their risk
parameters.

| Parameter | Meaning |
|---|---|
| `max_known_defects` | offer an own exhibit only if it has at most this many defects the lawyer can see |
| `min_gain` | spend a turn only if the move shifts the judge by at least this much |
| `objection_belief` | object only if the believed chance the exhibit is flawed is at least this |
| `objection_min_impact` | ...and only if the exhibit would matter by at least this much |
| `reserve_fraction` | share of the budget held back for objections |

Bold (aggressive), Careful (conservative) and Smart (adaptive: expected-value reasoning with a learned model of how often the other
side objects) are profiles. Wild plays random legal moves and sometimes breaks a rule. Lawyers do not see an exhibit's hidden flaws;
they see them through a noisy channel (a binary red-flag signal with a stated true- and false-positive rate) and hold the Bayesian
posterior. They can, like anyone, query the judge's public scoring rule to ask "what if this exhibit were accepted".

An optional **AI lawyer** (section 7) plays through exactly the same interface.

## 4. Game-theory methods

- **Payoff matrices.** For a case, every pairing of styles is played on a common set of seeds; the entries are mean payoffs.
- **Exact equilibria.** The matrix is solved with support enumeration over `Fraction`s, plus iterated elimination of dominated
  strategies, and each equilibrium is independently verified (no profitable deviation). A case is labelled *dominance-solvable*,
  *pure* or *mixed*.
- **Bootstrap stability.** The seed set is resampled with replacement and the game re-solved on each resample; the stability is the
  share of resamples that give the same label. Per-cell payoffs carry bootstrap intervals (`95%` of resamples fall inside).
- **Sensitivity.** The rulebook's own constants are moved and the library re-solved, to see which conclusions survive.
- **Best-response search (double oracle).** Section 5.
- **Classic games, Pareto efficiency, security values.** Section 6.7 and 6.8: an ordinal classifier for two-by-two games, exact Pareto
  and maximin computations, the minimax theorem checked on the win-probability game.
- **Minimax and alpha-beta on the trial tree.** Section 6.9: an open-file relaxation solved exactly, and a depth-limited lookahead lawyer.
- **Does strategy matter here?** For each case, every pairing of Bold, Careful and Smart over several seeds; the *pairing spread* is
  the best Accuser win rate minus the worst, and the *seed coin-flip* is the average of `2 · min(win rate, 1 − win rate)`. The words
  ("decided by the evidence", "by the lawyers") only label these two numbers.
- **Contested-case finder.** `generate_case(seed)` builds valid cases from seeds. The finder scores a run of them with the measure
  above, solves the 4×4 game for the most contested few, and returns those. The cases are found by search, not written.
- **Tipping point.** The smallest change to one exhibit's reliability or one witness's credibility that flips the verdict, found by
  scanning then bisecting over re-scored records with the judge itself. It does not replay the lawyers, so "apply" re-runs the whole trial.

## 5. The best-response search

The four styles are not the only possible lawyers. Starting from them on each side, the search (`courtroom/gametheory/oracle.py`) loops
for at most four rounds: solve the game; for each side take the other side's equilibrium mix, search the five profile parameters (a
seeded random search, then local refinement) for the profile that earns the most against that mix on *training* seeds; re-test the best
one against the current equilibrium mix on *held-out* seeds with a paired comparison; keep it only above two standard errors; add what
was kept, fill in the new rows and columns, and solve again. Each kept profile is then confirmed on a third set of seeds that played no
part in finding or accepting it. Nothing a language model produced is used.

## 6. Results

All of this is run with the plain rules and again with courtroom surprises on, because surprises change which cases are contested.
Nothing was tuned to make a result look better: no case, parameter or seed was changed after seeing a result.

### 6.1 Does strategy matter here?

<!-- BEGIN GENERATED:matters -->
| Case | Verdict (plain rules) | Lawyers move it by | Seed coin-flip | Verdict (surprises on) | Lawyers move it by | Seed coin-flip |
|---|---|---|---|---|---|---|
| Aurora Protocol Flash-Loan Exploit | Decided by the evidence | 0% | 0% | Decided by the evidence | 0% | 0% |
| The Broken Bike | Decided by the lawyers | 50% | 22% | Partly the lawyers | 38% | 17% |
| The Missing Cookies | Decided by the evidence | 0% | 0% | Decided by the evidence | 0% | 0% |
| Prosecution Brings Only Exculpatory Material | Decided by the evidence | 0% | 0% | Decided by the evidence | 0% | 0% |
| The Empty Docket | Decided by the evidence | 0% | 0% | Decided by the evidence | 0% | 0% |
| Mutually Exclusive Testimony | Decided by the evidence | 0% | 0% | Decided by the evidence | 0% | 0% |
| Fruit of the Poisonous Tree | Partly the lawyers | 25% | 17% | Partly the lawyers | 25% | 17% |
| The Dug-Up Garden | Decided by the evidence | 0% | 0% | Decided by the evidence | 0% | 0% |
| Helix Dynamics Trade-Secret Exfiltration | Decided by the lawyers | 100% | 17% | Decided by the lawyers | 88% | 22% |
| AV-7 Crosswalk Collision | Decided by the lawyers | 100% | 8% | Decided by the lawyers | 100% | 14% |
<!-- END GENERATED:matters -->

<!-- BEGIN GENERATED:matters_findings -->
- Measured over 8 seeds and all nine pairings of Bold, Careful and Smart: **6 of 10 cases are decided by the evidence alone** (Aurora Protocol Flash-Loan Exploit, The Missing Cookies, Prosecution Brings Only Exculpatory Material, The Empty Docket, Mutually Exclusive Testimony, The Dug-Up Garden). In those, no style and no seed changes the verdict, so a strategy comparison has nothing to find.
- The lawyers move the verdict in 4 cases: The Broken Bike, Fruit of the Poisonous Tree, Helix Dynamics Trade-Secret Exfiltration, AV-7 Crosswalk Collision.
- With courtroom surprises on, 6 of 10 cases are still decided by the evidence alone (Aurora Protocol Flash-Loan Exploit, The Missing Cookies, Prosecution Brings Only Exculpatory Material, The Empty Docket, Mutually Exclusive Testimony, The Dug-Up Garden).
<!-- END GENERATED:matters_findings -->

### 6.2 How sure are we?

<!-- BEGIN GENERATED:bootstrap -->
| Case | Label (plain) | Stability | Label (surprises on) | Stability |
|---|---|---|---|---|
| Aurora Protocol Flash-Loan Exploit | pure | 100.0% | pure | 100.0% |
| The Broken Bike | mixed | 87.0% | pure | 83.0% |
| The Missing Cookies | pure | 100.0% | dominance-solvable | 100.0% |
| Prosecution Brings Only Exculpatory Material | pure | 100.0% | pure | 100.0% |
| The Empty Docket | pure | 100.0% | pure | 100.0% |
| Mutually Exclusive Testimony | pure | 100.0% | pure | 100.0% |
| Fruit of the Poisonous Tree | mixed | 100.0% | mixed | 100.0% |
| The Dug-Up Garden | pure | 100.0% | pure | 60.5% |
| Helix Dynamics Trade-Secret Exfiltration | mixed | 99.5% | mixed | 100.0% |
| AV-7 Crosswalk Collision | mixed | 97.5% | dominance-solvable | 88.5% |
<!-- END GENERATED:bootstrap -->

<!-- BEGIN GENERATED:bootstrap_findings -->
- Each game was re-solved on 200 resamples of 200 seeds. Conclusions that came back less than 80% of the time with the plain rules: none.
- With surprises on: The Dug-Up Garden (60%).
<!-- END GENERATED:bootstrap_findings -->

### 6.3 What is fixed by design, and the sensitivity evidence

The rulebook's constants and the standards of proof (the table in section 2) are fixed by design: they are modelling choices, not
measurements, and the project does not claim they are right. What can be tested is whether the *conclusions* depend on them.

<!-- BEGIN GENERATED:sensitivity -->
| Constant moved | Label changes (plain) | Label changes (surprises on) |
|---|---|---|
| LLR SCALE | 1 | 2 |
| PRIOR DEFECT RATE | 6 | 6 |
| beyond reasonable doubt | 1 | 2 |
| costs | 1 | 2 |
| sanctions | 1 | 3 |
| standards of proof | 0 | 0 |
<!-- END GENERATED:sensitivity -->

<!-- BEGIN GENERATED:sensitivity_findings -->
- The library was re-solved under 14 settings of the rulebook's constants (costs, sanctions, evidence weight, the prior defect rate and the standards of proof, each moved by 25% either way, and the "almost certain" bar set from 80% to 95%), on 16 seeds per cell.
- Cases whose label never changed (plain rules): The Empty Docket, Fruit of the Poisonous Tree, Prosecution Brings Only Exculpatory Material. Cases whose label changed under at least one setting: Aurora Protocol Flash-Loan Exploit, The Broken Bike, The Missing Cookies, Mutually Exclusive Testimony, The Dug-Up Garden, Helix Dynamics Trade-Secret Exfiltration, AV-7 Crosswalk Collision.
- With surprises on, never changed: The Empty Docket, Fruit of the Poisonous Tree, Prosecution Brings Only Exculpatory Material.
<!-- END GENERATED:sensitivity_findings -->

### 6.4 Can a better lawyer be found?

<!-- BEGIN GENERATED:oracle -->
| Case | Surprises | Rounds | Profiles tried (best per round) | Kept | Confirmed on fresh seeds | Gain per trial vs old equilibrium | Final Accuser mix | Final Defender mix |
|---|---|---|---|---|---|---|---|---|
| The Broken Bike | off | 2 | 4 | 1 | 1 of 1 | defense: +0.88 | Bold | Found Defender 1 |
| The Broken Bike | on | 1 | 2 | 0 | 0 of 0 | none | Smart | Careful |
| Helix Dynamics Trade-Secret Exfiltration | off | 3 | 6 | 2 | 2 of 2 | defense: +1.59 | 67% Careful, 18% Smart, 15% Bold | 42% Smart, 31% Found Defender 1, 27% Found Defender 2 |
| Helix Dynamics Trade-Secret Exfiltration | on | 3 | 6 | 2 | 2 of 2 | defense: +0.91 | 43% Careful, 29% Bold, 28% Smart | 61% Smart, 32% Found Defender 1, 7% Found Defender 2 |
| AV-7 Crosswalk Collision | off | 1 | 2 | 0 | 0 of 0 | none | 87% Wild, 13% Bold | 51% Careful, 49% Bold |
| AV-7 Crosswalk Collision | on | 2 | 4 | 1 | 1 of 1 | prosecution: +1.22 | Found Accuser 1 | Bold |
<!-- END GENERATED:oracle -->

<!-- BEGIN GENERATED:oracle_findings -->
- **The Broken Bike**, surprises off: The hand-written styles could be beaten: 1 better profile(s) were found for the defense (gain 0.88 per trial), then the game was solved again with them. 1 of 1 also beat the original equilibrium on a third set of seeds nobody had looked at.
  - Defender best-def-1: shows evidence even with up to 1 known problem; spends a turn only if it moves the judge by at least 0.44; objects only when it is 87% sure of a flaw; and only if the exhibit would matter by 1.33 or more; holds back 18% of its budget for objections. Beats the old equilibrium by 0.71 per trial (z 2.23); on fresh seeds z 2.64.
- **The Broken Bike**, surprises on: No better lawyer was found: in 1 round(s) and 120 candidate profiles, none beat the current equilibrium by more than 2 standard errors on held-out seeds.
- **Helix Dynamics Trade-Secret Exfiltration**, surprises off: The hand-written styles could be beaten: 2 better profile(s) were found for the defense (gain 1.59 per trial), then the game was solved again with them. 2 of 2 also beat the original equilibrium on a third set of seeds nobody had looked at.
  - Defender best-def-1: shows only clean evidence; spends a turn only if it moves the judge by at least 0.81; objects only when it is 63% sure of a flaw; and only if the exhibit would matter by 1.44 or more; holds back 2% of its budget for objections (always asks for the trial to end early, objects to anything big whatever it suspects). Beats the old equilibrium by 1.53 per trial (z 4.6); on fresh seeds z 4.7.
  - Defender best-def-2: shows evidence even with up to 2 known problems; spends a turn only if it moves the judge by at least 0.51; objects only when it is 55% sure of a flaw; and only if the exhibit would matter by 0.86 or more; holds back 35% of its budget for objections (always asks for the trial to end early, objects to anything big whatever it suspects). Beats the old equilibrium by 0.77 per trial (z 2.24); on fresh seeds z 2.97.
- **Helix Dynamics Trade-Secret Exfiltration**, surprises on: The hand-written styles could be beaten: 2 better profile(s) were found for the defense (gain 0.91 per trial), then the game was solved again with them. 2 of 2 also beat the original equilibrium on a third set of seeds nobody had looked at.
  - Defender best-def-1: shows only clean evidence; spends a turn only if it moves the judge by at least 0.48; objects on the slightest suspicion; and only if the exhibit would matter by 0.10 or more; holds back 60% of its budget for objections (reasons about the other lawyer). Beats the old equilibrium by 0.90 per trial (z 6.52); on fresh seeds z 5.55.
  - Defender best-def-2: shows evidence even with up to 2 known problems; spends a turn only if it moves the judge by at least 0.85; objects on the slightest suspicion; and only if the exhibit would matter by 1.17 or more; holds back 60% of its budget for objections. Beats the old equilibrium by 1.42 per trial (z 2.22); on fresh seeds z 3.28.
- **AV-7 Crosswalk Collision**, surprises off: No better lawyer was found: in 1 round(s) and 120 candidate profiles, none beat the current equilibrium by more than 2 standard errors on held-out seeds.
- **AV-7 Crosswalk Collision**, surprises on: The hand-written styles could be beaten: 1 better profile(s) were found for the prosecution (gain 1.22 per trial), then the game was solved again with them. 1 of 1 also beat the original equilibrium on a third set of seeds nobody had looked at.
  - Accuser best-pro-1: shows evidence even with up to 1 known problem; spends a turn only if it moves the judge by at least 0.08; objects only when it is 64% sure of a flaw; and only if the exhibit would matter by 1.22 or more; holds back 31% of its budget for objections. Beats the old equilibrium by 1.99 per trial (z 2.05); on fresh seeds z 3.25.
- Search settings: 60 candidate profiles per side per round, searched on 8 seeds, accepted on 24 held-out seeds, confirmed on 24 more; at most 4 rounds; a profile is kept only above 2 standard errors.
<!-- END GENERATED:oracle_findings -->

### 6.5 The AI lawyer against the four styles

<!-- BEGIN GENERATED:exhibition -->
_Not run._ The harness is built and tested against a stub, but no language-model backend answered while this project was assembled, so there is no table. With a backend available, `python -m courtroom exhibition --json results/exhibition.json` produces one, and this section fills itself in.
<!-- END GENERATED:exhibition -->

### 6.6 The lecture concepts, and where each is computed

Six ideas from the course lectures are computed from this project's own games. Where an idea does not occur in our data, the table says so
plainly; no case, payoff or seed was changed to make a lecture game appear.

<!-- BEGIN GENERATED:lectures -->
| Lecture concept | Where it is computed | What our data says | Limits |
|---|---|---|---|
| Prisoner's dilemma | `gametheory/classic.py`; `python -m courtroom classic`; `results/classic*.json` | **Not found.** 0 of 360 corners in the library, and 0 kept after searching 395 generated cases. | Only pairs of styles (2×2 corners of the 4×4 table). A gap under two standard errors is a tie, and a game needing a strict order where there is a tie is called none of the classic games. |
| Stag hunt | same | **Not found.** 0 of 360 corners in the library, and 0 kept after searching 395 generated cases. | Risk is read from each play's worst case (a security-level notion), not from risk dominance. |
| Battle of the sexes (Bach or Stravinsky) | same | **Not found.** 0 of 360 corners in the library, and 0 kept after searching 395 generated cases. | Needs two pure equilibria that the sides rank differently. |
| Chicken | same | **Not found.** 0 of 360 corners in the library, and 0 kept after searching 395 generated cases. | The same two-equilibria shape with a full strict order of four outcomes. |
| Matching pennies | same | 16 corners (plain), 14 (surprises on) | Named when no pure equilibrium survives the tolerance; the sides need not be zero-sum. |
| Pareto optimality | `gametheory/efficiency.py`; `python -m courtroom efficiency`; `results/efficiency*.json` | Some equilibrium dominated for both sides in 1 of 10 cases (plain), 1 (surprises on). | Compared on mean payoffs over pure pairs of styles; a mixed equilibrium is compared by its expected payoffs, and mixing across cells together is not considered. |
| Minimax and the minimax theorem | `gametheory/efficiency.py` (exact maximin by vertex enumeration); `tests/test_efficiency.py` | Maximin = minimax = Nash value in 20 of 20 win-probability games. | Holds only for the constant-sum win-probability game. The real game is general-sum, so there the security value is only a floor. |
| Minimax on the trial tree | `gametheory/search.py`; `python -m courtroom tree`; `results/tree_search.json` | 17 of 18 cases solved exactly. | An open-file relaxation: both sides see all exhibits and flaws, no perception noise, and a zero-sum payoff (Accuser utility minus Defender utility). The real game has hidden information and is not zero-sum. |
| Alpha-beta pruning | same | Same value as plain minimax in all 15 cases where both finished, with move ordering cutting the nodes visited as shown in the table. | Pruning is exact; the saving depends on the case and on the ordering heuristic. |
| Thinking ahead (depth-limited alpha-beta) | `agents/lookahead.py`; `python -m courtroom lookahead`; `results/lookahead*.json` | Beat the four-style equilibrium in 1 of 10 cases (plain) and 1 (surprises on). | Exhibition, not certified. It uses only its own view and the public oracle, assumes the worst reply, and scores positions with a heuristic. |
<!-- END GENERATED:lectures -->

Two limits apply to everything in 6.6 to 6.9. **First, the standards of proof, costs and sanctions are game parameters, not legal probabilities:**
they are modelling choices, and 6.3 tests which conclusions depend on them. **Second, the real game is not the textbook game.** It has hidden
information (a lawyer sees the other side's exhibits only through a noisy signal), it is general-sum (each side's utility is its own win, cost
and sanctions), and it is sequential. Each lecture method below makes one of three relaxations and says which.

### 6.7 Which classic game is this?

A two-by-two game is a prisoner's dilemma, a stag hunt, a battle of the sexes, chicken or matching pennies according to the *order* of its
payoffs, not their size. The classifier (`courtroom/gametheory/classic.py`) reads that order and is tested on the textbook matrices, on
relabelled and rescaled copies of them, and with noise. A payoff counts as better than another only if it is higher by more than two standard
errors of the difference, so a game that needs a strict order where the data has a tie is called "none of the classic games" rather than forced
into a name. It is applied to every two-by-two corner of each case's measured 4×4 table (every pair of the four styles for each side), and
each label is re-tested on resamples of the seeds.

<!-- BEGIN GENERATED:classic_findings -->
- **Plain rules.** 10 cases, 360 two-by-two corners (every pair of the four styles for each side), measured over 200 seeds, labels re-tested on 200 resamples of the seeds.
  - Prisoner's dilemma: 0.
  - Stag hunt: 0.
  - Battle of the sexes: 0.
  - Chicken: 0.
  - Matching pennies: 16 (Fruit of the Poisonous Tree (9); Helix Dynamics Trade-Secret Exfiltration (5); AV-7 Crosswalk Collision (2)).
  - Dominance-solvable: 200 (Aurora Protocol Flash-Loan Exploit (32); The Broken Bike (7); The Missing Cookies (30); Prosecution Brings Only Exculpatory Material (9); The Empty Docket (9); Mutually Exclusive Testimony (25); Fruit of the Poisonous Tree (12); The Dug-Up Garden (25); Helix Dynamics Trade-Secret Exfiltration (19); AV-7 Crosswalk Collision (32)).
  - None of the classic games: 144 (Aurora Protocol Flash-Loan Exploit (4); The Broken Bike (29); The Missing Cookies (6); Prosecution Brings Only Exculpatory Material (27); The Empty Docket (27); Mutually Exclusive Testimony (11); Fruit of the Poisonous Tree (15); The Dug-Up Garden (11); Helix Dynamics Trade-Secret Exfiltration (12); AV-7 Crosswalk Collision (2)).
  - The matching-pennies corners kept their label on 89% of resamples on average.
- **Courtroom surprises on.** 10 cases, 360 two-by-two corners (every pair of the four styles for each side), measured over 200 seeds, labels re-tested on 200 resamples of the seeds.
  - Prisoner's dilemma: 0.
  - Stag hunt: 0.
  - Battle of the sexes: 0.
  - Chicken: 0.
  - Matching pennies: 14 (Fruit of the Poisonous Tree (9); Helix Dynamics Trade-Secret Exfiltration (5)).
  - Dominance-solvable: 151 (Aurora Protocol Flash-Loan Exploit (30); The Broken Bike (7); The Missing Cookies (30); Prosecution Brings Only Exculpatory Material (9); The Empty Docket (9); Fruit of the Poisonous Tree (12); The Dug-Up Garden (10); Helix Dynamics Trade-Secret Exfiltration (23); AV-7 Crosswalk Collision (21)).
  - None of the classic games: 195 (Aurora Protocol Flash-Loan Exploit (6); The Broken Bike (29); The Missing Cookies (6); Prosecution Brings Only Exculpatory Material (27); The Empty Docket (27); Mutually Exclusive Testimony (36); Fruit of the Poisonous Tree (15); The Dug-Up Garden (26); Helix Dynamics Trade-Secret Exfiltration (8); AV-7 Crosswalk Collision (15)).
  - The matching-pennies corners kept their label on 96% of resamples on average.
- **Search over generated cases (plain rules).** 395 generated cases (tried gen-0 to gen-394), 14220 corners. Read as exact numbers, 47 corners looked like a prisoner's dilemma, stag hunt or battle of the sexes (41 dilemma, 6 stag hunt, 0 battle of the sexes); **0 kept** their name under the full tolerance on fresh seeds.
- **Search over generated cases (surprises on).** 395 generated cases (tried gen-0 to gen-394), 14220 corners. Read as exact numbers, 48 corners looked like a prisoner's dilemma, stag hunt or battle of the sexes (46 dilemma, 2 stag hunt, 0 battle of the sexes); **0 kept** their name under the full tolerance on fresh seeds.
<!-- END GENERATED:classic_findings -->

What this does and does not show. The classifier looks at pairs of styles, so a classic game that needs a third style, or a mixed strategy,
to appear is invisible to it. The search over generated cases first reads the means as exact numbers to find candidates, then demands the full
tolerance on fresh seeds; a corner that only looked like a dilemma on a few seeds does not survive that. "Not found" is therefore a statement
about the library and about the generated cases tried, not a proof that no such case can exist.

### 6.8 Efficiency and what each side can guarantee

**Pareto optimality.** A cell of the payoff table is Pareto-efficient if no other cell is at least as good for both sides and better for one.
An equilibrium that some cell beats for both sides is the prisoner's-dilemma lesson: both play the equilibrium and both would prefer another
outcome.

<!-- BEGIN GENERATED:efficiency_findings -->
- **Plain rules** (200 seeds): an equilibrium dominated for **both** sides by some cell (the prisoner's-dilemma pattern) in 1 of 10 cases (AV-7 Crosswalk Collision); only weakly dominated (a cell helps one side and hurts nobody) in 3 (The Broken Bike, Fruit of the Poisonous Tree, Helix Dynamics Trade-Secret Exfiltration); every equilibrium Pareto-efficient in 6 (Aurora Protocol Flash-Loan Exploit, The Missing Cookies, Prosecution Brings Only Exculpatory Material, The Empty Docket, Mutually Exclusive Testimony, The Dug-Up Garden).
- **Courtroom surprises on** (200 seeds): an equilibrium dominated for **both** sides by some cell (the prisoner's-dilemma pattern) in 1 of 10 cases (AV-7 Crosswalk Collision); only weakly dominated (a cell helps one side and hurts nobody) in 2 (Fruit of the Poisonous Tree, Helix Dynamics Trade-Secret Exfiltration); every equilibrium Pareto-efficient in 7 (Aurora Protocol Flash-Loan Exploit, The Broken Bike, The Missing Cookies, Prosecution Brings Only Exculpatory Material, The Empty Docket, Mutually Exclusive Testimony, The Dug-Up Garden).
<!-- END GENERATED:efficiency_findings -->

**Security values and the minimax theorem.** The security (maximin) value of a side is the most it can guarantee whatever the other side does,
allowing it to mix its styles. It is computed exactly, by enumerating the vertices of the linear program in rational numbers
(`courtroom/gametheory/efficiency.py`). In a constant-sum game the two sides' security values meet at the value of the game and equal the Nash
value (the minimax theorem); a test checks this on random matrices and the committed results record it on our own tables, using the Accuser's
win probability, which is constant-sum because exactly one side wins.

<!-- BEGIN GENERATED:security_findings -->
- **Plain rules.** In the win-probability game (constant-sum) maximin equals minimax equals the Nash value in 10 of 10 cases, as the minimax theorem says; a pure saddle point (nobody needs to randomise) in 10. The Accuser's guaranteed win rate runs from 0% (Aurora Protocol Flash-Loan Exploit) to 100% (The Broken Bike). In the full general-sum game, an equilibrium pays the Accuser between 0.00 and 0.39 above its security value and the Defender between 0.00 and 1.51 above its own.
- **Courtroom surprises on.** In the win-probability game (constant-sum) maximin equals minimax equals the Nash value in 10 of 10 cases, as the minimax theorem says; a pure saddle point (nobody needs to randomise) in 10. The Accuser's guaranteed win rate runs from 0% (Aurora Protocol Flash-Loan Exploit) to 100% (The Broken Bike). In the full general-sum game, an equilibrium pays the Accuser between 0.00 and 0.66 above its security value and the Defender between 0.00 and 1.71 above its own.
<!-- END GENERATED:security_findings -->

The theorem is a statement about the win-probability game only. The real payoffs also count money spent and sanctions, so they are not
constant-sum; there the security value is a floor, and the gap above it is what reasoning about the other lawyer adds.

### 6.9 The trial as a tree: minimax, alpha-beta and thinking ahead

The payoff tables flatten a trial into one choice of style. The trial is really a sequence: offer an exhibit, the other side objects or not,
and so on. `courtroom/gametheory/search.py` searches that tree with plain minimax and with alpha-beta, using the engine's own rules: a node is
a real `Court`, the legal moves come from the real validator and judge, a move is applied by the real dispatcher, and the value is the real
judge's verdict through the real payoff. A test replays recorded trials through the tree and through the engine and checks they agree.

**What the relaxation assumes.** Both sides see every exhibit and every flaw, with no perception noise, so every move has a deterministic
outcome (perfect information). The payoff is made zero-sum: the Accuser's utility minus the Defender's. Passing a turn, and objections or
impeachments the judge would reject, are left out because they are never better than another move; a test puts them back and checks the value
is unchanged. None of this is the game the certified analysis solves.

<!-- BEGIN GENERATED:tree_table -->
| Case | Exhibits (Accuser, Defender) | Best-play value | Plain minimax nodes | Alpha-beta nodes | Alpha-beta with ordering | Same value? |
|---|---|---|---|---|---|---|
| aurora-defi | 8, 5 | -10 | not run | not run | 344,204 | yes |
| broken-bike | 4, 3 | 9.4 | 31,609 | 3,734 | 732 | yes |
| cookie-jar | 4, 3 | -10 | 21,691 | 3,126 | 444 | yes |
| edge-defense-only | 1, 1 | -10 | 9 | 9 | 8 | yes |
| edge-empty-docket | 0, 0 | -10 | 4 | 4 | 4 | yes |
| edge-mutual-exclusion | 1, 1 | -10 | 21 | 21 | 14 | yes |
| edge-poisoned-tree | 5, 0 | -10 | 46,387 | 2,408 | 1,826 | yes |
| garden-dog | 4, 3 | -10 | 20,849 | 2,389 | 542 | yes |
| gen-20 | 1, 2 | 9.7 | 28 | 25 | 24 | yes |
| gen-27 | 1, 2 | -9.7 | 45 | 44 | 45 | yes |
| gen-39 | 1, 3 | -10 | 19 | 19 | 9 | yes |
| gen-44 | 2, 1 | -10 | 233 | 138 | 20 | yes |
| gen-51 | 2, 2 | 9.7 | 48 | 33 | 29 | yes |
| gen-57 | 1, 3 | -10 | 475 | 137 | 8 | yes |
| gen-6 | 3, 1 | -10 | 16 | 14 | 13 | yes |
| gen-62 | 2, 2 | 9.7 | 248 | 163 | 102 | yes |
| helix-espionage | 10, 7 | not solved | not run | not run | more than 60,000 | – |
| kestrel-av | 7, 5 | -10 | not run | not run | 246,554 | yes |
<!-- END GENERATED:tree_table -->

<!-- BEGIN GENERATED:tree_findings -->
- 17 of 18 cases were solved exactly; plain minimax, alpha-beta and alpha-beta with move ordering returned **the same value in every one**.
- On the 15 cases where plain minimax also finished, alpha-beta with move ordering visited between 2% and 100% of minimax's nodes; the most expensive was edge-poisoned-tree: 46,387 nodes for plain minimax, 2,408 for alpha-beta, 1,826 with ordering.
- Move ordering helped in 13 of the 15 cases and made no difference or cost slightly more in 1 (gen-27).
- Larger cases (aurora-defi, kestrel-av) were solved with the ordered search alone, because plain minimax would not finish; helix-espionage could not be solved within the node limit.
- With both sides seeing everything, the Accuser can win in 4 of the 17 solved cases; in the others the Defender wins whatever the Accuser does.
<!-- END GENERATED:tree_findings -->

**A lawyer that thinks ahead.** `courtroom/agents/lookahead.py` is a depth-limited alpha-beta lawyer. In a real trial it uses only its own
view and the public scoring oracle (a test checks it reads nothing else). On its own turn it searches its next few moves and assumes the
opponent replies with whatever hurts it most; when the opponent offers an exhibit it weighs an objection by its belief that the objection
will be sustained, an expectation over its own hidden-information belief. This is the proposal's stretch expectimax agent in a simple form.
It was designed before it was compared and not tuned afterwards, with one disclosed exception: a first version scored positions only by an
estimate of winning and gave up too early in the largest case, so the log-odds potential the other styles already use to value a move was
added to its score before any comparison was run. It is **not** one of the four certified styles and is not in the recorded trials; it is
compared with them here as a labelled extra, with the same paired test the best-response search uses.

<!-- BEGIN GENERATED:lookahead_findings -->
- **Plain rules** (40 seeds, paired by seed, against the four-style equilibrium): lookahead beat it by more than two standard errors in 1 of 10 cases: AV-7 Crosswalk Collision (as Accuser and as Defender); did clearly worse in 4: Prosecution Brings Only Exculpatory Material (as Defender); The Empty Docket (as Defender); Mutually Exclusive Testimony (as Accuser and as Defender); The Dug-Up Garden (as Accuser and as Defender); was not distinguishable in 5: Aurora Protocol Flash-Loan Exploit, The Broken Bike, The Missing Cookies, Fruit of the Poisonous Tree, Helix Dynamics Trade-Secret Exfiltration.
- **Courtroom surprises on** (40 seeds, paired by seed, against the four-style equilibrium): lookahead beat it by more than two standard errors in 1 of 10 cases: AV-7 Crosswalk Collision (as Accuser and as Defender); did clearly worse in 5: The Broken Bike (as Accuser); Prosecution Brings Only Exculpatory Material (as Defender); The Empty Docket (as Defender); Mutually Exclusive Testimony (as Accuser and as Defender); The Dug-Up Garden (as Accuser and as Defender); was not distinguishable in 4: Aurora Protocol Flash-Loan Exploit, The Missing Cookies, Fruit of the Poisonous Tree, Helix Dynamics Trade-Secret Exfiltration.
<!-- END GENERATED:lookahead_findings -->

Read a result of "not distinguishable" as "this many seeds cannot tell", not as "as good". A win for lookahead shows the four hand-written
styles can be beaten by a lawyer that thinks ahead in that case; it does not show lookahead is a good lawyer in general.

### 6.10 What these results rest on

<!-- BEGIN GENERATED:files -->
| Result file | sha256 (first 12) | Size |
|---|---|---|
| `results/bootstrap.json` | `2fb6c00183c3` | 24 KiB |
| `results/bootstrap_surprises.json` | `e592d6c4cb6e` | 24 KiB |
| `results/classic.json` | `05e7a3228ca5` | 150 KiB |
| `results/classic_search.json` | `43face64976a` | 1 KiB |
| `results/classic_search_surprises.json` | `01b4699396ed` | 1 KiB |
| `results/classic_surprises.json` | `a419562fcb92` | 149 KiB |
| `results/efficiency.json` | `1674b8cfdbae` | 34 KiB |
| `results/efficiency_surprises.json` | `5fb1f68e474e` | 34 KiB |
| `results/lookahead.json` | `4f19ef9c385c` | 14 KiB |
| `results/lookahead_surprises.json` | `1ecc9349ef8a` | 14 KiB |
| `results/matters.json` | `d4c87d4ce5a1` | 6 KiB |
| `results/matters_surprises.json` | `0666468af658` | 6 KiB |
| `results/oracle/broken-bike.json` | `ae02f6839677` | 6 KiB |
| `results/oracle/broken-bike_surprises.json` | `447612ef1bf4` | 4 KiB |
| `results/oracle/helix-espionage.json` | `fb15f6beab54` | 8 KiB |
| `results/oracle/helix-espionage_surprises.json` | `8c0f0fe5738f` | 8 KiB |
| `results/oracle/kestrel-av.json` | `38c56ee34e51` | 4 KiB |
| `results/oracle/kestrel-av_surprises.json` | `405d7c1b2cf4` | 6 KiB |
| `results/sensitivity.json` | `943dc7ca3e48` | 11 KiB |
| `results/sensitivity_surprises.json` | `5e1e068989e5` | 11 KiB |
| `results/tree_search.json` | `452f4d8ce4ef` | 22 KiB |

160 recorded trials are pinned in `tests/golden/bundle_digests.json`; 537 spoken lines in `tests/golden/lines_baseline.json`.
<!-- END GENERATED:files -->

## 7. The language model's role and its limits

A model is optional everywhere. With no key, no Ollama and no network, the whole system runs and every test passes. It may play a
lawyer (the AI lawyer picks a move from a numbered list of the legal ones and says why in one sentence), draft a case file from plain
English (validated by the same contracts as any case, with up to two repair rounds, then handed to a person in an editor), word the
spoken lines for a case that has no script (any line that adds a number or a name not in the exhibit text is refused), and word the
verdict explanation (refused if it uses a figure the judge did not produce). It reads from the first backend that answers: Ollama
Cloud, a local Ollama, then Gemini, through one disk-cached client at temperature 0.

It may never decide a verdict, enter a certified payoff, change a recorded trial or be imported by the core. `docs/LLM_ROLE.md` states
this in full, including why a best-response check cannot certify an opaque policy: a model has no small parameter family to search,
no guarantee of the same answer twice from a cold cache, and no way to enumerate what it could play. Trials a model played are marked
`certified: false` and are shown beside the certified ones, never inside them.

## 8. Limitations

- **The cases are synthetic and were written by us.** Their evidence values are modelling choices. The library was not tuned to produce
  any result reported here, but it was written before the measurements, by people who knew what they wanted to show.
- **The payoffs come from our own engine.** Everything certified is a statement about the deterministic styles and the exact judge, not
  about real courts or real lawyers.
- **The surprise chances are chosen, not observed.** Plausible values were picked; no experiment says they are right. Results with
  surprises on are best read as "if this kind of luck exists".
- **The search covers five numbers.** "No better lawyer found" means none was found in that family within that budget. It is evidence,
  not proof. A lawyer that reasons differently (a model, a human) is outside it.
- **Several comparisons are made.** Two candidates per round over several rounds means a lone result just above two standard errors
  is weak evidence by itself, which is why every kept profile is confirmed on fresh seeds.
- **Seed counts are modest** (stated beside each result) so that everything can be reproduced in minutes on a laptop.
- **The hosted site replays.** Only the local server computes; the hosted site shows recorded trials and stored results, and says so.
- **The AI-lawyer exhibition** is run only when a model backend answers (section 6.5 says whether it was).
- **The tree search is a relaxation.** It assumes both sides see everything and the payoff is zero-sum, and it covers only the cases small
  enough to finish (6.9 lists which). It says what perfect play would be in the open-file game, not what lawyers with hidden information do.
- **The lookahead lawyer is an exhibition.** Its leaf estimate and its "assume the worst reply" rule are simplifications, and it does not model
  the opponent's own future offers. Its comparison with the four styles is paired by seed but uses one seed set and no held-out set.
- **Classic-game names are order statements about pairs of styles.** They depend on the tolerance (two standard errors) and cannot see games
  that need a third style or a mixed strategy. "Not found" is a statement about the cases tried.
- **Where the proposal and the code differ** is listed in `DEVIATIONS.md`.

## 9. AI-usage disclosure

The code, tests and documentation of this version were written with the help of a coding assistant (Claude Code). The instructor
cleared the use of language models verbally on 4 November 2026; the clearance was verbal, not written. Everything the assistant wrote
is covered by tests and the commands in `PROVENANCE.md`. Language models are also used *inside* the product as described in
section 7, optionally, and never for anything certified.

## 10. Related work

Only what each source's abstract states is claimed here; the double-oracle and empirical game-theoretic papers are cited by title only.

- **AgentCourt: Simulating Court with Adversarial Evolvable Lawyer Agents** (arXiv 2408.08089). An LLM-based courtroom simulation in
  which lawyer agents improve by adversarial interaction over many simulated cases. Ours differs in using a deterministic rulebook judge
  and fixed, inspectable strategies, so every conclusion is an exact computation over a game rather than a property of a model.
- **A Unified Game-Theoretic Approach to Multiagent Reinforcement Learning** (Lanctot et al., arXiv 1711.00832). Introduces
  Policy-Space Response Oracles: approximate best responses to a mixture of policies, with empirical game-theoretic analysis to pick
  meta-strategies; its abstract says the algorithm generalises double oracle among others. Our search is the same loop with a parameter
  search in place of reinforcement learning as the oracle.
- **Planning in the Presence of Cost Functions Controlled by an Adversary** (McMahan, Gordon and Blum, 2003): the double-oracle method.
  Cited by title only.
- **Methods for Empirical Game-Theoretic Analysis** (Wellman, 2006): building and solving a game from simulation outcomes. Cited by title only.
- **Code-Space Response Oracles: Generating Interpretable Multi-Agent Policies with Large Language Models** (arXiv 2603.10098).
  Replaces the reinforcement-learning oracle in PSRO with a language model that writes policies as readable code. This is the closest
  neighbour to a possible extension of ours: letting a model propose profiles or policies that our exact judge and held-out seeds
  then test. We do not do that here; our oracle is a plain parameter search and our model never enters a certified table.

## 11. Reproducing it

`PROVENANCE.md` gives one command per claim.
