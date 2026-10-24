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
