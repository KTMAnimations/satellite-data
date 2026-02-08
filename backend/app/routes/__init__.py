from fastapi import APIRouter

from app.routes.admin import router as admin_router
from app.routes.analysis import router as analysis_router
from app.routes.exports import router as exports_router
from app.routes.metrics import router as metrics_router
from app.routes.presets import router as presets_router
from app.routes.regions import router as regions_router
from app.routes.status import router as status_router
from app.routes.telemetry import router as telemetry_router
from app.routes.tiles import router as tiles_router


api_router = APIRouter()

api_router.include_router(regions_router, prefix="/regions", tags=["regions"])
api_router.include_router(metrics_router, prefix="/metrics", tags=["metrics"])
api_router.include_router(tiles_router, prefix="/tiles", tags=["tiles"])
api_router.include_router(analysis_router, prefix="/analysis", tags=["analysis"])
api_router.include_router(exports_router, prefix="/exports", tags=["exports"])
api_router.include_router(presets_router, prefix="/presets", tags=["presets"])
api_router.include_router(status_router, prefix="/status", tags=["status"])
api_router.include_router(telemetry_router, prefix="/telemetry", tags=["telemetry"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
