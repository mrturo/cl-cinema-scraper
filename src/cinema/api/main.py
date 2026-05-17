"""FastAPI application factory and entry point."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI

import cinema.scraper.chains  # noqa: F401 — triggers chain self-registration
from cinema.api.dependencies import get_db
from cinema.api.routes import router
from cinema.config import settings

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: initialise the database on startup."""
    db = get_db()
    await db.initialize()
    yield


app = FastAPI(
    title="Cinema Scraper API",
    description="REST API for Chilean cinema showtimes.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)


def run() -> None:
    """Entry point for the ``cinema-api`` console script."""
    uvicorn.run(
        "cinema.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    run()
