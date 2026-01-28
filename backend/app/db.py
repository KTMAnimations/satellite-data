from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.settings import get_settings


settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug and settings.environment == "development",
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

_db_init_lock = asyncio.Lock()
_db_initialized = False

_seed_lock = asyncio.Lock()
_seeded_predefined_regions = False


async def ensure_db_initialized() -> None:
    """
    Ensure tables exist even when lifespan/startup hooks aren't executed.

    This makes the API more robust in contexts like:
    - running the app with `--lifespan off`
    - tests that instantiate `TestClient(app)` without a context manager
    """

    global _db_initialized
    if _db_initialized:
        return

    async with _db_init_lock:
        if _db_initialized:
            return
        await init_db()
        _db_initialized = True


async def ensure_predefined_regions_seeded(session: AsyncSession) -> None:
    """
    Seed curated predefined regions once (idempotent).

    Uses `backend/data/predefined_regions.json` and inserts any missing regions.
    """

    if not getattr(settings, "auto_seed_predefined_regions", True):
        return

    global _seeded_predefined_regions
    if _seeded_predefined_regions:
        return

    async with _seed_lock:
        if _seeded_predefined_regions:
            return

        try:
            from app.predefined_regions import seed_predefined_regions

            await seed_predefined_regions(session)
        finally:
            # Mark as done regardless; seeding is best-effort and the API should
            # still work if the seed file is missing or invalid.
            _seeded_predefined_regions = True


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    await ensure_db_initialized()
    async with async_session_factory() as session:
        try:
            await ensure_predefined_regions_seeded(session)
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    from app.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await engine.dispose()
