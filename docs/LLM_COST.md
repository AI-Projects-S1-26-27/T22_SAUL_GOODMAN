# What the LLM exhibition cost

The Gemini API reports token counts but no prices, so for a long time the only cost in this
repository was "not priced". This page prices it from Google's published rates and shows the
arithmetic, so it can be checked.

## The rate

From Google's [pricing page](https://ai.google.dev/gemini-api/docs/pricing), row `gemini-3.1-flash-lite`
(the model used), standard tier, text input:

| | Paid tier | Free tier |
|---|---|---|
| Input | $0.25 per 1M tokens | free of charge |
| Output (including thinking) | $1.50 per 1M tokens | free of charge |

Read on 18 Oct 2026. Prices change, so treat this as a snapshot. Several third-party aggregators agree
on $0.25 and $1.50; one lists half of that, which does not match Google's page and is ignored.

The key used for this work was on the **free tier** (it hit a daily request cap), so the amount
actually charged is expected to be **zero**. The figures below are what the same tokens would cost on
the paid tier, which is the honest upper bound and the one the Rs 150 ceiling was meant to bound.

## The tokens that were recorded

Every real call was counted by `LLMClient.usage`. The cache holds exactly one entry per real call, so
the four counted runs account for all 363 entries:

| Run | Real calls | Input tokens | Output tokens |
|---|---|---|---|
| Smoke test, one trial | 15 | 9,444 | 92 |
| First exhibition run, 2 seeds | 84 | 48,140 | 508 |
| Resumed after the daily cap | 73 | 30,881 | 438 |
| Five-seed run | 191 | 97,434 | 1,151 |
| **Total recorded** | **363** | **185,899** | **2,189** |

At the paid rate: 185,899 x $0.25/1M + 2,189 x $1.50/1M = $0.0465 + $0.0033 = **about $0.050**, which
is roughly **Rs 4** at Rs 88 per USD (an exchange rate I assumed, not looked up).

## What this does not include

One early run was stuck on provider latency, held its counters in memory, and was killed before it saved
anything, so its calls are in no counter and no cache. The daily cap being hit shortly afterwards
suggests it made a few hundred requests, but that is an inference from the cap, not a measurement. Even
if that run used 400 calls at the average size of the recorded ones (about 630 input tokens each), it
would add roughly $0.06, giving a paid-tier total near $0.11, or about Rs 10. That is an estimate and
is labelled as one.

For comparison, the ceiling used during the run priced tokens at an assumed $2.00 and $8.00 per million,
about eight times Google's actual rate. Against that deliberately pessimistic rate the recorded tokens
come to about $0.39 (Rs 34).

## Why the printed estimate still says "not priced"

`COURTROOM_LLM_RATES` defaults to no rate on purpose: a price baked into code goes stale silently. To
get a figure from the command line, set it from the table above:

```bash
COURTROOM_LLM_RATES="0.25,1.50" python -m courtroom llm-exhibition
```
