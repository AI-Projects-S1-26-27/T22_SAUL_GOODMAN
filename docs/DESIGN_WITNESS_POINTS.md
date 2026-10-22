# Design: per-point burden, expert witnesses, and narrated examination

**Status (updated): Part B and Part C are implemented behind the flag (DEVIATIONS D13); the top-4-facts cap
was implemented instead of Part A (D12); Part A as briefed was skipped.** Where the code differs from the
design below, D13 says so. Every number in the audit sections was measured
against the current code on 18 Oct 2026; the commands are given so they can be re-run. Everything in
the proposal sections is a design to be accepted, changed or rejected.

Two things in here need a decision before any code is written, and both are flagged at the end:
a change to the judge's scoring formula (§7.1), and a second use of a language model (§7.2).

---

## 1. The compatibility flag

Everything proposed is gated behind one new optional field on `CaseFile`:

```python
rules: RuleSet | None = None   # None  =>  today's rules, bit for bit
```

**Why this is safe, demonstrated rather than asserted.** A trial's digest is the SHA-256 chain over
its events, and an event hashes exactly eleven fields:

```
action, actor, burden_index, element_probabilities, kind, phase, rules, seq, status, subject, summary
```

No case-file content reaches the hash. Adding a field to `CaseFile` therefore cannot change a digest
unless it changes behaviour. This is not speculation: `bar_log_odds` was added to `CaseFile` in
exactly this way (deviation D9) and all 42 pinned digests in `tests/test_golden.py` were unchanged.

```bash
python -m pytest tests/test_golden.py     # 42 digests, must stay green with the flag off
```

**The rule for this work:** `tests/test_golden.py`, `RESULTS.md`, `results/*.json` and the shipped
bundle are produced with `rules=None` and must not move. A second, opt-in results file covers the new
rules. If a golden digest changes, the flag has leaked; that is a stop-and-fix, not a regenerate.

New `ActionType` members are digest-safe on the same argument: an enum member that is never emitted
never appears in an event. New `EventKind` members likewise.

---

## 2. Part A audit: what the judge already does

Source: `courtroom/judge/scoring.py`, constants in `courtroom/judge/rules.py`.

For each legal element *e*, over admitted items only:

| Quantity | Formula | Constant | In code |
|---|---|---|---|
| Strength | `S_i = reliability_i × credibility_i` | — | `strength` |
| Credibility | `base × (1/2)^impeachments` | `IMPEACHMENT_FACTOR = 1/2` | `credibility()` |
| Contradiction discount | `d_i = min(9/10, Σ_j β·S_j/(S_i+S_j))` | `β = 4/5`, cap `9/10` | `discount` |
| Corroboration | `c_i = 1 + α(1 − 2^-k)` | `α = 1/2` | `corr` |
| Item weight | `w_i = s_i · S_i · (1 − d_i) · c_i` | — | `weights` |
| Element | `L_e = π + K · Σ_{counted} w_i` | `K = 3`, `π = −1` criminal, `0` civil | `log_odds` |
| Verdict | every element clears its bar (conjunctive) | `11/5`, `11/10`, `0` | `all_met` |

Four properties matter for what follows.

**Corroboration is a bounded multiplier, not a damper.** `k` counts *other facts* supporting the same
element with the same sign, so `c_i ∈ [1, 1.5)`. It *rises* as evidence accumulates.

**The cumulative-evidence rule already blocks same-fact spam.** One item is counted per `fact_id`, the
one with the largest `|w|`. Measured: one, two and four exhibits on the *same* fact all give
`L_e = 0.92`. That part works.

**There is no cap on the number of facts, and the proposal claims there is.** Proposal §6 states that
`Fe` is "the four facts with the largest |v| per side, so splitting one fact into many cannot inflate
the score". The code sums *every* counted item with no truncation. This is an implementation gap in
the existing system, not something this design introduces, and it is the root of the next point.

**The marginal exhibit never stops paying.** Identical exhibits on distinct facts, support 0.8,
reliability 0.8:

| Exhibits | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| `L_e` | 0.92 | 3.80 | 6.92 | 10.04 | 13.10 | 16.10 | 19.05 | 21.98 |
| marginal | — | +2.88 | +3.12 | +3.12 | +3.06 | +3.00 | +2.96 | +2.92 |

Growth is linear and unbounded. At eight exhibits `L_e = 21.98`, a probability of 1 − 3×10⁻¹⁰.

### 2.1 The brief's premise, corrected

The brief asks for a per-point burden "so I can show that 2-3 exhibits are needed to establish a
point". **That property already holds.** Measured exhibits needed to clear the criminal bar of 11/5:

| Exhibit quality (support / reliability) | `L_e` by exhibit count | Needed |
|---|---|---|
| strong (0.9 / 0.9) | 1.43, 5.08, 9.02, … | **2** |
| good (0.8 / 0.8) | 0.92, 3.80, 6.92, … | **2** |
| fair (0.6 / 0.7) | 0.26, 2.15, 4.20, … | **3** |
| weak (0.4 / 0.6) | −0.28, 0.80, 1.97, 3.14, … | 4 |

A single perfect exhibit cannot convict (`−1 + 3 = 2 < 2.2`), which the proposal claims and the code
delivers. So the burden does not need inventing. **What is missing is the ceiling.** The proposal
below is therefore aimed at the tail, not at the threshold, and it is deliberately tuned to leave the
2-3 behaviour above roughly where it is.

### 2.2 Proposal A1: rank-discounted corroboration

Sort the counted weights for an element in descending `|w|` and discount by rank:

```
L_e = π + K · Σ_{r=1..n} γ^(r−1) · w_(r)          γ = 2/3
```

* `γ` is a `Fraction`, so the arithmetic stays exact and order-independent (the sort is by `|w|` with
  the existing `evidence_id` tie-break, so it is still a pure function of the admitted set).
* The sum is bounded by `w_max/(1−γ) = 3·w_max`, so `L_e ≤ π + 3K·w_max`. With a perfect exhibit that
  is `−1 + 9 = 8` (p ≈ 99.97%) instead of unbounded.
* Effect on the table above (good exhibits): 0.92, **3.00**, 4.33, 5.22, 5.81, 6.21. Two still clears
  the bar; the fourth exhibit adds 0.89 instead of 3.12; the eighth adds under 0.2.

**What changes:** one expression in `score_record`. **What does not:** `S_i`, `d_i`, `c_i`, `K`, the
three standards, the prior, the conjunctive test, exact-`Fraction` arithmetic, permutation invariance,
and the cumulative-evidence rule.

**Alternative A1′, if the team prefers the smallest possible change:** implement the top-N cap the
proposal already claims (`N = 4` facts per side). It is one line, it closes the documented gap, and it
needs no new constant. It is cruder: the fifth exhibit is worth exactly nothing rather than a little,
which creates a cliff that an agent can sit exactly on top of.

Recommendation: **A1**, with `γ` exposed in the sensitivity sweep so its influence is measured rather
than asserted.

### 2.3 Proposal A2: argue a point with up to N exhibits

A new primary action, `ARGUE_POINT(element_id, [evidence_ids])`, with `N = 3`.

* **Cost** is the sum of the individual presentation costs. No bundle discount: the saving is turns,
  not budget.
* **Objections are unchanged.** The bundle opens *one response window per exhibit*, in listed order.
  The alternative (one window for the whole bundle) would make objections far weaker and would change
  what a sustained objection means; it is not proposed.
* **Turn economics change, which is the point.** Turn caps are 8–10 primary turns and budgets are
  10–12 units, so today the turn cap binds before the budget does for cheap documents. Bundling makes
  budget the binding constraint, which is what makes A1's diminishing returns bite as a *choice*:
  spend three units deepening one point, or spread them across three points.
* **Directed-verdict soundness is unaffected.** The review fires when the prosecution can present no
  more; a bundle is still a presentation, and defense evidence still cannot raise `L_e` (D5, D6).

---

## 3. Part B audit: what exists for witnesses

| Thing | Current state | Source |
|---|---|---|
| `Witness` | `id, name, role, credibility (0–1), bias_note` | `contracts/models.py` |
| `bias_note` | **free text, no mechanics** — it is displayed, never read by the judge | — |
| Impeachment | `ActionType.IMPEACH`, costs 1.0, needs the witness to have testified | `procedure/validator.py` |
| Success rule | `ok = witness_id in impeaching_item.impeaches` — **deterministic, from a hardcoded list** | `judge.rule_on_impeachment` |
| Effect | credibility `× 1/2`, cumulative per success | `IMPEACHMENT_FACTOR` |
| Perception | `perceive()` covers `ObjectionGround` on *evidence items* only; **no witness channel exists** | `agents/base.py` |
| Noise model | `tpr = a`, `fpr = (1−a)/4`, prior 0.15, posterior via Bayes | `defect_posteriors()` |

So there is a witness-attack move already, but it is a single binary action against a fixed list, with
no hidden structure and no uncertainty in the outcome. Everything in Part B is genuinely new.

> **A reversal to note.** An earlier instruction in this project said "Don't add cross-examination;
> impeachment already covers that strategic content", and that is why none exists. This brief asks for
> it. The design below supersedes that instruction if accepted; it should be recorded as such.

### 3.1 Proposal B1: hidden witness flaws

`Witness` gains an optional, hidden structure mirroring the evidence defect flags:

```python
qualified: bool = True        # an expert whose qualifications do not cover the opinion
impartial: bool = True        # undisclosed interest in the outcome
consistent: bool = True       # prior statement conflicts with the testimony given
```

Defaults make every existing witness flawless, so existing cases are unchanged. `bias_note` stays as
the human-readable gloss and is now backed by `impartial` where a case author sets it.

### 3.2 Proposal B2: examination moves

| Action | Window | Cost | Legality |
|---|---|---|---|
| `EXAMINE(witness)` | primary | 0.5 | own witness, has testified, once per witness |
| `CROSS_EXAMINE(witness, ground)` | primary | 1.0 | opposing witness, has testified, once per (witness, ground) |

`ground ∈ {QUALIFICATIONS, BIAS, INCONSISTENCY}`, mapping one-to-one onto the three flaws.

**Perception reuses the existing channel, it does not invent one.** `perceive_witness()` calls the
same `defect_posteriors(case.perception_accuracy)`, so a cross-examiner faces the same
tpr = *a*, fpr = (1−*a*)/4, prior 0.15 trade-off as an objector. At the flagship's accuracy of 0.65
the posterior after a red flag is 0.567 — below Conservative's 0.70 objection threshold, which is why
a careful lawyer currently never objects on a guessed ground. The same will be true of cross-exam, and
that is a finding to report rather than a bug to tune away.

**Outcomes are deterministic given the hidden truth, graded by ground:**

| Ground | If the flaw is real | If it is not |
|---|---|---|
| `QUALIFICATIONS` | credibility `× 1/2`, and the witness's expert opinions stop counting on points outside their field | cost + sanction 1/4 |
| `BIAS` | credibility `× 2/3` | cost + sanction 1/4 |
| `INCONSISTENCY` | credibility `× 1/2` **and** the contradicted statement's support is zeroed | cost + sanction 1/4 |

All factors are `Fraction`s and compose multiplicatively with the existing `IMPEACHMENT_FACTOR`.

**Why deterministic-given-truth rather than a coin flip.** The brief asks for moves "each succeeding
with a probability driven by the hidden flaw". There are two readings, and they differ in what they
cost:

* **(b) the uncertainty is in the agent's belief, the outcome follows the truth** — exactly how
  objections work today. The judge stays a pure function of the record, permutation invariance holds
  by construction, and nothing new has to be seeded. **Recommended.**
* **(a) the outcome is a seeded roll** — reproducible, but it puts chance inside a rulebook whose
  selling point is that it has none, and it adds an RNG stream whose consumption order becomes part of
  the replay contract. If the team wants it, the roll belongs in the *engine* (recorded in the event)
  and never in the judge, so the judge keeps reading only what is on the record.

The graded factors above give the *effect* of partial success that reading (a) was reaching for,
without the randomness.

**Logging.** One `EventKind.EXAMINATION` event per move, carrying actor, witness, ground, outcome and
the rule fired (`XEX-1` real flaw exposed, `XEX-2` attack failed, `XEX-3` illegal target). It is hashed
like every other event, so `verify_chain` covers it and a replay reproduces the verdict and the digest.
The existing `verify --inject` pattern gives the test shape.

---

## 4. Part C: narrated examination

No new machinery. The existing narrator (`courtroom/llm/narrator.py`) already runs **after** a trial is
decided, over the finished event stream, and returns a `{event_seq: text}` map that is never written
back into the record. Examination events become two more cases in it:

* direct examination → a question and the witness's answer, drawn only from the public record;
* cross-examination → the challenge and its outcome as the judge ruled it.

The guarantees are the existing ones and are already enforced by tests: the verdict and digest are
byte-identical with and without generated text; no core package imports `courtroom.llm`; prompts carry
no hidden flags. The new flaw booleans join `HIDDEN_FLAGS` in `tests/test_llm.py` so a prompt that
leaked "this witness is actually biased" fails the suite.

Cold cache or no key falls back to templates, as now.

---

## 5. What this adds for a course on agents and game theory

This is the part that justifies the work, and it is more than "more features".

**Endogenous information.** Today every agent plays with information of fixed quality: the noisy
channel hands it a posterior and that is that. Cross-examination is a *costly action that improves the
information structure* — a player can spend budget to resolve uncertainty about an opponent's witness.
That turns the game from a fixed-information Bayesian game into one with an information-acquisition
stage, which is the standard setting for the value of information.

**A real portfolio problem.** With A1's diminishing returns and A2's bundling, the budget question
stops being "buy as many facts as I can afford" and becomes "deepen a point I am winning, start a point
I am losing, or attack a witness". Those have different risk profiles: deepening is nearly certain and
nearly worthless at the margin; attacking is a gamble on a 0.567 posterior with a sanction if wrong.

**A measurable conjecture.** A1 should *reduce* the dominance of Aggressive, because its edge comes
from volume, and increase the value of Adaptive, which weighs cost against gain. That is a falsifiable
prediction the sweep can test, and reporting it either way is worth more than a feature.

**Honest limits.** None of this adds a new solution concept. The game stays finite, normal-form and
solved by the same exact support enumeration. What changes is the action space and the payoff shape.

---

## 6. Effect on the 4×4 game, and what regeneration costs

### 6.1 Does the Nash code cope? Yes, measured

`support_enumeration` tries `C(2n,n) − 1` support pairs, each solving two rational linear systems:

| Matrix | Support pairs | `analyze()` measured |
|---|---|---|
| 4×4 | 69 | 5.1 ms |
| 5×5 | 251 | 25.1 ms |
| 6×6 | 923 | 136.8 ms |

Even 6×6 is fast. The binding constraints are elsewhere: `GameRequest.strategies` is capped at
`max_length=4` in `courtroom/api/server.py` and must be raised, and the UI's style picker already
overflows its grid at six options.

### 6.2 Two ways to put witness moves in the strategy space

**Option 1 — extend the four existing profiles (matrix stays 4×4).** Each profile gains a
cross-examination policy: Aggressive attacks on belief ≥ 0.35, Conservative ≥ 0.70, Adaptive by
expected value, Mixed inherits. No new strategy, but **every payoff changes**, so the whole analysis is
regenerated. This is the smaller change and the one I would do first.

**Option 2 — add a fifth strategy (5×5).** An "Examiner" profile that prioritises witness attacks.
It answers a question Option 1 cannot ("is specialising in cross-examination viable?") at the cost of a
bigger matrix and the API/UI changes above.

### 6.3 Regeneration cost, measured (this replaces an earlier estimate that was wrong)

The first version of this section estimated "~4 min single-core, ~10 min with `--workers 4`" from the
1.9 ms trial rate. **That was wrong by a factor of about three.** Measured on this machine (11 cores,
nothing else running except light editing), `python -m courtroom analysis --workers 4`:

| Strategy space | Scope | Wall clock | CPU (user) |
|---|---|---|---|
| 4x4 (today) | all 7 cases | **13 min 56 s** | 18 min |
| 4x4 | `helix-espionage` only | 6 min 30 s | 8.6 min |
| 5x5 (+ `mixed:0.25`) | `helix-espionage` only | 9 min 44 s (**1.50x**) | 12.7 min |
| 6x6 (+ `mixed:0.75`) | `helix-espionage` only | 14 min 39 s (**2.25x**) | 19.0 min |

Stage times at 4x4, all cases: payoff matrices about 45 s, bootstrap about 55 s, **the sensitivity sweep
about 12 min**. The sweep is single-process (D4: constants are patched in the parent, so it cannot use
workers) and re-estimates every matrix at every perturbation, so it is 85% of the bill and it scales
with the number of cells.

Cost grows with cells (n^2), not with Nash enumeration, which stays under 0.15 s at 6x6. Scaling the
full library by the measured ratios gives about **21 min at 5x5 and about 31 min at 6x6**.

Is that too slow to redo late? No: a full regeneration is a half-hour job, not a blocker, and
`--workers` only helps the first two stages. What *would* hurt is regenerating several times in the last
days, because each also forces `RESULTS.md`, the proof-bar ladder in the bundle, the Strategy tab and
the exhibition baseline to be rewritten. Freeze the strategy space early and regenerate once. The
one cheap speed-up available is running the sweep per case in parallel processes, which D4 allows
because each process patches its own constants.

---|---|---|
| Matrix trials | 22,400 | 35,000 |
| Sweep trials | 94,080 | 147,000 |
| Bootstrap `analyze()` | 1,400 × 5.1 ms ≈ 7 s | 1,400 × 25.1 ms ≈ 35 s |
| Rough single-core total | ~4 min | ~6 min |
| Measured wall clock, `--workers 4` | **~10 min** for `analysis`, **5:43** for `export` | expect ~1.5× |

So regeneration is cheap in machine time. **The expensive part is not compute.** Changing the scoring
formula invalidates `RESULTS.md`, the seven-rung proof-bar ladder in the bundle, every equilibrium in
the Strategy tab, and the exhibition's deterministic baseline. All of it has to be rerun and rewritten
*under the flag*, as a second set of results, with the current set left untouched.

---

## 7. Decisions needed before any code

### 7.1 The scoring change is a team decision (new DEVIATIONS entry)

A1 changes `L_e`. The project has treated the judge's arithmetic as off-limits throughout — it is the
basis of "the judge is not an AI" — and three separate instructions in this project have said not to
touch it. Proceeding needs an explicit decision, recorded as a numbered deviation (D12 is now the top-4 cap; a rank-discount would be the next number), covering: which formula changed,
that the three standards and exact arithmetic are preserved, that `rules=None` reproduces the old
behaviour digest for digest, and why the unbounded tail justified the change.

This is also why the flag is not optional. Without it the change would invalidate `RESULTS.md` the way
the turn-order change did, and that has already cost this project one full regeneration.

### 7.2 The second language-model use needs the instructor check

The proposal states the contribution is "a small formal game with **no language model**". One
exception already exists (D8) for narration and the exhibition. Part C extends narration to
examination dialogue. That is the same kind of use, not a new one — the judge still reads nothing the
model writes — but it widens the surface, and the course's AI-usage disclosure should say so before
the work lands rather than after. `AI_USAGE.md` §2 is where it goes.

### 7.3 Smaller calls

* `γ = 2/3` in A1, or A1′'s top-4 cap instead.
* `N = 3` exhibits per bundle in A2.
* Option 1 (4×4) or Option 2 (5×5) in §6.2.
* Whether cross-examination outcomes are deterministic-given-truth (recommended) or a seeded roll.

---

## 8. Work split

Mapped onto the owners in the proposal.

| Engineer | Package | Work |
|---|---|---|
| **E1 Aditya** | `contracts/`, `cases/` | `RuleSet` flag; witness flaw fields; `ARGUE_POINT` and examination action types; author flaws into the three main cases; a new edge fixture for a witness whose flaw decides the case |
| **E2 Divvij** | `procedure/` | Legality for the new actions; one response window per bundled exhibit; once-per-(witness, ground); turn and budget accounting |
| **E3 Lakshya** | `judge/` | A1 rank discount behind the flag; graded credibility factors; `XEX-*` rules; hand-computed fixtures; proof that `rules=None` is unchanged |
| **E4 Mofasser** | `agents/` | `perceive_witness()` on the existing channel; cross-exam policy per profile; the Examiner profile if Option 2 |
| **E5 Rohan** | `gametheory/` | Regeneration under the flag; `γ` in the sweep; 5×5 if Option 2; the Aggressive/Adaptive conjecture in §5 |
| **E6 Pramit** | `engine/`, `api/`, `cli` | `EXAMINATION` events in the chain; replay and `verify` coverage; raise the API strategy cap; a second results file |
| **E7 Rakshit** | `viz/` | Examination in the transcript and the witness board; the style picker at six options; Part C narration |

---

## 9. Four-week schedule

Week boundaries are gates: if a gate is missed, the item below the cut line is dropped, not delayed.

| Week | Work | Gate |
|---|---|---|
| **1** | Flag plumbed end to end with no behaviour behind it. Witness flaw fields and action types defined. A1 implemented behind the flag with hand-computed fixtures. | 42 golden digests green; a trial with `rules=RuleSet()` matches `rules=None` digest for digest |
| **2** | Procedure legality for examination and bundling. Engine events, replay and tamper checks. `perceive_witness()`. | A cross-examined trial replays bit-identically; `verify_chain` and the exhibit-hash check pass |
| **3** | Agent policies. Regeneration under the flag. Comparison of old and new equilibria. | A second results file exists; the old one is byte-identical to what is committed today |
| **4** | UI, Part C narration, `RESULTS.md` under the flag, D12 written, AI-usage disclosure updated. | Full suite green; `vercel build` clean; both rule sets documented side by side |

**Cut line.** If week 2 slips, drop Option 2 (the fifth strategy) and `ARGUE_POINT`, and ship A1 plus
cross-examination only. If week 3 slips, drop Part C: it is cosmetic and the rest stands without it.

---

## 10. Risks

| Risk | Why it is real here | Mitigation |
|---|---|---|
| **The flag leaks** and the certified results move | This project has already lost one analysis to an engine change | The 42 golden digests are the tripwire and run in the suite; week 1's gate is exactly this |
| **Two rule sets to maintain** | Every new test must say which rules it assumes | Parametrise the judge fixtures over both; make `rules=None` the default everywhere |
| **Cross-exam is never used** at accuracy 0.65 | Measured: the posterior after a red flag is 0.567, below Conservative's 0.70 threshold | Report it as a finding; consider a case with higher accuracy rather than retuning the threshold to force the feature to look good |
| **A1 flattens the game** instead of enriching it | If every strategy converges on three exhibits, the matrix may go trivial | Bootstrap and the sweep will say so; `γ` is in the sweep so the effect is measured |
| **Scope**: Part B is the largest single change in the project | Four weeks, seven people, other coursework | The cut line in §9, and Part C is explicitly droppable |
| **Regeneration churn** | Every rerun invalidates the bundle, the ladder and the exhibition baseline | Regenerate once, at week 3, not per change |

---

## 11. Open questions for the team

1. Is bounding the tail worth touching the judge at all? The 2-3 burden already works; `L_e = 22` is
   ugly but it changes no verdict, because the conjunctive test only asks whether each element clears
   its bar. **A defensible answer is "no, do Part B only."**
2. If A1 is adopted, does the top-4 cap (A1′) that the proposal already promises suffice? It is one
   line and closes a documented gap between the proposal and the code.
3. Option 1 or Option 2 for the strategy space.
4. Does the instructor accept narrated examination under the existing D8 exception, or is a fresh check
   needed?
