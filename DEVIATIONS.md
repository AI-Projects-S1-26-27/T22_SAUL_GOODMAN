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
