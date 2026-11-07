"""F16: share links reopen a search; a reload brings the last search back,
even with no connection."""
from __future__ import annotations

import os

from .conftest import search_from_home, url

SHOTS = os.environ.get("EVIDENCE") == "1"


def test_f16_zip_link(page):
    page.goto(url("/near/46052"))
    page.wait_for_selector("#cards > li")
    assert page.text_content("#results-h") == "Offers near Lebanon, IN 46052"
    if SHOTS:
        page.screenshot(path="evidence/F16-zip-link.png")


def test_f16_city_link(page):
    page.goto(url("/near/?city=lebanon&st=IN"))
    page.wait_for_selector("#cards > li")
    assert page.text_content("#results-h") == "Offers near Lebanon, IN"
    if SHOTS:
        page.screenshot(path="evidence/F16-city-link.png")


def test_f16_share_button_builds_link(context, page):
    context.grant_permissions(["clipboard-read", "clipboard-write"])
    search_from_home(page, "Lebanon, IN")
    page.wait_for_selector("#cards > li")
    page.evaluate("() => { navigator.share = undefined; }")
    page.click("#share")
    page.wait_for_selector("#share-msg:not([hidden])")
    assert page.text_content("#share-msg").endswith("/near/?city=lebanon&st=IN")


def test_f16_reload_brings_search_back(page):
    search_from_home(page, "46052")
    page.wait_for_selector("#cards > li")
    assert page.url.endswith("/near/")          # the ZIP is not in the address bar
    page.reload()
    page.wait_for_selector("#cards > li")
    assert page.text_content("#results-h") == "Offers near Lebanon, IN 46052"


def test_f16_reload_with_no_connection(context, page):
    search_from_home(page, "46052")
    page.wait_for_selector("#cards > li")
    # Let the offline helper (service worker) finish storing the pages.
    page.wait_for_function("() => navigator.serviceWorker && navigator.serviceWorker.controller !== null",
                           timeout=15000)
    page.reload()
    page.wait_for_selector("#cards > li")
    context.set_offline(True)
    try:
        page.reload()
        page.wait_for_selector("#cards > li", timeout=15000)
        assert page.text_content("#results-h") == "Offers near Lebanon, IN 46052"
        assert page.locator("#cards > li").count() == 50
        if SHOTS:
            page.screenshot(path="evidence/F16-offline-reload.png")
    finally:
        context.set_offline(False)
