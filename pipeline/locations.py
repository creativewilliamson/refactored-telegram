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
ZIP_RE = re.compile(r"\b(\d{5})(?:-?\d{4})?\b")   # 12345, 12345-6789, 123456789
MAX_FROM_ANY_ZIP_MI = 60   # store must be this close to some U.S. ZIP centroid
ZIP_SLACK_MI = 10          # ...and within (ZIP radius + this) of its own ZIP
MIN_ZIP_ALLOWANCE_MI = 15
CITY_ALLOWANCE_MI = 25     # or within this of its own town's Census point
STATE_BORDER_MI = 15

# The source itself marks these as not real public stores: test and lab
# entries, closed or not-yet-open stores, and staff-only sites.
NOT_PUBLIC = re.compile(
    # test and lab entries
    r"\b(test|testing|qa|lab|dev|demo|uat|sandbox)\b|do not use|do not order|support cent(er|re)|"
    r"training (center|store)|\bplaceholder\b|"
    # offices, staff-only and restricted sites
    r"\b(corporate|head|company) office\b|\b(hq|headquarters)\b|\bcatering\b|secure\s*acc|\brestricted\b|\bprivate\b|\bno access\b|"
    r"\b(employees?|staff|associates?|students?|members?)\b[^|]{0,30}\bonly\b|"
    r"\bonly\b[^|]{0,15}\b(employees?|staff)\b|closed to (the )?public|"
    # closed or not open yet ("(Open 12/7)", "Opens December 2026")
    r"\bclosed\b|coming soon|opening soon|not (yet )?open|future (site|location)|"
    r"\bopen(s|ing)?\s+(\d{1,2}/\d{1,2}|(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|20\d\d)|"
    # cruise ships listed at a cruise line's office
    r"\b(ncl|rci)\b|of the seas|\bcruise\b|\bship\b",
    re.I,
)
DEDUP_MI = 0.06            # ~100 m: same brand closer than this = one store
# Listings the chain hasn't filled in yet are placeholders for stores not open
# yet (checked against chains' own pages in evaluator round 8: Dunkin' with
# neither phone nor hours 19/21 COMING_SOON; Playa Bowls with neither 9/14
# "coming soon"; Chipotle with no hours 29/44
# "COMING SOON!"; Wendy's with no hours 5/6 pages gone). See end of build().
COMPLETE_CHAIN_SHARE = 0.96    # >= this share has a phone or hours -> drop listings with neither
HOURS_CHAIN_SHARE = 0.97       # >= this share has hours -> drop listings without hours


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
STREET_NOT_PUBLIC = re.compile(
    r"do not use|do not order|closed|coming soon|secure\s*acc|not (yet )?open|"
    # provisional addresses: the store isn't built or open yet
    r"(temp|temporary|provisional) address|address (to change|pending|tbd)|(subject|to) change|"
    # inside the Pentagon (badge-only), not the public Pentagon City / Pentagon Row malls
    r"(^|,)\s*pentagon\s*\.?$|"
    # inside government department buildings: badge-only or closed on the
    # Veterans Day federal holiday (State Dept, USDA, Library of Congress...)
    r"(dept|department) of (state|justice|agriculture|defense|energy|labor|commerce|education|"
    r"transportation|the treasury|treasury|the interior|interior|homeland security|health|"
    r"veterans affairs|housing)\b|,\s*usda\s*$|library of congress|(house|senate) office building|"
    # postal plants and other industrial sites
    r"\busps\b|postal (service|facility)|sorting (facility|center)|processing (center|plant|facility)|"
    r"distribution cent(er|re)",
    re.I,
)


URL_NOT_PUBLIC = re.compile(
    r"coming[-_ ]?soon|temp(orarily)?[-_ ]?closed|permanently[-_ ]?closed|test[-_]restaurant", re.I)


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


CATEGORY_KEYS = ("shop", "amenity", "healthcare", "office")
WEEK = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def open_days_and_last_close(hours: str) -> tuple[set, int | None]:
    """Days a store opens and its latest closing minute, from an OSM-style
    string like 'Mo-Th 07:30-15:15; Fr 07:30-13:15'. (set(), None) if unclear."""
    days: set = set()
    ends: list[int] = []
    for part in (hours or "").split(";"):
        part = part.strip()
        if not part or re.search(r"off|closed", part):
            continue
        m = re.match(r"((?:Mo|Tu|We|Th|Fr|Sa|Su)(?:[-,](?:Mo|Tu|We|Th|Fr|Sa|Su))*)\s+(.*)$", part)
        if not m:
            return set(), None
        for seg in m.group(1).split(","):
            if "-" in seg:
                a, b = seg.split("-")
                i, j = WEEK.index(a), WEEK.index(b)
                days.update(WEEK[i:j + 1] if i <= j else WEEK[i:] + WEEK[:j + 1])
            else:
                days.add(seg)
        ends += [int(h) * 60 + int(mi) for h, mi in re.findall(r"-(\d{2}):(\d{2})", m.group(2))]
    return days, (max(ends) if ends else None)


def load_exclusions() -> set[tuple[str, str]]:
    """(spider, ref) pairs from data/location-exclusions.json; every entry must
    carry a reason and a source_url."""
    path = config.DATA / "location-exclusions.json"
    if not path.exists():
        return set()
    out = set()
    for e in json.loads(path.read_text(encoding="utf-8")).get("exclusions", []):
        if not (e.get("reason") and str(e.get("source_url", "")).startswith("https://")):
            raise ValueError(f"location exclusion without reason/source: {e}")
        out.add((e["spider"], str(e["ref"])))
    # Stores whose own chain page shows them closed, coming soon or gone
    # (tools/status_sweep.py; each entry has the page and the date checked).
    status = config.DATA / "store-status.json"
    if status.exists():
        for chain in json.loads(status.read_text(encoding="utf-8")).get("chains", {}).values():
            for e in chain.get("flagged", []):
                if not (e.get("status") and str(e.get("url", "")).startswith("https://")):
                    raise ValueError(f"store-status entry without status/page: {e}")
                out.add((e["spider"], str(e["ref"])))
    return out


def weekly_open_minutes(hours: str | None) -> int:
    """Rough minutes open per week from an OSM-style hours string (0 if unknown)."""
    h = (hours or "").strip()
    if not h:
        return 0
    if h == "24/7":
        return 7 * 24 * 60
    total = 0
    for part in h.split(";"):
        part = part.strip()
        m = re.match(r"((?:Mo|Tu|We|Th|Fr|Sa|Su)(?:[-,](?:Mo|Tu|We|Th|Fr|Sa|Su))*)\s+(.*)$", part)
        if not m or re.search(r"off|closed", m.group(2)):
            continue
        days = 0
        for seg in m.group(1).split(","):
            if "-" in seg:
                a, b = seg.split("-")
                i, j = WEEK.index(a), WEEK.index(b)
                days += (j - i + 1) if i <= j else (7 - i + j + 1)
            else:
                days += 1
        span = 0
        for a1, a2, b1, b2 in re.findall(r"(\d{2}):(\d{2})-(\d{2}):(\d{2})", m.group(2)):
            start, end = int(a1) * 60 + int(a2), int(b1) * 60 + int(b2)
            span += (end - start) if end > start else (24 * 60 - start + end)
        total += days * span
    return total


def workplace_hours(p: dict) -> bool:
    """Weekdays only and closed by 4 p.m. (or weekdays only with no public
    phone): a cafe inside an office campus, state office or plant, not a store
    a visitor walks into (Verizon HQ, Capital One campus, NJ state offices)."""
    days, close = open_days_and_last_close(str(p.get("opening_hours") or ""))
    if len(days) < 3 or {"Sa", "Su"} & days or close is None:
        return False
    return close <= 16 * 60 or not p.get("phone")


def not_public(p: dict, live_requires: tuple = ()) -> bool:
    if workplace_hours(p):
        return True
    if p.get("office"):                       # office=company: a head office, not a store
        return True
    start = str(p.get("start_date") or "").strip()
    if start and start[:10] > config.EVENT_DATE:   # opens after Veterans Day
        return True
    if any(not p.get(k) for k in live_requires):   # brand's listing not live yet
        return True
    for key in ("branch", "name", "addr:unit"):
        v = p.get(key)
        if v and NOT_PUBLIC.search(str(v)):
            return True
    for key in ("addr:street_address", "addr:street", "addr:full"):
        v = p.get(key)
        if v and STREET_NOT_PUBLIC.search(str(v)):
            return True
    # The source's own page/image URLs sometimes carry the status
    # (".../coming-soon-outlet-shoppes-at-el-paso/", "temp-closed.png").
    for key in ("website", "ref", "image", "@source_uri"):
        v = p.get(key)
        if v and URL_NOT_PUBLIC.search(str(v)):
            return True
    end = str(p.get("end_date") or "").strip()
    if end and (end == "yes" or end <= dt.date.today().isoformat()):
        return True
    return False


FULL_ADDR = re.compile(
    r"^(?P<street>.+?),\s*(?P<city>[^,]+?),\s*(?P<st>[A-Za-z]{2})\.?,?\s+(?P<zip>\d{5})(?:-?\d{4})?"
    r"(?:\s*,\s*(?:US|USA|United States))?\s*$"
)


def parse_full(full: str) -> tuple[str | None, str | None, str | None, str | None]:
    """Split addr:full into (street, city, state, zip). Handles 'street, City,
    ST 12345', 'street, City, ST, 12345' (TCBY), 9-digit ZIPs, and a trailing
    ', US' (Hard Rock). Returns Nones when it doesn't look like a full address."""
    m = FULL_ADDR.match((full or "").strip())
    if not m:
        return None, None, None, None
    return m.group("street").strip(), m.group("city").strip(), m.group("st").upper(), m.group("zip")


def street_of(p: dict) -> str:
    if p.get("addr:street_address"):
        return p["addr:street_address"].strip()
    hn, st = p.get("addr:housenumber"), p.get("addr:street")
    if st:
        return f"{hn} {st}".strip() if hn else st.strip()
    full = (p.get("addr:full") or "").strip()
    street, _c, _s, _z = parse_full(full)
    if street:
        return street
    if full and "," not in full and (p.get("addr:city") or p.get("addr:postcode")):
        return full            # Twin Peaks: addr:full is the street alone
    return full.split(",")[0].strip() if "," in full else ""


@dataclass
class BrandStats:
    features: int = 0
    wrong_brand: int = 0
    not_us: int = 0
    no_place: int = 0
    geocoded: int = 0
    not_public: int = 0
    not_store: int = 0
    incomplete: int = 0
    placeholder_phone: int = 0
    bad_coords: int = 0
    state_fixed: int = 0
    replaced: int = 0
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
    excluded = load_exclusions()
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
            live = tuple(b.get("live_listing_requires") or ())
            cats = set(b.get("store_categories") or ())
            not_store_names = re.compile(b["not_store_names"], re.I) if b.get("not_store_names") else None
            min_days = int(b.get("store_open_days_min") or 0)
            ob = str(b.get("store_opens_by") or "")
            opens_by = int(ob[:2]) * 60 + int(ob[3:5]) if ob else None
            for f in feats:
                st.features += 1
                p = f.get("properties") or {}
                if p.get("brand:wikidata") not in qids:
                    st.wrong_brand += 1
                    continue
                if (sp, str(p.get("ref"))) in excluded or not_public(p, live) or near_test_point(f, labs):
                    st.not_public += 1
                    continue
                if cats and not any(f"{k}={p.get(k)}" in cats for k in CATEGORY_KEYS if p.get(k)):
                    st.not_store += 1             # fuel pumps, pharmacy, liquor store...
                    continue
                if not_store_names and not_store_names.search(f"{p.get('name') or ''} {p.get('branch') or ''}"):
                    st.not_store += 1             # Hy-Vee HealthMarket Rx, Casey's Tobacco City...
                    continue
                if min_days and p.get("opening_hours"):
                    days, _close = open_days_and_last_close(str(p["opening_hours"]))
                    if p["opening_hours"].strip() not in ("24/7",) and days and len(days) < min_days:
                        st.not_store += 1         # grocery stores open daily; their pharmacies don't
                        continue
                if opens_by and p.get("opening_hours"):
                    starts = [int(a) * 60 + int(m) for a, m in
                              re.findall(r"(\d{2}):(\d{2})-", str(p["opening_hours"]))]
                    if starts and min(starts) > opens_by:
                        st.not_store += 1         # Food Lion stores open 6-7 a.m.; pharmacies at 9
                        continue
                raw = re.sub(r"\D", "", str(p.get("phone") or "").split(";")[0])[-10:]
                if len(raw) == 10 and is_placeholder_phone(raw):
                    st.placeholder_phone += 1
                country = (p.get("addr:country") or "").upper() or None
                _fa, fc, fs, fz = parse_full(p.get("addr:full") or "")
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
    def place(rec: dict, lat: float, lng: float) -> str:
        """'ok' (rec updated), 'retry' (point disagrees with the address:
        place it again from the address) or 'drop'."""
        if not (-15.0 <= lat <= 72.0) or not (-180.0 <= lng <= -64.0 or 144.0 <= lng <= 146.5):
            return "retry"
        near_d, near_state = zindex.nearest(lat, lng)
        if near_d > MAX_FROM_ANY_ZIP_MI:
            return "retry"
        # The point must agree with the store's own ZIP (allowing for big
        # rural ZIPs). If it doesn't, it may still be right when the ZIP is the
        # odd one out (ZIP far from the store's own town, point in that town).
        # When the ZIP and town agree with each other, the point is wrong.
        z = rec.get("z")
        town = None
        if rec.get("s") and rec.get("c"):
            town = cities.get(rec["s"], {}).get(norm_name(rec["c"]))
        near_town = bool(town) and miles(lat, lng, town[0], town[1]) <= CITY_ALLOWANCE_MI
        zip_state = None
        hide_zip = False
        if z and z in zindex.zips:
            zlat, zlng, zcity, zst = zindex.zips[z]
            radius = math.sqrt(areas.get(z, 0.0) / math.pi)
            allowed = max(MIN_ZIP_ALLOWANCE_MI, radius + ZIP_SLACK_MI)
            if miles(lat, lng, zlat, zlng) <= allowed:
                zip_state = zst
            else:
                zip_matches_town = bool(town) and miles(zlat, zlng, town[0], town[1]) <= allowed
                if near_town and not zip_matches_town:
                    hide_zip = True
                else:
                    return "retry"
        elif town and not near_town:
            return "retry"
        state = zip_state or rec["s"] or near_state
        if state != near_state and not zindex.state_near(lat, lng, state, STATE_BORDER_MI):
            return "retry"
        st = stats[rec["b"]]
        if zip_state:
            if rec["s"] and rec["s"] != zip_state:
                st.state_fixed += 1              # e.g. "New York, NJ 10001" -> NY
            rec["c"] = rec["c"] or zindex.zips[z][2].title()
        if hide_zip:
            del rec["z"]                         # ZIP contradicts the place: don't show it
            st.zip_hidden += 1
        rec["s"] = state
        rec["la"], rec["lo"] = round(lat, 5), round(lng, 5)
        return "ok"

    checked: list[dict] = []
    retry: list[dict] = []
    for rec in records:
        if place(rec, rec["la"], rec["lo"]) == "ok":
            checked.append(rec)
        elif rec.get("a"):
            retry.append(rec)
        else:
            stats[rec["b"]].bad_coords += 1
    # Points that disagree with their own address: ask the Census Geocoder
    # for the address and keep the store only if that answer fits.
    rows = [(str(i), r["a"], r.get("c") or "", r.get("s") or "", r.get("z") or "") for i, r in enumerate(retry)]
    found = geocode.batch(rows, offline)
    for i, rec in enumerate(retry):
        hit = found.get(str(i))
        if hit and place(rec, hit.lat, hit.lng) == "ok":
            stats[rec["b"]].replaced += 1
            checked.append(rec)
        else:
            stats[rec["b"]].bad_coords += 1

    # De-duplicate (same brand, ~100 m apart). Of listings sharing a site,
    # keep the one open the most hours a week: the store itself beats an
    # in-store pharmacy or a shop next door. Each card shows only its own
    # listing's phone and hours; nothing is copied between listings.
    out: list[dict] = []
    grid: dict[tuple[str, int, int], list[dict]] = collections.defaultdict(list)

    def rank(r: dict) -> tuple:
        return (-weekly_open_minutes(r.get("h")), -bool(r.get("p")), r["b"], r["la"], r["lo"])

    for rec in sorted(checked, key=rank):
        key = (rec["b"], int(rec["la"] * 100), int(rec["lo"] * 100))
        dup = any(
            miles(rec["la"], rec["lo"], other["la"], other["lo"]) < DEDUP_MI
            for di in (-1, 0, 1) for dj in (-1, 0, 1)
            for other in grid.get((rec["b"], key[1] + di, key[2] + dj), ())
        )
        if dup:
            stats[rec["b"]].duplicates += 1
            continue
        grid[key].append(rec)
        out.append(rec)
    out.sort(key=lambda r: (r["b"], r["la"], r["lo"]))
    # In a chain where nearly every listing has a phone or hours, a listing
    # with neither is a placeholder for a store not open yet (IHOP "SWC I-10
    # and Nuevo Hueco Tanks Road" shows "Coming Soon" on IHOP's own site).
    by_brand: dict[str, list[dict]] = collections.defaultdict(list)
    for rec in out:
        by_brand[rec["b"]].append(rec)
    final: list[dict] = []
    for slug, recs in by_brand.items():
        bare = [r for r in recs if not r.get("p") and not r.get("h")]
        no_hours = [r for r in recs if not r.get("h")]
        drop_bare = bare and 1 - len(bare) / len(recs) >= COMPLETE_CHAIN_SHARE
        drop_no_hours = no_hours and 1 - len(no_hours) / len(recs) >= HOURS_CHAIN_SHARE
        for rec in recs:
            if (drop_bare and not rec.get("p") and not rec.get("h")) or (drop_no_hours and not rec.get("h")):
                stats[slug].incomplete += 1
                continue
            final.append(rec)
    for rec in final:
        stats[rec["b"]].kept += 1
        for k in [k for k, v in rec.items() if v in (None, "")]:
            if k not in ("a", "c"):
                del rec[k]
    return final, stats, {sp: c for sp, c in choices.items()}


def derived_states(records: list[dict]) -> dict[str, list[str]]:
    by: dict[str, set] = collections.defaultdict(set)
    for r in records:
        by[r["b"]].add(r["s"])
    return {b: sorted(s) for b, s in by.items()}


def dump_sample(records: list[dict], path) -> None:  # debugging aid
    path.write_text(json.dumps(records[:50], indent=1), encoding="utf-8")
