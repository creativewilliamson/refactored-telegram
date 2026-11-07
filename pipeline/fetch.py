"""Cached downloads. Every download lands in data/cache/ and is logged in
data/cache/downloads.json with its URL, date, size and SHA-256. A build can
run offline from the cache (`--offline`)."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import config

MANIFEST = config.CACHE / "downloads.json"


class OfflineMiss(RuntimeError):
    pass


def _load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {}


def _save_manifest(m: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(MANIFEST)


def cached(url: str, rel_path: str, offline: bool = False, refresh: bool = False,
           retries: int = 3, timeout: int = 300) -> Path:
    """Return the local path for `url`, downloading into data/cache/rel_path
    if it isn't there yet."""
    path = config.CACHE / rel_path
    if path.exists() and not refresh:
        return path
    if offline:
        if path.exists():
            return path
        raise OfflineMiss(f"not in cache and --offline: {rel_path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            tmp = path.with_name(path.name + ".part")
            tmp.write_bytes(data)
            tmp.replace(path)
            m = _load_manifest()
            m[rel_path.replace("\\", "/")] = {
                "url": url,
                "downloaded": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            _save_manifest(m)
            return path
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_err = exc
            if isinstance(exc, urllib.error.HTTPError) and exc.code == 404:
                break
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"download failed: {url}: {last_err}")


def download_date(rel_path: str) -> str | None:
    entry = _load_manifest().get(rel_path.replace("\\", "/"))
    return entry["downloaded"][:10] if entry else None
