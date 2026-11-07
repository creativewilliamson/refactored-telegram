"""All The Places (alltheplaces.xyz) downloads.

Reads the run index first (https://data.alltheplaces.xyz/runs/history.json),
then downloads only the spider GeoJSON files we need from
https://alltheplaces-data.openaddresses.io/runs/<run_id>/output/<spider>.geojson
(URL pattern confirmed against the 2026-10-24 run).

Some spiders come back empty in a given weekly run. For each spider we use
the newest run (of the last LOOKBACK runs) whose feature count is at least
HEALTHY_SHARE of the best count seen, so one bad week doesn't wipe a brand.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config
from .fetch import OfflineMiss, cached

HISTORY_URL = "https://data.alltheplaces.xyz/runs/history.json"
RUN_BASE = "https://alltheplaces-data.openaddresses.io/runs/{run}"
LOOKBACK = 10
HEALTHY_SHARE = 0.8


def runs(offline: bool) -> list[str]:
    """Newest-first run ids."""
    path = config.CACHE / "atp" / "_history.json"
    if not offline:
        # Refresh the run index at most once a day.
        import datetime as dt
        import os
        fresh = path.exists() and (dt.datetime.now().timestamp() - os.path.getmtime(path) < 86400)
        cached(HISTORY_URL, "atp/_history.json", refresh=not fresh)
    if not path.exists():
        raise OfflineMiss("atp/_history.json missing")
    hist = json.loads(path.read_text(encoding="utf-8"))
    ids = [h["run_id"] for h in hist if h.get("run_id")]
    return sorted(ids, reverse=True)


def run_results(run_id: str, offline: bool) -> dict[str, int] | None:
    rel = f"atp/_results-{run_id}.json"
    try:
        path = cached(f"{RUN_BASE.format(run=run_id)}/stats/_results.json", rel, offline=offline)
    except (OfflineMiss, RuntimeError):
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r["spider"]: r.get("features", 0) for r in data.get("results", [])}


def choose_runs(spiders: list[str], offline: bool) -> dict[str, tuple[str, int] | None]:
    """Pick a run for each spider. Returns {spider: (run_id, features)}."""
    choice: dict[str, tuple[str, int] | None] = {}
    if offline:
        for sp in spiders:
            choice[sp] = _newest_cached(sp)
        return choice
    run_ids = runs(offline)[:LOOKBACK]
    counts: dict[str, dict[str, int]] = {}
    for rid in run_ids:
        res = run_results(rid, offline)
        if res is not None:
            counts[rid] = res
    for sp in spiders:
        seen = [(rid, counts[rid].get(sp, 0)) for rid in run_ids if rid in counts]
        best = max((n for _, n in seen), default=0)
        pick = None
        if best > 0:
            for rid, n in seen:  # newest first
                if n > 0 and n >= HEALTHY_SHARE * best:
                    pick = (rid, n)
                    break
        if pick is None:
            pick = _newest_cached(sp)
        choice[sp] = pick
    return choice


def _newest_cached(spider: str) -> tuple[str, int] | None:
    base = config.CACHE / "atp"
    if not base.exists():
        return None
    for d in sorted((p for p in base.iterdir() if p.is_dir()), reverse=True):
        if (d / f"{spider}.geojson").exists():
            return (d.name, -1)
    return None


def spider_file(spider: str, run_id: str, offline: bool) -> Path:
    url = f"{RUN_BASE.format(run=run_id)}/output/{spider}.geojson"
    return cached(url, f"atp/{run_id}/{spider}.geojson", offline=offline, timeout=600)


def load_features(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("features", [])
