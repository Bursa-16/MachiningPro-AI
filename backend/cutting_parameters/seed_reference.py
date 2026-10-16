"""Seed the CuttingParameterRegistry with REFERENCE_ONLY records.

Reads the external research report located at the path given by the
environment variable ``MACHININGPRO_CUTTING_PARAM_REF_PATH``.

Usage (in application startup or tests)::

    import os
    from backend.cutting_parameters.seed_reference import seed_reference_registry
    from backend.cutting_parameters.registry import CuttingParameterRegistry

    registry = CuttingParameterRegistry()
    report_path = os.environ.get("MACHININGPRO_CUTTING_PARAM_REF_PATH")
    n = seed_reference_registry(registry, report_path)

All records produced here carry ``EvidenceStatus.REFERENCE_ONLY``.
No record will pass ``is_authoritative``.  The registry enforces
duplicate-ID rejection, so calling this function twice on the same
registry instance raises ``KeyError`` on the second call — idempotency
must be ensured by the caller (typically by using a fresh registry or
gating on ``registry.has(id)`` before re-seeding).

Hard Rule compliance
--------------------
HARD RULE 02  VP100 and ToolLife968 empirical data are NOT used as
              cutting parameter sources.  This module reads only the
              external research report.
HARD RULE 10  RPM is not stored.  Vc is stored; RPM = 1000*Vc/(π*D)
              must be calculated at runtime.
HARD RULE 11  fz (FEED_PER_TOOTH / mm/tooth) and fn (FEED_PER_REV /
              mm/rev) are kept separate; no cross-operation conversion.
HARD RULE 12  ap (AXIAL_DEPTH_OF_CUT) is produced for TURNING and
              MILLING only.  DRILLING and REAMING omit ap because the
              source provides no ap column for those operations.
HARD RULE 22  Ingestion is reproducible: the registry is populated by
              running the parser on the same source file.  Idempotent
              when a fresh registry is used each time.
HARD RULE 28  Records are REFERENCE_ONLY — no ML labelling.
HARD RULE 29  CASE_D: source is general industry guidance (Quality C),
              integrated as REFERENCE_ONLY.
"""

from __future__ import annotations

import os
from pathlib import Path

from backend.cutting_parameters.models import EvidenceStatus
from backend.cutting_parameters.reference_parser import parse_reference_report
from backend.cutting_parameters.registry import CuttingParameterRegistry

__all__ = ["seed_reference_registry"]

_ENV_VAR = "MACHININGPRO_CUTTING_PARAM_REF_PATH"


def seed_reference_registry(
    registry: CuttingParameterRegistry,
    source_path: str | Path | None = None,
) -> int:
    """Parse the reference report and register all records.

    Args:
        registry: Registry instance to populate.  Must be mutable (i.e.
                  not have the same record IDs already registered).
        source_path: Path to the Markdown research report.  When ``None``
                     the value is read from the environment variable
                     ``MACHININGPRO_CUTTING_PARAM_REF_PATH``.

    Returns:
        Number of records registered.

    Raises:
        EnvironmentError: when *source_path* is None and the env var is
                          not set.
        FileNotFoundError: when the resolved path does not exist.
        ValueError: when the report is missing expected table sections.
        KeyError: when a record ID already exists in *registry* (registry
                  enforces duplicate rejection — the caller must not
                  seed twice on the same instance).
    """
    if source_path is None:
        raw = os.environ.get(_ENV_VAR)
        if not raw:
            raise OSError(
                f"Environment variable {_ENV_VAR!r} is not set and "
                "source_path was not supplied."
            )
        source_path = Path(raw)

    records = parse_reference_report(Path(source_path))

    for record in records:
        assert record.evidence_status is EvidenceStatus.REFERENCE_ONLY, (
            f"seed_reference_registry: unexpected evidence_status "
            f"{record.evidence_status!r} on record {record.record_id!r}. "
            "All reference records must be REFERENCE_ONLY."
        )
        registry.register(record)

    return len(records)
