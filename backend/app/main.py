"""FastAPI application entrypoint for LegalLens AI."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import get_settings

logger = logging.getLogger("legallens")
settings = get_settings()

log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
# Never log Gemini keys or document contents.
logging.getLogger("google.genai").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.database import init_db
    from app.db.database import SessionLocal
    from app.db.repository import ensure_demo_documents

    init_db()
    if settings.enable_demo:
        with SessionLocal() as db:
            try:
                count = ensure_demo_documents(db)
                if count:
                    logger.info("Seeded %d demo documents", count)
            except Exception:
                logger.exception("Failed to seed demo documents")
    yield
    # Uploads are cleaned up after each analysis; nothing persistent to tear down.


def create_app() -> FastAPI:
    app = FastAPI(
        title="LegalLens AI",
        description="Understand before you sign. AI-powered legal document intelligence with evidence-backed, grounded analysis.",
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        # Never fall back to a wildcard: if no frontend origin is configured,
        # allow only the bundled local dev servers (credentials are off).
        allow_origins=settings.cors_origins
        or ["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    app.include_router(router, prefix="/api")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Defensive: never leak stack traces or internals.
        logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc.__class__.__name__)
        return JSONResponse(
            status_code=500,
            content={"detail": "Something went wrong on our side. Please try again.", "code": "internal"},
        )

    return app


app = create_app()