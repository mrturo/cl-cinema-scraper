"""Tests for the FastAPI REST endpoints."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from cinema.api.dependencies import get_db
from cinema.api.main import app
from cinema.models import Showtime, Theater
from cinema.scraper.base import BaseChain, BaseFetcher, BaseParser
from cinema.scraper.registry import ChainRegistry
from cinema.storage.database import Database


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_theater(
    name: str = "Cinema Test",
    chain_id: str = "testchain",
) -> Theater:
    return Theater(
        name=name,
        address="Av. Test 1",
        district="Providencia",
        region="Región Metropolitana",
        chain_id=chain_id,
    )


def _make_showtime(
    movie: str = "Test Movie",
    chain_id: str = "testchain",
    theater: Theater | None = None,
    show_date: date = date(2024, 6, 1),
) -> Showtime:
    return Showtime(
        movie=movie,
        theater=theater or _make_theater(chain_id=chain_id),
        date=show_date,
        times=["14:00"],
        format="2D",
        language="SUB",
        chain_id=chain_id,
    )


def _make_stub_chain(chain_id: str, display_name: str = "Test Chain") -> BaseChain:
    class _StubFetcher(BaseFetcher):
        async def fetch(self, url: str) -> str:  # noqa: ARG002
            return ""

    class _StubParser(BaseParser):
        def parse(self, html: str) -> list[Showtime]:  # noqa: ARG002
            return []

    class _Chain(BaseChain):
        @property
        def chain_id(self) -> str:
            return chain_id

        @property
        def display_name(self) -> str:
            return display_name

        @property
        def urls(self) -> list[str]:
            return []

        @property
        def fetcher(self) -> BaseFetcher:
            return _StubFetcher()

        @property
        def parser(self) -> BaseParser:
            return _StubParser()

    return _Chain()


@pytest.fixture
async def db(tmp_path: Path) -> Database:
    """Isolated database for each test."""
    database = Database(db_path=tmp_path / "api_test.db")
    await database.initialize()
    return database


@pytest.fixture
def client(db: Database):
    """AsyncClient backed by the FastAPI app, using the test database."""
    app.dependency_overrides[get_db] = lambda: db
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# /chains
# ---------------------------------------------------------------------------


class TestChainsEndpoint:
    async def test_returns_registered_chains(self, client) -> None:
        ChainRegistry.register(_make_stub_chain("cinemark", "Cinemark Chile"))

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/chains")

        assert response.status_code == 200
        data = response.json()
        ids = [item["chain_id"] for item in data]
        assert "cinemark" in ids

    async def test_returns_empty_when_no_chains(self, client) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/chains")

        assert response.status_code == 200
        assert response.json() == []


# ---------------------------------------------------------------------------
# /showtimes
# ---------------------------------------------------------------------------


class TestShowtimesEndpoint:
    async def test_returns_all_showtimes(self, client, db: Database) -> None:
        await db.upsert_showtimes(
            [_make_showtime("Film A"), _make_showtime("Film B")]
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/showtimes")

        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_filter_by_date(self, client, db: Database) -> None:
        await db.upsert_showtimes(
            [
                _make_showtime(show_date=date(2024, 6, 1)),
                _make_showtime(movie="Film B", show_date=date(2024, 6, 2)),
            ]
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/showtimes?date=2024-06-01")

        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_filter_by_chain_id(self, client, db: Database) -> None:
        ChainRegistry.register(_make_stub_chain("cinemark"))
        await db.upsert_showtimes(
            [
                _make_showtime(chain_id="cinemark"),
                _make_showtime(movie="Film B", chain_id="other"),
            ]
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/showtimes?chain_id=cinemark")

        assert response.status_code == 200
        for item in response.json():
            assert item["chain_id"] == "cinemark"

    async def test_unknown_chain_returns_404(self, client) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/showtimes?chain_id=nonexistent")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# /movies
# ---------------------------------------------------------------------------


class TestMoviesEndpoint:
    async def test_returns_distinct_titles(self, client, db: Database) -> None:
        await db.upsert_showtimes(
            [_make_showtime("Inception"), _make_showtime("Dune")]
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/movies")

        assert response.status_code == 200
        assert sorted(response.json()) == ["Dune", "Inception"]

    async def test_filter_by_chain(self, client, db: Database) -> None:
        ChainRegistry.register(_make_stub_chain("cinemark"))
        await db.upsert_showtimes(
            [
                _make_showtime("Film A", chain_id="cinemark"),
            ]
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/movies?chain_id=cinemark")

        assert response.status_code == 200
        assert response.json() == ["Film A"]


# ---------------------------------------------------------------------------
# /theaters
# ---------------------------------------------------------------------------


class TestTheatersEndpoint:
    async def test_returns_theaters(self, client, db: Database) -> None:
        theater = _make_theater("Grand Cinema")
        await db.upsert_showtimes([_make_showtime(theater=theater)])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/theaters")

        assert response.status_code == 200
        names = [t["name"] for t in response.json()]
        assert "Grand Cinema" in names

    async def test_filter_by_chain(self, client, db: Database) -> None:
        ChainRegistry.register(_make_stub_chain("cinemark"))
        t_cm = _make_theater("Cinema Norte", chain_id="cinemark")
        await db.upsert_showtimes(
            [
                _make_showtime(theater=t_cm, chain_id="cinemark"),
            ]
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/theaters?chain_id=cinemark")

        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["chain_id"] == "cinemark"
