"""The three places a model can live, behind one ``chat`` call: Ollama Cloud, local Ollama, Gemini.

All three speak plain HTTP through ``http_json`` (standard library only: no SDK, no new dependency), which is also the single
place tests replace, so no test ever touches a network. Every failure becomes a ``BackendError``; nothing here raises anything
else at the caller. Keys come from the environment (``.env`` is read by ``courtroom.llm.env``) and are sent only in a request
header; they are never logged or stored.
"""

from __future__ import annotations

import contextlib
import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

CLOUD_URL = "https://ollama.com"
DEFAULT_CLOUD_MODEL = "gpt-oss:120b"
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"  # pinned, not a moving "-latest" alias, so a recorded cache stays valid
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta"
REQUEST_TIMEOUT = 90.0
PROBE_TIMEOUT = 2.5


class BackendError(RuntimeError):
    """A backend could not answer. The message is safe to show (it never contains a key)."""


def http_json(url: str, body: dict[str, Any] | None, headers: dict[str, str], timeout: float) -> dict[str, Any]:
    """One JSON request. GET when ``body`` is None. The only function in the package that opens a socket."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers}, method="GET" if body is None else "POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")
        with contextlib.suppress(ValueError, AttributeError, TypeError):
            err = json.loads(text).get("error", text)
            text = str(err.get("message", err) if isinstance(err, dict) else err)
        raise BackendError(f"HTTP {exc.code}: {text[:200]}") from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise BackendError(str(getattr(exc, "reason", exc))[:200]) from None


# tests (and nothing else) replace this
Transport = Callable[[str, dict[str, Any] | None, dict[str, str], float], dict[str, Any]]


@dataclass
class OllamaBackend:
    """Ollama's ``/api/chat``. With a key it is Ollama Cloud, without one a local server."""

    name: str  # "cloud" | "local"
    base_url: str
    model: str | None  # None: use the first installed model (local only)
    key: str | None = None
    transport: Transport | None = None
    _think: bool = True
    _probed: bool | None = None

    def _http(self, url: str, body: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        return (self.transport or http_json)(url, body, headers, timeout)

    def resolve_model(self) -> str | None:
        if self.model:
            return self.model
        models = self._http(f"{self.base_url}/api/tags", None, PROBE_TIMEOUT).get("models")
        if isinstance(models, list) and models and isinstance(models[0], dict):
            self.model = str(models[0].get("name"))
        return self.model

    def probe(self) -> bool:
        """Does it answer right now? Cached after the first probe (``reset`` clears it)."""
        if self._probed is None:
            try:
                self._probed = self.resolve_model() is not None
            except BackendError:
                self._probed = False
        return self._probed

    def reset(self) -> None:
        self._probed = None

    def chat(self, system: str, prompt: str, *, temperature: float, max_tokens: int, schema: type[BaseModel] | None) -> str:
        model = self.resolve_model()
        if model is None:
            raise BackendError("no model installed")
        for _ in range(2):  # a second pass only to drop ``think`` for a model that rejects it
            body: dict[str, Any] = {
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": temperature, "seed": 0, "num_predict": max_tokens},
            }
            if self.name == "local" and self._think:
                body["think"] = False
            if schema is not None:
                body["format"] = schema.model_json_schema()
            try:
                reply = self._http(f"{self.base_url}/api/chat", body, REQUEST_TIMEOUT)
            except BackendError as exc:
                if "think" in str(exc).lower() and self._think and self.name == "local":
                    self._think = False
                    continue
                raise
            message = reply.get("message")
            text = str(message.get("content", "")) if isinstance(message, dict) else ""
            if not text.strip():
                raise BackendError("the model returned an empty reply")
            return text.strip()
        raise BackendError("the model rejected the request")


@dataclass
class GeminiBackend:
    key: str
    model: str = DEFAULT_GEMINI_MODEL
    name: str = "gemini"
    transport: Transport | None = None

    def _http(self, url: str, body: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
        return (self.transport or http_json)(url, body, {"x-goog-api-key": self.key}, timeout)

    def probe(self) -> bool:
        try:
            self._http(f"{GEMINI_URL}/models?pageSize=1", None, PROBE_TIMEOUT)
            return True
        except BackendError:
            return False

    def reset(self) -> None:
        pass

    def chat(self, system: str, prompt: str, *, temperature: float, max_tokens: int, schema: type[BaseModel] | None) -> str:
        config: dict[str, Any] = {"temperature": temperature, "maxOutputTokens": max_tokens}
        if schema is not None:
            config["responseMimeType"] = "application/json"
        body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": config}
        reply = self._http(f"{GEMINI_URL}/models/{self.model}:generateContent", body, REQUEST_TIMEOUT)
        for cand in reply.get("candidates") or []:
            if "SAFETY" in str(cand.get("finishReason", "")).upper():
                raise BackendError("blocked by the provider's safety filter")
            parts = (cand.get("content") or {}).get("parts") or []
            text = "".join(str(p.get("text", "")) for p in parts).strip()
            if text:
                return text
        raise BackendError("the model returned an empty reply")


def configured_backends(transport: Transport | None = None) -> list[OllamaBackend | GeminiBackend]:
    """In the order they are tried: Ollama Cloud (if a key is set), local Ollama, then Gemini (if a key is set)."""
    out: list[OllamaBackend | GeminiBackend] = []
    if os.environ.get("OLLAMA_API_KEY"):
        out.append(OllamaBackend("cloud", CLOUD_URL, os.environ.get("OLLAMA_MODEL", DEFAULT_CLOUD_MODEL), os.environ["OLLAMA_API_KEY"], transport))
    local_url = os.environ.get("OLLAMA_LOCAL_URL", "http://localhost:11434").rstrip("/")
    out.append(OllamaBackend("local", local_url, os.environ.get("OLLAMA_LOCAL_MODEL") or None, None, transport))
    if os.environ.get("GEMINI_API_KEY"):
        out.append(GeminiBackend(os.environ["GEMINI_API_KEY"], os.environ.get("COURTROOM_GEMINI_MODEL", DEFAULT_GEMINI_MODEL), transport=transport))
    return out
