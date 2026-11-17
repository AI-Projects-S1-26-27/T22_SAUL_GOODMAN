## PRIORITY OVERRIDE (13 Nov) - read before everything below

Deadlines: demo 21 Nov, final report 23 Nov. Today is 13 Nov.
The submitted proposal (Section 3) positions the project as "a small formal game with no language model",
against LLM-courtroom work (AgentCourt and similar). The instructor cleared LLM use verbally on 4 Nov, but that
does not change what the proposal claims. Therefore:
- Order of work is W1, W3, W4, then W2. W2 (language-model layer) is OPTIONAL: build it only if W1, W3, W4 are
  committed and tested. It must be OFF by default, labelled "exhibition, not part of the certified analysis" in
  every place it appears, and described in REPORT.md as an extension that the proposal did not include.
- Do not change the documented game for the certified analysis: phase order, action space, perception model
  (one uniform noisy signal, true-positive a, false-positive (1-a)/4), and the four style definitions stay as
  they are. New mechanics (courtroom surprises) stay behind a flag, default OFF, and are reported as a separate,
  labelled variant, never mixed into the main results.
- Record every deviation from the proposal in DEVIATIONS.md.
- Check that the defect prior used in code matches the proposal (0.15) and that docs say the same.
- Keep saying in REPORT.md that proof thresholds are game parameters, not legal probabilities.

# FINAL_PLAN.md — finish the Saul Goodman Courtroom for the 21 Nov showing

Course project (CS F407, Agents & Game Theory, demo track). The marker's likely attack is
"this is hard-coded": pre-run trials, four hand-picked lawyer styles, hand-written lines, hand-written cases.
The goal of this job is that every one of those has a live, computed answer the examiner can drive himself.

## 0. Where you are working

- Repo: this folder (`~/Downloads/AI_Project_clone`). Run `git fetch origin` first.
- BASE = `origin/main` (teammates' current version: 3D courtroom, voices, strategy lab, Ollama analyst).
  A plain copy of it is at `~/Downloads/AI_Project-main-2`; `origin/main` must contain `courtroom/viz/web/lab.html`.
  If it does not, or the fetch fails, STOP and say so.
- DONOR = local branch `calibration-sweep` (tip 4a1af81): my engine work. Read it with
  `git show calibration-sweep:<path>` / `git diff origin/main calibration-sweep -- <path>`. It has
  `courtroom/llm/` (cached client, ollama, policy, narrator, explainer), `gametheory/bootstrap.py`,
  `gametheory/sensitivity.py`, adverse events, golden digests, PROVENANCE/HANDOFF/DEVIATIONS docs.
- Create `final-integration` from `origin/main`. Commit there in small commits. Do NOT push, do NOT merge,
  do NOT touch `main`, `calibration-sweep`, or `_backup/`. Port by re-implementing/cherry-picking onto BASE;
  never merge DONOR wholesale (it predates the 3D app and conflicts with it).
- Read `AGENTS.md` on BASE before editing; its rules apply (plain language, `?v=N` cache-busting,
  `node --check`, `node scripts/check_lab_math.cjs`).

## 0.5 What was measured on BASE on 12 Nov (re-measure, do not trust blindly)

- One trial takes about 20 ms, so a 4x4 table at 30 seeds is roughly 10 s on one core. Budget searches from that.
- THE REAL "HARD-CODED" PROBLEM: in most cases the verdict does not depend on the lawyers at all.
  Over 15 seeds x the 9 pairings of Bold/Careful/Smart, the Accuser's wins were: cookie-jar 0 in every
  pairing, garden-dog 0, aurora-defi 0, broken-bike 15 in 5 pairings and 10 in the rest, the edge cases
  constant. Only helix-espionage and kestrel-av change with the pairing, and there almost every pairing
  is all-or-nothing (15 or 0); the seed changes the event log but hardly ever the verdict.
  So a seed box alone will not convince anyone. The examiner must be able to see the verdict MOVE.
- Generated cases: of gen-0..gen-79, the verdict depended on the pairing in 17 and on the seed within a
  pairing in 10. Contested cases exist and can be found by search rather than written by hand.
- DONOR already has `courtroom/llm/policy.py`: it lists the legal actions, asks the model for an index
  under a JSON schema, re-prompts twice, then falls back to Adaptive and counts every fallback. BASE's
  `PartyView` has the fields it reads. W2(a) is a port plus small additions, not a new design.
- `run_trial(case, prosecution, defense, seed)` takes strategy NAMES. The best-response search needs to
  run arbitrary `StrategyProfile` objects, so add a way to pass agents/profiles without changing the
  behaviour or digests of named runs.
- The project needs Python 3.11+ (`StrEnum`).

## 1. Invariants (check after every workstream)

1. RECORDED TRIALS DO NOT CHANGE. Before any edit, save the digest of every trial in
   `courtroom/viz/web/data/bundle.js` (10 cases x 16 pairings, seed 0) to `tests/golden/bundle_digests.json`
   and add a test that re-runs them. They must stay identical, so the recorded voice clips stay valid and no
   voice re-recording is needed. Every new engine behaviour sits behind a flag that defaults to today's rules.
   `node scripts/collect_lines.cjs` output must be identical before and after.
2. The rulebook judge decides everything, in exact `Fraction` arithmetic. No language-model output ever
   reaches a verdict, a payoff used in certified analysis, or a digest of a non-LLM trial.
3. `courtroom/engine`, `judge`, `procedure`, `agents`, `gametheory` import nothing from `courtroom/llm` at
   module load. The whole system runs, and all tests pass, with no key, no Ollama and no network.
4. All randomness is seeded from the trial seed in its own named stream. `courtroom verify` stays bit-identical.
5. Keys come only from `.env` / environment. Never print, commit or put one under `courtroom/viz/web/`.
6. Numbers written in any doc are generated from files in `results/`, never typed by hand.

## 2. Workstreams, in priority order. Finish and commit each before starting the next.

### W1 — Live controls (no language model needed)
The hosted site replays; the local server computes. Make that visible and drivable.
- Seed: when the server is up, a seed box and a "new seed" button in the courtroom (today `app.js` sends
  `seed: 0` always). A badge: "LIVE - computed just now, seed N" vs "RECORDED".
- Verify: show the trial digest and a "Run it again and compare" button (`POST /api/verify`: runs twice,
  returns both digests and hash-chain validity).
- Does strategy matter here? For every case, compute (live, from fresh multi-seed runs) how much the
  verdict depends on the pairing and on the seed, and show it honestly in the docket and the lab
  ("decided by the evidence" / "decided by the lawyers" / "a coin-flip between seeds").
- Contested-case finder (`gametheory/finder.py`, CLI `courtroom find`, `/api/find` bounded): search
  `gen-<seed>` cases, score each by that same measure plus whether its 4x4 game has no dominant strategy,
  and return the most contested. "Surprise me" in the docket plays one of these in the 3D room. These
  cases were found by search, and the page says so.
- Tipping point: for the trial on screen, find the smallest change to one exhibit's reliability or one
  witness's credibility that flips the verdict (bisection over re-scored records), and show it:
  "if this witness were 12 points less believable, the verdict flips". One click applies it and re-runs.
- Courtroom surprises: port DONOR's adverse events (witness no-show, exhibit excluded for a missing
  certificate, witness turns hostile) behind a flag that is OFF for every recorded trial and a toggle
  in live mode, using DONOR's swept rates (see its docs/CALIBRATION_SWEEP.md). This is what makes the
  seed matter to the verdict. Add generic spoken lines for the three events.
- What-if editor: `POST /api/trial` accepts an optional inline `case` (a full `CaseFile`, size-bounded,
  validated). A panel lets the user change an exhibit's reliability, a witness's credibility, a defect
  flag, the standard of proof, the budget, then re-run and see the verdict and log-odds move.
- Speech for cases with no `story.js` entry: a generic narrator in `app.js` built from the exhibit's title,
  description, kind and witness, so every event still speaks (browser speech is fine in live mode).
- Verdict explainer: port the DONOR's (which terms moved the log-odds, and what single change would flip it).

### W2 — Language-model layer (optional at runtime, real when present)
Port `courtroom/llm` from DONOR and unify it with BASE's `api/analyst.py` backends: Ollama Cloud
(`OLLAMA_API_KEY`) -> local Ollama -> Gemini (`GEMINI_API_KEY`) if set. One client, temperature 0, with a
disk cache keyed by hash(prompt, model, temperature) so any recorded run replays offline.
- (a) LLM counsel, strategy name `llm`: port DONOR's `policy.py` and its tests (including the one proving
  the prompt sees no more than the `PartyView`). Add an optional one-sentence `reason` to the answer,
  shown in the UI as the lawyer's thinking and never spoken as a fact. Keep re-prompt, fallback to
  Adaptive and the fallback counter; show the fallback rate after the trial. It appears in the UI as "AI lawyer" only when a backend answers. Its trials are marked
  non-certified; a cached one replays exactly.
- (b) Case from plain English. `POST /api/case/draft {text}`: the model writes a `CaseFile`; validate with
  the pydantic contracts, feed errors back for up to 2 repairs, then sanity-check (both sides have evidence,
  weights in range). Return it into the W1 editor where every number is visible and editable, with a note
  that the model proposed them. With no model, the same editor works as a manual form.
- (c) Narration for cases with no story: the model words each event from the exhibit text, is told to add
  no facts, and falls back to the W1 generic narrator.
- Keep the existing analyst chat. Add `docs/LLM_ROLE.md`: what the model may and may not do, and why a
  best-response check cannot certify an opaque policy.

### W3 — Game theory that is not hand-picked
- (a) Port `bootstrap.py` and `sensitivity.py`. `/api/game` and the lab gain a chapter "How sure are we?":
  confidence intervals, how often the equilibrium label and support survive resampling, and whether the
  conclusion survives +/-25% changes to the rulebook constants.
- (b) Best-response search (`gametheory/oracle.py`), a double-oracle / PSRO-style loop over the
  `StrategyProfile` parameters (`max_known_defects`, `min_gain`, `objection_belief`,
  `objection_min_impact`, `reserve_fraction`). Start from the four styles; solve; for each side run a seeded
  random search plus local refinement for a profile that beats the current equilibrium mix by more than
  2 standard errors on held-out seeds; add it, re-solve; stop when neither side improves or after 4 rounds.
  Output: how exploitable the hand-written styles were, the discovered profiles in plain words, the final
  equilibrium. CLI `courtroom oracle --case X --budget N`, a bounded `/api/oracle`, a lab chapter
  "Can a better lawyer be found?", committed results for 3 cases in `results/oracle/`.
- (c) Exhibition table: `llm` counsel against the four styles on a few seeds for 2-3 cases, results cached
  and labelled "exhibition, not certified". Build the harness regardless; run it only if a backend answers.
- (d) Run (a) and (b) with courtroom surprises ON as well as OFF and report both, since surprises change
  which cases are contested. Do not tune any case to make a result look better; report what is found.

### W4 — Proof and paperwork
- Tests for everything above (stub the model; no network). Full suite, `ruff`, `node --check`, lab maths check.
- `PROVENANCE.md`: one command per claim. `DEMO_SCRIPT.md`: a 5-minute run where the examiner supplies the
  inputs: show the room on an everyday case, then move to helix-espionage or a found contested case,
  change the styles and watch the verdict change, apply a tipping point, turn surprises on and re-roll
  the seed, type a new case in English, pick the AI lawyer, and finish on the best-response result.
  Do not present cookie-jar or garden-dog as examples of strategy mattering: measured, it does not.
- `REPORT.md`: problem; the model with formulas; agents; game-theory methods; results (generated numbers);
  what is fixed by design (rulebook constants, proof bars) and the sensitivity evidence; the model's role
  and limits; limitations; AI-usage disclosure (instructor cleared LLM use verbally on 4 Nov 2026);
  related work to position against - AgentCourt (arXiv 2408.08089), empirical game-theoretic analysis and
  PSRO, the double-oracle method, Code-Space Response Oracles (arXiv 2603.10098). Read a source before
  describing it; if you cannot reach it, cite it by title only and claim nothing about its content.
- Update `README.md` and add a section to `AGENTS.md` for the new parts.

## 3. Decision rules
- Decide yourself and keep going. If an item fails three honest attempts, write what blocked it in
  `HANDOFF.md`, leave it off behind its flag, and move to the next item.
- Never weaken or delete a test to get green. Never regenerate the bundle trials or voices.
- A missing key is not a blocker: build against the stub, skip the live run, say so in the final report.
- Prefer the smaller change. No new heavy dependencies; no build step for the web app.

## 4. Stop and ask only if
`git fetch` fails or BASE lacks the lab; a recorded-trial digest changes and you cannot trace it to a bug of
yours; `courtroom verify` stops being bit-identical; or finishing would require re-recording voices.

## 5. Final report
What shipped per workstream, what was skipped and why, exact test/verify/lab-check output, the oracle's
headline finding, which LLM runs were live vs stubbed, and the three commands I should run to try it.
