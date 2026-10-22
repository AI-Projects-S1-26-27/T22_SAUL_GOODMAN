# Saul Goodman Courtroom

**Two AI lawyers. One rulebook judge.**

Team **Saul Goodman** · Track: Demo · Domain: Agents & Game Theory

**Live demo:** <https://ai-project-weld-omega.vercel.app>

Pick a fictional case, choose how each lawyer plays, and watch the trial unfold step by step.
A prosecution agent and a defense agent compete to build the strongest case from structured,
synthetic evidence. They present exhibits, object, challenge witnesses and rest, each under a
fixed budget. The judge is **not** an AI. It is a fully deterministic rulebook that uses exact
fractions: it rules on every objection with a named rule, weighs only the accepted evidence,
point by point, and records every step in a hash-chained audit trail. Same case, same choices,
same verdict, every time.

On top of the trials, a game-theory layer replays each case for every combination of styles,
builds the payoff matrix and solves it for **exact rational Nash equilibria**. That answers the
question the demo is built around: *should a lawyer go on the attack or play it safe?*

---

## Contents

- [Quick start](#quick-start)
- [The web app](#the-web-app)
- [How a trial works](#how-a-trial-works)
- [The four playing styles](#the-four-playing-styles)
- [How the judge decides](#how-the-judge-decides)
- [Game theory: which style wins?](#game-theory-which-style-wins)
- [The case library](#the-case-library)
- [Command-line tools](#command-line-tools)
- [Architecture](#architecture)
- [Robustness guarantees](#robustness-guarantees)
- [Deploying](#deploying)
- [Project layout](#project-layout)

---

## Quick start

Requires **Python 3.11+**.

```bash
git clone <this-repo>
cd AI-PROJECT_SAUL_GOODMAN
pip install -e ".[dev]"
python -m courtroom serve
```

Open <http://127.0.0.1:8000>. The local server runs the **live simulator**, so you can use any
trial number, any pairing of styles (including a mixed strategy) and larger strategy games.

Run the test suite (914 tests):

```bash
python -m pytest
```

---

## The web app

The web app is laid out as a lawyer's **case folder**: six index tabs on a single sheet. Each tab
has its own link (`#overview`, `#courtroom`, `#casefile`, `#verdict`, `#strategy`, `#judge`), so
you can share exactly what you're looking at.

| Tab | What it shows |
|---|---|
| **Overview** | The idea on one page. A live replay of a real trial runs in the hero. Below it: who's in the room (the judge, the record and both lawyers), the five moves a lawyer can make, the four playing styles, and why every result can be checked. |
| **Courtroom** | Pick a case and a style for each side, then play, pause or step through the trial. Every event is narrated in plain English. You also get stage progress, *How sure is the judge?* meters for each point with the bar it must clear, a clickable transcript, and live evidence boards showing what was shown, accepted or thrown out. |
| **Case file** | An **editor** where an examiner can load, edit or paste a case and run it, refused by the same validator with the failing field named. The accusation and charge, the points that must be proven, the standard of proof and the case budget. Witnesses come with credibility and possible bias. Every exhibit comes with its reliability, what it clashes with and its hidden flaws. |
| **Verdict** | Why the loaded trial ended the way it did. Each point shows a bar per exhibit for how far it pushed the judge either way. An **evidence map** shows which exhibits back each other up and which clash. Also here: the judge's exact working, each side's ledger, and the fingerprinted event chain. |
| **Strategy** | *Which style wins?* A win-rate matrix for every pairing of styles, the stable (Nash) choices explained in plain language, the smart mixes, and the win rate when both sides play smart. |
| **Courtroom, LLM exhibition** | A mode bar at the top switches between the certified simulation (the default, and what the page always opens in) and an exhibition in which a Gemini policy plays one seat. The exhibition is replayed from a committed cache with no key and no network, covers one case and seeds 0 to 4, and is labelled everywhere as not equilibrium analysis. |
| **Courtroom, add evidence** | In local mode, *Add evidence mid-trial* puts a new exhibit into one side's hand at the step you are viewing and replays the trial from there. The exhibit is committed to the hash chain, so the same inputs always give the same verdict. |
| **The judge** | How rulings and verdicts are made, the three standards of proof, the six objection grounds, and the exact formula. A **slider** re-decides the loaded trial at any bar from 50 % to 99 %, and a table gives each flaw's chance of being caught. |

The header has two switches:

- **Technical details** reveals rule IDs, the agents' reasoning, event hashes, exact payoffs,
  equilibrium fractions and a replicator-dynamics plot.
- **Light/dark theme** follows your system setting by default and remembers your choice.

The front end is plain HTML, CSS and JavaScript with **no build step and no network
dependencies**, and the fonts are self-hosted. When the API isn't reachable it falls back to the
pre-exported bundle (`courtroom/viz/web/data/bundle.js`), so it also works offline or opened
straight from `file://`.

**Hosted demo vs. local server.** The Vercel deployment is the static UI running on that bundle.
It includes the seed-0 trial for six style pairings per case, the full **4×4** payoff matrix for
every case (200 seeds per cell), and the precomputed bootstrap and sensitivity results, which
the Strategy tab labels as precomputed. It greys out everything else. Run `python -m courtroom
serve` locally to unlock any pairing, any seed, your own cases and live recomputation.

The optional LLM exhibition ships as a **separate** file, `data/exhibition.js`, replayed from the
committed response cache with the network disabled, so `bundle.js` can be audited as containing
no model output.

---

## How a trial works

The trial is a finite state machine:

```
OPENING → PROSECUTION_CASE → DIRECTED_VERDICT_REVIEW ─(granted)→ DELIBERATION → CLOSED
                                     │(denied)
                                     ▼
                              DEFENSE_CASE → REBUTTAL → DELIBERATION → CLOSED
```

On its turn, a lawyer can:

| Move | What happens |
|---|---|
| **Present evidence** | Offer a document, record or witness. The other side gets exactly one chance to object (or pass). |
| **Object** | Claim the evidence is hearsay, unverified, illegally obtained, shared too late, guesswork or off-topic. A wrong objection is penalised. |
| **Challenge a witness** | Use evidence to impeach a witness. If it works, that witness counts for half. |
| **Ask to end early** | The defense can move for a directed verdict if a point has no accepted evidence at all. |
| **Rest** | Stop presenting. Passing twice in a row counts as resting, so nobody can stall forever. |

Every move costs part of a fixed **budget**, each stage has a **turn cap**, and neither lawyer can
see the other side's hidden flaws for sure. Each lawyer reads every possible defect through a
noisy, seeded channel, so objecting is a decision made under uncertainty.

Flawed evidence is only thrown out if the opponent **objects on the right ground**. Unchallenged
flaws are waived, just as in real procedure, which is what makes objection strategy matter.

---

## The four playing styles

| Style | Behaviour |
|---|---|
| **Aggressive** | Offers everything that helps, including defective items, and objects on thin suspicion. |
| **Careful** (conservative) | Offers only clean evidence that matters, and objects only when confident. |
| **Adaptive** | Maximises expected value and learns the opponent's objection rate (Beta posterior). |
| **Chaotic** | Makes random, often illegal moves. It exists to prove the rules can't be broken. |
| **Mixed** *(local only)* | Aggressive with probability *p*, otherwise Careful. |

---

## How the judge decides

For each legal element (point) `e`, over **accepted** evidence only:

```
S_i    = reliability × witness credibility (halved per successful impeachment)
disc_i = min(9/10, Σ_{j contradicts i} (4/5)·S_j/(S_i+S_j))       symmetric → order-independent
corr   = 1 + ½(1 − 2^-k), k = other facts with same-sign support     bounded → no evidence spam
L_e    = prior + 3 · Σ_{one item per fact} support·S·(1−disc)·corr   exact Fraction arithmetic
verdict = GUILTY / LIABLE  iff  every element's L_e clears the standard (conjunctive test)
```

| Standard | Used for | Threshold (log-odds) | ≈ certainty |
|---|---|---|---|
| Beyond reasonable doubt | Criminal cases | `11/5` | ~90 % |
| Clear and convincing | Serious civil claims | `11/10` | ~75 % |
| Balance of probabilities | Civil cases | `> 0` | > 50 % |

- **Exact arithmetic.** Decisions compare exact rationals (`fractions.Fraction`). Floats exist
  only on display fields, so rounding can never flip a verdict.
- **Every ruling cites a rule:** `OBJ-HEARSAY`, `OBJ-AUTH`, `OBJ-EXCLUSIONARY`, `OBJ-DISCLOSURE`,
  `OBJ-SPECULATION`, `OBJ-RELEVANCE`, `DV-2`, `STALL-1`, `TURN-CAP`, `CONTEMPT-1`, …
- **Tamper-evident record.** Every event is chained with `h_n = SHA256(h_{n−1} ‖ event_n)`, and the
  final digest fingerprints the whole trial.
- **Penalties.** An overruled objection costs ¼ point. A procedural violation costs 1 point plus a
  budget fine. Knowingly offering illegally obtained or undisclosed evidence costs 2 points.

---

## Game theory: which style wins?

Payoffs are general-sum: `U = V·win − c·spent − μ·sanctions`. For each case, the game layer:

1. Estimates the payoff matrix by Monte-Carlo over many seeded trials per cell.
2. Solves for **all Nash equilibria** with an exact rational support-enumeration solver.
3. Independently verifies each equilibrium with a best-response check.
4. Runs iterated elimination of strictly dominated strategies (IESDS) and flags dominance.
5. Simulates replicator dynamics, showing how play would drift if both sides kept learning.

6. Resamples the seed set 200 times and reports how often each case's equilibrium label holds.
7. Sweeps the constants by ±25%, and the criminal standard across 80-95%, reporting which
   conclusions survive and which depend on a parameter.

The analyzer reports triviality honestly instead of hiding it: `kestrel-av` is reported as trivial
rather than dressed up. Measured results are in [`RESULTS.md`](RESULTS.md); calibration notes are in
[`docs/DESIGN.md`](docs/DESIGN.md).

---

## The case library

All cases, people and organisations are **synthetic**.

Equilibria below are from the **4×4** game (Aggressive, Careful, Adaptive, Mixed) over 200 common
seeds per cell, each verified by best response and resampled 200 times. Full numbers, including
what each result depends on, are in [`RESULTS.md`](RESULTS.md).

| Case | Type | What it demonstrates | Equilibrium (4×4, 200 seeds) |
|---|---|---|---|
| `helix-espionage` (flagship) | Criminal | No dominant strategy either side: optimal play has to randomise | **Mixed** NE: prosecution 87 % Careful / 13 % Adaptive, defense 93 % Adaptive / 7 % Careful (exactly 711/821 and 7870/8447). Label stable in 200/200 resamples |
| `kestrel-av` | Civil | **Trivial**: the plaintiff cannot win under any pairing, so there is no strategic content (see `RESULTS.md` §5) | Pure NE (Careful, Careful), dominance-solvable, strictly |
| `aurora-defi` | Criminal | Strong white-hat defense: aggression only burns budget | Pure NE (Careful, Careful); Careful strictly dominant for the prosecution |
| `edge-empty-docket` | Criminal | Zero evidence | Directed acquittal (rule DV-2) under every pairing, including Chaotic. Every profile ties |
| `edge-mutual-exclusion` | Civil | Two equally credible, contradictory witnesses | Exactly symmetric discount → log-odds exactly `0` → not liable |
| `edge-poisoned-tree` | Criminal | Every exhibit is defective | An objecting defense wins, while a passive defense can still lose |
| `edge-defense-only` | Criminal | Only exculpatory evidence | Directed acquittal ordered by the judge on its own motion (sua sponte) |

The three `edge-*` structural fixtures are the only cases whose label survives **every** parameter
perturbation. The four substantive cases each depend on at least one constant, and `RESULTS.md`
says which.

New cases can also be generated procedurally (`courtroom/cases/generator.py`).

---

## Command-line tools

```bash
python -m courtroom cases                           # list the case library
python -m courtroom run --live                      # animated terminal replay of the flagship case
python -m courtroom game --case helix-espionage     # payoff matrix + exact Nash equilibria
python -m courtroom tournament                      # game analysis across the whole library
python -m courtroom analysis --out results          # matrices + bootstrap + sweep, all to disk
python -m courtroom bootstrap                       # how stable is each case's equilibrium label?
python -m courtroom sensitivity                     # vary the constants; report what survives
python -m courtroom verify -p chaos -d adaptive     # prove bit-for-bit determinism
python -m courtroom stress --cases 100              # 2,500-trial fuzz run, exits 1 on any failure
python -m courtroom llm-models                      # Gemini models available on your key
python -m courtroom llm-exhibition                  # Gemini policy vs the four (NOT equilibrium analysis)
python -m courtroom run --narrate                   # spoken argument text over a decided trial
python -m courtroom export                          # rebuild the static web bundle (needs `analysis` first)
python -m courtroom export-exhibition               # replay the committed LLM cache into data/exhibition.js
python -m courtroom verify --inject file.json       # prove a trial with mid-trial evidence replays bit-identically
python -m courtroom serve                           # web UI + API on http://127.0.0.1:8000
```

Run any command with `--help` for its options.

### HTTP API (served by `python -m courtroom serve`)

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Liveness check |
| `GET /api/cases`, `GET /api/cases/{id}` | Case library and full case files |
| `GET /api/strategies` | Available playing styles |
| `GET /api/rules` | Judge constants and each flaw's chance of being caught |
| `POST /api/validate` | Check an examiner's own case file; names the failing field |
| `POST /api/trial` | Run one trial `{case_id \| case, prosecution, defense, seed}` |
| `POST /api/game` | Payoff matrix + equilibria `{case_id, strategies, seeds}` |

---

## The optional Gemini layer

**Everything above is deterministic and certified. This part is not, and is kept separate on
purpose.** See [`AI_USAGE.md`](AI_USAGE.md) and deviation D8 in [`DEVIATIONS.md`](DEVIATIONS.md).

The proposal's stated contribution is a formal game with **no language model**. A Gemini layer now
exists beside that core, never inside it, in two forms:

| | What it does | Status |
|---|---|---|
| **Argument text** | Turns a decided move into a line of courtroom argument. Runs *after* the trial is scored and hashed, over the finished record. | Cosmetic. Cannot move a verdict. |
| **Exhibition policy** | An agent that picks moves through the same `PartyView` / `Oracle` interface as every other agent. | **Exhibition only.** Never in a payoff matrix. |

The separation is enforced by tests, not by intention: the verdict and digest are asserted
byte-identical with and without generated text, no core package may import `courtroom.llm`, and
prompts are checked to carry only the public record and the same noisy defect posteriors every
other agent receives.

Why the policy is excluded from the analysis: an LLM's payoffs are not reproducible from a cold
cache on another machine, so no equilibrium computed over them could be certified by the
best-response verifier. Results go to [`LLM_EXHIBITION.md`](LLM_EXHIBITION.md), labelled exhibition.

Model `gemini-3.1-flash-lite` (cheapest tier, pinned rather than a `-latest` alias so a committed
cache stays meaningful). Set `GEMINI_API_KEY` to use it; **with no key the layer falls back to
templates silently and the demo still runs**. Responses are cached to disk and committed, so the
demo works offline. A daily-quota stop saves progress and resumes from the cache for free.

---

## Architecture

The project was built by seven engineers, each owning one package:

```
                        ┌──────────────────────────────┐
                        │ E1 contracts/ (Pydantic v2)  │  shared, frozen data contracts
                        └──────────────┬───────────────┘
      ┌───────────────┬────────────────┼────────────────┬────────────────┐
      ▼               ▼                ▼                ▼                ▼
 E1 cases/       E3 judge/        E2 procedure/     E4 agents/       E5 gametheory/
 library,        admissibility,   FSM, validator,   oracle, Bayesian payoff MC, exact
 generator       exact scoring,   ledgers           perception,      Nash, IESDS,
                 DV, verdict                        policies, chaos  replicator, stress
      └───────────────┴──────────┬─────┴────────────────┘                │
                                 ▼                                       │
                       E6 engine/ + api/ + cli  ◄────────────────────────┘
                       orchestration, fault barrier, audit chain, HTTP
                                 │  TrialResult / PayoffTable (read-only)
                                 ▼
                       E7 viz/  terminal dashboard (rich) + web app (vanilla JS)
```

| # | Owns | Package | Public contract | Tests |
|---|---|---|---|---|
| E1 | Contracts & case library | `contracts/`, `cases/` | `CaseFile`, `EvidenceItem`, `Action`, `TrialEvent`, `TrialResult`… | `test_contracts_and_cases.py` |
| E2 | Procedure & objection arbiter | `procedure/` | `ProcedureState.expected()`, `validate() → Violation \| None` | `test_procedure.py` |
| E3 | Deterministic judge | `judge/` | `Judge.rule_on_objection / directed_verdict_review / deliberate`, `score_record` | `test_judge.py` |
| E4 | Strategic agents | `agents/` | `Agent.act(PartyView, Oracle) → Action`, `make_agent(name, rng)` | `test_agents.py` |
| E5 | Game theory & tournament | `gametheory/` | `estimate_payoffs → PayoffTable`, `analyze → GameAnalysis`, `stress → StressReport` | `test_gametheory.py` |
| E6 | Engine, API, CLI | `engine/`, `api/`, `cli.py` | `run_trial → TrialResult`, `/api/*` | `test_engine.py`, `test_api.py` |
| E7 | Visualisation | `viz/` | Consumes `TrialResult` / `PayoffTable` only and never calls the engine | `test_api.py::test_ui_is_served` + manual |

**Dependency rule:** arrows only point down. The judge knows nothing about agents, agents see the
judge only through the read-only `Oracle`, and the visualisation layer can't influence outcomes.

---

## Robustness guarantees

- **Weak or no evidence:** prior-only scoring plus a mandatory directed-verdict review (DV-2,
  applied sua sponte even if the defense never asks).
- **Contradictions:** a symmetric discount, backed by a permutation-invariance test.
- **Bad-faith actions:** 11 typed violation rules. A violation becomes a PASS plus a fine and a
  sanction, and three violations mean contempt.
- **Loops and deadlocks:** one-action response windows (an objection can't be objected to), a
  stall rule, turn caps and a global watchdog.
- **Agent crashes:** caught at the fault barrier (`V-AGENT-FAULT`), including in `opening_statement()`.
- **Demo infrastructure:** bundle fallback, works from `file://`, and `no-cache` headers.
- **Verified:** a 2,500-trial fuzz run, including the Chaotic agent, had 0 crashes and 0 invariant
  violations, and 250/250 replays were bit-identical. All 914 tests pass (337 test functions,
  parametrised). Measured figures and what they depend on are in [`RESULTS.md`](RESULTS.md).

---

## Deploying

The live demo at <https://ai-project-weld-omega.vercel.app> is a static deployment of
`courtroom/viz/web` (see [`vercel.json`](vercel.json): no build command, output directory
`courtroom/viz/web`).

After changing cases, agents or judge constants, regenerate in this order:

```bash
python -m courtroom analysis --out results --workers 4   # matrices, bootstrap, sweep (about ten minutes)
python -m courtroom export --workers 4                   # courtroom/viz/web/data/bundle.js
python -m courtroom export-exhibition                    # courtroom/viz/web/data/exhibition.js (no key needed)
```

`export` **refuses to run** if `results/payoffs.json` does not match the current engine, so the
bundle can never ship analysis that describes a game the code no longer plays. `tests/test_bundle.py`
checks the same thing from the other side: every shipped trial must reproduce its digest.

To check the static build locally, `vercel build` works in a scratch copy with no login or project
link; its output is byte-identical to `courtroom/viz/web`.

Then commit and redeploy (push to the connected branch, or run `vercel --prod`).

---

## Project layout

```
courtroom/
  contracts/   frozen Pydantic data contracts
  cases/       synthetic case library + procedural generator
  procedure/   trial state machine, validator, ledgers
  judge/       admissibility, exact scoring, verdict
  agents/      strategic agents, noisy perception, policies
  gametheory/  payoff estimation, exact Nash, dynamics, stress
  engine/      trial orchestration, audit chain, utilities
  api/         FastAPI server (web UI + /api)
  viz/         terminal dashboard + web/ (index.html, styles.css, app.js, data/bundle.js)
  cli.py       command-line entry point
docs/DESIGN.md design dialectic and calibration notes
RESULTS.md     measured equilibria, bootstrap stability, sensitivity sweep
DEVIATIONS.md  every intentional divergence from the proposal, with reasons
tests/         337 test functions -> 914 parametrised cases
```

---

*All cases, people and organisations are fictional. This is a stylised simulation, not legal advice.*
