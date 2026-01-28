from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import close_db, ensure_db_initialized
from app.gee import initialize_ee
from app.routes import api_router
from app.settings import get_settings


logger = logging.getLogger("satellite")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Storage
    await ensure_db_initialized()

    # Earth Engine (optional at startup; errors surface on first request)
    try:
        initialize_ee()
        logger.info("Earth Engine initialized")
    except Exception as e:
        logger.warning("Earth Engine not initialized yet (%s). Run `earthengine authenticate` or configure service account.", e)

    yield

    await close_db()


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="Local-first satellite proxy metrics explorer (Earth Engine + SQLite).",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "0.2.0"}
