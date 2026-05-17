"""CineHoyts Chile fetcher using Playwright for JS-heavy pages."""

import asyncio
import logging

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from cinema.config import settings
from cinema.exceptions import FetchError
from cinema.scraper.base import BaseFetcher

logger = logging.getLogger(__name__)


class CineHoytsFetcher(BaseFetcher):
    """Fetches fully-rendered HTML from CineHoyts Chile theater pages.

    Uses Playwright (Chromium) to handle the JavaScript-driven frontend at
    cinehoyts.cl.
    """

    async def fetch(self, url: str) -> str:
        """Navigate to *url*, wait for content to render, return HTML.

        Args:
            url: A CineHoyts Chile theater URL
                (e.g. ``https://www.cinehoyts.cl/cine/cinehoyts-florida-center``).

        Returns:
            Fully rendered HTML string.

        Raises:
            FetchError: On navigation timeout or any Playwright error.
        """
        logger.info("Fetching CineHoyts URL: %s", url)
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=settings.headless)
                context = await browser.new_context(
                    user_agent=settings.user_agent,
                    locale="es-CL",
                )
                page = await context.new_page()

                await page.goto(url, wait_until="networkidle", timeout=60_000)
                await asyncio.sleep(settings.request_delay_seconds)

                try:
                    await page.wait_for_selector(
                        "[class*='movie'], [class*='pelicula'], [class*='film']",
                        timeout=10_000,
                    )
                except PlaywrightTimeoutError:
                    logger.warning(
                        "Movie selector not found on %s — proceeding with "
                        "raw page content.",
                        url,
                    )

                html = await page.content()
                await browser.close()
                return html

        except PlaywrightTimeoutError as exc:
            raise FetchError(
                f"Timeout fetching CineHoyts page: {url}"
            ) from exc
        except Exception as exc:
            raise FetchError(
                f"Failed to fetch CineHoyts page {url}: {exc}"
            ) from exc
