"""U.S. Census Geocoder (public) batch lookups, for All The Places stores
that come with an address but no coordinates. Responses are cached in
data/cache/census-geocoder/ so builds can run offline."""
from __future__ import annotations

import csv
import hashlib
import io
import urllib.request
import re
import uuid
from typing import NamedTuple

from . import config

URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
BENCHMARK = "Public_AR_Current"


DIRECTIONS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}


class Match(NamedTuple):
    lat: float
    lng: float
    street: str
    city: str
    state: str
    zip: str


def _title(s: str) -> str:
    out = []
    for tok in s.split():
        if tok in DIRECTIONS or tok in {"US", "SR", "FM", "CR"}:
            out.append(tok)
        elif re.fullmatch(r"\d+(ST|ND|RD|TH)", tok):
            out.append(tok.lower())
        else:
            out.append(tok.capitalize())
    return " ".join(out)


def _post(csv_text: str) -> str:
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in (("benchmark", BENCHMARK),):
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n")
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"addressFile\"; filename=\"a.csv\"\r\n"
        f"Content-Type: text/csv\r\n\r\n{csv_text}\r\n--{boundary}--\r\n"
    )
    body = "".join(parts).encode("utf-8")
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "User-Agent": config.USER_AGENT,
    })
    with urllib.request.urlopen(req, timeout=900) as resp:
        return resp.read().decode("utf-8", errors="replace")


def batch(rows: list[tuple[str, str, str, str, str]], offline: bool) -> dict[str, Match]:
    """rows: (id, street, city, state, zip). Returns {id: Match} for matches."""
    if not rows:
        return {}
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    for r in sorted(rows):
        w.writerow(r)
    text = out.getvalue()
    key = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    cache_dir = config.CACHE / "census-geocoder"
    resp_path = cache_dir / f"batch-{key}.csv"
    if not resp_path.exists():
        if offline:
            return {}
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"batch-{key}-input.csv").write_text(text, encoding="utf-8")
        resp_path.write_text(_post(text), encoding="utf-8")
    result: dict[str, Match] = {}
    for rec in csv.reader(io.StringIO(resp_path.read_text(encoding="utf-8"))):
        if len(rec) >= 6 and rec[2] == "Match" and rec[5]:
            lng, lat = (float(x) for x in rec[5].split(","))
            parts = [x.strip() for x in rec[4].split(",")]
            street, city, state, zipc = (parts + ["", "", "", ""])[:4]
            result[rec[0]] = Match(lat, lng, _title(street), _title(city), state, zipc[:5])
    return result
