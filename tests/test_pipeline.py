"""Pipeline tests. Run after a build:  python -m pipeline.build && pytest -q"""
from __future__ import annotations

import glob
import json
import re
from pathlib import Path

import pytest

from pipeline import config, offers as offers_mod
from pipeline.geo import norm_name

ROOT = config.ROOT
DIST = config.DIST


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def data():
    return load("dist/data/offers.json")


@pytest.fixture(scope="session")
def records():
    out = []
    for f in glob.glob(str(DIST / "data/tiles/*.json")):
        if not f.endswith("index.json"):
            out.extend(json.loads(Path(f).read_text(encoding="utf-8")))
    return out


# ---- offers -----------------------------------------------------------------
def test_seed_validates_and_has_130_offers():
    offers = offers_mod.load_offers()
    assert len(offers) == 130
    assert len({o.slug for o in offers}) == 130


def test_overrides_each_have_reason_and_source():
    for ov in load("data/overrides.json")["offers"]:
        assert len(ov["reason"]) >= 10
        assert ov["source_url"].startswith("https://")


def test_time_windows_come_from_overrides_only():
    seed = {o["slug"]: o for o in load("data/seed/offers-2026.json")["offers"]}
    windows = {ov["slug"] for ov in load("data/overrides.json")["offers"] if "time_window" in ov["set"]}
    assert "denny-s" in windows
    assert all("time_window" not in o for o in seed.values())


def test_every_offer_has_an_eligibility_tag():
    emap = load("data/eligibility-map.json")
    assert len(emap["offers"]) == 130
    assert all(row["tags"] for row in emap["offers"])


@pytest.mark.parametrize("text,has,lacks", [
    ("Veterans, active duty & Gold Star families", ["veteran", "active", "gold_star"], ["family"]),
    ("Veterans, service members & spouses", ["veteran", "active", "family"], ["gold_star"]),
    ("All visitors", ["everyone"], []),
    ("Active & retired military", ["active", "retiree"], ["veteran"]),
    ("Veterans, active duty, Reserve & Guard", ["guard_reserve"], []),
])
def test_eligibility_rules(text, has, lacks):
    tags, _ = offers_mod.eligibility_tags(text)
    for t in has:
        assert t in tags
    for t in lacks:
        assert t not in tags


def test_every_offer_links_to_its_source(data):
    seed = {o["slug"]: o for o in load("data/seed/offers-2026.json")["offers"]}
    overrides = {ov["slug"]: ov["set"] for ov in load("data/overrides.json")["offers"]}
    for o in data["offers"]:
        expected = overrides.get(o["id"], {}).get("source_url", seed[o["id"]]["source_url"])
        assert o["src"] == expected
        assert o["src"].startswith("https://")


# ---- brands and locations ---------------------------------------------------
def test_brands_cover_every_offer_and_qids_were_checked():
    doc = load("data/brands.json")
    checked = load("data/wikidata-check.json")["qids"]
    covered = {o for b in doc["brands"].values() for o in b["offers"]} | set(doc["no_store_offers"])
    seed = load("data/seed/offers-2026.json")["offers"]
    assert covered == {o["slug"] for o in seed if o["scope"] != "single_location"}
    for b in doc["brands"].values():
        if b["atp_spiders"]:
            assert b["brand_wikidata"], b["name"]
        for q in b["brand_wikidata"] or []:
            assert checked[q]["ok"], q


def test_records_are_in_us_and_known_brands(records, data):
    assert len(records) > 50_000
    for r in records:
        assert r["s"] in config.STATES
        assert r["b"] in data["brands"]
        assert -15 <= r["la"] <= 72
        assert (-180 <= r["lo"] <= -64) or (144 <= r["lo"] <= 146.5)
        if "p" in r:
            assert re.fullmatch(r"[2-9]\d{2}[2-9]\d{6}", r["p"])


def test_collision_prone_brands_have_only_brand_spider_stores(records):
    # These names collide with towns or other businesses (SPEC 6.2). Only
    # Q-id-matched stores from the brand's own spider may appear.
    doc = load("data/brands.json")["brands"]
    for slug in ("caseys", "main-event", "twin-peaks", "sheetz"):
        assert doc[slug]["brand_wikidata"]
        assert any(r["b"] == slug for r in records)
    for slug in ("eureka", "hacienda", "margaritas", "paisanos", "biscuit-belly", "110-grill"):
        assert not any(r["b"] == slug for r in records), slug


def test_single_places_have_sources():
    for p in load("data/places.json")["places"]:
        assert p["coord_source"] and p["address_source"]
        assert -15 <= p["la"] <= 72


def test_reports_exist():
    cov = (ROOT / "data/coverage.md").read_text(encoding="utf-8")
    assert "## Locations per brand" in cov and "## Test ZIPs" in cov
    assert (ROOT / "data/missing-brands.md").exists()


# ---- lookups ------------------------------------------------------------------
TEST_ZIPS = ["46052", "10001", "78205", "20001", "59301", "87301", "04401", "82001",
             "99701", "96813", "00901", "96910", "00802"]


@pytest.mark.parametrize("z", TEST_ZIPS)
def test_test_zips_resolve(z):
    shard = load(f"dist/data/zip/{z[:3]}.json")
    assert isinstance(shard[z], list)


@pytest.mark.parametrize("st,city", [("in", "lebanon"), ("pr", "san juan"), ("ak", "fairbanks"),
                                     ("gu", "hagatna"), ("vi", "saint thomas"), ("dc", "washington")])
def test_cities_resolve(st, city):
    assert city in load(f"dist/data/city/{st}.json")


def test_fairbanks_zip_point_is_in_town():
    lat, lng = load("dist/data/zip/997.json")["99701"][:2]
    assert abs(lat - 64.84) < 0.2 and abs(lng + 147.72) < 0.5


def test_norm_name():
    assert norm_name("St. Thomas") == "saint thomas"
    assert norm_name("Hagåtña") == "hagatna"
    assert norm_name("Ft Worth") == "fort worth"


# ---- site output -------------------------------------------------------------
def test_pages_and_pages_limits():
    files = [p for p in DIST.rglob("*") if p.is_file()]
    assert len(files) < 20_000
    assert max(p.stat().st_size for p in files) < 25 * 1024 * 1024
    assert len(list((DIST / "state").glob("*/index.html"))) == 56
    assert len(list((DIST / "offer").glob("*/index.html"))) == 130
    for name in ("index.html", "near/index.html", "print/index.html", "about/index.html",
                 "404.html", "sitemap.xml", "robots.txt", "og.png", "sw.js"):
        assert (DIST / name).exists(), name


def test_redirects_and_headers():
    assert "/near/* /near/index.html 200" in (DIST / "_redirects").read_text()
    headers = (DIST / "_headers").read_text()
    assert "/data/*\n  Cache-Control: public, max-age=3600" in headers
    assert "Content-Security-Policy: default-src 'self'" in headers
    assert "/sw.js\n  Cache-Control: no-cache" in headers


def test_no_third_party_scripts_or_images():
    for page in DIST.rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        for src in re.findall(r'<(?:script|img|link)[^>]+(?:src|href)="([^"]+)"', html):
            assert not src.startswith("http") or src.startswith(config.SITE_URL), (page, src)


def test_build_fails_when_pages_limits_exceeded(tmp_path, monkeypatch):
    from pipeline import build
    for i in range(3):
        (tmp_path / f"f{i}.txt").write_text("x" * 10)
    monkeypatch.setattr(config, "MAX_FILES", 3)
    with pytest.raises(SystemExit, match="20,000"):
        build.check_limits(tmp_path)
    monkeypatch.setattr(config, "MAX_FILES", 20_000)
    monkeypatch.setattr(config, "MAX_FILE_BYTES", 5)
    with pytest.raises(SystemExit, match="25 MiB"):
        build.check_limits(tmp_path)


# ---- evaluator round 1: real, public stores in the right place ---------------
def test_no_test_closed_or_staff_only_stores(records):
    from pipeline.locations import NOT_PUBLIC, STREET_NOT_PUBLIC
    for r in records:
        assert not (r.get("n") and NOT_PUBLIC.search(r["n"])), r
        assert not STREET_NOT_PUBLIC.search(r.get("a") or ""), r
    # Texas Roadhouse's QA/test entries on Guam are gone (it has no Guam store).
    assert not any(r["b"] == "texas-roadhouse" and r["s"] == "GU" for r in records)


def test_no_placeholder_phones(records):
    from pipeline.locations import is_placeholder_phone
    for r in records:
        if "p" in r:
            assert not is_placeholder_phone(r["p"]), r
    assert is_placeholder_phone("5555555555") and is_placeholder_phone("7667676767")
    assert not is_placeholder_phone("7654827644")


def test_stores_sit_near_their_zip_and_show_its_state(records):
    import math
    from pipeline.locations import MIN_ZIP_ALLOWANCE_MI, ZIP_SLACK_MI, miles
    zips, areas = {}, {}
    for f in glob.glob(str(DIST / "data/zip/*.json")):
        zips.update({k: v for k, v in json.loads(Path(f).read_text(encoding="utf-8")).items() if isinstance(v, list)})
    import zipfile
    with zipfile.ZipFile(config.CACHE / "census" / "2025_Gaz_zcta_national.zip") as z:
        lines = z.read(z.namelist()[0]).decode("utf-8").splitlines()
    head = lines[0].split("|")
    for ln in lines[1:]:
        row = dict(zip(head, ln.split("|")))
        areas[row["GEOID"]] = float(row["ALAND_SQMI"])
    for r in records:
        z = r.get("z")
        if z in zips:
            zl = zips[z]
            allowed = max(MIN_ZIP_ALLOWANCE_MI, math.sqrt(areas.get(z, 0) / math.pi) + ZIP_SLACK_MI)
            assert miles(r["la"], r["lo"], zl[0], zl[1]) <= allowed + 0.01, r
            assert r["s"] == zl[3], r


# ---- evaluator round 2 -------------------------------------------------------
@pytest.mark.parametrize("name", [
    "Granbury, TX (Open 12/7)", "Vero Beach, FL (Opens December 2026)", "EMPLOYEES ONLY-575 Washington",
    "Milstein staff & visitors only", "FIT- PRIVATE LOCATION SCHOOL O", "Pentagon - Restricted Access",
    "JHH Weinberg Bldg - Secure Acc", "SECUREACCESS Bath & Body Works", "NCL Jade", "RCI Oasis of the Seas",
    "JPMC EMPLOYEES ONLY (NO ACCESS", "HMSHost Corporate Office", "Hilton Headquarters", "LV Petroleum HQ",
    "M&S Catering at The Museum of Flight"])
def test_not_public_names_caught(name):
    from pipeline.locations import NOT_PUBLIC
    assert NOT_PUBLIC.search(name)


@pytest.mark.parametrize("name", ["Little Rd & Office Park", "Resorts World Box Office", "Now Open- Camp Verde",
                                  "Township Center", "Shipyard Plaza", "I-10 & Litchfield"])
def test_public_names_kept(name):
    from pipeline.locations import NOT_PUBLIC
    assert not NOT_PUBLIC.search(name)


def test_not_public_source_fields():
    from pipeline.locations import not_public
    assert not_public({"office": "company", "name": "Publix Office"})
    assert not_public({"start_date": "2026-12-07", "branch": "Livonia"})
    assert not not_public({"start_date": "2026-11-09", "branch": "Corpus Christi"})
    assert not_public({"addr:street_address": "790 state route 7, TEMP ADDRESS"})
    assert not_public({"addr:street_address": "45343 Alton Lane, (Subject to Change)"})
    assert not_public({"addr:street_address": "207 Sabal Loop, Address to change"})
    assert not_public({"addr:street_address": "Shirley Memorial Hwy, Pentagon"})
    assert not not_public({"addr:street_address": "1100 S. Hayes St.", "branch": "Fashion Center at Pentagon City"})
    assert not not_public({"addr:street_address": "3286 Pentagon Blvd"})
    assert not_public({"addr:street_address": "2201 C St NW, US Dept of State"})
    assert not_public({"addr:street_address": "1400 Jefferson Dr SW, USDA"})
    assert not_public({"addr:street_address": "101 Independence Ave SE, Library of Congress"})
    assert not not_public({"addr:street_address": "113 Courthouse Rd"})
    assert not not_public({"addr:street_address": "607 W Government St"})
    assert not_public({"website": "https://www.charleys.com/locations/coming-soon-outlet-shoppes-at-el-paso-canutillo-tx/"})
    assert not_public({"image": "https://www.in-n-out.com/x/large/temp-closed.png"})
    assert not_public({"branch": "Brownsburg", "phone": "x"}, ("opening_hours", "website"))


def test_points_agree_with_their_town(records, data):
    # A store whose own town is known must sit within 25 miles of it, unless it
    # sits within its ZIP's allowance (big rural ZIPs).
    from pipeline.locations import CITY_ALLOWANCE_MI, miles
    from pipeline.geo import norm_name
    cities = {}
    for st in config.STATES:
        cities[st] = load(f"dist/data/city/{st.lower()}.json")
    far = []
    for r in records:
        town = cities.get(r["s"], {}).get(norm_name(r.get("c") or ""))
        if town and miles(r["la"], r["lo"], town[0], town[1]) > CITY_ALLOWANCE_MI and "z" not in r:
            far.append(r)
    assert far == []
    names = {(r["b"], r.get("a")) for r in records}
    assert ("bjs-restaurant", "15081 South La Grange Road") not in names or any(
        r["b"] == "bjs-restaurant" and r.get("a") == "15081 South La Grange Road" and r["s"] == "IL" for r in records)
    assert not any(r["b"] == "texas-roadhouse" and "Open 12/7" in (r.get("n") or "") for r in records)


# ---- evaluator round 4 -------------------------------------------------------
def test_address_formats_parse():
    from pipeline.locations import parse_full, street_of, ZIP_RE
    assert parse_full("1313 Hwy 65 N, Harrison, AR, 72601") == ("1313 Hwy 65 N", "Harrison", "AR", "72601")
    assert parse_full("6801 Hollywood Blvd, Suite 105, Los Angeles, CA, 90028, US")[1:] == ("Los Angeles", "CA", "90028")
    assert street_of({"addr:full": "5260 Belt Line Rd.", "addr:city": "Dallas"}) == "5260 Belt Line Rd."
    assert ZIP_RE.search("170505251").group(1) == "17050"


def test_tcby_and_twin_peaks_have_full_addresses(records):
    tcby = [r for r in records if r["b"] == "tcby"]
    tp = [r for r in records if r["b"] == "twin-peaks"]
    assert tcby and all(r.get("c") and r.get("a") for r in tcby)
    assert sum(1 for r in tcby if r.get("z")) >= 0.9 * len(tcby)
    assert tp and all(r.get("a") for r in tp)
    # TCBY "Harrison" sits in Harrison, AR (or is gone), never near Clinton.
    from pipeline.locations import miles
    for r in tcby:
        if r.get("c") == "Harrison" and r["s"] == "AR":
            assert miles(r["la"], r["lo"], 36.23, -93.11) < 15


# ---- evaluator round 5 -------------------------------------------------------
def test_workplace_hours_rule():
    from pipeline.locations import workplace_hours as w
    assert w({"opening_hours": "Tu-Th 07:30-14:45", "phone": "8042841566"})      # Capital One campus
    assert w({"opening_hours": "Mo-Fr 07:30-14:45", "phone": "7326084423"})      # Verizon HQ
    assert w({"opening_hours": "Mo-Fr 07:00-16:30"})                              # Sanofi, no phone
    assert not w({"opening_hours": "Mo 11:00-22:00", "phone": "1"})               # source glitch, not weekday-only
    assert not w({"opening_hours": "Mo-Fr 09:00-17:00", "phone": "1"})            # Walgreens pharmacy hours
    assert not w({"opening_hours": "Mo-Su 05:00-21:00", "phone": "1"})


def test_store_feature_not_pumps_or_pharmacy(records):
    casey = [r for r in records if r["b"] == "caseys" and r.get("a") == "723 Indianapolis Ave"]
    assert casey and casey[0]["h"] == "Mo-Su 04:00-22:00"          # the store, not the 24/7 pumps
    names = {(r["b"], r.get("n") or "") for r in records}
    assert not any(b == "publix" and "Moffitt" in n for b, n in names)
    assert sum(1 for r in records if r["b"] == "hy-vee" and r.get("c") == "Lamoni") == 1
    from pipeline.locations import not_public
    assert not_public({"addr:street_address": "80 County Rd, USPS Sorting Facility"})


# ---- evaluator round 6 -------------------------------------------------------
def test_weekly_open_minutes():
    from pipeline.locations import weekly_open_minutes as w
    assert w("24/7") == 7 * 24 * 60
    assert w("Mo-Su 07:00-22:00") > w("Mo-Fr 09:00-19:00; Sa 09:00-16:00; Su closed")


def test_each_card_is_the_store_listing(records):
    by = lambda b, a: [r for r in records if r["b"] == b and (r.get("a") or "").startswith(a)]
    fl = by("food-lion", "3808 Guess")
    assert fl and fl[0]["p"] == "9194710817" and fl[0]["h"] == "Mo-Su 07:00-22:00"
    assert not any(r["b"] == "caseys" and "TOBACCO" in (r.get("n") or "").upper() for r in records)
    assert not any(r["b"] == "hy-vee" and (r.get("n") or "") in ("Spring Valley", "St. Charles", "Preston") for r in records)
    from pipeline.locations import open_days_and_last_close
    for r in records:
        if r["b"] in ("food-lion", "hy-vee") and r.get("h") and r["h"] != "24/7":
            days, _ = open_days_and_last_close(r["h"])
            assert not days or len(days) == 7, r


# ---- evaluator round 7 -------------------------------------------------------
def test_no_placeholder_listings_in_complete_chains(records):
    from pipeline.locations import COMPLETE_CHAIN_SHARE
    import collections
    by = collections.defaultdict(list)
    for r in records:
        by[r["b"]].append(r)
    for b, rs in by.items():
        bare = [r for r in rs if not r.get("p") and not r.get("h")]
        if bare:
            assert 1 - len(bare) / len(rs) < COMPLETE_CHAIN_SHARE, b
    assert not any(r["b"] == "ihop" and (r.get("a") or "").startswith("SWC I-10") for r in records)


def test_food_lion_pharmacy_listings_gone(records):
    fl = [r for r in records if r["b"] == "food-lion" and "Hughes" in (r.get("a") or "") and r.get("c") == "Elizabeth City"]
    assert len(fl) == 1 and fl[0]["p"] == "2523311301"
