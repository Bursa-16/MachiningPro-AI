"""VP100 registry seed function (Stage EMPIRICAL-01A).

Loads records from the VP100 source XLSX and populates the module-level
VP100EmpiricalRegistry.  Designed for application startup and for
reproducible testing.

Environment variable
--------------------
``MACHININGPRO_VP100_SOURCE_PATH``
    Path to the VP100 XLSX source file.  Used when *source_path* is not
    supplied explicitly.
"""

from __future__ import annotations

import os
from pathlib import Path

from backend.empirical.registry import VP100EmpiricalRegistry, get_vp100_registry
from backend.empirical.vp100_loader import load_vp100_records

__all__ = [
    "VP100_SOURCE_ENV_VAR",
    "seed_vp100_registry",
]

VP100_SOURCE_ENV_VAR = "MACHININGPRO_VP100_SOURCE_PATH"


def seed_vp100_registry(
    source_path: Path | str | None = None,
    *,
    registry: VP100EmpiricalRegistry | None = None,
    allow_reregister: bool = False,
) -> tuple[int, list[str]]:
    """Load VP100 data from the XLSX source and seed the registry.

    Parameters
    ----------
    source_path:
        Path to the VP100 XLSX.  Falls back to
        ``$MACHININGPRO_VP100_SOURCE_PATH`` when *None*.
    registry:
        Target registry.  Defaults to the module-level singleton
        (:func:`~backend.empirical.registry.get_vp100_registry`).
    allow_reregister:
        Passed to :meth:`~backend.empirical.registry.VP100EmpiricalRegistry.register_all`.
        Set *True* for idempotent re-seeding.

    Returns
    -------
    (count, rejections)
        *count* — number of records now in the registry.
        *rejections* — list of rejection reasons (empty when all 96 rows pass).

    Raises
    ------
    ValueError
        When *source_path* is not supplied and the environment variable is
        not set.
    FileNotFoundError
        When the resolved path does not exist.
    """
    if source_path is None:
        env_path = os.environ.get(VP100_SOURCE_ENV_VAR)
        if not env_path:
            raise ValueError(
                f"No VP100 source path supplied and {VP100_SOURCE_ENV_VAR} is not set."
            )
        source_path = Path(env_path)

    source_path = Path(source_path)

    records, rejections = load_vp100_records(source_path)

    target = registry if registry is not None else get_vp100_registry()
    count = target.register_all(records, allow_reregister=allow_reregister)

    return count, rejections
