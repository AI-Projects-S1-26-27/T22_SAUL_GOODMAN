# Rehearsal sheet: the live demo on 21 Nov

`DEMO_SCRIPT.md` is the five-minute walk-through (which case, which button, what to say). This sheet is what to do before it and what to do
when something goes wrong. Rehearse it once with a stopwatch and once with someone typing unfriendly input.

## The hour before

Run these on the machine that will be on the projector, on the venue's wifi if possible (the demo itself needs no internet).

```bash
python scripts/preflight.py                  # about a minute: every case plays to its pinned digest, every endpoint answers, no key needed
python -m pytest -q                          # the full suite
python -m courtroom serve                    # leave it running; open http://127.0.0.1:8000
```

Then, in the browser:

1. The badge in the courtroom header says **LIVE**. If it says **RECORDED**, the server is not answering: see the fallback table below.
2. Click **Enter the courtroom** with a real mouse click (browsers block audio started by a script) and let one trial play. Listen to the judge,
   both lawyers and one witness. Nothing should sound robotic; a robotic voice means a line fell back to the browser's voice
   (`python -m pytest tests/test_voice_coverage.py` checks every line of every recorded trial has a clip).
3. Turn the music slider to a level the room can talk over. Close other tabs, notifications and anything that plays sound.
4. Zoom the browser so the back row can read the verdict card. Test the Escape key: it closes the guided tour, the editor and the trial.
5. Do not set any API key variable. The language-model layer is off by default and the demo does not need it. If the model badge is lit,
   mention it only as an optional extra; if it is not lit, say nothing, because that is the normal state.

## Who says what (suggested, adjust to the slot)

| Time | Screen | One thing to say |
|---|---|---|
| 0:00 | Docket, an Everyday case | "Same exact judge every time: the verdict depends only on the record." |
| 0:45 | A case tagged Decided by the lawyers | "Change one style and the verdict changes; this case is where strategy matters." |
| 1:45 | Verdict card, **What would flip it?** | "The search re-scored the same record with the judge itself." |
| 2:30 | Surprises and seed | "The seed only matters to the verdict when surprises are on." |
| 3:15 | **Write a case yourself** | "The examiner's case goes through the same validator as ours." |
| 4:00 | **Surprise me** | "A case nobody wrote, found by search." |
| 4:40 | Strategy lab, last chapter | "End on a limitation, on purpose." |

Every member answers a question about their own package in the viva, so before the demo agree who answers if the examiner asks about
which package (see the proposal's ownership table). The presenter should not answer for another member.

## Inputs to hand the examiner (all of these are safe)

The editor clamps numbers and the server validates everything else (`tests/test_ui_editor_absurd.py` types these in a real browser):

- an empty title, a title of only spaces, a title with `<script>` tags: the case runs and the tags are shown as plain text;
- a title of hundreds of thousands of characters: the page says the case is too large, and nothing crashes;
- a negative, text, huge or empty number in a budget or reliability box: it is clamped to the allowed range;
- removing every exhibit: the empty-docket case runs and the defendant wins at the directed-verdict review.

The six edge fixtures (`edge-*` on the **Tricky tests** tab, plus the malformed and out-of-turn cases that tests cover) each give the
verdict the proposal fixed in advance.

## If something fails (fallback ladder)

| What you see | Do this | What to tell the examiner |
|---|---|---|
| Badge says **RECORDED**, or the live controls are missing | Check the terminal running `python -m courtroom serve`; restart it. Reload the page. | "The server stopped; the recorded trials still work." |
| Port 8000 is taken | `python -m courtroom serve --port 8001`, open that port. | Nothing. |
| The server will not start at all | Open the hosted site (the static copy of the same page, with recorded trials and the stored lab results). | "This is the offline version: every trial is recorded, the live controls need the server." |
| No internet and no hosted site | `cd courtroom/viz/web && python -m http.server 8080`, open `http://127.0.0.1:8080`. Same as the hosted site. | Same as above. |
| Audio is silent | Click once on the page, then **Enter the courtroom** again; check the browser tab is not muted and the volume slider is up. | Nothing. Subtitles are on screen. |
| A trial shows "SERVER DID NOT ANSWER: SAVED TRIAL" | The page fell back to the saved trial because the live request failed; restart the server. | Say so; do not present the saved trial as live. |
| Browser misbehaves | Open a private window (the guided tour and saved settings reset). | Nothing. |
| The examiner asks for something the demo cannot do | Say it is outside the model: the legal model is stylised and the thresholds are game parameters, not legal probabilities. | That sentence. |

## After the demo

Do not push or deploy anything during the session. Hosting the live server is prepared but not deployed (`docs/process/DEPLOY.md`); the team decides.
