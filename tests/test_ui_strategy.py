"""'Which style wins?' on the home page: it follows the docket, shows all four styles, and never turns missing data into 0%."""

from __future__ import annotations

from tests.ui_support import page, static_server


def _open(pg, base):
    pg.goto(f"{base}/index.html")
    pg.wait_for_function("window.selectCase && document.querySelector('#strat-case option')")


def test_docket_choice_drives_which_style_wins_and_its_dropdown() -> None:  # 1a
    with static_server() as base, page() as (pg, errors):
        _open(pg, base)
        pg.evaluate("selectCase('aurora-defi')")
        assert pg.input_value("#strat-case") == "aurora-defi"
        assert pg.is_visible("#strat-flat")
        pg.evaluate("selectCase('broken-bike')")
        assert pg.input_value("#strat-case") == "broken-bike"
        assert not pg.is_visible("#strat-flat")  # this case is decided by the lawyers, so no "evidence decides" note
        # the section's own dropdown still works and is independent of scrolling
        pg.select_option("#strat-case", "kestrel-av")
        assert "kestrel" in pg.inner_text("#matrix").lower() or pg.locator("#matrix .cell").count() == 16
        assert errors == []


def test_all_four_styles_are_shown() -> None:  # 1b
    with static_server() as base, page() as (pg, _):
        _open(pg, base)
        pg.evaluate("selectCase('broken-bike')")
        assert pg.locator("#matrix .cell").count() == 16
        text = pg.inner_text("#matrix")
        for label in ("Bold", "Careful", "Smart", "Wild"):
            assert f"{label} Accuser" in text and f"{label} Defender" in text


def test_evidence_decided_case_says_so_in_plain_words_and_keeps_the_true_numbers() -> None:  # 1c
    with static_server() as base, page() as (pg, _):
        _open(pg, base)
        pg.evaluate("selectCase('aurora-defi')")
        note = pg.inner_text("#strat-flat")
        assert "The evidence decides this case: the Accuser wins 0% whatever either lawyer does" in note
        assert "Decided by the evidence" in pg.inner_text("#strat-rating")
        cells = pg.locator("#matrix .cell b").all_inner_texts()
        assert cells == ["0%"] * 16  # the true value, not hidden
        assert "pays: Acc" in pg.inner_text("#matrix")  # what still differs


def test_missing_cell_reads_no_data_never_zero() -> None:  # 1c
    with static_server() as base, page() as (pg, _):
        _open(pg, base)
        pg.evaluate(
            """() => {
              const g = window.COURTROOM_ANALYSIS.efficiency.cases['broken-bike'];
              g.accuser_win_rate[1][1] = null; delete g.accuser_win_rate[2][2]; g.A[0][0] = null;
              renderStrategy('broken-bike');
            }"""
        )
        cells = pg.locator("#matrix .cell b").all_inner_texts()
        assert cells[5] == "no data" and cells[10] == "no data"
        assert cells.count("no data") == 2
        assert "no data" in pg.locator("#matrix .cell small.pay").first.inner_text()
        assert not pg.is_visible("#strat-flat")  # missing data must not be passed off as a flat grid


def test_takeaway_names_the_certified_equilibrium_including_mixed_ones() -> None:  # 1d
    with static_server() as base, page() as (pg, _):
        _open(pg, base)
        pg.evaluate("selectCase('kestrel-av')")
        t = pg.inner_text("#takeaway")
        assert "mix" in t and "Accuser" in t and "Defender" in t and "%" in t
        pg.evaluate("selectCase('broken-bike')")
        n = pg.evaluate("COURTROOM_ANALYSIS.efficiency.cases['broken-bike'].efficiency.equilibria.length")
        assert n >= 2  # several equilibria: the takeaway must say how many, as the certified table has them
        assert f"{n} stable picks" in pg.inner_text("#takeaway")


def test_surprises_toggle_updates_which_style_wins_in_live_mode() -> None:  # stale-state rule
    from tests.ui_support import live_server

    with live_server() as base, page() as (pg, errors):
        pg.goto(f"{base}/index.html")
        pg.wait_for_selector("#live-surprises")
        pg.evaluate("selectCase('broken-bike')")
        before = pg.inner_text("#strat-src")
        assert "surprises" not in before
        grid_before = pg.locator("#matrix .cell b").all_inner_texts()
        pg.check("#live-surprises")
        after = pg.inner_text("#strat-src")
        assert "with courtroom surprises on" in after
        assert pg.locator("#matrix .cell").count() == 16
        assert errors == []
        assert grid_before != [] and pg.locator("#matrix .cell b").all_inner_texts() != []


def test_a_failing_trial_request_is_never_replaced_by_a_different_saved_trial() -> None:  # W2, W3
    from tests.ui_support import live_server

    with live_server() as base, page() as (pg, errors):
        pg.route("**/api/trial", lambda r: r.fulfill(status=500, body="boom"))
        pg.goto(f"{base}/index.html")
        pg.wait_for_selector("#live-seed")
        pg.evaluate("selectCase('cookie-jar')")
        pg.fill("#live-seed", "7")
        pg.dispatch_event("#live-seed", "change")
        pg.click("#start")
        pg.wait_for_function("document.querySelector('#combo-note').innerText.includes('did not answer')")
        assert "seed 7" in pg.inner_text("#combo-note")
        assert pg.evaluate("document.querySelector('#court').hidden")  # the asked-for trial could not be played, and nothing else was passed off
        pg.fill("#live-seed", "0")
        pg.dispatch_event("#live-seed", "change")
        pg.click("#start")
        pg.wait_for_selector("#live-badge .pill.edit")
        assert "SAVED TRIAL" in pg.inner_text("#live-badge")  # seed 0 may fall back to the saved seed-0 trial, but says so
        # W3: arrow keys on the music slider must not step the trial
        i = pg.evaluate("S.idx")
        pg.focus("#music-vol")
        pg.keyboard.press("ArrowRight")
        assert pg.evaluate("S.idx") == i
        assert errors == []


def test_no_horizontal_overflow_on_a_phone() -> None:  # W1
    with static_server() as base, page(base_viewport=(375, 812)) as (pg, _):
        for path, wait in (("index.html", "#strat-case option"), ("lab.html", ".chapter")):
            pg.goto(f"{base}/{path}")
            pg.wait_for_selector(wait, state="attached")
            if path == "index.html":
                pg.evaluate("selectCase('broken-bike')")
            pg.wait_for_timeout(800)
            assert pg.evaluate("document.documentElement.scrollWidth") <= 376, path
