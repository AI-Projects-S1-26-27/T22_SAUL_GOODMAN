# AI Usage Disclosure

The course allows AI tools for brainstorming, code assistance, writing help and debugging, provided their use is disclosed and every
member can explain their own part. This file states which tools we used, what for, and how we checked the output. The same account is
in the report (`report/sections/07_ai_usage.tex`, Section 7 of the PDF).

## Tools

| Tool | Used for |
|---|---|
| **Claude** (Anthropic): Claude Code in the repository, and Claude chat | Brainstorming (how to model a trial as a game, which analyses to run, how to explain them in plain words), code assistance, debugging, writing help, and independent re-runs and reviews of the work |
| **Antigravity** (Google), an AI coding environment | Brainstorming designs before writing them, code assistance, explaining unfamiliar library calls (FastAPI, three.js, the Web Audio API), suggesting fixes for failing tests, and tidying code |

As a coding assistant, Claude Code wrote and refactored much of the code in this repository, and wrote or rewrote many of the tests and
documents. Examples: the bootstrap, sensitivity, best-response search, classic-game, efficiency, tree-search and lookahead modules; the
optional `courtroom/llm/` package; the web app's live controls, the strategy lab and the guided tours; the result scripts and generated
documents; the code review and its fixes; the preflight script, the browser tests, and the scripts that build the slides and the report.

Debugging examples: tracing why recorded trials' digests moved after the impeachment fix (deviation D6), the literal `null` on the verdict
card, and a lab chart that disagreed with the engine's exact table.

## Per member

| Member | Package | AI use, and how it was checked |
|---|---|---|
| **Aditya Singh** | `contracts/`, `cases/` | Claude and Antigravity for brainstorming the case library and the case validator, code assistance on the data models and generator, and debugging schema errors. Checked with `tests/test_contracts_and_cases.py` and by reading every case file. |
| **Divvij Y. Chichra** | `procedure/` | Claude and Antigravity for brainstorming the trial's phases, code assistance on the validator and ledgers, and debugging illegal-action edge cases. Checked with `tests/test_procedure.py` and the chaos-agent stress run. |
| **Lakshya Sachdeva** | `judge/`, 3D courtroom | Claude and Antigravity for brainstorming the scoring rules, code assistance on the judge, the web app and the **three.js 3D courtroom simulation** (the room, cast, camera shots and trial choreography), and debugging. Checked with the hand-computed fixtures in `tests/test_judge.py` and `tests/test_judge_boundaries.py`, and by playing every case in the courtroom. |
| **Mofasser A. Midda** | `agents/` | Claude and Antigravity for brainstorming the lawyer styles, code assistance on the policies and the Wild style, and debugging agent crashes. Checked with `tests/test_agents.py` and the fault-barrier tests. |
| **Pramit Khandelwal** | `engine/`, `api/`, `cli.py` | Claude (mainly Claude Code) and Antigravity for brainstorming, code assistance across the engine, API, analyses and documents, debugging, and writing help. Checked with the full test suite, the pinned digests, independent re-runs and the code review. |
| **Rakshit Goel** | `viz/` | Claude and Antigravity for brainstorming the 3D courtroom and the page layout, code assistance on three.js scenes, exhibit cards and tours, and debugging rendering and audio issues. Checked in the browser tests and by walking through every case. |
| **Rohan B. Pagire** | `gametheory/` | Claude and Antigravity for brainstorming the game-theory analyses, code assistance on the Nash solver and the lab maths, and debugging. Checked against known games in `tests/test_gametheory.py` and with `scripts/check_lab_math.cjs`. |

## How the output was verified

Nothing was accepted because it looked right.

- **Tests.** The full suite, including hand-computed judge fixtures written from the proposal's formulas rather than from the code, and
  property tests. No test was weakened, skipped or deleted to make a run pass.
- **Pinned digests and spoken lines.** The digest of every recorded trial and every spoken line is pinned, and a test replays them. A
  change that moves one must be deliberate and is recorded in `DEVIATIONS.md`.
- **Mutation checks.** For several tests we put the bug the test should catch into a temporary copy and confirmed the test failed.
- **Independent re-runs and a structured code review.** The review found, among other things, that the engine allowed impeachment with an
  unadmitted exhibit (fixed as D6).
- **Regeneration, not editing.** Every reported number is produced by a script from a seeded run (`PROVENANCE.md`), and a test fails if a
  document is stale.
- **Secrets.** Model keys are read only from the environment or an ignored `.env` file and are never committed.

## Language models inside the product

The optional `courtroom/llm/` layer (AI lawyer, case drafting, narration) is off by default, never imported by the core (a test checks),
and never part of a certified result. The judge is a deterministic rulebook, not a language model. See `docs/LLM_ROLE.md`.
