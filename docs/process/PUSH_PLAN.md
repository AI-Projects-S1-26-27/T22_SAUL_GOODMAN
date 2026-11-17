# Push plan (do not run until the team has decided; nothing here has been pushed)

Written 17 Nov 2026. Everything below was rehearsed in a scratch clone against a local bare repository standing in for the official one;
nothing was pushed to any real remote. **No force-push is needed or allowed. Never push to `origin` (the teammate's `BinaryCoder3012/AI_Project`).**

## What is where

| Remote | URL | State when this was written |
|---|---|---|
| `course` | https://github.com/AI-Projects-S1-26-27/T22_SAUL_GOODMAN.git (the official repository) | Already has `main` with **82 commits** by 8 author names, from 2 Oct to 11 Nov 2026 (the tip is `6d9cd17`). Its history shares **no common ancestor** with this branch. |
| `mine` | https://github.com/PramitKH26/saul-goodman-courtroom.git | `main` is an ancestor of `final-integration`, so a push fast-forwards. |
| `origin` | https://github.com/BinaryCoder3012/AI_Project.git | A teammate's repository. `origin/main` is an ancestor of `final-integration`. **Do not push.** |

This branch (`final-integration`) holds the work of this integration plus the earlier local branches' history (recorded by the merge
`Record the history of the earlier branches`, whose tree is identical to its first parent: `git diff HEAD^1 HEAD` is empty).

## Decide first (the team, not the assistant)

1. **The two histories disagree.** The official repository shows each member committing their own package from 2 Oct (contracts and cases from
   12 Oct, procedure 13 Oct, the judge 15 Oct, agents 17 Oct, the engine 18 Oct, game theory 19 Oct), while this branch's lineage starts with one commit
   on 27 Sep that already contains the whole core, and most of its core source files are byte-identical to the official repository's final versions.
   Publishing this branch onto the official `main` puts both timelines in one repository. Before you push, agree on a truthful account of how the
   official history was produced, and write it into the report (section 5.4, the red placeholder) and be ready to give it in the viva. Do not edit or
   re-date either history: the rules for this project are never to rewrite history or change authors.
2. **Who pushes.** The push needs write access to the official repository. Each author name keeps its authorship; the merge commit below is authored
   by whoever runs it.
3. **Whether to publish the hosted site from `mine`.** A push to `mine/main` may redeploy a static Vercel site if the repository is linked to one.

## Step 1: make sure what you push is what was checked

```bash
git switch final-integration
git status --short                      # only untracked files that are ignored locally (FINAL_PLAN.md, SUBMISSION_PLAN.md, _backup/) may appear
python -m pytest -q && ruff check courtroom tests scripts report presentation
for f in courtroom/viz/web/*.js; do node --check "$f" || break; done
node scripts/check_lab_math.cjs && python scripts/render_docs.py --check
node scripts/collect_lines.cjs | diff - tests/golden/lines_baseline.json && echo LINES_OK
python scripts/preflight.py
```

## Step 2: publish to your own repository (fast-forward only)

```bash
git fetch mine
git push mine final-integration:main    # refused (not forced) if mine/main has moved; then fetch and look first
```

## Step 3: publish to the official course repository without force

The official `main` already has history. Record it as an ancestor of this branch **without changing any file**, then the push is a fast-forward:

```bash
git fetch course
git merge -s ours --allow-unrelated-histories course/main -m "Record the official repository's history"
git diff --quiet HEAD^1 HEAD && echo "tree unchanged"          # must print: tree unchanged
git merge-base --is-ancestor course/main HEAD && echo "official history is an ancestor"
git push course final-integration:main                          # a fast-forward: no --force
```

If `git push` says it was rejected, `course/main` moved after your fetch (a teammate pushed). Run `git fetch course` and repeat the merge line
(a second `-s ours` merge), then push again. Do not use `--force`.

Rehearsal result (scratch clone, local bare repository seeded from `course/main`): the merge reported "Merge made by the 'ours' strategy", the tree was
unchanged, and the push moved `6d9cd17..8d4e4ab` as a fast-forward; the target then held 82 official commits, this branch's commits and the merge.

## Step 4: after the push

- On GitHub, open the commit history and the contributors graph and check every author name still has its own commits (authorship is untouched).
- Clone the official repository fresh and confirm the PDFs rebuild: `python report/build_report.py` (needs the `tectonic` LaTeX engine),
  `python presentation/build_slides.py --pdf` (needs python-pptx and Playwright's Chromium), `python scripts/make_figures.py` first if `results/` changed.
- If you host the live server, follow `docs/process/DEPLOY.md`; keep the static site as the fallback.

## What not to do

- No `git push --force`, no `git filter-branch` or rebase of published history, no changing authors or dates.
- No push to `origin`.
- No `git add -A` here: the folder holds untracked files that must stay out (`FINAL_PLAN.md`, `SUBMISSION_PLAN.md` at the top level, `_backup/`); the copies of the two plans are in `docs/process/`.
