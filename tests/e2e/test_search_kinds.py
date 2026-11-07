"""F12: search by City, ST, by state name, and by "Use my location"."""
from __future__ import annotations

import os

import pytest

from .conftest import search_from_home, url

SHOTS = os.environ.get("EVIDENCE") == "1"


@pytest.mark.parametrize("q,expect", [
    ("Lebanon, IN", "Offers near Lebanon, IN"),
    ("San Juan, PR", "Offers near San Juan, PR"),
    ("Fairbanks, AK", "Offers near Fairbanks, AK"),
    ("lebanon in", "Offers near Lebanon, IN"),
    ("Hagåtña, GU", "Offers near Hagatna, GU"),
    ("St. Thomas, VI", "Offers near St Thomas, VI"),
])
def test_f12_city_state(page, q, expect):
    search_from_home(page, q)
    page.wait_for_selector("#cards > li")
    assert page.text_content("#results-h").startswith(expect)
    assert page.locator("#cards > li").count() > 0
    if SHOTS and q in ("Lebanon, IN", "San Juan, PR", "Fairbanks, AK"):
        page.screenshot(path=f"evidence/F12-{q.split(',')[0].lower().replace(' ', '-')}.png")


@pytest.mark.parametrize("q,path", [("Indiana", "/state/in/"), ("IN", "/state/in/"),
                                    ("Puerto Rico", "/state/pr/"), ("new york", "/state/ny/")])
def test_f12_state_name_goes_to_state_page(page, q, path):
    page.goto(url("/"))
    page.fill("#q", q)
    page.click("button:has-text('Find offers')")
    page.wait_for_url("**" + path)
    assert page.text_content("h1").startswith("Veterans Day offers in")


def test_f12_use_my_location(context, page):
    asked = []
    page.on("dialog", lambda d: asked.append(d))
    context.grant_permissions(["geolocation"])
    context.set_geolocation({"latitude": 61.2176, "longitude": -149.8997})  # Anchorage
    page.goto(url("/"))
    # Nothing asks for location before the tap.
    assert page.evaluate("typeof window.__locAsked") == "undefined"
    page.click("[data-locate]")
    page.wait_for_function("() => /your location/.test(document.getElementById('results-h').textContent)")
    page.wait_for_selector("#cards > li")
    first = page.locator("#cards > li").first.locator(".addr").text_content()
    assert "AK" in first
    if SHOTS:
        page.screenshot(path="evidence/F12-location.png")


def test_f12_location_only_asked_on_tap(browser):
    """The page must not call geolocation until the button is tapped."""
    ctx = browser.new_context()
    page = ctx.new_page()
    page.add_init_script("""
      window.__geoCalls = 0;
      const real = navigator.geolocation.getCurrentPosition.bind(navigator.geolocation);
      navigator.geolocation.getCurrentPosition = function () { window.__geoCalls++; return real.apply(null, arguments); };
    """)
    for path in ("/", "/near/", "/state/in/", "/offer/starbucks/"):
        page.goto(url(path))
        page.wait_for_load_state("networkidle")
        assert page.evaluate("window.__geoCalls") == 0, path
    ctx.close()
