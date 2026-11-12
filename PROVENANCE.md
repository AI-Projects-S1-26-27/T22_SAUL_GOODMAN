# Provenance: one command per claim

Every claim the project makes can be checked with one command. Numbers are never typed into prose: they are read from files in
`results/`, and the regions that show them are generated (`python scripts/render_docs.py --check` fails if one is stale).

Set up once: Python 3.11 or newer and `pip install -e ".[dev]"`. Nothing below needs a key, Ollama or a network unless it says so.

## The recorded trials and the voices did not change

| Claim | Command | Where it is recorded |
|---|---|---|
| Every trial in the web bundle still produces the digest it was recorded with, so no voice clip is stale. | `python -m pytest tests/test_bundle_digests.py` | `tests/golden/bundle_digests.json` |
| The spoken lines are exactly the ones the voices were recorded for. | `node scripts/collect_lines.cjs \| diff - tests/golden/lines_baseline.json` | `tests/golden/lines_baseline.json` |
| The lab's browser maths agrees with the engine's exact analysis. | `node scripts/check_lab_math.cjs` | `courtroom/viz/web/data/bundle.js` |

## The judge is exact and deterministic

| Claim | Command |
|---|---|
| The same case, styles and seed give a bit-identical trial and a valid hash chain. | `python -m courtroom verify --case helix-espionage` |
| ...also with courtroom surprises on. | `python -m courtroom verify --case helix-espionage --seed 6 -p adaptive -d aggressive --surprises` |
| Verdict arithmetic is exact (`Fraction`), permutation invariant, and follows the rules. | `python -m pytest tests/test_judge.py tests/test_procedure.py tests/test_engine.py` |
| Nothing crashes under fuzzing (chaos agents, generated cases). | `python -m courtroom stress --cases 100` |
| The whole suite passes with no key, no Ollama and no network. | `python -m pytest` |
| Style, imports and syntax. | `ruff check courtroom tests scripts` and `node --check courtroom/viz/web/*.js` |

## What the live controls compute

| Claim | Command | Output |
|---|---|---|
| Whether strategy matters is measured, not assumed. | `python -m courtroom matters` | the table in `REPORT.md` section 6.1 comes from `python scripts/run_analysis.py matters` into `results/matters.json` |
| Contested cases can be found by search. | `python -m courtroom find --count 40` | a list of `gen-<seed>` cases playable in the room |
| The tipping point really flips the judge's verdict, one step before it does not. | `python -m pytest tests/test_live_api.py` | |
| Courtroom surprises are seeded, off by default and exact. | `python -m pytest tests/test_surprises.py` | |
| The page's digest check is the same one the engine uses. | `python -m courtroom serve`, then "Run it again and compare" | |

## The game-theory results

| Claim | Command | Output file |
|---|---|---|
| Stability of each case's conclusion under resampling. | `python scripts/run_analysis.py bootstrap --workers 4` (and `--surprises`) | `results/bootstrap.json`, `results/bootstrap_surprises.json` |
| Whether conclusions survive changes to the rulebook's constants. | `python scripts/run_analysis.py sensitivity` (and `--surprises`) | `results/sensitivity.json`, `results/sensitivity_surprises.json` |
| Whether the four hand-written styles can be beaten. | `python scripts/run_oracle_results.py --workers 4` | `results/oracle/<case>.json` and `<case>_surprises.json` |
| ...for one case, with your own budget. | `python -m courtroom oracle --case helix-espionage --budget 60 --workers 4` | |
| The lab and the report read those files, not new runs. | `python scripts/build_analysis_js.py` then `python scripts/render_docs.py` | `courtroom/viz/web/data/analysis.js` |
| The docs are not out of date. | `python scripts/render_docs.py --check` | |

The result files this version of the docs was generated from:

<!-- BEGIN GENERATED:files -->
| Result file | sha256 (first 12) | Size |
|---|---|---|
| `results/bootstrap.json` | `a6d12d32968a` | 24 KiB |
| `results/bootstrap_surprises.json` | `68c6cc900f5a` | 24 KiB |
| `results/matters.json` | `d4c87d4ce5a1` | 6 KiB |
| `results/matters_surprises.json` | `0666468af658` | 6 KiB |
| `results/oracle/broken-bike.json` | `ae02f6839677` | 6 KiB |
| `results/oracle/broken-bike_surprises.json` | `447612ef1bf4` | 4 KiB |
| `results/oracle/helix-espionage.json` | `c622d2855e70` | 8 KiB |
| `results/oracle/helix-espionage_surprises.json` | `9a00cf6de679` | 6 KiB |
| `results/oracle/kestrel-av.json` | `267180fa861f` | 4 KiB |
| `results/oracle/kestrel-av_surprises.json` | `a34e2704d278` | 6 KiB |
| `results/sensitivity.json` | `15e9ca0d1157` | 11 KiB |
| `results/sensitivity_surprises.json` | `3a373cf16d44` | 11 KiB |

160 recorded trials are pinned in `tests/golden/bundle_digests.json`; 540 spoken lines in `tests/golden/lines_baseline.json`.
<!-- END GENERATED:files -->

## The language model

| Claim | Command |
|---|---|
| The core imports nothing from `courtroom/llm`, and loading it loads no model code. | `python -m pytest tests/test_llm.py -k core` |
| The AI lawyer is only ever offered legal moves, sees only what a `PartyView` shows, falls back to Smart and counts every fallback. | `python -m pytest tests/test_llm.py` |
| A cached AI-lawyer trial replays exactly with no backend. | `python -m pytest tests/test_llm.py -k cached` |
| Case drafting validates, repairs at most twice and sanity-checks. | `python -m pytest tests/test_llm_api.py -k draft` |
| Narration refuses a line that invents a number or a name. | `python -m pytest tests/test_llm_api.py -k line` |
| A key never appears in a request URL or an error. | `python -m pytest tests/test_llm.py -k key` |

**Which model runs were live and which were stubbed.** No model backend was available while this version was assembled (no key was
set and no Ollama was running). Every model-dependent feature was therefore built and tested against a stub server (`tests/llm_stub.py`),
and the interface was exercised by hand against a stand-in (`scripts/stub_ollama.py`, which reports its model as `stub-model`).
No result in `results/` involves a model, and the AI-lawyer exhibition table has not been run (see `REPORT.md` section 6.5). To run it
for real, put `OLLAMA_API_KEY` (or `GEMINI_API_KEY`) in a git-ignored `.env`, or start `ollama serve`, then run
`python -m courtroom exhibition --json results/exhibition.json` and `python scripts/render_docs.py`.
