"""
app/main.py — FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.db import close_db, connect_db
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.complaints import router as complaints_router


# ---------------------------------------------------------------------------
# Lifespan: connect/disconnect MongoDB on startup/shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await connect_db()
    yield
    await close_db()


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Session middleware — must be added BEFORE CORSMiddleware
    # itsdangerous signs the cookie with SECRET_KEY; HttpOnly + SameSite=lax by default
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="session",
        max_age=settings.session_max_age_seconds,
        https_only=not settings.debug,   # Secure flag off in dev, on in prod
        same_site="lax",
    )

    # CORS — tighten allow_origins in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,   # Required for cookies to be sent cross-origin
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static files
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    # API routers
    PREFIX = "/api/v1"
    app.include_router(auth_router, prefix=PREFIX)
    app.include_router(users_router, prefix=PREFIX)
    app.include_router(complaints_router, prefix=PREFIX)

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        return {"status": "ok", "version": settings.app_version}

    return app


app = create_app()
