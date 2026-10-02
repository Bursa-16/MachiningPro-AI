"""
Tests for MachiningPro AI FastAPI HTTP foundation.
"""

from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)


class TestHealth:
    """Tests for GET /api/health"""

    def test_health_success(self):
        """Health endpoint should return 200 with required fields"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0-alpha.10"
        assert "database_ok" in data
        assert "server_time" in data
        # Truthful: no database in public arch
        assert data["database_ok"] is False

    def test_health_server_time_format(self):
        """Server time should be ISO format"""
        response = client.get("/api/health")
        data = response.json()
        # Should be valid ISO timestamp
        assert "T" in data["server_time"]
        assert "Z" in data["server_time"]


class TestLogin:
    """Tests for POST /api/login"""

    def test_login_success_with_env_credentials(self, monkeypatch):
        """Login succeeds when environment credentials match"""
        monkeypatch.setenv("MACHININGPRO_DEV_USERNAME", "testuser")
        monkeypatch.setenv("MACHININGPRO_DEV_PASSWORD", "testpass")
        secret = "test-secret-key-at-least-32-characters-long"
        monkeypatch.setenv("MACHININGPRO_DEV_JWT_SECRET", secret)

        response = client.post(
            "/api/login",
            json={"username": "testuser", "password": "testpass"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["display_name"] == "MachiningPro AI Developer"
        assert data["role"] == "engineer"
        assert data["expires_in"] > 0

    def test_login_invalid_credentials(self, monkeypatch):
        """Login fails with wrong credentials"""
        monkeypatch.setenv("MACHININGPRO_DEV_USERNAME", "testuser")
        monkeypatch.setenv("MACHININGPRO_DEV_PASSWORD", "testpass")
        secret = "test-secret-key-at-least-32-characters-long"
        monkeypatch.setenv("MACHININGPRO_DEV_JWT_SECRET", secret)

        response = client.post(
            "/api/login",
            json={"username": "testuser", "password": "wrongpass"}
        )

        assert response.status_code == 401

    def test_login_unconfigured_credentials_fail_closed(self, monkeypatch):
        """Login fails closed when credentials not configured"""
        monkeypatch.delenv("MACHININGPRO_DEV_USERNAME", raising=False)
        monkeypatch.delenv("MACHININGPRO_DEV_PASSWORD", raising=False)
        monkeypatch.delenv("MACHININGPRO_DEV_JWT_SECRET", raising=False)

        response = client.post(
            "/api/login",
            json={"username": "anyuser", "password": "anypass"}
        )

        assert response.status_code == 401
        data = response.json()
        assert "not configured" in data.get("detail", "").lower()

    def test_login_response_no_password_exposed(self, monkeypatch):
        """Login response never includes password"""
        monkeypatch.setenv("MACHININGPRO_DEV_USERNAME", "testuser")
        monkeypatch.setenv("MACHININGPRO_DEV_PASSWORD", "secretpass123")
        secret = "test-secret-key-at-least-32-characters-long"
        monkeypatch.setenv("MACHININGPRO_DEV_JWT_SECRET", secret)

        response = client.post(
            "/api/login",
            json={"username": "testuser", "password": "secretpass123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "password" not in data
        assert "secretpass123" not in str(data)


class TestPortConfiguration:
    """Verify backend is independent of TorqPro port"""

    def test_no_torqpro_references(self):
        """Backend code should not reference TorqPro or port 8000"""
        # Check app.py imports and references
        with open("backend/api/app.py") as f:
            app_content = f.read()
            assert "TorqPro" not in app_content
            assert "8000" not in app_content
            assert "localhost:8000" not in app_content

    def test_no_cross_project_terminology(self):
        """Backend should not use cross-project terminology"""
        with open("backend/api/app.py") as f:
            content = f.read()
            for term in ["TorqPro", "SpotWeldPro", "Origlyph", "VP100"]:
                assert term not in content, f"Found cross-project term: {term}"


class TestAuthToken:
    """Test JWT token generation and validation"""

    def test_token_is_jwt_format(self, monkeypatch):
        """Generated token should be valid JWT"""
        monkeypatch.setenv("MACHININGPRO_DEV_USERNAME", "testuser")
        monkeypatch.setenv("MACHININGPRO_DEV_PASSWORD", "testpass")
        secret = "test-secret-key-at-least-32-characters-long"
        monkeypatch.setenv("MACHININGPRO_DEV_JWT_SECRET", secret)

        response = client.post(
            "/api/login",
            json={"username": "testuser", "password": "testpass"}
        )

        data = response.json()
        token = data["token"]
        # JWT format: three parts separated by dots
        assert token.count(".") == 2
