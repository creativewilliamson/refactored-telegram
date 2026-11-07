"""F11: offer timing follows the visitor's own time zone.

Clock set to Nov 9, 11, 12 and Dec 1 (noon local) in New York and Hawaii,
plus one instant that is already Nov 12 in New York but still Nov 11 in
Hawaii. Screenshots go to evidence/ when EVIDENCE=1.
"""
from __future__ import annotations

import datetime as dt
import os
from zoneinfo import ZoneInfo

import pytest

from .conftest import url

ZONES = {"new_york": "America/New_York", "hawaii": "Pacific/Honolulu"}
DAYS = {"nov09": (2026, 11, 9), "nov11": (2026, 11, 11), "nov12": (2026, 11, 12), "dec01": (2026, 12, 1)}
SHOTS = os.environ.get("EVIDENCE") == "1"


def open_at(browser, tz: str, instant: dt.datetime):
    ctx = browser.new_context(viewport={"width": 375, "height": 1300}, timezone_id=tz)
    page = ctx.new_page()
    page.clock.install(time=instant)
    page.clock.pause_at(instant)
    page.goto(url("/near/46052"))
    page.wait_for_selector("#cards > li")
    return ctx, page


def card_states(page):
    return page.eval_on_selector_all("#cards > li", """lis => lis.map(li => ({
      name: li.querySelector('h3').textContent,
      ended: li.classList.contains('is-ended'),
      chips: [...li.querySelectorAll('.chips .chip')].map(c => c.textContent)
    }))""")


def chip_for(cards, name):
    for c in cards:
        if c["name"] == name:
            return c["chips"]
    return None


@pytest.mark.parametrize("zone", list(ZONES))
@pytest.mark.parametrize("day", list(DAYS))
def test_f11_labels(browser, zone, day):
    tz = ZONES[zone]
    y, m, d = DAYS[day]
    instant = dt.datetime(y, m, d, 12, 0, tzinfo=ZoneInfo(tz))
    ctx, page = open_at(browser, tz, instant)
    try:
        cards = card_states(page)
        # Show every card so Denny's / Texas Roadhouse are on the page.
        while page.is_visible("#more"):
            page.click("#more")
        cards = card_states(page)
        flat = [ch for c in cards for ch in c["chips"]]
        denny = chip_for(cards, "Denny's")
        texas = chip_for(cards, "Texas Roadhouse")
        assert denny and "5 a.m.–noon" in denny
        assert texas and any("May 31, 2027" in ch for ch in texas)
        if day == "nov09":
            assert "Starts Wed, Nov 11" in flat
            assert "Starts Tue, Nov 10" in flat          # Kohl's, Outback (Nov 10-11)
            assert any(ch.startswith("Today, through") for ch in flat)  # Benihana/STK/Eat'n Park
        if day == "nov11":
            assert "Today" in flat
            assert "Starts Wed, Nov 11" not in flat
            # Only McCormick & Schmick's (Sunday, Nov 8 only) has ended by Nov 11.
            ended = {c["name"] for c in cards if "Ended" in c["chips"]}
            assert ended <= {"McCormick & Schmick's"}, ended
        if day == "nov12":
            assert "Ended" in flat
            assert "Voucher good until May 31, 2027" in texas
        if day == "dec01":
            assert "Ended" in flat
            assert "Voucher good until May 31, 2027" in texas
            assert "Today" not in flat
        # Cards whose offers have all ended sit below every live card.
        flags = [c["ended"] for c in cards]
        assert flags == sorted(flags), "an ended card appears above a live one"
        if SHOTS and zone == "new_york" and day == "nov09":
            for name, fname in (("Denny's", "dennys"), ("Texas Roadhouse", "texas-roadhouse")):
                page.locator("#cards > li", has=page.locator("h3", has_text=name)).first.screenshot(
                    path=f"evidence/F11-{fname}.png")
        if SHOTS and zone == "new_york":
            page.set_viewport_size({"width": 375, "height": 1300})
            page.evaluate("window.scrollTo(0, document.getElementById('cards-h').offsetTop - 10)")
            page.screenshot(path=f"evidence/F11-{day}-{zone}.png")
    finally:
        ctx.close()


def test_f11_same_instant_differs_by_zone(browser):
    """03:00 Nov 12 in New York is 22:00 Nov 11 in Honolulu."""
    instant = dt.datetime(2026, 11, 12, 8, 0, tzinfo=dt.timezone.utc)
    states = {}
    for zone, tz in ZONES.items():
        ctx, page = open_at(browser, tz, instant)
        try:
            states[zone] = chip_for(card_states(page), "Starbucks")
            if SHOTS:
                page.evaluate("window.scrollTo(0, document.getElementById('cards-h').offsetTop - 10)")
                page.screenshot(path=f"evidence/F11-same-instant-{zone}.png")
        finally:
            ctx.close()
    assert "Ended" in states["new_york"]
    assert "Today" in states["hawaii"]
