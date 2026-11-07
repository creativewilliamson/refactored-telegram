"""F18: small and fast on old phones.

- Home page under 60 KB transferred (gzipped), first visit.
- Results usable within 3 s on Slow 4G: Chrome DevTools "Slow 4G" preset
  (562.5 ms latency, 1.6 Mbps down, 750 kbps up) plus 4x CPU slowdown,
  first visit with an empty cache and no service worker.
- A search works in WebKit (Safari's engine).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from .conftest import url

SLOW_4G = {"offline": False, "latency": 562.5, "downloadThroughput": 1.6e6 / 8,
           "uploadThroughput": 750e3 / 8}
RESULTS = Path(__file__).resolve().parents[2] / "evidence" / "F18-measurements.json"


def record(key, value):
    data = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    data[key] = value
    RESULTS.write_text(json.dumps(data, indent=1))


def cold_page(browser, throttle=True):
    ctx = browser.new_context(viewport={"width": 375, "height": 812}, service_workers="block")
    page = ctx.new_page()
    cdp = ctx.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.setCacheDisabled", {"cacheDisabled": False})
    if throttle:
        cdp.send("Network.emulateNetworkConditions", SLOW_4G)
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    return ctx, page, cdp


def test_f18_home_under_60kb(browser):
    ctx, page, cdp = cold_page(browser, throttle=False)
    sizes = {}
    cdp.on("Network.responseReceived", lambda e: sizes.__setitem__(e["requestId"], [e["response"]["url"], 0]))
    cdp.on("Network.loadingFinished", lambda e: sizes.get(e["requestId"]) and sizes[e["requestId"]].__setitem__(1, e["encodedDataLength"]))
    page.goto(url("/"), wait_until="networkidle")
    total = sum(v[1] for v in sizes.values())
    record("home_transfer_bytes", total)
    record("home_files", {v[0].replace(url(""), ""): v[1] for v in sizes.values()})
    ctx.close()
    assert total < 60 * 1024, total


def test_f18_results_on_slow_4g_direct_link(browser):
    ctx, page, _ = cold_page(browser)
    t0 = time.monotonic()
    page.goto(url("/near/46052"), wait_until="commit")
    page.wait_for_selector("#cards > li", timeout=30000)
    ms = round((time.monotonic() - t0) * 1000)
    record("slow4g_direct_link_ms", ms)
    if os.environ.get("EVIDENCE") == "1":
        page.screenshot(path="evidence/F18-slow4g.png")
    ctx.close()
    assert ms < 3000, ms


def test_f18_results_on_slow_4g_from_home(browser):
    ctx, page, _ = cold_page(browser)
    page.goto(url("/"))
    page.fill("#q", "46052")
    t0 = time.monotonic()
    page.click("button:has-text('Find offers')")
    page.wait_for_selector("#cards > li", timeout=30000)
    ms = round((time.monotonic() - t0) * 1000)
    record("slow4g_search_from_home_ms", ms)
    ctx.close()
    assert ms < 3000, ms


@pytest.fixture(scope="module")
def webkit(pw):
    b = pw.webkit.launch()
    yield b
    b.close()


def test_f18_webkit_search(webkit):
    ctx = webkit.new_context(viewport={"width": 375, "height": 812})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url("/"))
    page.fill("#q", "46052")
    page.click("button:has-text('Find offers')")
    page.wait_for_selector("#cards > li", timeout=30000)
    assert page.text_content("#results-h") == "Offers near Lebanon, IN 46052"
    page.select_option("#radius", "10")
    page.wait_for_function("() => document.getElementById('summary').textContent.includes('within 10 miles')")
    if os.environ.get("EVIDENCE") == "1":
        page.screenshot(path="evidence/F18-webkit.png")
    record("webkit_version", webkit.version)
    ctx.close()
    assert errors == []
