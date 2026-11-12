# What the language model may and may not do

The courtroom has a rulebook judge. It scores a record with exact `Fraction` arithmetic, and the same record always gets the same
verdict. A language model is an optional extra around that judge. This page says exactly where it may be used and where it may not,
because the whole project is only worth anything if the second list is never crossed.

## What it may do (all optional; the system runs with no key, no Ollama and no network)

| Feature | Where | What the model does | What stops it going wrong |
|---|---|---|---|
| **AI lawyer** (strategy `llm`) | `courtroom/llm/policy.py` | Picks one move from a numbered list of the moves that are legal right now, and says why in one sentence. | The list is built from the same rules the validator uses, so an illegal move cannot be expressed. A bad or out-of-range answer is re-asked up to twice, then the Smart style plays the move. Every fallback is counted and shown after the trial. It sees only what a human lawyer's `PartyView` shows, including the same noisy belief about the other side's exhibits. |
| **Case from plain English** | `courtroom/llm/draft.py`, `POST /api/case/draft` | Writes a case file as JSON. | The pydantic contracts validate it. Errors go back to the model for up to two repairs. Sanity checks (both sides have evidence, every point has something bearing on it, numbers in range) must pass. The result opens in the editor so a person sees and can change every number. |
| **Lines for unscripted cases** | `courtroom/llm/narrator.py`, `POST /api/narrate` | Words each exhibit's spoken line from the exhibit's own text. | A line is kept only if every number in it is in the source text and every capitalised word is in the source or an ordinary courtroom word. Otherwise the plain generated line stays. |
| **Verdict explanation wording** | `courtroom/llm/explainer.py` | Rephrases the explanation the judge's own numbers produce. | Any number or exhibit id that is not in the facts refuses the text; the template is used. |
| **Analyst chat** | `courtroom/api/analyst.py` | Explains numbers the lab has already computed. | It is told to use only the lab data it is given. |

The model reads from the first backend that answers, in this order: Ollama Cloud (`OLLAMA_API_KEY`), a local Ollama
(`http://localhost:11434`), then Gemini (`GEMINI_API_KEY`). Keys come only from `.env` or the environment and are never printed,
logged or placed under `courtroom/viz/web/`.

## What it may never do

1. **Decide a verdict.** The judge's `deliberate` takes admitted exhibits and impeachment counts. No model output is an input to it.
   A test (`test_the_judge_decides_the_same_whatever_the_model_says`) re-scores the record of an AI-played trial and checks that the
   judge reaches the same verdict.
2. **Enter a certified payoff.** `/api/game` rejects the `llm` strategy. Trials a model played are marked `certified: false` and are
   never averaged into a payoff table, a bootstrap, a sensitivity run or the best-response search.
3. **Change a recorded trial.** The deployed site replays trials recorded with the hand-written styles. `tests/golden/bundle_digests.json`
   pins the digest of every one, and a test re-runs them. The model layer registers itself as a strategy at start-up; loading it
   changes no other trial.
4. **Be imported by the core.** `engine`, `judge`, `procedure`, `agents`, `gametheory`, `cases` and `contracts` import nothing from
   `courtroom/llm`. A test scans for it and another loads the core in a fresh interpreter and checks no model code was loaded.
5. **Be trusted about facts.** What a model says about a case is the model's. The reason shown beside an AI lawyer's move is its
   *thinking*, displayed on screen and never spoken as if it were testimony.

## Reproducibility, stated plainly

Every model answer is cached on disk under a hash of (system prompt, prompt, model, temperature, output limit). Temperature is 0. A
cache hit never calls out, so a recorded AI-lawyer trial replays exactly on any machine, offline: the cache is looked up under every
model name it has seen. A cache **miss** on another machine calls a provider, and providers do not promise the same text over time
even at temperature 0. That is why nothing a model produced is allowed anywhere a number has to be reproducible from scratch.

## Why a best-response check cannot certify an opaque policy

For the four hand-written styles the project can say something strong. Each style is a few numbers (how many known defects it will
tolerate, how much gain it needs, how readily it objects ...). `courtroom/gametheory/oracle.py` searches over those numbers for a
counsel that beats the current equilibrium mix, adds what it finds to the game and solves again. If it finds nothing within its
budget, that is evidence the styles were hard to beat *in that family*.

A language model is not in that family. It is a function from a prompt to text, with no small set of parameters to search, no
guarantee of the same answer twice from a cold start, and no way to enumerate the strategies it could play. So:

* A best-response search over its behaviour would only ever probe the prompts we thought to write. Failing to beat it proves nothing
  about the model, only about our search.
* We cannot put it in a payoff table, because the table's entries must be reproducible averages over seeds, and a cold-cache model is
  not a function of the seed.
* The honest use is an **exhibition**: play it against the four styles on a few seeds, show the results labelled "exhibition, not
  certified", and say how often it fell back to the Smart style (a high rate means the table is mostly measuring Smart).

Everything certified in this project is a statement about the deterministic styles and the exact judge. The model is there to make
the demo easier to drive and to show what a different kind of counsel looks like, not to be a source of evidence.
