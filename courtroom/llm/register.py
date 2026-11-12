"""Make the AI lawyer a named strategy (``llm``) without the core ever importing this package.

Importing this module is what registers it; the server and the command line do that once at start-up.
"""

from __future__ import annotations

import random

from courtroom.agents import register_strategy
from courtroom.llm.client import default_client
from courtroom.llm.policy import LLMAgent


def _make(rng: random.Random) -> LLMAgent:
    return LLMAgent(default_client(), rng)


register_strategy("llm", _make, "AI lawyer", "A language model picks each move from the legal ones, and says why. Exhibition only, never certified.")
