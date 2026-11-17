# Prompts given to the coding assistant

The course asks teams to say how AI tools were used. The coding assistant (Claude Code) was driven by written instructions from
Pramit Khandelwal, who pasted them into the session. This page records them so the process is inspectable.

**What is recorded here, and what is not.** The instruction below is reproduced verbatim as it was given on 17 November 2026. The earlier
instructions (the finishing job in `FINAL_PLAN.md`, the strategy-lab and lecture-concept rounds, the UI audit and tours, and the code review)
were given in earlier sessions; their transcripts are not part of this repository, and this page does not reconstruct them from memory.
`FINAL_PLAN.md` and `SUBMISSION_PLAN.md` (in this folder) are the written specifications the sessions worked from.
\[TO BE ADDED BY Pramit Khandelwal: copies of the earlier instructions, if the team wants them in the repository\]

## The submission instruction (17 November 2026, verbatim)

```text
Work autonomously; do not wait for me. Repo ~/Downloads/AI_Project_clone, branch final-integration. The full specification is SUBMISSION_PLAN.md in the repo root: read all of it first and follow it. Also read AGENTS.md, HANDOFF.md, DEVIATIONS.md, REPORT.md, docs/CODE_REVIEW.md, and the submitted proposal, docs/proposal/AIPP_Team22_SaulGoodman.pdf, the reference for the report's style. Presentation, live demo and viva on 21 Nov; report on 23 Nov.

AIM. Produce everything the CS F407 final submission rubric grades, for 40 marks: report, 6-slide presentation, a polished robust live demo, viva preparation, an organised reproducible repo with honest history, and honest process and AI-usage sections.

DELIVERABLES, in this order, each committed before the next:
1. Demo readiness: record the 9 spoken lines left unrecorded by D6 per AGENTS.md section 4 (model files outside the repo), coverage check must show 0 missing; preflight and the full check list pass; every edge fixture and absurd editor input handled politely; rehearsal script with a fallback.
2. Presentation in presentation/: exactly 6 slides with the titles in SUBMISSION_PLAN.md section 2, .pptx plus PDF, charts from results/, speaker notes with timing.
3. Report in report/: LaTeX matching the proposal's style and title page, PDF committed, sections exactly as the brief requires plus deviations and references. Results section walks the proposal's evaluation plan row by row: met or not, with evidence. Reconcile the promised 200 seeds per cell and 200 bootstrap resamples with what was run: re-run with the documented scripts if it fits, otherwise state the deviation.
4. docs/VIVA_PREP.md: per member, their package, what to read, likely questions with answers pointing to file and line; plus whole-team questions.
5. Repo: README front page, process docs into docs/process/, record the earlier branches' history with merge -s ours and prove the tree unchanged, add remote course for the official repo, fetch it, write docs/process/PUSH_PLAN.md. Prepare a hosting config for the live server but do not deploy.

HONESTY RULES.
- Never invent a contribution, a result, a citation or an AI-usage claim. Individual contributions come from the proposal's ownership table and git history; where a member's work is not visible, write [TO BE WRITTEN BY name]. Leave a [MEMBER ADDS OWN AI USE] line per member.
- AI usage says plainly that Claude Code wrote and refactored much of the code and that Claude was used for planning and verification, and how each output was verified.
- Read every source before describing it; otherwise cite by title only.
- Every number in slides and report is generated from results/ by a script. Never edit a number by hand, never tune a case.
- Never rewrite history or change commit authors. Do not push anywhere.

STANDING INVARIANTS: judge exact and deterministic; tests never weakened; no network in tests; the language-model layer stays off by default and is described as an optional exhibition, consistent with the proposal's no-language-model positioning.

STOP AND ASK only if: a fix would change a recorded trial or pinned digest; a result in the report would contradict the slides or the proposal in a way you cannot state honestly; or a required file cannot be produced (for example no LaTeX engine and none installable).

DONE WHEN: pytest, ruff, node --check, check_lab_math.cjs, render_docs --check, the pinned-lines diff, voice coverage and preflight all pass; report PDF and slide PDF build from a clean checkout.

FINAL REPORT: list of deliverables with paths, every placeholder a teammate must fill, which proposal promises were met or not, the accountability risk in plain words, exact check output, and the push commands from PUSH_PLAN.md for me to run later.
```
