from __future__ import annotations

from fastapi import APIRouter

from app.gee import initialize_ee
from app.schemas import GEEStatusResponse
from app.settings import get_settings


router = APIRouter()


@router.get("/gee", response_model=GEEStatusResponse)
async def gee_status() -> GEEStatusResponse:
    settings = get_settings()

    key_path = settings.gee_key_path
    service_account_key_exists = key_path.exists()
    project_id_configured = bool(settings.gee_project_id)
    service_account_key_configured = service_account_key_exists
    auth_mode = "service_account" if service_account_key_exists else "user"

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
