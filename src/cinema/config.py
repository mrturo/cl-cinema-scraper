"""Global application settings loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration.

    All values can be overridden via environment variables or a .env file.
    Chain-specific URL lists use JSON array format in the .env file, e.g.
    ``CINEMARK_URLS=["https://url1","https://url2"]``.
    """

    headless: bool = True
    scraping_interval_hours: int = 6
    min_scraping_interval_hours: int = 4
    db_path: Path = Path("cinema.db")
    request_delay_seconds: float = 2.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    log_level: str = "INFO"

    # Chain-specific URL lists (JSON array format in .env)
    cinemark_urls: list[str] = []

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
