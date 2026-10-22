"""Render LLM_EXHIBITION.md from results/llm_exhibition.json.

Owner: Engineer 5.

Every number in the document is read from the results file. Nothing is typed in by hand, so
the write-up cannot drift from, or invent, what was actually measured.
"""

from __future__ import annotations

import json
from pathlib import Path

HEADER = """# LLM exhibition

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
"""


def render(results_path: Path, out_path: Path) -> str:
    data = json.loads(results_path.read_text(encoding="utf-8"))
    usage = data["usage"]
    cells = data["cells"]
    out = [HEADER]

    out.append("\n## Run\n")
    out.append("| Setting | Value |\n|---|---|")
    out.append(f"| Model | `{data['model']}` |")
    out.append(f"| Temperature | {data['temperature']} |")
    out.append(f"| Case | `{data['case_id']}` |")
    out.append(f"| Seeds per pairing | {len(data['seeds'])} ({', '.join(map(str, data['seeds']))}) |")
    out.append(f"| Opponents | {', '.join(f'`{o}`' for o in data['opponents'])} |")
    out.append(f"| Trials completed | {len(data['completed_trials'])} of {2 * len(data['opponents']) * len(data['seeds'])} |")
    if data.get("aborted"):
        out.append(f"| **Stopped early** | {data['aborted']} |")
        if data.get("resumable"):
            out.append(f"| Resumable | yes — {data['resume_hint']} |")

    out.append("\n## Cost and reliability\n")
    out.append("| Measure | Value |\n|---|---|")
    out.append(f"| Real API calls **in this run** | **{usage['calls']}** |")
    out.append(f"| Cache hits (no call made) | {usage['cache_hits']} |")
    total = data.get("cached_responses_total")
    if total is not None:
        out.append(f"| Distinct responses in the committed cache | {total} |")
    out.append(f"| Input tokens | {usage['input_tokens']:,} |")
    out.append(f"| Output tokens | {usage['output_tokens']:,} |")
    cost = usage["estimated_cost"]
    priced = f"${cost:.4f}" if cost else "not priced — the Gemini API exposes no pricing; set COURTROOM_LLM_RATES"
    out.append(f"| Estimated cost | {priced} |")
    out.append(f"| Overall fallback rate | **{data['overall_fallback_rate']:.1%}** |")
    out.append(f"| — rate-limited (per-minute 429) | {usage['rate_limited']} |")
    out.append(f"| — blocked (safety or empty) | {usage['blocked']} |")
    out.append(f"| — malformed or out-of-range index | {usage['malformed']} |")
    out.append(f"| — transport errors | {usage['errors']} |")
    out.append(f"| — unavailable (no key or call ceiling) | {usage['unavailable']} |")
    out.append(f"| Daily-quota stops | {usage.get('quota_stops', 0)} |")
    out.append(
        "\nA daily-quota stop is counted separately and is **not** a fallback: it is an outage of the "
        "free tier, not a failure of the model, and counting it as one would corrupt the statistic.\n"
    )
    if total is not None:
        out.append(
            f"\n**Read the call count carefully.** \"In this run\" means exactly that: a replay from the "
            f"committed cache reports **0** calls because it genuinely makes none. The cumulative cost of "
            f"producing these results is the **{total}** distinct responses in the cache, each of which "
            f"was paid for by one real API call at some point. A cold-cache reproduction would cost about "
            f"that many calls again.\n"
        )

    out.append("\n## Illegal actions\n")
    out.append(
        "**Structurally impossible, so the rate is 0 by construction rather than by luck.** The policy "
        "enumerates the legal moves itself and asks the model for an *index into that list*, constrained "
        "by a JSON schema, so an illegal move cannot be expressed. What can still go wrong is an "
        f"out-of-range or unparseable index: that happened **{usage['malformed']}** time(s), each "
        "re-prompted up to twice before falling back to Adaptive. "
        "`test_llm_policy_only_ever_offers_legal_actions` checks every enumerated action against the "
        "validator across whole trials.\n"
    )

    out.append("\n## Head to head\n")
    out.append("| LLM plays | Opponent | Trials | LLM win rate | Mean LLM payoff | Mean opponent payoff | Mean budget spent | Fallback rate |")
    out.append("|---|---|---|---|---|---|---|---|")
    for c in cells:
        out.append(
            f"| {c['llm_side']} | `{c['opponent']}` | {c['trials']} | {c['llm_win_rate']:.0%} | "
            f"{c['mean_llm_payoff']:+.2f} | {c['mean_opponent_payoff']:+.2f} | "
            f"{c['mean_llm_budget_spent']:.2f} | {c['fallback_rate']:.1%} |"
        )

    decided = data["llm_chosen"]
    out.append(
        f"\nAcross the run the model chose **{decided} of {data['decisions']}** decisions itself; the rest "
        "fell back to the Adaptive policy. A cell whose fallback rate is high is reporting Adaptive's play, "
        "not Gemini's, and should be read that way.\n"
    )

    baseline = data.get("deterministic_baseline") or []
    if baseline:
        out.append("\n## How its play differs from the four\n")
        out.append(
            "The same match-ups with a fixed strategy in the LLM's seat, simulated with no API calls. "
            "This turns \"it plays differently\" from an impression into a number.\n"
        )
        out.append("| Side | Who | Win rate | Budget spent | Exhibits offered | Admitted | Objections raised | Sustained |")
        out.append("|---|---|---|---|---|---|---|---|")
        for c in cells:
            out.append(
                f"| {c['llm_side']} | **LLM** vs `{c['opponent']}` | {c['llm_win_rate']:.0%} | "
                f"{c['mean_llm_budget_spent']:.2f} | {c.get('mean_exhibits_offered', 0):.1f} | "
                f"{c.get('mean_exhibits_admitted', 0):.1f} | {c.get('mean_objections_raised', 0):.1f} | "
                f"{c.get('mean_objections_sustained', 0):.1f} |"
            )
        for b in baseline:
            out.append(
                f"| {b['side']} | `{b['strategy']}` vs `{b['opponent']}` | {b['win_rate']:.0%} | "
                f"{b['mean_budget_spent']:.2f} | {b['mean_exhibits_offered']:.1f} | "
                f"{b['mean_exhibits_admitted']:.1f} | {b['mean_objections_raised']:.1f} | "
                f"{b['mean_objections_sustained']:.1f} |"
            )
        out.append(
            "\nRead the LLM rows against the fixed-strategy rows for the same side and opponent. "
            "Budget spent and objections raised are the two dimensions on which the deterministic "
            "profiles differ most sharply, so they are where a different policy shows up first.\n"
        )

    out.append("\n## Reproducing this\n")
    out.append("```bash\n# from the committed cache, no API key needed, no spend\npython -m courtroom llm-exhibition --seeds "
               f"{len(data['seeds'])} --case {data['case_id']}\n```\n")
    out.append(
        "With a cold cache and `GEMINI_API_KEY` set, the run calls Gemini again and the numbers may differ. "
        "That is the whole reason this is an exhibition.\n"
    )

    text = "\n".join(out)
    out_path.write_text(text, encoding="utf-8")
    return text
