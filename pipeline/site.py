"""Render every page of the site to static HTML in dist/ with Jinja2."""
from __future__ import annotations

import base64
import hashlib
import json
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config

# Tiny inline script: marks the page as JS-capable before first paint so
# CSS can hide the search form for visitors without JavaScript.
JS_FLAG_SCRIPT = "document.documentElement.className='js';"


def csp_hash(script: str) -> str:
    digest = hashlib.sha256(script.encode("utf-8")).digest()
    return "'sha256-" + base64.b64encode(digest).decode() + "'"


class Assets:
    """Copies static files into dist/ with a content hash in the name."""

    def __init__(self, dist: Path):
        self.dist = dist
        self.map: dict[str, str] = {}

    def publish(self) -> None:
        for src in sorted(config.STATIC.rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(config.STATIC).as_posix()
            data = src.read_bytes()
            if src.suffix in (".css", ".js"):
                h = hashlib.sha256(data).hexdigest()[:10]
                out_rel = rel[: -len(src.suffix)] + f".{h}" + src.suffix
            else:
                out_rel = rel
            out = self.dist / out_rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            self.map[rel] = "/" + out_rel

    def url(self, rel: str) -> str:
        return self.map[rel]


def make_env(assets: Assets, globals_: dict) -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(config.TEMPLATES)),
        autoescape=select_autoescape(["html", "xml", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals.update(globals_)
    env.globals["asset"] = assets.url
    env.globals["js_flag_script"] = JS_FLAG_SCRIPT
    env.filters["tojson_compact"] = lambda v: json.dumps(v, separators=(",", ":"), ensure_ascii=False)
    return env


def write_page(dist: Path, url_path: str, html: str) -> Path:
    """Write html for a URL path like '/', '/about/' or '/404.html'."""
    if url_path.endswith(".html") or url_path.endswith(".xml") or url_path.endswith(".txt"):
        out = dist / url_path.lstrip("/")
    else:
        out = dist / url_path.strip("/") / "index.html" if url_path.strip("/") else dist / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8", newline="\n")
    return out


def clean_dist(dist: Path) -> None:
    if dist.exists():
        for child in dist.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    dist.mkdir(parents=True, exist_ok=True)
