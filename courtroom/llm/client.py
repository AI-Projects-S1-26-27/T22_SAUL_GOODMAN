"""Cached, capped, optional Gemini client.

Owner: Engineer 6 (added alongside the deterministic core, never inside it).

Four properties the rest of the package relies on:

* **Optional.** No API key, no SDK, or no network and every call returns ``None``. The caller
  falls back to a template. Nothing in the deterministic engine imports this module.
* **Cached.** Every response is stored on disk under ``sha256(system | prompt | model |
  temperature | max_tokens)``. A committed cache makes the demo work offline, and a cache hit
  never calls out.
* **Capped.** Tokens per call, calls per trial, calls per process and a currency ceiling are
  all bounded. The running cost estimate is available at any time.
* **Never fatal.** Rate limits, safety blocks, malformed output and transport errors are each
  counted and turned into a fallback. Nothing retries forever and nothing raises at the caller.

Reproducibility, stated plainly: a cache *hit* is deterministic. A cache *miss* on another
machine calls the provider, and even at temperature 0 providers do not guarantee identical
output across time or model revisions. That is precisely why nothing produced here is allowed
into the payoff matrices.

The API key is read from ``GEMINI_API_KEY`` and is never logged, printed or persisted.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

# Single config value for the model, overridable without touching code.
# Verified against a live key: Flash-Lite is the cheapest tier, and a *pinned* version is used
# deliberately. ``gemini-flash-lite-latest`` also works but is a moving alias, and an alias that
# changes model underneath a committed cache would quietly destroy reproducibility.
# Rejected after testing: gemini-2.5-flash-lite (listed by the API but 404 "no longer available")
# and gemini-3.5-flash-lite (intermittent 503, and rejects a thinking budget).
DEFAULT_MODEL = os.environ.get("COURTROOM_GEMINI_MODEL", "gemini-3.1-flash-lite")
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS = 160

CACHE_PATH = Path(__file__).resolve().parent / "cache" / "responses.json"

# Spend ceilings. Deliberately small: this layer is an exhibition, not a workload.
MAX_CALLS_PER_TRIAL = 40
MAX_CALLS_PER_RUN = 400
MAX_RETRIES_ON_RATE_LIMIT = 3
BACKOFF_SECONDS = (1.0, 2.0, 4.0)

# Currency per million tokens, for the printed estimate only. Gemini pricing is not exposed by
# the API, so this MUST be set from the pricing page for the chosen model; the default is a
# placeholder, not a quoted price. Override with COURTROOM_LLM_RATES="<input>,<output>".
DEFAULT_RATES = (0.0, 0.0)


def _rates() -> tuple[float, float]:
    raw = os.environ.get("COURTROOM_LLM_RATES")
    if raw:
        try:
            a, b = (float(x) for x in raw.split(","))
            return a, b
        except ValueError:
            pass
    return DEFAULT_RATES


def cache_key(prompt: str, system: str, model: str, temperature: float, max_tokens: int) -> str:
    blob = json.dumps([system, prompt, model, temperature, max_tokens], separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class ActionChoice(BaseModel):
    """Structured output schema: the model must answer with an index into the legal-action list."""

    choice: int


@dataclass
class Usage:
    calls: int = 0
    cache_hits: int = 0
    refusals: int = 0  # no key, SDK missing, or a cap reached
    rate_limited: int = 0  # 429s that exhausted the retry budget
    blocked: int = 0  # empty response, or stopped by a safety filter
    malformed: int = 0  # structured output that would not parse
    errors: int = 0  # anything else from the transport
    quota_stops: int = 0  # daily cap hit; an outage, NOT a fallback and NOT a model failure
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def fallbacks(self) -> int:
        """Every outcome in which the caller had to use its own fallback.

        ``quota_stops`` is excluded on purpose: the run stops rather than falling back, so
        counting it here would blame the model for the free tier running out.
        """
        return self.refusals + self.rate_limited + self.blocked + self.malformed + self.errors

    @property
    def attempts(self) -> int:
        return self.calls + self.cache_hits + self.fallbacks

    def fallback_rate(self) -> float:
        return round(self.fallbacks / self.attempts, 4) if self.attempts else 0.0

    def cost_estimate(self) -> float:
        rin, rout = _rates()
        return round(self.input_tokens / 1e6 * rin + self.output_tokens / 1e6 * rout, 6)

    def summary(self) -> str:
        rates_set = _rates() != (0.0, 0.0)
        cost = f"${self.cost_estimate():.4f}" if rates_set else "not priced (set COURTROOM_LLM_RATES)"
        return (
            f"Gemini calls: {self.calls} · cache hits: {self.cache_hits} · "
            f"fallbacks: {self.fallbacks} (unavailable {self.refusals}, rate-limited {self.rate_limited}, "
            f"blocked {self.blocked}, malformed {self.malformed}, errors {self.errors}) · "
            f"fallback rate {self.fallback_rate():.1%} · "
            f"tokens in/out {self.input_tokens}/{self.output_tokens} · estimated cost {cost}"
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "calls": self.calls,
            "cache_hits": self.cache_hits,
            "fallbacks": self.fallbacks,
            "unavailable": self.refusals,
            "rate_limited": self.rate_limited,
            "blocked": self.blocked,
            "malformed": self.malformed,
            "errors": self.errors,
            "fallback_rate": self.fallback_rate(),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "quota_stops": self.quota_stops,
            "estimated_cost": self.cost_estimate(),
        }


class SpendCeilingReached(RuntimeError):
    """Raised at the harness boundary when a configured currency ceiling is hit."""


class QuotaExhausted(RuntimeError):
    """The key's daily quota is gone.

    Deliberately an exception rather than a fallback. A per-minute 429 is worth waiting out,
    but a daily cap is not: retrying cannot succeed, and silently substituting the Adaptive
    policy would corrupt the exhibition's fallback statistics with an outage that has nothing
    to do with the model's behaviour. The harness catches this, stops cleanly and resumes from
    the cache on the next run.
    """


def _is_daily_quota(message: str) -> bool:
    """Tell a daily cap apart from a per-minute rate limit. Both arrive as 429."""
    lowered = message.lower()
    return any(marker in lowered for marker in ("per day", "perday", "per_day", "daily limit", "requests per day"))


@dataclass
class LLMClient:
    """Returns text, or ``None`` when the caller must fall back."""

    model: str = DEFAULT_MODEL
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS
    cache_path: Path = CACHE_PATH
    allow_network: bool = True
    # Flash-Lite rejects a thinking budget with a bare 400, so this is off by default and the
    # transport drops it automatically if a model turns out not to accept it.
    disable_thinking: bool = False
    cost_ceiling: float | None = None  # in the same currency as COURTROOM_LLM_RATES
    max_calls_per_run: int = MAX_CALLS_PER_RUN  # explicit, so a harness cannot silently hit it
    usage: Usage = field(default_factory=Usage)
    _cache: dict[str, str] = field(default_factory=dict, init=False)
    _dirty: bool = field(default=False, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _calls_this_trial: int = field(default=0, init=False)
    _client: object | None = field(default=None, init=False)
    _thinking_supported: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        self._cache = self._load_cache()

    # ------------------------------------------------------------------ cache

    def _load_cache(self) -> dict[str, str]:
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def save(self) -> None:
        if not self._dirty:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._cache, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(self.cache_path)
        self._dirty = False

    # ------------------------------------------------------------------ availability

    @property
    def has_key(self) -> bool:
        return bool(os.environ.get("GEMINI_API_KEY"))

    def start_trial(self) -> None:
        self._calls_this_trial = 0

    def check_ceiling(self) -> None:
        if self.cost_ceiling is not None and self.usage.cost_estimate() >= self.cost_ceiling:
            raise SpendCeilingReached(
                f"estimated spend {self.usage.cost_estimate():.4f} reached the ceiling {self.cost_ceiling:.4f}"
            )

    def _sdk(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        return self._client

    # ------------------------------------------------------------------ the one entry point

    def complete(self, system: str, prompt: str, schema: type[BaseModel] | None = None) -> str | None:
        """Cached completion, or ``None`` when the caller must use its fallback.

        With ``schema``, structured JSON output is requested so the answer can be parsed
        mechanically rather than scraped out of prose.
        """
        key = cache_key(prompt, system, self.model, self.temperature, self.max_tokens)
        with self._lock:
            hit = self._cache.get(key)
        if hit is not None:
            self.usage.cache_hits += 1
            return hit

        if not self.allow_network or not self.has_key:
            self.usage.refusals += 1
            return None
        if self._calls_this_trial >= MAX_CALLS_PER_TRIAL or self.usage.calls >= self.max_calls_per_run:
            self.usage.refusals += 1
            return None
        self.check_ceiling()

        text = self._request(system, prompt, schema)
        if text is None:
            return None

        with self._lock:
            self._cache[key] = text
            self._dirty = True
        return text

    def choose(self, system: str, prompt: str, n_options: int) -> int | None:
        """Ask for an index into a legal-action list. ``None`` means fall back.

        Out-of-range or unparseable answers count as malformed, never as a silent zero.
        """
        if n_options <= 0:
            return None
        raw = self.complete(system, prompt, schema=ActionChoice)
        if raw is None:
            return None
        try:
            index = int(ActionChoice.model_validate_json(raw).choice)
        except (ValueError, TypeError):
            try:
                index = int(json.loads(raw)["choice"])
            except Exception:
                self.usage.malformed += 1
                return None
        if not 0 <= index < n_options:
            self.usage.malformed += 1
            return None
        return index

    # ------------------------------------------------------------------ transport

    def _config(self, system: str, schema: type[BaseModel] | None):
        from google.genai import types

        kwargs: dict[str, object] = {
            "system_instruction": system,
            "temperature": self.temperature,
            "max_output_tokens": self.max_tokens,
        }
        if schema is not None:
            kwargs["response_mime_type"] = "application/json"
            kwargs["response_schema"] = schema
        if self.disable_thinking and self._thinking_supported:
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        return types.GenerateContentConfig(**kwargs)

    def _request(self, system: str, prompt: str, schema: type[BaseModel] | None) -> str | None:
        """One logical request, with bounded 429 backoff. Every failure mode is counted."""
        from google.genai import errors

        for attempt in range(MAX_RETRIES_ON_RATE_LIMIT + 1):
            try:
                response = self._sdk().models.generate_content(
                    model=self.model, contents=prompt, config=self._config(system, schema)
                )
            except errors.ClientError as exc:
                status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
                message = str(exc)
                if status == 429 or "429" in message or "RESOURCE_EXHAUSTED" in message:
                    if _is_daily_quota(message):
                        # Not a fallback and not retryable: stop the run and resume from cache.
                        self.usage.quota_stops += 1
                        raise QuotaExhausted(
                            "Gemini daily quota exhausted. Progress is cached; rerun the same "
                            "command tomorrow to resume without re-spending calls."
                        ) from exc
                    if attempt < MAX_RETRIES_ON_RATE_LIMIT:
                        time.sleep(BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)])
                        continue
                    self.usage.rate_limited += 1
                    return None
                if self.disable_thinking and self._thinking_supported and (status == 400 or "INVALID_ARGUMENT" in message):
                    # Flash-Lite answers a thinking budget with a bare "invalid argument" that
                    # names no field, so attribute the first 400 to it and retry without.
                    self._thinking_supported = False
                    continue
                self.usage.errors += 1
                return None
            except errors.ServerError:
                if attempt < MAX_RETRIES_ON_RATE_LIMIT:
                    time.sleep(BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)])
                    continue
                self.usage.errors += 1
                return None
            except Exception:
                # A dead network must never take the demo down with it.
                self.usage.errors += 1
                return None

            self._record_tokens(response)
            text = self._extract(response)
            if text is None:
                self.usage.blocked += 1
                return None
            self.usage.calls += 1
            self._calls_this_trial += 1
            return text

        self.usage.errors += 1
        return None

    def _record_tokens(self, response: object) -> None:
        meta = getattr(response, "usage_metadata", None)
        if meta is None:
            return
        self.usage.input_tokens += getattr(meta, "prompt_token_count", 0) or 0
        self.usage.output_tokens += (getattr(meta, "candidates_token_count", 0) or 0) + (
            getattr(meta, "thoughts_token_count", 0) or 0
        )

    @staticmethod
    def _extract(response: object) -> str | None:
        """Text of the first candidate, or ``None`` if empty or stopped by a safety filter."""
        if getattr(response, "prompt_feedback", None) and getattr(response.prompt_feedback, "block_reason", None):
            return None
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            reason = str(getattr(candidate, "finish_reason", "") or "")
            if "SAFETY" in reason.upper() or "RECITATION" in reason.upper():
                return None
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            text = "".join(getattr(part, "text", "") or "" for part in parts).strip()
            if text:
                return text
        text = (getattr(response, "text", None) or "").strip()
        return text or None
