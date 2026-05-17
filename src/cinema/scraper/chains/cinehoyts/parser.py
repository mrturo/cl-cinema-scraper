"""CineHoyts Chile HTML parser.

HTML contract
-------------
This parser targets the structure produced by cinehoyts.cl after full JS
rendering.  The expected DOM layout is:

    <div class="cinema-header">
        <h1 class="cinema-name">[Theater Name]</h1>
        <address class="cinema-address">[Address], [District], [Region]</address>
    </div>

    <ul class="billboard-list">
        <li class="film-item">
            <h2 class="film-title">[Movie Title]</h2>

            <div class="session-group"
                 data-format="2D"
                 data-language="SUB"
                 data-date="2024-04-15">
                <button class="session-time">14:30</button>
                <button class="session-time">17:00</button>
            </div>
        </li>
    </ul>

Adjust the ``_SELECTORS`` constants when the live site changes, and keep the
test fixtures in ``tests/scraper/chains/test_cinehoyts_parser.py`` in sync.
"""

from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup, Tag

from cinema.exceptions import ParseError
from cinema.models import Showtime, Theater
from cinema.scraper.base import BaseParser

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunable CSS selector fragments
# ---------------------------------------------------------------------------
_SEL_THEATER_SECTION = (
    "[class*='cinema-header'], [class*='theater-header'], [class*='cinema-info']"
)
_SEL_THEATER_NAME = "h1"
_SEL_THEATER_ADDRESS = "address, [class*='address'], [class*='direccion']"
_SEL_MOVIES = "[class*='film-item'], [class*='movie-item'], [class*='pelicula']"
_SEL_MOVIE_TITLE = "[class*='film-title'], [class*='movie-title'], h2, h3"
_SEL_SHOWTIME_GROUP = (
    "[class*='session-group'], [class*='showtime-group'], [class*='horario-group']"
)
_SEL_SHOWTIME_TIME = (
    "[class*='session-time'], [class*='showtime-time'], [class*='hora']"
)

_VALID_FORMATS = {"2D", "3D", "XD", "4DX", "IMAX"}
_VALID_LANGUAGES = {"SUB", "DUB"}
_TIME_RE = re.compile(r"\b([01]\d|2[0-3]):[0-5]\d\b")


class CineHoytsParser(BaseParser):
    """Parses a rendered CineHoyts Chile theater page into Showtime objects."""

    def parse(self, html: str) -> list[Showtime]:
        """Extract all showtimes from a rendered CineHoyts theater page.

        Args:
            html: Fully rendered HTML from :class:`CineHoytsFetcher`.

        Returns:
            List of :class:`~cinema.models.Showtime` objects.

        Raises:
            ParseError: If theater information cannot be located in the HTML.
        """
        soup = BeautifulSoup(html, "html.parser")
        theater = self._parse_theater(soup)
        showtimes: list[Showtime] = []

        movie_items = soup.select(_SEL_MOVIES)
        if not movie_items:
            logger.warning(
                "No movie items found for theater '%s' — "
                "the site structure may have changed.",
                theater.name,
            )
            return showtimes

        for item in movie_items:
            title_el = item.select_one(_SEL_MOVIE_TITLE)
            if not title_el:
                continue
            movie_title = title_el.get_text(strip=True)
            if not movie_title:
                continue

            showtimes.extend(
                self._parse_showtime_groups(item, movie_title, theater)
            )

        logger.info(
            "Parsed %d showtimes for theater '%s'",
            len(showtimes),
            theater.name,
        )
        return showtimes

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_theater(self, soup: BeautifulSoup) -> Theater:
        """Extract theater metadata from the page.

        Args:
            soup: Parsed document.

        Returns:
            A :class:`~cinema.models.Theater` instance.

        Raises:
            ParseError: If the theater name cannot be determined.
        """
        section = soup.select_one(_SEL_THEATER_SECTION)
        root: BeautifulSoup | Tag = section if section else soup

        name_el = root.select_one(_SEL_THEATER_NAME) or soup.find("h1")
        if not name_el:
            raise ParseError(
                "Cannot locate theater name in CineHoyts HTML. "
                "The page structure may have changed."
            )
        name = name_el.get_text(strip=True)
        if not name:
            raise ParseError("Theater name element is empty.")

        address_el = root.select_one(_SEL_THEATER_ADDRESS)
        raw_address = address_el.get_text(strip=True) if address_el else ""
        address, district, region = _split_address(raw_address, name)

        return Theater(
            name=name,
            address=address,
            district=district,
            region=region,
            chain_id="cinehoyts",
        )

    def _parse_showtime_groups(
        self,
        item: Tag,
        movie_title: str,
        theater: Theater,
    ) -> list[Showtime]:
        """Extract all format/language/date groups from a single film item.

        Args:
            item: The film item ``<Tag>``.
            movie_title: Already-extracted movie title string.
            theater: Parent theater object.

        Returns:
            List of :class:`~cinema.models.Showtime` objects for this film.
        """
        showtimes: list[Showtime] = []
        groups = item.select(_SEL_SHOWTIME_GROUP)

        for group in groups:
            fmt = _extract_format(group)
            lang = _extract_language(group)
            showtime_date = _extract_date(group)
            times = _extract_times(group)

            if not times:
                continue
            if fmt not in _VALID_FORMATS:
                logger.debug("Skipping unknown format '%s' for '%s'", fmt, movie_title)
                continue
            if lang not in _VALID_LANGUAGES:
                logger.debug(
                    "Skipping unknown language '%s' for '%s'", lang, movie_title
                )
                continue

            showtimes.append(
                Showtime(
                    movie=movie_title,
                    theater=theater,
                    date=showtime_date,
                    times=times,
                    format=fmt,
                    language=lang,
                    chain_id="cinehoyts",
                )
            )

        return showtimes


# ---------------------------------------------------------------------------
# Module-level helpers (deliberately parallel to cinemark/parser.py)
# ---------------------------------------------------------------------------


def _extract_format(group: Tag) -> str:
    """Determine the projection format from a session group element."""
    data_fmt = (group.get("data-format") or "").strip().upper()
    if data_fmt in _VALID_FORMATS:
        return data_fmt
    text = group.get_text(" ", strip=True).upper()
    for fmt in ("IMAX", "4DX", "XD", "3D", "2D"):
        if fmt in text:
            return fmt
    return "2D"


def _extract_language(group: Tag) -> str:
    """Determine the audio/subtitle mode from a session group element.

    Returns the raw ``data-language`` attribute when present so the caller's
    ``_VALID_LANGUAGES`` check can reject unrecognised values.
    """
    data_lang = (group.get("data-language") or "").strip().upper()
    if data_lang:
        return data_lang
    text = group.get_text(" ", strip=True).upper()
    if "SUB" in text or "SUBTITULAD" in text:
        return "SUB"
    if "DUB" in text or "DOBLAD" in text:
        return "DUB"
    # No language detected — return raw text so the caller can skip it.
    return text


def _extract_date(group: Tag) -> date:
    """Parse the screening date from a session group element."""
    raw = (group.get("data-date") or "").strip()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return date.today()


def _extract_times(group: Tag) -> list[str]:
    """Collect all ``HH:MM`` time strings from a session group."""
    times: list[str] = []
    for el in group.select(_SEL_SHOWTIME_TIME):
        match = _TIME_RE.search(el.get_text(strip=True))
        if match:
            times.append(match.group())
    if not times:
        for match in _TIME_RE.finditer(group.get_text(" ")):
            times.append(match.group())
    return sorted(set(times))


def _split_address(raw: str, theater_name: str) -> tuple[str, str, str]:
    """Best-effort parse of a combined address string.

    Args:
        raw: Raw address text extracted from the page.
        theater_name: Used as fallback when the address is empty.

    Returns:
        Tuple of ``(address, district, region)``.
    """
    if not raw:
        return (theater_name, "Santiago", "Región Metropolitana")
    parts = [p.strip() for p in raw.split(",")]
    address = parts[0] if len(parts) > 0 else raw
    district = parts[1] if len(parts) > 1 else "Santiago"
    region = parts[2] if len(parts) > 2 else "Región Metropolitana"
    return (address, district, region)
