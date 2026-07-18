"""Playwright browser controller."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import sync_playwright

from config import SCREENSHOTS_DIR


@contextmanager
def browser_session(headless: bool = True):
    """Launch Chromium for mock payment automation."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        try:
            yield page
        finally:
            context.close()
            browser.close()


def screenshot_path(task_id: str) -> Path:
    path = SCREENSHOTS_DIR / f"{task_id}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
