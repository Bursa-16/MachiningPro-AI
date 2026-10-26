"""
Cutting Tool Catalog import pipeline.

Accepts CSV or JSON input (as string content).
Idempotent: duplicate stable_ids are flagged and skipped.
Dry-run: validates records without modifying the in-memory catalog.

MISSING_VALUE_AS_ZERO=NO — all unknown numeric fields stay None.
FABRICATED_TOOL_SPEC=NO — callers must supply published specs only.
PRIVATE_SOURCE_PATH_EXPOSED=NO
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field

from .catalog_models import CuttingToolCatalogRecord
from .seed_catalog import get_catalog

# ── Result type ───────────────────────────────────────────────────────────────


@dataclass
class ImportPipelineResult:
    total_parsed: int = 0
    valid: int = 0
    invalid: int = 0
    duplicate: int = 0
    added: int = 0          # 0 in dry-run
    dry_run: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    added_ids: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)
    invalid_ids: list[str] = field(default_factory=list)


# ── Internal helpers ──────────────────────────────────────────────────────────

_REQUIRED_FIELDS = {
    "stable_id", "manufacturer", "product_name",
    "tool_category", "tool_category_code",
    "supported_operations", "iso_material_groups",
    "source_title", "source_authority", "evidence_status",
}

_LIST_FIELDS = {"supported_operations", "iso_material_groups", "missing_fields"}

_FLOAT_FIELDS = {
    "insert_ic_mm", "insert_thickness_mm", "nose_radius_mm", "clearance_angle_deg",
    "cutting_diameter_mm", "shank_diameter_mm", "overall_length_mm",
    "cutting_length_mm", "flute_length_mm", "helix_angle_deg", "corner_radius_mm",
    "point_angle_deg", "vc_min_mpm", "vc_max_mpm", "fz_min_mm", "fz_max_mm",
    "fn_min_mm", "fn_max_mm", "ap_max_mm", "max_ap_mm", "max_ae_mm",
}

_INT_FIELDS = {"number_of_flutes", "max_rpm"}

_BOOL_FIELDS = {"through_coolant"}


def _coerce_value(key: str, raw: str) -> object:
    """Convert a raw CSV string to the correct Python type. Returns None for blank."""
    if raw == "" or raw is None:
        return None
    if key in _FLOAT_FIELDS:
        return float(raw)
    if key in _INT_FIELDS:
        return int(raw)
    if key in _BOOL_FIELDS:
        return raw.lower() in ("true", "1", "yes")
    if key in _LIST_FIELDS:
        return [s.strip() for s in raw.split("|") if s.strip()]
    return raw


def _parse_row(row: dict) -> tuple[CuttingToolCatalogRecord | None, str | None]:
    """Parse a single dict row; return (record, None) or (None, error_msg)."""
    missing_req = [f for f in _REQUIRED_FIELDS if not row.get(f)]
    if missing_req:
        sid = row.get("stable_id", "<unknown>")
        return None, f"{sid}: missing required fields: {', '.join(missing_req)}"

    coerced: dict = {}
    for key, raw in row.items():
        try:
            coerced[key] = _coerce_value(key, raw)
        except (ValueError, TypeError) as exc:
            sid = row.get("stable_id", "<unknown>")
            return None, f"{sid}: field '{key}' coercion failed: {exc}"

    # Ensure list fields are lists even if empty
    for lf in _LIST_FIELDS:
        if coerced.get(lf) is None:
            coerced[lf] = []

    # missing_fields computed from None optional fields
    if not coerced.get("missing_fields"):
        optional = [
            k for k, v in coerced.items()
            if v is None and k not in _REQUIRED_FIELDS
        ]
        coerced["missing_fields"] = optional

    try:
        record = CuttingToolCatalogRecord(**coerced)
        return record, None
    except Exception as exc:
        sid = coerced.get("stable_id", "<unknown>")
        return None, f"{sid}: validation error: {exc}"


# ── Public parsers ────────────────────────────────────────────────────────────


def parse_csv_tools(csv_content: str) -> list[dict]:
    """Parse CSV string into list of raw dicts (headers → values)."""
    reader = csv.DictReader(io.StringIO(csv_content))
    return [dict(row) for row in reader]


def parse_json_tools(json_content: str) -> list[dict]:
    """Parse JSON string (array of objects) into list of raw dicts."""
    data = json.loads(json_content)
    if not isinstance(data, list):
        raise ValueError("JSON input must be an array of tool objects")
    return data


# ── Pipeline entry point ──────────────────────────────────────────────────────


def run_import_pipeline(
    rows: list[dict],
    *,
    dry_run: bool = True,
) -> ImportPipelineResult:
    """
    Validate and optionally import tool records.

    Parameters
    ----------
    rows:     Raw dicts from parse_csv_tools or parse_json_tools.
    dry_run:  When True (default), validate without modifying the catalog.
              When False, add valid non-duplicate records to the in-memory catalog
              (imported records are not persisted across process restarts).
    """
    result = ImportPipelineResult(total_parsed=len(rows), dry_run=dry_run)

    existing_ids: set[str] = {r.stable_id for r in get_catalog()}
    new_records: list[CuttingToolCatalogRecord] = []

    for row in rows:
        record, error = _parse_row(row)
        if error:
            result.invalid += 1
            result.errors.append(error)
            sid = row.get("stable_id", "<unknown>")
            result.invalid_ids.append(sid)
            continue

        assert record is not None
        if record.stable_id in existing_ids:
            result.duplicate += 1
            result.duplicate_ids.append(record.stable_id)
            result.warnings.append(
                f"{record.stable_id}: already in catalog — skipped (idempotent)"
            )
            continue

        result.valid += 1
        new_records.append(record)
        existing_ids.add(record.stable_id)

    if not dry_run:
        from .seed_catalog import _RECORDS  # noqa: PLC0415
        _RECORDS.extend(new_records)
        result.added = len(new_records)
        result.added_ids = [r.stable_id for r in new_records]
    else:
        result.added_ids = [r.stable_id for r in new_records]

    return result
