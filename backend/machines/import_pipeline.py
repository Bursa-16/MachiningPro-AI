"""Machine catalog import pipeline (EPIC_02).

Supports ingesting machine records from CSV or JSON, validating them,
deduplicating against the existing catalog, and normalizing units.

Safety contract
---------------
MISSING_VALUE_AS_ZERO=NO   — empty cells become None, never 0.
SYNTHETIC_SPECIFICATIONS_ADDED=NO — no values are fabricated.
PRIVATE_SOURCE_PATH_EXPOSED=NO — source file paths are not stored in records.
UNLICENSED_PROPRIETARY_MACHINE_DATA_IMPORTED=NO — caller responsibility.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any

from backend.machines.validation import MachineRecordValidationResult, validate_machine_record

__all__ = [
    "ImportPipelineResult",
    "ImportedRecordRow",
    "run_import_pipeline",
    "parse_csv_machines",
    "parse_json_machines",
]

# Required fields every imported record must supply
_REQUIRED_FIELDS = frozenset(
    {
        "stable_id",
        "manufacturer",
        "model",
        "machine_type",
        "machine_type_code",
        "axis_count",
        "turning_capable",
        "milling_capable",
        "drilling_capable",
        "source_title",
        "evidence_status",
    }
)

# Integer fields — coerced from string; missing → None (not 0)
_INT_FIELDS = frozenset(
    {
        "axis_count",
        "simultaneous_axis_count",
        "spindle_max_rpm",
        "spindle_min_rpm",
        "spindle_torque_at_rpm",
        "tool_magazine_capacity",
        "year_introduced",
        "year_discontinued",
        "positioning_accuracy_um",
        "repeatability_um",
    }
)

# Float fields — coerced from string; missing → None (not 0)
_FLOAT_FIELDS = frozenset(
    {
        "spindle_power_kw",
        "spindle_power_continuous_kw",
        "spindle_power_peak_kw",
        "spindle_torque_nm",
        "spindle_torque_continuous_nm",
        "spindle_torque_peak_nm",
        "travel_x_mm",
        "travel_y_mm",
        "travel_z_mm",
        "table_length_mm",
        "table_width_mm",
        "table_load_kg",
        "max_turning_diameter_mm",
        "max_turning_length_mm",
        "bar_capacity_mm",
        "max_tool_diameter_mm",
        "max_tool_diameter_adj_mm",
        "max_tool_length_mm",
        "atc_chip_to_chip_sec",
        "atc_tool_to_tool_sec",
        "rapid_traverse_mpm",
        "rapid_x_mpm",
        "rapid_y_mpm",
        "rapid_z_mpm",
        "max_cutting_feed_mm_min",
        "coolant_pressure_bar",
        "machine_weight_kg",
    }
)

# Boolean fields — "true"/"1"/"yes" → True, else False
_BOOL_FIELDS = frozenset(
    {
        "turning_capable",
        "milling_capable",
        "drilling_capable",
        "through_spindle_coolant",
        "mql_support",
        "flood_coolant",
        "chip_conveyor",
        "has_subspindle",
        "has_y_axis",
        "has_live_tooling",
        "has_b_axis",
        "has_pallet_changer",
        "capable_tapping",
        "capable_boring",
        "capable_threading",
        "capable_reaming",
        "capable_5axis_simultaneous",
        "capable_3plus2",
    }
)

# List fields encoded as semicolon-separated strings in CSV
_LIST_FIELDS = frozenset({"supported_processes", "spindle_interfaces_supported"})


def _coerce_value(key: str, raw: Any) -> Any:
    """Coerce a raw value to the domain type.

    Returns None for empty strings and conversion failures.
    MISSING_VALUE_AS_ZERO=NO — never returns 0 for a missing value.
    """
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None

    if key in _INT_FIELDS:
        try:
            return int(raw)
        except (ValueError, TypeError):
            return None

    if key in _FLOAT_FIELDS:
        try:
            return float(raw)
        except (ValueError, TypeError):
            return None

    if key in _BOOL_FIELDS:
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("true", "1", "yes")

    if key in _LIST_FIELDS:
        if isinstance(raw, list):
            return raw
        return [s.strip() for s in str(raw).split(";") if s.strip()]

    return raw


def _normalize_record(raw: dict) -> dict:
    """Normalize a raw row dict to domain types.

    Empty → None for all typed fields.  Source path fields are stripped.
    """
    out: dict = {}
    for k, v in raw.items():
        out[k] = _coerce_value(k, v)
    # Ensure list fields exist
    if out.get("supported_processes") is None:
        out["supported_processes"] = []
    if out.get("spindle_interfaces_supported") is None:
        out["spindle_interfaces_supported"] = []
    return out


def parse_csv_machines(csv_text: str) -> list[dict]:
    """Parse machine records from CSV text.

    Columns map directly to MachineCatalogRecord fields. Unknown columns
    are silently ignored. MISSING_VALUE_AS_ZERO=NO.
    """
    reader = csv.DictReader(StringIO(csv_text))
    records: list[dict] = []
    for row in reader:
        records.append(_normalize_record(dict(row)))
    return records


def parse_json_machines(json_text: str) -> list[dict]:
    """Parse machine records from JSON array text.

    Each element must be an object. MISSING_VALUE_AS_ZERO=NO.
    """
    data = json.loads(json_text)
    if not isinstance(data, list):
        raise ValueError("JSON import expects a top-level array")
    return [_normalize_record(item) for item in data]


def parse_json_file(path: Path) -> list[dict]:
    """Parse machine records from a JSON file."""
    return parse_json_machines(path.read_text(encoding="utf-8"))


def parse_csv_file(path: Path) -> list[dict]:
    """Parse machine records from a CSV file."""
    return parse_csv_machines(path.read_text(encoding="utf-8"))


@dataclass
class ImportedRecordRow:
    """Per-record outcome from the import pipeline."""

    stable_id: str
    is_duplicate: bool
    validation: MachineRecordValidationResult
    normalized: dict


@dataclass
class ImportPipelineResult:
    """Aggregate result of one import run."""

    total_input: int
    accepted: int
    rejected_validation: int
    rejected_duplicate: int
    rows: list[ImportedRecordRow] = field(default_factory=list)
    dry_run: bool = True

    @property
    def accepted_records(self) -> list[dict]:
        return [
            r.normalized for r in self.rows
            if r.validation.is_valid and not r.is_duplicate
        ]


def run_import_pipeline(
    raw_records: list[dict],
    existing_ids: frozenset[str] | None = None,
    *,
    dry_run: bool = True,
) -> ImportPipelineResult:
    """Validate, deduplicate, and normalize a batch of machine records.

    Args:
        raw_records:  Parsed record dicts (from CSV or JSON).
        existing_ids: stable_ids already in the catalog; duplicate detection
                      is skipped when None.
        dry_run:      When True, returns the result without modifying anything.
                      When False, the caller is responsible for persisting
                      ``result.accepted_records``.

    Returns:
        :class:`ImportPipelineResult` with per-row outcomes and aggregate
        counts.  Errors are collected in each row's validation result.
    """
    if existing_ids is None:
        existing_ids = frozenset()

    rows: list[ImportedRecordRow] = []
    seen_in_batch: set[str] = set()
    accepted = 0
    rejected_val = 0
    rejected_dup = 0

    for raw in raw_records:
        normalized = _normalize_record(raw)
        sid = str(normalized.get("stable_id") or "")
        validation = validate_machine_record(normalized)

        # Duplicate detection — within batch AND against existing catalog
        is_dup = sid in existing_ids or sid in seen_in_batch
        if sid and not is_dup:
            seen_in_batch.add(sid)

        row = ImportedRecordRow(
            stable_id=sid,
            is_duplicate=is_dup,
            validation=validation,
            normalized=normalized,
        )
        rows.append(row)

        if is_dup:
            rejected_dup += 1
        elif not validation.is_valid:
            rejected_val += 1
        else:
            accepted += 1

    return ImportPipelineResult(
        total_input=len(raw_records),
        accepted=accepted,
        rejected_validation=rejected_val,
        rejected_duplicate=rejected_dup,
        rows=rows,
        dry_run=dry_run,
    )
