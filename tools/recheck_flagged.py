"""Re-check, one by one, the store pages run 1's round-9 sweep flagged (F20).

Scope is fixed: only the records in tools/round9-flagged.json (recovered from
commits fff5812 and 2aab420). No other chain or store is looked at, except a
small control sample (10 open-looking pages per chain) used to tell whether
that chain's 404s mean "store gone" or just "stale link".

For each flagged store this reads the chain's own page again and confirms
one of:
  - the store's own hours/status block says Coming Soon, Temporarily Closed
    or Permanently Closed (the chain-specific markers calibrated in run 1), or
  - every source link for the store returns 404 while the chain's control
    pages load (the store page is gone).
Confirmed stores are added to data/location-exclusions.json with a reason,
the https page that shows it, what the page says, and the date. Stores whose
page now looks open are left listed. Every outcome is written to
data/round9-recheck.json.

Polite: honest user agent, robots.txt checked per site, one request at a time
per site with at least 1 s between them, answers cached in
data/cache/recheck/ so a re-run fetches nothing twice.

Usage (inside the build container):
    docker compose run --rm --no-deps build python tools/recheck_flagged.py
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import gzip
import hashlib
import json
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import urllib.robotparser
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import atp, config  # noqa: E402

UA = "VetDayDeals-build/1.0 (store status re-check; static site data pipeline)"
LIST = ROOT / "tools" / "round9-flagged.json"
EXCLUSIONS = ROOT / "data" / "location-exclusions.json"
RESULTS = ROOT / "data" / "round9-recheck.json"
CACHE = config.CACHE / "recheck"
MIN_GAP = 1.0          # seconds between requests to the same site
US = {"US", "PR", "GU", "VI", "AS", "MP"}

WORDS = r"(coming soon|opening soon|temporarily closed|temp closed|permanently closed)"
# Each chain shows a store's own status inside that store's hours block. Only
# that block counts: reviews and "nearby stores" boxes on the same page can
# say "coming soon" about something else. (Calibrated in run 1, round 9.)
PATTERNS = {
    "ihop": re.compile(r'ico-hours[^"]*"><div class="hours-status[^"]*">\s*' + WORDS, re.I),
    "wendys": re.compile(r'(?:c-location-hours-additional-text|LocationInfo-hoursInfo)">\s*' + WORDS, re.I),
    "applebees": re.compile(r'no-hours-message[^"]*">\s*' + WORDS, re.I),
    # Dunkin' pages carry one machine-readable status, the store's own. Only
    # COMING_SOON counts: the page shows "Coming Soon" under the address.
    # TEMP_CLOSED does NOT mean the store is closed (checked in a browser,
    # 2026-11-07: Sauk Village IL said "Open Now - Closes at 6:45 PM" and
    # Mc Cook IL showed its hours; it seems to be about online ordering).
    "dunkin_us": re.compile(r'"status"\s*:\s*"(COMING_SOON)"'),
    "chipotle": re.compile(r'Restaurant Hours</div><div class="[^"]*"><p class="[^"]*">\s*' + WORDS, re.I),
    # Ruby Tuesday's branch pages print the status as a plain line.
    "ruby_tuesday_us": re.compile(WORDS, re.I),
}
GENERIC = re.compile(r'class="[^"]*(?:hours|status)[^"]*"[^>]*>(?:\s*<[^>]+>){0,3}\s*' + WORDS + r"\b", re.I)
PLAIN = {
    "COMING_SOON": "Coming Soon", "TEMPORARILY_CLOSED": "Temporarily Closed", "TEMP_CLOSED": "Temporarily Closed",
    "CLOSED": "Closed", "PERMANENTLY_CLOSED": "Permanently Closed", "INACTIVE": "Inactive",
}

_host_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
_host_last: dict[str, float] = defaultdict(float)
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
_robots_lock = threading.Lock()


def _cache_path(url: str) -> Path:
    return CACHE / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".json.gz")


def _robots_for(url: str):
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    with _robots_lock:
        if origin not in _robots:
            rp = urllib.robotparser.RobotFileParser(origin + "/robots.txt")
            try:
                req = urllib.request.Request(origin + "/robots.txt", headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=30) as r:
                    rp.parse(r.read().decode("utf-8", "replace").splitlines())
            except urllib.error.HTTPError as e:
                rp.parse([] if e.code in (404, 410) else ["User-agent: *", "Disallow: /"])
            except Exception:  # noqa: BLE001 - robots unreachable: be safe, don't fetch
                rp = None
            _robots[origin] = rp
        return _robots[origin]


def fetch(url: str) -> dict:
    """Status, final URL and body of a page; cached; polite per site."""
    path = _cache_path(url)
    if path.exists():
        return json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    rp = _robots_for(url)
    if rp is None or not rp.can_fetch(UA, url):
        return {"url": url, "status": "robots.txt does not allow it", "final": url, "body": ""}
    host = urlsplit(url).netloc
    out = None
    with _host_locks[host]:
        for attempt in range(3):
            wait = _host_last[host] + MIN_GAP - time.time()
            if wait > 0:
                time.sleep(wait)
            _host_last[host] = time.time()
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=30) as r:
                    out = {"url": url, "status": r.status, "final": r.geturl(),
                           "body": r.read().decode("utf-8", "replace")}
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 503) and attempt < 2:
                    time.sleep(10 * (attempt + 1))
                    continue
                out = {"url": url, "status": e.code, "final": url, "body": ""}
                break
            except Exception as e:  # noqa: BLE001 - network trouble: unknown, not "gone"
                out = {"url": url, "status": f"error: {str(e)[:80]}", "final": url, "body": ""}
                time.sleep(3)
    out["fetched"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    if isinstance(out["status"], int):   # don't cache network errors
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(json.dumps(out).encode("utf-8")))
    return out


def snippet(body: str, m: re.Match) -> str:
    text = re.sub(r"<[^>]+>", " ", body[max(0, m.start() - 160):m.end() + 40])
    return re.sub(r"\s+", " ", text).strip()[-150:]


def status_on_page(spider: str, page: dict):
    """(plain status, snippet) when the store's own block says it's not open."""
    if page["status"] != 200:
        return None
    pat = PATTERNS.get(spider, GENERIC)
    m = pat.search(page["body"])
    if not m:
        return None
    word = m.group(1)
    word = PLAIN.get(word, word.title())
    return word, snippet(page["body"], m)


def atp_features(spider: str) -> dict[str, dict]:
    """ref -> properties from the All The Places file the build uses."""
    choices = config.CACHE / "atp" / "_choices.json"
    run = None
    if choices.exists():
        pick = json.loads(choices.read_text(encoding="utf-8")).get(spider)
        if pick:
            run = pick[0] if isinstance(pick, list) else pick
    if not run or not (config.CACHE / "atp" / run / f"{spider}.geojson").exists():
        newest = atp._newest_cached(spider)
        run = newest[0] if newest else None
    if not run:
        return {}
    out = {}
    for f in atp.load_features(config.CACHE / "atp" / run / f"{spider}.geojson"):
        p = f.get("properties") or {}
        out[str(p.get("ref"))] = p
    return out


def brand_names() -> dict[str, str]:
    brands = json.loads((ROOT / "data" / "brands.json").read_text(encoding="utf-8"))["brands"]
    return {s: b["name"] for b in brands.values() for s in b.get("atp_spiders", [])}


def control_ok(spider: str, feats: dict[str, dict], flagged_refs: set[str]) -> tuple[bool, str]:
    """Does this chain's 404 mean 'gone'? Fetch 10 random un-flagged store
    pages; if more than 1 is a 404, the chain's links are too stale to trust."""
    links = sorted({p["website"] for r, p in feats.items()
                    if r not in flagged_refs and p.get("website", "").startswith("https://")
                    and (p.get("addr:country") or "US").upper() in US})
    sample = random.Random(20).sample(links, min(10, len(links)))
    res = [fetch(u)["status"] for u in sample]
    bad = sum(1 for s in res if s == 404)
    ok = sum(1 for s in res if s == 200)
    return (bad <= 1 and ok >= 8), f"{ok} of {len(sample)} control pages loaded, {bad} were 404"


def main() -> None:
    today = dt.date.today().isoformat()
    records = json.loads(LIST.read_text(encoding="utf-8"))["records"]
    ex_doc = json.loads(EXCLUSIONS.read_text(encoding="utf-8"))
    have = {(e["spider"], str(e["ref"])) for e in ex_doc["exclusions"]}
    names = brand_names()

    by_spider: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_spider[r["spider"]].append(r)
    feats = {s: atp_features(s) for s in by_spider}

    # One check per store page; a page may stand for several source records.
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in records:
        groups[(r["spider"], r["url"])].append(r)

    def check(key):
        spider, url = key
        links = [url] + [feats[spider].get(str(r["ref"]), {}).get("website") for r in groups[key]]
        links = [u for u in dict.fromkeys(links) if u and u.startswith("https://")]
        pages = []
        for u in links:
            page = fetch(u)
            pages.append(page)
            found = status_on_page(spider, page)
            if found:
                return key, {"outcome": "not open", "status": found[0], "page_says": found[1],
                             "source_url": page["final"] if page["final"].startswith("https://") else u}
            if page["status"] == 200:
                return key, {"outcome": "page looks open", "source_url": u}
        codes = [p["status"] for p in pages]
        if codes and all(c == 404 for c in codes):
            return key, {"outcome": "gone", "source_url": links[0], "links_tried": len(links)}
        return key, {"outcome": "could not check", "codes": [str(c) for c in codes]}

    t0 = time.time()
    results = {}
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        # Interleave the chains so each site gets one request at a time.
        queues = defaultdict(list)
        for key in sorted(groups):
            queues[key[0]].append(key)
        order = [q[i] for i in range(max(map(len, queues.values()))) for q in queues.values() if i < len(q)]
        for i, (key, res) in enumerate(ex.map(check, order), 1):
            results[key] = res
            if i % 50 == 0:
                print(f"  {i}/{len(groups)} pages checked ({time.time() - t0:.0f}s)", flush=True)

    trust = {}
    for spider in sorted(by_spider):
        if any(res["outcome"] == "gone" for (s, _), res in results.items() if s == spider):
            flagged_refs = {str(r["ref"]) for r in by_spider[spider]}
            trust[spider] = control_ok(spider, feats[spider], flagged_refs)
            print(f"  404 control for {spider}: {trust[spider][1]}", flush=True)

    added, outcomes = 0, []
    for (spider, url), res in sorted(results.items()):
        if res["outcome"] == "gone" and not trust.get(spider, (False, ""))[0]:
            res = {**res, "outcome": "could not check",
                   "why": "this chain's other store links also 404 (" + trust.get(spider, (False, "no control"))[1] + ")"}
        for r in groups[(spider, url)]:
            ref = str(r["ref"])
            p = feats[spider].get(ref, {})
            where = ", ".join(x for x in (p.get("addr:street_address") or r.get("street") or "",
                                          p.get("addr:city") or r.get("city") or "",
                                          p.get("addr:state") or "") if x)
            name = f"{names.get(spider, spider)}, {where}".strip(", ")
            outcomes.append({"spider": spider, "ref": ref, "name": name, "page": url, **res,
                             "in_current_source": bool(p), "checked": today})
            if res["outcome"] not in ("not open", "gone") or (spider, ref) in have:
                continue
            if res["outcome"] == "gone":
                reason = ("Gone: the chain's own page for this store no longer exists (404 on every source link), "
                          "while the chain's other store pages load. F20 re-check of the round-9 list.")
                says = "404 Not Found"
            else:
                reason = (f"Not open: the chain's own store page says \"{res['status']}\" for this store. "
                          "F20 re-check of the round-9 list.")
                says = res["page_says"]
            ex_doc["exclusions"].append({"spider": spider, "ref": ref, "name": name, "reason": reason,
                                         "source_url": res["source_url"], "page_says": says, "checked": today})
            have.add((spider, ref))
            added += 1

    EXCLUSIONS.write_text(json.dumps(ex_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    summary = defaultdict(lambda: defaultdict(int))
    for o in outcomes:
        summary[o["spider"]][o["outcome"]] += 1
    RESULTS.write_text(json.dumps({
        "_readme": ("Outcome of the F20 re-check (tools/recheck_flagged.py) for each record in "
                    "tools/round9-flagged.json. 'not open' and 'gone' are in data/location-exclusions.json; "
                    "'page looks open' and 'could not check' stay listed."),
        "checked": today, "control_404": {s: v[1] for s, v in trust.items()},
        "summary": {s: dict(v) for s, v in sorted(summary.items())},
        "records": outcomes}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    for s, v in sorted(summary.items()):
        print(f"{s}: {dict(v)}")
    print(f"added {added} exclusions; {len(ex_doc['exclusions'])} in total ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
