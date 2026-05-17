"""REST API route definitions."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from cinema.api.dependencies import get_db
from cinema.exceptions import ChainNotFoundError
from cinema.models import Showtime, Theater
from cinema.scraper.registry import ChainRegistry
from cinema.storage.database import Database

router = APIRouter()


@router.get("/showtimes", response_model=list[Showtime])
async def list_showtimes(
    date: date | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
    chain_id: str | None = Query(None, description="Filter by chain ID"),
    db: Database = Depends(get_db),
) -> list[Showtime]:
    """Return showtimes, optionally filtered by date and/or chain.

    Args:
        date: ISO date string to filter on.
        chain_id: Chain identifier to filter on (e.g. ``cinemark``).
        db: Injected database dependency.
    """
    if chain_id is not None:
        try:
            ChainRegistry.get(chain_id)
        except ChainNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return await db.get_showtimes(date=date, chain_id=chain_id)


@router.get("/movies", response_model=list[str])
async def list_movies(
    chain_id: str | None = Query(None, description="Filter by chain ID"),
    db: Database = Depends(get_db),
) -> list[str]:
    """Return distinct movie titles in alphabetical order.

    Args:
        chain_id: Chain identifier to filter on.
        db: Injected database dependency.
    """
    if chain_id is not None:
        try:
            ChainRegistry.get(chain_id)
        except ChainNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return await db.get_movies(chain_id=chain_id)


@router.get("/theaters", response_model=list[Theater])
async def list_theaters(
    chain_id: str | None = Query(None, description="Filter by chain ID"),
    db: Database = Depends(get_db),
) -> list[Theater]:
    """Return all theaters, optionally filtered by chain.

    Args:
        chain_id: Chain identifier to filter on.
        db: Injected database dependency.
    """
    if chain_id is not None:
        try:
            ChainRegistry.get(chain_id)
        except ChainNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return await db.get_theaters(chain_id=chain_id)


@router.get("/chains", response_model=list[dict])
async def list_chains() -> list[dict[str, str]]:
    """Return all registered chains with their IDs and display names."""
    return [
        {"chain_id": chain.chain_id, "display_name": chain.display_name}
        for chain in ChainRegistry.all()
    ]
