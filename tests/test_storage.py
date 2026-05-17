"""Tests for the async SQLite storage layer."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from cinema.models import Showtime, Theater
from cinema.storage.database import Database


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_theater(
    name: str = "Test Theater",
    chain_id: str = "testchain",
    district: str = "Providencia",
    region: str = "Región Metropolitana",
) -> Theater:
    return Theater(
        name=name,
        address="Av. Test 123",
        district=district,
        region=region,
        chain_id=chain_id,
    )


def _make_showtime(
    movie: str = "Test Movie",
    chain_id: str = "testchain",
    theater: Theater | None = None,
    fmt: str = "2D",
    lang: str = "SUB",
    show_date: date = date(2024, 6, 1),
    times: list[str] | None = None,
) -> Showtime:
    return Showtime(
        movie=movie,
        theater=theater or _make_theater(chain_id=chain_id),
        date=show_date,
        times=times or ["14:00", "17:00"],
        format=fmt,
        language=lang,
        chain_id=chain_id,
    )


@pytest.fixture
async def db(tmp_path: Path) -> Database:
    """Provide a fresh in-memory-like database for each test."""
    database = Database(db_path=tmp_path / "test.db")
    await database.initialize()
    return database


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestDatabaseInitialize:
    async def test_creates_tables(self, tmp_path: Path) -> None:
        import aiosqlite

        db_path = tmp_path / "init.db"
        database = Database(db_path=db_path)
        await database.initialize()

        async with aiosqlite.connect(str(db_path)) as conn:
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in await cursor.fetchall()}

        assert "theaters" in tables
        assert "showtimes" in tables

    async def test_idempotent(self, db: Database) -> None:
        # Calling initialize() twice must not raise.
        await db.initialize()


# ---------------------------------------------------------------------------
# Upsert showtimes
# ---------------------------------------------------------------------------


class TestUpsertShowtimes:
    async def test_insert_single_showtime(self, db: Database) -> None:
        st = _make_showtime()
        await db.upsert_showtimes([st])
        result = await db.get_showtimes()
        assert len(result) == 1

    async def test_movie_title_persisted(self, db: Database) -> None:
        st = _make_showtime(movie="Inception")
        await db.upsert_showtimes([st])
        result = await db.get_showtimes()
        assert result[0].movie == "Inception"

    async def test_times_roundtrip(self, db: Database) -> None:
        times = ["11:00", "14:30", "18:00"]
        st = _make_showtime(times=times)
        await db.upsert_showtimes([st])
        result = await db.get_showtimes()
        assert sorted(result[0].times) == sorted(times)

    async def test_upsert_updates_times(self, db: Database) -> None:
        st = _make_showtime(times=["10:00"])
        await db.upsert_showtimes([st])

        updated = _make_showtime(times=["10:00", "20:00"])
        await db.upsert_showtimes([updated])

        result = await db.get_showtimes()
        assert len(result) == 1
        assert "20:00" in result[0].times

    async def test_multiple_showtimes(self, db: Database) -> None:
        showtimes = [
            _make_showtime("Film A"),
            _make_showtime("Film B"),
            _make_showtime("Film C"),
        ]
        await db.upsert_showtimes(showtimes)
        result = await db.get_showtimes()
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Filtering by date and chain_id
# ---------------------------------------------------------------------------


class TestGetShowtimesFilters:
    async def test_filter_by_date(self, db: Database) -> None:
        await db.upsert_showtimes(
            [
                _make_showtime(show_date=date(2024, 6, 1)),
                _make_showtime(movie="Film B", show_date=date(2024, 6, 2)),
            ]
        )
        result = await db.get_showtimes(date=date(2024, 6, 1))
        assert len(result) == 1
        assert result[0].date == date(2024, 6, 1)

    async def test_filter_by_chain_id(self, db: Database) -> None:
        await db.upsert_showtimes(
            [
                _make_showtime(chain_id="cinemark"),
            ]
        )
        result = await db.get_showtimes(chain_id="cinemark")
        assert len(result) == 1
        assert result[0].chain_id == "cinemark"

    async def test_filter_by_date_and_chain(self, db: Database) -> None:
        await db.upsert_showtimes(
            [
                _make_showtime(
                    chain_id="cinemark", show_date=date(2024, 6, 1)
                ),
                _make_showtime(
                    movie="Other",
                    chain_id="cinemark",
                    show_date=date(2024, 6, 2),
                ),
            ]
        )
        result = await db.get_showtimes(
            date=date(2024, 6, 1), chain_id="cinemark"
        )
        assert len(result) == 1


# ---------------------------------------------------------------------------
# get_movies
# ---------------------------------------------------------------------------


class TestGetMovies:
    async def test_returns_distinct_titles(self, db: Database) -> None:
        await db.upsert_showtimes(
            [
                _make_showtime("Inception"),
                _make_showtime("Inception", fmt="3D"),  # same title, different format
                _make_showtime("Dune"),
            ]
        )
        movies = await db.get_movies()
        assert sorted(movies) == ["Dune", "Inception"]

    async def test_filter_by_chain(self, db: Database) -> None:
        await db.upsert_showtimes(
            [
                _make_showtime("Film A", chain_id="cinemark"),
            ]
        )
        assert await db.get_movies(chain_id="cinemark") == ["Film A"]

    async def test_empty_when_no_data(self, db: Database) -> None:
        assert await db.get_movies() == []


# ---------------------------------------------------------------------------
# get_theaters
# ---------------------------------------------------------------------------


class TestGetTheaters:
    async def test_returns_theaters(self, db: Database) -> None:
        theater = _make_theater("Cinema Norte", chain_id="cinemark")
        await db.upsert_showtimes([_make_showtime(theater=theater)])
        theaters = await db.get_theaters()
        assert len(theaters) == 1
        assert theaters[0].name == "Cinema Norte"

    async def test_filter_by_chain(self, db: Database) -> None:
        t1 = _make_theater("T1", chain_id="cinemark")
        await db.upsert_showtimes(
            [
                _make_showtime(theater=t1, chain_id="cinemark"),
            ]
        )
        result = await db.get_theaters(chain_id="cinemark")
        assert len(result) == 1
        assert result[0].chain_id == "cinemark"


# ---------------------------------------------------------------------------
# get_chains
# ---------------------------------------------------------------------------


class TestGetChains:
    async def test_returns_chain_ids(self, db: Database) -> None:
        await db.upsert_showtimes(
            [
                _make_showtime(chain_id="cinemark"),
            ]
        )
        chains = await db.get_chains()
        assert sorted(chains) == ["cinemark"]

    async def test_empty_when_no_data(self, db: Database) -> None:
        assert await db.get_chains() == []
