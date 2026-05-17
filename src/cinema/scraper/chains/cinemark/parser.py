"""Cinemark Chile HTML parser.

HTML contract
-------------
The parser targets the MUI-based React application served by cinemark.cl after
full JS rendering via Playwright.  The stable DOM anchor is:

    <section data-testid="theater-session-filters">…</section>

Navigation from this anchor (2 × .parent) reaches the *filters wrapper* div,
which is a direct sibling of the *theater-info* div and the *movies box* inside
the same ``MuiContainer-maxWidthLg``:

    MuiContainer
    ├── [0] empty div (swiper)
    ├── [1] theater-info div  ← ``filters_wrapper.find_previous_sibling("div")``
    │       <h1 class="…MuiTypography-h1…">Theater Name</h1>
    │       <p  class="…MuiTypography-body2…">Address, District</p>
    ├── [2] filters-wrapper   ← ``filters.parent.parent``
    │       └─ intermediate div
    │               └─ <section data-testid="theater-session-filters">
    ├── [3] movies box        ← ``filters_wrapper.find_next_sibling("div")``
    │       └─ movie entry divs, each structured as:
    │           ├── kid[0]: metadata (duration, rating + duplicate h1)
    │           └── kid[1]: details panel
    │                   ├── panel[0]: title wrapper  <h1 …>Movie Title</h1>
    │                   └── panel[1..n]: one div per format/language combo
    │                           inline text: "2D · Doblada 20:30hs 21:40hs"
    └── [4] "Comprar entradas" button div

Theater info is the ``div`` immediately before the filters wrapper; it holds
an ``h1.MuiTypography-h1`` (name) and a ``p.MuiTypography-body2`` (address).

If the site is updated and the selectors no longer match, update ``parse()``
and ``_parse_theater()`` here and the test fixtures in
``tests/scraper/chains/test_cinemark_parser.py``.
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

# Regex to pull HH:MM times from free text (handles "21:20hs" suffix)
_TIME_RE = re.compile(r"\b([01]\d|2[0-3]):[0-5]\d")

# Legacy CSS selectors used only for the fallback time-extraction pass and
# for test fixtures that still use the old HTML structure.
_SEL_SHOWTIME_TIME = "[class*='showtime-time'], [class*='hora'], [class*='btn-horario']"

# Allowed values (must match model validators)
_VALID_FORMATS = {"2D", "3D", "XD", "4DX", "IMAX"}
_VALID_LANGUAGES = {"SUB", "DUB"}


class CinemarkParser(BaseParser):
    """Parses a rendered Cinemark Chile theater page into Showtime objects."""

    def parse(self, html: str) -> list[Showtime]:
        """Extract all showtimes from a rendered Cinemark theater page.

        Args:
            html: Fully rendered HTML from :class:`CinemarkFetcher`.

        Returns:
            List of :class:`~cinema.models.Showtime` objects.

        Raises:
            ParseError: If theater information cannot be located in the HTML.
        """
        soup = BeautifulSoup(html, "html.parser")
        theater = self._parse_theater(soup)
        showtimes: list[Showtime] = []

        # Use the stable data-testid anchor to navigate to the movies box.
        filters = soup.find(attrs={"data-testid": "theater-session-filters"})
        if not filters:
            logger.warning(
                "No movies found for theater '%s' — "
                "theater-session-filters element not present.",
                theater.name,
            )
            return showtimes

        # filters → intermediate div → filters-wrapper (2 levels up, sibling of movies box)
        filters_wrapper = filters.parent.parent
        movies_box = filters_wrapper.find_next_sibling("div")
        if not movies_box:
            logger.warning(
                "No movies found for theater '%s' — "
                "movies box not found after filters wrapper.",
                theater.name,
            )
            return showtimes

        movie_entries = [
            c for c in movies_box.children
            if hasattr(c, "name") and c.name == "div"
        ]
        if not movie_entries:
            logger.warning(
                "No movie cards found for theater '%s' — "
                "the site structure may have changed.",
                theater.name,
            )
            return showtimes

        for entry in movie_entries:
            entry_children = [
                c for c in entry.children if hasattr(c, "name") and c.name
            ]
            if len(entry_children) < 2:
                continue

            # sub[1] is the details panel (sub[0] holds metadata chips)
            details_panel = entry_children[1]

            title_el = details_panel.find("h1")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title:
                continue

            # children[0] = title wrapper; children[1:] = one div per format combo
            panel_children = [
                c for c in details_panel.children if hasattr(c, "name") and c.name
            ]
            for fmt_group in panel_children[1:]:
                fmt = _extract_format(fmt_group)
                lang = _extract_language(fmt_group)
                times = _extract_times(fmt_group)

                if not times:
                    continue
                if fmt not in _VALID_FORMATS:
                    logger.debug(
                        "Skipping unknown format '%s' for '%s'", fmt, title
                    )
                    continue
                if lang not in _VALID_LANGUAGES:
                    logger.debug(
                        "Skipping unknown language '%s' for '%s'", lang, title
                    )
                    continue

                showtimes.append(
                    Showtime(
                        movie=title,
                        theater=theater,
                        date=date.today(),
                        times=times,
                        format=fmt,
                        language=lang,
                        chain_id="cinemark",
                    )
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
        # Primary path: navigate from the stable filters anchor.
        filters = soup.find(attrs={"data-testid": "theater-session-filters"})
        if filters:
            filters_wrapper = filters.parent.parent
            theater_info = filters_wrapper.find_previous_sibling("div")
            if theater_info:
                name_el = theater_info.find("h1")
                addr_el = theater_info.find("p", class_="MuiTypography-body2")
                if name_el:
                    name = name_el.get_text(strip=True)
                    raw_address = addr_el.get_text(strip=True) if addr_el else ""
                    address, district, region = _split_address(raw_address, name)
                    return Theater(
                        name=name,
                        address=address,
                        district=district,
                        region=region,
                        chain_id="cinemark",
                    )

        # Fallback for legacy / test HTML without MUI structure.
        name_el = soup.find("h1")
        if not name_el:
            raise ParseError(
                "Cannot locate theater name in Cinemark HTML. "
                "The page structure may have changed."
            )
        name = name_el.get_text(strip=True)
        if not name:
            raise ParseError("Theater name element is empty.")

        address_el = soup.select_one(
            "[class*='address'], [class*='direccion'], .theater-address"
        )
        raw_address = address_el.get_text(strip=True) if address_el else ""
        address, district, region = _split_address(raw_address, name)

        return Theater(
            name=name,
            address=address,
            district=district,
            region=region,
            chain_id="cinemark",
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _extract_format(group: Tag) -> str:
    """Determine the projection format from a format-group element.

    Scans the element's text for known format tokens.  If none is found,
    returns the text of the first ``<p>`` element so the caller's
    ``_VALID_FORMATS`` check can reject it.

    Args:
        group: A format-group ``<Tag>``.

    Returns:
        Format string (may not be in the allowed set — caller must validate).
    """
    text = group.get_text(" ", strip=True).upper()
    for fmt in ("IMAX", "4DX", "XD", "3D", "2D"):
        if fmt in text:
            return fmt

    # No known format found — return raw label so the caller can skip it.
    first_p = group.find("p")
    return first_p.get_text(strip=True) if first_p else text


def _extract_language(group: Tag) -> str:
    """Determine the audio/subtitle mode from a showtime group element.

    Args:
        group: A showtime group ``<Tag>``.

    Returns:
        Language string (may not be in the allowed set — caller must validate).
    """
    data_lang = (group.get("data-language") or "").strip().upper()
    if data_lang:
        # Return the attribute value as-is (even if invalid) so the caller
        # can decide whether to skip it via the _VALID_LANGUAGES check.
        return data_lang

    text = group.get_text(" ", strip=True).upper()
    if "SUB" in text or "SUBTITULAD" in text:
        return "SUB"
    if "DUB" in text or "DOBLAD" in text:
        return "DUB"
    return "SUB"  # Cinemark CL defaults to subtitled for non-animated films


def _extract_date(group: Tag) -> date:
    """Parse the screening date from a showtime group element.

    Tries ``data-date`` (ISO format ``YYYY-MM-DD``) first, then falls back
    to today's date so that partial scrapes still produce valid objects.

    Args:
        group: A showtime group ``<Tag>``.

    Returns:
        A :class:`datetime.date` instance.
    """
    raw = (group.get("data-date") or "").strip()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return date.today()


def _extract_times(group: Tag) -> list[str]:
    """Collect all ``HH:MM`` time strings from a showtime group.

    Args:
        group: A showtime group ``<Tag>``.

    Returns:
        Sorted, deduplicated list of time strings like ``["14:10", "17:30"]``.
    """
    times: list[str] = []
    for el in group.select(_SEL_SHOWTIME_TIME):
        text = el.get_text(strip=True)
        match = _TIME_RE.search(text)
        if match:
            times.append(match.group())
    # Also scan raw text in case times are not in dedicated elements
    if not times:
        for match in _TIME_RE.finditer(group.get_text(" ")):
            times.append(match.group())
    return sorted(set(times))


def _split_address(raw: str, theater_name: str) -> tuple[str, str, str]:
    """Best-effort parse of a combined address string.

    Cinemark Chile address strings typically follow the pattern:
    ``"Av. Américo Vespucio 1737, Independencia, Región Metropolitana"``

    Args:
        raw: Raw address text extracted from the page.
        theater_name: Used as a fallback placeholder when the address is empty.

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
