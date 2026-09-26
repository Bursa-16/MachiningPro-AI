"""UX-01A — MachiningPro AI grouped post-login navigation."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from frontend.app import app
from frontend.navigation import NAV_GROUPS, build_sidebar, iter_nav_items, legacy_nav_items
from frontend.routers.ui import NAV_ITEMS


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _registered_get_paths() -> set[str]:
    # Via the OpenAPI schema: works across FastAPI versions that nest routers.
    return {path for path, ops in app.openapi()["paths"].items() if "get" in ops}


class TestNavigationModel:
    def test_every_nav_item_maps_to_an_existing_route(self, client: TestClient) -> None:
        paths = _registered_get_paths()
        for item in iter_nav_items():
            assert item.href in paths, f"Sidebar points to unknown route {item.href}"
            assert client.get(item.href).status_code == 200

    def test_no_existing_ui_route_is_dropped_from_the_sidebar(self) -> None:
        hrefs = {item.href for item in iter_nav_items()}
        ui_pages = {p for p in _registered_get_paths() if p.startswith("/ui/")}
        assert ui_pages <= hrefs, f"Routes missing from sidebar: {ui_pages - hrefs}"

    def test_item_ids_and_hrefs_are_unique(self) -> None:
        items = iter_nav_items()
        assert len({i.id for i in items}) == len(items)
        assert len({i.href for i in items}) == len(items)

    def test_legacy_nav_items_shape_preserved(self) -> None:
        assert NAV_ITEMS == legacy_nav_items()
        assert NAV_ITEMS[0] == {"label": "Dashboard", "href": "/ui/", "icon": "home", "badge": ""}
        assert {"label", "href", "icon", "badge"} == set(NAV_ITEMS[1])

    def test_only_active_group_opens_by_default(self) -> None:
        views = {g.id: g for g in build_sidebar("/ui/tools")}
        assert views["manufacturing"].is_open and views["manufacturing"].is_active
        assert not views["engineering-data"].is_open
        assert not views["assurance"].is_open
        assert not views["intelligence"].is_open
        # Non-collapsible Dashboard section is always visible.
        assert views["workspace"].is_open

    def test_exactly_one_active_item(self) -> None:
        views = build_sidebar("/ui/cad-import")
        active = [i for g in views for i in g.items if i.is_active]
        assert [i.href for i in active] == ["/ui/cad-import"]

    def test_planned_status_is_factual(self) -> None:
        available = {i.href for i in iter_nav_items() if i.status == "available"}
        assert available == {"/ui/", "/ui/cad-import"}

    def test_groups_are_few_and_small(self) -> None:
        assert len(NAV_GROUPS) <= 7
        assert all(len(g.items) <= 6 for g in NAV_GROUPS)


class TestRenderedSidebar:
    def test_dashboard_is_static_not_collapsible(self, client: TestClient) -> None:
        html = client.get("/ui/").text
        assert 'class="mp-nav-section" data-nav-group="workspace"' in html
        assert '<details class="mp-nav-group" data-nav-group="workspace"' not in html

    @pytest.mark.parametrize(
        ("href", "group_id"),
        [
            ("/ui/cad-import", "engineering-data"),
            ("/ui/machining", "manufacturing"),
            ("/ui/validation", "assurance"),
            ("/ui/ai-assistant", "intelligence"),
        ],
    )
    def test_active_group_open_others_closed(
        self, client: TestClient, href: str, group_id: str
    ) -> None:
        html = client.get(href).text
        details = re.findall(r"<details[^>]*data-nav-group=\"([^\"]+)\"[^>]*>", html)
        assert details, "no collapsible groups rendered"
        for tag in re.findall(r"<details[^>]*>", html):
            if 'data-nav-group="' not in tag:
                continue
            gid = re.search(r'data-nav-group="([^"]+)"', tag).group(1)
            is_open = re.search(r"\sopen(\s|>|$)", tag) is not None
            assert is_open == (gid == group_id), f"{gid} open={is_open} on {href}"

    def test_active_item_has_aria_current_once(self, client: TestClient) -> None:
        html = client.get("/ui/tools").text
        assert html.count('aria-current="page"') == 1
        assert re.search(r'href="/ui/tools"\s+class="mp-nav-item mp-nav-item--active"', html)

    def test_group_has_chevron_and_hidden_decoration(self, client: TestClient) -> None:
        html = client.get("/ui/").text
        assert "mp-nav-group__chevron" in html
        assert 'aria-hidden="true"' in html

    def test_nav_landmark_is_labelled(self, client: TestClient) -> None:
        html = client.get("/ui/").text
        assert 'aria-label="Workspace modules"' in html
        assert 'aria-label="Main navigation"' in html


class TestResponsiveShell:
    def test_mobile_menu_button_controls_sidebar(self, client: TestClient) -> None:
        html = client.get("/ui/").text
        assert 'id="mp-sidebar"' in html
        assert 'aria-controls="mp-sidebar"' in html
        assert 'aria-expanded="false"' in html
        assert "data-mp-nav-toggle" in html

    def test_skip_link_targets_main(self, client: TestClient) -> None:
        html = client.get("/ui/").text
        assert 'href="#mp-main-content"' in html
        assert 'id="mp-main-content"' in html

    def test_shell_script_served(self, client: TestClient) -> None:
        html = client.get("/ui/").text
        assert "/static/js/app-shell.js" in html
        js = client.get("/static/js/app-shell.js")
        assert js.status_code == 200
        assert "localStorage" in js.text and "try" in js.text

    def test_drawer_css_present(self, client: TestClient) -> None:
        css = client.get("/static/design-system.css").text
        assert "@media (max-width: 900px)" in css
        assert ".mp-shell--nav-open .mp-sidebar" in css
        assert "--mp-focus-ring" in css

    def test_brand_uses_correct_product_name(self, client: TestClient) -> None:
        html = client.get("/ui/cad-import").text
        assert '<div class="mp-sidebar__brand-title">MachiningPro AI</div>' in html
