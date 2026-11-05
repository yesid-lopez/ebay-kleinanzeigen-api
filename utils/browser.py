import asyncio
import logging
import os
from typing import Dict, List
from playwright.async_api import async_playwright, BrowserContext, Page
from utils.user_agent import get_random_ua

logger = logging.getLogger(__name__)

# External CDP endpoint (e.g. BrowserUse cloud session, browserless, plain
# chromium --remote-debugging-port). When set, the app connects to that
# browser instead of launching a local bundled Chromium.
CDP_URL = os.environ.get("BROWSER_CDP_URL", "").strip() or None

# Hard cap on browser contexts (one page each) open at the same time across
# ALL requests. Every open page costs Chromium memory, so this bounds the
# memory footprint regardless of how many requests arrive concurrently.
# Without it, two 3-page searches open 6 pages and get the container OOM-killed.
MAX_CONCURRENT_PAGES = max(1, int(os.environ.get("BROWSER_MAX_CONCURRENT_PAGES", "3")))

# Upper bound for shutdown calls against a browser/driver that may be dead.
_SHUTDOWN_TIMEOUT = 5.0


class PlaywrightManager:
    def __init__(self):
        self._playwright = None
        self._browser = None

    async def start(self):
        self._playwright = await async_playwright().start()
        if CDP_URL:
            self._browser = await self._playwright.chromium.connect_over_cdp(CDP_URL)
        else:
            self._browser = await self._playwright.chromium.launch(headless=True)

    async def new_context_page(self):
        context = await self._browser.new_context(user_agent=get_random_ua())
        return await context.new_page()

    async def close_page(self, page):
        await page.close()

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()


class OptimizedPlaywrightManager:
    def __init__(
        self,
        max_contexts: int = 10,
        max_concurrent: int = 5,
        max_concurrent_pages: int = MAX_CONCURRENT_PAGES,
    ):
        self._playwright = None
        self._browser = None
        self._context_pool: List[BrowserContext] = []
        self._context_in_use: List[BrowserContext] = []
        self._max_contexts = max_contexts
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._context_lock = asyncio.Lock()

        # Global cap on simultaneously open pages. Acquired in get_context(),
        # released in release_context().
        self._max_concurrent_pages = max_concurrent_pages
        self._page_slots = asyncio.Semaphore(max_concurrent_pages)

        # Browser lifecycle. The generation increments on every (re)launch so
        # concurrent failures trigger a single restart, not one per request.
        self._browser_lock = asyncio.Lock()
        self._generation = 0
        self._context_generation: Dict[int, int] = {}
        self._browser_restarts = 0

        # Performance metrics
        self._contexts_created = 0
        self._contexts_reused = 0
        self._concurrent_operations = 0
        self._max_concurrent_reached = 0

    async def _launch(self):
        """Start the Playwright driver and browser, and pre-warm the pool."""
        self._playwright = await async_playwright().start()
        if CDP_URL:
            self._browser = await self._playwright.chromium.connect_over_cdp(CDP_URL)
        else:
            self._browser = await self._playwright.chromium.launch(headless=True)
        self._generation += 1

        # Pre-create some contexts for the pool
        initial_contexts = min(3, self._max_contexts)
        if not CDP_URL:  # skip pre-warm against external/ephemeral browsers
            for _ in range(initial_contexts):
                context = await self._browser.new_context(user_agent=get_random_ua())
                self._context_generation[id(context)] = self._generation
                self._context_pool.append(context)
                self._contexts_created += 1

    async def start(self):
        """Initialize the browser and create initial context pool"""
        await self._launch()

    def _browser_alive(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    async def _restart_browser(self, seen_generation: int, reason: str):
        """Replace a dead browser (e.g. Chromium or the driver was OOM-killed).

        Only restarts if nobody else already did since `seen_generation`.
        """
        async with self._browser_lock:
            if self._generation != seen_generation:
                return  # another request already restarted it

            logger.warning(
                "Restarting browser (generation %d): %s", self._generation, reason
            )
            old_browser, old_playwright = self._browser, self._playwright
            self._browser = None
            self._playwright = None

            # Pooled contexts belong to the dead browser. In-use contexts stay
            # tracked so their owners can release them (and their page slots).
            for context in self._context_pool:
                self._context_generation.pop(id(context), None)
            self._context_pool.clear()

            for closer in (
                old_browser.close if old_browser else None,
                old_playwright.stop if old_playwright else None,
            ):
                if closer is None:
                    continue
                try:
                    await asyncio.wait_for(closer(), timeout=_SHUTDOWN_TIMEOUT)
                except Exception:
                    pass  # already dead; nothing to clean up

            await self._launch()
            self._browser_restarts += 1
            logger.warning("Browser restarted (generation %d)", self._generation)

    async def _acquire_context(self) -> BrowserContext:
        """Take a context from the pool or create one, restarting a dead browser."""
        for attempt in range(2):
            generation = self._generation
            if not self._browser_alive():
                await self._restart_browser(generation, "browser not connected")
                generation = self._generation
            try:
                async with self._context_lock:
                    if self._context_pool:
                        context = self._context_pool.pop()
                        self._contexts_reused += 1
                    else:
                        context = await self._browser.new_context(
                            user_agent=get_random_ua()
                        )
                        self._context_generation[id(context)] = generation
                        self._contexts_created += 1
                    self._context_in_use.append(context)
                    return context
            except Exception as e:
                if attempt == 1:
                    raise
                await self._restart_browser(generation, f"new_context failed: {e}")
        raise RuntimeError("unreachable")

    async def get_context(self) -> BrowserContext:
        """Get a browser context, waiting for a free page slot first.

        Every successful call must be paired with release_context().
        """
        await self._page_slots.acquire()
        try:
            return await self._acquire_context()
        except BaseException:
            self._page_slots.release()
            raise

    async def release_context(self, context: BrowserContext):
        """Close the context's pages, return it to the pool, and free its slot.

        Never raises: a failure here used to skip the release and leak the
        context, so cleanup errors are swallowed and treated as a dead browser.
        """
        async with self._context_lock:
            if context not in self._context_in_use:
                return
            self._context_in_use.remove(context)
        generation = self._context_generation.get(id(context))

        try:
            # Close all pages and clear session state so reused contexts
            # don't carry Kleinanzeigen tracking cookies into the next request
            cleaned = False
            try:
                for page in context.pages:
                    await page.close()
                await context.clear_cookies()
                cleaned = True
            except Exception as e:
                logger.warning("Browser context cleanup failed: %s", e)

            reusable = (
                cleaned
                and generation == self._generation
                and self._browser_alive()
            )
            async with self._context_lock:
                if reusable and len(self._context_pool) < self._max_contexts // 2:
                    self._context_pool.append(context)
                    return

            self._context_generation.pop(id(context), None)
            try:
                await asyncio.wait_for(context.close(), timeout=_SHUTDOWN_TIMEOUT)
            except Exception:
                pass

            # A cleanup failure on the current browser means its connection is
            # broken; restart now instead of failing every following request.
            if not cleaned and generation == self._generation:
                try:
                    await self._restart_browser(generation, "context cleanup failed")
                except Exception as e:
                    logger.error("Browser restart failed: %s", e)
        finally:
            self._page_slots.release()

    async def execute_with_semaphore(self, coro):
        """Execute a coroutine with concurrency control"""
        async with self._semaphore:
            self._concurrent_operations += 1
            self._max_concurrent_reached = max(
                self._max_concurrent_reached, self._concurrent_operations
            )
            try:
                result = await coro
                return result
            finally:
                self._concurrent_operations -= 1

    async def new_context_page(self) -> Page:
        """Create a new page using context pooling (backward compatibility)"""
        context = await self.get_context()
        try:
            page = await context.new_page()
        except BaseException:
            await self.release_context(context)
            raise
        # Store context reference on page for cleanup
        page._context_ref = context
        return page

    async def close_page(self, page: Page):
        """Close a page and return its context to the pool"""
        context = getattr(page, "_context_ref", None)
        if context:
            await self.release_context(context)  # also closes the page
        else:
            await page.close()

    def get_performance_metrics(self) -> dict:
        """Get current performance metrics"""
        return {
            "contexts_created": self._contexts_created,
            "contexts_reused": self._contexts_reused,
            "contexts_in_pool": len(self._context_pool),
            "contexts_in_use": len(self._context_in_use),
            "max_contexts": self._max_contexts,
            "max_concurrent_pages": self._max_concurrent_pages,
            "max_concurrent_reached": self._max_concurrent_reached,
            "current_concurrent": self._concurrent_operations,
            "browser_restarts": self._browser_restarts,
            "reuse_ratio": self._contexts_reused / max(self._contexts_created, 1),
        }

    async def close(self):
        """Clean up all resources"""
        for context in self._context_pool + self._context_in_use:
            try:
                await context.close()
            except Exception:
                pass

        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._playwright:
            await self._playwright.stop()

        self._context_pool.clear()
        self._context_in_use.clear()
        self._context_generation.clear()
