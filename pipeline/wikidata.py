"""Check Wikidata Q-ids on wikidata.org (labels, descriptions, and for
single places the coordinate claim). Results are cached in
data/cache/wikidata/ and summarized in data/wikidata-check.json."""
from __future__ import annotations

import json
import urllib.parse

from . import config
from .fetch import OfflineMiss, cached

API = "https://www.wikidata.org/w/api.php"


def fetch_entities(qids: list[str], offline: bool, tag: str, claims: bool = False) -> dict:
    """Return {qid: entity} for the given ids (batched by 40)."""
    out: dict = {}
    qids = sorted(set(qids))
    for i in range(0, len(qids), 40):
        batch = qids[i:i + 40]
        props = "labels|descriptions" + ("|claims|sitelinks/urls" if claims else "")
        params = {
            "action": "wbgetentities", "ids": "|".join(batch), "props": props,
            "languages": "en", "format": "json",
        }
        url = API + "?" + urllib.parse.urlencode(params)
        key = f"wikidata/{tag}-{i // 40:02d}-{'_'.join(batch)[:60]}.json"
        try:
            path = cached(url, key, offline=offline)
        except OfflineMiss:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        out.update(data.get("entities", {}))
    return out


def label(entity: dict) -> str | None:
    return (entity.get("labels", {}).get("en") or {}).get("value")


def description(entity: dict) -> str | None:
    return (entity.get("descriptions", {}).get("en") or {}).get("value")


def coordinates(entity: dict) -> tuple[float, float] | None:
    for claim in entity.get("claims", {}).get("P625", []):
        v = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if v:
            return float(v["latitude"]), float(v["longitude"])
    return None


def check_brands(brands: dict, offline: bool) -> dict:
    qids = [q for b in brands.values() for q in (b.get("brand_wikidata") or [])]
    ents = fetch_entities(qids, offline, "brands")
    report = {}
    for q in sorted(set(qids)):
        e = ents.get(q)
        if not e or "missing" in e:
            report[q] = {"ok": False, "why": "not found on wikidata.org"}
            continue
        redirect = e.get("id") != q
        report[q] = {
            "ok": True,
            "label": label(e),
            "description": description(e),
            "url": f"https://www.wikidata.org/wiki/{q}",
            **({"redirects_to": e.get("id")} if redirect else {}),
        }
    return report


def write_check(report: dict) -> None:
    path = config.DATA / "wikidata-check.json"
    body = {
        "_readme": "Each brand Q-id from data/brands.json as found on wikidata.org "
                   "(label and description), checked by pipeline/wikidata.py.",
        "qids": report,
    }
    path.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
