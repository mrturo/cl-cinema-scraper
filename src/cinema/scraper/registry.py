"""Central registry where cinema chains self-register on import."""

import logging

from cinema.exceptions import ChainNotFoundError
from cinema.scraper.base import BaseChain

logger = logging.getLogger(__name__)


class ChainRegistry:
    """Singleton registry of all available cinema chain integrations.

    Chains call :meth:`register` from their own ``__init__.py`` on import,
    so importing ``cinema.scraper.chains`` is enough to populate the registry.
    """

    _chains: dict[str, BaseChain] = {}

    @classmethod
    def register(cls, chain: BaseChain) -> None:
        """Register a chain.

        Args:
            chain: A fully constructed :class:`BaseChain` instance.

        Raises:
            ValueError: If ``chain.chain_id`` is already registered.
        """
        if chain.chain_id in cls._chains:
            raise ValueError(f"Chain '{chain.chain_id}' is already registered")
        cls._chains[chain.chain_id] = chain
        logger.info(
            "Registered chain: %s (%s)", chain.chain_id, chain.display_name
        )

    @classmethod
    def get(cls, chain_id: str) -> BaseChain:
        """Retrieve a chain by its ID.

        Args:
            chain_id: The machine-readable chain identifier.

        Returns:
            The registered :class:`BaseChain` instance.

        Raises:
            ChainNotFoundError: If ``chain_id`` is not registered.
        """
        if chain_id not in cls._chains:
            raise ChainNotFoundError(
                f"Chain '{chain_id}' is not registered. "
                f"Available chains: {list(cls._chains)}"
            )
        return cls._chains[chain_id]

    @classmethod
    def all(cls) -> list[BaseChain]:
        """Return all registered chains in registration order."""
        return list(cls._chains.values())

    @classmethod
    def clear(cls) -> None:
        """Remove all registered chains.

        Intended for test isolation only — do not call in production code.
        """
        cls._chains.clear()
