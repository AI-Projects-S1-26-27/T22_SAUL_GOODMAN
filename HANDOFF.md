# Handoff

State of the `final-integration` branch (nothing pushed, nothing merged).

## What was not done, and why

### W3(c), the AI-lawyer exhibition table: shipped as a harness, live run skipped

- **Shipped:** `courtroom/llm/exhibition.py` and `python -m courtroom exhibition`. It plays the AI counsel against the four styles on both sides for the cases you choose, caches every model answer, labels the output "exhibition, not certified", and reports how often the model fell back to Smart. Tested against a stub (`tests/test_llm_api.py`, the exhibition tests), and the command is tested to refuse cleanly when nothing answers.
- **Skipped:** the live run that produces `results/exhibition.json`.
- **Reason, in the spec's terms:** a missing key is not a blocker. On 12 Nov 2026 there was no `OLLAMA_API_KEY`, no `GEMINI_API_KEY`, no `.env` and no Ollama (`python -m courtroom exhibition` exits with code 3 and runs nothing), so the harness was built against the stub and the live run was skipped. No stub output was saved as a result.
- **Where it shows:** the lab chapter "Can a better lawyer be found?" says "Not run yet" and `REPORT.md` section 6.5 says "Not run"; both fill themselves in from `results/exhibition.json` once it exists.
- **To finish it:** put a key in a git-ignored `.env` (or start `ollama serve`), run `python -m courtroom exhibition --json results/exhibition.json`, then `python scripts/render_docs.py`.


- **No live language-model run.** No key was set and no Ollama was running while this was built, so every model feature was built and
  tested against a stub (`tests/llm_stub.py`) and exercised by hand against `scripts/stub_ollama.py`. No file in `results/` involves a model.
- **The AI-lawyer exhibition table is not run.** The harness (`courtroom/llm/exhibition.py`, `python -m courtroom exhibition`) is built
  and tested; with a backend available, run it with `--json results/exhibition.json` then `python scripts/render_docs.py`.
- **No new voice clips.** The courtroom-surprise lines and lines for unscripted cases are spoken by the browser's own voice, by design,
  because recording them would not have changed any recorded trial but was out of scope. The recorded cast is untouched.
- **Agents do not know about surprises.** The lawyers' decision rules ignore the chance of a no-show, a missing certificate or a hostile
  witness. Making them aware would change their behaviour (and the equilibria) and is left as an open question.
- **Not deployed.** `vercel.json` serves `courtroom/viz/web`, so a push of the merged branch would publish the hosted lab, which reads
  `data/analysis.js`. Nothing was pushed.

## Blockers

None. Nothing failed three honest attempts.

## To merge

Not merged on purpose. When it is time: run `python -m pytest`, `ruff check courtroom tests scripts`, `node --check courtroom/viz/web/*.js`,
`node scripts/check_lab_math.cjs`, `python scripts/render_docs.py --check`, and `node scripts/collect_lines.cjs | diff - tests/golden/lines_baseline.json`.
