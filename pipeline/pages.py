"""Render every HTML page (plus sitemap.xml and robots.txt)."""
from __future__ import annotations

import collections
import datetime as dt

from . import config, dataset, geo as geo_mod, site

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FULL_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]


def d(iso: str) -> dt.date:
    return dt.date.fromisoformat(iso)


def fmt_day(iso: str) -> str:
    x = d(iso)
    return f"{DAYS[x.weekday()]}, {MONTHS[x.month - 1]} {x.day}"


def fmt_long(iso: str) -> str:
    x = d(iso)
    return f"{FULL_MONTHS[x.month - 1]} {x.day}, {x.year}"


def fmt_range(o: dict) -> str:
    if o["start"] == o["end"]:
        return f"{fmt_day(o['start'])}, {d(o['start']).year}"
    return f"{fmt_day(o['start'])} to {fmt_day(o['end'])}, {d(o['end']).year}"


def fmt_phone(p: str | None) -> str:
    if not p or len(p) != 10:
        return ""
    return f"({p[:3]}) {p[3:6]}-{p[6:]}"


def make_env(assets, data, states):
    env = site.make_env(assets, {
        "site_name": config.SITE_NAME,
        "site_url": config.SITE_URL,
        "states": states,
        "state_names": config.STATES,
        "cats": data["cats"],
        "types": data["types"],
        "tag_labels": data["tags"],
        "verified": data.get("verified"),
        "verified_long": fmt_long(data["verified"]) if data.get("verified") else "",
        "built": data.get("built"),
    })
    env.filters.update(day=fmt_day, long=fmt_long, range=fmt_range, phone=fmt_phone)
    return env


def render_all(dist, assets, data: dict, records: list[dict], g) -> int:
    states = sorted(config.STATES.items(), key=lambda kv: kv[1])
    env = make_env(assets, data, states)
    n = 0

    def page(url: str, template: str, **ctx) -> None:
        nonlocal n
        site.write_page(dist, url, env.get_template(template).render(**ctx))
        n += 1

    by_id = {o["id"]: o for o in data["offers"]}
    brand_states: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in records:
        brand_states[r["b"]][r["s"]] += 1

    page("/", "home.html.j2")
    page("/near/", "near.html.j2")
    page("/print/", "print.html.j2")
    page("/about/", "about.html.j2", counts={
        "stores": len(records), "offers": len(data["offers"]),
        "brands": len(data["brands"]), "places": len(data["places"]),
    })
    page("/404.html", "404.html.j2")

    for code, name in states:
        national, local = dataset.offers_for_state(data, code)
        here, elsewhere = [], []
        for o in national:
            if o["kind"] == dataset.STORES and brand_states[o["brand"]].get(code):
                here.append((o, brand_states[o["brand"]][code]))
            else:
                elsewhere.append(o)
        local_rows = []
        for o in local:
            count = brand_states[o["brand"]].get(code, 0) if o["kind"] == dataset.STORES else None
            local_rows.append((o, count))
        here.sort(key=lambda t: (-t[1], t[0]["name"].lower()))
        everywhere = [o for o in elsewhere if o["kind"] == dataset.EVERYWHERE]
        other = [o for o in elsewhere if o["kind"] != dataset.EVERYWHERE]
        cities = []
        for city, cnt in dataset.top_cities(records, code, 15):
            key = geo_mod.norm_name(city)
            if key in g.cities.get(code, {}):
                cities.append((g.cities[code][key][2], key, cnt))
            if len(cities) >= 12:
                break
        page(f"/state/{code.lower()}/", "state.html.j2", code=code, name=name,
             here=here, local=local_rows, everywhere=everywhere, other=other, cities=cities,
             store_count=sum(1 for r in records if r["s"] == code))

    for o in data["offers"]:
        places = [p for p in data["places"] if p["offer"] == o["id"]]
        states_with = sorted(brand_states[o["brand"]]) if o.get("brand") else []
        page(f"/offer/{o['id']}/", "offer.html.j2", o=o, places=places,
             store_total=sum(brand_states[o["brand"]].values()) if o.get("brand") else 0,
             states_with=states_with)

    urls = ["/", "/about/"] + [f"/state/{c.lower()}/" for c, _ in states] + [f"/offer/{o['id']}/" for o in data["offers"]]
    lastmod = data.get("built") or dt.date.today().isoformat()
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"  <url><loc>{config.SITE_URL}{u}</loc><lastmod>{lastmod}</lastmod></url>" for u in urls]
    sm.append("</urlset>")
    (dist / "sitemap.xml").write_text("\n".join(sm) + "\n", encoding="utf-8")
    (dist / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nDisallow: /data/\n\n"
        f"Sitemap: {config.SITE_URL}/sitemap.xml\n", encoding="utf-8")
    n += 2
    return n
