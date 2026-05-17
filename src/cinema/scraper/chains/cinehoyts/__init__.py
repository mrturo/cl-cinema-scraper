"""CineHoyts Chile chain definition and self-registration."""

from cinema.config import settings
from cinema.scraper.base import BaseChain, BaseFetcher, BaseParser
from cinema.scraper.chains.cinehoyts.fetcher import CineHoytsFetcher
from cinema.scraper.chains.cinehoyts.parser import CineHoytsParser
from cinema.scraper.registry import ChainRegistry


class CineHoytsChain(BaseChain):
    """CineHoyts Chile cinema chain integration."""

    @property
    def chain_id(self) -> str:
        """Unique identifier for this chain."""
        return "cinehoyts"

    @property
    def display_name(self) -> str:
        """Human-readable chain name."""
        return "CineHoyts Chile"

    @property
    def urls(self) -> list[str]:
        """Theater URLs loaded from ``CINEHOYTS_URLS`` in the environment."""
        return settings.cinehoyts_urls

    @property
    def fetcher(self) -> BaseFetcher:
        """Returns a :class:`CineHoytsFetcher` instance."""
        return CineHoytsFetcher()

    @property
    def parser(self) -> BaseParser:
        """Returns a :class:`CineHoytsParser` instance."""
        return CineHoytsParser()


ChainRegistry.register(CineHoytsChain())
