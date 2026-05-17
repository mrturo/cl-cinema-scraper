"""Tests for the Cinemark Chile parser using static HTML fixtures.

Every fixture in this module must match the HTML contract documented at the
top of ``cinema/scraper/chains/cinemark/parser.py``.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from cinema.exceptions import ParseError
from cinema.scraper.chains.cinemark.parser import CinemarkParser

# ---------------------------------------------------------------------------
# HTML fixtures — mirror the real MUI structure served by cinemark.cl.
# Navigation anchor: <section data-testid="theater-session-filters">
#   filters.parent.parent                    → filters-wrapper (direct child of MuiContainer)
#   filters_wrapper.find_previous_sibling()  → theater-info box
#   filters_wrapper.find_next_sibling()      → movies box
# ---------------------------------------------------------------------------

MINIMAL_VALID_HTML = """
<html>
<body>
  <div>
    <div>
      <h1 class="MuiTypography-root MuiTypography-h1">Cinemark Mall Plaza Norte</h1>
      <p class="MuiTypography-root MuiTypography-body2">Av. Américo Vespucio 1737, Independencia, Región Metropolitana</p>
    </div>
    <div>
      <div>
        <section data-testid="theater-session-filters"></section>
      </div>
    </div>
    <div>
      <div>
        <div></div>
        <div>
          <div>
            <h1 class="MuiTypography-root MuiTypography-h1">Kung Fu Panda 4</h1>
          </div>
          <div>2D · Subtitulada 14:10hs 16:30hs 19:00hs</div>
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""

MULTI_MOVIE_HTML = """
<html>
<body>
  <div>
    <div>
      <h1 class="MuiTypography-root MuiTypography-h1">Cinemark Arauco Maipú</h1>
      <p class="MuiTypography-root MuiTypography-body2">Av. Américo Vespucio 399, Maipú, Región Metropolitana</p>
    </div>
    <div>
      <div>
        <section data-testid="theater-session-filters"></section>
      </div>
    </div>
    <div>
      <div>
        <div></div>
        <div>
          <div>
            <h1 class="MuiTypography-root MuiTypography-h1">Dune: Part Two</h1>
          </div>
          <div>IMAX · Subtitulada 13:00hs 16:30hs</div>
          <div>2D · Doblada 19:00hs</div>
        </div>
      </div>
      <div>
        <div></div>
        <div>
          <div>
            <h1 class="MuiTypography-root MuiTypography-h1">Ghostbusters: Frozen Empire</h1>
          </div>
          <div>3D · Subtitulada 14:45hs 17:15hs</div>
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""

NO_THEATER_NAME_HTML = """
<html><body><div class="movies-container"></div></body></html>
"""

NO_MOVIES_HTML = """
<html>
<body>
  <section class="theater-info">
    <h1>Cinemark Mall Plaza Norte</h1>
    <p class="theater-address">Av. Test 1, Santiago, Región Metropolitana</p>
  </section>
  <div class="movies-container"></div>
</body>
</html>
"""

INVALID_FORMAT_HTML = """
<html>
<body>
  <div>
    <div>
      <h1 class="MuiTypography-root MuiTypography-h1">Cinemark Test</h1>
      <p class="MuiTypography-root MuiTypography-body2">Calle Test 1, Santiago, Región Metropolitana</p>
    </div>
    <div>
      <div>
        <section data-testid="theater-session-filters"></section>
      </div>
    </div>
    <div>
      <div>
        <div></div>
        <div>
          <div>
            <h1 class="MuiTypography-root MuiTypography-h1">Some Film</h1>
          </div>
          <div>ScreenX · Doblada 14:00hs</div>
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCinemarkParserTheater:
    """Theater extraction from Cinemark HTML."""

    def test_extracts_theater_name(self) -> None:
        parser = CinemarkParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert result[0].theater.name == "Cinemark Mall Plaza Norte"

    def test_extracts_theater_chain_id(self) -> None:
        parser = CinemarkParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert result[0].theater.chain_id == "cinemark"

    def test_extracts_theater_district(self) -> None:
        parser = CinemarkParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert result[0].theater.district == "Independencia"

    def test_extracts_theater_region(self) -> None:
        parser = CinemarkParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert result[0].theater.region == "Región Metropolitana"

    def test_raises_parse_error_when_no_theater_name(self) -> None:
        parser = CinemarkParser()
        with pytest.raises(ParseError):
            parser.parse(NO_THEATER_NAME_HTML)


class TestCinemarkParserShowtimes:
    """Showtime extraction from Cinemark HTML."""

    def test_returns_empty_list_when_no_movies(self) -> None:
        parser = CinemarkParser()
        assert parser.parse(NO_MOVIES_HTML) == []

    def test_basic_showtime_count(self) -> None:
        parser = CinemarkParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert len(result) == 1

    def test_showtime_movie_title(self) -> None:
        parser = CinemarkParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert result[0].movie == "Kung Fu Panda 4"

    def test_showtime_date(self) -> None:
        parser = CinemarkParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert result[0].date == date.today()

    def test_showtime_times(self) -> None:
        parser = CinemarkParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert set(result[0].times) == {"14:10", "16:30", "19:00"}

    def test_showtime_format(self) -> None:
        parser = CinemarkParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert result[0].format == "2D"

    def test_showtime_language(self) -> None:
        parser = CinemarkParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert result[0].language == "SUB"

    def test_showtime_chain_id(self) -> None:
        parser = CinemarkParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert result[0].chain_id == "cinemark"

    def test_scraped_at_is_set(self) -> None:
        parser = CinemarkParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert isinstance(result[0].scraped_at, datetime)


class TestCinemarkParserMultipleMovies:
    """Parser handles pages with multiple movies and formats."""

    def test_total_showtime_count(self) -> None:
        parser = CinemarkParser()
        result = parser.parse(MULTI_MOVIE_HTML)
        assert len(result) == 3  # IMAX SUB + 2D DUB + 3D SUB

    def test_imax_format_extracted(self) -> None:
        parser = CinemarkParser()
        result = parser.parse(MULTI_MOVIE_HTML)
        formats = {st.format for st in result}
        assert "IMAX" in formats

    def test_dub_language_extracted(self) -> None:
        parser = CinemarkParser()
        result = parser.parse(MULTI_MOVIE_HTML)
        languages = {st.language for st in result}
        assert "DUB" in languages

    def test_movie_titles_extracted(self) -> None:
        parser = CinemarkParser()
        result = parser.parse(MULTI_MOVIE_HTML)
        titles = {st.movie for st in result}
        assert titles == {"Dune: Part Two", "Ghostbusters: Frozen Empire"}

    def test_unknown_format_is_skipped(self) -> None:
        parser = CinemarkParser()
        result = parser.parse(INVALID_FORMAT_HTML)
        assert result == []
