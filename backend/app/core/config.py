import json
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields in .env
    )

    # Application
    app_name: str = "SatelliteMigration"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # CORS
    cors_origins: list[str] = [
        "http://localhost:5173",  # Vite dev server
        "http://localhost:5174",  # Vite dev server (alternate port)
        "http://localhost:3000",  # React dev server
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ]

    # Database
    database_url: str = "postgresql+asyncpg://satellite:satellite_dev@localhost:5432/satellite_data"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Data paths
    data_dir: str = "/data"
    cache_dir: str = "/data/cache"
    exports_dir: str = "/data/exports"
    regions_dir: str = "/data/regions"
    rasters_dir: str = "/data/rasters"  # Storage for metric raster GeoTIFFs

    # Satellite providers - Google Earth Engine
    gee_project_id: str | None = None
    gee_service_account_key: str | None = None  # Path to service account JSON file

    # Microsoft Planetary Computer
    pc_subscription_key: str | None = None

    # Sentinel Hub / Copernicus Data Space
    sentinelhub_client_id: str | None = None
    sentinelhub_client_secret: str | None = None

    # Processing
    max_region_area_km2: float = 50000.0  # Max region size in km²
    default_cloud_cover_threshold: float = 20.0  # Max cloud cover percentage
    tile_size: int = 256

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_period: int = 60  # seconds

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
            # Allow JSON list or comma-separated string
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
