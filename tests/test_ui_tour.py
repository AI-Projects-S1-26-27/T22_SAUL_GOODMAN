"""The guided tours: they open once per browser, skip steps whose element is absent, and cover the page."""

from __future__ import annotations

from tests.ui_support import live_server, page, static_server

TOUR_OPEN = "document.querySelector('.tour') && !document.querySelector('.tour').hidden"


def titles(pg) -> list[str]:
    return [s["title"] for s in pg.evaluate("Tour.steps()")]


def test_tour_opens_by_itself_once_per_browser() -> None:
    with static_server() as base, page(tour_seen=False) as (pg, errors):
        pg.goto(f"{base}/index.html")
        pg.wait_for_function(TOUR_OPEN, timeout=5000)
        pg.keyboard.press("Escape")
        assert not pg.evaluate(TOUR_OPEN)
        pg.reload()
        pg.wait_for_timeout(2000)
        assert not pg.evaluate(TOUR_OPEN)  # remembered: no second automatic start
        pg.goto(f"{base}/lab.html")  # the lab has its own memory
        pg.wait_for_function(TOUR_OPEN, timeout=5000)
        assert errors == []


def test_tour_marks_itself_seen_as_soon_as_it_opens() -> None:
    with static_server() as base, page(tour_seen=False) as (pg, _):
        pg.goto(f"{base}/index.html")
        pg.wait_for_function(TOUR_OPEN, timeout=5000)
        assert pg.evaluate("localStorage.getItem(Tour.key)") == "seen"  # closing by reload or crash still counts


def test_tour_skips_live_only_steps_on_the_hosted_site_and_keeps_them_when_live() -> None:
    with static_server() as base, page() as (pg, _):
        pg.goto(f"{base}/index.html")
        pg.wait_for_function("window.Tour && document.querySelector('#live-panel .pill.rec')")
        recorded = titles(pg)
        for live_only in ("The seed box", "The LIVE badge", "Courtroom surprises", "Surprise me", "Change this case (what-if)", "Run it again and compare", "Why this verdict?"):
            assert live_only not in recorded, live_only
        assert "RECORDED: replaying saved trials" in recorded and "Which style wins" in recorded
    with live_server() as base, page() as (pg, errors):
        pg.goto(f"{base}/index.html")
        pg.wait_for_selector("#live-seed")
        live = titles(pg)
        for step in ("The seed box", "The LIVE badge", "Courtroom surprises", "Surprise me", "Change this case (what-if)", "Run it again and compare", "Why this verdict?", "What would flip it (the tipping point)", "Does strategy matter here?"):
            assert step in live, step
        assert "RECORDED: replaying saved trials" not in live
        assert errors == []


def test_a_step_whose_element_is_missing_is_skipped_and_the_tour_walks_to_the_end() -> None:
    with static_server() as base, page() as (pg, errors):
        pg.goto(f"{base}/index.html")
        pg.wait_for_function("window.Tour")
        pg.evaluate("document.querySelector('#how').remove(); document.querySelector('#lab .btn').remove()")
        t = titles(pg)
        assert "How a trial works" not in t and "The strategy lab" not in t
        pg.evaluate("Tour.start(0)")
        seen = []
        for _ in range(len(t) + 2):
            if not pg.evaluate(TOUR_OPEN):
                break
            seen.append(pg.inner_text("#tour-title"))
            pg.keyboard.press("ArrowRight")
        assert seen == t and not pg.evaluate(TOUR_OPEN)
        assert errors == []


def test_guide_in_the_nav_restarts_the_tour_on_both_pages_and_shows_the_map() -> None:
    with static_server() as base, page() as (pg, _):
        for path in ("index.html", "lab.html"):
            pg.goto(f"{base}/{path}")
            pg.wait_for_selector("#guide-btn")
            assert not pg.evaluate(TOUR_OPEN)
            pg.click("#guide-btn")
            assert pg.evaluate(TOUR_OPEN)
            assert pg.locator(".tour-map").count() == 1 and "Certified or extra" in pg.inner_text(".tour-map")
            pg.click("[data-act=end]")
            assert not pg.evaluate(TOUR_OPEN)


def test_lab_tour_covers_every_chapter() -> None:
    with static_server() as base, page() as (pg, _):
        pg.goto(f"{base}/lab.html")
        pg.wait_for_selector(".chapter")
        pg.wait_for_function("document.querySelectorAll('.chapter').length >= 17", timeout=10000)
        ids = pg.evaluate("[...document.querySelectorAll('.chapter')].map((c) => c.id)")
        t = titles(pg)
        n = len(ids)
        chapter_steps = [x for x in t if x[:2].strip(". ").isdigit() or x.split(".")[0].isdigit()]
        assert len(chapter_steps) == n, (n, t)


def test_tour_does_not_open_over_the_courtroom_or_a_shared_watch_link() -> None:
    with static_server() as base, page(tour_seen=False) as (pg, _):
        pg.goto(f"{base}/index.html#watch=cookie-jar|aggressive|conservative")
        pg.wait_for_timeout(2000)
        assert not pg.evaluate(TOUR_OPEN)
