"""F17: plain messages with a way forward for unknown ZIP, denied location,
offline, and a tile that fails to load."""
from __future__ import annotations

import os

from .conftest import search_from_home, url, wait_results

SHOTS = os.environ.get("EVIDENCE") == "1"


def test_f17_unknown_zip(page):
    search_from_home(page, "00000")
    page.wait_for_selector("#nq-msg:not([hidden])")
    msg = page.text_content("#nq-msg")
    assert "couldn’t find ZIP code 00000" in msg and "Lebanon, IN" in msg
    assert page.evaluate("document.activeElement.id") == "nq"   # ready to type again
    if SHOTS:
        page.screenshot(path="evidence/F17-unknown-zip.png")


def test_f17_misspelled_city_suggests(page):
    search_from_home(page, "Lebnon, IN")
    page.wait_for_selector("#nq-msg:not([hidden])")
    assert "Did you mean" in page.text_content("#nq-msg")
    page.click("[data-suggest='Lebanon, IN']")
    page.wait_for_selector("#cards > li")
    assert page.text_content("#results-h") == "Offers near Lebanon, IN"


def test_f17_military_mail_zip(page):
    search_from_home(page, "09001")
    page.wait_for_selector("#nq-msg:not([hidden])")
    assert "military mail" in page.text_content("#nq-msg")


def test_f17_location_denied(browser):
    ctx = browser.new_context(viewport={"width": 375, "height": 812})  # no geolocation permission
    page = ctx.new_page()
    page.goto(url("/"))
    page.click("[data-locate]")
    page.wait_for_selector("#nq-msg:not([hidden])", timeout=20000)
    msg = page.text_content("#nq-msg")
    assert "didn’t share your location" in msg and "type your ZIP code" in msg
    assert page.evaluate("document.activeElement.id") == "nq"
    if SHOTS:
        page.screenshot(path="evidence/F17-location-denied.png")
    ctx.close()


def test_f17_offline_then_retry(browser):
    ctx = browser.new_context(viewport={"width": 375, "height": 812}, service_workers="block")
    page = ctx.new_page()
    page.goto(url("/near/"))
    ctx.set_offline(True)
    page.fill("#nq", "46052")
    page.click("#near-form button[type=submit]")
    page.wait_for_selector("#nq-msg:not([hidden])")
    msg = page.text_content("#nq-msg")
    assert "offline" in msg and "Try again" in msg
    if SHOTS:
        page.screenshot(path="evidence/F17-offline.png")
    ctx.set_offline(False)
    page.click("#retry-search")
    page.wait_for_selector("#cards > li")
    ctx.close()


def test_f17_one_tile_fails_rest_still_works(browser):
    ctx = browser.new_context(viewport={"width": 375, "height": 1000}, service_workers="block")
    page = ctx.new_page()
    blocked = []

    def block(route):
        blocked.append(route.request.url)
        route.abort()

    page.route("**/data/tiles/80_-173.json", block)     # the tile with Lebanon itself
    page.goto(url("/near/46052"))
    wait_results(page)
    page.wait_for_selector("#cards > li")
    assert blocked
    note = page.text_content("#cards-empty")
    assert "didn’t load" in note and "Try again" in note
    assert page.locator("#cards > li").count() > 0       # stores from the other tiles still show
    if SHOTS:
        page.screenshot(path="evidence/F17-tile-failed.png")
    page.unroute("**/data/tiles/80_-173.json")
    page.click("#retry-tiles")
    page.wait_for_function("() => document.getElementById('cards-empty').hidden")
    assert page.text_content("#summary").startswith("353 stores")
    ctx.close()
