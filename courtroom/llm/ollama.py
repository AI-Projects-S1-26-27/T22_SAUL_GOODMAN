"""Ollama as a second provider behind the same client interface.

Owner: Engineer 6 (beside ``client.py``; nothing in the deterministic core imports this).

``OllamaClient`` is an ``LLMClient`` whose transport is a local HTTP call to an Ollama server
(``POST /api/chat``). Everything else is inherited unchanged: the on-disk response cache keyed by
(system, prompt, model, temperature, max_tokens), the per-trial and per-run call caps, the usage
counters, and the rule that no failure ever raises at the caller. So a live run writes to the cache
and any later run, on any machine, can replay it with the network disabled.

What differs, stated plainly:

* **Cost is zero.** The model runs on the user's machine. ``Usage.free`` is set so the summary says so.
* **No key.** Availability means the server answers. It is probed once per client.
* **Separate cache file and key space.** Cache keys carry ``ollama/<model>``, and the default file is
  ``cache/responses.ollama.json``, so the committed Gemini cache is never touched.
* **Not reproducible across machines from a cold cache**, exactly like Gemini, so the same label
  applies: exhibition, not equilibrium analysis. Local inference is also not bit-stable across
  hardware or Ollama versions even with a fixed seed.

The wire format follows Ollama's documented ``/api/chat``: ``stream: false``, ``format`` set to a JSON
schema for structured output, ``options`` for temperature, seed, context and output length, and
``think: false`` to stop reasoning models spending the token budget on a hidden chain of thought.
It has been exercised against a stub only; see ``tests/test_ollama.py``.
"""

from __future__ import annotations

import contextlib
import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from courtroom.llm.client import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE, LLMClient, Usage

# Chosen for an 18 GB Apple-silicon laptop; see docs/OLLAMA.md for the reasoning.
DEFAULT_OLLAMA_MODEL = os.environ.get("COURTROOM_OLLAMA_MODEL", "qwen3:8b")
OLLAMA_CACHE_PATH = Path(__file__).resolve().parent / "cache" / "responses.ollama.json"
REQUEST_TIMEOUT = 180.0  # the first call loads the model into memory
PROBE_TIMEOUT = 2.0
NUM_CTX = 4096  # prompts are a few hundred tokens; a small window keeps memory use low

Transport = Callable[[str, dict[str, object] | None, float], dict[str, object]]


def default_host() -> str:
    raw = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434").strip()
    if not raw.startswith(("http://", "https://")):
        raw = f"http://{raw}"
    return raw.rstrip("/")


def _http(host: str) -> Transport:
    def call(path: str, payload: dict[str, object] | None, timeout: float) -> dict[str, object]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{host}{path}", data=data, headers={"Content-Type": "application/json"}, method="GET" if data is None else "POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return call


@dataclass
class OllamaClient(LLMClient):
    model: str = DEFAULT_OLLAMA_MODEL
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS
    cache_path: Path = OLLAMA_CACHE_PATH
    host: str = field(default_factory=default_host)
    seed: int = 0
    keep_alive: str = "30m"
    transport: Transport | None = None  # injected in tests; defaults to real HTTP
    last_error: str | None = field(default=None, init=False)
    _reachable: bool | None = field(default=None, init=False)
    _think_supported: bool = field(default=True, init=False)

    provider_tag = "ollama"

    def __post_init__(self) -> None:
        super().__post_init__()
        self.usage = Usage(provider="Ollama", free=True)

    # ------------------------------------------------------------------ identity

    @property
    def cache_model(self) -> str:
        return f"ollama/{self.model}"

    def _post(self, path: str, payload: dict[str, object] | None, timeout: float) -> dict[str, object]:
        return (self.transport or _http(self.host))(path, payload, timeout)

    # ------------------------------------------------------------------ availability

    @property
    def available(self) -> bool:
        """True when the server answers and the model is installed. Probed once, then remembered."""
        if self._reachable is None:
            try:
                tags = self._post("/api/tags", None, PROBE_TIMEOUT)
                names = {m.get("name") for m in tags.get("models", []) if isinstance(m, dict)}  # type: ignore[union-attr]
                installed = any(n == self.model or (isinstance(n, str) and n.split(":")[0] == self.model and ":" not in self.model) for n in names)
                if not installed:
                    self.last_error = f"model {self.model!r} is not installed: run `ollama pull {self.model}`"
                self._reachable = installed
            except Exception as exc:
                self.last_error = f"Ollama is not answering at {self.host} ({type(exc).__name__}): run `ollama serve`"
                self._reachable = False
        return bool(self._reachable)

    def installed_models(self) -> list[str]:
        tags = self._post("/api/tags", None, PROBE_TIMEOUT)
        return sorted(str(m["name"]) for m in tags.get("models", []) if isinstance(m, dict) and "name" in m)  # type: ignore[union-attr]

    # ------------------------------------------------------------------ transport

    def _payload(self, system: str, prompt: str, schema: type[BaseModel] | None) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": self.temperature,
                "seed": self.seed,
                "num_ctx": NUM_CTX,
                "num_predict": self.max_tokens,
            },
        }
        if self._think_supported:
            payload["think"] = False
        if schema is not None:
            payload["format"] = schema.model_json_schema()
        return payload

    def _request(self, system: str, prompt: str, schema: type[BaseModel] | None) -> str | None:
        """One logical request. Every failure mode is counted and becomes a fallback, never an exception."""
        for _ in range(2):  # a second pass only to drop ``think`` for a model that rejects it
            try:
                data = self._post("/api/chat", self._payload(system, prompt, schema), REQUEST_TIMEOUT)
            except urllib.error.HTTPError as exc:
                body = ""
                with contextlib.suppress(Exception):  # a body that cannot be read adds nothing
                    body = exc.read().decode("utf-8", "replace")
                if exc.code == 400 and "think" in body.lower() and self._think_supported:
                    self._think_supported = False
                    continue
                self.last_error = f"Ollama answered {exc.code}: {body[:200]}"
                self.usage.errors += 1
                return None
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                self.usage.errors += 1
                self._reachable = None  # look again next time, the server may have been restarted
                return None
            self.usage.input_tokens += int(data.get("prompt_eval_count") or 0)  # type: ignore[call-overload]
            self.usage.output_tokens += int(data.get("eval_count") or 0)  # type: ignore[call-overload]
            message = data.get("message")
            text = (message.get("content") if isinstance(message, dict) else "") or ""
            text = str(text).strip()
            if not text:
                self.usage.blocked += 1
                return None
            self.usage.calls += 1
            self._calls_this_trial += 1
            return text
        self.usage.errors += 1
        return None
