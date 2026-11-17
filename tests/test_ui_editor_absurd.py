"""Absurd input in the case editor is handled politely: no page error, no script runs, and the page says what is wrong or runs the case."""

from __future__ import annotations

import pytest

from tests.ui_support import live_server, page


def _open_blank(pg, base):
    pg.goto(f"{base}/index.html")
    pg.wait_for_selector("#blank-case", timeout=20000)
    pg.click("#blank-case")
    pg.wait_for_selector("#editor:not([hidden]) input")


def _run(pg) -> str:
    pg.click("text=Run it here")
    pg.wait_for_function("(() => { const t = document.querySelector('#ed-result')?.innerText || ''; return t && !t.startsWith('Running'); })()", timeout=30000)
    return pg.inner_text("#ed-result")


def test_blank_case_runs_and_shows_before_and_after() -> None:
    with live_server() as base, page() as (pg, errors):
        _open_blank(pg, base)
        out = _run(pg)
        assert "Verdict" in out and errors == []


@pytest.mark.parametrize("value", ["<script>window.__pwned = 1</script>", "<img src=x onerror=window.__pwned=1>", "", "   ", "x" * 200_000, "\u0000‮﻿", "💥" * 50])
def test_hostile_or_odd_titles_never_execute_or_crash(value: str) -> None:
    with live_server() as base, page() as (pg, errors):
        _open_blank(pg, base)
        pg.fill("input[aria-label='Title']", value)
        pg.dispatch_event("input[aria-label='Title']", "change")
        out = _run(pg)
        assert out.strip() != ""  # either the before/after table or a readable refusal
        assert not out.lstrip().startswith("The server did not accept this case: 422 {")  # the reason, not the raw reply
        if len(value) > 100_000:
            assert "too large" in out
        assert pg.evaluate("window.__pwned") is None
        assert errors == []


@pytest.mark.parametrize("value", ["-5", "abc", "1e9", "0", "99999999999999999999", "NaN", ""])
def test_absurd_numbers_are_clamped_not_sent_as_is(value: str) -> None:
    with live_server() as base, page() as (pg, errors):
        _open_blank(pg, base)
        for label, lo, hi in (("Budget for each lawyer", 1, 50), ("Reliability of The Accuser's evidence", 0, 1)):
            box = pg.locator(f"input[aria-label=\"{label}\"]")
            box.evaluate("(el, v) => { el.type = 'text'; el.value = v; el.dispatchEvent(new Event('change')); }", value)
            shown = box.input_value()
            assert shown.replace(".", "", 1).replace("-", "", 1).isdigit(), shown
            assert lo <= float(shown) <= hi
        out = _run(pg)
        assert "Verdict" in out and errors == []


def test_an_empty_docket_is_a_clean_result_not_a_crash() -> None:
    with live_server() as base, page() as (pg, errors):
        _open_blank(pg, base)
        while pg.locator("text=Remove").count() > 2:  # keep the one point's own button out of it
            break
        for _ in range(2):
            pg.locator("table.ed tbody tr:has(td input[aria-label='Exhibit title']) button:has-text('Remove')").first.click()
        out = _run(pg)
        assert out.strip() != "" and errors == []
