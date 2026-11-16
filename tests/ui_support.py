"""Shared helpers for the browser tests: a static file server for the web app and a Playwright browser.

The browser tests need ``playwright`` and its Chromium (``pip install -e .[dev]`` then ``python -m playwright install chromium``).
They never touch the network: the page's CDN scripts (fonts, gsap, three) are blocked, and the app works without them.
"""

from __future__ import annotations

import functools
import http.server
import socketserver
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "courtroom" / "viz" / "web"


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a: object) -> None:
        pass


@contextmanager
def static_server() -> Iterator[str]:
    handler = functools.partial(_Quiet, directory=str(WEB))
    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler) as srv:
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            yield f"http://127.0.0.1:{srv.server_address[1]}"
        finally:
            srv.shutdown()


@contextmanager
def page(base_viewport: tuple[int, int] = (1300, 900), tour_seen: bool = True) -> Iterator[tuple[object, list[str]]]:
    """A fresh Chromium page with outside hosts blocked; yields (page, list of page errors).

    ``tour_seen`` marks the guided tours as already shown, so they do not open over the page under test.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": base_viewport[0], "height": base_viewport[1]})
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith("http://127.0.0.1") else r.abort())
        if tour_seen:
            ctx.add_init_script("try { localStorage.setItem('courtroom-tour-home-v3', 'seen'); localStorage.setItem('courtroom-tour-lab-v3', 'seen'); } catch (e) {}")
        pg = ctx.new_page()
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        try:
            yield pg, errors
        finally:
            browser.close()


@contextmanager
def live_server() -> Iterator[str]:
    """The real local server (python -m courtroom serve) on a free port, for the tests of live-only controls."""
    import socket
    import subprocess
    import sys
    import time

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen([sys.executable, "-m", "courtroom", "serve", "--port", str(port)], cwd=WEB.parent.parent.parent, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try:
                socket.create_connection(("127.0.0.1", port), 0.3).close()
                break
            except OSError:
                time.sleep(0.25)
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()
        proc.wait(timeout=10)
