# Demo script: five minutes, the examiner supplies the inputs

Start the local server, not the hosted site: `python -m courtroom serve`, then open <http://127.0.0.1:8000>. The badge in the room must
say **LIVE**. Everything below is computed in front of the examiner by the exact judge; nothing is replayed unless it says **RECORDED**.

Which cases to use, measured by `python -m courtroom matters` (stored in `results/matters.json`):

<!-- BEGIN GENERATED:demo_cases -->
- Cases where changing the styles flips the verdict (use these to show strategy mattering): `broken-bike`, `helix-espionage`, `kestrel-av`.
- Cases where it moves a little: `edge-poisoned-tree`.
- Cases where the evidence alone decides (show these as everyday trials, **not** as examples of strategy mattering): `aurora-defi`, `cookie-jar`, `edge-defense-only`, `edge-empty-docket`, `edge-mutual-exclusion`, `garden-dog`.
<!-- END GENERATED:demo_cases -->

Do not present a case from the last group as an example of strategy mattering: measured, it does not.

## 0:00 An everyday case, to show the room (about 45 seconds)

Pick an everyday case from the docket and enter the courtroom. Point at the **LIVE** badge: "this trial was computed just now". Ask
the examiner for a **seed** (the box in "Brief your lawyers") and run it. Click **Run it again and compare**: both digests match and
the hash chain is valid. Say plainly what you are about to see: in this case the evidence decides, so the verdict will not move
however the lawyers play. The docket tag on the card says so.

## 0:45 A case where the lawyers matter (about 60 seconds)

Go back to the docket and open one from the "lawyers move the verdict" group. Under **Does strategy matter here?** show the table of
all nine pairings. Ask the examiner to pick a style for each lawyer, enter the room, and let it play to the verdict. Go back, change
one style, play again: the verdict changes. Then open **Why this verdict?** on the verdict card: the judge's own numbers in plain
words.

## 1:45 Tip the verdict (about 45 seconds)

On the verdict card, under **What would flip it?**, read the first line: "if this exhibit were so many points less reliable, the verdict
flips". Press **Try it**. The whole trial plays again with that one change, and the verdict flips. Explain that the search re-scored
the same record with the judge itself, and that "try it" re-plays everything because the lawyers may play differently.

## 2:30 Surprises and the seed (about 45 seconds)

Tick **Courtroom surprises**, press **New seed** three times, and enter the room each time. A witness fails to appear, a digital record
has no certificate, a witness turns hostile. Say that this is what makes the seed matter to the verdict; with surprises off the seed
mostly changes the event log but not the outcome.

## 3:15 A case the examiner types (about 45 seconds)

Press **Write a case yourself**, or, if the model badge is lit, describe a dispute in a sentence or two and press **Draft it with AI**.
Either way it opens in the editor with every number visible. Change an exhibit's reliability, press **Run it here**, and read the
before and after: the verdict, how sure the judge is, the log-odds. Press **Watch it in the courtroom**. If the model drafted it, say
the model proposed the numbers and the examiner should check them; the judge is still the fixed rulebook.

## 4:00 A case nobody wrote, and the AI lawyer (about 40 seconds)

Press **Surprise me** on the docket. It searches generated cases for one where the lawyers move the verdict and plays it. The page says
it was found by search. If the **AI lawyer** style is offered, pick it for one side: the lawyer's thinking appears in italics (never
spoken), the badge says **NOT CERTIFIED**, and the verdict card says how often the model's answer was unusable and Smart stepped in. If
no model answers, that style is not offered, and that is the honest behaviour.

## 4:40 End on the best-response result (about 20 seconds)

Open the **Strategy lab**, chapter **Can a better lawyer be found?**, on one of the cases the search was run for. Read the headline
and say what the table of discovered lawyers shows in plain words, including whether the finding was confirmed on seeds nobody had
looked at. Then **How sure are we?**: say which conclusions are shaky. Ending on a limitation is deliberate.

## If something is not available

| Missing | What happens |
|---|---|
| A model backend | The AI lawyer and "Draft it with AI" are not offered; the manual editor still works; spoken lines for unscripted cases use plain generated text. |
| The local server | The hosted site shows **RECORDED** trials and the stored lab results, and says live features need the server. |
| Voices for unscripted lines | The browser's own speech is used; the recorded cast is only for the library cases. |

Before the session: `python -m pytest`, `node scripts/check_lab_math.cjs`, and `python scripts/render_docs.py --check` should all pass.

## Optional, about 60 seconds more: tie it to the lectures

Stay in the **Strategy lab** and walk four chapters, each computed from our own games:

1. **Which classic game is this?** Say what the chapter looked for: the prisoner's dilemma, stag hunt, battle of the sexes and chicken in
   every two-by-two corner of every case's table, and in generated cases found by search. Read the answer honestly, including "not found"
   for the games that do not occur; point at the corners that are matching pennies, and show one beside the textbook matrix. Do not claim
   a case is a dilemma that the chapter does not call one.
2. **Is the equilibrium efficient?** Pick a case and read whether its equilibrium is Pareto-efficient, or dominated for both sides.
3. **What can each side guarantee?** Show the security values and the minimax theorem line for the win-probability game: maximin equals
   minimax equals the Nash value. Say that the real game is not constant-sum, so there the security value is only a floor.
4. **Thinking ahead.** Show the table of nodes: plain minimax against alpha-beta with the best move first, with the same value every time.
   Open the drawn tree and point at a scissors line. Say plainly that this is the open-file version (both sides see everything, zero-sum),
   and that the lookahead lawyer below it is an exhibition. If the local server is on, pick **Lookahead** as one side's style in the room.
