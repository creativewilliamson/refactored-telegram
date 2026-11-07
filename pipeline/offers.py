"""Load, validate and enrich the offer seed.

- data/seed/offers-2026.json is read-only (never edited).
- data/overrides.json adds corrections (each with reason + source_url).
- eligibility_tags are parsed from the `eligibility` text; the parse table is
  written to data/eligibility-map.json for a human to check.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator, model_validator

from . import config

Category = Literal["meal", "coffee", "retail", "care", "fun"]
OfferType = Literal["free", "discount", "purchase"]
Scope = Literal["national", "regional", "single_location"]

CATEGORY_LABELS = {
    "meal": "Meals",
    "coffee": "Coffee & treats",
    "retail": "Shopping",
    "care": "Haircuts & car care",
    "fun": "Attractions",
}
TYPE_LABELS = {"free": "Free", "purchase": "Free with purchase", "discount": "Discount"}
TAG_LABELS = {
    "veteran": "Veterans",
    "active": "Active duty",
    "guard_reserve": "Guard and Reserve",
    "retiree": "Retirees",
    "family": "Spouses and family",
    "gold_star": "Gold Star families",
    "everyone": "Everyone",
}

# Parse table: (regex on the eligibility text, tags it adds, why).
ELIGIBILITY_RULES: list[tuple[str, list[str], str]] = [
    (r"\bveterans?\b", ["veteran"], "says veterans"),
    (r"\bformer military\b", ["veteran"], "former military = veterans"),
    (r"\bactive( duty)?\b", ["active"], "says active duty"),
    (r"\bservice members?\b", ["active"], "service members = active duty"),
    (r"^military\b", ["active"], "'Military' = serving members"),
    (r"\breserve\b", ["guard_reserve"], "says Reserve"),
    (r"\bguard\b", ["guard_reserve"], "says Guard"),
    (r"\bretire(d|es?)\b", ["retiree"], "says retirees / retired military"),
    (r"(?<!gold star )\bfamil(y|ies)\b", ["family"], "says family / families (not Gold Star)"),
    (r"\bspouses?\b", ["family"], "says spouses"),
    (r"\bdependents?\b", ["family"], "says dependents"),
    (r"\bgold star\b", ["gold_star"], "says Gold Star families"),
    (r"\beveryone\b|\ball visitors\b", ["everyone"], "open to everyone"),
]
# Phrases the regex table can't read on its own; checked by hand against the
# source page and the eligibility rules of the program named.
ELIGIBILITY_SPECIAL: dict[str, tuple[list[str], str]] = {
    "Exchange-eligible shoppers": (
        ["active", "guard_reserve", "retiree", "veteran", "family"],
        "Exchange shopping is open to active duty, Guard/Reserve, retirees, "
        "dependents and (online) honorably discharged veterans; see source.",
    ),
}
# Military retirees are veterans, so any offer for veterans covers them too.
IMPLIED = [("veteran", "retiree", "military retirees are veterans")]

ALLOWED_OVERRIDE_KEYS = {
    "time_window", "offer", "terms", "eligibility", "start_date", "end_date",
    "redeem_by", "redeem_note", "states", "source_url", "category", "type",
}


class Offer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    category: Category
    type: OfferType
    offer: str
    terms: Optional[str] = None
    eligibility: str
    start_date: dt.date
    end_date: dt.date
    redeem_by: Optional[dt.date] = None
    redeem_note: Optional[str] = None
    states: Optional[list[str]] = None
    place: Optional[str] = None
    map_query: str
    source_url: HttpUrl
    verified_on: dt.date
    scope: Scope
    time_window: Optional[str] = None

    @field_validator("slug")
    @classmethod
    def slug_ok(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", v):
            raise ValueError(f"bad slug {v!r}")
        return v

    @field_validator("states")
    @classmethod
    def states_ok(cls, v):
        if v is not None:
            for s in v:
                if s not in config.STATES:
                    raise ValueError(f"unknown state {s!r}")
        return v

    @model_validator(mode="after")
    def dates_ok(self):
        if self.end_date < self.start_date:
            raise ValueError(f"{self.slug}: end_date before start_date")
        if self.redeem_by and self.redeem_by < self.end_date:
            raise ValueError(f"{self.slug}: redeem_by before end_date")
        if self.scope == "single_location" and not self.place:
            raise ValueError(f"{self.slug}: single_location offer needs place")
        return self


class Override(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    set: dict
    reason: str
    source_url: HttpUrl

    @field_validator("set")
    @classmethod
    def keys_ok(cls, v: dict) -> dict:
        bad = set(v) - ALLOWED_OVERRIDE_KEYS
        if bad:
            raise ValueError(f"override keys not allowed: {sorted(bad)}")
        return v

    @field_validator("reason")
    @classmethod
    def reason_ok(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("override reason too short")
        return v


def load_seed() -> dict:
    return json.loads(config.SEED.read_text(encoding="utf-8"))


def load_overrides() -> list[Override]:
    path = config.DATA / "overrides.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Override(**o) for o in raw.get("offers", [])]


def eligibility_tags(text: str) -> tuple[list[str], list[str]]:
    """Return (tags, reasons) for an eligibility string."""
    if text in ELIGIBILITY_SPECIAL:
        tags, why = ELIGIBILITY_SPECIAL[text]
        tags = list(tags)
        reasons = [why]
    else:
        tags, reasons = [], []
        low = text.lower()
        for pattern, add, why in ELIGIBILITY_RULES:
            if re.search(pattern, low):
                for t in add:
                    if t not in tags:
                        tags.append(t)
                reasons.append(why)
    for have, implied, why in IMPLIED:
        if have in tags and implied not in tags:
            tags.append(implied)
            reasons.append(why)
    order = list(TAG_LABELS)
    tags.sort(key=order.index)
    return tags, reasons


def load_offers() -> list[Offer]:
    seed = load_seed()
    raw = {o["slug"]: dict(o) for o in seed["offers"]}
    if len(raw) != len(seed["offers"]):
        raise ValueError("duplicate slugs in seed")
    if seed.get("count") is not None and seed["count"] != len(raw):
        raise ValueError(f"seed count {seed['count']} != {len(raw)} offers")
    for ov in load_overrides():
        if ov.slug not in raw:
            raise ValueError(f"override for unknown offer {ov.slug!r}")
        raw[ov.slug].update(ov.set)
    offers = [Offer(**o) for o in raw.values()]
    return offers


def eligibility_map(offers: list[Offer]) -> dict:
    rows = []
    for o in offers:
        tags, reasons = eligibility_tags(o.eligibility)
        rows.append({"slug": o.slug, "eligibility": o.eligibility, "tags": tags, "why": reasons})
    return {
        "_readme": "Generated by pipeline/offers.py from each offer's eligibility text. "
                   "A person should read this table and fix the rules if a tag is wrong.",
        "tags": TAG_LABELS,
        "rules": [{"pattern": p, "adds": a, "why": w} for p, a, w in ELIGIBILITY_RULES]
                 + [{"phrase": k, "adds": v[0], "why": v[1]} for k, v in ELIGIBILITY_SPECIAL.items()]
                 + [{"if": h, "adds": [i], "why": w} for h, i, w in IMPLIED],
        "offers": rows,
    }


def write_eligibility_map(offers: list[Offer]) -> dict:
    emap = eligibility_map(offers)
    for row in emap["offers"]:
        if not row["tags"]:
            raise ValueError(f"offer {row['slug']} has no eligibility tags")
    path = config.DATA / "eligibility-map.json"
    path.write_text(json.dumps(emap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return emap
