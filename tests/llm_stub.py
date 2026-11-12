"""A fake model server for tests: records every request, answers from a function. No test touches a network."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from courtroom.llm import LLMClient, OllamaBackend


class Stub:
    def __init__(self, reply: Callable[[dict[str, Any]], str] | None = None) -> None:
        self.reply = reply or (lambda body: json.dumps({"choice": 0, "reason": "It helps my side."}))
        self.requests: list[tuple[str, dict[str, Any] | None, dict[str, str]]] = []

    def __call__(self, url: str, body: dict[str, Any] | None, headers: dict[str, str], timeout: float) -> dict[str, Any]:
        self.requests.append((url, body, headers))
        if url.endswith("/api/tags"):
            return {"models": [{"name": "stub-model"}]}
        return {"message": {"content": self.reply(body or {})}}

    @property
    def chats(self) -> list[dict[str, Any]]:
        return [b for u, b, _ in self.requests if u.endswith("/api/chat") and b]


def stub_client(tmp_path: Path, stub: Stub | None = None, **kwargs: Any) -> tuple[LLMClient, Stub]:
    stub = stub or Stub()
    backend = OllamaBackend("local", "http://stub", "stub-model", None, transport=stub)
    return LLMClient(backends=[backend], cache_path=tmp_path / "cache.json", **kwargs), stub
