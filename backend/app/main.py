from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.core.config import get_settings
from app.core.database import close_db, init_db
from app.core.logging import get_logger, setup_logging
from app.core.redis import close_redis_client, get_redis_client

settings = get_settings()
logger = get_logger(__name__)

# Track connection states for health checks
_db_connected = False
_redis_connected = False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler with graceful failure handling."""
    global _db_connected, _redis_connected

    setup_logging()
    logger.info("Starting application", environment=settings.environment)

    # Initialize database - gracefully handle failures
    try:
        await init_db()
        _db_connected = True
        logger.info("Database initialized successfully")
    except Exception as e:
        _db_connected = False
        logger.warning(
            "Database connection failed - app will start but database features unavailable",
            error=str(e),
        )

    # Initialize Redis client - gracefully handle failures
    try:
        redis_client = get_redis_client()
        await redis_client.connect()
        _redis_connected = True
        logger.info("Redis connected successfully")
    except Exception as e:
        _redis_connected = False
        logger.warning(
            "Redis connection failed - app will start but caching/status features unavailable",
            error=str(e),
        )

    yield

    # Cleanup - close connections that were successfully opened
    if _db_connected:
        try:
            await close_db()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error("Error closing database connections", error=str(e))

    if _redis_connected:
        try:
            await close_redis_client()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error("Error closing Redis connection", error=str(e))

    logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.app_name,
    description="Satellite imagery migration and activity analysis platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware - configurable for different environments
cors_origins = [
    "http://localhost:5173",  # Vite dev server
    "http://localhost:3000",  # React dev server
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

# Add production origins in non-development environments
if settings.environment != "development":
    # Add your production domains here
    # cors_origins.append("https://your-domain.com")
    pass

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Total-Count"],
    max_age=600,  # Cache preflight requests for 10 minutes
)


# Exception handlers for common error types
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions with consistent format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "type": "http_error",
            "status_code": exc.status_code,
        },
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle request validation errors with detailed information."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })

    logger.warning(
        "Validation error",
        path=request.url.path,
        method=request.method,
        errors=errors,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Request validation failed",
            "type": "validation_error",
            "errors": errors,
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle ValueError exceptions."""
    logger.warning(
        "Value error",
        path=request.url.path,
        method=request.method,
        error=str(exc),
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": str(exc),
            "type": "value_error",
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled errors."""
    logger.error(
        "Unhandled exception",
        exc_info=exc,
        path=request.url.path,
        method=request.method,
        exception_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected error occurred. Our team has been notified.",
            "type": "internal_error",
        },
    )


# Include API routes
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint.

    Returns the health status of the application and its dependencies.
    Status is 'healthy' if all services are connected, 'degraded' if some
    services are unavailable, or 'unhealthy' if critical services are down.
    """
    # Determine overall health status
    if _db_connected and _redis_connected:
        overall_status = "healthy"
    elif _db_connected:
        overall_status = "degraded"  # DB works but Redis doesn't
    else:
        overall_status = "degraded"  # App runs but DB is down

    return {
        "status": overall_status,
        "version": "0.1.0",
        "environment": settings.environment,
        "services": {
            "database": "connected" if _db_connected else "disconnected",
            "redis": "connected" if _redis_connected else "disconnected",
        },
    }


@app.get("/health/live")
async def liveness_check() -> dict:
    """Kubernetes liveness probe - checks if app is running."""
    return {"status": "alive"}


@app.get("/health/ready", response_model=None)
async def readiness_check():
    """Kubernetes readiness probe - checks if app can handle traffic."""
    if not _db_connected:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "reason": "database_unavailable"},
        )
    return {"status": "ready"}


@app.get("/")
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
