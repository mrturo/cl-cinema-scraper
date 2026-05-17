"""Chain-agnostic domain models."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class Theater(BaseModel):
    """A physical cinema theater location."""

    name: str
    address: str
    district: str
    region: str
    city: str | None = None
    chain_id: str

    @field_validator("name", "address", "district", "region")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        """Reject empty or whitespace-only strings."""
        if not v.strip():
            raise ValueError("Field must not be blank")
        return v.strip()


class Movie(BaseModel):
    """Metadata about a film (optional enrichment layer)."""

    title: str
    genre: str | None = None
    duration_min: int | None = None
    rating: str | None = None


class Showtime(BaseModel):
    """A set of screening times for one movie at one theater on one date."""

    movie: str
    theater: Theater
    date: date
    times: list[str]
    format: str
    language: str
    chain_id: str
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Accept only known projection formats."""
        allowed = {"2D", "3D", "XD", "4DX", "IMAX"}
        if v not in allowed:
            raise ValueError(f"Format must be one of {allowed}")
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Accept only known audio/subtitle modes."""
        allowed = {"SUB", "DUB"}
        if v not in allowed:
            raise ValueError(f"Language must be one of {allowed}")
        return v
