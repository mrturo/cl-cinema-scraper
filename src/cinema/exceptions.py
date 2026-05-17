"""Custom exception hierarchy for the cinema scraper."""


class CinemaError(Exception):
    """Base exception for all scraper errors."""


class FetchError(CinemaError):
    """Raised when the browser or network fails to retrieve the page."""


class ParseError(CinemaError):
    """Raised when structured data cannot be extracted from HTML."""


class StorageError(CinemaError):
    """Raised when a database read or write operation fails."""


class ChainNotFoundError(CinemaError):
    """Raised when a requested chain_id is not registered."""
