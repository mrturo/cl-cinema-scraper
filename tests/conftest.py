"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from cinema.scraper.registry import ChainRegistry


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio as the anyio backend for all async tests."""
    return "asyncio"


@pytest.fixture(autouse=True)
def clear_chain_registry() -> None:
    """Reset the global chain registry before every test.

    This prevents registration side-effects from one test leaking into
    another when test modules import chain packages.
    """
    ChainRegistry.clear()
    yield  # type: ignore[misc]
    ChainRegistry.clear()
