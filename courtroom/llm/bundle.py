"""Offline exhibition bundle: the committed cache, replayed into static JSON.

Owner: Engineer 7 (presentation only).

The web demo is hosted as static files, so the LLM exhibition has to ship as data. This replays
every exhibition trial from the committed response cache with the network switched **off**
(``allow_network=False``), so building it needs no key and spends nothing, and the client
cannot reach the provider even if a key happens to be set in the environment.

The output is a *separate* file from the certified bundle. ``bundle.js`` stays free of any
language-model output so it can be audited as such; this file carries its own label.

Two checks make the replay trustworthy rather than merely plausible:

* every cell's win rate, mean payoff and budget are recomputed from the replayed trials and
  compared with ``results/llm_exhibition.json``, which came from the live run;
* misses are counted, not hidden. A decision the cache cannot answer falls back to Adaptive
  exactly as it did in the live run, and is reported.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from courtroom.cases import get_case
from courtroom.contracts import Side
from courtroom.llm.client import CACHE_PATH, LLMClient
from courtroom.llm.exhibition import build_court

LABEL = "Exhibition — not equilibrium analysis"
NOT_EQUILIBRIUM = (
    "A language-model policy is not reproducible from a cold cache on another machine, so its "
    "payoffs cannot be certified by the best-response verifier. These trials are replayed from a "
    "committed cache for demonstration and are excluded from the payoff matrices, the bootstrap "
    "and the sensitivity sweep."
)


def replay_exhibition(results_path: Path, cache_path: Path = CACHE_PATH) -> dict[str, object]:
    results = json.loads(results_path.read_text(encoding="utf-8"))
    case_id = results["case_id"]
    case = get_case(case_id)
    client = LLMClient(cache_path=cache_path, allow_network=False)

    trials: dict[str, object] = {}
    stats: dict[str, object] = {}
    cells: dict[tuple[str, str], dict[str, list[float]]] = {}

    for llm_side in (Side.PROSECUTION, Side.DEFENSE):
        for opponent in results["opponents"]:
            for seed in results["seeds"]:
                before_hits, before_miss = client.usage.cache_hits, client.usage.refusals
                client.start_trial()
                court, agent = build_court(case, llm_side, opponent, seed, client)
                result = court.run()
                key = f"{case_id}|{result.prosecution_strategy}|{result.defense_strategy}|{seed}"
                trials[key] = json.loads(result.model_dump_json())
                stats[key] = {
                    "llm_side": llm_side.value,
                    "opponent": opponent,
                    "decisions": agent.decisions,
                    "llm_chosen": agent.llm_decisions,
                    "trivial": agent.trivial_decisions,
                    "fallbacks": sum(agent.fallback_reasons.values()),
                    "cache_hits": client.usage.cache_hits - before_hits,
                    "cache_misses": client.usage.refusals - before_miss,
                }
                cell = cells.setdefault((llm_side.value, opponent), {"win": [], "payoff": [], "spent": []})
                cell["win"].append(float(result.verdict.outcome.favours is llm_side))
                cell["payoff"].append(result.utilities[llm_side])
                cell["spent"].append(result.ledgers[llm_side].spent)

    mismatches = _compare(results["cells"], cells)
    summary = {k: v for k, v in results.items() if k not in {"completed_trials", "resume_hint"}}
    return {
        "meta": {
            "label": LABEL,
            "not_equilibrium": NOT_EQUILIBRIUM,
            "kind": "exhibition",
            "model": results["model"],
            "temperature": results["temperature"],
            "case_id": case_id,
            "seeds": results["seeds"],
            "opponents": results["opponents"],
            "source": "replayed from the committed response cache with the network disabled",
            "cache_misses": sum(s["cache_misses"] for s in stats.values()),  # type: ignore[index]
            "mismatches_vs_live_run": mismatches,
        },
        "summary": summary,
        "trials": trials,
        "stats": stats,
    }


def _compare(stored: list[dict[str, object]], replayed: dict[tuple[str, str], dict[str, list[float]]]) -> list[str]:
    """Differences between the live run's aggregates and the replay's. Empty means identical."""
    problems: list[str] = []
    for cell in stored:
        got = replayed.get((str(cell["llm_side"]), str(cell["opponent"])))
        if got is None:
            problems.append(f"{cell['llm_side']} vs {cell['opponent']}: not replayed")
            continue
        checks = (
            ("trials", cell["trials"], len(got["win"])),
            ("win rate", cell["llm_win_rate"], round(statistics.fmean(got["win"]), 4)),
            ("mean payoff", cell["mean_llm_payoff"], round(statistics.fmean(got["payoff"]), 4)),
            ("mean budget spent", cell["mean_llm_budget_spent"], round(statistics.fmean(got["spent"]), 4)),
        )
        for name, want, have in checks:
            if abs(float(want) - float(have)) > 1e-9:
                problems.append(f"{cell['llm_side']} vs {cell['opponent']}: {name} stored {want}, replayed {have}")
    return problems
