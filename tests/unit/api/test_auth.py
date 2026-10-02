"""
Tests for authentication module.
"""

from datetime import UTC, datetime, timedelta

import jwt

from backend.api.auth import (
    LoginRequest,
    authenticate,
    get_configured_credentials,
    verify_token,
)


class TestConfiguredCredentials:
    """Tests for credential configuration"""

    def test_credentials_from_env(self, monkeypatch):
        """Should load credentials from environment"""
        monkeypatch.setenv("MACHININGPRO_DEV_USERNAME", "devuser")
        monkeypatch.setenv("MACHININGPRO_DEV_PASSWORD", "devpass")
        monkeypatch.setenv(
            "MACHININGPRO_DEV_JWT_SECRET",
            "test-secret-key-at-least-32-characters-long"
        )

        creds = get_configured_credentials()
        assert creds is not None
        assert creds["username"] == "devuser"
        assert creds["password"] == "devpass"
        assert creds["display_name"] == "MachiningPro AI Developer"
        assert creds["role"] == "engineer"

    def test_credentials_not_configured_returns_none(self, monkeypatch):
        """Should return None when credentials not set"""
        monkeypatch.delenv("MACHININGPRO_DEV_USERNAME", raising=False)
        monkeypatch.delenv("MACHININGPRO_DEV_PASSWORD", raising=False)
        monkeypatch.delenv("MACHININGPRO_DEV_JWT_SECRET", raising=False)

        creds = get_configured_credentials()
        assert creds is None

    def test_credentials_empty_strings_not_valid(self, monkeypatch):
        """Empty env vars should be treated as unconfigured"""
        monkeypatch.setenv("MACHININGPRO_DEV_USERNAME", "")
        monkeypatch.setenv("MACHININGPRO_DEV_PASSWORD", "")
        monkeypatch.setenv(
            "MACHININGPRO_DEV_JWT_SECRET",
            "test-secret-key-at-least-32-characters-long"
        )

        creds = get_configured_credentials()
        assert creds is None


class TestAuthentication:
    """Tests for authentication logic"""

    def test_authenticate_valid(self, monkeypatch):
        """Should authenticate with valid credentials"""
        monkeypatch.setenv("MACHININGPRO_DEV_USERNAME", "testuser")
        monkeypatch.setenv("MACHININGPRO_DEV_PASSWORD", "testpass")
        monkeypatch.setenv(
            "MACHININGPRO_DEV_JWT_SECRET",
            "test-secret-key-at-least-32-characters-long"
        )

        req = LoginRequest(username="testuser", password="testpass")
        response = authenticate(req)

        assert response is not None
        assert response.token
        assert response.display_name == "MachiningPro AI Developer"
        assert response.role == "engineer"
        assert response.expires_in > 0

    def test_authenticate_invalid_password(self, monkeypatch):
        """Should reject wrong password"""
        monkeypatch.setenv("MACHININGPRO_DEV_USERNAME", "testuser")
        monkeypatch.setenv("MACHININGPRO_DEV_PASSWORD", "testpass")
        monkeypatch.setenv(
            "MACHININGPRO_DEV_JWT_SECRET",
            "test-secret-key-at-least-32-characters-long"
        )

        req = LoginRequest(username="testuser", password="wrongpass")
        response = authenticate(req)

        assert response is None

    def test_authenticate_invalid_username(self, monkeypatch):
        """Should reject wrong username"""
        monkeypatch.setenv("MACHININGPRO_DEV_USERNAME", "testuser")
        monkeypatch.setenv("MACHININGPRO_DEV_PASSWORD", "testpass")
        monkeypatch.setenv(
            "MACHININGPRO_DEV_JWT_SECRET",
            "test-secret-key-at-least-32-characters-long"
        )

        req = LoginRequest(username="wronguser", password="testpass")
        response = authenticate(req)

        assert response is None

    def test_authenticate_unconfigured_returns_none(self, monkeypatch):
        """Should return None when credentials not configured"""
        monkeypatch.delenv("MACHININGPRO_DEV_USERNAME", raising=False)
        monkeypatch.delenv("MACHININGPRO_DEV_PASSWORD", raising=False)

        req = LoginRequest(username="anyuser", password="anypass")
        response = authenticate(req)

        assert response is None


class TestTokenVerification:
    """Tests for JWT token verification"""

    def test_verify_valid_token(self, monkeypatch):
        """Should verify valid token"""
        monkeypatch.setenv("MACHININGPRO_DEV_USERNAME", "testuser")
        monkeypatch.setenv("MACHININGPRO_DEV_PASSWORD", "testpass")
        monkeypatch.setenv(
            "MACHININGPRO_DEV_JWT_SECRET",
            "test-secret-key-at-least-32-characters-long"
        )

        req = LoginRequest(username="testuser", password="testpass")
        auth_response = authenticate(req)
        token = auth_response.token

        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "testuser"
        assert payload["role"] == "engineer"

    def test_verify_invalid_token(self, monkeypatch):
        """Should reject invalid token"""
        monkeypatch.setenv(
            "MACHININGPRO_DEV_JWT_SECRET",
            "test-secret-key-at-least-32-characters-long"
        )
        payload = verify_token("invalid.token.here")
        assert payload is None

    def test_verify_malformed_token(self, monkeypatch):
        """Should reject malformed token"""
        monkeypatch.setenv(
            "MACHININGPRO_DEV_JWT_SECRET",
            "test-secret-key-at-least-32-characters-long"
        )
        payload = verify_token("not-a-jwt")
        assert payload is None

    def test_verify_expired_token(self, monkeypatch):
        """Should reject expired token"""
        secret = "test-secret-key-at-least-32-characters-long"
        monkeypatch.setenv("MACHININGPRO_DEV_JWT_SECRET", secret)

        # Construct an already-expired token
        expired_time = datetime.now(UTC) - timedelta(hours=1)
        payload = {
            "sub": "testuser",
            "exp": expired_time,
            "role": "engineer"
        }
        expired_token = jwt.encode(payload, secret, algorithm="HS256")

        # Verify it is rejected
        result = verify_token(expired_token)
        assert result is None


class TestJWTSecretConfiguration:
    """Tests for JWT secret validation"""

    def test_missing_jwt_secret_fails_closed(self, monkeypatch):
        """Missing JWT secret should fail authentication"""
        monkeypatch.setenv("MACHININGPRO_DEV_USERNAME", "testuser")
        monkeypatch.setenv("MACHININGPRO_DEV_PASSWORD", "testpass")
        monkeypatch.delenv("MACHININGPRO_DEV_JWT_SECRET", raising=False)

        creds = get_configured_credentials()
        assert creds is None

    def test_empty_jwt_secret_fails_closed(self, monkeypatch):
        """Empty JWT secret should fail authentication"""
        monkeypatch.setenv("MACHININGPRO_DEV_USERNAME", "testuser")
        monkeypatch.setenv("MACHININGPRO_DEV_PASSWORD", "testpass")
        monkeypatch.setenv("MACHININGPRO_DEV_JWT_SECRET", "")

        creds = get_configured_credentials()
        assert creds is None

    def test_short_jwt_secret_fails_closed(self, monkeypatch):
        """JWT secret less than 32 chars should fail"""
        monkeypatch.setenv("MACHININGPRO_DEV_USERNAME", "testuser")
        monkeypatch.setenv("MACHININGPRO_DEV_PASSWORD", "testpass")
        monkeypatch.setenv("MACHININGPRO_DEV_JWT_SECRET", "short")

        creds = get_configured_credentials()
        assert creds is None

    def test_valid_jwt_secret_accepted(self, monkeypatch):
        """JWT secret of 32+ chars should be accepted"""
        monkeypatch.setenv("MACHININGPRO_DEV_USERNAME", "testuser")
        monkeypatch.setenv("MACHININGPRO_DEV_PASSWORD", "testpass")
        monkeypatch.setenv(
            "MACHININGPRO_DEV_JWT_SECRET",
            "this-is-a-safe-test-secret-32-chars"
        )

        creds = get_configured_credentials()
        assert creds is not None
