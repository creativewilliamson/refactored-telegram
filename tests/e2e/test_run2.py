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


# ------------------------------------------- CSP: no inline script blocked
@pytest.mark.parametrize("path", ["/", "/near/46052", "/print/?zip=46052&r=25", "/state/in/", "/offer/hy-vee/"])
def test_no_csp_violations(page, path):
    """The inline scripts' hashes in _headers must match the pages (a stale
    hash silently blocks the results page's early data loading)."""
    msgs = []
    page.on("console", lambda m: msgs.append(m.text) if m.type == "error" else None)
    page.goto(url(path))
    page.wait_for_load_state("networkidle")
    assert not [m for m in msgs if "Content Security Policy" in m], msgs


# ------------------------------------------------------ F23 tap targets
TAP_PAGES = ["/", "/near/46052", "/state/dc/", "/state/in/", "/state/as/", "/state/hi/",
             "/offer/texas-roadhouse/", "/offer/aquarium-of-the-pacific/", "/offer/national-parks/",
             "/offer/110-grill/", "/print/?zip=46052&r=25", "/about/", "/no-such-page/"]

TAP_CHECK = """() => {
  const vis = el => { const s = getComputedStyle(el); const b = el.getBoundingClientRect();
    return s.visibility !== 'hidden' && s.display !== 'none' && b.width > 0 && b.height > 0 && !el.closest('.sr-only'); };
  const bad = [];
  document.querySelectorAll('a, button, input, select, summary').forEach(el => {
    if (!vis(el)) return;
    const b = el.getBoundingClientRect();
    if (b.height >= 47.5 && b.width >= 47.5) return;
    // WCAG 2.2 (2.5.8) inline exception: a link inside a sentence of text.
    const par = el.parentElement;
    const own = el.textContent.trim().length;
    const inSentence = el.tagName === 'A' && getComputedStyle(el).display === 'inline'
      && /^(P|LI|DD|SPAN)$/.test(par.tagName) && par.textContent.trim().length >= own + 15;
    if (!inSentence) bad.push(el.outerHTML.slice(0, 90) + ' ' + Math.round(b.width) + 'x' + Math.round(b.height));
  });
  return bad;
}"""


@pytest.mark.parametrize("path", TAP_PAGES)
def test_f23_tap_targets(page, path):
    page.set_viewport_size({"width": 375, "height": 800})
    page.goto(url(path))
    if path.startswith("/near/"):
        page.wait_for_selector("#cards > li")
        page.click("#filters summary")
    if path.startswith("/print/"):
        page.wait_for_selector("#print-list > li")
    assert page.evaluate(TAP_CHECK) == []


def test_f23_key_links_are_48px(page):
    page.set_viewport_size({"width": 375, "height": 800})
    page.goto(url("/offer/texas-roadhouse/"))
    assert page.locator("a.src-link").bounding_box()["height"] >= 48
    page.goto(url("/about/"))
    for name in ("Call 988, then press 1", "Text 838255"):
        assert page.locator("main").get_by_role("link", name=name).bounding_box()["height"] >= 48
    page.goto(url("/no-such-page/"))
    assert page.get_by_role("link", name="See every offer by state").bounding_box()["height"] >= 48


def test_f23_dc_washington_once(page):
    page.goto(url("/state/dc/"))
    cities = page.locator("#cities-h + .link-grid li a").all_inner_texts()
    assert [c.strip().lower() for c in cities].count("washington") == 1


# ------------------------------------------------------ F24 small messages
def test_f24_find_nearest_none_in_range_says_so(page):
    page.goto(url("/offer/hy-vee/"))
    page.fill("form[data-search] input[type=text]", "46052")
    page.locator("form[data-search] button[type=submit]").click()
    page.wait_for_selector("#cards-empty:not([hidden])")
    text = page.locator("#cards-empty").inner_text()
    assert text.startswith("The nearest Hy-Vee is more than 100 miles from Lebanon, IN 46052.")
    assert "Hy-Vee has stores in" in text and "Iowa" in text
    assert "chains listed below" not in text
    # Only Hy-Vee is missing; Lebanon has plenty of other stores.
    assert page.locator("#everywhere-note").inner_text() == "These offers don’t need a store near you."


def test_f24_no_mention_of_an_empty_chain_list(page):
    page.goto(url("/near/96799"))
    page.wait_for_selector("#cards-empty:not([hidden])")
    mentions = "chains listed below" in page.locator("#cards-empty").inner_text()
    assert mentions == (page.locator("#find-list li").count() > 0)


def test_f24_bad_share_link_is_not_the_last_search(page):
    page.goto(url("/near/46052"))
    page.wait_for_selector("#cards > li")
    page.goto(url("/near/abc"))
    page.wait_for_selector("#nq-msg:not([hidden])")
    assert "couldn’t find “abc”" in page.locator("#nq-msg").inner_text()
    assert page.locator("#results").is_hidden()
    page.goto(url("/near/"))                      # the real last search still comes back
    page.wait_for_selector("#cards > li")
    assert "46052" in page.locator("h1").inner_text()


@pytest.mark.parametrize("slug,roundup", [("110-grill", True), ("texas-roadhouse", True),
                                          ("applebee-s", False), ("national-parks", False)])
def test_f24_source_link_wording(page, slug, roundup):
    page.goto(url(f"/offer/{slug}/"))
    link = page.locator("a.src-link")
    text, host = link.inner_text(), link.get_attribute("href")
    if roundup:
        assert re.search(r"military\.com|news\.va\.gov|legion\.org", host)
        assert "opens the offer list where we found this" in text
    else:
        assert not re.search(r"military\.com|news\.va\.gov|legion\.org", host)
        assert text == "Offer details on the business's page"


def test_f24_card_notes_match_source(page):
    page.goto(url("/near/46052"))
    page.wait_for_selector("#cards > li")
    pairs = page.eval_on_selector_all(
        "#cards .links a, #everywhere-list a, #find-list a",
        "els => els.filter(a => a.querySelector('.sr-only') && /opens/.test(a.textContent))"
        ".map(a => [a.hostname, a.querySelector('.sr-only').textContent])")
    assert pairs
    for host, note in pairs:
        roundup = bool(re.search(r"military\.com|news\.va\.gov|legion\.org", host))
        assert ("offer list where we found this" in note) == roundup, (host, note)
        assert ("business’s page" in note) == (not roundup), (host, note)


# ------------------------------ evaluator round 1 (run 2), W1: no invented distance
@pytest.mark.parametrize("slug,zip_", [("mission-bbq", "21061"), ("eureka", "93710"),
                                       ("chicken-salad-chick", "36830"), ("veterans-canteen-service", "46202")])
def test_w1_no_store_list_claims_no_distance(page, slug, zip_):
    page.goto(url(f"/offer/{slug}/"))
    page.fill("form[data-search] input[type=text]", zip_)
    page.locator("form[data-search] button[type=submit]").click()
    page.wait_for_selector("#cards-empty:not([hidden])")
    body = page.locator("#results").inner_text()
    assert "is more than" not in body and "No stores with offers within" not in body
    assert page.locator("#summary").inner_text().startswith("We don’t have a store list for ")
    assert page.locator("#widen-note").is_hidden()
    assert page.locator("#radius").input_value() == "25"
    assert "google.com/maps/search" in page.locator("#cards-empty a").get_attribute("href")
    assert "No offers here match your filters" not in page.locator("#everywhere-list").inner_text()


def test_w1_every_unlisted_chain(page):
    """All "find" offers (no store list) from one ZIP: never a distance claim."""
    offers = page.request.get(url("/data/offers.json")).json()["offers"]
    finds = [o for o in offers if o["kind"] == "find"]
    assert len(finds) >= 40
    page.goto(url("/near/46052"))                 # warm the same ZIP once
    page.wait_for_selector("#cards > li")
    for o in finds:
        page.goto(url(f"/offer/{o['id']}/"))
        page.fill("form[data-search] input[type=text]", "46052")
        page.locator("form[data-search] button[type=submit]").click()
        page.wait_for_selector("#cards-empty:not([hidden])")
        assert "is more than" not in page.locator("#results").inner_text(), o["id"]
        assert page.locator("#summary").inner_text().startswith("We don’t have a store list"), o["id"]
