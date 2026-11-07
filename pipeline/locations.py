"""Brand -> real store locations from All The Places.

Rules (SPEC 6.2):
- Only features in the US or a US territory.
- Only features whose brand:wikidata is one of the brand's checked Q-ids.
  This blocks name collisions ("Eureka!" vs Eureka, CA; "Casey's"; etc.).
- Coordinates must sit near the store's own ZIP centroid and inside the
  U.S. (checked against Census ZIP centroids); anything else is dropped.
- Stores with an address but no coordinates are placed with the public U.S.
  Census Geocoder; stores with neither are dropped.

Record: {b: brandSlug, n: branch?, a: street, c: city, s: state, z: zip,
         la: lat (5 dp), lo: lng (5 dp), p: phone?, h: hours?}
"""
from __future__ import annotations

import collections
import json
import math
import re
import urllib.parse
from dataclasses import dataclass, field

from . import atp, config, geocode

US_COUNTRIES = {"US", "PR", "GU", "VI", "AS", "MP"}
STATE_BY_NAME = {v.lower(): k for k, v in config.STATES.items()}
STATE_BY_NAME.update({"virgin islands": "VI", "us virgin islands": "VI", "washington dc": "DC",
                      "washington, d.c.": "DC", "puerto rico": "PR"})
ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")
MAX_FROM_ZIP_MI = 75       # store must be this close to its own ZIP centroid
MAX_FROM_ANY_ZIP_MI = 60   # and this close to some U.S. ZIP centroid
DEDUP_MI = 0.06            # ~100 m: same brand closer than this = one store


def miles(lat1, lng1, lat2, lng2) -> float:
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


class ZipIndex:
    """Nearest-ZIP lookups on a 1-degree grid."""

    def __init__(self, zips: dict[str, list]):
        self.zips = zips
        self.grid: dict[tuple[int, int], list[tuple[float, float, str]]] = collections.defaultdict(list)
        for code, (lat, lng, _city, st) in zips.items():
            self.grid[(math.floor(lat), math.floor(lng))].append((lat, lng, st))

    def nearest(self, lat: float, lng: float) -> tuple[float, str | None]:
        best = (1e9, None)
        gi, gj = math.floor(lat), math.floor(lng)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for zlat, zlng, st in self.grid.get((gi + di, gj + dj), ()):
                    d = miles(lat, lng, zlat, zlng)
                    if d < best[0]:
                        best = (d, st)
        return best

    def state_near(self, lat: float, lng: float, state: str, within: float) -> bool:
        gi, gj = math.floor(lat), math.floor(lng)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for zlat, zlng, st in self.grid.get((gi + di, gj + dj), ()):
                    if st == state and miles(lat, lng, zlat, zlng) <= within:
                        return True
        return False


def norm_state(v: str | None) -> str | None:
    if not v:
        return None
    v = v.strip()
    if v.upper() in config.STATES:
        return v.upper()
    return STATE_BY_NAME.get(v.lower())


def norm_phone(v: str | None) -> str | None:
    if not v:
        return None
    first = v.split(";")[0]
    digits = re.sub(r"\D", "", first)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10 and digits[0] not in "01" and digits[3] not in "01":
        return digits
    return None


def street_of(p: dict) -> str:
    if p.get("addr:street_address"):
        return p["addr:street_address"].strip()
    hn, st = p.get("addr:housenumber"), p.get("addr:street")
    if st:
        return f"{hn} {st}".strip() if hn else st.strip()
    full = p.get("addr:full") or ""
    return full.split(",")[0].strip() if "," in full else ""


def parse_full(full: str) -> tuple[str | None, str | None, str | None]:
    """Pull (city, state, zip) out of 'street, City, ST 12345'."""
    if not full:
        return None, None, None
    m = re.search(r",\s*([^,]+?),?\s+([A-Za-z]{2})\.?\s+(\d{5})(?:-\d{4})?\s*$", full)
    if m:
        return m.group(1).strip(), m.group(2).upper(), m.group(3)
    return None, None, None


@dataclass
class BrandStats:
    features: int = 0
    wrong_brand: int = 0
    not_us: int = 0
    no_place: int = 0
    geocoded: int = 0
    bad_coords: int = 0
    duplicates: int = 0
    kept: int = 0
    run: str = ""
    spiders: list[str] = field(default_factory=list)


def build(brands: dict, zips: dict[str, list], offline: bool) -> tuple[list[dict], dict[str, BrandStats], dict]:
    zindex = ZipIndex({k: v for k, v in zips.items() if isinstance(v, list)})
    spiders = sorted({s for b in brands.values() for s in b.get("atp_spiders", [])})
    choices = atp.choose_runs(spiders, offline)
    stats: dict[str, BrandStats] = {}
    pending: list[tuple[str, dict, dict]] = []   # (brand, props, partial record)
    records: list[dict] = []

    for slug, b in brands.items():
        if not b.get("atp_spiders"):
            continue
        st = stats[slug] = BrandStats(spiders=list(b["atp_spiders"]))
        qids = set(b.get("brand_wikidata") or [])
        for sp in b["atp_spiders"]:
            pick = choices.get(sp)
            if not pick:
                continue
            st.run = pick[0]
            feats = atp.load_features(atp.spider_file(sp, pick[0], offline))
            for f in feats:
                st.features += 1
                p = f.get("properties") or {}
                if p.get("brand:wikidata") not in qids:
                    st.wrong_brand += 1
                    continue
                country = (p.get("addr:country") or "").upper() or None
                fc, fs, fz = parse_full(p.get("addr:full") or "")
                state = norm_state(p.get("addr:state")) or fs
                if country and country not in US_COUNTRIES:
                    st.not_us += 1
                    continue
                if not country and state not in config.STATES:
                    st.not_us += 1
                    continue
                if country in US_COUNTRIES - {"US"}:
                    state = state if state == country else country
                zm = ZIP_RE.search(p.get("addr:postcode") or "") or (re.match(r"\d{5}", fz) if fz else None)
                zipc = zm.group(1) if zm and zm.re is ZIP_RE else (fz or None)
                rec = {
                    "b": slug,
                    "n": (p.get("branch") or "").strip() or None,
                    "a": street_of(p),
                    "c": (p.get("addr:city") or fc or "").strip(),
                    "s": state,
                    "z": zipc,
                    "p": norm_phone(p.get("phone")),
                    "h": (p.get("opening_hours") or "").strip() or None,
                }
                if not rec["a"] and b.get("ref_address_pattern"):
                    m = re.search(b["ref_address_pattern"], p.get("ref") or p.get("website") or "")
                    if m:
                        rec["a"] = urllib.parse.unquote(m.group("a")).replace("-", " ")
                        rec["c"] = urllib.parse.unquote(m.group("c")).replace("-", " ").title()
                        rec["s"] = norm_state(m.group("s"))
                        rec["from_url"] = True
                geom = f.get("geometry") or {}
                if geom.get("type") == "Point" and geom.get("coordinates"):
                    lng, lat = geom["coordinates"][:2]
                    rec["la"], rec["lo"] = float(lat), float(lng)
                    records.append(rec)
                elif rec["a"] and (rec["z"] or (rec["c"] and rec["s"])):
                    pending.append((slug, p, rec))
                else:
                    st.no_place += 1

    # Census Geocoder for stores with an address but no coordinates.
    rows = []
    for i, (_slug, _p, rec) in enumerate(pending):
        rows.append((str(i), rec["a"], rec["c"] or "", rec["s"] or "", rec["z"] or ""))
    found = geocode.batch(rows, offline)
    for i, (slug, _p, rec) in enumerate(pending):
        hit = found.get(str(i))
        from_url = rec.pop("from_url", False)
        if hit:
            rec["la"], rec["lo"] = hit.lat, hit.lng
            if from_url:
                # Show the Census-matched address, not our reading of the URL.
                rec["a"], rec["c"], rec["s"], rec["z"] = hit.street, hit.city, hit.state, hit.zip
            elif not rec.get("z"):
                rec["z"] = hit.zip
            records.append(rec)
            stats[slug].geocoded += 1
        else:
            stats[slug].no_place += 1

    # Coordinate checks, state/ZIP fill-in, rounding.
    checked: list[dict] = []
    for rec in records:
        lat, lng = rec["la"], rec["lo"]
        st = stats[rec["b"]]
        if not (-15.0 <= lat <= 72.0) or not (-180.0 <= lng <= -64.0 or 144.0 <= lng <= 146.5):
            st.bad_coords += 1
            continue
        near_d, near_state = zindex.nearest(lat, lng)
        if near_d > MAX_FROM_ANY_ZIP_MI:
            st.bad_coords += 1
            continue
        z = rec.get("z")
        if z and z in zindex.zips:
            zlat, zlng, zcity, zst = zindex.zips[z]
            if miles(lat, lng, zlat, zlng) > MAX_FROM_ZIP_MI:
                st.bad_coords += 1
                continue
            rec["s"] = rec["s"] or zst
            rec["c"] = rec["c"] or zcity.title()
        if not rec["s"]:
            rec["s"] = near_state
        if rec["s"] != near_state and not zindex.state_near(lat, lng, rec["s"], 30):
            st.bad_coords += 1
            continue
        rec["la"], rec["lo"] = round(lat, 5), round(lng, 5)
        checked.append(rec)

    # De-duplicate (same brand, ~100 m apart).
    out: list[dict] = []
    grid: dict[tuple[str, int, int], list[dict]] = collections.defaultdict(list)
    for rec in sorted(checked, key=lambda r: (r["b"], r["la"], r["lo"])):
        key = (rec["b"], int(rec["la"] * 100), int(rec["lo"] * 100))
        dup = False
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for other in grid.get((rec["b"], key[1] + di, key[2] + dj), ()):
                    if miles(rec["la"], rec["lo"], other["la"], other["lo"]) < DEDUP_MI:
                        dup = True
                        for k in ("p", "h", "n", "z", "a"):
                            if not other.get(k) and rec.get(k):
                                other[k] = rec[k]
                        break
                if dup:
                    break
            if dup:
                break
        if dup:
            stats[rec["b"]].duplicates += 1
            continue
        grid[key].append(rec)
        out.append(rec)
    for rec in out:
        stats[rec["b"]].kept += 1
        for k in [k for k, v in rec.items() if v in (None, "")]:
            if k not in ("a", "c"):
                del rec[k]
    return out, stats, {sp: c for sp, c in choices.items()}


def derived_states(records: list[dict]) -> dict[str, list[str]]:
    by: dict[str, set] = collections.defaultdict(set)
    for r in records:
        by[r["b"]].add(r["s"])
    return {b: sorted(s) for b, s in by.items()}


def dump_sample(records: list[dict], path) -> None:  # debugging aid
    path.write_text(json.dumps(records[:50], indent=1), encoding="utf-8")
