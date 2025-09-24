from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .logging_config import configure_logging, get_logger
from .routes import api_router

logger = get_logger(__name__)


# Register global exception handlers for consistent error responses across the API
def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.debug("validation error", extra={"errors": exc.errors(), "path": str(request.url)})
        return JSONResponse(
            {"ok": False, "error": "Invalid request", "detail": exc.errors()},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(request: Request, exc: HTTPException):
        logger.debug(
            "http error",
            extra={"detail": exc.detail, "status": exc.status_code, "path": str(request.url)},
        )
        detail = exc.detail
        if not isinstance(detail, str):
            detail = json.dumps(detail)
        return JSONResponse({"ok": False, "error": detail}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error", extra={"path": str(request.url)})
        return JSONResponse(
            {"ok": False, "error": "Internal server error"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


configure_logging()
_settings = get_settings()

app = FastAPI(
    title=_settings.app_name,
    version=_settings.app_version,
    docs_url=_settings.resolved_docs_url,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(api_router)


@app.on_event("startup")
# Initialize background services when the app starts
async def _start_services() -> None:
    print("🚀 Personal Assistant starting up...", flush=True)

    try:
        from .services.background_services import get_background_manager
        from .services.supabase_client import init_database_tables

        print("📊 Initializing database tables...", flush=True)
        # Initialize database tables
        await init_database_tables()

        print("⚙️  Starting background services...", flush=True)
        # Start background services
        background_manager = get_background_manager()
        await background_manager.start_services()

        print("✅ Personal Assistant startup completed successfully", flush=True)

    except Exception as e:
        print(f"❌ Error during startup: {e}", flush=True)
        import traceback
        traceback.print_exc()


@app.on_event("shutdown")
# Gracefully shutdown background services when the app stops
async def _stop_services() -> None:
    logger.info("Personal Assistant shutting down...")

    try:
        from .services.background_services import get_background_manager

        # Stop background services
        background_manager = get_background_manager()
        await background_manager.stop_services()

        logger.info("Personal Assistant shutdown completed")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


__all__ = ["app"]