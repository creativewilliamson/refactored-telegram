"""F14: with JavaScript off, the state list leads to 56 pre-rendered pages."""
from __future__ import annotations

import os

import pytest

from .conftest import url

SHOTS = os.environ.get("EVIDENCE") == "1"


@pytest.fixture()
def nojs(browser):
    ctx = browser.new_context(java_script_enabled=False, viewport={"width": 375, "height": 1400})
    page = ctx.new_page()
    yield page
    ctx.close()


def test_f14_home_without_js(nojs):
    nojs.goto(url("/"))
    assert not nojs.is_visible("#search-form")          # search needs JS: hidden
    assert "Pick your state" in nojs.text_content("noscript")
    hrefs = nojs.eval_on_selector_all(".state-list a", "as => as.map(a => a.getAttribute('href'))")
    assert len(hrefs) == 56
    for h in hrefs:
        r = nojs.request.get(url(h))
        assert r.status == 200, h
        assert "<h1>Veterans Day offers in" in r.text()


@pytest.mark.parametrize("st,name", [("in", "Indiana"), ("gu", "Guam"), ("tx", "Texas")])
def test_f14_state_pages(nojs, st, name):
    nojs.goto(url("/"))
    nojs.click(f".state-list a[href='/state/{st}/']")
    nojs.wait_for_url(f"**/state/{st}/")
    assert nojs.text_content("h1") == f"Veterans Day offers in {name}"
    assert nojs.locator("#here-h").count() == 1           # national chains with stores here
    assert nojs.locator("#everywhere-h + p + ul li").count() >= 2
    assert nojs.locator("#other-h").count() == 1          # more national offers
    cities = nojs.eval_on_selector_all("#cities-h + ul a", "as => as.map(a => a.getAttribute('href'))")
    assert cities and all(c.startswith("/near/?city=") and f"st={st.upper()}" in c for c in cities)
    rows = nojs.locator(".offer-row").count()
    assert rows >= 100   # every national offer is listed somewhere on the page
    if st == "tx":
        assert nojs.locator("#local-h").count() == 1      # Texas-only offers (Pluckers, zoo...)
        assert "Pluckers" in nojs.text_content("#local-h + ul")
    if SHOTS:
        nojs.screenshot(path=f"evidence/F14-{st}.png")


def test_f14_56_state_pages_exist(page):
    from pathlib import Path
    dist = Path(__file__).resolve().parents[2] / "dist" / "state"
    assert len([p for p in dist.iterdir() if (p / "index.html").exists()]) == 56
