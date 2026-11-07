"""Assemble the public data files: dist/data/offers.json and helpers the
page templates share."""
from __future__ import annotations

import collections
import json

from . import config, offers as offers_mod

EVERYWHERE = "everywhere"   # no store at all (National Parks, ...)
STORES = "stores"           # real locations from All The Places
FIND = "find"               # chain with no store list: "Find nearest" link
PLACE = "place"             # single location, hand-entered with a source


def load_brands() -> dict:
    return json.loads((config.DATA / "brands.json").read_text(encoding="utf-8"))


def load_places() -> list[dict]:
    path = config.DATA / "places.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))["places"]


def offer_kind(o, brand_of: dict, brands: dict, no_store: set, kept: dict) -> str:
    if o.slug in no_store:
        return EVERYWHERE
    if o.scope == "single_location":
        return PLACE
    b = brand_of[o.slug]
    if brands[b].get("atp_spiders") and kept.get(b, 0) > 0:
        return STORES
    return FIND


def build_offers_json(offers, brands_doc: dict, kept: dict, derived: dict, places: list[dict]) -> dict:
    brands = brands_doc["brands"]
    no_store = set(brands_doc.get("no_store_offers", []))
    brand_of = {o: slug for slug, b in brands.items() for o in b["offers"]}
    out_offers = []
    for o in sorted(offers, key=lambda x: x.name.lower()):
        tags, _ = offers_mod.eligibility_tags(o.eligibility)
        kind = offer_kind(o, brand_of, brands, no_store, kept)
        states = o.states
        if o.scope == "regional" and kind == STORES:
            states = derived.get(brand_of[o.slug]) or o.states
        rec = {
            "id": o.slug, "name": o.name, "cat": o.category, "type": o.type,
            "offer": o.offer, "terms": o.terms, "elig": o.eligibility, "tags": tags,
            "start": o.start_date.isoformat(), "end": o.end_date.isoformat(),
            "redeem_by": o.redeem_by.isoformat() if o.redeem_by else None,
            "redeem_note": o.redeem_note, "tw": o.time_window,
            "scope": o.scope, "states": states, "src": str(o.source_url),
            "map": o.map_query, "kind": kind, "brand": brand_of.get(o.slug),
            "checked": o.verified_on.isoformat(),
        }
        out_offers.append({k: v for k, v in rec.items() if v is not None})
    brand_out = {slug: {"name": b["name"], "offers": b["offers"]}
                 for slug, b in brands.items() if kept.get(slug, 0) > 0}
    return {
        "event": config.EVENT_DATE,
        "cats": offers_mod.CATEGORY_LABELS,
        "types": offers_mod.TYPE_LABELS,
        "tags": offers_mod.TAG_LABELS,
        "offers": out_offers,
        "brands": brand_out,
        "places": places,
    }


def offers_for_state(data: dict, st: str) -> tuple[list[dict], list[dict]]:
    """(offers good anywhere in the U.S., offers specific to this state)."""
    national, local = [], []
    for o in data["offers"]:
        if o["kind"] == PLACE:
            if any(p["offer"] == o["id"] and p["s"] == st for p in data["places"]):
                local.append(o)
        elif o["scope"] == "regional":
            if st in (o.get("states") or []):
                local.append(o)
        else:
            national.append(o)
    return national, local


def top_cities(records: list[dict], st: str, n: int = 12) -> list[tuple[str, int]]:
    c = collections.Counter(r["c"] for r in records if r["s"] == st and r.get("c"))
    return c.most_common(n)
