"""Tests for the abstract base classes and the BaseChain.scrape() method."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cinema.exceptions import FetchError, ParseError
from cinema.models import Showtime, Theater
from cinema.scraper.base import BaseChain, BaseFetcher, BaseParser


# ---------------------------------------------------------------------------
# Concrete stubs that satisfy the ABCs
# ---------------------------------------------------------------------------


class _StubFetcher(BaseFetcher):
    def __init__(self, html: str = "<html/>") -> None:
        self._html = html

    async def fetch(self, url: str) -> str:  # noqa: ARG002
        return self._html


class _StubParser(BaseParser):
    def __init__(self, result: list[Showtime] | None = None) -> None:
        self._result = result or []

    def parse(self, html: str) -> list[Showtime]:  # noqa: ARG002
        return self._result


class _StubChain(BaseChain):
    def __init__(
        self,
        fetcher: BaseFetcher,
        parser: BaseParser,
        urls: list[str] | None = None,
    ) -> None:
        self._fetcher = fetcher
        self._parser = parser
        self._urls = urls or ["http://example.com"]

    @property
    def chain_id(self) -> str:
        return "stub"

    @property
    def display_name(self) -> str:
        return "Stub Chain"

    @property
    def urls(self) -> list[str]:
        return self._urls

    @property
    def fetcher(self) -> BaseFetcher:
        return self._fetcher

    @property
    def parser(self) -> BaseParser:
        return self._parser


# ---------------------------------------------------------------------------
# Helper factory
# ---------------------------------------------------------------------------

def _make_showtime(movie: str = "Test Movie", chain: str = "stub") -> Showtime:
    return Showtime(
        movie=movie,
        theater=Theater(
            name="Test Theater",
            address="Av. Test 123",
            district="Test District",
            region="Test Region",
            chain_id=chain,
        ),
        date=date(2024, 6, 1),
        times=["14:00", "17:00"],
        format="2D",
        language="SUB",
        chain_id=chain,
    )


# ---------------------------------------------------------------------------
# BaseFetcher contract
# ---------------------------------------------------------------------------


class TestBaseFetcherContract:
    """BaseFetcher must be abstract and require fetch()."""

    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            BaseFetcher()  # type: ignore[abstract]

    async def test_stub_fetcher_returns_html(self) -> None:
        fetcher = _StubFetcher("<p>hello</p>")
        result = await fetcher.fetch("http://example.com")
        assert result == "<p>hello</p>"


# ---------------------------------------------------------------------------
# BaseParser contract
# ---------------------------------------------------------------------------


class TestBaseParserContract:
    """BaseParser must be abstract and require parse()."""

    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            BaseParser()  # type: ignore[abstract]

    def test_stub_parser_returns_list(self) -> None:
        expected = [_make_showtime()]
        parser = _StubParser(expected)
        assert parser.parse("<html/>") == expected


# ---------------------------------------------------------------------------
# BaseChain.scrape() orchestration
# ---------------------------------------------------------------------------


class TestBaseChainScrape:
    """BaseChain.scrape() must call fetcher and parser for each URL."""

    async def test_scrape_aggregates_across_urls(self) -> None:
        st1 = _make_showtime("Movie A")
        st2 = _make_showtime("Movie B")

        fetcher = _StubFetcher("<html/>")
        parser = _StubParser([st1, st2])
        chain = _StubChain(fetcher, parser, urls=["http://url1", "http://url2"])

        result = await chain.scrape()
        assert len(result) == 4  # 2 showtimes × 2 URLs

    async def test_scrape_empty_urls_returns_empty(self) -> None:
        chain = _StubChain(_StubFetcher(), _StubParser(), urls=[])
        assert await chain.scrape() == []

    async def test_fetch_error_propagates(self) -> None:
        class _ErrorFetcher(BaseFetcher):
            async def fetch(self, url: str) -> str:
                raise FetchError("network down")

        chain = _StubChain(_ErrorFetcher(), _StubParser())
        with pytest.raises(FetchError, match="network down"):
            await chain.scrape()

    async def test_parse_error_propagates(self) -> None:
        class _ErrorParser(BaseParser):
            def parse(self, html: str) -> list[Showtime]:
                raise ParseError("bad html")

        chain = _StubChain(_StubFetcher(), _ErrorParser())
        with pytest.raises(ParseError, match="bad html"):
            await chain.scrape()
