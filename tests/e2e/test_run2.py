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


# ------------------------------------------------------------ F27 New search
NEW_SEARCH_PAGES = ["/near/46052", "/offer/texas-roadhouse/", "/state/in/",
                    "/print/?zip=46052&r=25", "/about/", "/no-such-page/"]


def _home_focused(page):
    page.wait_for_url(url("/"))
    page.wait_for_selector("#q:focus")  # (not wait_for_function: the site's CSP blocks eval)
    assert page.evaluate("window.scrollY") == 0


def test_f27_not_on_home(page):
    page.goto(url("/"))
    assert page.locator(".new-search").count() == 0


@pytest.mark.parametrize("path", NEW_SEARCH_PAGES)
def test_f27_top_button_by_keyboard(page, path):
    page.goto(url(path))
    page.wait_for_load_state("networkidle")
    btn = page.locator(".new-search-top a.new-search")
    assert btn.inner_text().strip() == "New search"
    assert btn.bounding_box()["height"] >= 48
    if path.startswith("/near/"):
        # Results move focus to their heading (for screen readers); the
        # button sits just above it, one Shift+Tab back.
        page.wait_for_selector("#cards li")
        page.wait_for_selector("#results-h:focus")
        page.keyboard.press("Shift+Tab")
    else:
        for _ in range(3):  # skip link, site name, New search
            page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.classList.contains('new-search')")
    with page.expect_navigation():
        page.keyboard.press("Enter")
    _home_focused(page)


def test_f27_results_top_and_bottom(browser):
    # A fresh context: no history, as if the link came from Facebook or a text.
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    p = ctx.new_page()
    try:
        p.goto(url("/near/46052"))
        p.wait_for_selector("#cards li")
        top = p.locator(".new-search-top a")
        top_box = top.bounding_box()
        assert top_box["y"] + top_box["height"] <= p.locator("#results-h").bounding_box()["y"]
        assert p.evaluate("""() => {
            const more = document.getElementById('more');
            const b = document.querySelector('.new-search-bottom');
            return !!(more.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
        }""")
        bottom = p.locator(".new-search-bottom a")
        bottom.scroll_into_view_if_needed()
        assert bottom.is_visible() and bottom.bounding_box()["height"] >= 48
        bottom.click()
        _home_focused(p)
        p.goto(url("/near/46052"))
        p.wait_for_selector("#cards li")
        p.locator(".new-search-top a").click()
        _home_focused(p)
    finally:
        ctx.close()


def test_f27_hidden_when_printed(page):
    page.goto(url("/print/?zip=46052&r=25"))
    page.wait_for_load_state("networkidle")
    assert page.locator(".new-search-top a").is_visible()
    page.emulate_media(media="print")
    assert not page.locator(".new-search-top a").is_visible()


# ------------------------------------------------------------- F21 counts
@pytest.mark.parametrize("path,text", [
    ("/state/vi/", "1 store location with Veterans Day offers"),
    ("/state/as/", "0 store locations with Veterans Day offers"),
    ("/state/in/", "store locations with Veterans Day offers"),
])
def test_f21_state_counts(page, path, text):
    page.goto(url(path))
    assert text in page.locator("p.lead").first.inner_text()


@pytest.mark.parametrize("query,expect", [
    ("zip=00802&r=10", re.compile(r"^1 place within 10 miles")),
    ("zip=46052&r=10", re.compile(r"^\d+ places within 10 miles")),
    ("zip=96799&r=100", re.compile(r"^No places within 100 miles")),
])
def test_f21_print_counts(page, query, expect):
    page.goto(url("/print/?" + query))
    page.wait_for_selector("#print-sub:not(:empty)")
    assert expect.search(page.locator("#print-sub").inner_text())


def test_f21_no_bad_plurals_in_pages(page):
    for path in ("/state/vi/", "/state/as/", "/about/", "/offer/hy-vee/", "/state/dc/"):
        page.goto(url(path))
        text = page.locator("main").inner_text()
        assert not re.search(r"\b1 (store locations|stores|places|offers|chains)\b", text), path
        many = r"\b(?:0|[2-9]|[1-9][\d,]+) "
        assert not re.search(many + r"(?:store location|place|offer|chain)(?![s\w])", text), path
        assert not re.search(many + r"store(?![s\w]| location)", text), path


# ------------------------------------------------- F22 print page widening
def _print_read(page):
    page.wait_for_selector("#print-sub:not(:empty)")
    w = page.locator("#print-widen")
    return page.locator("#print-sub").inner_text(), (w.inner_text() if w.is_visible() else "")


@pytest.mark.parametrize("zip_", ["00802", "96910"])
def test_f22_print_widens_when_few_places(page, zip_):
    page.goto(url(f"/print/?zip={zip_}&r=25"))
    sub, note = _print_read(page)
    assert "within 100 miles" in sub
    assert note.startswith("Showing up to 100 miles because few places are close by.")
    assert page.locator("#print-list > li").count() >= 1


@pytest.mark.parametrize("query,miles", [("zip=46052&r=25", 25), ("zip=00802&r=10", 10),
                                         ("zip=00802&r=25&fixed=1", 25)])
def test_f22_print_keeps_radius(page, query, miles):
    page.goto(url("/print/?" + query))
    sub, note = _print_read(page)
    assert f"within {miles} miles" in sub
    assert "Showing up to" not in note


def test_f22_results_to_print_and_back(page):
    page.goto(url("/near/00802"))
    page.wait_for_selector("#cards li")
    assert "w=1" in page.locator("#print-link").get_attribute("href")
    page.click("#print-link")
    sub, note = _print_read(page)
    assert "within 100 miles" in sub and note.startswith("Showing up to 100 miles")
    back = page.locator(".print-actions .back-link")
    assert back.bounding_box()["height"] >= 48
    back.click()
    page.wait_for_selector("#cards li")
