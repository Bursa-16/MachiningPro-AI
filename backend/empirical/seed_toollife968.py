"""
Seed function for ToolLife968Registry.

Source path is resolved from env var MACHININGPRO_TOOLLIFE968_SOURCE_PATH.
No personal or machine-specific paths are hardcoded in this module.
"""

from __future__ import annotations

import os
from pathlib import Path

from backend.empirical.exceptions import EmpiricalDataError
from backend.empirical.toollife968_loader import load_toollife968_records
from backend.empirical.toollife968_registry import (
    ToolLife968Registry,
    get_toollife968_registry,
)

_ENV_VAR = "MACHININGPRO_TOOLLIFE968_SOURCE_PATH"


def seed_toollife968_registry(
    source_path: Path | None = None,
    registry: ToolLife968Registry | None = None,
) -> tuple[int, list[str]]:
    """
    Load ToolLife 968 records and seed the registry.

    Args:
        source_path: explicit workbook path. If None, reads env var
            MACHININGPRO_TOOLLIFE968_SOURCE_PATH.
        registry: registry instance to seed. Defaults to the process singleton.

    Returns:
        (record_count, rejections) tuple.

    Raises:
        EmpiricalDataError: if source path cannot be determined.
        FileNotFoundError: if the resolved path does not exist.
    """
    if source_path is None:
        env_val = os.environ.get(_ENV_VAR)
        if not env_val:
            raise EmpiricalDataError(
                f"ToolLife 968 source path not configured. "
                f"Set {_ENV_VAR} to the workbook path."
            )
        source_path = Path(env_val)

    if registry is None:
        registry = get_toollife968_registry()

    records, rejections = load_toollife968_records(source_path)
    registry.register_all(records)
    return len(records), rejections
