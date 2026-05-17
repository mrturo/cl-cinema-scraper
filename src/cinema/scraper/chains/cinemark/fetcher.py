"""Cinemark Chile fetcher using Playwright for JS-heavy pages."""

import asyncio
import logging

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from cinema.config import settings
from cinema.exceptions import FetchError
from cinema.scraper.base import BaseFetcher

logger = logging.getLogger(__name__)


class CinemarkFetcher(BaseFetcher):
    """Fetches fully-rendered HTML from Cinemark Chile theater pages.

    Uses Playwright (Chromium) so that the React frontend has time to mount
    before the HTML snapshot is taken.
    """

    async def fetch(self, url: str) -> str:
        """Navigate to *url*, wait for the page to stabilise, return HTML.

        Args:
            url: A Cinemark Chile theater URL
                (e.g. ``https://www.cinemark.cl/cine/cinemark-mall-plaza-norte``).

        Returns:
            Fully rendered HTML string.

        Raises:
            FetchError: On navigation timeout or any Playwright error.
        """
        logger.info("Fetching Cinemark URL: %s", url)
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=settings.headless)
                context = await browser.new_context(
                    user_agent=settings.user_agent,
                    locale="es-CL",
                )
                page = await context.new_page()

                await page.goto(url, wait_until="networkidle", timeout=60_000)

                # Give the React app extra time to render dynamic content.
                await asyncio.sleep(settings.request_delay_seconds)

                # Wait for the MUI theater filters section — its presence
                # means the full movie listing has been rendered by React.
                try:
                    await page.wait_for_selector(
                        "[data-testid='theater-session-filters']",
                        timeout=30_000,
                    )
                except PlaywrightTimeoutError:
                    logger.warning(
                        "theater-session-filters not found on %s — "
                        "proceeding with raw page content.",
                        url,
                    )

                html = await page.content()
                await browser.close()
                return html

        except PlaywrightTimeoutError as exc:
            raise FetchError(
                f"Timeout fetching Cinemark page: {url}"
            ) from exc
        except Exception as exc:
            raise FetchError(
                f"Failed to fetch Cinemark page {url}: {exc}"
            ) from exc
