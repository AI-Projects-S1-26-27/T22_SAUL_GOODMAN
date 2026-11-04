# Deviations from the proposal

Every intentional divergence from `AIPP_Team22_SaulGoodman.pdf`, with the reason.

| # | Proposal says | What the code does | Reason |
|---|---|---|---|
| D1 | Sec. 5: every defect reaches the opponent through a noisy channel (tpr `a`, fpr `(1−a)/4`, prior 0.15). | Late disclosure is observed **exactly** (belief 0 or 1); the other four noisy grounds are unchanged. Relevance was already exact. | Late disclosure is a fact about the record, not an inference from the exhibit: a party knows whether it received the item before trial. Modelling it as a guess let the defense miss an undisclosed exhibit it must have noticed. |
| D2 | Sec. 7: Aggressive "presents even known-defective items (up to two)". | Aggressive still presents defective items, but **no** profile offers an item that is irrelevant as a matter of law (`|support| < RELEVANCE_FLOOR = 1/20` on every element). | Such an item is certain to be excluded if challenged and worth ~0.02 log-odds if not, against a 1.0–2.0 budget cost. The EV (Adaptive) profile already refused it on cost grounds; the non-adaptive ranking ignores `presentation_cost`, so only Aggressive offered it. Strategy profile constants are unchanged. |

## Known limitation, deliberately not changed

`CounselAgent._value_presentation` ranks options by **raw log-odds gain** for the Aggressive and
Conservative profiles; only the Adaptive profile subtracts `presentation_cost`. Making the
non-adaptive ranking cost-aware would change what `min_gain` means (it is calibrated against raw
gain: 1e-9 aggressive, 0.15 conservative), i.e. it would silently redefine the strategy profiles the
proposal specifies. D2 fixes the symptom that motivated the question without touching those
constants. Flagged here rather than fixed.

## D3 — consequence of D1, not retuned

Making late disclosure observable removed `kestrel-av`'s strategic content: `P-BUGS` is the
plaintiff's only support for the `defect` element and is undisclosed, so it is now always excluded
and the plaintiff cannot win under any pairing (win rate 0.00 in all four 2x2 cells, down from 0.56
/ 1.00 on the aggressive row). The case is published as trivial rather than retuned, because editing
a case file to restore a result after measuring it is result-driven case design. The proposal allows
retuning "within documented bounds" as a team decision; `RESULTS.md` section 5 records the one-line
change that would restore a contestable case.

**Superseded by D14**, which made that retune on the user's instruction.

## D4 — sensitivity sweep runs single-process

`sweep()` does not accept a `workers` argument. A `ProcessPoolExecutor` child re-imports
`courtroom.*`, so constants patched in the parent never reach the trials and every variation
silently returns the baseline. This was a real defect in the first implementation, caught because
the sweep reported zero movement everywhere; `test_sweep_variations_actually_bite` now guards it.

## D5 — alternating turns (CP1)

| Proposal says | What the code does | Reason |
|---|---|---|
| Sec. 5, Fig. 2: `Prosecution case -> Directed-verdict review -> Defense case`. The prosecution presents its whole case before the defense begins. | A single `Phase.EVIDENCE` in which the two sides **alternate**, prosecution first. The phase ends the moment the prosecution can present no more; the directed-verdict review fires there. `Phase.DEFENSE_CASE` is now the defense's solo continuation, and `Phase.PROSECUTION_CASE` is retired (kept in the enum so previously exported bundles still parse). | Requested: a trial where one side empties its case before the other speaks does not read like a trial. |

**Why the directed-verdict review survives.** It is sound only because nothing after it can raise
`L_e`. That rests on three premises:

- **P1** the prosecution can present no more. Previously guaranteed by "the prosecution has rested".
  Now guaranteed by the `EVIDENCE` phase's end condition: the phase ends when the prosecution rests,
  stalls on two consecutive passes (`STALL-1`), exhausts its turns (`TURN-CAP`) or can no longer
  afford any action (`BUDGET-1`, new).
- **P2** defense evidence never raises `L_e`. True by construction for the library;
  `test_p2_defense_evidence_can_never_raise_an_element` now enforces it for the generator too.
- **P3** rebuttal adds no new support. **Not enforced — see D7.**

`BUDGET-1` deliberately fires *after* a side has had its turn, not before, so an over-budget attempt
is still caught by the validator (`V-BUDGET`) instead of being silently excused.

Turn caps and consecutive-pass counts are now tracked **per side** rather than per phase, so
alternating does not halve either side's allowance.

## D6 — generator could produce defense evidence that helps the prosecution

`cases/generator.py` gave 8% of items a near-zero "irrelevant or self-defeating" support value drawn
from `[-0.04, +0.04]`, overriding the owner's sign. For a defense item a positive draw breaks P2
above. The range is now `[-0.04, 0]` for defense items and unchanged for the prosecution. Library
cases were never affected.

## D7 — rebuttal can still add support (known, pre-existing, NOT fixed)

The proposal states rebuttal "may only answer defense exhibits ... it cannot add new support for an
element". The engine does not enforce this: `rebuttal_targets()` offers unpresented prosecution
exhibits that contradict admitted defense evidence, and presenting one contributes its full support,
raising `L_e`. Measured on the current corpus this is the sole remaining way `L_e` rises after the
directed-verdict review.

It is **not** fixed here because both available fixes are out of bounds for this checkpoint: zeroing
a rebuttal item's support would change how `L_e` is computed (judge arithmetic, explicitly
off-limits), and forbidding `PRESENT` in rebuttal changes the game again and would invalidate the
analysis a second time. `test_any_post_dv_rise_is_confined_to_rebuttal` pins the gap so it stays
visible and cannot spread to the defense case unnoticed.

For scale: the same measurement on the original code (`git worktree` at `e5e97b2`, 67 cases x 16
pairings, 2,160 element checks) found **21** post-DV rises. After D5 and D6 it is **2**, both from
rebuttal. Alternating turns reduced the problem because most defense evidence is now admitted
*before* the review rather than after it.

## D8 — an optional LLM layer, beside the certified core

**Instructor clearance: verbal, not written.** The instructor cleared the use of a language model in this project verbally on 4 November 2026 (this covers the Gemini and Ollama providers, narration, the exhibition and the verdict explainer). There is no written record of it. The isolation claims below are unchanged: the core imports nothing from `courtroom/llm`, and no model output reaches a verdict, a digest or a payoff matrix.

**Provider: Google Gemini**, model `gemini-3.1-flash-lite`, temperature 0, via `google-genai`.
The Anthropic client that this layer first used has been removed along with its dependency.

Flash-Lite is the cheapest tier on the key. A **pinned** version was chosen over the
`gemini-flash-lite-latest` alias deliberately: an alias can change model underneath a committed
cache, which would quietly destroy the reproducibility the cache exists to give. Tested against
the live key and rejected: `gemini-2.5-flash-lite` (listed by `models.list()` but returns 404
"no longer available") and `gemini-3.5-flash-lite` (intermittent 503, and rejects a thinking
budget with a bare 400). **The API exposes no pricing**, so spend is reported in tokens and the
currency rate is configuration (`COURTROOM_LLM_RATES`), never a quoted price.

Gemini-specific behaviour, each counted separately and never retried forever:

| Outcome | Handling |
|---|---|
| Transient 429 (per-minute) | Exponential backoff, hard cap of 3 retries, then a fallback. |
| **Daily quota 429** | **Not a fallback.** Raises `QuotaExhausted`, the run stops cleanly, the cache is saved, and the next identical run replays finished work as cache hits at no cost. Counting an outage as a fallback would blame the model for the free tier running out. |
| 5xx | Backoff, then counted as an error and a fallback. |
| Safety block or empty candidate | Counted as blocked, falls back. |
| Malformed or out-of-range index | Counted as malformed, re-prompted up to twice, then falls back to Adaptive. |

Action choice uses **structured output** (`response_schema`, JSON mime type) over an index into a
list of legal actions the policy enumerates itself, so an illegal move cannot be expressed at all.


The proposal's stated contribution is "a small formal game with **no language model**, an exact
judge, and a game-theory layer whose equilibria we can check". A language model now appears in the
repository. It is an **addition beside** that core, not a replacement for any part of it, and the
separation is enforced by tests rather than by intention:

| Guarantee | How it is enforced |
|---|---|
| The judge never reads generated text. | Narration runs over a **finished** `TrialResult`; the trial is fully decided, scored and hashed before a word exists. `test_verdict_is_byte_identical_with_and_without_argument_text` runs a trial, narrates it with a client that always answers, and asserts the whole `TrialResult` JSON and digest are unchanged. |
| Generated text never enters the record. | `narrate()` returns a separate `{event_seq: text}` map. `test_narration_is_not_stored_on_the_trial_record` asserts the result object is untouched. |
| The core cannot depend on the layer. | `test_engine_and_judge_do_not_import_the_llm_package` greps `engine/`, `judge/`, `procedure/`, `gametheory/`, `agents/`, `cases/` and `contracts/` for any import of `courtroom.llm`. Deleting `courtroom/llm/` breaks nothing certified. |
| Prompts carry only the public record. | `test_narrator_prompt_leaks_no_latent_defect` and `test_public_item_description_carries_no_latent_defect` assert no exhibit's hidden flags reach a prompt. An objection *ground* is exempt, because it is spoken aloud in court. |
| The demo cannot be broken by a network failure. | No key, no SDK, no cache entry or any exception → `complete()` returns `None` and the caller uses a template. |

**Reproducibility, stated plainly.** A cache *hit* is deterministic. A cache *miss* on another
machine calls the provider, and providers do not guarantee identical output across time or model
revisions even at temperature 0. Nothing produced by this layer is therefore eligible for the
payoff matrices, the bootstrap or the sweep, and none of those were regenerated or extended.

**Spend controls.** `MAX_CALLS_PER_TRIAL = 40`, `MAX_CALLS_PER_RUN = 400`, `max_tokens = 160` per
call. Every run prints calls, cache hits, unavailable calls, tokens and an estimated cost. The USD
rate is a configurable placeholder (`COURTROOM_LLM_RATES`), not a quoted price.

## D9 — the proof standard's bar is a parameter (touches the judge's code path, not its arithmetic)

Requested: "standards 11/5, 11/10, 0 as game parameters, not hard-coded". Before this, the bar was
read in five places as `THRESHOLD_LOG_ODDS[case.standard]` (`judge/scoring.py`, `judge/judge.py`,
`agents/base.py`, `engine/trial.py`) and was retyped as constants in `app.js`.

What changed: `CaseFile` gained an optional `bar_log_odds` (an exact rational string, validated to
lie between 0 and 7), and the five reads now go through `judge.rules.threshold_for(case)`. With no
override it returns exactly `THRESHOLD_LOG_ODDS[case.standard]`. The standard still decides whether a
tie passes (strict for preponderance, inclusive otherwise). The page now reads the standards from
`/api/rules` (or the bundle's copy of it) instead of its own constants.

What did **not** change: the formulas for `S_i`, `d_i`, `c_i` and `L_e`, and the three constants.
The guarantee is empirical and enforced, not asserted: `tests/test_golden.py` pins 42 digests
recorded **before** the change, and all 42 are identical after it.

`override_for_bar` treats a requested bar within the same whole percent as the standard's own as
"no override", so choosing 90% on a beyond-reasonable-doubt case keeps the exact 11/5 rather than a
rounded 2.1972. Without that, the slider would have silently nudged borderline verdicts the moment
anyone touched it.

Two limits worth knowing. First, the agents' `Oracle` reads the same bar, so lawyers play the game
they are in; "same evidence, different bar" and "lawyers who know the bar" are therefore different
questions, and the page presents them separately. Second, the precomputed ladder in the bundle has
seven rungs, so it is a coarse picture of how the equilibrium depends on the bar.

## D10 — evidence can be added mid-trial (a new event kind and two new rules)

Requested: "live evidence injection: logged in the hash-chained event stream, replay-identical".

**Where it lives.** `EventKind.INJECTION` is new, and so is `status = "injected"`. The exhibit itself
is **not** a field on the event, because `TrialEvent` is hashed field by field and any new field
would have changed every digest ever produced. Instead the event carries the exhibit's SHA-256 in
rule `INJ-1`, and the full exhibit rides on the result as `TrialResult.injections`.
`verify_injections` checks that each recorded exhibit is the one the chain committed to: editing the
event breaks `verify_chain`, and editing the exhibit afterwards breaks `verify_injections`.
`tests/test_injection.py` includes a forgery that rewrites the event *and* re-chains it, to show the
second check is not redundant.

**When it lands.** The point is "after the trial has produced N events". The engine applies it at
the next primary turn, never inside a response window, so an objection is always ruled on against
the case as it stood when the exhibit was offered. If the trial leaves the evidence phases first,
rule `INJ-2` records that, with the same hash, instead of silently dropping the exhibit.

**A bug the test suite found in my first version.** I recorded only the injections that had been
applied. Replaying such a result silently dropped an input whenever the trial ended before the
injection point: the empty-docket and defense-only cases diverged. A result now carries every
injection that was *requested*, because an unapplied one still shaped the trial by producing
`INJ-2`. `test_a_late_injection_is_still_an_input_so_the_replay_must_include_it` pins it.

**A rule I added.** A defense exhibit may not have positive support for any point. The
directed-verdict review is sound only because defense evidence can never raise an element's
log-odds (D5, D6); allowing an injected defense exhibit to do so would have let anyone reopen the
hole D6 closed. The mirror case, a prosecution exhibit that hurts the prosecution, is allowed: it is
foolish, not unsound.

**Limits.** Three injections per trial. An injected exhibit joins its owner's hand and can be
offered only while that owner is still presenting, so adding prosecution evidence after the
prosecution has rested changes nothing, and the page says so. It needs the local simulator: the
static demo has no engine to replay with.

## D11 — the LLM opponent mode is a cache-only replay, and the page never opens in it

**Instructor clearance: verbal, not written.** The instructor cleared the use of a language model in this project verbally on 4 November 2026 (this covers the Gemini and Ollama providers, narration, the exhibition and the verdict explainer). There is no written record of it. The isolation claims below are unchanged: the core imports nothing from `courtroom/llm`, and no model output reaches a verdict, a digest or a payoff matrix.

Requested: a deterministic-versus-LLM-exhibition toggle whose LLM mode "must use the cache only and
show a clear 'exhibition, not equilibrium' label".

**How it is cache-only.** The exhibition is data, not a service. `courtroom/viz/web/data/exhibition.js`
holds 40 trials replayed from the committed response cache with `allow_network=False`, built by
`python -m courtroom export-exhibition`, which needs no key. The page loads it on demand when the
mode is switched on, and reads trials from it; it never sends an exhibition request to the engine,
because the engine has no `llm` strategy and the page must not try. `tests/test_ui_smoke.py` runs the
real page against a fake API and fails if any request names the LLM strategy, and a mutation test
proves the check fails when the page is made to ask the server.

**A behaviour I changed.** `/api/narrate` used to build its client with the network on, so a server
that happened to hold a Gemini key could have spent money on a page view. It is now cache-only, and
`test_narration_never_reaches_the_network_even_when_a_key_is_set` booby-traps the SDK to prove it.

**What the mode does and does not offer.** One case (the one that was played), seeds 0 to 4, either
seat, against each fixed style. Adding evidence, moving the bar, recomputing a matrix and the
certified analysis are all hidden, and their handlers are guarded as well as their buttons: a hidden
button is not a safeguard, and the smoke test found that the replay-at-a-bar handler would still have
sent `llm` to the server. The Strategy tab shows the model's own results in place of the matrix,
labelled "not equilibrium analysis", with the four fixed styles in the same seat for comparison.

**The page always opens certified.** The mode is deliberately not remembered, so a shared link or a
screenshot cannot open in the exhibition by accident.

**Honest limits.** The replay is exact for the 40 trials in it and says nothing about any other
case. Four requests in it missed the cache because they were rate-limited when recorded; they were
re-asked, none fell back, and the page reports the count. The mode needs no key, but it also cannot
produce a new trial: that takes the local `llm-exhibition` command and a key.

## D12 — the top-4-facts cap on Fe (a conformance fix, not a new rule)

Proposal Sec. 6: "Fe is the four facts with the largest |v| per side, so splitting one fact into many
cannot inflate the score." The judge never implemented the cap. The cumulative-evidence rule (one
counted item per `fact_id`) covered *splitting one fact*, but distinct facts each added a flat
`+3 * w` without limit, so a side could buy log-odds by exhibit count.

**Change.** `rules.MAX_FACTS_PER_SIDE = 4`; `scoring._cap_facts_per_side` keeps, per sign, the four
counted facts with the largest |w| (ties by id). Set the constant to `None` to reproduce the old
judge exactly. No new tuned constant: 4 is the proposal's number.

**Why this is a bug fix and not a scoring change.** The submitted spec states the rule; the code
did not match it. On the seven library cases the cap changes nothing: 875 trials, 0 digest and 0
verdict differences (`test_no_library_trial_changes_with_the_cap_on_or_off`). It does bite on
generated cases (16 of 1,500 digests move, 0 verdicts), which is what a tail rule should do.
RESULTS.md and the 42 pinned digests are unaffected.

**Effect on the tail** (one criminal element, s=0.8, reliability 0.8, k counted facts, L_e):

| Exhibits per side | before | after |
|---|---|---|
| 4 | 10.04 | 10.04 |
| 6 | 16.10 | 10.40 |
| 8 | 21.98 | 10.49 |

Not zero growth: corroboration `k` still counts every same-sign fact (the proposal defines it so), so
the four counted facts get a multiplier that saturates below 3/2.

**Two other spec divergences, measured and NOT changed.** (a) The proposal nets per fact
`max[v]+ - max[v]-`; the code keeps the single largest |w| per fact. No library fact has opposite-sign
items on one element, so there is no effect today. (b) The proposal writes strict `Le > theta`; the
code is strict only for preponderance. The 144 elements landing exactly on a bar are all civil
preponderance, so there are 0 disagreements. Either would be a scoring change needing a team decision
if a case ever exercised it.

## D13 — witness examination: direct and cross-examination, behind `RuleSet.witnesses`

Requested: witnesses with hidden flaws, cross-examination whose success depends on them, and the
language model only narrating the exchange. This **reverses** an earlier instruction ("don't add
cross-examination; impeachment already covers it"), which is why it is logged.

**The fence.** `CaseFile.rules` is `None` by default, which is the certified rulebook. Every library
case has `rules=None`; the three examination variants live in `WITNESS_CASES`
(`courtroom/cases/witness_cases.py`), not `CASES`, so the analysis, `RESULTS.md` and the bundle never see
them. With the flag off, an `EXAMINE`/`CROSS_EXAMINE` action is refused as `V-WINDOW`. The 42 pinned
digests and the bundle freshness test pass unchanged, and 768 tests pass.

**What was added, and what it could have broken.**

| Addition | Why it cannot move a certified digest |
|---|---|
| `ExamGround` (qualifications, bias, inconsistency) is a **separate enum** | `perceive()` and the chaos fuzzer iterate `ObjectionGround`; a new member there would change every RNG stream |
| `ActionType.EXAMINE`, `CROSS_EXAMINE`; `EventKind.EXAMINATION` | never emitted when the flag is off |
| `ChaosAgent` now samples a fixed six-action tuple | it used `list(ActionType)`, which the new members would have lengthened. Caught by a mutation check (`test_bundle` fails if reverted) |
| witness perception uses `Random(f"{seed}:witness-perception")` | a separate stream, drawn only when the flag is on, for every witness in sorted order, so it is a pure function of (case, seed) |
| `Action.ground: ObjectionGround \| ExamGround \| None` | serialises to the same string for every existing action |
| `PartyView` and `Witness` gain defaulted fields | neither is hashed |

**Rules.** Cross-examination costs 1.0, direct examination (redirect) 0.5, once per (witness, ground) and per
witness; both need the witness to have testified, and both are refused in rebuttal (`V-EXAM-PHASE`).
A cross succeeds **exactly when the named flaw is real** (`XEX-1`), multiplying the witness's credibility
by 1/3 (qualifications), 1/2 (inconsistency) or 2/3 (bias); a cross on a flaw that is not there fails
(`XEX-2`) and costs 0.25 sanction points. Redirect withdraws the most recent exposure (`XEX-4`) or does
nothing (`XEX-5`). The factors are exact rationals and compose with each other and with impeachment.
Exposures ride in the impeachment ledger under `"<witness>#<ground>"`, so `score_record`'s signature and
the oracle cache are unchanged, and the score stays a pure function of the record.

**Uncertainty is in the belief, not the outcome.** Agents see each flaw through the objector's channel
(true-positive rate = accuracy, false-positive rate = (1 - accuracy)/4, prior 0.15). The ruling follows
the truth. Cross-examination reuses each profile's objection thresholds (0.35, 0.70; the EV rule for
Adaptive), so it adds no new risk parameter.

**Soundness of the directed-verdict review (P1, P2) is preserved.** A cross can only lower the side that
called the witness; because examination is refused in rebuttal, everything after the review is the
defense's cross of a prosecution witness or the defense repairing its own, and both can only lower
L_e. Tested exhaustively on every prosecution and defense witness and ground
(`test_exposing_a_witness_only_ever_hurts_the_side_that_called_it`) and along every trial
(`test_no_examination_can_raise_the_prosecution_after_...`).

**Simplifications against `docs/DESIGN_WITNESS_POINTS.md`, stated plainly.** `INCONSISTENCY` halves
credibility but does **not** also zero a contradicted statement (that needs a designated prior-statement
item the case format does not have). `QUALIFICATIONS` is a credibility factor of 1/3, not an
"opinions outside the field stop counting" rule (the format has no field-of-expertise). Either can be
added later; neither is needed for the strategic content.

**What the agents do with it** (3 strategies each side, 30 seeds, 270 trials per case):

| Case | Verdict flips vs the same case without the rules | Notes |
|---|---|---|
| `helix-espionage-witnesses` | 0 | only Aggressive and Adaptive ever cross; **Conservative never does** (posterior after a red flag is 0.567, below its 0.70 bar, as predicted) |
| `aurora-defi-witnesses` | 0 | 142 exposures, 39 repairs; the prosecution already loses every trial |
| `kestrel-av-witnesses` | 11 | 3.9% of trials change outcome; Aggressive makes 213 examination moves, Conservative 40 |

The conjecture that examination helps the profile that gambles on thin suspicion is visible here but
**is not an equilibrium result**: no game has been solved with the rules on, and `RESULTS.md` is
unchanged. That would be a second, opt-in analysis and is not done.

**Language model.** `courtroom.llm.narrator` writes a Q-and-A line for each examination event from the
public ruling only. The prompt names the line of questioning and the outcome the judge announced; it
never carries a witness's flaw flags (`test_examination_prompts_carry_the_public_record_and_never_a_hidden_flaw`),
and no core package imports `courtroom.llm` (`test_no_core_package_imports_the_language_model_layer`).
Template fallback with no key or cold cache. **This is a second narrated move type, not a new kind of
language-model use**; the instructor cleared the use of a language model verbally on 4 November 2026 (not in writing).

**Not done.** The web case list does not offer the witness variants and the exhibition bundle contains no
examination trials. The Gemini policy agent is not told about the new moves. The strategy space is
still the certified 4x4; see `docs/DESIGN_WITNESS_POINTS.md` section 6 for what widening it costs.

## D14 — `aurora-defi` and `kestrel-av` rebalanced (case data only; this IS result-driven case design)

> **Superseded by D19 (calibration sweep).** The admission below stands as written: the values were chosen by measuring, after D3 had refused to. D19 replaces the process with a measured sweep, finds that with adverse events on neither case can be contested by either value, and leaves the values as they were.

Requested after `docs/LEGAL_AND_BALANCE_AUDIT.md` showed both cases ended in a directed acquittal in all 960
trials. D3 had refused to retune `kestrel-av` precisely because editing a case after measuring it is
result-driven. That objection stands and is not answered: the values below were **chosen by measuring**, by trying
about 20 configurations and keeping one that lands in a contested band. No formula, constant or rule changed.

**aurora-defi** (two independent causes, audit section 1):
* `execution` could never clear the bar: both on-chain items share one fact, and one fact gives at most 1.82 against
  2.2. Added an independent fact, `P-CALLTRACE` (0.85 / 0.9). `P-TXS-DUP` is unchanged, so the cumulative-evidence
  test still holds.
* `control`'s strong items were all defective (`P-SEED` illegal, `P-KYC` late), so added the clean `P-IP` (0.7 / 0.85).
* `fraud_intent` was -3.14 with everything admitted. Added the clean `P-LAUNDER` (0.9 / 0.92) and `P-LOGS`
  (0.75 / 0.9, contradicts `D-ZHAO`); softened the defense by `D-BOUNTY` -0.60 to -0.42 ("if reported first"),
  `D-RETURN` -0.75 to -0.45 (22M of 31M returned), `D-ZHAO` -0.50 to -0.45.
* `budget` 11 to 12 and `max_primary_turns` 7 to 8: with seven turns the extra exhibits could not all be offered
  and the win rate stayed at 0 to 3%.

**kestrel-av**: added one clean `defect` exhibit, `P-RECALL` (0.15 / 0.70). `P-BUGS` stays undisclosed, so the late-disclosure
gamble remains and is now an upside, not the only route.

**Measured result** (200 seeds per cell, certified analysis): `aurora-defi` prosecution wins 0 to 16.5%, two pure equilibria,
no dominant strategy, label stability 80.5%. `kestrel-av` wins 0 to 42%, one mixed equilibrium, not trivial, stability 98.0%.
Helix and the five edge fixtures are untouched; their results are identical.

**Fragility, stated plainly.** Both cases sit near a cliff. In `kestrel-av`, a clean defect exhibit of 0.275 or more gives
the prosecution 99 to 100% in every cell; 0.075 to 0.25 gives about 10%, so `P-RECALL` was moved from 0.25 to **0.15**, the
middle of the measured band (the audit appendix has the sweep). In `aurora-defi`, a small further strengthening of the intent
evidence also flips it to 100%. The published values are a narrow band, not a robust design.

**What moved.** 11 of the 42 pinned digests (all aurora and kestrel entries; helix and the edge cases are unchanged) and
the bundle, regenerated deliberately. `results/*.json`, `RESULTS.md` sections 2 to 4 and 7 and the web bundle were regenerated.
`README.md` still quotes older test counts.

## D15 — seeded adverse events behind `RuleSet.adverse_events`

> **Partly superseded by D19.** "The certified library never has it" no longer holds: four library cases now ship with these events on, at the rates chosen by the sweep. The plain library is `PLAIN_CASES`. The `-adverse` variant registry and `results/adverse/` were removed because the shipped cases are those variants.

Requested to give the strategies real risk: moves that can fail through no fault of the player. Three events, each
drawn from a stream seeded `"<seed>:adverse"` and logged as an `ADVERSE` event in the hash chain:

| Event | Fires when | Effect | Rule |
|---|---|---|---|
| Witness no-show | a testimony exhibit is offered (default 10%) | exhibit excluded, cost not refunded, turn spent | `ADV-1` |
| Missing 65B certificate | a `digital_log` exhibit is offered (default 15%) | excluded by the court without objection, no bad-faith sanction | `ADV-2` |
| Hostile witness | a witness's testimony is admitted, once per witness (default 10%) | credibility x1/4 (exact), testimony **not** flipped | `ADV-3` |

**The fence.** Off by default; the certified library never has it. The events live in `courtroom/cases/adverse_cases.py`
(`ADVERSE_CASES`: helix, aurora, kestrel and poisoned-tree variants), reachable through `get_case`. The stream is created
per trial but a certified case never draws from it. With the flag on and every rate at zero a trial's digest equals the plain
trial's (`test_every_rate_at_zero_reproduces_the_plain_trial_exactly`), and a mutation that shared the perception stream
fails that test.

**Why a new stream and not the existing one.** The instruction was to draw from the trial's RNG so replays hold. Replays do
hold, the draws being a pure function of (seed, trace). Using the *objection-perception* stream would have shifted every
perception draw as soon as an adverse draw was inserted between them, which changes behaviour of the existing channel;
a separate stream seeded from the same trial seed avoids that.

**Soundness.** The directed-verdict review needs "nothing afterwards raises the prosecution". Events only remove or
down-weight evidence at the instant of offer or admission, so a defense exhibit lost after the review leaves L_e at or below its
review value. Tested along every trial (`test_no_adverse_event_can_raise_the_prosecution_after_...`).

**Not modelled.** The side that called a witness cannot respond to hostility (declare it, cross its own witness) and cannot
re-summon a no-show. `ADVERSE` events with a single party are narrated as the offer that failed; hostility has no actor and is
not narrated.

**Agents.** Only Adaptive reads the published rates (`PartyView.adverse`, empty on every certified case) and discounts an
exhibit's gain by its survival probability. Aggressive and Conservative ignore the risk, so the difference between them is part
of what is measured.

**Measured: payoff standard deviation per strategy** (utility, over 4 opponents x 60 seeds; same seeds, adverse variant against the
plain case; kestrel at `P-RECALL` 0.15):

| Case | Side | Strategy | sd before | sd after | mean before | mean after |
|---|---|---|---|---|---|---|
| helix-espionage | prosecution | aggressive | 5.73 | 5.34 | -2.84 | -3.92 |
| helix-espionage | prosecution | conservative | 0.00 | 0.08 | -2.25 | -2.23 |
| helix-espionage | prosecution | adaptive | 4.32 | 4.39 | -0.46 | -1.02 |
| helix-espionage | prosecution | mixed:0.5 | 3.85 | 3.63 | -2.64 | -3.17 |
| helix-espionage | defense | aggressive | 1.74 | 0.98 | 4.64 | 4.98 |
| helix-espionage | defense | conservative | 4.76 | 4.91 | 1.78 | 2.89 |
| helix-espionage | defense | adaptive | 2.83 | 2.57 | 5.69 | 5.92 |
| helix-espionage | defense | mixed:0.5 | 3.87 | 3.60 | 3.23 | 3.99 |
| aurora-defi | prosecution | aggressive | 3.70 | 3.64 | -4.40 | -4.34 |
| aurora-defi | prosecution | conservative | 0.33 | 2.65 | -2.76 | -2.04 |
| aurora-defi | prosecution | adaptive | 3.29 | 3.54 | -2.31 | -2.23 |
| aurora-defi | prosecution | mixed:0.5 | 2.71 | 3.25 | -3.47 | -3.22 |
| aurora-defi | defense | aggressive | 1.97 | 2.98 | 4.67 | 4.55 |
| aurora-defi | defense | conservative | 2.82 | 2.97 | 6.59 | 6.47 |
| aurora-defi | defense | adaptive | 2.82 | 3.10 | 6.59 | 6.38 |
| aurora-defi | defense | mixed:0.5 | 2.60 | 3.06 | 5.64 | 5.42 |
| kestrel-av | prosecution | aggressive | 3.93 | 4.82 | -3.78 | -2.48 |
| kestrel-av | prosecution | conservative | 0.00 | 3.77 | -2.10 | -0.41 |
| kestrel-av | prosecution | adaptive | 3.05 | 4.80 | -2.83 | -1.00 |
| kestrel-av | prosecution | mixed:0.5 | 2.78 | 4.45 | -2.85 | -1.46 |
| kestrel-av | defense | aggressive | 0.93 | 3.54 | 6.33 | 4.86 |
| kestrel-av | defense | conservative | 4.12 | 4.59 | 5.93 | 4.95 |
| kestrel-av | defense | adaptive | 1.57 | 3.72 | 7.24 | 5.78 |
| kestrel-av | defense | mixed:0.5 | 2.98 | 3.95 | 6.07 | 4.90 |
| edge-poisoned-tree | prosecution | aggressive | 5.16 | 5.11 | -4.78 | -4.54 |
| edge-poisoned-tree | prosecution | conservative | 0.00 | 0.00 | 0.00 | 0.00 |
| edge-poisoned-tree | prosecution | adaptive | 1.86 | 1.78 | -0.87 | -0.96 |
| edge-poisoned-tree | prosecution | mixed:0.5 | 4.18 | 4.09 | -1.98 | -1.88 |
| edge-poisoned-tree | defense | aggressive | 2.14 | 2.14 | 9.04 | 9.05 |
| edge-poisoned-tree | defense | conservative | 2.56 | 2.50 | 8.86 | 8.91 |
| edge-poisoned-tree | defense | adaptive | 2.56 | 2.50 | 8.86 | 8.91 |
| edge-poisoned-tree | defense | mixed:0.5 | 2.40 | 2.40 | 8.95 | 8.96 |

Reading: the events create risk where it was missing and add little where it already existed. Kestrel's sd rises for every
strategy (Conservative 0.00 to 3.77); aurora's Conservative prosecution goes 0.33 to 2.65; helix, which was already volatile, barely
moves (Aggressive prosecution 5.73 to 5.34); poisoned-tree has one witness and one digital record and is unchanged.

**Measured: equilibria with the events on** (certified procedure, 200 seeds, `results/adverse/`):

| Case | Certified | With adverse events |
|---|---|---|
| helix-espionage | mixed, Conservative and Adaptive both sides, stability 100% | **same supports**; prosecution wins 0 to 68.5% (was 0 to 100%) |
| aurora-defi | pure, 2 equilibria, stability 80.5% | **dominance-solvable**, Conservative both sides, stability 100%; wins 11 to 23% |
| kestrel-av | mixed, stability 98.0% | **dominance-solvable**, Conservative both sides, stability 99.5%; wins 17.5 to 42% |
| edge-poisoned-tree | pure, 4 equilibria | unchanged |

Adding risk made two cases *more* stable and *less* strategic: when a play can fail at random the cautious profile
dominates, so the matrix collapses toward Conservative. That is a result worth stating, and it is the opposite of the hoped
for "more strategic variety". Helix keeps its mixed equilibrium.

### D15 addendum: adverse events the examiner pushes in (step 2)

`POST /api/adverse` and a panel on the Courtroom tab ("Push an adverse event mid-trial") mirror evidence injection.
`AdversePush(at_seq, kind, target)` lives on the trial result, never on a hashed event, so no digest moves; every push
requested is recorded, applied or not, and `replay_trial` reproduces the trial from it.

* `no_show` / `missing_certificate` name an exhibit not yet offered and take effect when it is offered. `hostile` takes
  effect now if the witness has testified, otherwise on admission. Pushes are forced, draw no randomness, and work on a
  certified case with no flag.
* Each push is **announced** as a logged `ADVERSE` event (`ADV-4`), so both sides know. Agents see only the public
  announcement (`PartyView.known_adverse`), never the armed state.
* **Refused rather than applied:** an exhibit already offered, a witness already hostile, a hostile push on a defense witness
  after the directed-verdict review (it would help the prosecution after the point where the review is sound), and a push the
  trial never reaches (`ADV-5`).
* **Adaptive reacts, the others do not.** The expected-value profile prices an announced exhibit at survival 0 (or a hostile
  witness at 0.25) and stops offering it; Aggressive and Conservative ignore the announcement and walk into the failure. The page
  shows, per side, the first decision that changed, the announcement behind it, and the lawyer's own logged rationale. It is
  computed from two finished trials (`engine/reaction.py`); no language model is involved.

Measured on `helix-espionage`, Adaptive v Adaptive, seed 0: a missing-certificate announcement for `P-VPN` makes the
prosecution offer `P-EXPERT` instead (the verdict goes from guilty to a directed acquittal); Aggressive still offers `P-VPN`
and loses it to exclusion.

## D16 — a generated case brief at the start of every trial (no rule changed)

Answers the audit's point that the burden was computed at the end and never stated at the start
(`docs/LEGAL_AND_BALANCE_AUDIT.md`, 2b). `courtroom/judge/brief.py` builds, from a case file and the judge's own constants:
the story and charge, the issues as the court frames them (the case's own elements, in order), who carries the burden, the
standard in plain words with its bar and tie rule, the starting presumption, what each side must or may do, the docket
(exhibit and witness counts, budget, turns), how the judge weighs, and any published risks (witness examination, adverse
events). It is shown as the opening screen of the Courtroom tab and folds away once the trial moves on.

* **It cannot drift.** Every number is read from `threshold_for`, `PRIOR_LOG_ODDS` and `judge.rules` at build time
  (`test_the_brief_follows_the_judges_constants_when_they_change` patches them and watches the text change), and the issues are
  the case's elements (`test_the_issues_are_the_cases_own_elements_in_order`). The shipped bundle's briefs are checked
  against the engine (`test_the_shipped_bundle_holds_the_brief_the_engine_builds_now`).
* **It carries nothing hidden:** no exhibit ids, titles or flags, no witness flaws.
* **No digest, verdict or result changed.** It is a read-only view; the bundle gained a `briefs` key and nothing else.
* Served by `GET /api/brief/{case_id}` and `POST /api/brief` (a custom case at a chosen bar); the static page reads the bundle.
* **Wording choice to check with a lawyer:** civil cases still say "prosecution side" for the plaintiff, because the engine uses
  one pair of side names for both case types.

## D17 — Ollama as a second language-model provider (exhibition only; no result changed)

**Instructor clearance: verbal, not written.** The instructor cleared the use of a language model in this project verbally on 4 November 2026 (this covers the Gemini and Ollama providers, narration, the exhibition and the verdict explainer). There is no written record of it. The isolation claims below are unchanged: the core imports nothing from `courtroom/llm`, and no model output reaches a verdict, a digest or a payoff matrix.

`courtroom/llm/ollama.py` adds `OllamaClient`, a subclass of the Gemini `LLMClient` that swaps only the transport (a local HTTP
call to `/api/chat`). The cache, the per-trial and per-run caps, the usage counters and the never-raises rule are inherited.
Selection is by `COURTROOM_LLM_PROVIDER` or `--provider`; `make_client` is the one place that decides.

* **Separate everything.** Cache keys carry `ollama/<model>` and the default file is `responses.ollama.json`; results go to
  `results/llm_exhibition_ollama.json`. The shipped Gemini cache, results and `exhibition.js` are byte-identical to before
  (`test_the_shipped_gemini_exhibition_is_byte_for_byte_what_it_was`), and exporting an Ollama exhibition refuses to replace them
  without `--force`.
* **Replayable.** A live run writes to the cache; a later run with the network disabled reproduces the same trial and digest.
* **Same label.** Exhibition, not equilibrium analysis. Local inference is not bit-stable across hardware, so a cold-cache rerun can differ.
* **Never fatal.** A server that is down, a model that is not pulled, a timeout, an empty answer and a malformed index are each counted
  and become a fallback, with the fix in the message (`ollama serve`, `ollama pull`).
* **A logged rationale changed shape.** The policy's rationale now reads `[<provider>] chose option ...`; for Gemini it is still
  `[gemini]`, so no committed trial changed.
* **Not verified against a real server.** Ollama is not installed on the development machine; the wire format follows Ollama's
  documented API and is tested against a stub only. `docs/OLLAMA.md` has the model recommendation, the one-time setup and the
  pre-demo check.

## D18 — "Why did it rule that way?": a verdict explainer that reads the record and cannot change it

**Instructor clearance: verbal, not written.** The instructor cleared the use of a language model in this project verbally on 4 November 2026 (this covers the Gemini and Ollama providers, narration, the exhibition and the verdict explainer). There is no written record of it. The isolation claims below are unchanged: the core imports nothing from `courtroom/llm`, and no model output reaches a verdict, a digest or a payoff matrix.

A button on the Verdict tab writes a plain-language account of the verdict (`courtroom/llm/explainer.py`, `POST /api/explain`).

* **Read-only by construction.** `build_facts` copies the judge's own snapshot (scores, bars, probabilities, counted exhibits) and the
  public events (exclusions, credibility changes, adverse events) out of a *finished* `TrialResult`. It runs no agent and scores nothing.
  Explaining a trial leaves its serialised result byte-identical (`test_explaining_changes_nothing_about_the_trial`).
* **The numbers are shown beside the prose** as a table taken from the same facts, so every figure in the text can be checked against the
  judge's.
* **A model can phrase it but not add to it.** Its text is accepted only if every number and every exhibit id appears in the facts;
  otherwise it is discarded and the template is used, with the reason shown. Tested with invented figures and exhibits.
* **Works offline.** The always-available path is a template written from the facts. If `COURTROOM_LLM_PROVIDER=ollama` and a local server
  answers, the page shows its phrasing; the answer is cached, so a replay needs no server. Gemini is replay-only here as everywhere on the
  page, so a request can never spend money. The static page shows the template stored in the bundle (`explanations`, one per bundled trial).
* **What it can read:** exhibit titles and ids, the grounds argued, rulings, and the judge's numbers. Not exhibit flags or witness flaws.
* **A wording bug found and fixed while testing:** the first template said every early ending meant "no accepted exhibit supported it".
  That is only DV-2; DV-1 (below even odds, on motion) is a different finding, so the facts now carry which rule fired
  (`test_the_reason_for_ending_the_case_early_matches_the_rule_the_judge_fired`).
* **Not done:** the explainer was exercised against stubs, not a live Ollama. The template runs long (it lists every point); a model's
  version is capped at about 120 words by its prompt.

## D19 — adverse events ship on, at rates chosen by a measured sweep; the aurora and kestrel values are left as they were

**Why.** D14 admitted that `aurora-defi` and `kestrel-av` were calibrated by trying configurations until they looked contested, and that this was
result-driven design. It was also calibrated **without** adverse events, while D15 had added events whose rates (10%, 15%, 10%, credibility x1/4) were guesses. With events
on, both cases became dominance-solvable. `docs/CALIBRATION_SWEEP.md` replaces the guesswork with a sweep.

**What was measured** (`results/calibration/`, 200 seeds, 200 bootstrap resamples, all seven cases, strategy space frozen at 4x4): 21 settings of the four
parameters (each alone, and the three rates together), recording equilibrium label, supports, label stability, support stability, and per-strategy payoff sd; then the
two case values (`P-RECALL` strength, aurora defense-evidence scale) swept at the chosen rates, 32 values (including the exact +/-10% neighbours of each shipped value).

**What was chosen:** no-show 10%, missing certificate 15%, hostile 10%, hostile credibility 1/4, by the rules set in advance (variance must rise where it was
missing; at least 3 of 7 cases not dominance-solvable; every case holds label and support stability of 95% or better; then highest minimum stability). They are
the values that had been guessed. By the letter of the rules a qualifying band exists (11 of 20 settings). **Counting only the four cases that are real contests, none does**:
rule (b) is carried by structural fixtures, and rule (a) by the `edge-mutual-exclusion` tie fixture. Uncertainty flattens strategic depth here and nothing tried
restores it. Both readings select the same setting.

**What was left alone:** with events on, **no value** of either calibrated parameter makes its case anything but dominance-solvable (32 of 32 values). The rule was to
leave such a case as it is and document it, not to tune it to taste, so `P-RECALL` stays at 0.15 and the aurora scale at 1.0. Both cases are contested in outcome
(the prosecution wins 11 to 23% and 17.5 to 42%) but not in strategy.

**What changed in what ships.**
* `courtroom/cases/events.py`: `helix-espionage`, `aurora-defi`, `kestrel-av` and `edge-poisoned-tree` carry the chosen `RuleSet`. The three fixtures (an empty
  docket, a defense-only docket, an exact tie) stay plain: each shows one rule, and a random event would blur it. `PLAIN_CASES` is the library as it was.
* The hostile credibility factor became a `RuleSet` field (`hostile_credibility`, default "1/4") so the sweep can vary it in worker processes; at 1/4 nothing moves.
* The recorded language-model exhibition was played on the plain rulebook and is replayed on it (`get_plain_case`); its baseline is self-contained and unchanged.
  `LLM_EXHIBITION.md` and the exhibition banner now say so.
* **Certified analysis regenerated once.** `aurora-defi` pure becomes dominance-solvable (stability 80.5% becomes 100.0% label, 99.0% support); `kestrel-av` mixed becomes
  dominance-solvable (98.0% becomes 99.5%); `helix-espionage` stays mixed with a new mixture (837/1009 and 172/1009 for the prosecution) and 100% stability;
  the others are unchanged. The sensitivity sweep and the proof-bar ladder were regenerated with them.
* **Pinned digests.** 15 of 42 changed, all in the three cases whose trials events touched. Each was confirmed to trace to this edit before anything was regenerated:
  with events off, the plain library reproduces all 42 old digests (`tests/golden/digests_plain.json`, never regenerated), and every moved digest belongs to a case that ships with
  events (`test_every_shipped_digest_that_moved_is_a_case_that_ships_with_events`). `tests/golden/digests.json` was regenerated for the shipped cases.
* **The certified `results/*.json` are now tracked.** They had been gitignored as "regenerable", which meant a fresh clone had nothing to compare a regeneration against and two tests would have failed there. They are 100 KB in total.
* `results/adverse/` and the `-adverse` registry were removed: the shipped cases are those variants, and the sweep's `default` row supersedes the old analysis.

**Open, stated plainly.** The rates are chosen, not observed. The plateau is narrow in the joint direction (all rates x1.5 fails the stability floor by half a point).
`aurora-defi` sits 4% above a win-rate cliff (label unaffected). Conservative strategies that rarely offer an exposed exhibit stay flat. See section 7 of the sweep document.

## Corrections to claims made about the repo (no code or doc changed)

- **"84 tests, not 483."** Both numbers are right and describe the same suite: 84 `def test_`
  functions across 7 files, which `@pytest.mark.parametrize` expands into the test cases pytest
  reports. The README was accurate and was not "corrected" downwards; it now reads **495**, the
  current count after 12 tests were added for the bootstrap, sweep and case-editor work.
- **"The 27% prior contradicts the 0.15 defect prior."** They are different parameters, both
  matching the proposal: `PRIOR_DEFECT_RATE = 0.15` (`agents/base.py`) is the lawyer's prior that a
  ground applies to an exhibit (Sec. 5); `PRIOR_LOG_ODDS[CRIMINAL] = −1` → p ≈ 0.269 (`judge/rules.py`)
  is the presumption of innocence (Sec. 6). The UI's "27%" is computed from the latter
  (`viz/web/app.js`), not hardcoded. Nothing was wrong, so nothing was changed.
