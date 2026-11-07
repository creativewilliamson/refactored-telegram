"""Browser tests for run 2 features (F20-F27)."""
from __future__ import annotations

import re

import pytest

from .conftest import url

OLD_NAME = re.compile(r"vets\s*eat\s*free", re.I)
SITE = "https://vetdaydeals.pages.dev"

RENAME_PAGES = ["/", "/near/46052", "/state/in/", "/offer/texas-roadhouse/",
                "/print/?zip=46052&r=25", "/about/", "/no-such-page/"]


# ---------------------------------------------------------------- F26 rename
@pytest.mark.parametrize("path", RENAME_PAGES)
def test_f26_name_on_every_page(page, path):
    page.goto(url(path))
    page.wait_for_load_state("networkidle")
    assert page.locator(".site-header .brand").inner_text().strip() == "Vet Day Deals"
    assert "Vet Day Deals" in page.title()
    html = page.content()
    assert not OLD_NAME.search(html)
    assert page.locator('meta[property="og:site_name"]').get_attribute("content") == "Vet Day Deals"
    assert page.locator('link[rel="canonical"]').get_attribute("href").startswith(SITE + "/")
    assert page.locator('meta[property="og:url"]').get_attribute("content").startswith(SITE + "/")
    assert page.locator('meta[property="og:image"]').get_attribute("content") == SITE + "/og.png"


def test_f26_assets_and_sitemap_use_new_name(page):
    page.goto(url("/"))
    assets = page.eval_on_selector_all(
        "script[src], link[rel=stylesheet]", "els => els.map(e => e.src || e.href)")
    for extra in ("/sw.js", "/sitemap.xml", "/robots.txt", "/about/"):
        assets.append(url(extra))
    for a in assets:
        body = page.request.get(a).text()
        assert not OLD_NAME.search(body), a
    sitemap = page.request.get(url("/sitemap.xml")).text()
    locs = re.findall(r"<loc>([^<]+)</loc>", sitemap)
    assert locs and all(u.startswith(SITE + "/") for u in locs)
