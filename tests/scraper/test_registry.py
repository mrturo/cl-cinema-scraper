"""Tests for the chain registry."""

from __future__ import annotations

import pytest

from cinema.exceptions import ChainNotFoundError
from cinema.models import Showtime
from cinema.scraper.base import BaseChain, BaseFetcher, BaseParser
from cinema.scraper.registry import ChainRegistry


# ---------------------------------------------------------------------------
# Minimal stubs
# ---------------------------------------------------------------------------


class _MinimalFetcher(BaseFetcher):
    async def fetch(self, url: str) -> str:  # noqa: ARG002
        return ""


class _MinimalParser(BaseParser):
    def parse(self, html: str) -> list[Showtime]:  # noqa: ARG002
        return []


def _make_chain(chain_id: str, display_name: str = "Test") -> BaseChain:
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
            return _MinimalFetcher()

        @property
        def parser(self) -> BaseParser:
            return _MinimalParser()

    return _Chain()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestChainRegistration:
    def test_register_single_chain(self) -> None:
        chain = _make_chain("alpha")
        ChainRegistry.register(chain)
        assert ChainRegistry.get("alpha") is chain

    def test_register_multiple_chains(self) -> None:
        ChainRegistry.register(_make_chain("alpha"))
        ChainRegistry.register(_make_chain("beta"))
        assert len(ChainRegistry.all()) == 2

    def test_duplicate_registration_raises(self) -> None:
        ChainRegistry.register(_make_chain("alpha"))
        with pytest.raises(ValueError, match="already registered"):
            ChainRegistry.register(_make_chain("alpha"))

    def test_all_returns_registered_order(self) -> None:
        ChainRegistry.register(_make_chain("first"))
        ChainRegistry.register(_make_chain("second"))
        ids = [c.chain_id for c in ChainRegistry.all()]
        assert ids == ["first", "second"]


class TestChainRetrieval:
    def test_get_existing_chain(self) -> None:
        chain = _make_chain("my_chain", "My Chain")
        ChainRegistry.register(chain)
        assert ChainRegistry.get("my_chain").display_name == "My Chain"

    def test_get_missing_chain_raises(self) -> None:
        with pytest.raises(ChainNotFoundError, match="not registered"):
            ChainRegistry.get("nonexistent")


class TestRegistryClear:
    def test_clear_empties_registry(self) -> None:
        ChainRegistry.register(_make_chain("alpha"))
        ChainRegistry.clear()
        assert ChainRegistry.all() == []

    def test_re_registration_after_clear(self) -> None:
        ChainRegistry.register(_make_chain("alpha"))
        ChainRegistry.clear()
        chain = _make_chain("alpha")
        ChainRegistry.register(chain)  # should not raise
        assert ChainRegistry.get("alpha") is chain
