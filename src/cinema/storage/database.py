"""Chain-agnostic async SQLite storage layer."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path

import aiosqlite

from cinema.config import settings
from cinema.exceptions import StorageError
from cinema.models import Showtime, Theater

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------
_CREATE_THEATERS = """
CREATE TABLE IF NOT EXISTS theaters (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id TEXT NOT NULL,
    name     TEXT NOT NULL,
    address  TEXT NOT NULL,
    district TEXT NOT NULL,
    region   TEXT NOT NULL,
    city     TEXT,
    UNIQUE(chain_id, name, address)
)
"""

_CREATE_SHOWTIMES = """
CREATE TABLE IF NOT EXISTS showtimes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id    TEXT    NOT NULL,
    movie       TEXT    NOT NULL,
    theater_id  INTEGER NOT NULL REFERENCES theaters(id),
    date        TEXT    NOT NULL,
    times       TEXT    NOT NULL,   -- JSON array of HH:MM strings
    format      TEXT    NOT NULL,
    language    TEXT    NOT NULL,
    scraped_at  TEXT    NOT NULL,
    UNIQUE(chain_id, movie, theater_id, date, format, language)
)
"""


class Database:
    """Async SQLite storage for showtimes and theaters.

    All queries are chain-agnostic; ``chain_id`` is used only as a filter
    parameter when explicitly requested.

    Args:
        db_path: Override the database file path.  Defaults to
            :attr:`~cinema.config.Settings.db_path`.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._path = str(db_path or settings.db_path)

    async def initialize(self) -> None:
        """Create tables if they do not already exist.

        Raises:
            StorageError: On any SQLite error.
        """
        try:
            async with aiosqlite.connect(self._path) as db:
                await db.execute(_CREATE_THEATERS)
                await db.execute(_CREATE_SHOWTIMES)
                await db.commit()
        except aiosqlite.Error as exc:
            raise StorageError(
                f"Failed to initialize database at '{self._path}': {exc}"
            ) from exc

    async def upsert_showtimes(self, showtimes: list[Showtime]) -> None:
        """Insert or update a batch of showtimes.

        For each showtime the theater row is upserted first, then the
        showtime row is inserted or updated (preserving id).

        Args:
            showtimes: List of :class:`~cinema.models.Showtime` objects.

        Raises:
            StorageError: On any SQLite error.
        """
        try:
            async with aiosqlite.connect(self._path) as db:
                for showtime in showtimes:
                    t = showtime.theater

                    # Upsert theater ------------------------------------------------
                    await db.execute(
                        """
                        INSERT INTO theaters
                            (chain_id, name, address, district, region, city)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(chain_id, name, address) DO UPDATE SET
                            district   = excluded.district,
                            region     = excluded.region,
                            city       = excluded.city
                        """,
                        (
                            t.chain_id,
                            t.name,
                            t.address,
                            t.district,
                            t.region,
                            t.city,
                        ),
                    )

                    cursor = await db.execute(
                        "SELECT id FROM theaters "
                        "WHERE chain_id = ? AND name = ? AND address = ?",
                        (t.chain_id, t.name, t.address),
                    )
                    row = await cursor.fetchone()
                    theater_id: int = row[0]  # type: ignore[index]

                    # Upsert showtime -----------------------------------------------
                    await db.execute(
                        """
                        INSERT INTO showtimes
                            (chain_id, movie, theater_id, date, times,
                             format, language, scraped_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(chain_id, movie, theater_id, date, format, language)
                        DO UPDATE SET
                            times      = excluded.times,
                            scraped_at = excluded.scraped_at
                        """,
                        (
                            showtime.chain_id,
                            showtime.movie,
                            theater_id,
                            showtime.date.isoformat(),
                            json.dumps(showtime.times),
                            showtime.format,
                            showtime.language,
                            showtime.scraped_at.isoformat(),
                        ),
                    )

                await db.commit()
                logger.debug("Upserted %d showtimes", len(showtimes))

        except aiosqlite.Error as exc:
            raise StorageError(f"Failed to upsert showtimes: {exc}") from exc

    async def get_showtimes(
        self,
        date: date | None = None,
        chain_id: str | None = None,
    ) -> list[Showtime]:
        """Retrieve showtimes with optional date and chain filters.

        Args:
            date: Return only showtimes on this date.
            chain_id: Return only showtimes for this chain.

        Returns:
            List of :class:`~cinema.models.Showtime` objects.

        Raises:
            StorageError: On any SQLite error.
        """
        conditions: list[str] = []
        params: list[str] = []
        if date is not None:
            conditions.append("s.date = ?")
            params.append(date.isoformat())
        if chain_id is not None:
            conditions.append("s.chain_id = ?")
            params.append(chain_id)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        sql = f"""
            SELECT
                s.chain_id,
                s.movie,
                s.date,
                s.times,
                s.format,
                s.language,
                s.scraped_at,
                t.name     AS t_name,
                t.address  AS t_address,
                t.district AS t_district,
                t.region   AS t_region,
                t.city     AS t_city,
                t.chain_id AS t_chain_id
            FROM showtimes s
            JOIN theaters t ON t.id = s.theater_id
            {where_clause}
            ORDER BY s.date, t.name, s.movie
        """
        try:
            async with aiosqlite.connect(self._path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(sql, params)
                rows = await cursor.fetchall()
                return [_row_to_showtime(row) for row in rows]
        except aiosqlite.Error as exc:
            raise StorageError(f"Failed to query showtimes: {exc}") from exc

    async def get_movies(self, chain_id: str | None = None) -> list[str]:
        """Return distinct movie titles in alphabetical order.

        Args:
            chain_id: Restrict results to one chain when provided.

        Returns:
            List of movie title strings.

        Raises:
            StorageError: On any SQLite error.
        """
        sql = "SELECT DISTINCT movie FROM showtimes"
        params: list[str] = []
        if chain_id is not None:
            sql += " WHERE chain_id = ?"
            params.append(chain_id)
        sql += " ORDER BY movie"
        try:
            async with aiosqlite.connect(self._path) as db:
                cursor = await db.execute(sql, params)
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
        except aiosqlite.Error as exc:
            raise StorageError(f"Failed to query movies: {exc}") from exc

    async def get_theaters(self, chain_id: str | None = None) -> list[Theater]:
        """Return all theaters in alphabetical order.

        Args:
            chain_id: Restrict results to one chain when provided.

        Returns:
            List of :class:`~cinema.models.Theater` objects.

        Raises:
            StorageError: On any SQLite error.
        """
        sql = "SELECT * FROM theaters"
        params: list[str] = []
        if chain_id is not None:
            sql += " WHERE chain_id = ?"
            params.append(chain_id)
        sql += " ORDER BY name"
        try:
            async with aiosqlite.connect(self._path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(sql, params)
                rows = await cursor.fetchall()
                return [
                    Theater(
                        name=row["name"],
                        address=row["address"],
                        district=row["district"],
                        region=row["region"],
                        city=row["city"],
                        chain_id=row["chain_id"],
                    )
                    for row in rows
                ]
        except aiosqlite.Error as exc:
            raise StorageError(f"Failed to query theaters: {exc}") from exc

    async def get_chains(self) -> list[str]:
        """Return distinct chain IDs that have data in the database.

        Returns:
            Sorted list of chain ID strings.

        Raises:
            StorageError: On any SQLite error.
        """
        try:
            async with aiosqlite.connect(self._path) as db:
                cursor = await db.execute(
                    "SELECT DISTINCT chain_id FROM theaters ORDER BY chain_id"
                )
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
        except aiosqlite.Error as exc:
            raise StorageError(f"Failed to query chains: {exc}") from exc


# ---------------------------------------------------------------------------
# Row converter
# ---------------------------------------------------------------------------


def _row_to_showtime(row: aiosqlite.Row) -> Showtime:
    """Convert a raw database row to a :class:`~cinema.models.Showtime`.

    Args:
        row: An :class:`aiosqlite.Row` from the joined showtimes query.

    Returns:
        A :class:`~cinema.models.Showtime` domain object.
    """
    return Showtime(
        chain_id=row["chain_id"],
        movie=row["movie"],
        theater=Theater(
            name=row["t_name"],
            address=row["t_address"],
            district=row["t_district"],
            region=row["t_region"],
            city=row["t_city"],
            chain_id=row["t_chain_id"],
        ),
        date=date.fromisoformat(row["date"]),
        times=json.loads(row["times"]),
        format=row["format"],
        language=row["language"],
        scraped_at=datetime.fromisoformat(row["scraped_at"]),
    )
