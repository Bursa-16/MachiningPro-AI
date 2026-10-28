"""Test that all demo-critical pages have sidebar navigation entries."""
from pathlib import Path

NAV_FILE = Path("frontend/app/src/lib/navigation.ts")
REQUIRED_PATHS = [
    "process-capability",
    "manufacturing-plan",
    "drawing-parser",
    "cad-features",
    "process-routes",
]


class TestNavigationSidebar:
    def test_nav_file_exists(self):
        assert NAV_FILE.exists(), "navigation.ts not found"

    def test_process_capability_in_nav(self):
        content = NAV_FILE.read_text(encoding="utf-8")
        assert "process-capability" in content, "Process Capability not in sidebar navigation"

    def test_manufacturing_plan_in_nav(self):
        content = NAV_FILE.read_text(encoding="utf-8")
        assert "manufacturing-plan" in content, "Manufacturing Plan not in sidebar navigation"

    def test_drawing_parser_in_nav(self):
        content = NAV_FILE.read_text(encoding="utf-8")
        assert "drawing-parser" in content, "Drawing Parser not in sidebar navigation"

    def test_cad_features_in_nav(self):
        content = NAV_FILE.read_text(encoding="utf-8")
        assert "cad-features" in content, "CAD Features not in sidebar navigation"

    def test_process_routes_in_nav(self):
        content = NAV_FILE.read_text(encoding="utf-8")
        assert "process-routes" in content, "Process Routes not in sidebar navigation"

    def test_legacy_drawing_to_process_resolved(self):
        content = NAV_FILE.read_text(encoding="utf-8")
        # drawing-to-process removed to avoid confusion alongside drawing-parser
        assert "drawing-to-process" not in content, \
            "Legacy 'Drawing to Process' route still present alongside Drawing Parser"
