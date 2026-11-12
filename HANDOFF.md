# Handoff

State of the `final-integration` branch (nothing pushed, nothing merged).

## What was not done, and why

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
