"""The optional language-model layer.

Nothing in the deterministic core (engine, judge, procedure, agents, gametheory, cases, contracts) imports this package. The
model may play a lawyer, draft a case for a person to check, and word lines for a case with no script. It never decides a verdict
and never enters a certified payoff table; see docs/LLM_ROLE.md.
"""

from courtroom.llm.backends import BackendError, GeminiBackend, OllamaBackend, configured_backends
from courtroom.llm.client import ActionChoice, LLMClient, Usage, cache_key, default_client, make_client

__all__ = [
    "ActionChoice",
    "BackendError",
    "GeminiBackend",
    "LLMClient",
    "OllamaBackend",
    "Usage",
    "cache_key",
    "configured_backends",
    "default_client",
    "make_client",
]
