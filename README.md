# VetsEatFree: Veterans Day 2026 offers near you

A free, static website. A veteran types a ZIP code, "City, ST" or taps "Use
my location", and sees Veterans Day 2026 offers at real nearby places, with
distance, address, phone, directions and a link to each offer's source.
The ZIP and location never leave the visitor's phone: every lookup reads
static files by index and all distance math runs in the browser.

## Start it

```powershell
.\start.ps1
```

Then open http://localhost:8095/. The first start downloads public store
and Census data into `data\cache\` (a minute or two); later starts reuse it.

## Commands

| What | Command |
|---|---|
| Start (build data + pages, serve on :8095) | `.\start.ps1` |
| Data + build only (writes `dist/`) | `docker compose run --rm build` |
| Build offline from the cache | `docker compose run --rm build python -m pipeline.build --offline` |
| Pipeline tests (pytest) | `docker compose run --rm build python -m pytest -q tests` |
| Browser tests (Playwright + axe) | `docker compose --profile test run --rm e2e` |
| Lighthouse mobile audits | `docker compose --profile test run --rm e2e sh tools/lighthouse.sh` |
| Serve `dist/` only | `docker compose up -d web` |
| Stop | `docker compose down` |
| Trace random stores to their source | `docker compose run --rm build python tools/spot_check.py 20` |
| Deploy (J.Will only) | see `DEPLOY.md` |

## How it fits together

- `data/seed/offers-2026.json`: the 130 offers. Never edited.
- `data/overrides.json`: corrections and time windows, each with a reason
  and a source.
- `data/brands.json`: each chain's Wikidata Q-id and All The Places spider.
- `data/places.json`: single-location offers (museums, zoos) with sources.
- `data/location-exclusions.json`: individual store listings the chain's own
  page shows as closed, each with a reason and the page that proves it.
- `pipeline/`: Python. `build.py` runs everything: offers -> eligibility
  tags (`data/eligibility-map.json`) -> store locations from All The Places,
  kept only when in the U.S./territories and matching the brand's Q-id ->
  ZIP and city lookups from Census files -> map tiles -> every page via
  Jinja2 templates -> `data/coverage.md` and `data/missing-brands.md`.
- `pipeline/static/`: the plain JavaScript and CSS for the browser.
- `pipeline/serve.py`: a tiny static server that honors `_redirects` and
  `_headers` like Cloudflare Pages.
- `dist/`: the finished site (not committed). Upload this to Pages.

## Data sources

All public: the offer seed; All The Places (alltheplaces.xyz) store data;
Wikidata; U.S. Census Gazetteer files and the Census Geocoder; the
`zipcodes` dataset (MIT). Business names appear as plain text only. No
logos, no tracking, no cookies.
