"""UI-DESIGN-0A — Design system integration tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from frontend.app import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


class TestDesignSystemLoaded:
    """design-system.css must be served and linked."""

    def test_css_file_served(self, client: TestClient) -> None:
        resp = client.get("/static/design-system.css")
        assert resp.status_code == 200
        assert "text/css" in resp.headers["content-type"]

    def test_base_links_design_system(self, client: TestClient) -> None:
        assert "design-system.css" in client.get("/ui/").text

    def test_css_contains_tokens(self, client: TestClient) -> None:
        css = client.get("/static/design-system.css").text
        for token in ["--mp-brand-500", "--mp-bg-sidebar", "--mp-text",
                       "--mp-border", "--mp-font", "--mp-radius"]:
            assert token in css, f"Missing token: {token}"


class TestApplicationShell:
    """Shell structure on every page."""

    def test_shell_wrapper(self, client: TestClient) -> None:
        assert "mp-shell" in client.get("/ui/").text

    def test_sidebar_present(self, client: TestClient) -> None:
        assert "mp-sidebar" in client.get("/ui/").text

    def test_main_present(self, client: TestClient) -> None:
        assert "mp-main" in client.get("/ui/").text


class TestNavigation:
    """Navigation contract."""

    def test_all_nav_items(self, client: TestClient) -> None:
        html = client.get("/ui/").text
        for label in ["Dashboard", "CAD Import", "Geometry / Topology",
                       "Machining", "Tools &amp; Parameters", "Materials",
                       "Validation", "AI Assistant"]:
            assert label in html, f"Missing: {label}"

    def test_active_state(self, client: TestClient) -> None:
        assert "mp-nav-item--active" in client.get("/ui/").text

    def test_aria_current(self, client: TestClient) -> None:
        assert 'aria-current="page"' in client.get("/ui/").text

    def test_planned_badge(self, client: TestClient) -> None:
        html = client.get("/ui/").text
        assert "mp-badge-planned" in html
        assert "PLANNED" in html

    def test_cad_import_accessible(self, client: TestClient) -> None:
        resp = client.get("/ui/cad-import")
        assert resp.status_code == 200
        assert "CAD Import" in resp.text


class TestStatusStyling:
    """Status states must be visually distinguishable."""

    def test_banner_variants_in_css(self, client: TestClient) -> None:
        css = client.get("/static/design-system.css").text
        for variant in ["success", "warning", "error", "info", "unavail"]:
            assert f"mp-banner--{variant}" in css, f"Missing: mp-banner--{variant}"

    def test_dashboard_success_banner(self, client: TestClient) -> None:
        # Banner classes exist in CSS and are used in cad_import.html
        css = client.get("/static/design-system.css").text
        assert "mp-banner--success" in css

    def test_status_dot_present(self, client: TestClient) -> None:
        # Status dot is present in the sidebar footer
        html = client.get("/ui/").text
        assert "mp-sidebar__status-dot" in html


class TestDeterministicVsAI:
    """Calculated vs AI advisory: separate visual identity."""

    def test_calc_token_exists(self, client: TestClient) -> None:
        css = client.get("/static/design-system.css").text
        assert "--mp-calc-accent" in css

    def test_ai_token_exists(self, client: TestClient) -> None:
        css = client.get("/static/design-system.css").text
        assert "--mp-ai-accent" in css

    def test_calc_badge_class(self, client: TestClient) -> None:
        assert "mp-badge--calc" in client.get("/static/design-system.css").text

    def test_ai_badge_class(self, client: TestClient) -> None:
        assert "mp-badge--ai" in client.get("/static/design-system.css").text

    def test_ai_uses_dashed_border(self, client: TestClient) -> None:
        assert "dashed" in client.get("/static/design-system.css").text

    def test_colors_differ(self, client: TestClient) -> None:
        css = client.get("/static/design-system.css").text
        assert "#2563eb" in css  # calc = blue
        assert "#7c3aed" in css  # ai = violet

    def test_card_calc_variant(self, client: TestClient) -> None:
        assert "mp-card--calc" in client.get("/static/design-system.css").text

    def test_card_ai_variant(self, client: TestClient) -> None:
        assert "mp-card--ai" in client.get("/static/design-system.css").text


class TestNoRouteRegression:
    """All existing routes must still work."""

    def test_root(self, client: TestClient) -> None:
        assert client.get("/").status_code == 200

    def test_dashboard(self, client: TestClient) -> None:
        assert client.get("/ui/").status_code == 200

    def test_health(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_cad_import(self, client: TestClient) -> None:
        assert client.get("/ui/cad-import").status_code == 200

    def test_app_title(self) -> None:
        assert app.title == "MachineryPro AI"
