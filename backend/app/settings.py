from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """
    Local-first settings (no Docker required).

    Defaults are optimized for personal/local use:
    - SQLite for storage
    - Earth Engine for server-side compute + tiles
    """

    model_config = SettingsConfigDict(
        # Always read the repo-root .env (works regardless of cwd).
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "SatelliteMigration"
    api_v1_prefix: str = "/api/v1"
    environment: Literal["development", "production"] = "development"
    debug: bool = True

    # CORS
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Local storage
    database_path: str = Field(default="data/satellite.sqlite3")
    exports_dir: str = Field(default="data/exports")

    # Regions
    auto_seed_predefined_regions: bool = True

    # Earth Engine
    gee_project_id: str | None = None
    gee_service_account_key: str | None = None  # Path to service-account JSON

    # Limits
    max_timeseries_points: int = Field(default=2000, ge=1)

    # Tile/viz defaults
    default_tile_opacity: float = Field(default=0.7, ge=0.0, le=1.0)
    tile_token_ttl_seconds: int = Field(default=6 * 60 * 60, ge=60)

    @property
    def database_url(self) -> str:
        path = Path(self.database_path).expanduser()
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{path}"

    @property
    def exports_path(self) -> Path:
        path = Path(self.exports_dir).expanduser()
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        path = path.resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in raw.split(",") if origin.strip()]
        return [str(value).strip()] if str(value).strip() else []


@lru_cache
def get_settings() -> Settings:
    return Settings()
