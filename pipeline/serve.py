"""Serve dist/ as plain static files, the way Cloudflare Pages would.

Honors dist/_redirects (200 rewrites and 301/302 redirects, with `*`
splats) and dist/_headers, gzips text responses, and serves 404.html for
missing paths. There is no search API: this only hands out files.

Usage: python -m pipeline.serve [--dir dist] [--port 8095]
"""
from __future__ import annotations

import argparse
import fnmatch
import gzip
import http.server
import os
import posixpath
import re
import threading
import urllib.parse
from pathlib import Path

TEXT_TYPES = (
    "text/", "application/javascript", "application/json",
    "application/xml", "image/svg+xml", "application/manifest+json",
)


def parse_redirects(path: Path) -> list[tuple[str, str, int]]:
    rules: list[tuple[str, str, int]] = []
    if not path.exists():
        return rules
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        status = int(parts[2]) if len(parts) > 2 else 302
        rules.append((parts[0], parts[1], status))
    return rules


def parse_headers(path: Path) -> list[tuple[str, list[tuple[str, str]]]]:
    rules: list[tuple[str, list[tuple[str, str]]]] = []
    if not path.exists():
        return rules
    current: list[tuple[str, str]] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw[0] not in " \t":
            current = []
            rules.append((raw.strip(), current))
        elif current is not None and ":" in raw:
            name, value = raw.strip().split(":", 1)
            current.append((name.strip(), value.strip()))
    return rules


def match_rule(pattern: str, path: str) -> str | None:
    """Return the splat text if `path` matches `pattern`, else None."""
    if "*" not in pattern:
        return "" if pattern == path else None
    regex = "^" + re.escape(pattern).replace(r"\*", "(.*)") + "$"
    m = re.match(regex, path)
    return m.group(1) if m else None


class Handler(http.server.SimpleHTTPRequestHandler):
    root: Path
    redirects: list[tuple[str, str, int]]
    headers_rules: list[tuple[str, list[tuple[str, str]]]]
    _gzip_cache: dict = {}
    _lock = threading.Lock()

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "application/javascript",
        ".json": "application/json",
        ".svg": "image/svg+xml",
        ".xml": "application/xml",
        ".webmanifest": "application/manifest+json",
        ".txt": "text/plain",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.root), **kwargs)

    def log_message(self, fmt, *args):  # quieter logs
        if os.environ.get("SERVE_QUIET"):
            return
        super().log_message(fmt, *args)

    # -- routing -----------------------------------------------------
    def _resolve(self) -> tuple[str | None, int, str | None]:
        """Return (file path, status, redirect location)."""
        parsed = urllib.parse.urlsplit(self.path)
        url_path = urllib.parse.unquote(parsed.path)
        url_path = posixpath.normpath(url_path) + ("/" if url_path.endswith("/") and url_path != "/" else "")
        if url_path.startswith("//"):
            url_path = "/" + url_path.lstrip("/")
        fs = self._fs_path(url_path)
        if fs and os.path.isdir(fs):
            if not url_path.endswith("/"):
                q = ("?" + parsed.query) if parsed.query else ""
                return None, 308, url_path + "/" + q
            index = os.path.join(fs, "index.html")
            if os.path.isfile(index):
                return index, 200, None
        elif fs and os.path.isfile(fs):
            return fs, 200, None
        # Pretty URL: /about -> /about/
        for src, dest, status in self.redirects:
            splat = match_rule(src, url_path)
            if splat is None:
                continue
            target = dest.replace(":splat", splat)
            if status == 200:
                tfs = self._fs_path(target)
                if tfs and os.path.isdir(tfs):
                    tfs = os.path.join(tfs, "index.html")
                if tfs and os.path.isfile(tfs):
                    return tfs, 200, None
            else:
                return None, status, target
        notfound = self.root / "404.html"
        return (str(notfound) if notfound.exists() else None), 404, None

    def _fs_path(self, url_path: str) -> str | None:
        parts = [p for p in url_path.split("/") if p and p not in (".", "..")]
        candidate = self.root.joinpath(*parts) if parts else self.root
        try:
            candidate.resolve().relative_to(self.root.resolve())
        except ValueError:
            return None
        return str(candidate)

    def _extra_headers(self, url_path: str) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for pattern, hdrs in self.headers_rules:
            if match_rule(pattern, url_path) is not None or fnmatch.fnmatch(url_path, pattern):
                out.extend(hdrs)
        return out

    # -- responses ---------------------------------------------------
    def do_HEAD(self):
        self._respond(head=True)

    def do_GET(self):
        self._respond(head=False)

    def _respond(self, head: bool) -> None:
        fs, status, location = self._resolve()
        if location:
            self.send_response(status)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if fs is None:
            self.send_error(404)
            return
        ctype = self.guess_type(fs)
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            if "charset" not in ctype:
                ctype += "; charset=utf-8"
        body = Path(fs).read_bytes()
        encoding = None
        accept = self.headers.get("Accept-Encoding", "")
        if "gzip" in accept and ctype.startswith(TEXT_TYPES) and len(body) > 256:
            body = self._gzipped(fs, body)
            encoding = "gzip"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if encoding:
            self.send_header("Content-Encoding", encoding)
        self.send_header("Vary", "Accept-Encoding")
        url_path = urllib.parse.urlsplit(self.path).path
        for name, value in self._extra_headers(url_path):
            self.send_header(name, value)
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def _gzipped(self, fs: str, body: bytes) -> bytes:
        key = (fs, os.path.getmtime(fs), len(body))
        with self._lock:
            hit = self._gzip_cache.get(key)
            if hit is None:
                hit = gzip.compress(body, compresslevel=6, mtime=0)
                if len(self._gzip_cache) > 4000:
                    self._gzip_cache.clear()
                self._gzip_cache[key] = hit
        return hit


def make_handler(root: Path) -> type[Handler]:
    class Bound(Handler):
        pass

    Bound.root = root.resolve()
    Bound.redirects = parse_redirects(root / "_redirects")
    Bound.headers_rules = parse_headers(root / "_headers")
    return Bound


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="dist")
    ap.add_argument("--port", type=int, default=8095)
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()
    root = Path(args.dir)
    handler = make_handler(root)
    server = http.server.ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving {root.resolve()} at http://localhost:{args.port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
