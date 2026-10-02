"""
MachiningPro AI FastAPI HTTP Application

Minimal standalone HTTP foundation supporting:
- GET /api/health - System health and version info
- POST /api/login - Local development authentication
"""

from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .auth import LoginRequest, authenticate, get_configured_credentials


class ChangePasswordRequest(BaseModel):
    """Frontend change-password contract"""
    current_password: str
    new_password: str

# Create FastAPI application
app = FastAPI(title="MachiningPro AI", version="0.1.0-alpha.10")


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.api.app:app",
        host="127.0.0.1",
        port=8010,
        reload=True
    )
