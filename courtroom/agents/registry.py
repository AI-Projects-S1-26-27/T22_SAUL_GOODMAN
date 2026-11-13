"""Strategy-name to agent factory. Names are part of the public API (CLI, HTTP, web UI)."""

from __future__ import annotations

import random
from collections.abc import Callable

from courtroom.agents.adversarial import ChaosAgent, RecklessAgent
from courtroom.agents.base import Agent
from courtroom.agents.lookahead import LookaheadAgent
from courtroom.agents.policies import PROFILES, CounselAgent, MixedAgent

STRATEGY_NAMES: tuple[str, ...] = ("aggressive", "conservative", "adaptive", "reckless", "chaos")

# Extra strategies that live outside the certified core (the AI lawyer). The package that provides one registers it here
# when it is loaded, so the core never has to import it.
_EXTRA: dict[str, tuple[Callable[[random.Random], Agent], str, str]] = {}


def register_strategy(name: str, factory: Callable[[random.Random], Agent], label: str, description: str) -> None:
    _EXTRA[name] = (factory, label, description)


def describe_strategies() -> list[dict[str, str]]:
    out = [{"name": p.name, "label": p.label, "description": p.description} for p in PROFILES.values()]
    out.append({"name": "reckless", "label": "Reckless", "description": "Random legal moves and the occasional rule break."})
    out.append({"name": "chaos", "label": "Chaos", "description": "Random, often illegal actions (robustness fuzzing)."})
    out.append({"name": "lookahead", "label": "Lookahead (exhibition)", "description": "Thinks a few moves ahead with alpha-beta. Not one of the four certified styles; compared with them in a labelled extra."})
    out.extend({"name": n, "label": label, "description": desc} for n, (_, label, desc) in _EXTRA.items())
    out.append({"name": "mixed:<p>", "label": "Mixed", "description": "Aggressive with probability p, else Conservative."})
    return out


def make_agent(strategy: str, rng: random.Random) -> Agent:
    """Build an agent. ``rng`` must be the side-specific trial RNG so results are reproducible."""
    if strategy in PROFILES:
        return CounselAgent(PROFILES[strategy])
    if strategy == "chaos":
        return ChaosAgent(rng)
    if strategy == "reckless":
        return RecklessAgent(rng)
    if strategy == "lookahead":  # an exhibition style: selectable, never part of the certified analysis or the recorded bundle
        return LookaheadAgent()
    if strategy in _EXTRA:
        return _EXTRA[strategy][0](rng)
    if strategy.startswith("mixed:"):
        p = float(strategy.split(":", 1)[1])
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"mixed probability must be in [0, 1], got {p}")
        return MixedAgent(p, rng)
    raise ValueError(f"unknown strategy {strategy!r}; choose from {STRATEGY_NAMES} or mixed:<p>")
