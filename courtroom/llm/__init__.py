"""Optional Gemini layer: argument text and an exhibition policy.

Nothing in ``courtroom.engine``, ``courtroom.judge``, ``courtroom.procedure``,
``courtroom.gametheory``, ``courtroom.agents``, ``courtroom.cases`` or ``courtroom.contracts``
imports this package. It sits beside the deterministic core and can be deleted without
affecting a single certified result.
"""

from courtroom.llm.client import ActionChoice, LLMClient, SpendCeilingReached, Usage, cache_key
from courtroom.llm.narrator import narrate
from courtroom.llm.policy import LLMAgent, legal_actions

__all__ = [
    "ActionChoice",
    "LLMAgent",
    "LLMClient",
    "SpendCeilingReached",
    "Usage",
    "cache_key",
    "legal_actions",
    "narrate",
]
