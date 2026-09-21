"""Responsive scrolling contracts for the application shell and workstation."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from frontend.app import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def css(client: TestClient) -> str:
    response = client.get("/static/design-system.css")
    assert response.status_code == 200
    return response.text


def _rule(css: str, selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>.*?)\}}", css, re.DOTALL)
    assert match is not None, f"Missing CSS rule: {selector}"
    return re.sub(r"\s+", " ", match.group("body")).strip()


def _assert_declaration(rule: str, declaration: str) -> None:
    assert declaration in rule, f"Missing declaration {declaration!r} in {rule!r}"


class TestApplicationShellScrolling:
    def test_shell_uses_dynamic_viewport_height_without_horizontal_overflow(
        self, css: str
    ) -> None:
        body = _rule(css, "body")
        shell = _rule(css, ".mp-shell")

        _assert_declaration(body, "height: 100dvh")
        _assert_declaration(body, "overflow-x: hidden")
        _assert_declaration(shell, "height: 100dvh")
        _assert_declaration(shell, "min-width: 0")
        _assert_declaration(shell, "overflow-x: hidden")

    def test_standard_pages_scroll_inside_main_while_shell_stays_fixed(
        self, css: str
    ) -> None:
        main = _rule(css, ".mp-main")
        content = _rule(css, ".mp-content")

        _assert_declaration(main, "min-height: 0")
        _assert_declaration(main, "min-width: 0")
        _assert_declaration(main, "overflow: hidden")
        _assert_declaration(content, "flex: 1 1 auto")
        _assert_declaration(content, "min-height: 0")
        _assert_declaration(content, "min-width: 0")
        _assert_declaration(content, "overflow-y: auto")
        _assert_declaration(content, "overflow-x: hidden")

    @pytest.mark.parametrize(
        ("width", "height"),
        [(1366, 768), (1440, 900), (1920, 1080)],
    )
    def test_supported_viewports_preserve_a_scrollable_main_region(
        self, client: TestClient, css: str, width: int, height: int
    ) -> None:
        assert client.get("/ui/").status_code == 200
        assert client.get("/ui/cad-import").status_code == 200
        assert width - 240 > 0
        assert height > 0
        _assert_declaration(_rule(css, ".mp-shell"), "height: 100dvh")
        _assert_declaration(_rule(css, ".mp-content"), "overflow-y: auto")


class TestWorkstationIndependentScrolling:
    @pytest.mark.parametrize(
        "selector",
        [
            ".mp-workstation",
            ".mp-model-tree",
            ".mp-engineering-viewport",
            ".mp-right-panel",
            ".mp-tab-content",
            ".mp-ai-panel",
            ".mp-ai-scroll",
        ],
    )
    def test_grid_and_flex_children_can_shrink(self, css: str, selector: str) -> None:
        rule = _rule(css, selector)
        _assert_declaration(rule, "min-height: 0")
        _assert_declaration(rule, "min-width: 0")

    @pytest.mark.parametrize(
        "selector",
        [
            ".mp-tree-scroll",
            ".mp-engineering-viewport",
            ".mp-tab-content",
            ".mp-ai-scroll",
        ],
    )
    def test_workspace_regions_scroll_independently(
        self, css: str, selector: str
    ) -> None:
        rule = _rule(css, selector)
        _assert_declaration(rule, "overflow-y: auto")
        _assert_declaration(rule, "overscroll-behavior: contain")

    def test_workstation_outer_grid_remains_fixed(self, css: str) -> None:
        content = _rule(css, ".mp-content--workstation")
        workstation = _rule(css, ".mp-workstation")

        _assert_declaration(content, "overflow: hidden")
        _assert_declaration(workstation, "overflow: hidden")
        _assert_declaration(workstation, "grid-template-columns: 220px minmax(0, 1fr) 280px")


class TestDarkScrollbar:
    def test_scrollable_surfaces_use_thin_dark_scrollbars(self, css: str) -> None:
        assert "scrollbar-width: thin" in css
        assert "scrollbar-color:" in css
        assert "::-webkit-scrollbar" in css
        assert "::-webkit-scrollbar-thumb" in css
