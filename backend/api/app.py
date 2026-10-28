"""
MachiningPro AI FastAPI HTTP Application

Minimal standalone HTTP foundation supporting:
- GET /api/health - System health and version info
- POST /api/login - Local development authentication
- /api/drawings/... - authenticated drawing upload, explicit AI analysis jobs and human review
"""

import os
import pathlib
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .auth import LoginRequest, authenticate, get_configured_credentials
from .compatibility import router as compatibility_router
from .cutting_parameters import router as cutting_parameters_router
from .cutting_tools import router as cutting_tools_router
from .drawing_analysis import router as drawing_analysis_router
from .drawing_parser import router as drawing_parser_router
from .drawing_to_process import router as drawing_to_process_router
from .engineering_import import router as engineering_import_router
from .gdt import router as gdt_router
from .cad_features import router as cad_features_router
from .process_routes import router as process_routes_router
from .machines import router as machines_router
from .materials import router as materials_router
from .nc_path import router as nc_path_router
from .process_planning import router as process_planning_router
from .selection import router as selection_router
from .tool_holders import router as tool_holders_router
from .tool_life import router as tool_life_router
from .calibration import router as calibration_router
from .manufacturing_plan import router as manufacturing_plan_router


class ChangePasswordRequest(BaseModel):
    """Frontend change-password contract"""
    current_password: str
    new_password: str

# Create FastAPI application
app = FastAPI(title="MachiningPro AI", version="0.1.0-alpha.10")

# Optional CORS — activated only when CORS_ORIGINS env var is set (split-deployment mode).
# Same-origin deployment (recommended): leave CORS_ORIGINS unset; middleware is not added.
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

app.include_router(compatibility_router)
app.include_router(cutting_parameters_router)
app.include_router(drawing_to_process_router)
app.include_router(materials_router)
app.include_router(cutting_tools_router)
app.include_router(drawing_analysis_router)
app.include_router(engineering_import_router)
app.include_router(machines_router)
app.include_router(nc_path_router)
app.include_router(process_planning_router)
app.include_router(selection_router)
app.include_router(tool_holders_router)
app.include_router(tool_life_router)
app.include_router(drawing_parser_router)
app.include_router(gdt_router)
app.include_router(cad_features_router)
app.include_router(process_routes_router)
app.include_router(calibration_router)
app.include_router(manufacturing_plan_router)


@app.get("/api/health")
async def health():
    """
    Return system health status compatible with frontend Dashboard.

    POLICY: Public (unauthenticated) health endpoint.
    Rationale: Public bootstrap health endpoint for local alpha diagnostics.
    It exposes only non-sensitive application status and does not provide
    authenticated administrative health data.

    No database is part of the current public architecture.
    database_ok is false because no database is configured in this public alpha.
    """
    utc_now = datetime.now(UTC)
    return {
        "status": "ok",
        "version": "0.1.0-alpha.10",
        "database_ok": False,  # Truthful: no database in public arch
        "server_time": utc_now.isoformat(timespec='milliseconds').replace(
            '+00:00', 'Z'
        )
    }


@app.post("/api/login")
async def login(req: LoginRequest):
    """
    Authenticate with local development credentials.

    Requires MACHININGPRO_DEV_USERNAME and MACHININGPRO_DEV_PASSWORD
    environment variables to be set.

    Returns:
        LoginResponse with JWT token if credentials match

    Raises:
        HTTPException 401 if credentials don't match or not configured
    """

    # Check if credentials are configured
    if not get_configured_credentials():
        raise HTTPException(
            status_code=401,
            detail=(
                "Local development credentials not configured. "
                "Set MACHININGPRO_DEV_USERNAME, MACHININGPRO_DEV_PASSWORD, "
                "and MACHININGPRO_DEV_JWT_SECRET environment variables."
            ),
        )

    # Authenticate
    response = authenticate(req)

    if not response:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    return response.model_dump()


@app.post("/api/change-password")
async def change_password(req: ChangePasswordRequest):
    """
    Change password endpoint.

    This is a public alpha preview. Password changes are not yet supported.
    Returns unsupported response matching the alpha release scope.
    """
    return {
        "ok": False,
        "error": "not supported in alpha"
    }


# Production SPA/static serving — active only when frontend/dist exists.
# Development API-only mode is unaffected when dist is absent.
_DIST = pathlib.Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if _DIST.is_dir():
    # Serve hashed asset bundles with StaticFiles (proper ETag/caching headers).
    if (_DIST / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="static-assets")
    if (_DIST / "branding").is_dir():
        app.mount(
            "/branding",
            StaticFiles(directory=str(_DIST / "branding")),
            name="static-branding",
        )

    # SPA catch-all — MUST be last route registered so API routes retain priority.
    # Serves specific root-level files (favicon.svg, icons.svg, …) if they exist,
    # otherwise returns index.html for all frontend routes (supports browser refresh).
    _DIST_RESOLVED = _DIST.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa_fallback(full_path: str) -> FileResponse:
        # Unmatched /api/ paths (e.g. URL-normalised traversal /api/drawings/../../x → /api/)
        # must return 404, not the SPA, so that API path-traversal tests remain meaningful.
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        # Path traversal guard: resolve and verify the target is inside dist.
        try:
            target = (_DIST / full_path).resolve()
            target.relative_to(_DIST_RESOLVED)
        except ValueError:
            return FileResponse(str(_DIST / "index.html"))
        if target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(_DIST / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.api.app:app",
        host="127.0.0.1",
        port=8010,
        reload=True
    )
