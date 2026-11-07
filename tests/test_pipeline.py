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
