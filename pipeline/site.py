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

# Results page only: start the data downloads before the main scripts
# arrive, so a slow phone saves two round trips. It asks for the same
# by-index files the page would ask for anyway (offer list, map index, and
# the ZIP or state file of the search), never the search itself.
NEAR_PRELOAD_SCRIPT = (
    "(function(){var P=window.VEF_PRE={};"
    "function g(u){P[u]=fetch(u,{credentials:'omit'}).then(function(r){"
    "if(!r.ok){throw r.status;}return r.json();});P[u].catch(function(){});}"
    "g('/data/offers.json');g('/data/tiles/index.json');"
    r"var q=null,h=0;try{var m=/^\/near\/(\d{5})\/?$/.exec(location.pathname);"
    "if(m){q=m[1];}else if(!location.search){"
    "var s=JSON.parse(sessionStorage.getItem('vef-pending')||localStorage.getItem('vef-last')||'null');"
    "if(s&&s.q){q=String(s.q);}if(s){h=1;}}}catch(e){}"
    # A search is about to run: start in the folded "searching" layout so
    # nothing jumps when the results arrive.
    "if(m||h||/[?&](city|zip|q)=/.test(location.search)){"
    "document.documentElement.className+=' searching';}"
    # Once the ZIP file and map index are in, start the 25-mile map squares.
    "function T(la,lo,ix){var d=ix.deg,a=25/69,b=25/(69.17*Math.max(.05,Math.cos(la*Math.PI/180)));"
    "for(var i=Math.floor((la-a)/d);i<=Math.floor((la+a)/d);i++){"
    "for(var j=Math.floor((lo-b)/d);j<=Math.floor((lo+b)/d);j++){"
    "if(ix.tiles[i+'_'+j]===1){g('/data/tiles/'+i+'_'+j+'.json');}}}}"
    r"if(q){var z=/^\s*(\d{5})/.exec(q);if(z){var zu='/data/zip/'+z[1].slice(0,3)+'.json';g(zu);"
    "Promise.all([P[zu],P['/data/tiles/index.json']]).then(function(x){var v=x[0][z[1]];"
    "if(v&&v.length){T(v[0],v[1],x[1]);}}).catch(function(){});}"
    r"else{var c=/,\s*([A-Za-z]{2})\s*$/.exec(q);if(c){g('/data/city/'+c[1].toLowerCase()+'.json');}}}"
    "})();"
)


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
    env.globals["near_preload_script"] = NEAR_PRELOAD_SCRIPT
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
