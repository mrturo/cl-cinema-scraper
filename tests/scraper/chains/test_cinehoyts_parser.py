"""Tests for the CineHoyts Chile parser using static HTML fixtures.

Every fixture here must match the HTML contract in
``cinema/scraper/chains/cinehoyts/parser.py``.  Never use Cinemark HTML here.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from cinema.exceptions import ParseError
from cinema.scraper.chains.cinehoyts.parser import CineHoytsParser

# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

MINIMAL_VALID_HTML = """
<html>
<body>
  <div class="cinema-header">
    <h1 class="cinema-name">CineHoyts Florida Center</h1>
    <address class="cinema-address">Av. Vicuña Mackenna 6100, La Florida, Región Metropolitana</address>
  </div>

  <ul class="billboard-list">
    <li class="film-item">
      <h2 class="film-title">Oppenheimer</h2>

      <div class="session-group"
           data-format="IMAX"
           data-language="SUB"
           data-date="2024-04-15">
        <button class="session-time">15:30</button>
        <button class="session-time">19:00</button>
      </div>
    </li>
  </ul>
</body>
</html>
"""

MULTI_MOVIE_HTML = """
<html>
<body>
  <div class="cinema-header">
    <h1 class="cinema-name">CineHoyts Parque Arauco</h1>
    <address class="cinema-address">Av. Kennedy 5413, Las Condes, Región Metropolitana</address>
  </div>

  <ul class="billboard-list">
    <li class="film-item">
      <h2 class="film-title">Inside Out 2</h2>

      <div class="session-group"
           data-format="2D"
           data-language="DUB"
           data-date="2024-04-20">
        <button class="session-time">13:15</button>
        <button class="session-time">15:45</button>
      </div>
    </li>

    <li class="film-item">
      <h2 class="film-title">Kingdom of the Planet of the Apes</h2>

      <div class="session-group"
           data-format="3D"
           data-language="SUB"
           data-date="2024-04-20">
        <button class="session-time">14:00</button>
        <button class="session-time">17:30</button>
        <button class="session-time">21:00</button>
      </div>
    </li>
  </ul>
</body>
</html>
"""

NO_THEATER_NAME_HTML = """
<html><body><ul class="billboard-list"></ul></body></html>
"""

NO_MOVIES_HTML = """
<html>
<body>
  <div class="cinema-header">
    <h1 class="cinema-name">CineHoyts Test</h1>
    <address class="cinema-address">Calle Test 1, Santiago, Región Metropolitana</address>
  </div>
  <ul class="billboard-list"></ul>
</body>
</html>
"""

INVALID_LANGUAGE_HTML = """
<html>
<body>
  <div class="cinema-header">
    <h1 class="cinema-name">CineHoyts Test</h1>
    <address class="cinema-address">Calle Test 1, Santiago, Región Metropolitana</address>
  </div>
  <ul class="billboard-list">
    <li class="film-item">
      <h2 class="film-title">Mystery Film</h2>
      <div class="session-group"
           data-format="2D"
           data-language="DUBBED_WRONG"
           data-date="2024-04-20">
        <button class="session-time">18:00</button>
      </div>
    </li>
  </ul>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCineHoytsParserTheater:
    """Theater extraction from CineHoyts HTML."""

    def test_extracts_theater_name(self) -> None:
        parser = CineHoytsParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert result[0].theater.name == "CineHoyts Florida Center"

    def test_extracts_chain_id(self) -> None:
        parser = CineHoytsParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert result[0].theater.chain_id == "cinehoyts"

    def test_showtime_chain_id_matches_theater(self) -> None:
        parser = CineHoytsParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert result[0].chain_id == "cinehoyts"

    def test_extracts_district(self) -> None:
        parser = CineHoytsParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert result[0].theater.district == "La Florida"

    def test_raises_parse_error_when_no_theater_name(self) -> None:
        parser = CineHoytsParser()
        with pytest.raises(ParseError):
            parser.parse(NO_THEATER_NAME_HTML)


class TestCineHoytsParserShowtimes:
    """Showtime extraction from CineHoyts HTML."""

    def test_returns_empty_list_when_no_movies(self) -> None:
        parser = CineHoytsParser()
        assert parser.parse(NO_MOVIES_HTML) == []

    def test_basic_showtime_count(self) -> None:
        parser = CineHoytsParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert len(result) == 1

    def test_movie_title(self) -> None:
        parser = CineHoytsParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert result[0].movie == "Oppenheimer"

    def test_date_parsed(self) -> None:
        parser = CineHoytsParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert result[0].date == date(2024, 4, 15)

    def test_times_extracted(self) -> None:
        parser = CineHoytsParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert set(result[0].times) == {"15:30", "19:00"}

    def test_format_imax(self) -> None:
        parser = CineHoytsParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert result[0].format == "IMAX"

    def test_language_sub(self) -> None:
        parser = CineHoytsParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert result[0].language == "SUB"

    def test_scraped_at_is_set(self) -> None:
        parser = CineHoytsParser()
        result = parser.parse(MINIMAL_VALID_HTML)
        assert isinstance(result[0].scraped_at, datetime)

    def test_unknown_language_skipped(self) -> None:
        parser = CineHoytsParser()
        result = parser.parse(INVALID_LANGUAGE_HTML)
        assert result == []


class TestCineHoytsParserMultipleMovies:
    """Parser correctly handles a page with several films."""

    def test_total_showtime_count(self) -> None:
        parser = CineHoytsParser()
        result = parser.parse(MULTI_MOVIE_HTML)
        assert len(result) == 2

    def test_movie_titles(self) -> None:
        parser = CineHoytsParser()
        result = parser.parse(MULTI_MOVIE_HTML)
        titles = {st.movie for st in result}
        assert titles == {
            "Inside Out 2",
            "Kingdom of the Planet of the Apes",
        }

    def test_dub_language_present(self) -> None:
        parser = CineHoytsParser()
        result = parser.parse(MULTI_MOVIE_HTML)
        assert any(st.language == "DUB" for st in result)

    def test_all_showtimes_same_theater(self) -> None:
        parser = CineHoytsParser()
        result = parser.parse(MULTI_MOVIE_HTML)
        names = {st.theater.name for st in result}
        assert names == {"CineHoyts Parque Arauco"}
