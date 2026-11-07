"""F19: offer pages, sitemap.xml, robots.txt, Open Graph tags, OG image."""
from __future__ import annotations

import os
import re
import struct

from .conftest import url

SHOTS = os.environ.get("EVIDENCE") == "1"


def offers(page):
    return page.request.get(url("/data/offers.json")).json()["offers"]


def test_f19_texas_roadhouse_page(page):
    o = next(x for x in offers(page) if x["id"] == "texas-roadhouse")
    page.set_viewport_size({"width": 375, "height": 1500})
    page.goto(url("/offer/texas-roadhouse/"))
    assert page.text_content("h1") == "Texas Roadhouse"
    facts = page.text_content(".facts")
    assert "Who qualifies" in facts and o["elig"] in facts
    assert "Rules" in facts and "11 a.m." in facts
    assert "May 31, 2027" in page.text_content("main")
    assert page.get_attribute(".facts a[href^='http']", "href") == o["src"]
    assert page.text_content("#find-h") == "Find the nearest Texas Roadhouse"
    if SHOTS:
        page.screenshot(path="evidence/F19-texas-roadhouse.png")


def test_f19_find_nearest_from_offer_page(page):
    page.goto(url("/offer/texas-roadhouse/"))
    page.fill("#of-q", "46052")
    page.click("form[data-search] button[type=submit]")
    page.wait_for_url("**/near/")
    page.wait_for_selector("#cards > li")
    names = set(page.eval_on_selector_all("#cards h3", "h => h.map(x => x.textContent)"))
    assert names == {"Texas Roadhouse"}
    assert "Showing only Texas Roadhouse" in page.text_content("#offer-filter-note")
    if SHOTS:
        page.screenshot(path="evidence/F19-find-nearest.png")
    page.click("#all-offers")
    assert len(set(page.eval_on_selector_all("#cards h3", "h => h.map(x => x.textContent)"))) > 5


def test_f19_national_parks_page(page):
    page.set_viewport_size({"width": 375, "height": 1500})
    page.goto(url("/offer/national-parks/"))
    assert page.text_content("h1") == "National Parks"
    assert "Good anywhere in the U.S." in page.text_content(".facts")
    assert "Everyone" in page.text_content(".facts")
    href = page.get_attribute("#find-h ~ p a.btn", "href")
    assert href.startswith("https://www.google.com/maps/search/") and "national%20park" in href
    if SHOTS:
        page.screenshot(path="evidence/F19-national-parks.png")


def test_f19_every_offer_has_a_page(page):
    for o in offers(page):
        r = page.request.get(url(f"/offer/{o['id']}/"))
        assert r.status == 200, o["id"]
        assert f"<h1>{o['name'].replace('&', '&amp;')}" in r.text().replace("&#39;", "'"), o["id"]


def test_f19_sitemap_and_robots(page):
    sm = page.request.get(url("/sitemap.xml"))
    assert sm.status == 200
    locs = re.findall(r"<loc>([^<]+)</loc>", sm.text())
    assert len(locs) == 2 + 56 + 130
    assert all(u.startswith("https://vetdaydeals.pages.dev/") for u in locs)
    assert "https://vetdaydeals.pages.dev/offer/texas-roadhouse/" in locs
    robots = page.request.get(url("/robots.txt")).text()
    assert "Sitemap: https://vetdaydeals.pages.dev/sitemap.xml" in robots


def test_f19_open_graph(page):
    page.goto(url("/"))
    og = page.eval_on_selector_all("meta[property^='og:']", "m => Object.fromEntries(m.map(x => [x.getAttribute('property'), x.content]))")
    for key in ("og:title", "og:description", "og:image", "og:url", "og:type"):
        assert og.get(key), key
    assert og["og:image"] == "https://vetdaydeals.pages.dev/og.png"
    img = page.request.get(url("/og.png"))
    assert img.headers["content-type"] == "image/png"
    w, h = struct.unpack(">II", img.body()[16:24])
    assert (w, h) == (1200, 630)


def test_f19_find_nearest_widens_for_that_chain(page):
    # A "find the nearest X" search widens until it finds at least one X
    # (the general rule, fewer than 10 places, counts every chain).
    page.goto(url("/offer/hy-vee/"))
    page.fill("#of-q", "61701")            # Bloomington, IL has a Hy-Vee
    page.click("form[data-search] button[type=submit]")
    page.wait_for_selector("#cards > li")
    assert set(page.eval_on_selector_all("#cards h3", "h => h.map(x => x.textContent)")) == {"Hy-Vee"}
