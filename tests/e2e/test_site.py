"""Browser tests for the core flows, one block per feature in FEATURES.json.

Run: docker compose --profile test run --rm e2e
"""
from __future__ import annotations

import re

import pytest

from .conftest import search_from_home, url, wait_results

TEST_ZIPS = ["46052", "10001", "78205", "20001", "59301", "87301", "04401", "82001",
             "99701", "96813", "00901", "96910", "00802"]


# ---- F01 home -----------------------------------------------------------------
def test_f01_home_first_screen(page):
    page.goto(url("/"))
    assert "Free meals and deals" in page.text_content(".lead")
    for sel in ("#q", "button:has-text('Find offers')", "[data-locate]"):
        box = page.locator(sel).bounding_box()
        assert box and box["y"] + box["height"] < 812, sel
    links = page.eval_on_selector_all(".state-list a", "as => as.map(a => a.getAttribute('href'))")
    assert len(links) == 56 and all(re.fullmatch(r"/state/[a-z]{2}/", h) for h in links)
    before = page.text_content("#before-h + ul")
    assert "proof of service" in before and "Call ahead" in before


# ---- F02 results ----------------------------------------------------------------
def test_f02_zip_results_cards(page):
    search_from_home(page, "46052")
    page.wait_for_selector("#cards > li")
    cards = page.eval_on_selector_all("#cards > li", """lis => lis.map(li => ({
        miles: parseFloat(li.querySelector('.miles').textContent),
        ok: !!(li.querySelector('h3') && li.querySelector('.offer-text') && li.querySelector('.chips .chip')
              && li.querySelector('.addr') && (li.querySelector('a[href^="tel:"]') || li.querySelector('.no-phone'))
              && li.querySelector('a[href^="https://www.google.com/maps/dir/"]')
              && li.querySelector('a[href^="https://maps.apple.com/"]') && li.querySelector('.links a[href^="http"]'))
    }))""")
    assert len(cards) == 50
    assert all(c["ok"] for c in cards)
    assert [c["miles"] for c in cards] == sorted(c["miles"] for c in cards)
    assert page.is_visible("#more")
    page.click("#more")
    assert page.locator("#cards > li").count() == 100


def test_f02_stacked_offers_on_one_card(page):
    page.goto(url("/near/50309"))
    page.wait_for_selector("#cards > li")
    hy = page.locator("#cards > li", has=page.locator("h3", has_text="Hy-Vee")).first
    assert hy.locator(".card-offer").count() == 2


# ---- F03 sources -----------------------------------------------------------------
def test_f03_offer_details_go_to_source(page):
    page.goto(url("/near/10001"))
    page.wait_for_selector("#cards > li")
    data = page.request.get(url("/data/offers.json")).json()
    by_text = {o["offer"]: o["src"] for o in data["offers"]}
    for i in range(3):
        card = page.locator("#cards > li").nth(i)
        text = card.locator(".offer-text").first.text_content().strip()
        assert card.locator(".links a").first.get_attribute("href") == by_text[text]
    assert page.locator("#find-list a.btn[href^='https://www.google.com/maps/search/']").count() > 20


# ---- F04 everywhere + places ----------------------------------------------------
def test_f04_everywhere_and_special_places(page):
    page.goto(url("/near/23185"))
    page.wait_for_selector("#far-cards > li")
    names = " ".join(page.eval_on_selector_all("#far-cards h3", "h => h.map(x => x.textContent)"))
    assert "Colonial Williamsburg" in names and "Yorktown" in names
    assert page.locator("#far-cards .miles").count() >= 3
    assert "National Parks" in page.text_content("#everywhere-list")


# ---- F05 radius --------------------------------------------------------------------
def test_f05_radius_changes_count(page):
    page.goto(url("/near/46052"))
    page.wait_for_selector("#cards > li")
    counts = {}
    for r in ("10", "25", "50", "100"):
        page.select_option("#radius", r)
        page.wait_for_function(f"() => document.getElementById('summary').textContent.includes('within {r} miles')")
        counts[r] = int(page.text_content("#summary").split()[0])
    assert counts["10"] < counts["25"] < counts["50"] < counts["100"]


def test_f05_auto_widen_miles_city(page):
    page.goto(url("/near/59301"))
    wait_results(page)
    assert "Showing up to 100 miles because few places are close by." in page.text_content("#widen-note")


# ---- F06 test ZIPs -----------------------------------------------------------------
@pytest.mark.parametrize("z", TEST_ZIPS)
def test_f06_test_zip(page, z):
    page.goto(url(f"/near/{z}"))
    wait_results(page)
    assert not page.is_visible("#nq-msg")
    assert page.locator("#everywhere-list li").count() >= 2
    n = page.locator("#cards > li").count()
    assert n > 0 or page.is_visible("#cards-empty")


# ---- F07 privacy -------------------------------------------------------------------
def test_f07_nothing_leaves_the_browser(context, page):
    log = []
    page.on("request", lambda r: log.append((r.method, r.url, r.post_data or "")))
    search_from_home(page, "46052")
    page.wait_for_selector("#cards > li")
    search_from_home(page, "Lebanon, IN")
    page.wait_for_function("() => /Lebanon, IN/.test(document.getElementById('results-h').textContent)")
    context.grant_permissions(["geolocation"])
    context.set_geolocation({"latitude": 40.0449, "longitude": -86.4641})
    page.goto(url("/"))
    page.click("[data-locate]")
    page.wait_for_function("() => /your location/.test(document.getElementById('results-h').textContent)")
    page.wait_for_selector("#cards > li")
    secrets = ["46052", "lebanon", "Lebanon", "40.04", "-86.46"]
    for method, u, body in log:
        assert method == "GET"
        assert u.startswith(url("/")), u
        assert not any(s in u or s in body for s in secrets), u
    assert context.cookies() == []


# ---- F08 footer + about -----------------------------------------------------------
@pytest.mark.parametrize("path", ["/", "/near/46052", "/state/in/", "/print/?zip=46052&r=25", "/about/"])
def test_f08_footer(page, path):
    page.goto(url(path))
    footer = page.text_content(".site-footer")
    assert "Call 988, press 1" in footer and "Text 838255" in footer
    assert "not affiliated with any business listed" in footer
    assert page.locator(".site-footer a[href='/about/']").count() == 1


def test_f08_about(page):
    page.goto(url("/about/"))
    text = page.text_content("main")
    assert re.search(r"last checked on\s+November 6, 2026", text)
    assert "stay on your phone" in text and "All The Places" in text


# ---- F10 accessibility ---------------------------------------------------------------
A11Y_PAGES = ["/", "/near/46052", "/state/in/", "/offer/texas-roadhouse/", "/print/?zip=46052&r=25", "/about/"]
SIZE_PAGES = A11Y_PAGES + ["/state/hi/", "/state/mi/", "/state/de/", "/state/tx/", "/404.html"]


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("path", A11Y_PAGES)
def test_f10_axe(page, axe_source, path, scheme):
    page.emulate_media(color_scheme=scheme)
    page.goto(url(path))
    if path.startswith("/near/"):
        page.wait_for_selector("#cards > li")
        page.click("#filters summary")
    if path.startswith("/print/"):
        page.wait_for_selector("#print-list > li")
    page.evaluate(axe_source)
    violations = page.evaluate("""async () => (await axe.run(document, {runOnly: {type: 'tag',
        values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa','best-practice']}})).violations
        .map(v => v.id + ' x' + v.nodes.length)""")
    assert violations == []


@pytest.mark.parametrize("width", [375, 640])
@pytest.mark.parametrize("path", SIZE_PAGES)
def test_f10_sizes(page, path, width):
    page.set_viewport_size({"width": width, "height": 800})
    page.goto(url(path))
    if path.startswith("/near/"):
        page.wait_for_selector("#cards > li")
        page.click("#filters summary")
    res = page.evaluate("""() => {
      const vis = el => { const s = getComputedStyle(el); const b = el.getBoundingClientRect();
        return s.visibility !== 'hidden' && s.display !== 'none' && b.width > 0 && b.height > 0 && !el.closest('.sr-only'); };
      let minFont = 99;
      document.querySelectorAll('body *').forEach(el => { if (vis(el) && [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()))
        minFont = Math.min(minFont, parseFloat(getComputedStyle(el).fontSize)); });
      const small = [];
      document.querySelectorAll('a, button, input, select, summary').forEach(el => {
        if (!vis(el)) return; const b = el.getBoundingClientRect();
        const inline = getComputedStyle(el).display === 'inline' && el.tagName === 'A' && /^(P|LI|DD)$/.test(el.parentElement.tagName)
          && el.parentElement.textContent.trim().length > el.textContent.trim().length + 15;
        if ((b.height < 47.5 || b.width < 47.5) && !inline) small.push(el.outerHTML.slice(0, 80));
      });
      return {minFont, small, overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth};
    }""")
    assert res["minFont"] >= 18
    assert res["small"] == []
    assert res["overflow"] <= 0


def test_f10_keyboard_search(page):
    page.goto(url("/"))
    for _ in range(6):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement.id") == "q":
            break
    page.keyboard.type("46052")
    page.keyboard.press("Enter")
    page.wait_for_selector("#cards > li")
    assert page.evaluate("document.activeElement.id") == "results-h"
