"""Build the whole static site into dist/.

Usage: python -m pipeline.build [--offline]

Steps: load offers, load locations and lookups (from data/cache, downloading
anything missing unless --offline), write data files, render pages, check
Cloudflare Pages limits.
"""
from __future__ import annotations

import argparse
import sys
import time

from . import config, site


HTML_ROUTES = ["/", "/near/*", "/state/*", "/offer/*", "/print/*", "/about/*", "/404.html"]


def headers_file(csp: str) -> str:
    # Each Cache-Control lives on exactly one rule: Cloudflare Pages joins
    # duplicate headers from overlapping rules with commas.
    parts = [f"""/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: no-referrer
  Permissions-Policy: geolocation=(self), camera=(), microphone=(), interest-cohort=()
  Content-Security-Policy: {csp}
"""]
    for route in HTML_ROUTES:
        parts.append(f"{route}\n  Cache-Control: public, max-age=300\n")
    parts.append("/data/*\n  Cache-Control: public, max-age=3600\n")
    parts.append("/css/*\n  Cache-Control: public, max-age=31536000, immutable\n")
    parts.append("/js/*\n  Cache-Control: public, max-age=31536000, immutable\n")
    return "\n".join(parts)


REDIRECTS = """# Shared search links reopen the results page; the page reads the URL.
/near/* /near/index.html 200
"""


def build(offline: bool = False) -> None:
    t0 = time.time()
    dist = config.DIST
    site.clean_dist(dist)
    assets = site.Assets(dist)
    assets.publish()
    states = sorted(config.STATES.items(), key=lambda kv: kv[1])
    env = site.make_env(assets, {
        "site_name": config.SITE_NAME,
        "site_url": config.SITE_URL,
        "states": states,
    })
    site.write_page(dist, "/", env.get_template("home.html.j2").render())

    csp = ("default-src 'self'; script-src 'self' " + site.csp_hash(site.JS_FLAG_SCRIPT)
           + "; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
           "form-action 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'")
    (dist / "_headers").write_text(headers_file(csp), encoding="utf-8", newline="\n")
    (dist / "_redirects").write_text(REDIRECTS, encoding="utf-8", newline="\n")
    print(f"Built dist/ in {time.time() - t0:.1f}s", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="use data/cache only; never download")
    args = ap.parse_args()
    try:
        build(offline=args.offline)
    except Exception as exc:  # noqa: BLE001 - report and fail the build
        print(f"BUILD FAILED: {exc}", file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    main()
