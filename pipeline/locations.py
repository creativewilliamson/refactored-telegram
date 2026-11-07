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
import datetime as dt
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
MAX_FROM_ANY_ZIP_MI = 60   # store must be this close to some U.S. ZIP centroid
ZIP_SLACK_MI = 10          # ...and within (ZIP radius + this) of its own ZIP
MIN_ZIP_ALLOWANCE_MI = 15
CITY_ALLOWANCE_MI = 25     # or within this of its own town's Census point
STATE_BORDER_MI = 15

# The source itself marks these as not real public stores: test and lab
# entries, closed or not-yet-open stores, and staff-only sites.
NOT_PUBLIC = re.compile(
    r"\b(test|testing|qa|lab|dev|demo|uat|sandbox)\b|do not use|do not order|support cent(er|re)|training (center|store)|"
    r"corporate office|secure access|closed to (the )?public|\bclosed\b|coming soon|opening soon|"
    r"not (yet )?open|future (site|location)|\bplaceholder\b",
    re.I,
)
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
    if len(digits) != 10 or digits[0] in "01" or digits[3] in "01":
        return None
    if is_placeholder_phone(digits):
        return None
    return digits


def is_placeholder_phone(d: str) -> bool:
    """Numbers the source uses as fillers (555-555-5555, 999-999-9999,
    766-767-6767, 123-456-7890). The store stays; the phone is dropped."""
    if d[3:6] == "555":                       # 555 exchange: fictional/directory
        return True
    if len(set(d)) == 1:                       # 999-999-9999
        return True
    local = d[3:]
    if all(local[i] == local[i % 2] for i in range(7)):   # 767-6767 style filler
        return True
    if d in ("1234567890", "2345678901", "9876543210"):
        return True
    if d[1:3] == "11" or d[4:6] == "11":       # N11 codes (411, 911...) aren't store lines
        return True
    return False


# Street fields hold real names like "Test Drive", so only unmistakable
# markers count there.
STREET_NOT_PUBLIC = re.compile(r"do not use|do not order|closed|coming soon|secure access|not (yet )?open", re.I)


TEST_SITE = re.compile(r"\b(test|testing|qa|lab|dev|demo|uat|sandbox)\b|do not (use|order)|support cent(er|re)", re.I)
TEST_CLUSTER_MI = 0.25


def test_points(feats: list[dict], qids: set) -> list[tuple[float, float]]:
    """Where the brand keeps test/lab entries. Other entries of the same brand
    within a quarter mile are staging copies too (e.g. "TXRH Win10", "Tier 2"
    beside a "QA Lab"), so they are dropped with them."""
    pts = []
    for f in feats:
        p = f.get("properties") or {}
        if p.get("brand:wikidata") not in qids:
            continue
        names = " ".join(str(p.get(k) or "") for k in ("branch", "name", "addr:unit"))
        streets = " ".join(str(p.get(k) or "") for k in ("addr:street_address", "addr:full"))
        g = f.get("geometry") or {}
        if (TEST_SITE.search(names) or re.search(r"do not (use|order)", streets, re.I)) and g.get("coordinates"):
            lng, lat = g["coordinates"][:2]
            pts.append((float(lat), float(lng)))
    return pts


def near_test_point(f: dict, pts: list[tuple[float, float]]) -> bool:
    g = f.get("geometry") or {}
    if not pts or not g.get("coordinates"):
        return False
    lng, lat = g["coordinates"][:2]
    return any(miles(lat, lng, a, b) <= TEST_CLUSTER_MI for a, b in pts)


def not_public(p: dict) -> bool:
    for key in ("branch", "name", "addr:unit"):
        v = p.get(key)
        if v and NOT_PUBLIC.search(str(v)):
            return True
    for key in ("addr:street_address", "addr:street", "addr:full"):
        v = p.get(key)
        if v and STREET_NOT_PUBLIC.search(str(v)):
            return True
    end = str(p.get("end_date") or "").strip()
    if end and (end == "yes" or end <= dt.date.today().isoformat()):
        return True
    return False


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
    not_public: int = 0
    placeholder_phone: int = 0
    bad_coords: int = 0
    state_fixed: int = 0
    zip_hidden: int = 0
    duplicates: int = 0
    kept: int = 0
    run: str = ""
    spiders: list[str] = field(default_factory=list)


def build(brands: dict, zips: dict[str, list], offline: bool, areas: dict[str, float] | None = None,
          cities: dict[str, dict] | None = None) -> tuple[list[dict], dict[str, BrandStats], dict]:
    from .geo import norm_name
    areas = areas or {}
    cities = cities or {}
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
            labs = test_points(feats, qids)
            for f in feats:
                st.features += 1
                p = f.get("properties") or {}
                if p.get("brand:wikidata") not in qids:
                    st.wrong_brand += 1
                    continue
                if not_public(p) or near_test_point(f, labs):
                    st.not_public += 1
                    continue
                raw = re.sub(r"\D", "", str(p.get("phone") or "").split(";")[0])[-10:]
                if len(raw) == 10 and is_placeholder_phone(raw):
                    st.placeholder_phone += 1
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
        # The point must agree with the store's own ZIP (allowing for big
        # rural ZIPs) or, if the ZIP itself is off, with its own town.
        z = rec.get("z")
        town = None
        if rec.get("s") and rec.get("c"):
            town = cities.get(rec["s"], {}).get(norm_name(rec["c"]))
        near_town = bool(town) and miles(lat, lng, town[0], town[1]) <= CITY_ALLOWANCE_MI
        if z and z in zindex.zips:
            zlat, zlng, zcity, zst = zindex.zips[z]
            radius = math.sqrt(areas.get(z, 0.0) / math.pi)
            allowed = max(MIN_ZIP_ALLOWANCE_MI, radius + ZIP_SLACK_MI)
            if miles(lat, lng, zlat, zlng) <= allowed:
                if rec["s"] and rec["s"] != zst:
                    st.state_fixed += 1          # e.g. "New York, NJ 10001" -> NY
                rec["s"] = zst
                rec["c"] = rec["c"] or zcity.title()
            elif near_town:
                del rec["z"]                     # ZIP contradicts the place: don't show it
                st.zip_hidden += 1
            else:
                st.bad_coords += 1
                continue
        elif town and not near_town:
            st.bad_coords += 1
            continue
        if not rec["s"]:
            rec["s"] = near_state
        if rec["s"] != near_state and not zindex.state_near(lat, lng, rec["s"], STATE_BORDER_MI):
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
