"""Cut location records into 0.5-degree tiles for the browser.

dist/data/tiles/{latIdx}_{lngIdx}.json holds every store in that cell
(latIdx = floor(lat / 0.5), lngIdx = floor(lng / 0.5)). A tile larger than
100 KB gzipped is split into four quarters ({id}_0 .. {id}_3, quarter order:
SW, SE, NW, NE), up to three levels deep. dist/data/tiles/index.json lists
every tile and how it was split, so the browser only asks for files that
exist.
"""
from __future__ import annotations

import gzip
import json
import math
from pathlib import Path

TILE_DEG = 0.5
MAX_GZ = 100 * 1024
MAX_LEVEL = 3


def _dump(records: list[dict]) -> bytes:
    return json.dumps(records, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _split(records, south, west, size, tid, level, out, tree):
    body = _dump(records)
    if len(gzip.compress(body, 6)) <= MAX_GZ or level >= MAX_LEVEL:
        out[tid] = body
        return 1
    half = size / 2
    quads = [[], [], [], []]
    for r in records:
        q = (1 if r["lo"] >= west + half else 0) + (2 if r["la"] >= south + half else 0)
        quads[q].append(r)
    sub = {}
    for q, recs in enumerate(quads):
        if not recs:
            continue
        s = south + (half if q >= 2 else 0)
        w = west + (half if q % 2 else 0)
        child = {}
        _split(recs, s, w, half, f"{tid}_{q}", level + 1, out, child)
        sub[str(q)] = child or 1
    tree.update(sub)
    return len(sub)


def build(records: list[dict]) -> tuple[dict[str, bytes], dict]:
    cells: dict[tuple[int, int], list[dict]] = {}
    for r in records:
        key = (math.floor(r["la"] / TILE_DEG), math.floor(r["lo"] / TILE_DEG))
        cells.setdefault(key, []).append(r)
    files: dict[str, bytes] = {}
    index: dict[str, object] = {}
    for (i, j), recs in sorted(cells.items()):
        recs.sort(key=lambda r: (r["la"], r["lo"]))
        tid = f"{i}_{j}"
        tree: dict = {}
        _split(recs, i * TILE_DEG, j * TILE_DEG, TILE_DEG, tid, 0, files, tree)
        index[tid] = tree or 1
    return files, {"deg": TILE_DEG, "tiles": index}


def write(files: dict[str, bytes], index: dict, dist: Path) -> int:
    tdir = dist / "data" / "tiles"
    tdir.mkdir(parents=True, exist_ok=True)
    for tid, body in files.items():
        (tdir / f"{tid}.json").write_bytes(body)
    (tdir / "index.json").write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")
    return len(files) + 1
