"""One cached language-model client over Ollama Cloud, local Ollama and Gemini.

What the rest of the layer relies on:

* **Optional.** No key, no Ollama and no network and every call returns ``None``; the caller falls back to something that needs
  no model. Nothing in the deterministic engine imports this package.
* **Cached.** Every answer is stored on disk under ``sha256(system, prompt, model, temperature, max_tokens, schema)``. A cache
  hit never calls out, so any recorded run replays offline and exactly. Entries are looked up under every model the client
  could use *and* every model the cache has seen, so a recording made on one machine replays on another with no key at all.
* **Temperature 0.** The cache is what makes a run reproducible. A cache *miss* on another machine calls the provider, and
  providers do not promise identical text over time, which is why nothing produced here ever reaches a verdict or a payoff.
* **Capped and never fatal.** Calls per trial and per run are bounded. A backend that fails is skipped for the next one in
  order (cloud, local, Gemini); if all fail the answer is ``None``. Every outcome is counted in ``usage``.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from courtroom.llm.backends import BackendError, GeminiBackend, OllamaBackend, Transport, configured_backends
from courtroom.llm.env import load_env

DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS = 220
CACHE_PATH = Path(os.environ.get("COURTROOM_LLM_CACHE") or Path(__file__).resolve().parent / "cache" / "responses.json")
MAX_CALLS_PER_TRIAL = 60
MAX_CALLS_PER_RUN = 600
PROBE_TTL = 30.0

Backend = OllamaBackend | GeminiBackend


def cache_key(system: str, prompt: str, model: str, temperature: float, max_tokens: int, schema: str = "") -> str:
    blob = json.dumps([system, prompt, model, temperature, max_tokens, schema], separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class ActionChoice(BaseModel):
    """Structured answer for the lawyer: an index into the legal-action list, and one sentence of why."""

    choice: int
    reason: str = ""


@dataclass
class Usage:
    calls: int = 0
    cache_hits: int = 0
    refusals: int = 0  # nothing could be asked: no backend answers, or a cap was reached
    blocked: int = 0
    malformed: int = 0  # an answer that would not parse, or an index out of range
    errors: int = 0  # every backend failed

    @property
    def fallbacks(self) -> int:
        return self.refusals + self.blocked + self.malformed + self.errors

    @property
    def attempts(self) -> int:
        return self.calls + self.cache_hits + self.fallbacks

    def fallback_rate(self) -> float:
        return round(self.fallbacks / self.attempts, 4) if self.attempts else 0.0

    def as_dict(self) -> dict[str, object]:
        return {
            "calls": self.calls,
            "cache_hits": self.cache_hits,
            "fallbacks": self.fallbacks,
            "unavailable": self.refusals,
            "blocked": self.blocked,
            "malformed": self.malformed,
            "errors": self.errors,
            "fallback_rate": self.fallback_rate(),
        }


@dataclass
class LLMClient:
    backends: list[Backend] = field(default_factory=list)
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS
    cache_path: Path = CACHE_PATH
    allow_network: bool = True
    max_calls_per_run: int = MAX_CALLS_PER_RUN
    usage: Usage = field(default_factory=Usage)
    last_error: str | None = field(default=None, init=False)
    last_source: str | None = field(default=None, init=False)  # "cache" | "cloud" | "local" | "gemini" for the latest answer
    last_model: str | None = field(default=None, init=False)
    _entries: dict[str, dict[str, str]] = field(default_factory=dict, init=False)
    _models_seen: list[str] = field(default_factory=list, init=False)
    _dirty: bool = field(default=False, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _calls_this_trial: int = field(default=0, init=False)
    _probe: tuple[float, bool] | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        raw: dict[str, Any] = {}
        with contextlib.suppress(OSError, ValueError):
            raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
        self._entries = dict(raw.get("entries", {}))
        self._models_seen = list(raw.get("_models", []))

    # ------------------------------------------------------------------ cache

    def save(self) -> None:
        """Write the cache to disk. Safe to call from several requests at once; a write that fails never breaks a caller."""
        with self._lock:
            if not self._dirty:
                return
            payload = json.dumps({"_models": sorted(set(self._models_seen)), "entries": self._entries}, indent=1, sort_keys=True)
            tmp = self.cache_path.with_name(f"{self.cache_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
            try:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_text(payload, encoding="utf-8")
                tmp.replace(self.cache_path)
                self._dirty = False
            except OSError as exc:
                self.last_error = f"could not save the cache: {exc}"
                with contextlib.suppress(OSError):
                    tmp.unlink()

    def _candidate_models(self) -> list[str]:
        names = [b.model for b in self.backends if b.model]
        return list(dict.fromkeys([*names, *self._models_seen]))

    def _lookup(self, system: str, prompt: str, schema: str) -> dict[str, str] | None:
        for model in self._candidate_models():
            hit = self._entries.get(cache_key(system, prompt, model, self.temperature, self.max_tokens, schema))
            if hit is not None:
                return hit
        return None

    # ------------------------------------------------------------------ availability

    def available(self, refresh: bool = False) -> bool:
        """Does any backend answer right now? Probed, then remembered for a short while."""
        if not self.allow_network:
            return False
        now = time.monotonic()
        if refresh or self._probe is None or now - self._probe[0] > PROBE_TTL:
            for b in self.backends:
                b.reset()
            self._probe = (now, any(b.probe() for b in self.backends))
        return self._probe[1]

    def status(self) -> dict[str, object]:
        """For the UI: whether an AI backend answers, and which one would be asked first."""
        ok = self.available()
        live = [b for b in self.backends if b.probe()] if ok else []
        first = live[0] if live else None
        return {
            "available": ok,
            "backend": first.name if first else None,
            "model": first.model if first else None,
            "backends": [{"name": b.name, "model": b.model} for b in self.backends],
        }

    def start_trial(self) -> None:
        self._calls_this_trial = 0

    # ------------------------------------------------------------------ the one entry point

    def complete(self, system: str, prompt: str, schema: type[BaseModel] | None = None) -> str | None:
        """Cached completion, or ``None`` when the caller must use its fallback."""
        sname = schema.__name__ if schema else ""
        with self._lock:
            hit = self._lookup(system, prompt, sname)
        if hit is not None:
            self.usage.cache_hits += 1
            self.last_source, self.last_model = "cache", hit.get("model")
            return hit["text"]
        if not self.allow_network or not self.backends:
            self.usage.refusals += 1
            return None
        if self._calls_this_trial >= MAX_CALLS_PER_TRIAL or self.usage.calls >= self.max_calls_per_run:
            self.usage.refusals += 1
            return None
        if not self.available():
            self.usage.refusals += 1
            self.last_error = "no model backend answers (set OLLAMA_API_KEY or GEMINI_API_KEY in .env, or start `ollama serve`)"
            return None
        reasons: list[str] = []
        for b in self.backends:
            if not b.probe():
                continue
            try:
                text = b.chat(system, prompt, temperature=self.temperature, max_tokens=self.max_tokens, schema=schema)
            except BackendError as exc:
                reasons.append(f"{b.name}: {exc}")
                continue
            model = b.model or b.name
            with self._lock:
                self._entries[cache_key(system, prompt, model, self.temperature, self.max_tokens, sname)] = {"model": model, "provider": b.name, "text": text}
                self._models_seen.append(model)
                self._dirty = True
            self.usage.calls += 1
            self._calls_this_trial += 1
            self.last_source, self.last_model = b.name, model
            return text
        self.usage.errors += 1
        self.last_error = "; ".join(reasons) or "no backend answered"
        return None

    def choose(self, system: str, prompt: str, n_options: int) -> tuple[int, str] | None:
        """Ask for an index into a legal-action list, and a one-sentence reason. ``None`` means fall back."""
        if n_options <= 0:
            return None
        raw = self.complete(system, prompt, schema=ActionChoice)
        if raw is None:
            return None
        try:
            parsed = ActionChoice.model_validate_json(raw)
            index, reason = int(parsed.choice), parsed.reason
        except (ValueError, TypeError):
            try:
                data = json.loads(raw)
                index, reason = int(data["choice"]), str(data.get("reason", ""))
            except Exception:
                self.usage.malformed += 1
                return None
        if not 0 <= index < n_options:
            self.usage.malformed += 1
            return None
        return index, " ".join(reason.split())[:240]


_default: LLMClient | None = None


def default_client(refresh: bool = False) -> LLMClient:
    """The shared client, built from ``.env`` and the environment. Tests build their own with a stub transport."""
    global _default
    if _default is None or refresh:
        load_env()
        _default = LLMClient(backends=configured_backends())
    return _default


def make_client(transport: Transport | None = None, **kwargs: Any) -> LLMClient:
    load_env()
    return LLMClient(backends=configured_backends(transport), **kwargs)
