"""The strategy lab's "ask the analyst" backend: forwards a question to an Ollama model.

The browser never sees the API key. It is read from the environment (or a git-ignored ``.env`` file at the
repo root) and used only here. Two backends are tried in order:

1. Ollama Cloud (``https://ollama.com``) with ``OLLAMA_API_KEY``.
2. A local Ollama server (``http://localhost:11434``), which needs no key.

The model explains numbers the lab has already computed; it is told never to invent its own.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CLOUD_URL = "https://ollama.com"
DEFAULT_CLOUD_MODEL = "gpt-oss:120b"

SYSTEM_PROMPT = """You are the analyst in the Strategy Lab of the Saul Goodman Courtroom, a simulation where two AI \
lawyers (the Accuser and the Defender) each pick a style (Bold, Careful, Smart or Wild) and a rulebook judge decides.
You explain the game theory of the selected case to a curious visitor.

Rules:
- Use only the numbers in the LAB DATA block. Never invent or recompute payoffs, equilibria or win rates. If the \
data does not answer the question, say so.
- Plain, everyday language. Short sentences. Explain any game theory term the first time you use it.
- Keep answers under 140 words unless asked for more. No markdown tables, no headings.
- Payoff per trial is: win value x (1 if that lawyer wins) - cost weight x budget spent - sanction weight x sanctions.

You can also operate the lab. When the visitor asks to see something or to try a what-if, finish your reply with one \
final line of the exact form
ACTIONS: [ ... ]
holding a JSON array of any of these objects:
  {"type":"case","id":"<case id from LAB DATA>"}
  {"type":"pair","p":"<style>","d":"<style>"}   styles: aggressive (Bold), conservative (Careful), adaptive (Smart), reckless (Wild)
  {"type":"weights","V":<0-20>,"c":<0-2>,"mu":<0-5>}   any subset of V (win value), c (cost weight), mu (sanction weight)
  {"type":"reset"}   back to the default weights
Leave the ACTIONS line out when there is nothing to change."""


class AnalystTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=2000)


class AnalystRequest(BaseModel):
    question: str = Field(min_length=1, max_length=600)
    context: str = Field(default="", max_length=8000)
    history: list[AnalystTurn] = Field(default_factory=list, max_length=8)


class AnalystUnavailable(Exception):
    """No backend could answer. ``reasons`` lists what each one said."""

    def __init__(self, reasons: list[str]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = reasons


def load_env(path: Path | None = None) -> None:
    """Read KEY=VALUE lines from ``.env`` into the environment without overriding what is already set."""
    path = path or REPO_ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _local_url() -> str:
    return os.environ.get("OLLAMA_LOCAL_URL", "http://localhost:11434").rstrip("/")


def _request(url: str, body: dict[str, object] | None, key: str | None, timeout: float) -> dict[str, object]:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        text = exc.read().decode(errors="replace")
        try:
            text = str(json.loads(text).get("error", text))
        except (ValueError, AttributeError):
            pass
        raise RuntimeError(text[:200] or f"HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise RuntimeError(str(getattr(exc, "reason", exc))[:200]) from None


def _local_model() -> str | None:
    if os.environ.get("OLLAMA_LOCAL_MODEL"):
        return os.environ["OLLAMA_LOCAL_MODEL"]
    models = _request(f"{_local_url()}/api/tags", None, None, timeout=2).get("models")
    if isinstance(models, list) and models and isinstance(models[0], dict):
        return str(models[0].get("name"))
    return None


def _chat(base: str, model: str, key: str | None, messages: list[dict[str, str]]) -> str:
    body: dict[str, object] = {"model": model, "messages": messages, "stream": False, "options": {"temperature": 0.3}}
    reply = _request(f"{base}/api/chat", body, key, timeout=90)
    message = reply.get("message")
    content = str(message.get("content", "")) if isinstance(message, dict) else ""
    if not content.strip():
        raise RuntimeError("the model returned an empty reply")
    return content.strip()


def ask(req: AnalystRequest) -> dict[str, str]:
    """Answer ``req`` with the first backend that works. Raises AnalystUnavailable when none does."""
    load_env()
    messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\nLAB DATA:\n" + (req.context or "(none)")}]
    messages += [t.model_dump() for t in req.history]
    messages.append({"role": "user", "content": req.question})
    reasons: list[str] = []

    key = os.environ.get("OLLAMA_API_KEY")
    if key:
        model = os.environ.get("OLLAMA_MODEL", DEFAULT_CLOUD_MODEL)
        try:
            return {"reply": _chat(CLOUD_URL, model, key, messages), "source": "cloud", "model": model}
        except RuntimeError as exc:
            reasons.append(f"Ollama Cloud: {exc}")
    else:
        reasons.append("Ollama Cloud: no OLLAMA_API_KEY set")

    try:
        local = _local_model()
        if local is None:
            reasons.append("Local Ollama: no models installed")
        else:
            return {"reply": _chat(_local_url(), local, None, messages), "source": "local", "model": local}
    except RuntimeError as exc:
        reasons.append(f"Local Ollama: {exc}")
    raise AnalystUnavailable(reasons)
