"""F13: large-print list at /print/?zip=46052&r=25."""
from __future__ import annotations

import os

from .conftest import url

SHOTS = os.environ.get("EVIDENCE") == "1"


def test_f13_print_layout(browser):
    ctx = browser.new_context(viewport={"width": 816, "height": 1056})
    page = ctx.new_page()
    page.emulate_media(media="print", color_scheme="light")
    page.goto(url("/print/?zip=46052&r=25"))
    page.wait_for_selector("#print-list > li")
    r = page.evaluate("""() => {
      const vis = el => { const s = getComputedStyle(el); const b = el.getBoundingClientRect();
        return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0 && !el.closest('.sr-only'); };
      let minPx = 99, minEl = '';
      document.querySelectorAll('body *').forEach(el => {
        if (vis(el) && [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) {
          const f = parseFloat(getComputedStyle(el).fontSize);
          if (f < minPx) { minPx = f; minEl = el.tagName + ' ' + el.textContent.trim().slice(0, 30); } } });
      const items = [...document.querySelectorAll('#print-list > li')];
      return {
        print: matchMedia('print').matches, count: items.length, minPt: minPx * 0.75, minEl,
        columns: new Set(items.slice(0, 30).map(li => Math.round(li.getBoundingClientRect().left))).size,
        images: document.querySelectorAll('img, svg, picture, video, canvas').length
          + [...document.querySelectorAll('*')].filter(e => getComputedStyle(e).backgroundImage !== 'none').length,
        header: getComputedStyle(document.querySelector('.site-header')).display,
        first: items[0].innerText,
      };
    }""")
    assert r["print"]
    assert r["count"] > 100
    assert round(r["minPt"], 1) >= 16, r["minEl"]
    assert r["columns"] == 1
    assert r["images"] == 0
    assert r["header"] == "none"
    first = r["first"]
    assert "miles" in first and "Lebanon, IN" in first and ("Phone:" in first or "No phone listed" in first)
    assert "Free" in first or "%" in first  # the offer text
    if SHOTS:
        page.screenshot(path="evidence/F13.png")
        page.pdf(path="evidence/F13-print.pdf", format="Letter")
    ctx.close()


def test_f13_results_page_has_print_link(page):
    page.goto(url("/near/46052"))
    page.wait_for_selector("#cards > li")
    href = page.get_attribute("#print-link", "href")
    assert href.startswith("/print/#") and "zip=46052" in href and "r=25" in href
    page.click("#print-link")
    page.wait_for_selector("#print-list > li")
    assert page.text_content("#print-h") == "Veterans Day offers near Lebanon, IN 46052"


def test_f13_print_link_keeps_filters(page):
    page.goto(url("/near/46052"))
    page.wait_for_selector("#cards > li")
    page.click("#filters summary")
    page.click("[data-cat='coffee']")
    page.click("#print-link")
    page.wait_for_selector("#print-list > li")
    names = page.eval_on_selector_all("#print-list h2", "h => h.map(x => x.childNodes[0].textContent.trim())")
    coffee = {"Starbucks", "Dunkin'", "Casey's", "Biggby Coffee", "Bruegger's Bagels", "Einstein Bros. Bagels",
              "7 Brew", "TCBY", "WaBa Grill", "Polly's Pies"}
    assert names and set(names) <= coffee
