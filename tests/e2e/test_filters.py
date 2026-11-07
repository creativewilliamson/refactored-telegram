"""F15: filter by category, free only, and who qualifies."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from .conftest import url

SHOTS = os.environ.get("EVIDENCE") == "1"
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def results(page):
    page.goto(url("/near/46052"))
    page.wait_for_selector("#cards > li")
    page.click("#filters summary")
    data = page.request.get(url("/data/offers.json")).json()
    page.offers_by_text = {o["offer"]: o for o in data["offers"]}  # type: ignore[attr-defined]
    return page


def shown_offers(page):
    texts = page.eval_on_selector_all(
        "#cards .offer-text, #far-cards .offer-text, #everywhere-list .offer-text, #find-list .offer-text",
        "els => els.map(e => e.textContent)")
    return [page.offers_by_text[t] for t in texts]


def summary_count(page):
    s = page.text_content("#summary")
    return 0 if s.startswith("No ") else int(s.split()[0])


@pytest.mark.parametrize("cat", ["meal", "coffee", "retail", "care", "fun"])
def test_f15_category(results, cat):
    page = results
    before = summary_count(page)
    page.click(f"[data-cat='{cat}']")
    offers = shown_offers(page)
    assert offers and all(o["cat"] == cat for o in offers)
    assert summary_count(page) < before
    if SHOTS and cat == "coffee":
        page.screenshot(path="evidence/F15-coffee.png")


def test_f15_free_only(results):
    page = results
    assert any(o["type"] != "free" for o in shown_offers(page))
    page.click("#free-only")
    assert page.get_attribute("#free-only", "aria-pressed") == "true"
    offers = shown_offers(page)
    assert offers and all(o["type"] == "free" for o in offers)
    assert not any("Discount" == c or "Free with purchase" == c
                   for c in page.eval_on_selector_all("#cards .chip-type", "e => e.map(x => x.textContent)"))
    if SHOTS:
        page.screenshot(path="evidence/F15-free.png")


def test_f15_gold_star(results):
    page = results
    page.select_option("#who", "gold_star")
    offers = shown_offers(page)
    assert offers
    assert all("gold_star" in o["tags"] or "everyone" in o["tags"] for o in offers)
    assert {"Benihana"} <= {o["name"] for o in offers}
    if SHOTS:
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path="evidence/F15-gold-star.png", full_page=False)


def test_f15_clear_filters(results):
    page = results
    before = summary_count(page)
    page.click("[data-cat='coffee']")
    page.click("#free-only")
    page.select_option("#who", "family")
    assert summary_count(page) < before
    page.click("#clear-filters")
    assert summary_count(page) == before


def test_f15_eligibility_map_tags_every_offer():
    emap = json.loads((ROOT / "data/eligibility-map.json").read_text(encoding="utf-8"))
    assert len(emap["offers"]) == 130 and all(r["tags"] for r in emap["offers"])
