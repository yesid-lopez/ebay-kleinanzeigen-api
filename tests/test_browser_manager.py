"""Unit tests for OptimizedPlaywrightManager page cap and crash recovery.

Uses an in-memory fake of Playwright, so no real browser is needed.
"""

import asyncio

import pytest

import utils.browser as browser_mod
from utils.browser import OptimizedPlaywrightManager


class Dead(Exception):
    pass


class FakePage:
    def __init__(self, browser):
        self._browser = browser

    async def close(self):
        self._browser.check()


class FakeContext:
    def __init__(self, browser):
        self.browser = browser
        self.pages = []

    async def new_page(self):
        self.browser.check()
        page = FakePage(self.browser)
        self.pages.append(page)
        return page

    async def clear_cookies(self):
        self.browser.check()

    async def close(self):
        self.browser.check()


class FakeBrowser:
    def __init__(self):
        self.dead = False  # transport closed: every call fails
        self.report_connected = True  # what is_connected() claims

    def check(self):
        if self.dead:
            raise Dead("handler is closed")

    def is_connected(self):
        return self.report_connected

    async def new_context(self, user_agent=None):
        self.check()
        return FakeContext(self)

    async def close(self):
        self.check()

    def kill(self, still_reports_connected=False):
        self.dead = True
        self.report_connected = still_reports_connected


class FakeChromium:
    def __init__(self, launched):
        self._launched = launched

    async def launch(self, headless=True):
        browser = FakeBrowser()
        self._launched.append(browser)
        return browser


class FakePlaywright:
    def __init__(self, launched):
        self.chromium = FakeChromium(launched)

    async def stop(self):
        pass


@pytest.fixture
def launched(monkeypatch):
    browsers = []

    class Starter:
        async def start(self):
            return FakePlaywright(browsers)

    monkeypatch.setattr(browser_mod, "async_playwright", lambda: Starter())
    monkeypatch.setattr(browser_mod, "CDP_URL", None)
    return browsers


async def make_manager(pages=2):
    manager = OptimizedPlaywrightManager(
        max_contexts=20, max_concurrent=10, max_concurrent_pages=pages
    )
    await manager.start()
    return manager


async def test_caps_open_pages_across_concurrent_requests(launched):
    manager = await make_manager(pages=2)
    open_now = 0
    peak = 0

    async def fetch():
        nonlocal open_now, peak
        context = await manager.get_context()
        try:
            open_now += 1
            peak = max(peak, open_now)
            await context.new_page()
            await asyncio.sleep(0.01)
        finally:
            open_now -= 1
            await manager.release_context(context)

    await asyncio.gather(*(fetch() for _ in range(8)))
    assert peak == 2


async def test_restarts_browser_reported_disconnected(launched):
    manager = await make_manager()
    launched[0].kill()

    context = await manager.get_context()
    assert context.browser is launched[1]
    assert manager.get_performance_metrics()["browser_restarts"] == 1
    await manager.release_context(context)


async def test_restarts_when_transport_dies_but_still_reports_connected(launched):
    # Production failure: driver pipe closed, every call raises "handler is closed"
    manager = await make_manager()
    # Drain the pre-warmed pool so get_context has to call new_context
    manager._context_pool.clear()
    launched[0].kill(still_reports_connected=True)

    context = await manager.get_context()
    assert context.browser is launched[1]
    await manager.release_context(context)


async def test_release_on_dead_browser_frees_slot_and_recovers(launched):
    manager = await make_manager(pages=1)
    context = await manager.get_context()
    await context.new_page()
    launched[0].kill(still_reports_connected=True)

    await manager.release_context(context)  # must not raise

    # Slot was freed (would hang otherwise) and we got a fresh browser
    fresh = await asyncio.wait_for(manager.get_context(), timeout=1)
    assert fresh.browser is launched[1]
    await manager.release_context(fresh)


async def test_concurrent_failures_trigger_single_restart(launched):
    manager = await make_manager(pages=5)
    launched[0].kill()

    contexts = await asyncio.gather(*(manager.get_context() for _ in range(5)))
    assert len(launched) == 2
    for context in contexts:
        await manager.release_context(context)


async def test_double_release_does_not_inflate_slots(launched):
    manager = await make_manager(pages=1)
    context = await manager.get_context()
    await manager.release_context(context)
    await manager.release_context(context)

    first = await manager.get_context()
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(manager.get_context(), timeout=0.05)
    await manager.release_context(first)
