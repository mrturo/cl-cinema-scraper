"""Cinemark Chile chain definition and self-registration."""

from cinema.config import settings
from cinema.scraper.base import BaseChain, BaseFetcher, BaseParser
from cinema.scraper.chains.cinemark.fetcher import CinemarkFetcher
from cinema.scraper.chains.cinemark.parser import CinemarkParser
from cinema.scraper.registry import ChainRegistry


class CinemarkChain(BaseChain):
    """Cinemark Chile cinema chain integration."""

    @property
    def chain_id(self) -> str:
        """Unique identifier for this chain."""
        return "cinemark"

    @property
    def display_name(self) -> str:
        """Human-readable chain name."""
        return "Cinemark Chile"

    @property
    def urls(self) -> list[str]:
        """Theater URLs loaded from ``CINEMARK_URLS`` in the environment."""
        return settings.cinemark_urls

    @property
    def fetcher(self) -> BaseFetcher:
        """Returns a :class:`CinemarkFetcher` instance."""
        return CinemarkFetcher()

    @property
    def parser(self) -> BaseParser:
        """Returns a :class:`CinemarkParser` instance."""
        return CinemarkParser()


ChainRegistry.register(CinemarkChain())
