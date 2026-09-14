"""UI-VISUAL-1A — Premium visual system tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from frontend.app import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def css(client: TestClient) -> str:
    return client.get("/static/design-system.css").text


@pytest.fixture()
def landing(client: TestClient) -> str:
    return client.get("/").text


@pytest.fixture()
def dashboard(client: TestClient) -> str:
    return client.get("/ui/").text


class TestPremiumDesignTokens:
    def test_steel_palette(self, css: str) -> None:
        assert "--mp-steel-900" in css
        assert "--mp-steel-700" in css

    def test_shadow_elevated(self, css: str) -> None:
        assert "--mp-shadow-elevated" in css

    def test_shadow_hover(self, css: str) -> None:
        assert "--mp-shadow-hover" in css

    def test_btn_gradient(self, css: str) -> None:
        assert "linear-gradient" in css

    def test_pulse_animation(self, css: str) -> None:
        assert "mp-pulse" in css

    def test_reduced_motion(self, css: str) -> None:
        assert "prefers-reduced-motion" in css


class TestLandingPremium:
    def test_dark_hero(self, landing: str) -> None:
        assert "mp-hero-dark" in landing

    def test_hero_grid_overlay(self, landing: str) -> None:
        assert "mp-hero-dark__grid" in landing

    def test_hero_scanline(self, landing: str) -> None:
        assert "mp-hero-dark__scanline" in landing

    def test_hero_accent_text(self, landing: str) -> None:
        assert "deterministic-first" in landing

    def test_large_cta(self, landing: str) -> None:
        assert "mp-btn--lg" in landing

    def test_hero_visual_container(self, landing: str) -> None:
        assert "mp-hero-visual" in landing


class TestWorkspacePremium:
    def test_ws_workstation_layout(self, dashboard: str) -> None:
        assert "mp-workstation" in dashboard

    def test_ws_context_bar(self, dashboard: str) -> None:
        assert "mp-context-bar" in dashboard

    def test_ws_command_strip(self, dashboard: str) -> None:
        assert "mp-command-strip" in dashboard

    def test_ws_operation_ribbon(self, dashboard: str) -> None:
        assert "mp-operation-ribbon" in dashboard

    def test_ws_engineering_viewport(self, dashboard: str) -> None:
        assert "mp-engineering-viewport" in dashboard
        assert "<svg" in dashboard

    def test_ws_properties_panel(self, dashboard: str) -> None:
        assert "mp-right-panel" in dashboard
        assert "mp-tab" in dashboard
        assert "data-tab-panel=\"properties\"" in dashboard

    def test_ws_process_timeline(self, dashboard: str) -> None:
        assert "mp-process-timeline" in dashboard

    def test_ws_model_tree(self, dashboard: str) -> None:
        assert "mp-model-tree" in dashboard
        assert "data-tree-row" in dashboard

    def test_ws_ai_assistant(self, dashboard: str) -> None:
        assert "mp-ai-panel" in dashboard
        assert "mp-ai-rec" in dashboard
        assert "data-tab-panel=\"ai-assistant\"" in dashboard

    def test_context_bar_fields(self, dashboard: str) -> None:
        assert "PART" in dashboard
        assert "MATERIAL" in dashboard
        assert "MACHINE" in dashboard

    def test_operation_ribbon_items(self, dashboard: str) -> None:
        assert "Milling" in dashboard
        assert "Turning" in dashboard
        assert "Drilling" in dashboard

    def test_status_pulse(self, css: str) -> None:
        assert "mp-pulse" in css

    def test_accent_border(self, dashboard: str) -> None:
        assert "mp-accent-top" in dashboard or "mp-cap-card" in dashboard


class TestCSSComponents:
    def test_hero_dark_class(self, css: str) -> None:
        assert ".mp-hero-dark" in css

    def test_ws_hero_class(self, css: str) -> None:
        assert ".mp-ws-hero" in css

    def test_action_card_class(self, css: str) -> None:
        assert ".mp-action-card" in css

    def test_module_card_class(self, css: str) -> None:
        assert ".mp-module-card" in css

    def test_btn_lg(self, css: str) -> None:
        assert ".mp-btn--lg" in css

    def test_card_hover_shadow(self, css: str) -> None:
        assert "mp-shadow-elevated" in css


class TestNoRegression:
    def test_root(self, client: TestClient) -> None:
        assert client.get("/").status_code == 200

    def test_workspace(self, client: TestClient) -> None:
        assert client.get("/ui/").status_code == 200

    def test_cad_import(self, client: TestClient) -> None:
        assert client.get("/ui/cad-import").status_code == 200

    def test_health(self, client: TestClient) -> None:
        assert client.get("/health").json()["status"] == "ok"

    def test_app_title(self) -> None:
        assert app.title == "MachineryPro AI"
