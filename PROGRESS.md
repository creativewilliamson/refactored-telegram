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
