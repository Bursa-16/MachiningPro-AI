"""Root test conftest.py — test environment setup.

Sets TESSERACT_CMD for tests when Tesseract is installed at a standard OS
location but not on PATH. Production code uses only env var + shutil.which;
this conftest handles test-environment discovery.

HARDCODED_TESSERACT_PATH=NO (production code rule)
TEST_TESSERACT_DISCOVERY=AUTO (test infrastructure rule)
"""

from __future__ import annotations

import os
import shutil
import sys


def _discover_tesseract() -> str | None:
    """Discover Tesseract binary for the test environment."""
    # If already set (CI, docker, developer config), trust it
    env_val = os.environ.get("TESSERACT_CMD", "").strip()
    if env_val:
        return env_val

    # Try PATH first
    found = shutil.which("tesseract")
    if found:
        return found

    # Standard OS-specific installation locations (test-side discovery only)
    if sys.platform == "win32":
        candidates = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
    elif sys.platform == "darwin":
        candidates = [
            "/usr/local/bin/tesseract",
            "/opt/homebrew/bin/tesseract",
        ]
    else:
        candidates = [
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
        ]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    return None


_tesseract_cmd = _discover_tesseract()
if _tesseract_cmd and not os.environ.get("TESSERACT_CMD", "").strip():
    os.environ["TESSERACT_CMD"] = _tesseract_cmd
