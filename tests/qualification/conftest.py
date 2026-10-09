"""Add the scoring module to sys.path for tests."""
import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[2] / "docs" / "qualification" / "scoring"),
)
