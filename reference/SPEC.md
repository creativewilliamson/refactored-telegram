# SPEC — Veterans Day Finder

Site name: Vet Day Deals (renamed in run 2; was VetsEatFree, which is kept
for a later app and must not appear on this site). Planned URL:
https://vetdaydeals.pages.dev. Cloudflare Pages project name: vetdaydeals.
Contact email: none yet (hide the "report a problem" email line).

## 1. Mission and hard rules
Every veteran and service member in the country, including rural vets,
older vets on old phones, and vets with no smartphone, can find Veterans
Day offers near them in under 30 seconds. Free forever.
1. Free: no login, no ads, no paywall, no email required to see anything.
2. Private: the visitor's ZIP or location never leaves their device. All
   distance math runs in the browser. No cookies. No analytics code (J.Will
   may turn on Cloudflare Web Analytics at deploy time).
3. Nationwide: all 50 states, DC, PR, GU, VI, AS and MP return a useful
   result. If nothing is near, widen the radius and say so.
4. No logos or brand images. Business names as plain text. Footer says
   the site isn't affiliated with any listed business.
5. Never invent an offer, location, phone number or hour. Every offer
   links to its source.
6. Never edit offer wording in data/seed/. Corrections go in
   data/overrides.json, each with `reason` and `source_url`.
7. Accessibility: WCAG 2.2 AA; 18px minimum body text; 48px minimum tap
   targets; works at 200% zoom, with a screen reader, and by keyboard.
8. Speed: home page under 60 KB transferred (gzipped). Results usable
   within 3 s on Slow 4G.
9. Fully static output in dist/. No server for search.
10. Footer on every page: Veterans Crisis Line "Call 988, press 1 · Text
    838255".

## 2. Stack
- Python 3 data pipeline under `pipeline/`; Jinja2 templates render every
  page to static HTML in `dist/`.
- Plain JavaScript (no framework, no build step needed) and plain CSS;
  system fonts only. Target Safari 14 and Chrome 90.
- Tests: pytest for the pipeline; Playwright (with axe) for the browser.
- Docker: one service builds data and pages, one serves dist/ at
  http://localhost:8095 as plain static files (never 8080: another
  project uses it) (honor _redirects locally,
  or serve /near/ for /near/*).
- Document the commands in README.md: data, build, test, serve.

## 3. What the visitor can do
1. Enter a 5-digit ZIP, "City, ST", or a state name; or tap "Use my
   location" (ask only on tap).
2. See nearby locations sorted by distance. Each card: business name, the
   offer, dates and time window, street address, miles, phone (tap to
   call), Google Maps and Apple Maps directions, "Offer details" source
   link. A location with several offers shows them stacked on one card.
3. Filter by category (meals, coffee & treats, shopping, haircuts & car
   care, attractions), free only, and who qualifies (veteran, active duty,
   Guard/Reserve, retiree, spouse or family, Gold Star).
4. Radius 10 / 25 / 50 / 100 miles, default 25. Fewer than 10 found:
   widen 25 → 50 → 100 and say "Showing up to 100 miles because few
   places are close by."
5. "Everywhere" offers with no store (National Parks, etc.) in their own
   section; single-location offers within 150 miles with distance.
6. Large-print list: /print/?zip=46052&r=25. 16pt+, one column, no
   images; name, offer, address, phone, distance.
7. Share: /near/46052 and /near/?city=lebanon&st=IN reopen the search.
8. Without JavaScript: home page state list links to pre-rendered
   /state/{st}/ pages.

## 4. Pages
- `/` search box, "Use my location", state list, how it works, "Before
  you go" (bring proof of service; call ahead; dine-in rules).
- `/near/` results (client-rendered). `_redirects`:
  `/near/* /near/index.html 200`.
- `/state/{st}/` 56 pages: national offers, that state's offers, top
  cities linking to /near/.
- `/offer/{slug}/` one per offer: details, terms, who qualifies, source,
  "find the nearest" search.
- `/print/` large-print list.
- `/about/` sources, last-checked date, plain-words privacy statement,
  not-affiliated notice.
- `sitemap.xml`, `robots.txt`, Open Graph tags, text-only OG image.
- `_headers`: `/data/*` Cache-Control public, max-age=3600; HTML 300.

## 5. Date and time rules (visitor's own time zone)
- Before start: "Starts Tue, Nov 10". During: highlighted "Today". After
  end with no redeem_by: "Ended", moved to the bottom.
- With redeem_by: "Voucher good until May 31, 2027".
- Time windows from terms (e.g. "5 a.m.–noon") show as a chip. Parse them
  into `time_window` in data/overrides.json; never guess.
- Store hours, when present: "Usual hours — call ahead on Veterans Day."

## 6. Data pipeline
All downloads cached in data/cache/ with the date; a run must work
offline from the cache.

### 6.1 Offers
- Input: data/seed/offers-2026.json (130 offers). Validate (pydantic or
  similar). Merge data/overrides.json.
- Add `eligibility_tags` (veteran, active, guard_reserve, retiree, family,
  gold_star, everyone) parsed from `eligibility`. Write the parse table to
  data/eligibility-map.json for a human to check.
- Output: dist/data/offers.json.

### 6.2 Brand → locations
- data/brands.json: for each national or regional offer, `brand_wikidata`
  (Q-id) and `atp_spiders` (All The Places spider names), found by
  research. Verify each Q-id on wikidata.org. Mark unknowns.
- Source: All The Places (alltheplaces.xyz). Read the latest run index
  first (https://data.alltheplaces.xyz/ and the repo's DATA_FORMAT.md);
  download only the needed spider GeoJSON. Don't hard-code URLs you
  haven't confirmed.
- Keep only features in the US or a US territory whose `brand:wikidata`
  matches. This blocks name collisions: "Eureka!" vs Eureka, CA; "Main
  Event"; "Casey's"; "Twin Peaks"; "Sheetz"; "Hacienda"; "Margaritas";
  "Paisano's"; "Biscuit Belly"; "110 Grill".
- No OpenStreetMap Overpass fallback this run (rate limits and ODbL
  attribution). Brands with no spider stay visible with a "Find nearest"
  Google Maps search link (brand name + visitor's city). List them in
  data/missing-brands.md.
- Single-location offers: lat/lng by hand in data/places.json, with the
  source of the coordinates.
- Regional offers: derive real states from downloaded locations. Where
  they differ from the seed's `states`, note it in PROGRESS.md and use the
  derived ones (some seed lists were estimates).
- Location record: `{b: brandSlug, n: name?, a: street, c: city, s:
  state, z: zip, la: lat (5 dp), lo: lng (5 dp), p: phone?, h: hours?}`

### 6.3 Tiles
- 0.5° × 0.5° tiles: dist/data/tiles/{latIdx}_{lngIdx}.json, plus
  dist/data/tiles/index.json. Split any tile over 100 KB gzipped into four
  (up to 3 levels).
- Cloudflare Pages limits: under 20,000 files, each under 25 MiB. Fail
  the build if exceeded.

### 6.4 ZIP and city lookup
- ZIP centroids: Census Gazetteer ZCTA file; fill gaps (PO-box ZIPs) from
  a permissively licensed ZIP dataset (e.g. the `zipcodes` data, BSD).
- GU, VI, AS, MP if missing: data/territories.json by hand, with a source.
- Shard by first 3 digits: dist/data/zip/{zip3}.json.
- Cities: Census Gazetteer Places, sharded by state:
  dist/data/city/{st}.json.

### 6.5 Coverage report (data/coverage.md)
- Locations per brand, flagged when under 50% of the expected U.S. count
  (e.g. Applebee's about 1,500).
- Percent of offers with at least one location.
- For each test ZIP: locations within 25 and 100 miles.

## 7. Test locations (all must pass)
| ZIP | Place | Why |
|---|---|---|
| 46052 | Lebanon, IN | home pilot |
| 10001 | New York, NY | dense |
| 78205 | San Antonio, TX | big military city |
| 20001 | Washington, DC | DC |
| 59301 | Miles City, MT | rural, must auto-widen |
| 87301 | Gallup, NM | rural |
| 04401 | Bangor, ME | Northeast regional offers |
| 82001 | Cheyenne, WY | small state |
| 99701 | Fairbanks, AK | Alaska |
| 96813 | Honolulu, HI | Hawaii |
| 00901 | San Juan, PR | territory |
| 96910 | Hagåtña, GU | territory with little data |
| 00802 | St. Thomas, VI | territory with little data |

Each returns locations or a clear "Everywhere" section with a note on why
nothing is close. None may error or show a blank page.

## 8. Look and feel
- Plain, high-contrast, patriotic but not loud: navy, white, one red
  accent. Light and dark themes.
- First screen: the search box and one line saying what the site does.
- Copy for a 70-year-old on a phone in a parking lot: short sentences,
  no jargon.

## 9. Deploy (J.Will's step)
- DEPLOY.md: exact steps. Either Cloudflare dashboard > Workers & Pages >
  create Pages project > upload dist/, or Wrangler (`npx wrangler pages
  deploy dist`) after `wrangler login`, or connect a GitHub repo. Include
  custom domain steps and turning on Web Analytics.
- Daily rebuild and redeploy through Nov 12 for offer updates: document
  the one-line command.
