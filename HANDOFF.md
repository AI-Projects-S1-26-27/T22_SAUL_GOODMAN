# Handoff

For whoever picks this up cold. Read this first, then `PROVENANCE.md` (how to verify every claim) and `DEVIATIONS.md` (D1 to D18,
every place the code differs from the submitted proposal, with the reason).

The project is a deterministic rulebook judge, two agents with fixed strategies, exact-rational Nash analysis, an optional language-model
layer clearly labelled as exhibition, and a static web demo. Team 22, CS F407.

---

## 1. What works, and how to check it yourself

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

| What | Command | Correct result |
|---|---|---|
| Determinism: same case, seeds and strategies give the same events and verdict | `python -m courtroom verify` | `bit-identical results: YES   hash chain valid: YES` |
| The test suite | `python -m pytest` | 1024 passed, about 90 seconds |
| 42 pinned trial digests | `python -m pytest tests/test_golden.py` | all pass; a failure means the certified engine changed |
| Fuzz | `python -m courtroom stress --cases 100` | `"trials": 2500`, `"crashes": 0`, `"failures": []` |
| The certified analysis regenerates exactly | `python -m courtroom analysis --out /tmp/a --workers 4` then `cmp results/payoffs.json /tmp/a/payoffs.json` (and the other two files) | byte-identical; about 14 minutes |
| The web bundle regenerates exactly | `python -m courtroom export --out /tmp/e` then `cmp /tmp/e/bundle.js courtroom/viz/web/data/bundle.js` | byte-identical; about 6 minutes |
| The language-model exhibition replays offline | `python -m courtroom export-exhibition --out /tmp/x` then `cmp` against `courtroom/viz/web/data/exhibition.js` | byte-identical; no key, no network |
| Run the app | `python -m courtroom serve --port 8000` | the full page, including the case editor, injection, adverse-event push and verdict explainer |
| Demo script | `DEMO_WALKTHROUGH.md` | ordered steps with what to click and what to point at |

The static Vercel build shows only bundled data. Anything that runs the engine needs `serve`.

### Where things are

| Path | What |
|---|---|
| `courtroom/judge/` | the rulebook judge (exact `Fraction` arithmetic), `brief.py` builds the case brief |
| `courtroom/engine/` | the trial loop, hash chain, utilities, `reaction.py` for pushed events |
| `courtroom/procedure/`, `courtroom/contracts/` | legal moves and validation; the data models |
| `courtroom/agents/` | Aggressive, Conservative, Adaptive, Mixed, Chaos (fuzzing only) |
| `courtroom/gametheory/` | payoff matrices, Nash support enumeration, bootstrap, sensitivity sweep |
| `courtroom/cases/` | seven library cases (`CASES` as shipped, four with adverse events on; `PLAIN_CASES` without); `WITNESS_CASES` are opt-in variants; `events.py` holds the calibrated rates |
| `courtroom/llm/` | **optional** Gemini and Ollama clients, narrator, exhibition, explainer. Nothing in the core imports this |
| `results/` | the certified analysis; `results/calibration/` is the measured sweep that chose the adverse-event rates (`docs/CALIBRATION_SWEEP.md`) |
| `docs/` | `DESIGN.md`, `DESIGN_WITNESS_POINTS.md`, `LEGAL_AND_BALANCE_AUDIT.md`, `OLLAMA.md`, `LLM_COST.md` |

---

## 2. Invariants: do not break these

Each is enforced by a test that fails loudly. If you need to break one, write a deviation first.

1. **The core imports nothing from `courtroom/llm`.** Core means `contracts`, `judge`, `procedure`, `agents`, `engine`, `cases`, `gametheory`.
   Tests parse the source of each: `python -m pytest tests -k "language_model_layer or only_reachable or reaches_nothing or do_not_import_the_llm"`.
2. **All randomness is seeded and has its own stream.** Streams are `"<seed>:perception"`, `"<seed>:witness-perception"`, `"<seed>:adverse"`,
   `"<seed>:agent:prosecution"`, `"<seed>:agent:defense"`, `"<seed>:llm"`, `"case-gen:<seed>"` and the bootstrap's `rng_seed`. Never use the global
   `random` module or the clock. Never draw from an existing stream for a new feature: a new draw shifts every later draw and changes digests.
   Draws for a feature that is switched off must not happen at all (`test_every_rate_at_zero_reproduces_the_plain_trial_exactly`).
3. **The judge uses exact `Fraction` arithmetic.** Floats appear only in display fields. The score is a pure function of the admitted record.
   Inputs have at most four decimals so they convert exactly (`q()` in `judge/rules.py`).
4. **No network in tests.** Tests stub the HTTP layer or pass `allow_network=False`; the Ollama and explainer tests replace `urlopen` with a
   function that raises. A new test that reaches a real server is a bug.
5. **The system runs with no API key and no Ollama.** Every language-model path falls back to a template or to the Adaptive policy and never raises.
   `python -m courtroom verify`, the suite and the whole certified analysis need neither.
6. **Anything optional is behind a flag whose default is today's rules.** `CaseFile.rules is None` reproduces the certified rulebook bit for bit.
   New enum members must not enter loops that existing code iterates (this is how the chaos agent's digests nearly changed; see D13).
7. **Language-model output never reaches a verdict, a digest or a payoff matrix.** It is read-only, labelled exhibition, and excluded from the analysis.
8. **Do not regenerate `tests/golden/digests.json` to make a failure go away.** Regenerate only for a deliberate, documented case or rule change.

---

## 3. Known issues, stated plainly

### 3.1 The aurora and kestrel calibration (D19)
The values were first chosen without adverse events, and the events' rates were guesses. *Correction:* earlier versions of this note said the library "ships with events on".
It did not; it was on the plain rulebook until D19 made events the shipped configuration for four cases.

**Resolved.**
- The rates are swept: 21 settings, all seven cases, 200 seeds, 200 resamples (`docs/CALIBRATION_SWEEP.md`, `results/calibration/events.jsonl`).
- The two case values are re-calibrated with events on: 32 values of `P-RECALL` strength and aurora defense scale, including the exact +/-10% neighbours of each shipped value.
- **No value contests either case**: all 32 are dominance-solvable (Conservative against Conservative), so the values were left as they were and documented, not tuned.
- Stability is 99% or better for every case (label/support: helix 100.0/100.0, aurora 100.0/99.0, kestrel 99.5/99.5, the other four cases 100.0/100.0), the same figures `RESULTS.md` quotes, and `helix-espionage` keeps its mixed equilibrium.

**Not resolved.**
- `aurora-defi` and `kestrel-av` still have one best strategy. They are contested in outcome (the prosecution wins 11 to 23% and 17.5 to 42%) but not in strategy. Making them strategic again needs a different case design, not another parameter value.
- `aurora-defi` sits 4% above a win-rate cliff (its label is unaffected).

### 3.2 Adverse events raised risk and removed strategic depth
Payoff variance rose where it was missing (kestrel Conservative prosecution sd 0.00 to 3.85, aurora Conservative 0.31 to 3.34).

**Resolved.**
- The rates are swept: no-show 0 to 30%, missing certificate 0 to 35%, hostile 0 to 30%, credibility 1/8 to 3/4, and all rates together x0.5 to x3.
- The selection rules were applied and both readings published. **By the letter of the rules a qualifying band exists (11 of 20 settings); counting only the four cases that are real contests, none does.** Both select the same setting.

**Not resolved.**
- The rates are chosen, not observed: nothing in the evidence says real trials have these frequencies.
- The plateau is narrow in the joint direction: all rates x1.5 fails the 95% stability floor by half a point.
- Conservative strategies that rarely offer an exposed exhibit stay flat (helix Conservative sd 0.08).
- Rule (b) as worded lets structural fixtures carry it.

### 3.3 The cases were tuned after measuring (D14); the process is replaced, not erased
D14's admission stands unedited. D19 supersedes the process.

**Resolved.**
- The sweep is published and the shipped values sit inside measured plateaus.
- No value was moved to taste, and the rule that a case which cannot be contested is documented as such was followed.
- Every stability figure here is the one `RESULTS.md` quotes, and `tests/test_docs_agree.py` fails if either drifts from `results/`.

**Not resolved.**
- Both cases are still tuned values: `kestrel-av`'s `P-RECALL` has a second regime above 0.275 (the prosecution wins 70 to 76%), and `aurora-defi` has the win-rate cliff noted above.
- The selection rules were written after D14, so they are a better process, not an independent one.
- Three structural fixtures (and the recorded exhibition) stay on the plain rulebook by choice, so they were not tuned and are not covered by the events sweep's conclusions.

### 3.4 The Ollama provider has never run against a real Ollama server
It follows Ollama's documented API and is tested against a stub only (`tests/test_ollama.py`). Ollama is not installed on the development machine, so the
recommended model (`qwen3:8b`) and all speed figures in `docs/OLLAMA.md` are untested. Run its 3-minute pre-demo check before relying on it.

### 3.5 Open team decisions (nobody has made these)
* **Is the four-facts cap a bug fix or a scoring deviation?** The proposal (Sec. 6) states the cap and the code lacked it, so D12 treats it as a
  conformance fix. It changes no library result. If the team disagrees, set `rules.MAX_FACTS_PER_SIDE = None`, which restores the old judge.
* **`kestrel-av` and `aurora-defi`: tune or document?** Decided by measurement (D19): with events on no value contests them, so they are documented as dominance-solvable and the values left alone. A team that prefers a mixed `kestrel-av` can run `PLAIN_CASES` (events off), where D14's calibration holds.
* **Should witness moves join the strategy matrix?** Today the matrix is 4x4 and witness examination is an opt-in variant that has not been solved as a game.
  Adding a fifth strategy costs roughly double the regeneration time.

### 3.6 The legal model comes from second-hand student notes, not a lawyer
`docs/LEGAL_AND_BALANCE_AUDIT.md` lists where the engine diverges from them. Two notes were too ambiguous to implement ("probability shifted" and
"fly fail arguments"). The engine still excludes illegally obtained evidence (a US-law rule; the notes say Indian law does not), has bare physical
exhibits in five places, has no final-argument phase, and the section 65B certificate is modelled only as a random event, not as an admissibility
attribute with a cure. Civil cases use the labels "prosecution" and "defense" for the plaintiff and defendant.

### 3.7 Instructor clearance for the language-model layer: verbal only
The proposal says the contribution is a formal game with **no language model**. The optional Gemini and Ollama layers (D8, D11, D17), narration, the
exhibition and the verdict explainer (D18) are an addition to that. **The instructor cleared the use of a language model verbally on 4 November 2026.
It was not given in writing and there is no record beyond this note.** If a written confirmation matters for marking, it still needs to be requested.
The layer remains isolated exactly as before, so it can be deleted without moving a certified result: nothing in the core imports it and nothing it
writes reaches a verdict, a digest or a payoff matrix.

### 3.8 Smaller things
* D7: rebuttal evidence can still add support after the directed-verdict review. Pinned by `test_any_post_dv_rise_is_confined_to_rebuttal`, not fixed.
* `LLM_EXHIBITION.md` shows an estimated cost of $0.2041. That is the cost of the 191 calls made in that run, not of the 363 responses in the cache.
  `docs/LLM_COST.md` has the cost from Google's published rates.
* The Vercel check fails on every PR with "Git author PramitKH26 must have access to the project": it needs a team invite, not a code fix.
* The shared Gemini key was pasted into a chat during development. It was never committed, but it should be rotated.
* The witness-examination variants (`WITNESS_CASES`) are not offered in the web case list and have no analysis.

---

## 4. What regeneration costs

Measured with `python -m courtroom analysis --workers 4` on an Apple M3 Pro.

| Scope | Time |
|---|---|
| All 7 cases at 4x4 (the shipped game) | **13 min 56 s** (matrices about 45 s, bootstrap about 55 s, sensitivity sweep about 12 min) |
| One case (`helix-espionage`) at 4x4 / 5x5 / 6x6 | **390 s / 584 s / 879 s** (1.0x, 1.5x, 2.25x) |
| All 7 cases at 5x5 / 6x6 | about 21 min / 31 min, scaled from the one-case ratios, **not measured** |

The sweep is single-process (D4: constants are patched in the parent) and is about 85% of the bill. Nash enumeration stays under 0.15 s even at 6x6, so cost
grows with the number of matrix cells, not with solving. Regenerating also means rewriting `RESULTS.md`, the proof-bar ladder, the Strategy tab and the exhibition
baseline, so freeze the strategy space first and regenerate once.
