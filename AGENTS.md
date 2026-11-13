# AGENTS.md: how to change this project safely

Rules for anyone (person or coding agent) changing the Saul Goodman Courtroom. Read the section for the part
you're touching before you start, and finish its checklist before you push.

The project has two halves:

- **The engine** (`courtroom/`, Python): cases, lawyer agents, the rulebook judge, game theory. It decides
  *what happens* in a trial. Deterministic: same case, styles and seed give the same events, every time.
- **The web app** (`courtroom/viz/web/`, static HTML/JS, no build step): plays a trial in a 3D courtroom with
  voices and music. It decides *how it looks and sounds*. The deployed site uses only pre-run trials from
  `data/bundle.js`; the local server (`python -m courtroom serve`) can also run trials live.

---

## 1. Which files hold what

| You want to change | Edit | Then also |
|---|---|---|
| A case, its evidence or witnesses | `courtroom/cases/library.py` | §2 bundle, §3 story, §4 voices |
| How a lawyer style plays | `courtroom/agents/` | §2 bundle, §4 voices |
| What anyone *says* (openings, exhibit lines, witness testimony, closings) | `courtroom/viz/web/story.js` | §4 voices |
| Generic courtroom lines (objections, rulings, "No objection", the oath) | `narrate()` and `witnessBeats()` in `courtroom/viz/web/app.js` | §4 voices |
| What an exhibit looks like (note, text message, receipt, CCTV still) | `courtroom/viz/web/artifacts.js` | nothing |
| The 3D room, people, camera shots | `courtroom/viz/web/courtroom3d.js` | §6 check |
| Music and sound effects | `courtroom/viz/web/sound.js` | §5 levels |
| Page layout and colours | `courtroom/viz/web/index.html`, `styles.css` | §6 check |
| The strategy lab page (game theory chapters, charts, analyst chat) | `courtroom/viz/web/lab.html`, `lab.js`, `lab-math.js`, `lab.css` | §7 |
| The analyst's Ollama backend | `courtroom/api/analyst.py` | §7 |

Every spoken line is built from the trial events plus `story.js`. **If a line's text changes in any way,
even one comma, its recording no longer matches and must be re-recorded** (§4).

---

## 2. Rebuild the trial bundle after engine changes

The deployed site can only play trials that are in `courtroom/viz/web/data/bundle.js`.

```bash
python -m pytest                          # must pass first
python -m courtroom export --workers 4    # rewrites data/bundle.js (all 16 pairings of the 4 UI styles, every case)
```

- The UI styles are `aggressive` (Bold), `conservative` (Careful), `adaptive` (Smart) and `reckless` (Wild).
  `chaos` is a fuzzing agent for tests; keep it out of the UI.
- A new case needs a `tags` entry so the docket can file it: `everyday`, `edge-case`, or neither (serious).
- After exporting, re-record voices (§4): new trials usually contain new lines.

---

## 3. Writing the story (`story.js`, `artifacts.js`)

- Plain, everyday language. Short sentences. No legal jargon without an explanation.
- Every exhibit in a case needs an entry in `story.js` (`say` and `short`). Testimony and expert exhibits also
  need `witness` ("Name, role") and `wit` (what the witness says on the stand).
- The witness's `say` line must contain "… calls <Name>, <role>." followed by the lawyer's question. The app
  splits it into the call, the oath and the question, so keep that shape.
- Non-witness exhibits get a picture of the real thing in `artifacts.js` (`note`, `sms`, `receipt`, `log`, `cctv`,
  `photo`, `doc`, `ledger`, `ad`, `chat`).
- Everything is fictional. No real people, companies or brands.

---

## 4. Voices: record the audio, then check it plays

Speech is **pre-recorded**, so every device hears the same voice for each character. The browser's own
voice is only a fallback for lines that were never recorded. That fallback should never be heard on the
deployed site.

### 4.1 One-time setup (about 120 MB, kept outside the repo)

```bash
pip install kokoro-onnx soundfile onnxruntime numpy
# ffmpeg must be installed (winget install Gyan.FFmpeg, brew install ffmpeg, apt install ffmpeg)
```

Download from Hugging Face, `onnx-community/Kokoro-82M-v1.0-ONNX` (Apache-2.0):

- `onnx/model_quantized.onnx`
- `voices/<name>.bin` for every voice in the cast (`MAIN` and `WITNESS` in `scripts/record_voices.py`)

Pack the voices into one file:

```bash
python -c "import numpy as np,glob,os; np.savez('voices.npz', **{os.path.basename(f)[:-4]: np.fromfile(f, dtype=np.float32).reshape(-1,1,256) for f in glob.glob('voices/*.bin')})"
```

Do not commit the model or `voices.npz`. Only the MP3s and `manifest.json` belong in the repo.

### 4.2 Record (do this after any change from §1 that touches spoken text)

```bash
node scripts/collect_lines.cjs > lines.json
python scripts/record_voices.py lines.json --model model_quantized.onnx --voices voices.npz
# add --ffmpeg "C:\path\to\ffmpeg.exe" if ffmpeg isn't on Python's PATH
```

- `collect_lines.cjs` runs the app's own narration over every trial in the bundle and lists each unique
  (speaker, text) pair. Always regenerate `lines.json`; never edit it by hand.
- `record_voices.py` only records lines that don't have an MP3 yet. It rewrites
  `courtroom/viz/web/voices/manifest.json`, which maps `who|text` to a file. Use `--force` to re-record everything
  (for example after changing a character's voice).
- Old MP3s that no line uses any more are harmless, but you can delete files not listed in the manifest.
- Expect about 1 minute of recording time per minute of speech on a laptop CPU. Run it in the background.

### 4.3 The cast is fixed

The voice for every character lives in `MAIN` and `WITNESS` in `scripts/record_voices.py`:
judge `bm_george`, Accuser `bf_emma`, Defender `am_michael`, bailiff `am_adam`, one fixed voice per witness.
A new witness must be added to `WITNESS` (a female or male voice that suits them), or it gets a generic
default. Change a voice only on purpose, then re-record that character with `--force`.

### 4.4 Check the recordings, then check they play

Recording and playback are separate steps. Do both:

1. **Coverage:** in the browser console on the running site, every line in every bundled trial must have a clip:

   ```js
   const man = await (await fetch("voices/manifest.json")).json(); let miss = 0;
   for (const t of Object.values(COURTROOM_BUNDLE.trials)) { S.caseId = t.case_id; S.trial = t;
     for (const ev of t.events) for (const b of narrate(ev).beats)
       if (!man[(b.who === "witness" ? "witness:" + b.name : b.who) + "|" + b.text]) miss++; }
   miss // must be 0
   ```

2. **Playback:** open the site, click **Enter the courtroom** with a real mouse click (browsers block audio
   started by scripts), and listen to the judge, both lawyers and a witness. Nothing should sound robotic. A
   robotic voice means a line fell back to browser speech: re-run §4.2.
3. Spot-check a few MP3s directly in a media player, especially new witnesses.

---

## 5. Music and sound

All sound is synthesised in `sound.js`. There are no audio files to manage.

- Music defaults to **full volume**. The slider in the courtroom header is saved per browser
  (`court-music-volume-v2`; change the key if you change the default so old saved values don't override it).
- Music **ducks under speech** (`Sound.duck`). Keep it that way so voices stay clear.
- Loud moments (the opening logo on first entry, the verdict themes) play on `featureBus`. A limiter on the
  master output keeps the peak level under 1.0. Measure before you push: anything that peaks near or above 1.0
  needs taming.
- The verdict theme must start the moment the verdict card appears (no scheduling delay).

---

## 6. Before you push

```bash
python -m pytest
node --check courtroom/viz/web/*.js
```

- **Cache-busting:** after changing any web file, bump the `?v=N` on every `<script>` and stylesheet link in
  `index.html`, or returning visitors may keep the old file.
- **Browser check:** pick an everyday case, enter the courtroom, step through with Next. Watch for:
  - a witness walking to the stand, swearing the oath and testifying
  - an exhibit card with its stamp
  - the bailiff carrying a document
  - the verdict card and its music
  - no console errors
- **Deploy:** pushing `main` on `BinaryCoder3012/AI_Project` deploys to Vercel automatically
  (`vercel.json` serves `courtroom/viz/web`), usually within a minute. Confirm with
  `curl -s https://ai-project-weld-omega.vercel.app/ | grep app.js`.
- Never force-push `main` without first saving the remote `main` to a backup branch.

---

## 7. The strategy lab

The lab is its own page, `courtroom/viz/web/lab.html`, linked from the home page's nav and from the "Want to
know why?" card. It has its own light "casebook" theme (`lab.css` flips the colour tokens for `body.lab-page`).
It does not change the courtroom, the trial player, the bundle or any spoken line, so it never needs a voice
re-record.

- **Every chapter has the same five parts**, built by `chapter()` in `lab.js`: a plain-language lead, "How to
  read it", the chart, "What it says for this case" (written from the live numbers by `says()`), and "Show the
  working". Keep that shape when adding a chapter, and follow §3's writing rules: plain words first, every
  game theory term explained where it first appears and listed in the glossary chapter.
- **Numbers come from trials, never from the model.** `lab-math.js` builds the 4x4 payoff table from trial
  ledgers and solves it (best replies, dominance, Nash equilibria, replicator dynamics). After changing it:

  ```bash
  node scripts/check_lab_math.cjs    # compares it with the engine's exact results in the bundle
  ```

- **Data.** Offline and on the deployed site the lab uses the one bundled trial per pairing (seed 0). With the
  local server running, "Run fresh trials" calls `/api/trial` for several seeds and averages them.
- **Chart colours** are set at the top of `lab.js`. They were checked for colour-blind separation on the
  paper background; re-check any new colour before using it for a series.
- **"Watch this trial in the courtroom"** links to `index.html#watch=<case>|<accuser>|<defender>`.
  `handoff.js` on the home page reads that and selects the case and styles.
- **The analyst.** The chat box posts to `/api/analyst` on the local server, which forwards to Ollama Cloud
  and then to a local Ollama (`http://localhost:11434`). If neither answers, the page's built-in analyst
  replies from the same numbers, so the chat always works.
- **The API key lives in `.env` at the repo root** (`OLLAMA_API_KEY=...`, optional `OLLAMA_MODEL`,
  `OLLAMA_LOCAL_MODEL`). `.env` is git-ignored. Never put the key in any file under `courtroom/viz/web/`:
  that folder is published as-is. The deployed site has no analyst route yet, so it uses the built-in analyst.
- **Cache-busting** (§6) applies to `lab.html` too: bump its `?v=N` along with `index.html`.


---

## 8. Live controls, the language-model layer and the analysis results

These parts were added later and have their own rules. None of them may change a recorded trial or a spoken line.

**The invariant that guards everything.** `tests/golden/bundle_digests.json` pins the digest of every trial in `data/bundle.js` and
`tests/golden/lines_baseline.json` pins every spoken line. `python -m pytest tests/test_bundle_digests.py` re-runs them. If either
moves, you changed a recorded trial or a line and the voices are stale: stop and find out why before going on. New engine behaviour
goes behind a flag that defaults to today's rules (see `Surprises`).

| You want to change | Edit | Then also |
|---|---|---|
| Courtroom surprises (what they do, their chances) | `Court` in `courtroom/engine/trial.py`, `Surprises` in `courtroom/contracts/models.py` | `tests/test_surprises.py`; the pinned digests must not move |
| Live controls on the home page (seed, badge, editor, Surprise me, tipping, explainer, AI box) | `courtroom/viz/web/live.js`, `live.css`, hooks in `app.js` | bump `?v=N` in `index.html`; `node --check`; step through in the browser with the server on |
| Spoken lines for a new kind of event | `narrate()` in `app.js`. New lines have no recording, so the browser's own voice speaks them | do not change an existing line |
| Lab chapters that need the server or the results | `courtroom/viz/web/lab-extra.js` | `python scripts/build_analysis_js.py` after any change in `results/`; bump `?v=N` in `lab.html` |
| Anything a model does | `courtroom/llm/` | nothing in the core may import it (a test checks); add a stub test; read `docs/LLM_ROLE.md` |
| A certified result | run `scripts/run_analysis.py` or `scripts/run_oracle_results.py`, which write `results/` | then `python scripts/build_analysis_js.py` and `python scripts/render_docs.py` |
| Numbers in `REPORT.md`, `PROVENANCE.md`, `DEMO_SCRIPT.md` | never by hand: edit `scripts/render_docs.py` | `python scripts/render_docs.py --check` (a test runs it) |

**Rules for the model layer.**

- Keys come only from `.env` or the environment. Never print one, commit one or put one under `courtroom/viz/web/`. `.env` is git-ignored.
- Every model answer is cached on disk (`courtroom/llm/cache/`). Run live features against the stub (`scripts/stub_ollama.py`, or
  `COURTROOM_LLM_CACHE=/tmp/x.json` so a stub's answers do not land in the repo's cache), and never commit a cache or a result produced by a stub.
- A trial a model played is `certified: false` and must never be averaged into a payoff table, bootstrap, sensitivity run or search.
- Tests never touch a network: use `tests/llm_stub.py`.

**Rules for results.** A search result is whatever it found. Do not change a case, a parameter or a seed after seeing a result to make it
look better; if the method changes, re-run everything and say so.


---

## 9. The lecture concepts: classic games, Pareto, security values, the trial tree, lookahead

These parts read results or search the trial; none may change a recorded trial, a spoken line or the certified styles.

| You want to change | Edit | Then also |
|---|---|---|
| How a 2x2 game is named (prisoner's dilemma, stag hunt, ...) | `courtroom/gametheory/classic.py` | `tests/test_classic.py` (textbook matrices, relabelling, rescaling, noise); re-run `scripts/run_analysis.py classic` (and `--surprises`) and `scripts/run_classic_search.py` |
| Pareto cells, security values, the minimax theorem check | `courtroom/gametheory/efficiency.py` | `tests/test_efficiency.py`; re-run `scripts/run_analysis.py efficiency` (and `--surprises`) |
| The trial tree (minimax, alpha-beta, move ordering) | `courtroom/gametheory/search.py` | `tests/test_search.py`; re-run `scripts/run_tree.py` |
| The lookahead lawyer | `courtroom/agents/lookahead.py` | `tests/test_lookahead.py`; re-run `scripts/run_lookahead.py` (and `--surprises`) |
| The chapters "Which classic game is this?", "Is the equilibrium efficient?", "What can each side guarantee?", "Thinking ahead" | `courtroom/viz/web/lab-extra.js`, `lab.css` | `python scripts/build_analysis_js.py`; bump `?v=N` in `lab.html`; `node --check` |
| Numbers in `REPORT.md` and `DEVIATIONS.md` for these | `scripts/render_docs.py` (never by hand) | `python scripts/render_docs.py` then `--check` |

Rules that matter here:

- **The tree uses the engine's rules, not a copy.** A node is a real `Court` with logging switched off; legal moves come from `validate` and the
  judge, moves are applied by `Court._dispatch`, values come from the judge and `utilities`. `tests/test_search.py` replays recorded trials
  through the tree and compares. If you change how the engine takes a step, that test is the one that tells you the tree has drifted.
- **The open-file game is a relaxation** (both sides see everything, no perception noise, zero-sum payoff). Never present its values as the
  certified game's. Any new "dominated move" you leave out of the search needs a test that putting it back leaves the value unchanged.
- **Lookahead is an exhibition.** It must read only its `PartyView` and the public `Oracle` (a test checks the source), must not be added to
  the four certified styles, the bundle or any payoff table behind a certified claim, and is labelled "exhibition, not certified". Do not tune
  it after seeing its comparison; if you change it, say so and re-run everything.
- **Search results are whatever they found.** "Not found" is a result. Do not change a case, a tolerance or a seed to make a lecture game appear;
  if the method changes, re-run both modes and say so in the report.

