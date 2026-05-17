"""Minimal aiosqlite shim — wraps sqlite3 with asyncio."""
from __future__ import annotations

import asyncio
import sqlite3
from typing import Any, Optional, Sequence

Row = sqlite3.Row
Error = sqlite3.Error


class AsyncCursor:
    def __init__(self, cursor: sqlite3.Cursor) -> None:
        self._cursor = cursor

    async def fetchall(self) -> list:
        loop = asyncio.get_event_loop()
        cursor = self._cursor
        return await loop.run_in_executor(None, cursor.fetchall)

    async def fetchone(self) -> Any:
        loop = asyncio.get_event_loop()
        cursor = self._cursor
        return await loop.run_in_executor(None, cursor.fetchone)

    @property
    def lastrowid(self) -> Optional[int]:
        return self._cursor.lastrowid


class AsyncConnection:
    def __init__(self, path: str) -> None:
        self._path = path
        self._conn: Optional[sqlite3.Connection] = None
        self._row_factory: Any = None

    @property
    def row_factory(self) -> Any:
        return self._row_factory

    @row_factory.setter
    def row_factory(self, value: Any) -> None:
        self._row_factory = value
        if self._conn is not None:
            self._conn.row_factory = sqlite3.Row if value is Row else value

    async def __aenter__(self) -> "AsyncConnection":
        loop = asyncio.get_event_loop()
        path = self._path

        def _open() -> sqlite3.Connection:
            return sqlite3.connect(path, check_same_thread=False)

        self._conn = await loop.run_in_executor(None, _open)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._conn is not None:
            conn = self._conn
            if exc_type is not None:
                conn.rollback()
            await asyncio.get_event_loop().run_in_executor(None, conn.close)
            self._conn = None

    async def execute(self, sql: str, parameters: Sequence[Any] = ()) -> AsyncCursor:
        loop = asyncio.get_event_loop()
        conn = self._conn
        assert conn is not None, "Connection is not open"
        row_factory = self._row_factory

        def _run() -> sqlite3.Cursor:
            if row_factory is not None:
                conn.row_factory = sqlite3.Row if row_factory is Row else row_factory
            return conn.execute(sql, parameters)

        cursor = await loop.run_in_executor(None, _run)
        return AsyncCursor(cursor)

    async def commit(self) -> None:
        loop = asyncio.get_event_loop()
        conn = self._conn
        assert conn is not None, "Connection is not open"
        await loop.run_in_executor(None, conn.commit)


def connect(path: str) -> AsyncConnection:
    return AsyncConnection(path)
