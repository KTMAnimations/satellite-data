from fastapi import APIRouter

from app.api.routes import regions, analysis, metrics, exports, auth, tiles

api_router = APIRouter()

api_router.include_router(regions.router, prefix="/regions", tags=["regions"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
api_router.include_router(exports.router, prefix="/exports", tags=["exports"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(tiles.router, prefix="/tiles", tags=["tiles"])
