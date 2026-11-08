# Run report — Vet Day Deals, Run 2 — 2026-11-07 19:05 EST

**Run ended by:** evaluator round cap. All 27 features pass with browser evidence (run 2 added F20–F27). Evaluator round 3 of 3 returned NEEDS_WORK with 1 blocking finding, which is left unfixed under the round cap (see Known bugs). The run took about 2 h 10 min of the 3-hour limit.
**Start it:** `.\start.ps1`, then open http://localhost:8095/

## Try these
- **Home:** type `46052` and press **Find offers**. You get nearby stores, nearest first, one card per place with the offer, hours, **Call**, Google/Apple directions and **Offer details**, plus an **Everywhere** section.
- **New name (F26):** the header, page titles, About, the print page and the share image all say **Vet Day Deals**. Links and the sitemap use https://vetdaydeals.pages.dev.
- **New search (F27):** on any page except home, tap **New search** at the top. You land on the home page with the cursor in the search box.
  - On results there's a second one just under **Show more places**.
  - It also works when you open http://localhost:8095/near/46052 in a fresh tab, and it's hidden when the print page is printed.
- **Radius:** change it to 10/25/50/100 miles (46052 gives 21 / 349 / 771 / 1,319 stores). `59301`, `96910` (Guam) and `00802` (St. Thomas) widen to 100 miles by themselves and say so.
- **Filters:** Meals, Coffee & treats, Shopping, Haircuts & car care, Attractions, **Free only**, Gold Star. **Clear filters** brings everything back.
- **Town search:** `Lebanon, IN`, `San Juan, PR`, `Fairbanks, AK`, `Washington, DC`. `Springfeild, IL` offers "Did you mean Springfield". **Use my location** works too.
- **Bad input:**
  - `00000`, `zzzz` and the APO ZIP `09012` each give a plain message.
  - http://localhost:8095/near/abc now says "We couldn't find "abc". The link may be mistyped…" instead of reopening your last search.
- **Large print (F22):** open http://localhost:8095/print/?zip=00802&r=25. It widens to 100 miles like the results page and says so. "← Back to results" and **New search** are 48 px tall.
- **Offer pages:** http://localhost:8095/offer/texas-roadhouse/ shows the voucher date and the source.
  - Sources that are offer roundups (military.com, VA News, legion.org) say "opens the offer list where we found this". The businesses' own sites say "the business's page".
  - **Find the nearest** for Hy-Vee from `46052` says "The nearest Hy-Vee is more than 100 miles from Lebanon, IN 46052. Hy-Vee has stores in Iowa, Illinois…".
  - For a chain with no store list, like http://localhost:8095/offer/mission-bbq/ from `21061`, it says we don't have its store list and gives a **Find nearest** map button.
- **Counts (F21):** http://localhost:8095/state/vi/ says "1 store location". `/state/as/` says "0 store locations". `/state/dc/` lists Washington once.
- **Closed stores (F20):** search `79103` (Amarillo). The Wendy's at 2000 Ross Osage Dr, which Wendy's own page marks "Temporarily Closed", is gone; the open Wendy's nearby still show.
- **No JavaScript:** the 56 state links lead to pre-rendered state pages.
- **Privacy:** in the browser's Network tab, requests go only to localhost and never carry your ZIP, town or location. No cookies.
- **Crisis line:** every page's footer shows the Veterans Crisis Line. About now has two big **Call 988** / **Text 838255** buttons.

## Status
Done: F01–F19 (run 1, all still pass) and F20, F21, F22, F23, F24, F25, F26, F27 (run 2). That's all 27, with evidence in `evidence/`; the two evaluator fixes are `evidence/R2-W1.png` and `R2-W2.png`. | Stubbed: none | Failed: none

**What changed in run 2:**
- **F26:** the site was renamed **Vet Day Deals** (SITE_URL https://vetdaydeals.pages.dev). `dist/` has 0 matches for VetsEatFree, Vets Eat Free or vetseatfree. The browser storage keys, cache names and JS namespace that used the old initials ("vef"/"VEF") are now "vdd"/"VDD". DEPLOY.md uses `--project-name vetdaydeals`, with Wrangler as the main way, because a dashboard drag-and-drop upload is limited to 1,000 files and the site has about 3,100. The folder, repo, data files and Docker names keep "vetseatfree".
- **F20:** I re-checked only the 645 records run 1's round-9 sweep flagged (`tools/round9-flagged.json`, recovered from 2aab420), politely, and added **509** exclusions with sources. That makes 529 in total, each with a reason, an https source, what the page says, and a date.
  - **Decision:** only a status a visitor can actually see counts. Dunkin's hidden `TEMP_CLOSED` value is *not* a closure: Sauk Village IL's page says "Open Now – Closes at 6:45 PM". So those 126 Dunkin' stores stay listed. Run 1's sweep would have hidden them.
  - Every record's outcome is in `data/round9-recheck.json`. Stores went from 80,176 to 80,086.
- **F21–F25:** singular and plural counts, print-page widening, 48 px targets, honest small messages, and the share image fits.
- **Evaluator fixes:**
  - Round 1: no distance claim for chains without a store list.
  - Round 2: one-chain large-print lists and results name the chain and make no false "no places" claim.
- **Bug found while testing:** the local server (`pipeline/serve.py`) kept the CSP header it read at startup. After F26 that blocked the results page's preload script, and Slow-4G results took 4.0 s. It now re-reads `_headers`/`_redirects` when they change, and a new browser test catches CSP violations. Cloudflare Pages wasn't affected.

**Final checks (commit a3ecc3c, the evaluated build):**
- 130 offers, 80,086 stores, 3,112 files in `dist/` (Pages limit 20,000), largest 251 KB.
- Unit tests: 81 passed.
- Browser tests (Chromium + WebKit, with axe in light and dark): 197 passed. That's run 1's 130 plus 67 new ones in `tests/e2e/test_run2.py`.

## Known bugs

**Unfixed (round cap): evaluator round 3's blocking finding**
- **B1 — "Find the nearest X" can still claim "more than R miles" when X's stores are only hidden by an ended offer or a filter. Unfixed (round cap).**
  - **Ended offer (print page):** on Tue Nov 10, `/offer/mccormick-and-schmick-s/` from `20001` correctly shows 1 store at 8.6 mi marked Ended (the offer was Nov 8). Its Large-print list instead says "The nearest McCormick & Schmick's is more than 25 miles from Washington, DC 20001."
    - From Nov 12 this happens for every chain's one-chain print.
    - On Nov 12 the all-offers print for `59301` says "No places within 100 miles", when the nearby offers have only ended.
  - **Filter hides X (results and print):** search Texas Roadhouse from `46052`, then pick "Coffee & treats". The summary says "No Texas Roadhouse within 25 miles of Lebanon, IN 46052", and so does the print.
  - **Fix:** decide "none in range" from X's store records *before* removing ended offers and filtered-out offers. Say "the offer ended Sun, Nov 8" or "your filters hide X" instead. The code is in `pipeline/static/js/print.js` (rows filter and `sub` text) and `pipeline/static/js/near.js` (the one-chain summary uses `n` after filters).
  - **Impact before deploy:** on Nov 9–11 it only affects chains whose offer has already ended (a few), and searches where a filter hides the chain.

**Polish from evaluator rounds 1–3 (not fixed, per CLAUDE.md)**
- **New search:** the second button sits right under "Show more places", not at the very bottom; Everywhere and "More chains" follow it. The footer's "Search again" is at the bottom.
- **Find nearest, no-store-list chains:** in this mode, Find nearest shows twice (in the notice and in "More chains"), and the "How far?" picker does nothing.
- **Print page:**
  - `/print/?zip=abc` says "Check your signal" instead of "unknown ZIP".
  - "← Back to results" goes to `/near/` (the last search), not the printed place.
  - A filtered print doesn't name the filter it used.
- **Wording:**
  - The one-chain status line can say "Found 0 …".
  - Results counts have no thousands separator ("2782 stores").
  - nps.gov and archives.gov sources are called "the business's page".
  - About calls the zipcodes list "MIT licence"; SPEC says BSD.
- **Search inputs:**
  - `/near/46052/extra` reopens the last search.
  - `/near/?city=xyzzy&st=ZZ` and typed "abc" get the odd hint 'like "abc, IN"'. This is run 1's; GOAL said leave it.
  - "Charlotte Amalie, VI", "Queens, NY" and "Manhattan, NY" aren't found as towns; their ZIPs work.
  - `/near/index.html` says "couldn't find" locally; Pages redirects it in production.
- **WebKit console:** it logs a CSP note about its own built-in `<details>` styling, and an unknown ZIP logs a 404 for its data file. Both are handled; they're only console noise.
- **Missing tiles:** when a map tile fails to load, a one-chain summary can say "No X within R miles". The "may be missing a few" note does show.

**Carried over from run 1 (not in run 2's scope)**
- **Closed or seasonal stores outside the round-9 list** are still listed: stadium and seasonal venues (Shake Shack at ballparks, Dunkin' at the Carrier Dome), Playa Bowls boardwalk shops, and airport, base, campus and hospital outlets.
  - The 126 Dunkin' `TEMP_CLOSED` records are listed on purpose (see above).
  - To leave out more, add entries to `data/location-exclusions.json` with the page that shows it.
- **Playa Bowls threshold side effect:** 6 extra bare listings are hidden; J.Will accepted this.
- **Source data quirks:**
  - Hard Rock Cafe Bristol VA shows twice.
  - Some streets include the city, state and ZIP.
  - BRAVO! has no street addresses, and its happy-hour windows show in the hours.
  - Some phone numbers are shared central lines (Charleys, Dunkin').
  - Some Starbucks streets have "TBD"/"N/A".
  - Sport Clips names are messy, Bucky's stores show as Casey's, and some Golden Corral streets have no house number.
- **Category filters:** with fewer than 10 results they show a "Show up to 50 miles" button rather than widening.
- **Source links that block scripts:** five offer sources (Applebee's, AutoNation, Colonial Williamsburg, jyfmuseums.org, Tractor Supply) return 403 or time out to scripts. They load in a browser.

**Process notes**
- My first test command in this run wrote a 159-byte log to Git Bash's `/tmp`, which is outside the folder. I stopped it within seconds and deleted that one file. All later logs went to `test-results/` (gitignored).
- In round 3 the evaluator stopped one of its own hung test containers, `vetseatfree-e2e-run-…`, which belongs to this project. No other project's containers were touched.
- No other files outside this folder were changed.

## Evaluator's last verdict
**NEEDS_WORK** (round 3 of 3, commit a3ecc3c). That reached the round cap, so the run ended.
- **Blocking:** the one finding is B1 above, the ended-offer and filter paths of "Find the nearest X".
- **Confirmed fixed:** round 1's and round 2's targets hold (Mission BBQ, Hy-Vee and Texas Roadhouse on results and print).
- **Checked and passing:**
  - **Data:** all 130 offers match the seed plus overrides, and all 19 overrides have sources.
  - **Stores:** all 80,086 have the right Q-id and a U.S. state, and every point is within 60 mi of its ZIP. Phones match the cached source, and no excluded store is left. That's 529 exclusions, each with a source.
  - **Coverage and privacy:** all 13 SPEC ZIPs work. Privacy holds: no ZIP, town or coordinates in any request, no cookies, no third-party requests.
  - **Run-2 features:** F20–F27 hold, and axe finds 0 violations on extra states.
  - **Tests:** unit 81 passed; browser 197 passed.

## Suggested next goal
Before Monday's deploy, a short run 3 (about 1 hour, at most 2 evaluator rounds):
1. Fix B1: decide "none in range" for "Find the nearest X" from X's store records before date and filter filtering, on both results and print. Say "offer ended" or "your filters hide X" instead. Make the all-offers print say when nearby offers have only ended.
2. Optionally pick up the cheapest polish items: the print `?zip=abc` message, the thousands separators, and "Back to results" going to the printed place.

Then rebuild, run both test suites, and deploy per DEPLOY.md (`npx wrangler pages deploy dist --project-name vetdaydeals --branch main`), with the daily rebuild through Nov 12.
