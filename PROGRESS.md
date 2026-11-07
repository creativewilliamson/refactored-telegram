# Progress

Run 1: planned.
- Planner note: stack is Python (pipeline + Jinja2 static pages) with plain
  JS in the browser, served locally by Docker, deployed by J.Will to
  Cloudflare Pages. Public offer data is an approved exception to "sample
  data only" (see GOAL.md Constraints).

## Run 1: setup (2026-11-07)
What I took from `reference\` (README + SPEC; no images yet):
- Layout: first screen is one line saying what the site does, the search box
  and "Use my location"; then "Before you go", how it works, a 56-entry state
  list. Results page = location cards (closest first), an "Everywhere" section,
  and "Find nearest" map links for chains with no store list.
- Look: plain, high-contrast, navy + white + one red accent, light and dark
  themes, system fonts, 18px body, 48px tap targets, copy for a 70-year-old.
- Pages: /, /near/, /state/{st}/ x56, /offer/{slug}/, /print/, /about/,
  sitemap, robots, text-only OG image, _headers and _redirects.
- Data: 130 seed offers (108 national, 9 regional, 13 single-location).
  Stores from All The Places filtered by country + brand:wikidata.

Decisions:
- Stack: Python 3.12 (pipeline + Jinja2), plain JS/CSS, no framework.
  Docker: `build` service (one-shot, writes ./dist) + `web` service (a small
  Python static server, pipeline/serve.py, that honors _redirects/_headers
  and gzips like Pages does) on 127.0.0.1:8095.
- Privacy: searching never puts the ZIP/city/coords in a request. The home
  page hands the query to /near/ through sessionStorage; /near/ keeps the
  last search in localStorage. Only share links (/near/46052) and the
  /print/?zip= form carry a ZIP, because the visitor chose to share/print.
  In-app Print links use /print/#zip=... (fragments never leave the device).
- Strict CSP in _headers (self only; the one inline script is hashed).
- ATP: latest run is 2026-10-24. Per-spider files live at
  https://alltheplaces-data.openaddresses.io/runs/<run>/output/<spider>.geojson
  (confirmed). Several big spiders returned 0 in the latest run (Olive
  Garden, Red Lobster, Red Robin, Shake Shack, LongHorn, Tractor Supply,
  Food Lion, Yard House, Pilot Flying J, Charleys, Eat'n Park); for those the
  pipeline uses the newest earlier run where the spider was healthy.

## F01: home page (passes) + data pipeline
- Built the whole pipeline: offers (pydantic, overrides, eligibility tags ->
  data/eligibility-map.json), brands.json (114 brands, Q-ids checked on
  wikidata.org -> data/wikidata-check.json), All The Places stores (81,174
  kept), Census/zipcodes ZIP + city shards, 0.5-degree tiles, 193 pages.
  `python -m pipeline.build` (~40 s); `--quick` reuses data for page work.
- Home: one-line purpose, ZIP/City search, Use my location, Before you go,
  How it works, 56-state list (2 columns on phones). Evidence: evidence/F01.png.
- Decisions:
  - 10 ATP spiders have no brand:wikidata on any store (Eureka!, Eddie
    Merlot's, Perry's, WOB, El Chico, Aspen Creek, Biscuit Belly, Viva
    Chicken, Polly's Pies, VA facilities). SPEC 6.2 keeps only Q-id matches,
    so these show a "Find nearest" link (listed in data/missing-brands.md).
  - Stores with an address but no coordinates (Hy-Vee, Lucille's, 7 Brew...)
    are placed with the public U.S. Census Geocoder; unmatched ones dropped.
    7 Brew's spider only has store-page URLs (locations.7brew.com/st/city/
    street): the address is read from the URL and kept only on a Census
    match, showing the Census-matched address. 462 of 561 placed.
  - Census ZCTA internal points can be far from town in huge rural ZIPs
    (99701 Fairbanks: 180 mi). When the ZCTA point is >15 mi from the postal
    town point (zipcodes data), the postal town point is used (324 ZIPs).
  - Single places (data/places.json): address/phone only from official
    sites (or Wikidata where the official site refused automated reads);
    coordinates from the Census Geocoder or Wikidata. Yorktown museum and
    both Old Town Trolley offers have no sourced street address: they use
    the Census town point and the card says "about N miles" and that the
    exact spot is on the offer page. Nothing guessed.
  - Native Python on this PC needs `python -s` (a user-site entry points at
    a missing E: drive, outside this project). Docker is unaffected.
- Next: F02 evidence (results for 46052).

## F02: results for a ZIP (passes)
- Search from home -> /near/ (no ZIP in the URL or any request). 46052: 353
  places within 25 mi, nearest first; all 50 shown cards have name, offer,
  date chip, address, miles, call link or "No phone listed", Google + Apple
  directions, Offer details; Denny's shows "5 a.m.-noon"; Show more at 50.
- Stacked offers: only Hy-Vee has two offers; nearest Hy-Vee to 46052 is
  135 mi away, so verified with 50309 (Des Moines): both offers on one card.
  Evidence: evidence/F02.png, evidence/F02-stacked.png.
- Next: F03 (data provenance checks + Docker build via start.ps1).

## F03: real places only (passes)
- tools/spot_check.py traces random stores in dist/ back to the cached ATP
  feature (spider, run, ref) or Census Geocoder match and checks brand Q-id
  + state + coordinates: 10/10 and 40/40 OK.
- All 33 distinct source links load in a real browser except Smashburger's
  (true 404). Override in data/overrides.json points it at the VA News 2026
  list, which names the offer; offer wording unchanged.
- 10001: three Offer details links open exactly their source_url; 38 chains
  without store data show "Find nearest" (Google Maps search, brand + town).
- tests/test_pipeline.py: 39 pytest checks (seed, overrides, tags, brands,
  US-only records, collision-prone brands, lookups, Pages limits, headers).
- Evidence: evidence/F03.png, evidence/F03-source.png. Next: F04.

## F04: Everywhere + special places (passes)
- Every results page has "Everywhere" (Grace for Vets, National Parks).
- Decision: single-location offers get their own section, "Museums and
  special places within 150 miles", above the store cards and always listed
  in full (they used to sit in the store list and Yorktown hid behind
  "Show more"). 23185: Colonial Williamsburg 2.2 mi, Jamestown 4.8 mi,
  Yorktown museum about 10 mi, Mount Vernon 104 mi.
- Evidence: evidence/F04.png, evidence/F04-everywhere.png. Next: F05.

## F05: radius + auto-widen (passes)
- 46052 radius 10/25/50/100 -> 21/353/777/1333 stores. A radius the visitor
  picks is respected (no auto-widen; a "Show up to N miles" button appears
  when under 10). Fresh searches widen 25 -> 50 -> 100 while under 10 places.
- 59301 Miles City: widens to 100 mi, 5 stores, message shown.
- Evidence: evidence/F05.png. Next: F06 (13 test ZIPs).
