"""Optional Gemini layer: argument text and an exhibition policy.

Nothing in ``courtroom.engine``, ``courtroom.judge``, ``courtroom.procedure``,
``courtroom.gametheory``, ``courtroom.agents``, ``courtroom.cases`` or ``courtroom.contracts``
imports this package. It sits beside the deterministic core and can be deleted without
affecting a single certified result.
"""

from courtroom.llm.client import ActionChoice, LLMClient, SpendCeilingReached, Usage, cache_key
from courtroom.llm.factory import PROVIDERS, make_client, provider_name
from courtroom.llm.narrator import narrate
from courtroom.llm.ollama import OllamaClient
from courtroom.llm.policy import LLMAgent, legal_actions

__all__ = [
    "PROVIDERS",
    "ActionChoice",
    "LLMAgent",
    "LLMClient",
    "OllamaClient",
    "SpendCeilingReached",
    "Usage",
    "cache_key",
    "legal_actions",
    "make_client",
    "narrate",
    "provider_name",
]
