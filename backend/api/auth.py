"""
Local development authentication foundation for MachiningPro AI public preview.

This is NOT production authentication.
It uses environment variables for credentials and simple token generation.
"""

import os
from datetime import UTC, datetime, timedelta

import jwt
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    display_name: str
    role: str
    expires_in: int


TOKEN_EXPIRE_MINUTES = 1440  # 24 hours for dev
JWT_SECRET_MIN_LENGTH = 32


def get_jwt_secret() -> str | None:
    """
    Load JWT signing secret from environment variable.

    Validates minimum length of 32 characters for security.

    Returns:
        JWT secret if configured and valid, None if not set or too short
        (auth fails closed)
    """
    secret = os.environ.get("MACHININGPRO_DEV_JWT_SECRET")
    if secret and len(secret) >= JWT_SECRET_MIN_LENGTH:
        return secret
    return None


def get_configured_credentials() -> dict | None:
    """
    Load local development credentials from environment variables.

    Returns:
        Dict with 'username', 'password', 'display_name', 'role' if configured
        None if environment variables are not set (auth fails closed)
    """
    username = os.environ.get("MACHININGPRO_DEV_USERNAME")
    password = os.environ.get("MACHININGPRO_DEV_PASSWORD")
    jwt_secret = get_jwt_secret()

    if not username or not password or not jwt_secret:
        # Any required auth configuration absent; fail closed
        return None

    return {
        "username": username,
        "password": password,
        "display_name": "MachiningPro AI Developer",
        "role": "engineer"  # Default role for local dev
    }


def authenticate(req: LoginRequest) -> LoginResponse | None:
    """
    Authenticate against configured local development credentials.

    Args:
        req: Login request with username/password

    Returns:
        LoginResponse with token if credentials match, None otherwise
    """
    creds = get_configured_credentials()

    if not creds:
        # No credentials configured; fail closed
        return None

    if req.username != creds["username"] or req.password != creds["password"]:
        # Credentials don't match
        return None

    # Credentials valid; generate token
    jwt_secret = get_jwt_secret()
    expires = datetime.now(UTC) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": req.username,
        "exp": expires,
        "role": creds["role"]
    }

    token = jwt.encode(payload, jwt_secret, algorithm="HS256")

    return LoginResponse(
        token=token,
        display_name=creds["display_name"],
        role=creds["role"],
        expires_in=TOKEN_EXPIRE_MINUTES * 60  # seconds
    )


def verify_token(token: str) -> dict | None:
    """
    Verify JWT token validity.

    Args:
        token: JWT token string

    Returns:
        Decoded payload if valid, None if expired or invalid
    """
    jwt_secret = get_jwt_secret()
    if not jwt_secret:
        # JWT secret not configured; can't verify
        return None

    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        return payload
    except jwt.InvalidTokenError:
        return None
