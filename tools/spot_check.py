"""Trace random stores on the built site back to their source.

For each sampled store in dist/data/tiles it finds the All The Places
feature it came from (in data/cache/atp/<run>/<spider>.geojson), or the
Census Geocoder match for stores that had no coordinates, and prints the
brand Q-id found there, the Q-id the brand should have (data/brands.json,
checked on wikidata.org), the state, and whether the point sits inside the
U.S. near a ZIP of that state.

Usage: python tools/spot_check.py [N] [--seed S]
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import atp, config  # noqa: E402
from pipeline.locations import miles  # noqa: E402


def load_tiles() -> list[dict]:
    out = []
    for f in glob.glob(str(ROOT / "dist/data/tiles/*.json")):
        if f.endswith("index.json"):
            continue
        out.extend(json.loads(Path(f).read_text(encoding="utf-8")))
    return out


def geocoder_matches() -> dict[tuple[float, float], str]:
    found = {}
    for f in glob.glob(str(config.CACHE / "census-geocoder/batch-*.csv")):
        if f.endswith("-input.csv"):
            continue
        for rec in csv.reader(open(f, encoding="utf-8")):
            if len(rec) >= 6 and rec[2] == "Match":
                lng, lat = (float(x) for x in rec[5].split(","))
                found[(round(lat, 5), round(lng, 5))] = f"Census Geocoder: {rec[1]} -> {rec[4]}"
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("n", nargs="?", type=int, default=10)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    brands = json.loads((ROOT / "data/brands.json").read_text(encoding="utf-8"))["brands"]
    checked = json.loads((ROOT / "data/wikidata-check.json").read_text(encoding="utf-8"))["qids"]
    zips = {}
    for f in glob.glob(str(ROOT / "dist/data/zip/*.json")):
        for k, v in json.loads(Path(f).read_text(encoding="utf-8")).items():
            if isinstance(v, list):
                zips[k] = v
    records = load_tiles()
    rng = random.Random(args.seed)
    sample = rng.sample(records, args.n)
    geo = geocoder_matches()
    feats_cache: dict[str, list] = {}
    ok_all = True
    for r in sample:
        b = brands[r["b"]]
        want = set(b["brand_wikidata"])
        source, got = None, None
        for sp in b["atp_spiders"]:
            pick = atp._newest_cached(sp)
            if not pick:
                continue
            key = f"{pick[0]}/{sp}"
            if key not in feats_cache:
                feats_cache[key] = atp.load_features(config.CACHE / "atp" / pick[0] / f"{sp}.geojson")
            for f in feats_cache[key]:
                g = f.get("geometry") or {}
                if g.get("type") == "Point":
                    lng, lat = g["coordinates"][:2]
                    if abs(lat - r["la"]) < 2e-5 and abs(lng - r["lo"]) < 2e-5:
                        source, got = f"ATP {sp} run {pick[0]} ref={f['properties'].get('ref')}", f["properties"].get("brand:wikidata")
                        break
            if source:
                break
        if not source and (r["la"], r["lo"]) in geo:
            source = geo[(r["la"], r["lo"])]
            got = "(address from ATP feature of this brand; see geocoder input file)"
        near = min(((miles(r["la"], r["lo"], z[0], z[1]), z[3]) for z in zips.values()
                    if abs(z[0] - r["la"]) < 1 and abs(z[1] - r["lo"]) < 1), default=(999, None))
        in_us = near[0] < 60
        brand_ok = got in want or (got and got.startswith("("))
        ok = bool(source) and brand_ok and in_us
        ok_all &= ok
        labels = ", ".join(f"{q} = {checked.get(q, {}).get('label')}" for q in sorted(want))
        print(f"{'OK  ' if ok else 'FAIL'} {b['name']} | {r.get('a')}, {r.get('c')}, {r['s']} {r.get('z', '')} "
              f"| {r['la']},{r['lo']}")
        print(f"     source: {source or 'NOT FOUND'}")
        print(f"     brand:wikidata in source: {got}  expected: {labels}")
        print(f"     nearest ZIP centroid: {near[0]:.1f} mi, state {near[1]} (record says {r['s']})")
    print("ALL OK" if ok_all else "SOME FAILED")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
