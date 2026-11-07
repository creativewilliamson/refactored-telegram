"""Shared fixtures for the browser tests (run inside the e2e container)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

BASE = os.environ.get("BASE_URL", "http://localhost:8095").rstrip("/")
AXE_PATH = Path(os.environ.get("AXE_PATH", "/opt/axe/axe.min.js"))


@pytest.fixture(scope="session")
def pw():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(pw):
    b = pw.chromium.launch()
    yield b
    b.close()


@pytest.fixture()
def context(browser):
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    yield ctx
    ctx.close()


@pytest.fixture()
def page(context):
    p = context.new_page()
    errors: list[str] = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    p.js_errors = errors  # type: ignore[attr-defined]
    yield p
    assert not errors, f"JavaScript errors: {errors}"


@pytest.fixture(scope="session")
def axe_source() -> str:
    return AXE_PATH.read_text(encoding="utf-8")


def url(path: str) -> str:
    return BASE + path


def search_from_home(page, q: str) -> None:
    page.goto(url("/"))
    page.fill("#q", q)
    page.click("button:has-text('Find offers')")
    page.wait_for_url("**/near/")


def wait_results(page) -> None:
    page.wait_for_function(
        "() => !document.getElementById('results').hidden || !document.getElementById('nq-msg').hidden",
        timeout=30000,
    )
