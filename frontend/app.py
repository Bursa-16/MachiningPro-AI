"""MachineryPro AI — FastAPI application factory (UI-0A).

Creates the ASGI application that serves both the JSON health endpoint
and the Jinja2-rendered engineering UI.

Usage::

    uvicorn frontend.app:app --reload
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from frontend.routers import health, public, ui

_HERE = Path(__file__).resolve().parent
_TEMPLATES_DIR = _HERE / "templates"
_STATIC_DIR = _HERE / "static"


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    application = FastAPI(
        title="MachineryPro AI",
        description="Engineering Intelligence for Manufacturing",
        version="0.1.0",
    )

    # --- shared template engine (attached to app state) ---
    application.state.templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    # --- static files ---
    application.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # --- routers ---
    application.include_router(health.router)
    application.include_router(ui.router)
    application.include_router(public.router)

    return application


app: FastAPI = create_app()
