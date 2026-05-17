"""FastAPI dependency providers."""

from __future__ import annotations

from cinema.storage.database import Database

_db: Database | None = None


def get_db() -> Database:
    """Return the shared :class:`~cinema.storage.database.Database` instance.

    Uses a module-level singleton so the same connection pool is shared
    across all requests within a process.

    Returns:
        The application-wide :class:`~cinema.storage.database.Database`.
    """
    global _db
    if _db is None:
        _db = Database()
    return _db
