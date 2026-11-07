# GOAL — Veterans Day Finder (VetsEatFree)

## End goal
A free public website where any veteran or service member in the U.S.
(all 50 states, DC and the territories) enters a ZIP code, "City, ST" or
taps "Use my location" and sees Veterans Day 2026 offers at real nearby
locations, with distance, address, phone, directions and a link to each
offer's source. Built as a static site, ready for J.Will to deploy to
Cloudflare Pages on Mon Nov 9.

## Who uses it
Veterans and service members on phones, often older and rural, on slow
connections, many on Nov 11 itself. Also VFW and Legion post volunteers
who print a large-print list for vets without smartphones.

## Core flows (must work by end of run)
1. A veteran enters a ZIP (or "City, ST", or uses their location) and sees
   nearby offer locations sorted by distance; each card shows name, offer,
   dates and time window, address, miles, tap-to-call phone, Google and
   Apple directions, and an "Offer details" source link.
2. A veteran narrows or widens results: category, free only, who
   qualifies, and radius (10/25/50/100 mi). When fewer than 10 places are
   found, the radius widens automatically and the page says so.
3. A veteran anywhere in the country, including Guam and the Virgin
   Islands, gets a useful page: nearby places or a clear "Everywhere"
   section with a note on why nothing is close. Never blank, never an
   error.
4. A veteran sees each offer's timing right for their own time zone:
   "Starts Tue, Nov 10", "Today", "Ended" (moved to the bottom), or
   "Voucher good until May 31, 2027".
5. A post volunteer prints a large-print list for an area
   (/print/?zip=46052&r=25), and a visitor with no JavaScript can browse
   pre-rendered state pages and offer pages.
6. A veteran shares a search link (/near/46052) that reopens the same
   search, and gets a plain message with a way forward on an unknown ZIP,
   denied location, or failed load.
7. J.Will gets a site he can trust: no visitor location leaves the
   phone, no invented data, accessible (WCAG 2.2 AA), fast on Slow 4G, and
   a build in dist/ that fits Cloudflare Pages limits, with DEPLOY.md.

## Out of scope for this run
- Deploying, pushing to git remotes, or creating any account (J.Will does
  this).
- Logins, ads, cookies, email capture, waitlist forms, analytics code.
- Any server-side search or API.
- Spanish interface.
- Logos or brand images.

## Constraints
- Runs on: personal machine, local only for the build; opens in a browser
  at http://localhost:8095 through Docker (port 8080 is taken by
  another project; never use it). The output is a static site
  in dist/ meant for public hosting.
- Stack: Python for the data pipeline and for generating every page as
  static HTML (Jinja2); plain JavaScript and plain CSS in the browser; no
  UI framework; system fonts only. Runs in Docker via docker compose. No
  Microsoft products.
- Data (approved exception to "sample data only" for this app): real
  PUBLIC data only — the offer seed in data/seed/offers-2026.json and
  public store-location and Census data with their sources. Business
  names as plain text. Nothing confidential, personal, or from work. No
  secrets.
- Stays inside this project folder. Downloads are cached in data/cache/.
- Full rules and details: reference/SPEC.md.

## Limits
- Stop after: 30 hours or 600 turns, whichever comes first.

## Done bar (fixed — do not edit per app)
1. Starts with one documented command and opens locally.
2. Every core flow works end to end, proven by tests plus a browser
   click-through.
3. RUN-REPORT.md: how to start it, what to click, done / stubbed /
   failed, known bugs, suggested next goal.
4. Sample data only, stays in folder, git commit per milestone.
5. Stops at the done bar or the limit, and says which.

## Notes for the planner (optional)
- Done bar item 4 reads as "public data only, every offer linked to its
  source" for this app (see Constraints).
- Build Monday-critical features first (FEATURES.json priorities 1–9).
- Write copy for a 70-year-old on a phone in a parking lot.
