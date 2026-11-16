"""One command that checks everything the demo needs, and prints a clear pass or fail list.

    python scripts/preflight.py            # about a minute
    python scripts/preflight.py --quick    # skip playing every case (a few seconds)

It checks: the Python version, the dependencies, that the demo port is free, that the server starts, that every endpoint answers, that every
library case plays to a verdict with the pinned digest, that the static site files are served, and that no API key is needed (the server is
started with every key variable removed). It never uses the network and never prints a secret. Exit code 0 only if everything passes.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
KEY_VARS = ("OLLAMA_API_KEY", "OLLAMA_HOST", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
DEMO_PORT = 8000

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail and not ok else ""))
    return ok


def http(method: str, url: str, body: object | None = None, timeout: float = 120.0) -> tuple[int, bytes]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="do not play every case")
    quick = ap.parse_args().quick

    print("Python and dependencies")
    check("Python 3.11 or newer", sys.version_info >= (3, 11), sys.version.split()[0])
    for mod in ("pydantic", "fastapi", "uvicorn", "rich"):
        try:
            importlib.import_module(mod)
            check(f"import {mod}", True)
        except Exception as e:
            check(f"import {mod}", False, str(e))

    print("Port")
    with socket.socket() as s:
        free = s.connect_ex(("127.0.0.1", DEMO_PORT)) != 0
    check(f"port {DEMO_PORT} is free (the demo's default)", free, "something is already listening; stop it or serve with --port")

    print("Cases (engine only, no server)")
    from courtroom.cases import CASES
    from courtroom.engine import run_trial, verify_chain

    pinned = json.loads((ROOT / "tests/golden/bundle_digests.json").read_text())
    if quick:
        check("every case plays (skipped by --quick)", True)
    else:
        bad = []
        for cid in CASES:
            try:
                res = run_trial(CASES[cid], "aggressive", "conservative", 0)
                if not res.digest or not verify_chain(res.events):
                    bad.append(f"{cid}: bad digest or chain")
                key = f"{cid}|aggressive|conservative|0"
                if key in pinned and pinned[key] != res.digest:
                    bad.append(f"{cid}: digest differs from the pinned one")
            except Exception as e:
                bad.append(f"{cid}: {type(e).__name__}: {e}")
        check(f"all {len(CASES)} library cases play to a verdict with the pinned digest", not bad, "; ".join(bad))

    print("Server (started with every API key variable removed)")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {k: v for k, v in os.environ.items() if k not in KEY_VARS}
    proc = subprocess.Popen([sys.executable, "-m", "courtroom", "serve", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        up = False
        for _ in range(80):
            try:
                socket.create_connection(("127.0.0.1", port), 0.3).close()
                up = True
                break
            except OSError:
                time.sleep(0.25)
        if not check("the server starts", up and proc.poll() is None):
            return finish()
        gets = ["/api/health", "/api/cases", "/api/strategies", "/api/results", "/api/ai", "/api/cases/cookie-jar"]
        for path in gets:
            st, _ = http("GET", base + path)
            check(f"GET {path}", st == 200, f"status {st}")
        posts = [
            ("/api/trial", {"case_id": "cookie-jar", "prosecution": "aggressive", "defense": "conservative", "seed": 1}),
            ("/api/game", {"case_id": "cookie-jar", "strategies": ["aggressive", "conservative"], "seeds": 2}),
            ("/api/matters", {"case_id": "cookie-jar", "seeds": 2}),
            ("/api/classic", {"case_id": "cookie-jar", "seeds": 5, "resamples": 10}),
            ("/api/efficiency", {"case_id": "cookie-jar", "seeds": 5}),
            ("/api/tree", {"case_id": "cookie-jar"}),
            ("/api/lookahead", {"case_id": "cookie-jar", "seeds": 4}),
            ("/api/bootstrap", {"case_id": "cookie-jar", "seeds": 5, "resamples": 20}),
            ("/api/explain", {"case_id": "cookie-jar", "prosecution": "aggressive", "defense": "conservative", "seed": 1}),
        ]
        for path, body in posts:
            st, _ = http("POST", base + path, body)
            check(f"POST {path}", st == 200, f"status {st}")
        st, raw = http("POST", base + "/api/trial", {"case_id": "cookie-jar", "prosecution": "aggressive", "defense": "conservative", "seed": 0})
        digest = json.loads(raw).get("digest") if st == 200 else None
        check("a live trial has the same digest as the recorded one", digest == pinned.get("cookie-jar|aggressive|conservative|0"), f"{digest}")
        for path, want in (("/api/analyst", 503), ("/api/case/draft", 503), ("/api/narrate", 503)):
            st, _ = http("POST", base + path, {"text": "x" * 20, "messages": [{"role": "user", "content": "hi"}], "case_id": "cookie-jar"})
            check(f"POST {path} without a model backend is a clean 503 or 422, not a crash", st in (want, 422), f"status {st}")
        st, _ = http("POST", base + "/api/trial", {"case_id": "no-such-case"})
        check("an unknown case is a 4xx, not a 500", 400 <= st < 500, f"status {st}")
        for path in ("/", "/index.html", "/lab.html", "/data/bundle.js", "/data/analysis.js", "/voices/manifest.json", "/tour.js", "/app.js"):
            st, _ = http("GET", base + path)
            check(f"static {path}", st == 200, f"status {st}")
        st, _ = http("GET", base + "/api/health")
        check("the server still answers after all of that", st == 200)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    return finish()


def finish() -> int:
    failed = [n for n, ok, _ in results if not ok]
    print()
    print(f"{len(results) - len(failed)} passed, {len(failed)} failed")
    if failed:
        print("FAILED: " + "; ".join(failed))
    else:
        print("READY: everything the demo needs is in place.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
