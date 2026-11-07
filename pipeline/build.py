"""Build the whole static site into dist/.

Usage: python -m pipeline.build [--offline]

1. Offers: validate the seed, merge data/overrides.json, tag eligibility.
2. Lookups: Census ZIP/places + zipcodes (cached in data/cache/).
3. Locations: All The Places, filtered by country and brand:wikidata.
4. Write dist/data (offers, ZIP and city shards, tiles), render every page.
5. Reports (data/coverage.md, data/missing-brands.md) and Pages-limit check.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pickle
import sys
import time

from . import (config, dataset, geo, locations, offers as offers_mod, og, pages,
               reports, site, tiles, wikidata)

HTML_ROUTES = ["/", "/near/*", "/state/*", "/offer/*", "/print/*", "/about/*", "/404.html"]

REDIRECTS = """# Shared search links (/near/46052) reopen the results page,
# which reads the ZIP from the address bar.
/near/* /near/index.html 200
"""


def headers_file(csp: str) -> str:
    # Each Cache-Control lives on exactly one rule: Cloudflare Pages joins
    # duplicate headers from overlapping rules with commas.
    parts = [f"""/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: no-referrer
  Permissions-Policy: geolocation=(self), camera=(), microphone=()
  Content-Security-Policy: {csp}
"""]
    for route in HTML_ROUTES:
        parts.append(f"{route}\n  Cache-Control: public, max-age=300\n")
    parts.append("/sw.js\n  Cache-Control: no-cache\n")
    parts.append("/data/*\n  Cache-Control: public, max-age=3600\n")
    parts.append("/css/*\n  Cache-Control: public, max-age=31536000, immutable\n")
    parts.append("/js/*\n  Cache-Control: public, max-age=31536000, immutable\n")
    return "\n".join(parts)


def write_json(path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


def check_limits(dist) -> tuple[int, int]:
    count, biggest = 0, 0
    for root, _dirs, files in os.walk(dist):
        for f in files:
            count += 1
            size = os.path.getsize(os.path.join(root, f))
            biggest = max(biggest, size)
            if size > config.MAX_FILE_BYTES:
                raise SystemExit(f"BUILD FAILED: {f} is {size} bytes (Pages limit is 25 MiB)")
    if count >= config.MAX_FILES:
        raise SystemExit(f"BUILD FAILED: {count} files (Pages limit is 20,000)")
    return count, biggest


def build(offline: bool = False, quick: bool = False) -> None:
    t0 = time.time()
    log = lambda msg: print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)  # noqa: E731

    offers = offers_mod.load_offers()
    offers_mod.write_eligibility_map(offers)
    log(f"offers: {len(offers)} valid")

    brands_doc = dataset.load_brands()
    check = wikidata.check_brands(brands_doc["brands"], offline or quick)
    bad = [q for q, v in check.items() if not v.get("ok")]
    if check and not (offline or quick):
        wikidata.write_check(check)
    if bad and not (offline or quick):
        raise SystemExit(f"BUILD FAILED: Q-ids not found on wikidata.org: {bad}")

    state_path = config.CACHE / "_last_build.pickle"
    if quick and state_path.exists():
        g, records, stats, choices = pickle.loads(state_path.read_bytes())
        log("quick: reusing ZIP and store data from the last full build")
    else:
        g = geo.load(offline)
        log(f"geo: {g.counts}")
        records, stats, choices = locations.build(brands_doc["brands"], g.zips, offline)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_bytes(pickle.dumps((g, records, stats, choices)))
    kept = {b: s.kept for b, s in stats.items()}
    log(f"locations: {len(records)} stores")

    places = [{k: v for k, v in p.items() if k not in ("address_source", "coord_source")}
              for p in dataset.load_places()]
    derived = locations.derived_states(records)
    data = dataset.build_offers_json(offers, brands_doc, kept, derived, places)
    data["built"] = dt.date.today().isoformat()
    data["verified"] = max(o["checked"] for o in data["offers"])

    dist = config.DIST
    site.clean_dist(dist)
    assets = site.Assets(dist)
    assets.publish()
    write_json(dist / "data" / "offers.json", data)
    nshards = geo.write_shards(g, dist)
    tile_files, tile_index = tiles.build(records)
    ntiles = tiles.write(tile_files, tile_index, dist)
    log(f"data: {nshards} ZIP/city shards, {ntiles} tile files")

    npages = pages.render_all(dist, assets, data, records, g)
    og.write_image(dist / "og.png")
    log(f"pages: {npages}")

    csp = ("default-src 'self'; script-src 'self' " + site.csp_hash(site.JS_FLAG_SCRIPT)
           + " " + site.csp_hash(site.NEAR_PRELOAD_SCRIPT)
           + "; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
           "form-action 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'")
    (dist / "_headers").write_text(headers_file(csp), encoding="utf-8", newline="\n")
    (dist / "_redirects").write_text(REDIRECTS, encoding="utf-8", newline="\n")

    reports.write("coverage.md", reports.coverage(brands_doc, stats, choices, records, g.zips, data, places))
    reports.write("missing-brands.md", reports.missing_brands(brands_doc, data))
    notes = []
    for o in data["offers"]:
        if o["scope"] == "regional" and o["kind"] == "stores":
            seed_states = next(x.states for x in offers if x.slug == o["id"]) or []
            if sorted(seed_states) != sorted(o.get("states") or []):
                notes.append(f"{o['name']}: seed {sorted(seed_states)} -> stores in {o['states']}")
    if notes:
        log("regional states derived from store data (differ from seed):\n  " + "\n  ".join(notes))

    count, biggest = check_limits(dist)
    log(f"Cloudflare Pages check: {count} files (limit 20,000), largest {biggest / 1024:.0f} KB (limit 25 MiB). OK")
    log("Built dist/")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="use data/cache only; never download")
    ap.add_argument("--quick", action="store_true",
                    help="developer shortcut: reuse the last full build's ZIP and store data")
    args = ap.parse_args()
    try:
        build(offline=args.offline, quick=args.quick)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - report and fail the build
        print(f"BUILD FAILED: {exc}", file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    main()
