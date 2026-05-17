"""Abstract base classes that define the contracts for every cinema chain."""

from abc import ABC, abstractmethod

from cinema.exceptions import FetchError, ParseError  # noqa: F401 – re-exported
from cinema.models import Showtime


class BaseFetcher(ABC):
    """Defines how to retrieve raw HTML for a cinema chain."""

    @abstractmethod
    async def fetch(self, url: str) -> str:
        """Fetch rendered HTML from the given URL.

        Args:
            url: Target page URL.

        Returns:
            Rendered HTML as a string.

        Raises:
            FetchError: If the page cannot be retrieved.
        """


class BaseParser(ABC):
    """Defines how to extract structured data from raw HTML."""

    @abstractmethod
    def parse(self, html: str) -> list[Showtime]:
        """Parse rendered HTML and return a list of showtimes.

        Args:
            html: Rendered HTML string from the fetcher.

        Returns:
            List of Showtime domain objects.

        Raises:
            ParseError: If the HTML structure is unexpected.
        """


class BaseChain(ABC):
    """Top-level contract for a cinema chain integration.

    Each chain must declare its identity and provide its own fetcher and
    parser implementations.  The ``scrape`` orchestration method is
    implemented here once and must **not** be overridden by subclasses.
    """

    @property
    @abstractmethod
    def chain_id(self) -> str:
        """Unique machine-readable identifier, e.g. ``'cinemark'``."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name, e.g. ``'Cinemark Chile'``."""

    @property
    @abstractmethod
    def urls(self) -> list[str]:
        """List of URLs to scrape (one per theater or region)."""

    @property
    @abstractmethod
    def fetcher(self) -> BaseFetcher:
        """Returns the fetcher instance for this chain."""

    @property
    @abstractmethod
    def parser(self) -> BaseParser:
        """Returns the parser instance for this chain."""

    async def scrape(self) -> list[Showtime]:
        """Orchestrate fetch + parse for every URL in this chain.

        Chains do **not** override this method.

        Returns:
            Aggregated list of showtimes across all URLs.
        """
        showtimes: list[Showtime] = []
        for url in self.urls:
            html = await self.fetcher.fetch(url)
            showtimes.extend(self.parser.parse(html))
        return showtimes
