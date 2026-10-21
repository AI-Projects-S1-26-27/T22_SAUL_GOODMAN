# Demo walkthrough (branch `witness-moves`)

Run locally for the full app: `python -m courtroom serve --port 8000`, then open <http://127.0.0.1:8000>.
The static Vercel build shows the bundled data only; the case editor, injection and "recompute" buttons need the local server.
Pick **helix-espionage** unless a step says otherwise. Aurora and kestrel are now contested too (D14). Tab names: Overview, Courtroom, Case file, Verdict, Strategy, The judge.

| # | Show | Do this | Point at |
|---|---|---|---|
| 1 | Verification | Terminal: `python -m pytest -q` then `python -m courtroom verify` | **827 passed**. Verify prints two identical digests, "bit-identical: YES, hash chain valid: YES" |
| 2 | Strategy tab | Open **Strategy** | Payoff matrix and exact fractions. helix has **no dominant strategy**; prosecution plays Conservative 711/821, defense Adaptive 7870/8447. Bootstrap stability 100% |
| 3 | The judge + slider | Open **The judge**, drag the bar slider (`thr-slider`) from 90% to 95%, press **Replay the trial at this bar** | The verdict flips; at 95% the prosecution cannot win. 80 to 90% is the stable mixed band. Press **Recompute the equilibrium** to show the label change |
| 4 | Case editor | In the **Case file** area find "Write your own case"; add a short case and run it | Judge's per-point breakdown; "not counted" rows now explain the top-4 cap |
| 5 | Evidence injection | Find the injection panel ("Add it and replay from here"); add a defense exhibit mid-trial | Timeline gets an injection event; the hash chain commits to the exhibit; a defense exhibit that helps the prosecution is refused |
| 6 | Witness / cross-exam | **Terminal only** (variants are not in the web case list): `python -m courtroom run --case kestrel-av-witnesses -p aggressive -d aggressive --seed 0` | Events 17, 27, 28: "cross-examines W-ENG on qualifications: a real flaw", then "cross-examines W-EYE2 ... a real flaw" and "rehabilitated". Add `--narrate` for the Q and A lines. Try `helix-espionage-witnesses`: Conservative never cross-examines |
| 7 | Gemini exhibition | Click **LLM exhibition** in the mode bar | Banner says "not certified / not equilibrium"; 40 replayed trials, no key and no network used; the matrix is replaced by the model's own results |
| 8 | Close | Switch back to **Deterministic** | The page always opens certified; nothing above changed the certified results; the only certified change on this branch is the D14 rebalancing of aurora and kestrel |

## Key numbers

**Top-4 fact cap (D12).** Library: 875 trials, **0** digest changes, **0** verdict changes. Generated: 1,500 trials, **16** digest changes, **0** verdict changes.
Tail (log-odds, one side's good exhibits): 4 exhibits 10.04 both; 6 exhibits 16.10 to 10.40; 8 exhibits 21.98 to 10.49.

**Regeneration time** (`analysis --workers 4`).

| Space | Scope | Wall clock | Source |
|---|---|---|---|
| 4x4 | all 7 cases | 13 min 56 s | measured |
| 4x4 / 5x5 / 6x6 | helix only | 6.5 / 9.7 / 14.7 min | measured |
| 5x5 / 6x6 | all 7 cases | about 21 / 31 min | scaled from the above |

Stages at 4x4: matrices about 45 s, bootstrap about 55 s, sensitivity sweep about 12 min (single process).

**Exhibition (helix-espionage, gemini-3.1-flash-lite, 5 seeds x 4 opponents).** 40 of 40 trials completed. **191 real API calls in that run**, 464 cache hits, **363 distinct cached responses** (the true cumulative number of paid calls). Fallback rate **0.0%** (6 per-minute rate limits, re-asked, none fell back). Illegal actions 0 by construction. Stated cost $0.2041 is for the 191-call run only; a cold reproduction would need about 363 calls.

**Witness variants (270 trials each).** helix 0 verdict flips, aurora 0, kestrel 11 (3.9%). No equilibrium has been solved with these rules on.
