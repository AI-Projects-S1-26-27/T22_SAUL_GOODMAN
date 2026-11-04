# Legal conformance and case-balance audit

> **Snapshot from before D19.** The balance figures below (win rates, labels, the appendix sweep) describe the plain rulebook, which is now `PLAIN_CASES`. With the shipped adverse events the library's labels and win rates differ; see `docs/CALIBRATION_SWEEP.md` and `RESULTS.md`.

**Status: findings only. No code, case, or formula was changed.** Everything below was measured on branch
`witness-moves` on 20 Oct 2026. Experiments that altered a case (marked *in memory*) were run in a scratch
script against copies; the library is untouched. Scripts are not in the repo; every figure can be re-derived
with `run_trial` and `score_record`.

Method for win rates: the certified 4x4 strategy set (aggressive, conservative, adaptive, mixed:0.5), all 16
pairings, 60 seeds each (960 trials per case). "Prosecution win" means the verdict favours the prosecution or
plaintiff. Utilities are `10 x win - 0.3 x spend - 1.0 x sanctions` (`engine/utility.py:11,14`).

---

## Audit 1: why every case after helix shows about 0% prosecution wins

### Headline

The premise is slightly off, and the cause is different from what was suspected.

| Case | Win rate across the 16 pairings | Verdict | Cause |
|---|---|---|---|
| helix-espionage | 0% to 100%, 11 distinct values | leave as-is | contested, the one healthy case |
| aurora-defi | **0.000 in all 16**, 960/960 directed acquittal | **rebalance** | facts: ceiling below the bar, and intent lost |
| kestrel-av | **0.000 in all 16**, 960/960 directed acquittal | **rebalance (mechanism)** | winnable on the facts; observable late disclosure kills it |
| edge-empty-docket | **0.000 in all 16** | leave as-is | designed fixture: no evidence |
| edge-mutual-exclusion | **0.000 in all 16**, 960/960 not liable | leave as-is | designed fixture: exact cancellation |
| edge-poisoned-tree | 0.000 to 0.167, 9 distinct values | leave as-is | not invariant; works as designed |
| edge-defense-only | **0.000 in all 16** | leave as-is | designed fixture: no prosecution case |

So five of the six are **literally invariant**, not merely low. Three of those five (empty docket, mutual
exclusion, defense-only) are structural fixtures built to show a rule (DV-2 sua sponte, exact tie, defense-only
docket), and `RESULTS.md` reports their 16 equilibria as "all profiles tie" by design. Only **aurora-defi** and
**kestrel-av** are cases that look like contests and are not.

### Is the formula saturating? No

* Perception accuracy is 0.65 (helix, kestrel) and 0.8 (the rest): not pinned near 0 or 1
  (`CaseFile.perception_accuracy`, `contracts/models.py`, default 0.8).
* No log-odds ceiling or floor exists in `score_record` (`judge/scoring.py`); scores are unbounded rationals.
* The new top-4 cap (D12, `judge/scoring.py`, `_cap_facts_per_side`) is **not** the cause: with the cap on or off,
  the prosecution-only ceiling is identical in every case (aurora 7.76 / 1.82 / 3.75; kestrel 5.75 / 2.91 / 5.38).
  No case has more than four facts on one side of an element.
* Not a bug in the new witness code: every figure here uses `rules=None`, and 768 tests including the 42 golden
  digests pass.

### aurora-defi: honest result, two separate problems

Evidence (support, reliability, hidden defects): prosecution `P-TXS` execution 0.95 / 0.99; `P-TXS-DUP` execution
0.90 / 0.95 **same fact as P-TXS**; `P-TRACE` control 0.8 / 0.85; `P-SEED` control 0.95, **illegally obtained**;
`P-KYC` control 0.6, **late**; `P-MIXER` intent 0.7 / 0.85; `P-DEV` intent 0.5 / 0.7, **speculative**; `P-CHAT`
intent 0.55 / 0.6, **unauthenticated**. Defense: `D-BOUNTY` intent -0.6 / 0.95; `D-RETURN` intent -0.75 / 0.95
(contradicts `P-MIXER`); `D-ZHAO` intent -0.5 / 0.8; `D-SHARED` control -0.45 (contradicts `P-TRACE`); `D-DEVBIAS`
intent -0.05 (impeaches `W-DEV`). Budget 11.0, all prosecution items cost 9.5.

1. **The `execution` element cannot be proven by any play.** Even with every prosecution item admitted and no
   defense evidence at all, `execution` is 1.82, below the 2.2 bar. `P-TXS-DUP` shares `fact_id` `onchain` with
   `P-TXS`, so the cumulative-evidence rule counts only one. One fact gives `-1 + 3 x 0.9405 = 1.82`. A single fact
   cannot clear a beyond-reasonable-doubt bar from a -1 prior even at perfect support and reliability (`-1 + 3 = 2`).
   *In memory*, giving `P-TXS-DUP` its own `fact_id` lifts `execution` to **5.73**. That is a one-field tweak.
2. **`fraud_intent` is genuinely lopsided.** With everything admitted it is **-3.14**. Even with a corrected
   `execution`, the prosecution needs about **+5.3 log-odds** on intent. *In memory*: removing `D-RETURN` gives -0.02;
   removing `D-RETURN` and `D-BOUNTY` gives 2.46 (just over the bar). So the defense carries three independent intent
   facts against three defective prosecution ones. Making intent contested means weakening two of three defense
   intent facts or adding two clean strong prosecution ones. That is a **redesign of one element**, not a tweak.
3. Only the clean prosecution items (no illegal, late, speculative, unauthenticated) reach `control` 1.04 and
   `fraud_intent` 0.79; both are below the bar. The strong items are exactly the defective ones.

**Verdict: rebalance** (both fixes are case data, no formula change). Note audit 2(e): if illegally obtained evidence
is admissible, `P-SEED` is clean, which alone lifts `control` from 1.04 to 7.76.

### kestrel-av: winnable on the facts, killed by a mechanism

Evidence: prosecution `P-EYE1` causation 0.6, `P-BUGS` defect **0.8, late**, `P-TAN` defect 0.65 (testimony of
`W-ENG`, credibility 0.6), `P-RECON` causation 0.55 / defect 0.3, `P-MED` damages 0.9, `P-BILLS` damages 0.7,
`P-FORUM` defect 0.4 / reliability 0.3, **hearsay and unauthenticated**. Defense: `D-EYE2` causation -0.6
(contradicts `P-EYE1`), `D-TELEM` defect -0.4 / causation -0.3, `D-NHTSA` defect -0.3, `D-TERM` impeaches `W-ENG`,
`D-HELMET` damages -0.2. Civil, preponderance, bar 0.

Counterfactual (3 prosecution strategies x 30 seeds, scripted defense):

| Defense behaviour | Prosecution wins |
|---|---|
| never objects, offers nothing | **90 / 90** |
| never objects, offers everything | **60 / 90** |
| the real strategies | **0 / 960** |

With everything admitted the prosecution scores defect 3.41, causation 0.38, damages 4.84, so it **wins on the
facts**. The whole 0% comes from objections. `P-BUGS` is the only strong `defect` item and carries `late_disclosure`,
which is in `OBSERVABLE_GROUNDS` (`agents/base.py:109`): the opponent knows it exactly, so it always objects and is
always sustained. Without it, the clean `defect` evidence (`P-TAN`, `P-RECON`) is weak and the directed-verdict
review finds `defect` at about -0.83. This is already documented as **D3** in `DEVIATIONS.md` (the consequence of D1),
and the open question there ("publish as trivial or retune") is still undecided.

**Verdict: rebalance (mechanism).** Options without touching the formula: make `P-BUGS` disclosed and put the
defect on a different exhibit, or strengthen one clean `defect` item. The facts are within about 1 log-odds of
contested.

### The edge fixtures

`edge-empty-docket`, `edge-defense-only` (zero or one weak prosecution document) and `edge-mutual-exclusion`
(`P-A` and `D-B`, equal and opposite, contradicting; `L = 0`, and preponderance is strict, `threshold_met` in `judge/rules.py`) are tests of
rules, not contests. Their 0% is the correct, intended answer. Leave them. `edge-poisoned-tree` is the only edge case
with variation (0 to 16.7%). Its prosecution evidence is mostly illegal, which matters for audit 2(e).

---

## Audit 2: conformance with the Indian-procedure notes

The notes use civil terms (plaint, written statement) and criminal terms (prosecution, evidence stage). Our engine
uses "prosecution/defense" for both case types (`contracts/models.py`, `Side`), so the mapping is ambiguous: see
questions at the end.

| | Point | Status | Where |
|---|---|---|---|
| (a) | Evidence one exhibit at a time, alternating | **conforms** | `procedure/state.py:123` `next_primary_side`; one `evidence_id` per action, `procedure/validator.py:81` |
| (b) | Plaint, statement, issues and burden, evidence, adjourn/dismiss, judgment | **partly; issues not modelled** | below |
| (c) | s.65B certificate | **not modelled** (approximated by `authenticated`) | `judge/admissibility.py:41` |
| (d) | Physical objects need a document or witness | **diverges (5 items)** | below |
| (e) | No exclusion of illegally obtained evidence | **diverges** | `judge/admissibility.py:43-45` |
| (f) | Chief, same-side, cross, hostile | **partly; hostile not modelled** | below |
| (g) | Final arguments, prosecution then defense | **not modelled** | `contracts/models.py:111-121` |
| (h) | New evidence at the argument stage | **not representable** | `engine/trial.py:285-289` |

### (a) Turn structure: confirmed

Evidence alternates side by side, starting with the prosecution, until the prosecution rests
(`procedure/state.py:123-136`, `173`), and each primary action offers exactly one exhibit, followed by the other
side's response window (`engine/trial.py:367`, `procedure/state.py:110`). **This confirms the current design**: note it
in the report as matching the notes. It was introduced as D5 (previously the prosecution presented everything first).

### (b) Procedural flow

Our state machine (`contracts/models.py:111-121`, `procedure/state.py:18`): opening, evidence (alternating), directed-verdict
review, defense case, rebuttal, deliberation, closed.

| Notes | Engine | Status |
|---|---|---|
| Plaint / written statement | `CaseFile` holds `charge`, `synopsis`, `elements`; opening statements are free text with no effect (`engine/trial.py:190,258`) | not a stage; pleadings are static data |
| Judge frames issues and burden | Elements are the issues and are fixed in the case file. No framing step, no event | **not modelled as a step** |
| Burden known at the start | **Yes in the numbers**: event 0 already carries `burden_index` 0.2689 and per-element probability 0.2689, the prior of -1 log-odds (`engine/trial.py:105-131`, `judge/rules.py:49`) | partial |
| Standard of proof announced | Only appears at deliberation as rule `STD-1` (`judge/judge.py:134`); the UI shows it separately | **computed at the end, not announced at the start** |
| Insufficient prosecution evidence: adjourn or dismiss | Directed-verdict review: DV-2 sua sponte, DV-1 on motion at L < 0 (`judge/judge.py:82`, `judge/rules.py:35`) | conforms in spirit |
| Evidence stage then judgment | `Phase.EVIDENCE` to `DEFENSE_CASE` to deliberation | conforms |

Answer to the question: **burden is exposed as a number from the first event, but the bar and who must meet it are
only stated at the end.** A cheap fix is an issues event after the opening, emitting the elements, the burden-bearer
and the bar. It would be a new event and would change every digest if on by default, so it belongs behind the flag.

### (c) Section 65B

Not modelled. The nearest mechanism is `EvidenceItem.authenticated` and `ObjectionGround.AUTHENTICATION`
(`judge/admissibility.py:41-42`), which already excludes any unauthenticated exhibit of any kind. Digital exhibits in
the library: helix 3 (`P-DLP` is unauthenticated), aurora 4, kestrel 1, poisoned-tree 1.

Assessment:
* **(i) attribute plus (ii) new ground** is cheap but mostly **noise**: a certificate flag behaves exactly like
  `authenticated=False` on a `digital_log` item. Adding a field to `EvidenceItem` also changes `digest_item`
  (`engine/audit.py`), so injected-exhibit digests would move unless it is optional and excluded when unset.
* It adds a **real strategic choice only if there is a cure**: a move "file the certificate late" costing budget and a
  turn, usable once, that removes the defect before or after an objection. That makes the defect negotiable and gives
  the offering side a decision, which pure exclusion does not.
* Naming: the Bharatiya Sakshya Adhiniyam 2023 replaced the Evidence Act from 1 July 2024, and as I understand it
  section 63 now plays the role of 65B. **Verify with the source which they mean.**

### (d) Bare physical exhibits: diverges, 5 of them

`EvidenceKind.PHYSICAL` exists (`contracts/models.py:87`) and nothing requires a document or testimony to be attached
(only `TESTIMONY` requires a witness). Items with no `witness_id` and no sibling on the same `fact_id`:

| Case | Exhibit | Owner |
|---|---|---|
| helix-espionage | `P-LAPTOP`, `P-CCTV` | prosecution |
| aurora-defi | `P-SEED` | prosecution |
| edge-poisoned-tree | `P-DRIVE` | prosecution |
| kestrel-av | `D-HELMET` | defense |

All five stand alone. Fix would be case data (add a forensic-report exhibit on the same fact, or a custodian witness)
or a validator rule that a physical item must name a `witness_id`. The first is a content change; the second would
make existing cases invalid.

### (e) Illegally obtained evidence: we model the wrong jurisdiction

`ground_is_valid` makes `ILLEGALLY_OBTAINED` sustainable for prosecution items in criminal cases
(`judge/admissibility.py:43-45`), the offender is sanctioned as bad faith (`engine/trial.py:506`, constant
`SANCTION_BAD_FAITH_EVIDENCE = 2.0`), and agents reason about it (`agents/policies.py:224`). Affected exhibits:
helix `P-LAPTOP`, aurora `P-SEED`, poisoned-tree `P-WIRE` and `P-DRIVE`. A whole fixture, `edge-poisoned-tree`, is built
on this US-style exclusionary rule. As I understand the Indian position (illegally obtained but relevant evidence is
generally admissible, e.g. *Pooran Mal v. Director of Inspection*, 1974), that is a divergence. Removing it is a rule
change (`lawfully_obtained` would stop being an objection ground) and would re-weight `aurora-defi` and the poisoned-tree case.
**Ask the source whether courts keep any discretion to exclude**, since "always admissible" and "admissible subject
to discretion" are different rules.

### (f) Witness sequence

| Notes | Engine | Status |
|---|---|---|
| Examination-in-chief | Offering a `TESTIMONY` exhibit (`engine/trial.py:367`) | implicit |
| Same-side questioning | `EXAMINE` = redirect, undoes the latest exposure (`engine/trial.py:468`, `judge/judge.py:65`) | conforms in spirit, behind `rules.witnesses` |
| Cross-examination on credibility | `CROSS_EXAMINE` on qualifications, bias, inconsistency (`procedure/validator.py:71`, `judge/judge.py:53`) | conforms, behind the flag |
| Impeachment by exhibit | `IMPEACH` (`judge/judge.py:43`) | existing, flag-independent |
| **Hostile witness** | none | **not modelled** |

Hostile witness assessment: a witness called by a side turns against it. It is the clearest missing source of risk,
because today calling a witness is safe: `Witness` carries only `credibility` (`contracts/models.py:188-198`). A model:
a hidden `hostile_risk` on `Witness`; when the testimony is admitted, a deterministic-given-truth rule flips or halves
its support unless the calling side pays to declare the witness hostile and cross-examine its own witness. Cost: a new
hidden field, one rule, one action, a perception channel (reuse `perceive_witnesses`, `agents/base.py`). It is the best
candidate in audit 3. Soundness note: if the flip raises the other side's score, it must be confined to phases before the
directed-verdict review, as examination already is (`procedure/state.py`, `EXAM_PHASES`).

### (g) Final arguments: not modelled

There is no argument phase (`contracts/models.py:111-121`). The closest is `REBUTTAL`: prosecution evidence only,
scope-limited (`procedure/validator.py:94`), running after the defense case (`procedure/state.py:168-169`). So we end
with a prosecution step, whereas the notes end with the defense. Opening statements exist as text only
(`engine/trial.py:258`). Adding speeches that have no scoring effect would be decoration; giving them an effect would
need a new scoring term, which is a formula change.

### (h) New evidence at the argument stage

Injection is permitted only between turns, with no pending exhibit, and only in a phase in `CASE_PHASES`: evidence,
defense case, rebuttal (`engine/trial.py:285-289`). It is not allowed in the directed-verdict review or deliberation.
Unreached injections are reported, not applied (`engine/trial.py:310`, rule `INJ-2`). Two limits matter: a prosecution
exhibit presented in rebuttal must also be a rebuttal target (`procedure/validator.py:94`), and a defense exhibit
with positive support is refused (`engine/trial.py:657`). So injection covers "new development" **only before
deliberation**, and cannot represent a post-argument development because that stage does not exist. The feature is the
right mechanism; the missing piece is the phase.

---

## Audit 3: how different are the strategies in risk?

Utility across all 16 pairings and 40 seeds. Utility spans about -9 to +10. `sd` is the standard deviation of one side's
utility over all pairings and seeds.

| Case, side | Aggressive | Conservative | Adaptive | Mixed 0.5 |
|---|---|---|---|---|
| helix, prosecution | sd 5.63 (-9.1 to 3.8) | **sd 0.00** (always -2.25) | sd 4.34 | sd 3.56 |
| helix, defense | sd 2.11 | sd 4.79 | sd 3.05 | sd 3.92 |
| poisoned-tree, prosecution | sd 5.68 (-7.7 to 8.7) | **sd 0.00** (always 0) | sd 1.53 | sd 4.05 |
| aurora, prosecution | sd 1.11 | sd 0.26 | sd 2.02 | sd 3.05 |
| kestrel, prosecution | sd 0.29 | sd 0.00 | sd 1.36 | sd 1.81 |
| aurora/kestrel, defense | all under 1.0 | all under 1.0 | all under 1.0 | under 1.0 |

Finding: the notes are **right for the lost cases and wrong for the contested ones**.
* In helix and poisoned-tree, risk already differs sharply: Aggressive swings 12 to 16 points, Conservative is a
  constant. Conservative's zero variance is not caution; it never presents (it rests with nothing) and takes a fixed
  loss.
* In aurora and kestrel variance is near zero for everyone, because the outcome is fixed before play. This follows
  from audit 1, not from the strategies.
* There is no move that can fail badly **beyond a bounded penalty**. The worst downside is the 2.0 bad-faith sanction
  and wasted budget.
* The witness work already adds one real gamble: an unfounded cross-examination costs 1.0 plus 0.25 sanction for no
  effect. It shows up in the data (kestrel variant, 270 trials: 39 unfounded crosses against 156 exposed).

### Proposed high-variance moves (not built)

1. **Call a witness who may turn hostile.** Hidden `hostile_risk`; if real, support flips to the opponent at half
   strength on admission. Remedy: pay to declare hostile and cross your own witness. Widens the matrix because Aggressive
   would call every witness, Conservative only low-risk ones, Adaptive weigh belief against upside, which is a genuinely
   new axis.
2. **Offer a digital exhibit that may lack its certificate, with a late cure.** Excluded on objection with a sanction,
   or cured for a fee once. Works only with the cure; otherwise it duplicates `authenticated` (audit 2c).
3. **All-in cross-examination.** Allow crossing on every ground at once for a flat cost; success only if at least
   two flaws are real, failure sanctions heavily. Largest variance, simplest to add on top of the existing code.

**Cost.** Each is a small rules change behind the flag plus a new option in `CounselAgent._primary`
(`agents/policies.py`). The matrix stays 4x4 if added to the four existing profiles, but every payoff changes and the
analysis has to be regenerated: measured **13 min 56 s** at 4x4 and about 21 min at 5x5 if a fifth "risk-taker" profile
is added (see `docs/DESIGN_WITNESS_POINTS.md` section 6.3). Note the dependency: new risk moves only matter if the
cases are contested, so **audit 1 fixes should come first**.

---

## Questions for the source (ambiguous in the notes)

1. Civil or criminal? "Plaint" and "written statement" are civil, "prosecution" and "fruit of the poisonous tree" are
   usually discussed in criminal terms. Which procedure does the demo follow?
2. Do they mean section 65B (Evidence Act) or section 63 (Bharatiya Sakshya Adhiniyam 2023)?
3. Is illegally obtained evidence **always** admissible, or admissible with judicial discretion?
4. Do final arguments come **before or after** any rebuttal evidence, and who speaks last?
5. Can the calling side cross-examine its own hostile witness freely, or only with the court's permission?
6. Should a physical exhibit with no document or witness be treated as inadmissible, or merely weak?

## Decisions needed

* aurora-defi: fix `execution` (one field) and redesign `intent`? Or leave as a deliberate "unwinnable" teaching case.
* kestrel-av: resolve D3 by making `P-BUGS` disclosed, or publish as trivial.
* Remove the exclusionary rule (changes two cases and one fixture) or keep it as a stated US-law assumption.
* Whether to build the hostile-witness move before any further regeneration.

---

## Appendix: how the rebalanced values sit against a measured transition

This replaces the earlier description of the values as "chosen from about 20 configurations". The values were first
found by trial; this appendix measures the curve around them so the choice can be judged against it. Each row is the
full certified procedure (4 strategies, 16 cells, 200 common seeds, 200 bootstrap resamples) on one parameter value.
"Mean win" is the prosecution win rate averaged over the 16 cells. "Label" is the proposal's pure / mixed /
dominance-solvable classification; "label stability" is the share of resamples that keep it; "support stability" is
the share that keep the exact set of equilibrium supports, which is stricter. Scripts: not in the repo.

### kestrel-av: strength of the one clean `defect` exhibit `P-RECALL` (reliability 0.70)

| Support | Mean win | Cell range | Label | Label stability | Support stability |
|---|---|---|---|---|---|
| 0.00 (absent) | 0.0% | 0 to 0% | dominance-solvable | 100% | 100% |
| 0.025, 0.05 | 0.0% | 0 to 0% | dominance-solvable | 100% | 100% |
| **0.075** | 10.0% | 0 to 42% | mixed | 98.0% | 76.5% |
| 0.10, 0.15 | 9.9 to 10.0% | 0 to 42% | mixed | 98.0% | 76.5% |
| 0.20 | 10.1% | 0 to 42% | mixed | 98.0% | 66.5% |
| 0.225 | 10.4% | 0 to 42% | mixed | 98.0% | 53.5% |
| **0.25 (shipped)** | 10.4% | 0 to 42% | mixed | 98.0% | **53.5%** |
| 0.26, 0.27, 0.275 | 99.0% | 91 to 100% | dominance-solvable | 100% | 100% |
| 0.30 to 0.50 | 99 to 100% | 91 to 100% | dominance-solvable | 100% | 100% |

Reading: the transition is two steps, not a slope. Below about 0.06 the prosecution never wins; from about 0.075 to
0.25 it wins about 10% (the contested band); above about 0.255 it wins about 99%. **The shipped 0.25 is inside the band but
at its upper edge, within 0.01 of the cliff.** Inside the band the win rate is flat, so moving down costs nothing
and the support of the mixed equilibrium becomes steadier (76.5% at 0.10 to 0.15 against 53.5% at 0.25).

### aurora-defi: scale on the three defense intent items (`D-BOUNTY`, `D-RETURN`, `D-ZHAO`; 1.0 is shipped)

| Scale | Mean win | Cell range | Label | Label stability | Support stability |
|---|---|---|---|---|---|
| 0.6, 0.8, 0.9, 0.95 | 98.2% | 95 to 100% | pure | 100% | 100% |
| 0.7 | 98.5% | 95 to 100% | dominance-solvable | 100% | 74.0% |
| 0.96, 0.97, 0.98, 0.99 | 5.6% | 0 to 17% | pure | 80.5% | 80.5% |
| **1.0 (shipped)** | 5.6% | 0 to 17% | pure | **80.5%** | 80.5% |
| 1.05 to 1.4 | 5.6 to 6.3% | 0 to 17% | pure | 80.5% | 80 to 80.5% |

Reading: one step, between 0.95 and 0.96. The contested band runs from 0.96 to at least 1.4, so **the shipped value
sits inside it and about 4% above the edge; 1.1 to 1.2 would sit mid-band**. But the instability does not come from the
edge: label stability is 80.5% on the whole band (about 16% of resamples read as dominance-solvable and 3.5% as
mixed). The game is intrinsically fragile because the prosecution wins at most 17% of any cell, so payoff gaps
between strategies are close to sampling noise.

A second parameter, the prosecution's intent strength (`P-LAUNDER`, `P-LOGS`), is also a cliff: x1.1 flips the case to
98% prosecution wins unless the defense scale is also raised to 1.2.

### aurora-defi: litigation budget (defense scale 1.1)

| Budget | Mean win | Cell range | Label | Label stability | Support stability |
|---|---|---|---|---|---|
| 8 | 0.0% | 0 to 0% | dominance-solvable | 100% | 100% |
| 9 | 0.4% | 0 to 3% | dominance-solvable | 100% | 100% |
| **9.5** | 4.5% | 0 to 20% | dominance-solvable | **100%** | **100%** |
| 10 | 4.9% | 0 to 10% | dominance-solvable | 93.0% | 87.0% |
| 10.5 | 5.1% | 0 to 10% | dominance-solvable | 93.0% | 87.0% |
| 11 | 5.8% | 0 to 14% | dominance-solvable | 61.0% | 53.0% |
| 12 | 6.2% | 0 to 17% | pure | 80.5% | 80.5% |
| 13, 14 | 6.2% | 0 to 17% | pure | 80.5% | 80.5% |

### Findings and recommendation

1. **Both shipped values are inside a measured contested band, and both are near an edge.** kestrel-av at its upper
   edge (0.25, cliff at about 0.255). aurora-defi near its lower edge (1.0, cliff at about 0.955).
2. **Stability.** Certified result for the shipped values: kestrel-av label 98.0% / support 53.5%; aurora-defi label
   80.5% / support 80.5%. The kestrel mixed label holds but the exact mixture does not; aurora's label itself is fragile.
3. **kestrel-av: move `P-RECALL` to 0.15.** Same win rate, same label stability (98%), support stability 76.5% instead
   of 53.5%, and 0.10 of margin below the cliff instead of 0.005.
4. **aurora-defi: a stable neighbour exists but it is thinner.** Budget 9.5 with defense scale 1.1 gives 4.5% mean wins,
   100% label and support stability, but the game becomes dominance-solvable (one clear best style per side), which is
   the "trivial" shape D3 objected to. Budget 9.5 also sits next to a second cliff (0.4% at budget 9). No setting found
   is contested, stable and non-trivial at once. Options: accept 80.5% and say so; or accept a dominance-solvable aurora
   and let helix and kestrel carry the mixed-strategy content.
