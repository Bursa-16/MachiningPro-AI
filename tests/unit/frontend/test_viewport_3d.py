"""UI-VISUAL-1E — Interactive 3D engineering viewport tests.

Asserts that the workstation mounts a real WebGL/Three.js viewport engine,
that the engine exposes the full interactive capability surface (orbit, pan,
zoom, picking, display modes, view cube, fit/reset, tree synchronization,
toolpath preview, resize handling, WebGL fallback), and that the existing
landing/workstation/CAD-import pages remain intact (UI-VISUAL-1D layout
preservation).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from frontend.app import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def workspace_html(client: TestClient) -> str:
    return client.get("/ui/").text


@pytest.fixture()
def viewport_js(client: TestClient) -> str:
    return client.get("/static/js/machining-3d-viewport.js").text


@pytest.fixture()
def three_js(client: TestClient) -> str:
    return client.get("/static/js/vendor/three.min.js").text


@pytest.fixture()
def css(client: TestClient) -> str:
    return client.get("/static/design-system.css").text


class TestWorkspaceMount:
    """The workstation must load the interactive 3D viewport."""

    def test_3d_viewport_container(self, workspace_html: str) -> None:
        assert 'id="mp-3d-viewport"' in workspace_html
        assert "data-3d-viewport" in workspace_html
        assert "mp-3d-viewport" in workspace_html

    def test_three_engine_loaded(self, workspace_html: str) -> None:
        assert "/static/js/vendor/three.min.js" in workspace_html

    def test_viewport_engine_loaded(self, workspace_html: str) -> None:
        assert "/static/js/machining-3d-viewport.js" in workspace_html

    def test_scripts_are_deferred(self, workspace_html: str) -> None:
        assert 'src="/static/js/vendor/three.min.js" defer' in workspace_html
        assert 'src="/static/js/machining-3d-viewport.js" defer' in workspace_html

    def test_display_mode_controls(self, workspace_html: str) -> None:
        for mode in ("shaded", "edges", "wireframe", "transparent"):
            assert f'data-vp-mode="{mode}"' in workspace_html

    def test_view_cube_controls(self, workspace_html: str) -> None:
        for view in ("iso", "top", "front", "right", "back", "left", "bottom"):
            assert f'data-vp-view="{view}"' in workspace_html
        assert "mp-view-cube" in workspace_html

    def test_toolbar_tools(self, workspace_html: str) -> None:
        for tool in ("axes", "toolpath", "dims", "section", "fit", "reset"):
            assert f'data-vp-tool="{tool}"' in workspace_html

    def test_static_svg_fallback_kept(self, workspace_html: str) -> None:
        # The deterministic 2D prerender remains as a no-JS / fallback layer.
        assert "mp-engineering-svg" in workspace_html


class TestViewportEngineCapabilities:
    """The engine JS must implement the full interactive capability surface."""

    def test_webgl_guard_and_fallback(self, viewport_js: str) -> None:
        assert "checkWebGL" in viewport_js
        assert "showFallback" in viewport_js
        assert "WebGLRenderingContext" in viewport_js

    def test_bootstrap_survives_deferred_script_evaluation(self, viewport_js: str) -> None:
        """Regression: v0.1.0-alpha.4 shipped a bootstrap that checked
        ``window.MP3D`` before the namespace was exported, so under
        ``<script defer>`` (readyState "interactive", not "loading") the
        immediate bootstrap call silently skipped ``init()`` and the
        workstation rendered an empty viewport. The export must therefore
        appear before the bootstrap block, and the bootstrap must call the
        in-scope ``MP3D`` closure reference rather than ``window.MP3D``.
        """
        export_pos = viewport_js.find("window.MP3D = MP3D;")
        bootstrap_pos = viewport_js.find("function bootstrapMP3D")
        assert export_pos != -1, "window.MP3D export missing"
        assert bootstrap_pos != -1, "bootstrapMP3D missing"
        assert export_pos < bootstrap_pos, (
            "window.MP3D must be exported BEFORE the bootstrap block: "
            "deferred scripts evaluate in readyState 'interactive', so the "
            "bootstrap runs immediately at evaluation time"
        )
        assert "window.MP3D.init" not in viewport_js, (
            "bootstrap must call the in-scope MP3D closure, not window.MP3D"
        )
        assert 'MP3D.init(mount.id' in viewport_js

    def test_orbit_interaction(self, viewport_js: str) -> None:
        assert "onPointerDown" in viewport_js
        assert "orbitBy" in viewport_js
        assert "pointerdown" in viewport_js

    def test_pan_interaction(self, viewport_js: str) -> None:
        assert "panBy" in viewport_js

    def test_zoom_interaction(self, viewport_js: str) -> None:
        assert "onWheel" in viewport_js
        assert "zoomBy" in viewport_js

    def test_display_modes(self, viewport_js: str) -> None:
        assert "setDisplayMode" in viewport_js
        assert "wireframe" in viewport_js
        assert "transparent" in viewport_js

    def test_shaded_with_edges_mode(self, viewport_js: str) -> None:
        assert "EdgesGeometry" in viewport_js

    def test_object_picking_raycasting(self, viewport_js: str) -> None:
        assert "THREE.Raycaster()" in viewport_js
        assert "intersectObjects" in viewport_js

    def test_tree_to_3d_sync(self, viewport_js: str) -> None:
        assert "data-tree-row" in viewport_js
        assert "mp-tree-row--active" in viewport_js

    def test_view_cube_orientations(self, viewport_js: str) -> None:
        assert "setView" in viewport_js
        for key in ("front", "back", "right", "left", "top", "bottom", "iso"):
            assert key in viewport_js

    def test_fit_and_reset(self, viewport_js: str) -> None:
        assert "fitToScene" in viewport_js
        assert "resetView" in viewport_js

    def test_toolpath_preview_toggle(self, viewport_js: str) -> None:
        assert "showToolpath" in viewport_js

    def test_resize_handling(self, viewport_js: str) -> None:
        assert "onResize" in viewport_js
        assert "resize" in viewport_js

    def test_reduced_motion_respected(self, viewport_js: str) -> None:
        assert "prefers-reduced-motion" in viewport_js

    def test_operation_switching(self, viewport_js: str) -> None:
        assert "setOperation" in viewport_js
        assert "mp-3d-operation" in viewport_js

    def test_scene_objects(self, viewport_js: str) -> None:
        for obj in ("workpiece", "chuck", "tool", "toolpath"):
            assert obj in viewport_js

    def test_ready_event(self, viewport_js: str) -> None:
        assert "mp-3d-viewport-ready" in viewport_js


class TestViewportAssetsPolicy:
    def test_three_engine_served(self, three_js: str) -> None:
        assert "THREE" in three_js

    def test_viewport_js_served(self, viewport_js: str) -> None:
        assert "window.MP3D = MP3D" in viewport_js

    def test_no_external_urls_in_viewport_js(self, viewport_js: str) -> None:
        filtered = viewport_js.replace("http://www.w3.org/2000/svg", "")
        assert "http://" not in filtered
        assert "https://" not in filtered

    def test_css_viewport_classes(self, css: str) -> None:
        assert ".mp-3d-viewport" in css
        assert ".mp-view-cube" in css
        assert ".mp-vp-view" in css
        assert ".mp-viewport-fallback" in css


class TestLayoutFixesPreserved:
    """UI-VISUAL-1D layout contract must not regress."""

    def test_upper_region_not_empty(self, workspace_html: str) -> None:
        # Context bar + command strip + operation ribbon occupy the upper area.
        assert "mp-context-bar" in workspace_html
        assert "mp-command-strip" in workspace_html
        assert "mp-operation-ribbon" in workspace_html

    def test_workstation_grid_intact(self, workspace_html: str) -> None:
        assert "mp-engineering-viewport" in workspace_html
        assert "mp-model-tree" in workspace_html
        assert "mp-right-panel" in workspace_html

    def test_timeline_visible_or_reachable(self, workspace_html: str) -> None:
        assert "mp-process-timeline" in workspace_html
        assert 'data-step="validation"' in workspace_html


class TestNoRegression:
    def test_landing(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "MachineryPro AI" in resp.text

    def test_workspace(self, client: TestClient) -> None:
        assert client.get("/ui/").status_code == 200

    def test_cad_import(self, client: TestClient) -> None:
        assert client.get("/ui/cad-import").status_code == 200

    def test_health(self, client: TestClient) -> None:
        assert client.get("/health").json()["status"] == "ok"

    def test_app_title(self) -> None:
        assert app.title == "MachineryPro AI"
