"""UI-0A — FastAPI application shell tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from frontend.app import app, create_app

# ------------------------------------------------------------------
# App factory
# ------------------------------------------------------------------

class TestCreateApp:
    """Verify create_app() produces a well-configured FastAPI instance."""

    def test_returns_fastapi(self) -> None:
        result = create_app()
        assert result.__class__.__name__ == "FastAPI"

    def test_title(self) -> None:
        assert app.title == "MachineryPro AI"

    def test_version(self) -> None:
        assert app.version == "0.1.0"

    def test_templates_attached(self) -> None:
        assert hasattr(app.state, "templates")


# ------------------------------------------------------------------
# Health endpoint
# ------------------------------------------------------------------

class TestHealthEndpoint:
    """GET /health must return JSON status."""

    @pytest.fixture()
    def client(self) -> TestClient:
        return TestClient(app)

    def test_status_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["application"] == "MachineryPro AI"

    def test_engineering_core_online(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.json()["engineering_core"] == "online"


# ------------------------------------------------------------------
# UI routes
# ------------------------------------------------------------------

class TestUIRoutes:
    """HTML page routes must return 200 with expected content."""

    @pytest.fixture()
    def client(self) -> TestClient:
        return TestClient(app)

    def test_root_returns_html(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_dashboard_returns_html(self, client: TestClient) -> None:
        resp = client.get("/ui/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_dashboard_contains_title(self, client: TestClient) -> None:
        resp = client.get("/ui/")
        assert "MachineryPro AI" in resp.text

    def test_dashboard_contains_status(self, client: TestClient) -> None:
        resp = client.get("/ui/")
        # Status is shown in the sidebar footer
        assert "Engineering Core Online" in resp.text

    def test_dashboard_contains_nav_items(self, client: TestClient) -> None:
        html = client.get("/ui/").text
        for label in [
            "Dashboard",
            "CAD Import",
            "Geometry / Topology",
            "Machining",
            "Tools &amp; Parameters",
            "Materials",
            "Validation",
            "AI Assistant",
        ]:
            assert label in html, f"Missing nav item: {label}"

    def test_dashboard_contains_capability_cards(self, client: TestClient) -> None:
        html = client.get("/ui/").text
        for card_title in [
            "CAD Interoperability",
            "Machining Engineering",
            "DFM Validation",
            "Process Planning",
        ]:
            assert card_title in html, f"Missing card: {card_title}"

    def test_planned_badges_visible(self, client: TestClient) -> None:
        html = client.get("/ui/").text
        assert "PLANNED" in html

    def test_sidebar_subtitle(self, client: TestClient) -> None:
        html = client.get("/ui/").text
        assert "Engineering Intelligence for Manufacturing" in html
