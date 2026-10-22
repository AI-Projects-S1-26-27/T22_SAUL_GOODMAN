"""Choose the language-model provider by configuration.

``COURTROOM_LLM_PROVIDER`` (``gemini`` by default, or ``ollama``) picks the provider for every code path
that builds a client without being told one. A command-line ``--provider`` wins over the environment.
"""

from __future__ import annotations

import os
from typing import Any

from courtroom.llm.client import LLMClient

PROVIDERS = ("gemini", "ollama")


def provider_name(explicit: str | None = None) -> str:
    name = (explicit or os.environ.get("COURTROOM_LLM_PROVIDER") or "gemini").strip().lower()
    if name not in PROVIDERS:
        raise ValueError(f"unknown LLM provider {name!r}; choose from {PROVIDERS}")
    return name


def make_client(provider: str | None = None, **kwargs: Any) -> LLMClient:
    """A client for ``provider``. ``model=None`` means that provider's own default."""
    if kwargs.get("model") is None:
        kwargs.pop("model", None)
    if provider_name(provider) == "ollama":
        from courtroom.llm.ollama import OllamaClient

        return OllamaClient(**kwargs)
    return LLMClient(**kwargs)
