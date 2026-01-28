from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from app.gee import initialize_ee
from app.schemas import GEEStatusResponse
from app.settings import get_settings


router = APIRouter()


@router.get("/gee", response_model=GEEStatusResponse)
async def gee_status() -> GEEStatusResponse:
    settings = get_settings()

    project_id_configured = bool(settings.gee_project_id)
    service_account_key_configured = bool(settings.gee_service_account_key)
    service_account_key_exists = (
        Path(settings.gee_service_account_key).expanduser().exists() if settings.gee_service_account_key else False
    )
    auth_mode = "service_account" if (settings.gee_project_id and settings.gee_service_account_key) else "user"

    try:
        initialize_ee()
        initialized = True
        error = None
    except Exception as e:
        initialized = False
        error = str(e)

    return GEEStatusResponse(
        auth_mode=auth_mode,
        project_id_configured=project_id_configured,
        service_account_key_configured=service_account_key_configured,
        service_account_key_exists=service_account_key_exists,
        initialized=initialized,
        error=error,
    )
