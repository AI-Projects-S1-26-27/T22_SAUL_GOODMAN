# SUBMISSION_PLAN.md - final submission for CS F407, Team 22 (Saul Goodman)

Written 17 Nov 2026. Presentation + live demo + individual viva: 21 Nov. Report: 23 Nov.
Official course repo: https://github.com/AI-Projects-S1-26-27/T22_SAUL_GOODMAN  (do NOT push; the team pushes)
Reference for the report's look and structure: the submitted proposal "AIPP_Team22_SaulGoodman" (LaTeX, BITS title
page, header "CS F407 Artificial Intelligence, ... | Team 22, Saul Goodman", numbered sections, booktabs tables,
figures with captions, numbered references). Its content is summarised in section 6 below.

## 1. What is graded (40 marks) and what answers each line

| Rubric line | Marks | What must exist |
|---|---|---|
| Report: technical depth & correctness | 5 | report/ PDF with Introduction, Background/Related Work, Method, Results/Evaluation, Discussion & Limitations, Individual Contributions, AI Usage. Every number generated from results/. |
| Track-specific (Demo) | 5 | Robust, polished, handles edge cases and unexpected input gracefully, not only the ideal path. Hosting the demo live online is "highly recommended". |
| Live demo | 15 | Presentation (exactly 6 slides) + live demo that runs first time. |
| Q&A | 5 | Every member answers an unscripted question about their own part. |
| GitHub code | 5 | Reproducible, organised, consistent; commit history across the semester (a repo assembled in the last 48 h is flagged). |
| Process & accountability | 5 | Work distribution among members over time; an honest reflection section. |

Also required by section 6 of the brief: AI usage section naming tools, what each was used for, and HOW THE OUTPUT WAS
VERIFIED; every member able to explain their part; a running trail of progress. "The AI generated it" is no excuse.

## 2. Presentation: exactly 6 slides, in this order
1. Title: team name (Saul Goodman), team number (22), project name (Strategic AI Agents in a Simulated Courtroom),
   GitHub link (the official repo above), project type (Demo track) and area (Agents & Game Theory; judge draws on KR&R).
2. Problem statement: the trial as a budgeted game with hidden flaws; the project question from the proposal.
3. Related work: AgentsCourt, Strategic Courtroom Framework, Zhang & Ashley (LLM-centred) vs our formal game with an
   exact judge; empirical game-theoretic analysis (Wellman). Our contribution in one sentence.
4. Methods: pipeline (case -> procedure -> agents -> judge -> game layer), the scoring formula, the four styles, the
   analysis methods (payoff Monte Carlo, exact Nash, bootstrap, sensitivity, best-response search, classic-game
   classifier, minimax/alpha-beta), each named in one line.
5. Results: at most 4 numbers, generated: strategy matters in 4 of 10 cases; best-response search beats the hand-written
   styles in some cases; stability figures; the lecture-concept findings including the honest "not found".
6. Project management and work division: planned vs actual timeline (gates G1-G3 with real dates from git log),
   owner per package, deviations from the proposal, what was cut.
No backup slides inside the deck (put any extras in a separate appendix file). Speaker notes on every slide with a
target time; total talk time short enough to leave room for the demo (assume about 6 minutes of slides; adjust once
the team knows the slot length). Build as .pptx (python-pptx or equivalent) plus a PDF export, charts rendered from
results/, readable when projected (large type, few words).

## 3. Report (report/ folder, LaTeX, PDF committed)
Match the proposal's style. Sections required by the brief, mapped to content:
- Introduction: problem, project question, contribution, what was delivered.
- Background / Related Work: from proposal section 3 and REPORT.md section 10. Read every source you describe; if a
  source cannot be read, cite by title only and claim nothing about its content.
- Method: case model, procedure (phase diagram), deterministic judge (formulas exactly as in code), perception model,
  agents, game layer, analysis methods, the lecture concepts and the relaxations each one assumes.
- Results / Evaluation: go through the proposal's evaluation plan (proposal section 8) row by row and say for each
  "done when" criterion whether it was met, with the evidence: hand-computed fixtures, known games, six edge
  fixtures, 2,500-trial fuzz, replay hashes, 4x4 matrices, bootstrap stability, +/-25% sensitivity, live-demo
  criteria (trial < 1 s, edge fixtures run live, examiner-made case never crashes). The proposal promised 200 common
  seeds per cell and 200 bootstrap resamples: check what the certified results used; if fewer, re-run at 200 with the
  documented scripts if it fits in time (a trial takes ~20 ms), otherwise state the deviation.
- Discussion & Limitations: 6 of 10 cases decided by evidence alone; weak stability under plain rules; sensitivity
  to the prior defect rate; relaxations of tree search; lookahead and the LLM layer are labelled extras; the legal
  model is stylised and thresholds are game parameters, not legal probabilities. Honest reflection on process.
- Individual Contributions: one short paragraph per member. Source of truth: the proposal's ownership table and the
  git history. Never invent a contribution. Where the history does not show a member's work, write
  "[TO BE WRITTEN BY <name>]" for that member to fill in themselves.
- AI Usage: tools (Claude Code wrote and refactored much of the code under review; Claude was used for planning,
  prompts and independent verification; the in-product Ollama/Gemini layer was built but never run live), what for,
  and how verified (tests, pinned digests, hand-computed fixtures, independent re-runs of the full suite, code review
  findings in docs/CODE_REVIEW.md). Leave a "[MEMBER ADDS OWN AI USE]" line per member.
- Deviations from the proposal: summarise DEVIATIONS.md (including D6, the impeachment fix, and the LLM layer being an
  optional exhibition against the proposal's "no language model" positioning).
- References in the proposal's numbered style.
REPORT.md stays as the long technical document; the PDF report is the graded one. Every number in either comes from a
script reading results/.

## 4. Repository
- README top: one paragraph, three commands to run, links to report PDF, slides, demo script, hosted site.
- Organise: process documents (FINAL_PLAN.md, SUBMISSION_PLAN.md, prompts) into docs/process/; no build junk tracked
  (egg-info, caches); .gitignore covers them.
- History: final-integration contains the teammates' history from 27 Sep but not the earlier local branches main
  (merged PR stack, Nov 4-5) and calibration-sweep, whose work was ported in. Record that ancestry without changing any
  file: `git merge -s ours --no-ff main calibration-sweep -m "Record the history of the earlier branches"` (or one
  branch at a time), then prove `git diff HEAD~1 HEAD` is empty. Never rewrite history, never change authors.
- Push plan (do not run): add remote `course` for the official repo, fetch it, and write docs/process/PUSH_PLAN.md
  with what is already there and the exact commands to publish all history without force (merge with
  --allow-unrelated-histories if the official repo already has a starter commit).

## 5. Demo readiness
- D6 left 9 spoken lines unrecorded, so the browser's robotic voice reads them. Record them per AGENTS.md section 4
  (Kokoro model files are downloaded outside the repo, never committed), then run the AGENTS.md 4.4 coverage check:
  missing must be 0 for every bundled trial.
- Run scripts/preflight.py and the full check list. Walk DEMO_SCRIPT.md end to end. Rehearsal script: which case to
  open, which buttons, what to say, a fallback if the server fails (the hosted static site).
- Edge cases live: every edge fixture plays cleanly; a malformed examiner case gives a readable error; absurd inputs
  in the editor (empty, huge, negative, non-numeric, script tags) are rejected politely.
- Hosting: the hosted site is static (recorded trials only). Prepare, but do not deploy, a config to host the live
  server (Dockerfile plus a short DEPLOY.md for a free host); the team decides.

## 6. Viva preparation (docs/VIVA_PREP.md)
For each member, from the proposal's roles: their package, a 5-line plain explanation, the 3 files to read, and
6 likely questions with short answers pointing to file and line. Plus whole-team questions: why no language model in
the core, why these constants, what a Nash equilibrium means here, what bootstrap stability measures, why 6 of 10
cases are evidence-decided, what alpha-beta prunes and why it gives the same value as minimax, what the AI tools did.

Members and packages (proposal section 11):
Aditya Singh - contracts/, cases/ | Divvij Y. Chichra - procedure/ | Lakshya Sachdeva - judge/ |
Mofasser A. Midda - agents/ | Rohan B. Pagire - gametheory/ | Pramit Khandelwal - engine/, api/, cli |
Rakshit Goel - viz/

## 7. Accountability risk to state plainly to the team (not to paper over)
Git history shows commits from very few members. The rubric grades work distribution over time and adjusts individual
grades by viva performance. The fix is real work by each member in their own name (their contributions paragraph,
their viva notes, reviewing and testing their package), never rewriting authorship or inventing contributions.
