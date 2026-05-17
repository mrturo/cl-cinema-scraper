"""Periodic scraping scheduler.

Discovers all registered chains via :class:`~cinema.scraper.registry.ChainRegistry`
and runs each one on a configurable interval.  A failure in one chain never
prevents the others from running.
"""

import asyncio
import logging
import time

import cinema.scraper.chains  # noqa: F401 — triggers chain self-registration
from cinema.config import settings
from cinema.exceptions import CinemaError
from cinema.scraper.registry import ChainRegistry
from cinema.storage.database import Database

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

db = Database()


async def scrape_all_chains() -> None:
    """Run a full scrape cycle for every registered chain.

    Each chain is scraped independently.  Errors are caught and logged so
    that a broken chain does not interrupt the rest.
    """
    chains = ChainRegistry.all()
    if not chains:
        logger.warning("No chains registered — nothing to scrape.")
        return

    for chain in chains:
        start = time.monotonic()
        try:
            logger.info("Starting scrape for chain: %s", chain.chain_id)
            showtimes = await chain.scrape()
            await db.upsert_showtimes(showtimes)
            duration = time.monotonic() - start
            logger.info(
                "Finished scrape for chain: %s — %d showtimes found (%.1fs)",
                chain.chain_id,
                len(showtimes),
                duration,
            )
        except CinemaError as exc:
            logger.error(
                "Scrape failed for chain '%s': %s", chain.chain_id, exc
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Unexpected error scraping chain '%s': %s", chain.chain_id, exc
            )


async def _run_loop() -> None:
    """Async loop: scrape immediately, then repeat every N hours."""
    await db.initialize()
    interval_seconds = settings.scraping_interval_hours * 3600
    while True:
        await scrape_all_chains()
        logger.info(
            "Next scrape in %d hours. Press Ctrl+C to stop.",
            settings.scraping_interval_hours,
        )
        await asyncio.sleep(interval_seconds)


def main() -> None:
    """Entry point for the ``cinema-scheduler`` console script.

    Runs an initial scrape immediately on startup, then fires again every
    :attr:`~cinema.config.Settings.scraping_interval_hours` hours.
    """
    try:
        asyncio.run(_run_loop())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shutting down.")


if __name__ == "__main__":
    main()
