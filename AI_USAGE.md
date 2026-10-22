# AI usage disclosure

Course requirement, CS F407. This records every use of AI in this project: what was used, for
what, and how the output was checked. It covers two separate things that are easy to confuse —
AI used **to build** the project, and AI used **inside** the project at run time.

---

## 1. AI used to build the project

**Tool:** Anthropic Claude (via Claude Code), used as a coding assistant on the repository.

**What it was used for:**

| Area | What the assistant did |
|---|---|
| Verification | Ran the test suite, the 2,500-trial fuzz and the determinism checks; reported the real numbers. |
| `gametheory/bootstrap.py` | Wrote the bootstrap equilibrium-label stability analysis (proposal Sec. 8, previously missing). |
| `gametheory/sensitivity.py` | Wrote the parameter sweep (proposal Sec. 8, previously missing). |
| Turn order | Implemented alternating turns, redefined the directed-verdict trigger, and re-derived the DV fixtures. |
| `cases/generator.py` | One-line correctness fix: defense evidence could be generated with positive support. |
| `llm/` | Wrote the entire optional Gemini layer and its tests. |
| UI | Case editor, threshold slider, catch-probability table, spoken-argument toggle. |
| Proof bar | Made the standard's bar a parameter (`CaseFile.bar_log_odds`, `judge.rules.threshold_for`), with an API, a three-question slider and a precomputed ladder (D9). |
| Evidence injection | Logged mid-trial evidence in the hash chain with replay and tamper checks, plus its API, CLI and UI (D10). |
| LLM exhibition mode | Cache-only opponent mode, lazy-loaded replay, and labelling (D11). |
| Static bundle | Export that refuses stale analysis; Vercel build check; bundle freshness tests. |
| Test infrastructure | `tests/ui_smoke.cjs`: runs the real `app.js` in Node against the real bundle, with mutation tests that prove it fails on real bugs. |
| Docs | `RESULTS.md`, `DEVIATIONS.md`, this file, and README updates. |

**What was NOT written by the assistant:** the original simulator — contracts, case library,
procedure state machine, deterministic judge, agent policies, the exact Nash solver, engine, API
and the first web UI — was written by the team (commits `e6d4f32`, `0518c85` and the UI work in
`9d9bafb`–`e5e97b2`).

**How the output was checked.** Nothing was accepted because it looked right:

- **The suite is the gate.** 693 tests pass. No failing test was deleted, skipped or weakened to
  make a run go green. Where a test failed, either the code was fixed or the test's reference
  data was updated for an intended design change, with the reason recorded.
- **Four assistant bugs were caught and fixed, not papered over.** Each one would have produced
  a plausible-looking but wrong number:
  1. A budget-exhaustion rule fired *before* a party's turn and masked the validator's
     `V-BUDGET` check, so bad-faith over-budget attempts went unpunished.
  2. The first sensitivity sweep reported zero movement everywhere, because perturbed constants
     never crossed a `ProcessPoolExecutor` boundary. A regression test now asserts the sweep
     actually moves something: "nothing changed" is indistinguishable from "the measurement is
     broken".
  3. The exhibition's fallback rate counted decisions where only **one legal move existed** as
     fallbacks, reporting **27.1%** where the true rate was **4.4%** — enough to trip a 30%
     alarm for a reason having nothing to do with the model.
  4. `QuotaExhausted` escaped into the engine's fault barrier (`except Exception` around
     `agent.act()`) and became a silent procedural violation. The run did not stop, `resumable`
     stayed false, and the affected cells reported a **fabricated 100% fallback rate with no
     reasons recorded**. The tell was `quota_stops: 63` sitting beside `aborted: null`. Two tests
     now pin it, one asserting the decision counters **partition** the total exactly, so any
     unrecorded outcome fails the suite.
**Bugs from the latest round, each found by a test rather than by looking:**

5. A replay of an injected trial diverged whenever the trial ended before the injection point,
   because only *applied* injections were recorded. The empty-docket and defense-only cases exposed
   it; a result now carries every injection requested.
6. A string splice in `app.js` deleted three functions `init()` still called, and the page crashed
   on load. No Python test could see it. The UI smoke harness exists because of this, and it was
   itself found to miss errors the app catches and shows to the user, so it now reads what the app
   displays.
7. The injected exhibit never reached the on-screen evidence board, and the same stale-board bug was
   already present in the editor's "Try it in the courtroom". No exception, just a wrong page.
8. In the LLM exhibition, the judge tab's replay-at-a-bar handler would still have sent
   `"prosecution": "llm"` to the server. The buttons were hidden by CSS, which is not a safeguard.
   The handler is now guarded, and a test fails if any request names the LLM strategy.
9. `/api/narrate` could call the provider if the server happened to hold a key. It is cache-only now.

Two of my own claims were also corrected before they stood: a sentence in `RESULTS.md` asserting
where the flagship's equilibrium band ends (the ladder cannot resolve that) and a causal explanation
for it that I had not tested.

- **A reported figure was withdrawn rather than published.** The first exhibition run's
  defense-side results were contaminated by bug 4 and were discarded, not reported.
- **Claims were measured, not asserted.** Where the assistant was told something about the repo
  that turned out to be false — a test count, a "stale" prior, a bug supposedly introduced by a
  change — it measured first and reported the contradiction. The directed-verdict regression was
  checked against the original code in a throwaway `git worktree`: 21 violations before, 2 after.
- **Determinism is re-checked after every change.** `courtroom verify` must stay bit-identical.

---

## 2. AI used inside the project at run time

**Tool:** Google Gemini, model `gemini-3.1-flash-lite`, temperature 0, via `google-genai`.

**This contradicts the proposal**, which states the contribution is "a small formal game with
**no language model**". It is recorded as deviation **D8** in [`DEVIATIONS.md`](DEVIATIONS.md) and
is an *addition beside* the certified core, never a replacement for any part of it.

**Why that model.** Flash-Lite is the cheapest tier on the key. A *pinned* version was chosen over
the `gemini-flash-lite-latest` alias because an alias can silently change model underneath a
committed cache, which would destroy the reproducibility the cache exists to provide. Two
candidates were rejected after testing against the live key: `gemini-2.5-flash-lite` is listed by
the API but returns 404 "no longer available", and `gemini-3.5-flash-lite` returned intermittent
503s. **The API exposes no pricing**, so cost is reported in tokens and the currency rate is a
configuration value (`COURTROOM_LLM_RATES`), never a quoted price.

**Two distinct uses:**

1. **Argument text** (`llm/narrator.py`) — cosmetic. Generated *after* a trial has been decided,
   over the finished immutable record. The trial is scored and hashed before any text exists.
2. **An exhibition policy** (`llm/policy.py`) — an opponent that chooses moves through the same
   `PartyView` / `Oracle` interface every other agent uses. **Exhibition only.** It is not in the
   payoff matrices, the bootstrap or the sensitivity sweep, because an LLM's payoffs are not
   reproducible from a cold cache and so cannot be certified by the best-response verifier.

**How the isolation is enforced — by tests, not by intention:**

| Guarantee | Test |
|---|---|
| Generated text cannot move a verdict | `test_verdict_is_byte_identical_with_and_without_argument_text` |
| Text never enters the trial record | `test_narration_is_not_stored_on_the_trial_record` |
| The certified core never imports the LLM layer | `test_engine_and_judge_do_not_import_the_llm_package` |
| Prompts carry no exhibit's true flags | `test_narrator_prompt_leaks_no_latent_defect`, `test_llm_policy_reads_the_noisy_posterior_not_the_truth` |
| The opponent's unplayed hand never reaches a prompt | `test_llm_policy_prompt_names_no_exhibit_it_cannot_see` |
| The policy can only pick legal moves | `test_llm_policy_only_ever_offers_legal_actions` |
| Every transport failure degrades to a fallback | `tests/test_llm_gemini.py` (21 stub tests; no test makes a network call) |

**Cost control.** 160 output tokens per call, 40 calls per trial, 400 per run, an optional spend
ceiling, and a daily-quota stop that saves the cache and resumes for free rather than re-spending.

**Secrets.** The key is read from `GEMINI_API_KEY` and is never logged, printed or committed;
`test_the_api_key_is_never_written_to_the_cache` checks the last of those. During development the
key was held in a file outside the repository with mode 600, and the repository was grepped to
confirm no key material reached any tracked file.

**What it cost.** About $0.05 on the paid-tier rate for the recorded tokens, and nothing charged on the free tier the key was on; the arithmetic, the source and what it leaves out are in [`docs/LLM_COST.md`](docs/LLM_COST.md).

**Reading the call counts.** `LLM_EXHIBITION.md` reports calls made *in that run*. A replay from
the committed cache honestly reports **0**, because it makes none. The cumulative cost of
producing the results is the number of distinct responses in the cache, each paid for by one real
call at some point; the write-up states both so the zero cannot be mistaken for "this was free".

---

## 3. Honest limits

- A cache *hit* is deterministic. A cache *miss* on another machine calls Gemini, and providers do
  not guarantee identical output across time or model revisions even at temperature 0. Everything
  in [`LLM_EXHIBITION.md`](LLM_EXHIBITION.md) therefore carries that caveat.
- The deterministic results in [`RESULTS.md`](RESULTS.md) have no such caveat: they are exact
  rational arithmetic over seeded trials and reproduce bit-for-bit.
- The deterministic analysis was **regenerated against the current alternating-turn engine**, so
  [`RESULTS.md`](RESULTS.md) now describes the game the code actually plays. It had previously
  gone stale when the turn order changed, and was carrying a staleness banner until it was rerun.
