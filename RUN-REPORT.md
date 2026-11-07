# Run report — VetsEatFree — 2026-11-07 16:10 EST

**Run ended by:** done bar met (all 19 features pass with browser evidence; evaluator round 11 PASS on commit 8ebb79a)
**Start it:** `.\start.ps1`, then open http://localhost:8095/

## Try these
- Home page: type `46052` and press **Find offers**. You get real nearby stores sorted nearest first, one card per place with today's offer, hours, a **Call** button and directions, and an **Everywhere** section for offers with no store (National Parks and others).
- On the results: change the radius (10/25/50/100 miles). 46052 gives 21 / 349 / 771 / 1,319 stores. Try a search with few stores, like `59301` or `96910` (Guam): it widens to 100 miles by itself and says so.
- Pick a category filter (Meals, Coffee & treats, Shopping, Haircuts & car care, Attractions), or tick **Free only** / **Gold Star**. **Clear filters** brings everything back.
- Search by town: `Lebanon, IN`, `San Juan, PR`, `Fairbanks, AK`, `St. Thomas, VI`, `Washington, DC`. A misspelling like `Springfeild, IL` offers "Did you mean Springfield". **Use my location** works too, and if you deny it you get "type your ZIP code instead".
- Errors: `00000`, `zzzz` or the APO ZIP `09012` each give a plain message and a next step, never a blank page.
- Share: open http://localhost:8095/near/46052 or http://localhost:8095/near/?city=lebanon&st=IN directly. The same search opens, and a reload brings back the last search.
- Large print for a post volunteer: on the results click **Large-print list**, or open http://localhost:8095/print/?zip=46052&r=25. Text is 16 pt or larger, there are no images, and it fits on paper.
- Offer pages: click any offer name, or open http://localhost:8095/offer/texas-roadhouse/. You see who qualifies, what to bring, the terms, the source link and "Find the nearest". Texas Roadhouse shows "Voucher good until May 31, 2027".
- No JavaScript: turn it off and open the home page. The 56 state and territory links lead to pre-rendered state pages (for example `/state/in/`, `/state/gu/`).
- Privacy: open the browser's developer tools, then Network, and search. Requests only go to localhost, only fetch numbered data files, and never include the ZIP, the town or your location. No cookies.
- The footer on every page shows the Veterans Crisis Line (Call 988, press 1 · Text 838255).

## Status
Done: F01, F02, F03, F04, F05, F06, F07, F08, F09, F10, F11, F12, F13, F14, F15, F16, F17, F18, F19 (all 19; evidence in `evidence/`) | Stubbed: none | Failed: none

Final checks on the last build (8ebb79a): 130 offers, 80,176 stores, 3,114 files (Cloudflare Pages limit 20,000). pytest 78 passed. Browser suite (Chromium + WebKit, Playwright, including axe on every page type) 130 passed. Lighthouse on the slow-4G phone profile was 100/100 when last measured for F18 (not re-run on this final build).

## Known bugs
Per J.Will's STEER note, individual closed, seasonal or coming-soon stores are polish, not blocking. None of these are fixed in this run.

**Closed, coming-soon or seasonal stores (from All The Places, the chains' own data)**
- The 15 stores evaluator round 9 named are left out, each with a source, in `data/location-exclusions.json`: Playa Bowls ×9, IHOP New Smyrna Beach and Crowley, Ruby Tuesday Harriman and West Ashley, and Wendy's Radford, 3900 Georgia Ave NW DC and Lawrenceville NJ. Charleys Fort Buchanan was already there. No automatic sweep of the chains' store pages is done (STEER). The round-9 sweep, since removed, flagged about 600 more source records whose own page said "Temporarily Closed" or "Coming Soon" or was gone: mostly Wendy's (508 records; Wendy's has several records per store), plus Chipotle (31), Charleys (13), Pilot/Flying J (8) and Great Clips (6). Those are still listed. To leave out more, add entries to `data/location-exclusions.json` with the page that shows it.
- Side effect of removing the 9 named Playa Bowls: Playa Bowls is now above the 97.5% "complete listings" share, so the existing "no phone and no hours means not open yet" rule also hides 6 Playa Bowls listings round 9 didn't name: Sarasota (81 N Cattlemen Rd), Sparta NJ, Scottsdale (8870 N 90th St), Sunrise FL (Panther Pkwy), 570 Lexington Ave NYC and Danbury CT. Playa Bowls goes from 435 to 421 stores. Nothing is invented by this. If J.Will wants exactly the named stores hidden, work out the share before exclusions are applied (`pipeline/locations.py`, end of `build()`). I didn't change this after the PASS because it's a choice for J.Will.
- The Playa Bowls exclusion source (`playabowls.com/api/locations`) now redirects to an ordinary page, and its `store_page` links return 404 (the site was redesigned). The Ruby Tuesday and Wendy's sources still load.
- Stadium and seasonal venues are still listed: Shake Shack at Nationals Park, Citi Field, Citizens Bank Park, Daikin Park and Saratoga Race Course; Dunkin' at the Carrier Dome, Syracuse; Playa Bowls boardwalk shops with no hours; about 36 Shake Shack listings with no phone. Airport, base, campus and hospital outlets also still show.

**Store data quirks carried from the source**
- Hard Rock Cafe Bristol VA shows twice (two source listings about 0.1 mi apart).
- Some streets run the city, state and ZIP into the street line ("500 Gate City Highway Bristol VA 24201", BWW GO Palmetto, Starbucks Camp Bowie Blvd).
- BRAVO! Italian Kitchen (19 stores): no street address, so the cards show only the town. Its hours include happy-hour windows. Bethel Road, Columbus shows "Tue–Thu 3 a.m.–6 p.m."
- Shared central phone numbers: Charleys 833-230-2930 is on 45 stores, and Dunkin' 603-397-7368 is on stores in several states.
- Starbucks placeholder text in some streets (", TBD", ", N/A", "Unknown (Target Power Center)", "Blossom Hill Pavilion Relocation").
- Messy Sport Clips names ("Haircuts for Men | ..."); Bucky's stores shown as Casey's; about 284 Golden Corral streets without a house number.

**Pages and wording**
- State pages say "1 store locations" (`/state/vi/`) and "0 store locations" (`/state/as/`).
- The print page says "1 places within 25 miles". Opening `/print/?zip=00802&r=25` directly doesn't widen the radius the way the results page does (it hands the print page r=100). The print page's "← Back to results" link is 28px tall. Print lists can be very long (349 entries for 46052 at 25 mi).
- The share image `og.png` cuts off "near you" at the right edge.
- Inline links on About, offer pages and the 404 page are 22px tall.
- The DC state page has duplicate "Washington" links.
- "Find the nearest" for Hy-Vee from 46052 stops at 100 miles. Its message says "the chains listed below may still have a store near you", but the list is empty.
- `/near/abc` reopens the last search, and "abc" gets the odd suggestion "like “abc, IN”".
- "Opens the business's page" wording also appears when the source is military.com or VA News.
- Category filters with under 10 results show a "Show up to 50 miles" button instead of widening by themselves. This was a builder decision, noted in PROGRESS.md.
- Five offer source links (Applebee's, AutoNation, Colonial Williamsburg, jyfmuseums.org, Tractor Supply) return 403 or time out to scripts. They load in a real browser.

**Process notes**
- I missed J.Will's STEER.md when it arrived mid-round 9 and built a store-page status sweep he had told me to skip (commits fff5812, 2aab420). Commit 8ebb79a undid it and did exactly what STEER asked.
- During round 11 the evaluator wrote one temporary file under Git Bash's `/tmp` (outside the project folder) and deleted it right away. Nothing else outside the project folder was written by the build or by me.

## Evaluator's last verdict
**PASS** (round 11, commit 8ebb79a). No blocking findings.
- The STEER changes were done as asked: the sweep is gone, `pipeline/locations.py` is identical to before the sweep, and the 20 exclusions all have a reason, an https source and a date.
- None of the named stores appear in the results.
- pytest 78 passed and e2e 130 passed. The 13 SPEC ZIPs, radius, filters, searches, dates, sharing, print and no-JS paths all work.
- Privacy: about 550 requests, all same-site, with no ZIP, town or coordinates and no cookies.
- Data: `data/seed` is untouched, every override has a source, all 130 offers match their source_url, and 20 random stores traced 20/20 to the source.

Polish items are listed under Known bugs above.

## Suggested next goal
Before Nov 11: let J.Will decide on the Playa Bowls side effect and add any more closed stores he wants hidden to `data/location-exclusions.json`, each with its page. Then fix the small wording and size polish (plural "store locations"/"places", the og.png text, 22px and 28px links, print radius widening for island ZIPs, the Hy-Vee empty list message), and deploy per DEPLOY.md with a daily rebuild through Nov 12.
