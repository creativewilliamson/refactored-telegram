"""ZIP and city lookups, built from public Census and ZIP data.

Sources (downloaded to data/cache/ by pipeline.fetch):
- Census Gazetteer 2025, ZCTA file: ZIP centroids (internal points).
- Census Gazetteer 2025, Places file: city/town/CDP internal points.
- `zipcodes` dataset (MIT licence, github.com/seanpianka/zipcodes): fills
  ZIPs that aren't ZCTAs (PO boxes, Guam, Virgin Islands, American Samoa,
  Northern Mariana Islands) and gives each ZIP its postal city and state.

Output shards (fetched by the browser by index only):
- dist/data/zip/{zip3}.json   {"46052": [lat, lng, "Lebanon", "IN"], "09001": "M"}
- dist/data/city/{st}.json    {"lebanon": [lat, lng, "Lebanon"]}
"""
from __future__ import annotations

import bz2
import collections
import json
import math
import re
import unicodedata
import zipfile
from dataclasses import dataclass

from . import config
from .fetch import cached

GAZ = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/"
ZCTA_FILE = "2025_Gaz_zcta_national.zip"
PLACE_FILE = "2025_Gaz_place_national.zip"
ZIPCODES_URL = "https://raw.githubusercontent.com/seanpianka/zipcodes/master/crates/zipcodes/src/zips.json.bz2"
ZIPCODES_LICENSE_URL = "https://raw.githubusercontent.com/seanpianka/zipcodes/master/LICENSE.txt"

MILITARY_MAIL = {"AA", "AE", "AP"}
ZCTA_POSTAL_MAX_MI = 15
SOURCES = {
    "zcta": GAZ + ZCTA_FILE,
    "places": GAZ + PLACE_FILE,
    "zipcodes": ZIPCODES_URL,
}

PLACE_SUFFIX = re.compile(
    r"\s+(city and borough|consolidated government|metropolitan government|metro government|"
    r"unified government|urban county|zona urbana|comunidad|municipality|corporation|"
    r"city|town|village|borough|CDP)$"
)
FIRST_TOKEN = {"st": "saint", "ste": "sainte", "ft": "fort", "mt": "mount", "pt": "point"}


def norm_name(s: str) -> str:
    """Normalize a place name for lookup. Mirrored in static/js/near.js."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = s.replace("&", " and ").replace("'", "").replace("’", "").replace(".", " ")
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    toks = s.split()
    if toks and toks[0] in FIRST_TOKEN:
        toks[0] = FIRST_TOKEN[toks[0]]
    return " ".join(toks)


def _miles(lat1, lng1, lat2, lng2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2)
    return 2 * 3958.8 * math.asin(min(1.0, math.sqrt(a)))


def _read_gazetteer(path) -> list[dict]:
    with zipfile.ZipFile(path) as z:
        name = z.namelist()[0]
        text = z.read(name).decode("utf-8", errors="replace")
    lines = text.splitlines()
    header = [h.strip() for h in lines[0].split("|")]
    return [dict(zip(header, (v.strip() for v in ln.split("|")))) for ln in lines[1:] if ln.strip()]


@dataclass
class Geo:
    zips: dict[str, list]          # zip -> [lat, lng, city, state] or "M"
    cities: dict[str, dict]        # state -> {key: [lat, lng, display]}
    counts: dict[str, int]
    areas: dict[str, float]        # ZCTA land area, square miles


def load(offline: bool = False) -> Geo:
    zcta_path = cached(SOURCES["zcta"], f"census/{ZCTA_FILE}", offline=offline)
    place_path = cached(SOURCES["places"], f"census/{PLACE_FILE}", offline=offline)
    zc_path = cached(ZIPCODES_URL, "zipcodes/zips.json.bz2", offline=offline)
    cached(ZIPCODES_LICENSE_URL, "zipcodes/LICENSE.txt", offline=offline)

    zcta = {}
    areas: dict[str, float] = {}
    for r in _read_gazetteer(zcta_path):
        zcta[r["GEOID"]] = (float(r["INTPTLAT"]), float(r["INTPTLONG"]))
        areas[r["GEOID"]] = float(r.get("ALAND_SQMI") or 0)

    zc = json.loads(bz2.decompress(zc_path.read_bytes()))
    postal: dict[str, dict] = {z["zip_code"]: z for z in zc}

    # zip3 -> most common state, for ZCTAs the postal list doesn't know.
    zip3_state: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for z in zc:
        if z["state"] in config.STATES:
            zip3_state[z["zip_code"][:3]][z["state"]] += 1

    zips: dict[str, list | str] = {}
    moved = 0
    for code in sorted(set(zcta) | set(postal)):
        p = postal.get(code)
        state = p["state"] if p else None
        if state in MILITARY_MAIL:
            zips[code] = "M"
            continue
        if state is None:
            c = zip3_state.get(code[:3])
            state = c.most_common(1)[0][0] if c else None
        if state not in config.STATES:
            continue  # FM, MH, PW (freely associated states) or unknown
        postal_pt = None
        if p and p.get("lat") and p.get("long") and float(p["lat"]) != 0.0:
            postal_pt = (float(p["lat"]), float(p["long"]))
        if code in zcta:
            lat, lng = zcta[code]
            # Huge rural ZCTAs (99701 Fairbanks: 180 mi off) put their
            # internal point far from the town. Use the postal town point then.
            if postal_pt and _miles(lat, lng, *postal_pt) > ZCTA_POSTAL_MAX_MI:
                lat, lng = postal_pt
                moved += 1
        elif postal_pt:
            lat, lng = postal_pt
        else:
            continue
        city = p["city"] if p else ""
        zips[code] = [round(lat, 4), round(lng, 4), city, state]

    # Cities: Census places first, then postal city names they don't cover.
    cities: dict[str, dict] = collections.defaultdict(dict)
    best: dict[tuple[str, str], tuple] = {}
    for r in _read_gazetteer(place_path):
        st = r["USPS"]
        if st not in config.STATES:
            continue
        raw = r["NAME"].replace(" (balance)", "")
        name = PLACE_SUFFIX.sub("", raw).strip()
        incorporated = r.get("FUNCSTAT") == "A" or r.get("LSAD") not in ("57", "55", "62")
        rank = (1 if incorporated else 0, int(r.get("ALAND") or 0))
        lat, lng = float(r["INTPTLAT"]), float(r["INTPTLONG"])
        names = [name]
        for sep in ("-", "/", ","):
            if sep in name:
                names.append(name.split(sep)[0].strip())
        for i, n in enumerate(names):
            key = norm_name(n)
            if not key:
                continue
            r_rank = rank if i == 0 else (rank[0] - 2, rank[1])
            cur = best.get((st, key))
            if cur is None or r_rank > cur[0]:
                best[(st, key)] = (r_rank, [round(lat, 4), round(lng, 4), n])
    for (st, key), (_, val) in best.items():
        cities[st][key] = val

    by_city: dict[tuple[str, str], list] = collections.defaultdict(list)
    for code, v in zips.items():
        if isinstance(v, list) and v[2]:
            by_city[(v[3], v[2])].append(v)
    added = 0
    for (st, name), vals in by_city.items():
        key = norm_name(name)
        if key and key not in cities[st]:
            lat = sum(v[0] for v in vals) / len(vals)
            lng = sum(v[1] for v in vals) / len(vals)
            cities[st][key] = [round(lat, 4), round(lng, 4), name.title() if name.isupper() else name]
            added += 1

    counts = {
        "zips": sum(1 for v in zips.values() if isinstance(v, list)),
        "zcta": len(zcta),
        "military_mail": sum(1 for v in zips.values() if v == "M"),
        "cities": sum(len(v) for v in cities.values()),
        "postal_cities_added": added,
        "zcta_point_replaced_by_postal_town": moved,
    }
    return Geo(zips=zips, cities=dict(cities), counts=counts, areas=areas)


def write_shards(geo: Geo, dist) -> int:
    """Write ZIP and city shards; return the number of files written."""
    zdir = dist / "data" / "zip"
    cdir = dist / "data" / "city"
    zdir.mkdir(parents=True, exist_ok=True)
    cdir.mkdir(parents=True, exist_ok=True)
    shards: dict[str, dict] = collections.defaultdict(dict)
    for code, v in geo.zips.items():
        shards[code[:3]][code] = v
    n = 0
    for z3, data in shards.items():
        (zdir / f"{z3}.json").write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False),
                                         encoding="utf-8")
        n += 1
    for st in config.STATES:
        data = dict(sorted(geo.cities.get(st, {}).items()))
        (cdir / f"{st.lower()}.json").write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False),
                                                 encoding="utf-8")
        n += 1
    return n


def zip_state_index(geo: Geo) -> dict[str, list]:
    return {k: v for k, v in geo.zips.items() if isinstance(v, list)}

