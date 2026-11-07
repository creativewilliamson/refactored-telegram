"""Check chains' own store pages for stores that are closed or not open yet.

All The Places sometimes still lists a store that the chain's own page shows
as "Coming Soon" or "Temporarily Closed", or whose page is gone. This tool
reads each store's own page (the `website` URL in the cached All The Places
file) and writes the stores it flags, with the page and the date, to
data/store-status.json. The build leaves those stores out.

Polite by design: honest user agent, a few requests at a time, robots.txt
allows these store pages (checked 2026-11-07). Before a full run it checks a
random sample per chain: if the status words appear on too many pages, they
are page template text, and the chain is skipped rather than guessed.

Usage: python tools/status_sweep.py [chain ...]   (run inside the build container)
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import atp, config  # noqa: E402

UA = {"User-Agent": "VetsEatFree-build/1.0 (store status check)"}
OUT = ROOT / "data" / "store-status.json"
US = {"US", "PR", "GU", "VI", "AS", "MP"}
WORDS = r"(coming soon|temporarily closed|temp closed|permanently closed)"
# Each chain shows a store's status inside that store's own hours block. Only
# that block counts: customer reviews and "nearby stores" boxes on the same
# page also say "coming soon" about other things.
CHAINS = {
    # spider: (brand Q-ids, store page from the website URL, own-status pattern)
    "ihop": ({"Q1185675"}, lambda u: u,
             re.compile(r'ico-hours[^"]*"><div class="hours-status[^"]*">\s*' + WORDS, re.I)),
    "wendys": ({"Q550258"}, lambda u: "/".join(u.split("/")[:7]),   # .../united-states/st/city/street
               re.compile(r'(?:c-location-hours-additional-text|LocationInfo-hoursInfo)">\s*' + WORDS, re.I)),
    "applebees": ({"Q621532"}, lambda u: u,
                  re.compile(r'no-hours-message[^"]*">\s*' + WORDS, re.I)),
    "chipotle": ({"Q465751"}, lambda u: u,
                 re.compile(r'Restaurant Hours</div><div class="[^"]*"><p class="[^"]*">\s*' + WORDS, re.I)),
}
RT_STATUS = re.compile(WORDS, re.I)

# Other chains whose store pages put status inside an hours/status element.
# One general pattern; calibration skips a chain where it hits template text.
GENERIC_PATTERN = re.compile(
    r'class="[^"]*(?:hours|status)[^"]*"[^>]*>(?:\s*<[^>]+>){0,3}\s*'
    r'(coming soon|opening soon|temporarily closed|temp closed|permanently closed)\b', re.I)
GENERIC_SPIDERS = [
    "dennys_us",
    "outback_steakhouse",
    "carrabbas_italian_grill",
    "bonefish_grill",
    "einstein_bros_us",
    "brueggers",
    "eatn_park_us",
    "waba_grill_us",
    "great_clips",
    "food_lion_us",
    "pilot_flying_j",
    "sport_clips_us",
    "golden_corral",
    "charleys_philly_steaks",
    "white_castle",
    "logans_roadhouse_us",
    "dave_and_busters",
    "smashburger",
    "bj_restaurant_us",
    "twin_peaks",
    "hooters",
    "benihana",
    "fogo_de_chao",
    "farmer_boys",
    "hopdoddy_burger_bar_us",
    "piada_us",
    "sizzler_us",
    "main_event",
    "joes_crab_shack_us",
    "mccormick_and_schmicks_us",
    "bravo_italian_us",
    "7_brew_us",
    "publix_us",
    "hy_vee_us",
    "blaze_pizza",
    "tgi_fridays_us",
    "keke",
    "innout",
    "bob_evans_us",
    "chilis",
]


def chain_config(spider: str):
    if spider in CHAINS:
        return CHAINS[spider]
    brands = json.loads((ROOT / "data" / "brands.json").read_text(encoding="utf-8"))["brands"]
    for b in brands.values():
        if spider in b.get("atp_spiders", []):
            return set(b["brand_wikidata"]), (lambda u: u), GENERIC_PATTERN
    return None


def fetch(url: str) -> tuple[int | str, str]:
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                time.sleep(5 * (attempt + 1))
                continue
            return e.code, ""
        except Exception as e:  # noqa: BLE001 - network trouble: unknown status
            last = str(e)[:60]
            time.sleep(2)
    return f"error: {last}", ""


def verdict(status, html: str, pattern, trust_404: bool = True) -> str | None:
    if status == 404:
        return "store page gone (404)" if trust_404 else None
    if status != 200:
        return None
    m = pattern.search(html)
    return f"store's hours block says '{m.group(1)}'" if m else None


def snippet(html: str, pattern) -> str:
    m = pattern.search(html or "")
    if not m:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html[max(0, m.start() - 200):m.end() + 40]))[-160:]


def features(spider: str, qids: set) -> list[dict]:
    pick = atp._newest_cached(spider)
    if not pick:
        return []
    out = []
    for f in atp.load_features(config.CACHE / "atp" / pick[0] / f"{spider}.geojson"):
        p = f.get("properties") or {}
        if p.get("brand:wikidata") in qids and (p.get("addr:country") or "US").upper() in US and p.get("website"):
            out.append(p)
    return out


def sweep_chain(spider: str, today: str) -> dict:
    cfg = chain_config(spider)
    if cfg is None:
        return {"skipped": "unknown spider", "flagged": []}
    qids, page_of, pattern = cfg
    by_url: dict[str, list[dict]] = {}
    for p in features(spider, qids):
        by_url.setdefault(page_of(p["website"]), []).append(p)
    urls = sorted(by_url)

    def fetch_store(key: str) -> tuple:
        """Try the source's own links for this store (several listings of one
        store may carry different sub-page links); first page that answers."""
        last: tuple = ("no link", "")
        for link in dict.fromkeys(p["website"] for p in by_url[key]):
            last = fetch(link)
            if last[0] == 200:
                return last
        return last

    rng = random.Random(11)
    sample = rng.sample(urls, min(20, len(urls)))
    results = [fetch_store(u) for u in sample]
    hits = sum(1 for st, h in results if st == 200 and pattern.search(h))
    gone = sum(1 for st, _ in results if st == 404)
    blocked = sum(1 for st, _ in results if st != 200 and st != 404)
    if hits > len(sample) * 0.25:
        return {"skipped": f"status words on {hits}/{len(sample)} sample pages: template text", "flagged": []}
    if blocked > len(sample) * 0.5:
        return {"skipped": f"{blocked}/{len(sample)} sample pages blocked or failing", "flagged": []}
    # Stale links in the source make 404s meaningless for some chains.
    trust_404 = gone <= len(sample) * 0.05
    flagged, errors = [], 0
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch_store, u): u for u in urls}
        for fut in cf.as_completed(futs):
            u = futs[fut]
            status, html = fut.result()
            if not isinstance(status, int):
                errors += 1
            why = verdict(status, html, pattern, trust_404)
            if why:
                for p in by_url[u]:
                    flagged.append({"spider": spider, "ref": str(p.get("ref")), "url": u, "status": why,
                                    "street": p.get("addr:street_address") or p.get("addr:full"),
                                    "city": p.get("addr:city"), "checked": today,
                                    "context": snippet(html, pattern)})
    return {"pages": len(urls), "errors": errors, "trust_404": trust_404,
            "flagged": sorted(flagged, key=lambda x: x["url"])}


def sweep_ruby_tuesday(today: str) -> dict:
    """Ruby Tuesday's records have no store link; its source is the chain's
    locations list. A branch missing from that list is gone; a branch page
    saying 'Temp Closed' is closed."""
    status, html = fetch("https://www.rubytuesday.com/locations/")
    if status != 200:
        return {"skipped": f"locations list returned {status}", "flagged": []}
    slugs = set(re.findall(r'href="https://www\.rubytuesday\.com/locations/([a-z0-9-]+)/"', html))
    flat = re.sub(r"[^a-z0-9]+", " ", html.lower())
    flagged = []
    for p in features_no_site("ruby_tuesday_us", {"Q7376400"}):
        street = (p.get("addr:street_address") or p.get("addr:full") or "").lower()
        words = re.sub(r"[^a-z0-9]+", " ", street).split()
        key = " ".join(words[:2])                      # house number + first street word
        slug = re.sub(r"[^a-z0-9]+", "-", (p.get("branch") or "").lower()).strip("-")
        url = f"https://www.rubytuesday.com/locations/{slug}/"
        if key and f" {key} " not in f" {flat} ":
            why = "not on the chain's locations list"
        else:
            if slug not in slugs:
                cand = [x for x in slugs if x.startswith(slug.split("-")[0])]
                url = f"https://www.rubytuesday.com/locations/{cand[0]}/" if len(cand) == 1 else url
            st, page = fetch(url)
            m = RT_STATUS.search(page) if st == 200 else None
            why = f"store page says '{m.group(1)}'" if m else None
        if why:
            flagged.append({"spider": "ruby_tuesday_us", "ref": str(p.get("ref")), "url": url, "status": why,
                            "street": p.get("addr:street_address") or p.get("addr:full"),
                            "city": p.get("addr:city"), "checked": today})
    return {"pages": len(slugs), "flagged": flagged}


def features_no_site(spider: str, qids: set) -> list[dict]:
    pick = atp._newest_cached(spider)
    return [f["properties"] for f in atp.load_features(config.CACHE / "atp" / pick[0] / f"{spider}.geojson")
            if f["properties"].get("brand:wikidata") in qids]


def main() -> None:
    today = dt.date.today().isoformat()
    wanted = sys.argv[1:] or list(CHAINS) + ["ruby_tuesday_us"] + GENERIC_SPIDERS
    if "generic" in wanted:
        wanted = [w for w in wanted if w != "generic"] + GENERIC_SPIDERS
    doc = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"chains": {}}
    doc["_readme"] = ("Stores whose own chain page shows them closed, coming soon, or gone, found by "
                      "tools/status_sweep.py. The build leaves these out. Each entry has the page and date.")
    for spider in wanted:
        t0 = time.time()
        res = sweep_ruby_tuesday(today) if spider == "ruby_tuesday_us" else sweep_chain(spider, today)
        res["checked"] = today
        doc["chains"][spider] = res
        OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print(f"{spider}: {len(res['flagged'])} flagged, {res.get('pages', 0)} pages, "
              f"{res.get('errors', 0)} errors {res.get('skipped', '')} ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
