"""Stage 1 smoke test: verifies the skeleton imports cleanly and that the
pre-existing source material is still untouched in place.

Runs under pytest (``pytest``) or directly (``python tests/test_smoke.py``).
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import backend  # noqa: E402

SUBPACKAGES = [
    "core",
    "knowledge",
    "machining",
    "materials",
    "tooling",
    "machines",
    "process_planning",
    "cutting_parameters",
    "quality",
    "costing",
    "ai",
]


def test_version() -> None:
    assert isinstance(backend.__version__, str)
    assert backend.__version__.count(".") == 2


def test_subpackages_importable_and_documented() -> None:
    for name in SUBPACKAGES:
        module = importlib.import_module(f"backend.{name}")
        assert module.__doc__, f"backend.{name} is missing a docstring"


def test_source_material_present_and_untouched() -> None:
    # Stage 0 guarantee: existing material must remain in place, read-only.
    assert (ROOT / "Machinery_Article").is_dir(), "Machinery_Article folder missing"
    assert (ROOT / "Programlar").is_dir(), "Programlar folder missing"
    assert any((ROOT / "Programlar").glob("*.md")), "Programlar markdown reports missing"


def test_foundation_files_present() -> None:
    for relative in ("README.md", "pyproject.toml", ".gitignore", "config/app.yaml"):
        assert (ROOT / relative).is_file(), f"missing foundation file: {relative}"


if __name__ == "__main__":
    failures = 0
    for check in (
        test_version,
        test_subpackages_importable_and_documented,
        test_source_material_present_and_untouched,
        test_foundation_files_present,
    ):
        try:
            check()
            print(f"PASS {check.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {check.__name__}: {exc}")
    sys.exit(1 if failures else 0)
