# Running the language-model layer on Ollama

Ollama is a second provider behind the same client interface as Gemini. It runs on your own machine, needs no key and
costs nothing per call. It is **not** part of the certified analysis: like Gemini, its output is an exhibition, not equilibrium
analysis, and nothing it writes can change a verdict, a digest or a payoff matrix.

**What is and is not verified.** The code and its wire format are tested against a stub of the Ollama API
(`tests/test_ollama.py`, 22 tests, no network). Ollama is not installed on the machine this was written on, so it has
**not** been run against a real server, and the speed figures below are estimates, not measurements. The first thing to do
before the demo is the 3-minute check at the end of this page.

## One-time setup (run once, before the demo)

```bash
brew install ollama            # or install the app from https://ollama.com
brew services start ollama     # starts the server; `ollama serve` in a spare terminal also works
ollama pull qwen3:8b           # about 5.2 GB download
python -m courtroom llm-models --provider ollama   # should list qwen3:8b and mark it "configured"
```

Then, in the shell you will demo from:

```bash
export COURTROOM_LLM_PROVIDER=ollama     # optional: makes every LLM feature use Ollama by default
```

## Using it

```bash
# spoken argument lines for one trial (never affects the verdict)
python -m courtroom run --case helix-espionage --narrate --provider ollama

# a small live exhibition: Ollama as a lawyer against the four fixed styles
python -m courtroom llm-exhibition --provider ollama --seeds 2

# replay it offline, any time, with the server stopped
python -m courtroom export-exhibition --results results/llm_exhibition_ollama.json --out /tmp/ollama-exhibition
```

Every live answer is written to `courtroom/llm/cache/responses.ollama.json`, keyed by the prompt and the model, so a later
run replays it without calling the server. The shipped Gemini cache and `results/llm_exhibition.json` are never touched:
Ollama has its own cache file and its own results file, and its cache keys begin `ollama/`.

To show an Ollama exhibition in the web page, export it over the shipped one and restore afterwards:

```bash
python -m courtroom export-exhibition --results results/llm_exhibition_ollama.json --force
git checkout courtroom/viz/web/data/exhibition.js     # put the Gemini exhibition back
```

Without `--force` the export refuses to replace an exhibition from a different provider or model.

## Which model, and why: `qwen3:8b`

The machine is an 18 GB M3 Pro. Apple silicon shares memory between CPU and GPU, and macOS lets the GPU wire roughly two
thirds of it, so about **12 GB is usable for a model plus its working memory**, while the browser and the app also need
room.

| Model (Ollama tag) | Download | Fits an 18 GB machine? | Verdict |
|---|---|---|---|
| `qwen3:4b` | 2.5 GB | easily | fallback if the machine is busy; weaker at following the move-selection format |
| **`qwen3:8b`** | **5.2 GB** | **comfortably, about 6 GB resident with the small context used here** | **recommended** |
| `gemma3:12b` | 8.2 GB | yes, about 9 GB resident | good alternative with no reasoning mode; slower |
| `qwen3:14b` | 9.3 GB | tight, about 10 GB resident leaves little for other apps | step up for nicer narration if nothing else is open |
| `qwen3:30b`, `qwen3:32b` | 19 to 20 GB | **no** | does not fit |

Reasons for `qwen3:8b`:

1. **The jobs are small.** The agent picks one number from a short list of legal moves, and the narrator writes one line of at
   most 30 words. An 8-billion-parameter model handles both; the Gemini run used a small "flash-lite" model for the same jobs.
2. **It supports what the client asks for**: schema-constrained JSON output (so an illegal move cannot be expressed) and a switch to
   turn off its hidden reasoning (`think: false`), which would otherwise spend the output budget before answering.
3. **Speed.** The prompts are a few hundred tokens and the answers a handful, so time is dominated by reading the prompt.
   My estimate for this class of model on this chip is about 1 to 3 seconds per call, so the 363 calls of the Gemini exhibition would
   take roughly 10 to 20 minutes cold, and nothing once cached. This is an estimate to be confirmed, not a measurement.
4. **Memory headroom.** Leaves about half of the usable GPU memory free, so the model is not swapped out mid-demo.

To change it: `export COURTROOM_OLLAMA_MODEL=qwen3:14b` (then `ollama pull qwen3:14b`), or pass `--model` to a command.

## Quick check before the demo (3 minutes)

```bash
python -m courtroom llm-models --provider ollama                       # the server answers and the model is listed
python -m courtroom run --case helix-espionage --narrate --provider ollama   # lines appear; "Ollama calls: N ... free"
python -m courtroom llm-exhibition --provider ollama --seeds 1 --max-calls 20
```

If the server is not running the commands do not crash: every call falls back to the template or to the Adaptive policy and the
message says `run ollama serve`. If the model is missing it says `run ollama pull qwen3:8b`.

## What stays true

* Nothing in `courtroom.engine`, `judge`, `procedure`, `agents`, `cases`, `contracts` or `gametheory` imports `courtroom.llm`
  (a test scans for it).
* No test makes a network call; the suite replaces the HTTP layer and fails loudly if anything tries to open a connection.
* The label is unchanged: **exhibition, not equilibrium analysis**. A local model is not bit-stable across hardware or Ollama
  versions even with a fixed seed, so a cold-cache rerun on another machine can differ.
