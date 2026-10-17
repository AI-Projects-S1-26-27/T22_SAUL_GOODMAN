# LLM exhibition

**These are exhibition results, not equilibrium analysis.**

The four deterministic strategies (Aggressive, Conservative, Adaptive, Mixed) form a closed,
reproducible strategy set. Their payoff matrix is solved in exact rationals, every equilibrium is
checked by an independent best-response verifier, and the whole thing reproduces bit-for-bit from
a seed. See [`RESULTS.md`](RESULTS.md) for that work.

An LLM row cannot join them, for one concrete reason: **a cache miss on another machine calls
Gemini again, and providers do not guarantee identical output across time or model revisions even
at temperature 0.** A payoff that cannot be reproduced cannot be certified, and an equilibrium
computed over uncertifiable payoffs would be a number with nothing behind it. So this policy is
played head-to-head and reported on its own, and `results/payoffs.json`, `bootstrap.json` and
`sensitivity.json` were not regenerated, extended or touched.

What *is* reproducible here: every response is cached on disk under a hash of
(system, prompt, model, temperature, max_tokens), and the cache is committed. Replaying this
exhibition from the committed cache needs no API key and spends nothing.


## Run

| Setting | Value |
|---|---|
| Model | `gemini-3.1-flash-lite` |
| Temperature | 0.0 |
| Case | `helix-espionage` |
| Seeds per pairing | 5 (0, 1, 2, 3, 4) |
| Opponents | `aggressive`, `conservative`, `adaptive`, `mixed:0.5` |
| Trials completed | 40 of 40 |

## Cost and reliability

| Measure | Value |
|---|---|
| Real API calls **in this run** | **191** |
| Cache hits (no call made) | 464 |
| Distinct responses in the committed cache | 363 |
| Input tokens | 97,434 |
| Output tokens | 1,151 |
| Estimated cost | $0.2041 |
| Overall fallback rate | **0.0%** |
| — rate-limited (per-minute 429) | 6 |
| — blocked (safety or empty) | 0 |
| — malformed or out-of-range index | 0 |
| — transport errors | 0 |
| — unavailable (no key or call ceiling) | 0 |
| Daily-quota stops | 0 |

A daily-quota stop is counted separately and is **not** a fallback: it is an outage of the free tier, not a failure of the model, and counting it as one would corrupt the statistic.


**Read the call count carefully.** "In this run" means exactly that: a replay from the committed cache reports **0** calls because it genuinely makes none. The cumulative cost of producing these results is the **363** distinct responses in the cache, each of which was paid for by one real API call at some point. A cold-cache reproduction would cost about that many calls again.


## Illegal actions

**Structurally impossible, so the rate is 0 by construction rather than by luck.** The policy enumerates the legal moves itself and asks the model for an *index into that list*, constrained by a JSON schema, so an illegal move cannot be expressed. What can still go wrong is an out-of-range or unparseable index: that happened **0** time(s), each re-prompted up to twice before falling back to Adaptive. `test_llm_policy_only_ever_offers_legal_actions` checks every enumerated action against the validator across whole trials.


## Head to head

| LLM plays | Opponent | Trials | LLM win rate | Mean LLM payoff | Mean opponent payoff | Mean budget spent | Fallback rate |
|---|---|---|---|---|---|---|---|
| prosecution | `aggressive` | 5 | 40% | -2.37 | +0.85 | 11.40 | 0.0% |
| prosecution | `conservative` | 5 | 100% | +4.05 | -2.34 | 11.50 | 0.0% |
| prosecution | `adaptive` | 5 | 60% | -0.39 | +0.16 | 11.30 | 0.0% |
| prosecution | `mixed:0.5` | 5 | 80% | +2.03 | -0.88 | 11.40 | 0.0% |
| defense | `aggressive` | 5 | 80% | +3.79 | -5.10 | 11.20 | 0.0% |
| defense | `conservative` | 5 | 100% | +5.09 | -2.25 | 11.70 | 0.0% |
| defense | `adaptive` | 5 | 60% | +1.65 | -0.81 | 11.00 | 0.0% |
| defense | `mixed:0.5` | 5 | 100% | +5.14 | -3.17 | 11.70 | 0.0% |

Across the run the model chose **655 of 655** decisions itself; the rest fell back to the Adaptive policy. A cell whose fallback rate is high is reporting Adaptive's play, not Gemini's, and should be read that way.


## How its play differs from the four

The same match-ups with a fixed strategy in the LLM's seat, simulated with no API calls. This turns "it plays differently" from an impression into a number.

| Side | Who | Win rate | Budget spent | Exhibits offered | Admitted | Objections raised | Sustained |
|---|---|---|---|---|---|---|---|
| prosecution | **LLM** vs `aggressive` | 40% | 11.40 | 8.2 | 6.4 | 2.8 | 0.6 |
| prosecution | **LLM** vs `conservative` | 100% | 11.50 | 8.6 | 7.6 | 2.0 | 0.0 |
| prosecution | **LLM** vs `adaptive` | 60% | 11.30 | 8.2 | 6.6 | 2.8 | 0.4 |
| prosecution | **LLM** vs `mixed:0.5` | 80% | 11.40 | 8.4 | 7.2 | 2.2 | 0.0 |
| defense | **LLM** vs `aggressive` | 80% | 11.20 | 6.0 | 5.6 | 3.8 | 1.6 |
| defense | **LLM** vs `conservative` | 100% | 11.70 | 5.0 | 5.0 | 1.8 | 0.0 |
| defense | **LLM** vs `adaptive` | 60% | 11.00 | 5.4 | 5.0 | 2.8 | 0.6 |
| defense | **LLM** vs `mixed:0.5` | 100% | 11.70 | 5.2 | 5.2 | 2.2 | 0.2 |
| prosecution | `aggressive` vs `aggressive` | 20% | 12.00 | 8.0 | 6.2 | 4.8 | 0.4 |
| prosecution | `aggressive` vs `conservative` | 100% | 11.90 | 8.0 | 7.0 | 4.0 | 0.0 |
| prosecution | `aggressive` vs `adaptive` | 0% | 12.00 | 8.0 | 6.0 | 4.6 | 0.2 |
| prosecution | `aggressive` vs `mixed:0.5` | 60% | 12.00 | 8.0 | 6.4 | 4.6 | 0.4 |
| prosecution | `conservative` vs `aggressive` | 0% | 7.50 | 6.0 | 6.0 | 0.0 | 0.0 |
| prosecution | `conservative` vs `conservative` | 0% | 7.50 | 6.0 | 6.0 | 0.0 | 0.0 |
| prosecution | `conservative` vs `adaptive` | 0% | 7.50 | 6.0 | 6.0 | 0.0 | 0.0 |
| prosecution | `conservative` vs `mixed:0.5` | 0% | 7.50 | 6.0 | 6.0 | 0.0 | 0.0 |
| prosecution | `adaptive` vs `aggressive` | 0% | 9.70 | 7.0 | 6.8 | 2.4 | 0.4 |
| prosecution | `adaptive` vs `conservative` | 100% | 10.20 | 8.0 | 7.0 | 1.4 | 0.0 |
| prosecution | `adaptive` vs `adaptive` | 40% | 10.20 | 7.4 | 6.8 | 2.6 | 0.4 |
| prosecution | `adaptive` vs `mixed:0.5` | 40% | 9.90 | 7.4 | 6.8 | 2.0 | 0.4 |
| prosecution | `mixed:0.5` vs `aggressive` | 20% | 11.10 | 7.6 | 6.4 | 3.6 | 0.4 |
| prosecution | `mixed:0.5` vs `conservative` | 80% | 11.00 | 7.6 | 6.8 | 3.0 | 0.0 |
| prosecution | `mixed:0.5` vs `adaptive` | 0% | 11.10 | 7.6 | 6.2 | 3.6 | 0.2 |
| prosecution | `mixed:0.5` vs `mixed:0.5` | 60% | 11.10 | 7.6 | 6.6 | 3.4 | 0.4 |
| defense | `aggressive` vs `aggressive` | 80% | 12.00 | 6.0 | 5.6 | 8.0 | 1.8 |
| defense | `aggressive` vs `conservative` | 100% | 11.50 | 5.0 | 5.0 | 6.0 | 0.0 |
| defense | `aggressive` vs `adaptive` | 100% | 12.00 | 5.0 | 4.6 | 7.0 | 0.2 |
| defense | `aggressive` vs `mixed:0.5` | 80% | 11.90 | 5.8 | 5.4 | 7.6 | 1.2 |
| defense | `conservative` vs `aggressive` | 0% | 7.00 | 5.0 | 5.0 | 1.0 | 1.0 |
| defense | `conservative` vs `conservative` | 100% | 8.00 | 5.0 | 5.0 | 0.0 | 0.0 |
| defense | `conservative` vs `adaptive` | 0% | 7.00 | 5.0 | 5.0 | 1.0 | 1.0 |
| defense | `conservative` vs `mixed:0.5` | 20% | 7.20 | 5.0 | 5.0 | 0.8 | 0.8 |
| defense | `adaptive` vs `aggressive` | 100% | 10.70 | 5.8 | 5.6 | 4.2 | 2.0 |
| defense | `adaptive` vs `conservative` | 100% | 9.40 | 5.0 | 5.0 | 1.8 | 0.0 |
| defense | `adaptive` vs `adaptive` | 60% | 10.10 | 5.6 | 5.2 | 2.8 | 0.6 |
| defense | `adaptive` vs `mixed:0.5` | 100% | 10.60 | 5.8 | 5.6 | 3.4 | 1.4 |
| defense | `mixed:0.5` vs `aggressive` | 40% | 10.00 | 5.6 | 5.2 | 5.2 | 1.6 |
| defense | `mixed:0.5` vs `conservative` | 100% | 10.10 | 5.0 | 5.0 | 3.6 | 0.0 |
| defense | `mixed:0.5` vs `adaptive` | 60% | 10.00 | 5.0 | 4.6 | 4.6 | 0.6 |
| defense | `mixed:0.5` vs `mixed:0.5` | 40% | 9.90 | 5.4 | 5.0 | 4.8 | 1.0 |

Read the LLM rows against the fixed-strategy rows for the same side and opponent. Budget spent and objections raised are the two dimensions on which the deterministic profiles differ most sharply, so they are where a different policy shows up first.


## Reproducing this

```bash
# from the committed cache, no API key needed, no spend
python -m courtroom llm-exhibition --seeds 5 --case helix-espionage
```

With a cold cache and `GEMINI_API_KEY` set, the run calls Gemini again and the numbers may differ. That is the whole reason this is an exhibition.
